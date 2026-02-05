from __future__ import annotations
import pygame

class Button:
    def __init__(self, rect: pygame.Rect, text: str, col, cb=None, arg=None, icon=None, tooltip: str=""):
        self.rect = rect
        self.text = text
        self.col = col
        self.cb = cb
        self.arg = arg
        self.icon = icon
        self.disabled = False
        self.visible = True
        self.tooltip = tooltip

    def draw(self, surf, fonts):
        if not self.visible: return
        c = (60,60,60) if self.disabled else self.col
        pygame.draw.rect(surf, c, self.rect, border_radius=10)
        pygame.draw.rect(surf, (150,150,150), self.rect, 2, border_radius=10)
        if self.icon == "STAR":
            pygame.draw.circle(surf, (255,215,0), self.rect.center, self.rect.w//3)
        elif self.icon == "MENU":
            cx, cy = self.rect.center
            w = self.rect.w//2
            pygame.draw.line(surf, (240,240,240), (cx-w//2, cy-7), (cx+w//2, cy-7), 3)
            pygame.draw.line(surf, (240,240,240), (cx-w//2, cy), (cx+w//2, cy), 3)
            pygame.draw.line(surf, (240,240,240), (cx-w//2, cy+7), (cx+w//2, cy+7), 3)
        elif self.icon == "CLOSE":
            cx, cy = self.rect.center
            s = self.rect.w//4
            pygame.draw.line(surf, (255,100,100), (cx-s, cy-s), (cx+s, cy+s), 4)
            pygame.draw.line(surf, (255,100,100), (cx-s, cy+s), (cx+s, cy-s), 4)
        else:
            txt = fonts.s.render(self.text, True, (240,240,240))
            surf.blit(txt, (self.rect.centerx - txt.get_width()//2, self.rect.centery - txt.get_height()//2))

    def click(self, pos):
        if self.visible and (not self.disabled) and self.rect.collidepoint(pos) and self.cb:
            if self.arg is None: self.cb()
            else: self.cb(self.arg)
            return True
        return False
