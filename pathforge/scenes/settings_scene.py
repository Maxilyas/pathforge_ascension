from __future__ import annotations
import pygame
from ..core.scene import Scene
from ..ui.widgets import Button

class SettingsScene(Scene):
    name="SETTINGS"
    def enter(self, payload=None):
        w,h = self.game.w, self.game.h
        self.btn_back = Button(pygame.Rect(20,20,120,50), "RETOUR", (70,80,90), cb=self._back)
        self.btn_full = Button(pygame.Rect(w//2-160, h//2-30, 320, 70), "TOGGLE FULLSCREEN", (255,215,0), cb=self._toggle)

    def _back(self): self.request("MENU", None)
    def _toggle(self): self.game.set_fullscreen(not self.game.fullscreen)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.btn_back.click(event.pos)
            self.btn_full.click(event.pos)

    def draw(self, screen):
        screen.fill((10,12,16))
        t = self.game.fonts.l.render("OPTIONS", True, (255,215,0))
        screen.blit(t, (self.game.w//2 - t.get_width()//2, 90))
        self.btn_back.draw(screen, self.game.fonts)
        self.btn_full.draw(screen, self.game.fonts)
