from __future__ import annotations
import pygame
from ..core.scene import Scene
from ..ui.widgets import Button

class PauseScene(Scene):
    name="PAUSE"
    def enter(self, payload=None):
        w,h = self.game.w, self.game.h
        def rc(w0,h0, yoff):
            return pygame.Rect(w//2-w0//2, h//2+yoff, w0, h0)
        self.btn_resume = Button(rc(280,60,-70), "REPRENDRE", (70,80,90), cb=self._back)
        self.btn_save = Button(rc(280,60,0), "SAUVEGARDER", (70,80,90), cb=self._save)
        self.btn_quit = Button(rc(280,60,70), "MENU", (160,70,70), cb=self._quit)

    def _back(self): self.request("BACK", None)
    def _save(self): self.game.request_save = True
    def _quit(self): self.request("MENU", None)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.btn_resume.click(event.pos)
            self.btn_save.click(event.pos)
            self.btn_quit.click(event.pos)

    def draw(self, screen):
        if self.game.scene_stack:
            self.game.scene_stack[-1].draw(screen)
        s = pygame.Surface((self.game.w, self.game.h), pygame.SRCALPHA)
        s.fill((0,0,0,180))
        screen.blit(s, (0,0))
        self.btn_resume.draw(screen, self.game.fonts)
        self.btn_save.draw(screen, self.game.fonts)
        self.btn_quit.draw(screen, self.game.fonts)
