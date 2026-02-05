from __future__ import annotations
import pygame
from ..core.scene import Scene
from ..ui.widgets import Button

class PauseScene(Scene):
    name="PAUSE"

    def enter(self, payload=None):
        w, h = self.game.w, self.game.h

        def rc(w0: int, h0: int, yoff: int) -> pygame.Rect:
            return pygame.Rect(w//2 - w0//2, h//2 + yoff, w0, h0)

        self.btn_resume   = Button(rc(300, 60, -105), "REPRENDRE", (70, 80, 90), cb=self._back)
        self.btn_save     = Button(rc(300, 60,  -35), "SAUVEGARDER", (70, 80, 90), cb=self._save)
        self.btn_bestiary = Button(rc(300, 60,   35), "BESTIAIRE", (70, 80, 90), cb=self._bestiary)
        self.btn_quit     = Button(rc(300, 60,  105), "MENU", (160, 70, 70), cb=self._quit)

    def _back(self): self.request("BACK", None)
    def _save(self): self.game.request_save = True
    def _bestiary(self): self.request("BESTIARY", None)
    def _quit(self): self.request("MENU", None)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._back()
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.btn_resume.click(event.pos)
            self.btn_save.click(event.pos)
            self.btn_bestiary.click(event.pos)
            self.btn_quit.click(event.pos)

    def draw(self, screen):
        # Always draw the base (bottom-most) scene behind to avoid recursion with stacked overlays.
        if self.game.scene_stack:
            self.game.scene_stack[0].draw(screen)

        s = pygame.Surface((self.game.w, self.game.h), pygame.SRCALPHA)
        s.fill((0, 0, 0, 180))
        screen.blit(s, (0, 0))

        self.btn_resume.draw(screen, self.game.fonts)
        self.btn_save.draw(screen, self.game.fonts)
        self.btn_bestiary.draw(screen, self.game.fonts)
        self.btn_quit.draw(screen, self.game.fonts)
