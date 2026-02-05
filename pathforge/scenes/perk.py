from __future__ import annotations
import pygame
from ..core.scene import Scene

RAR_COL = {"C":(200,200,200),"R":(120,200,255),"E":(210,120,255),"L":(255,215,0),"SS+":(255,120,80),"SS++":(255,80,200)}

class PerkScene(Scene):
    name="PERK"
    def enter(self, payload=None):
        self.stats = payload["stats"]
        self.options = payload["options"]
        self.rerolls = int(self.stats.perk_rerolls)
        self.rng = payload.get("rng")
        self.towers = payload.get("towers", [])

    def _pick(self, idx: int):
        p = self.options[idx]
        self.stats.apply_perk(p)
        # Recalc tower-side dynamic mods if needed (simple approach: do nothing, towers read stats on tick)
        self.request("BACK", None)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                # no skip; force pick in real game; allow back here
                return
            if event.key == pygame.K_r:
                if self.rerolls > 0 and self.stats.fragments >= 25:
                    self.stats.fragments -= 25
                    self.rerolls -= 1
                    self.stats.perk_rerolls = self.rerolls
                    self.options = self.game.roll_perks(3, rarity_bias=0.0)  # reroll baseline
        if event.type == pygame.MOUSEBUTTONDOWN:
            mx,my = event.pos
            w,h = self.game.w, self.game.h
            cx, cy = w//2, h//2
            for i,p in enumerate(self.options):
                rr = pygame.Rect(cx-280, cy-180+i*130, 560, 110)
                if rr.collidepoint((mx,my)):
                    self._pick(i)

    def draw(self, screen):
        if self.game.scene_stack:
            self.game.scene_stack[-1].draw(screen)
        s = pygame.Surface((self.game.w, self.game.h), pygame.SRCALPHA)
        s.fill((0,0,0,205))
        screen.blit(s, (0,0))

        t = self.game.fonts.l.render("CHOIX DU BONUS", True, (255,215,0))
        screen.blit(t, (self.game.w//2 - t.get_width()//2, 90))

        cx, cy = self.game.w//2, self.game.h//2
        for i,p in enumerate(self.options):
            rr = pygame.Rect(cx-280, cy-180+i*130, 560, 110)
            pygame.draw.rect(screen, (38,42,52), rr, border_radius=16)
            rar = p.get("rarity","C")
            col = RAR_COL.get(rar, (220,220,220))
            pygame.draw.rect(screen, col, rr, 2, border_radius=16)

            name = self.game.fonts.m.render(p["name"], True, col)
            screen.blit(name, (rr.x+18, rr.y+18))
            tags = ", ".join(p.get("tags",[]))
            info = self.game.fonts.s.render(f"Rareté: {rar}   Tags: {tags}", True, (220,220,220))
            screen.blit(info, (rr.x+18, rr.y+52))

        hint = self.game.fonts.s.render(f"Clique pour choisir. R = reroll (25 fragments). Rerolls: {self.rerolls}", True, (200,200,200))
        screen.blit(hint, (self.game.w//2 - hint.get_width()//2, self.game.h-70))
