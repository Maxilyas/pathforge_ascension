from __future__ import annotations
import json
import random
from pathlib import Path
import pygame

from .settings import DEFAULT_W, DEFAULT_H, FPS, COLS
from .assets import make_fonts
from .core.time import GameClock
from .core.storage import SaveManager
from .scenes.menu import MenuScene
from .scenes.game import GameScene
from .scenes.pause import PauseScene
from .scenes.perk import PerkScene
from .scenes.settings_scene import SettingsScene
from .scenes.talent import TalentScene

class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Pathforge Ascension: V4")

        self.fullscreen = False
        self.w, self.h = DEFAULT_W, DEFAULT_H
        self.screen = pygame.display.set_mode((self.w, self.h))

        self.clock_pygame = pygame.time.Clock()
        self.clock = GameClock()

        self.fonts = make_fonts(self.w // COLS)

        self.saves = SaveManager()
        self.meta = self.saves.load_meta()

        base = Path(__file__).resolve().parent / "data"
        self.towers_db = json.loads((base/"towers.json").read_text(encoding="utf-8"))
        self.enemies_db = json.loads((base/"enemies.json").read_text(encoding="utf-8"))
        self.perks_db = json.loads((base/"perks.json").read_text(encoding="utf-8"))
        self.biomes = json.loads((base/"biomes.json").read_text(encoding="utf-8"))

        self._perk_rng = random.Random()

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
        self.fonts = make_fonts(self.w // COLS)

        # reset to menu (safe)
        self.scene_stack.clear()
        self.scene.exit()
        self.scene = self.scenes["MENU"]
        self.scene.enter(None)


    def roll_perks(self, n: int = 3, rarity_bias: float = 0.0) -> list[dict]:
        """Roll n perk options with rarity bias (0..0.6). No duplicates in a single roll."""
        weights = {"C": 66.0, "R": 22.0, "E": 9.0, "L": 2.0, "SS+": 0.8, "SS++": 0.2}
        b = max(0.0, min(0.60, float(rarity_bias)))
        # shift probability mass upward
        weights["C"] *= (1.0 - 0.70*b)
        weights["R"] *= (1.0 - 0.40*b)
        weights["E"] *= (1.0 + 0.70*b)
        weights["L"] *= (1.0 + 1.40*b)
        weights["SS+"] *= (1.0 + 2.00*b)
        weights["SS++"] *= (1.0 + 2.60*b)

        pool = list(self.perks_db)
        picks: list[dict] = []
        for _ in range(min(n, len(pool))):
            total = 0.0
            for p in pool:
                total += weights.get(p.get("rarity", "C"), 1.0)
            r = self._perk_rng.random() * total
            acc = 0.0
            chosen_idx = 0
            for i, p in enumerate(pool):
                acc += weights.get(p.get("rarity", "C"), 1.0)
                if acc >= r:
                    chosen_idx = i
                    break
            picks.append(pool.pop(chosen_idx))
        return picks

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
                overlays = {"PAUSE","PERK","TALENT"}
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

        pygame.quit()

def run():
    Game().loop()
