from __future__ import annotations
import json
import random
from pathlib import Path
import pygame

from .settings import DEFAULT_W, DEFAULT_H, FPS, COLS, ROWS, TOP_BAR_FRAC, BOTTOM_BAR_FRAC
from .assets import make_fonts
from .core.time import GameClock
from .core.storage import SaveManager
from .core.balance_profile import load_profile, apply_profile
from .core.telemetry import Telemetry
from .systems.perk_factory import extend_with_procedural, PerkPool
from .scenes.menu import MenuScene
from .scenes.game import GameScene
from .scenes.pause import PauseScene
from .scenes.perk import PerkScene
from .scenes.settings_scene import SettingsScene
from .scenes.talent import TalentScene
from .scenes.bestiary import BestiaryScene


class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pathforge Ascension: V4.7.0")

        self.fullscreen = False
        self.w, self.h = DEFAULT_W, DEFAULT_H
        self.screen = pygame.display.set_mode((self.w, self.h))

        self.clock_pygame = pygame.time.Clock()
        self.clock = GameClock()

        ui_tile = max(12, min(self.w // COLS, int(((self.h - int(self.h*BOTTOM_BAR_FRAC)) - int(self.h*TOP_BAR_FRAC)) // ROWS)))
        self.fonts = make_fonts(ui_tile)

        self.saves = SaveManager()
        self.meta = self.saves.load_meta()

        base = Path(__file__).resolve().parent / "data"
        self.towers_db = json.loads((base / "towers.json").read_text(encoding="utf-8"))
        self.enemies_db = json.loads((base / "enemies.json").read_text(encoding="utf-8"))
        self.perks_db = json.loads((base / "perks.json").read_text(encoding="utf-8"))
        # Load optional balance profile (produced by the AutoBalancer)
        profile = load_profile()
        if profile:
            apply_profile(self.towers_db, self.enemies_db, profile)

        # Expand perk pool with thousands of procedural templates
        self.perks_db = extend_with_procedural(self.perks_db, self.towers_db)
        self.perk_pool = PerkPool(self.perks_db)

        self.biomes = json.loads((base / "biomes.json").read_text(encoding="utf-8"))

        self._perk_rng = random.Random()

        # --- telemetry (balancing & debug) ---
        import os as _os
        tel_env = str(_os.environ.get('PATHFORGE_TELEMETRY', '1')).strip().lower()
        tel_on = tel_env not in ('0','false','no','off')
        self.telemetry = Telemetry(enabled=tel_on)
        try:
            self.telemetry.start_run(seed=self._perk_rng.randint(0, 10**9), meta={'version':'v4_7_0'})
        except Exception:
            pass

        self.running = True
        self.request_save = False

        self.scene_stack = []
        self.scenes = {
            "MENU": MenuScene(self),
            "GAME": GameScene(self),
            "PAUSE": PauseScene(self),
            "PERK": PerkScene(self),
            "SETTINGS": SettingsScene(self),
            "TALENT": TalentScene(self),
            "BESTIARY": BestiaryScene(self),
        }
        self.scene = self.scenes["MENU"]
        self.scene.enter(None)

    def set_fullscreen(self, on: bool):
        self.fullscreen = on
        if on:
            info = pygame.display.Info()
            self.w, self.h = info.current_w, info.current_h
            self.screen = pygame.display.set_mode((self.w, self.h), pygame.FULLSCREEN)
        else:
            self.w, self.h = DEFAULT_W, DEFAULT_H
            self.screen = pygame.display.set_mode((self.w, self.h))

        ui_tile = max(12, min(self.w // COLS, int(((self.h - int(self.h*BOTTOM_BAR_FRAC)) - int(self.h*TOP_BAR_FRAC)) // ROWS)))
        self.fonts = make_fonts(ui_tile)

        # reset to menu (safe)
        self.scene_stack.clear()
        self.scene.exit()
        self.scene = self.scenes["MENU"]
        self.scene.enter(None)

    def roll_perks(self, n: int = 3, rarity_bias: float = 0.0) -> list[dict]:
        """Roll n perk options with rarity bias (0..0.6).
        Uses an indexed perk pool + procedural templates (thousands of possibilities).
        """
        if not hasattr(self, "perk_pool"):
            return list(self.perks_db)[:n]
        return self.perk_pool.roll(self._perk_rng, n=n, rarity_bias=rarity_bias)

    def loop(self):
        while self.running:
            dt = self.clock_pygame.tick(FPS) / 1000.0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                else:
                    self.scene.handle_event(event)

            self.scene.update(dt)

            res = self.scene.consume_result()
            if res.next_scene:
                overlays = {"PAUSE", "PERK", "TALENT", "BESTIARY"}
                if res.next_scene == "BACK":
                    if self.scene_stack:
                        self.scene.exit()
                        self.scene = self.scene_stack.pop()
                    else:
                        self.scene.exit()
                        self.scene = self.scenes["MENU"]
                        self.scene.enter(None)
                elif res.next_scene in overlays:
                    self.scene_stack.append(self.scene)
                    self.scene = self.scenes[res.next_scene]
                    self.scene.enter(res.payload)
                else:
                    self.scene_stack.clear()
                    self.scene.exit()
                    self.scene = self.scenes[res.next_scene]
                    self.scene.enter(res.payload)

            self.scene.draw(self.screen)
            pygame.display.flip()

        try:
            self.telemetry.close()
        except Exception:
            pass
        pygame.quit()


def run():
    Game().loop()