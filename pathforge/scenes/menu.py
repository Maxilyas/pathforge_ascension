from __future__ import annotations
import pygame
from ..core.scene import Scene
from ..ui.widgets import Button

class MenuScene(Scene):
    name="MENU"
    def enter(self, payload=None):
        w,h = self.game.w, self.game.h
        def rc(w0,h0, yoff):
            return pygame.Rect(w//2-w0//2, h//2+yoff, w0, h0)

        self.btn_new = Button(rc(320,78,-70), "NOUVELLE PARTIE", (70,80,90), cb=self._new)
        self.btn_cont = Button(rc(320,78,30), "CONTINUER", (255,215,0), cb=self._cont)
        self.btn_bestiary = Button(rc(320,78,130), "BESTIAIRE", (70,80,90), cb=self._bestiary)
        self.btn_settings = Button(rc(320,78,230), "OPTIONS", (70,80,90), cb=self._settings)

        self.btn_cont.disabled = (self.game.saves.load_run() is None)

    def _new(self):
        self.game.saves.clear_run()
        self.request("GAME", {"new": True})

    def _cont(self):
        self.request("GAME", {"new": False})

    def _bestiary(self):
        self.request("BESTIARY", None)

    def _settings(self):
        self.request("SETTINGS", None)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.btn_new.click(event.pos)
            self.btn_cont.click(event.pos)
            self.btn_bestiary.click(event.pos)
            self.btn_settings.click(event.pos)

    def draw(self, screen):
        screen.fill((12,14,18))
        t = self.game.fonts.xl.render("PATHFORGE ASCENSION — V4", True, (255,215,0))
        screen.blit(t, (self.game.w//2 - t.get_width()//2, 110))
        self.btn_new.draw(screen, self.game.fonts)
        self.btn_cont.draw(screen, self.game.fonts)
        self.btn_bestiary.draw(screen, self.game.fonts)
        self.btn_settings.draw(screen, self.game.fonts)
