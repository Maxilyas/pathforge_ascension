from __future__ import annotations
import json
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
