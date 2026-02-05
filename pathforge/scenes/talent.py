from __future__ import annotations
import pygame
from ..core.scene import Scene
from ..ui.widgets import Button

TALENTS = {
    "P1": {"name":"Forge Might", "desc":"+12% dégâts", "prereq":[], "exclusive":[], "effect":{"mods":{"dmg_mul":1.12}}},
    "P2": {"name":"Sharpen", "desc":"+10% cadence", "prereq":["P1"], "exclusive":[], "effect":{"mods":{"rate_mul":1.10}}},
    "P3A":{"name":"Execution", "desc":"Faiblesses +25%", "prereq":["P2"], "exclusive":["P3B"], "effect":{"mods":{"weakness_mul":2.05}}},
    "P3B":{"name":"Splashcraft", "desc":"Projectiles = mini AOE", "prereq":["P2"], "exclusive":["P3A"], "effect":{"mods":{"flag_all_projectiles_splash":True}}},
    "P4": {"name":"Overclock Protocol", "desc":"Overclock durée +25%", "prereq":["P3A"], "exclusive":[], "effect":{"mods":{"overclock_dur_mul":1.25}}},

    "U1": {"name":"Long Sight", "desc":"+12% portée", "prereq":[], "exclusive":[], "effect":{"mods":{"range_mul":1.12}}},
    "U2": {"name":"Chrono Sync", "desc":"Spells -10% CD", "prereq":["U1"], "exclusive":[], "effect":{"mods":{"spell_cd_mul":0.90}}},
    "U3A":{"name":"Permafrost", "desc":"Cryo slow +20%", "prereq":["U2"], "exclusive":["U3B"], "effect":{"mods":{"tower_bonus":{"CRYO":{"slow_strength_add":0.20}}}}},
    "U3B":{"name":"Arc Grid", "desc":"Tesla +2 chains", "prereq":["U2"], "exclusive":["U3A"], "effect":{"mods":{"tower_bonus":{"TESLA":{"chains_add":2}}}}},
    "U4": {"name":"Field Engineer", "desc":"Construire sur rochers", "prereq":["U3B"], "exclusive":[], "effect":{"mods":{"flag_build_on_rocks":True}}},

    "E1": {"name":"Rations", "desc":"+2 vies", "prereq":[], "exclusive":[], "effect":{"grant":{"lives":2}}},
    "E2": {"name":"Compound Interest", "desc":"+2% intérêt", "prereq":["E1"], "exclusive":[], "effect":{"mods":{"interest_add":0.02}}},
    "E3A":{"name":"Salvage Pact", "desc":"Revente 80%", "prereq":["E2"], "exclusive":["E3B"], "effect":{"mods":{"sell_refund":0.80}}},
    "E3B":{"name":"Core Fortify", "desc":"+12 bouclier", "prereq":["E2"], "exclusive":["E3A"], "effect":{"grant":{"core_shield":12}}},
    "E4": {"name":"Perk Rerolls", "desc":"+1 reroll", "prereq":["E3A"], "exclusive":[], "effect":{"mods":{"perk_rerolls_add":1}}},
}

LAYOUT = [
    ("P1", 0, 0), ("P2", 0, 1), ("P3A", -1, 2), ("P3B", 1, 2), ("P4", 0, 3),
    ("U1", 3, 0), ("U2", 3, 1), ("U3A", 2, 2), ("U3B", 4, 2), ("U4", 3, 3),
    ("E1", 6, 0), ("E2", 6, 1), ("E3A", 5, 2), ("E3B", 7, 2), ("E4", 6, 3),
]

class TalentScene(Scene):
    name="TALENT"
    def enter(self, payload=None):
        self.stats = payload["stats"]
        self.btn_close = Button(pygame.Rect(self.game.w-62, 12, 50, 50), "", (30,35,40), cb=self._close, icon="CLOSE", tooltip="Fermer (ESC)")
        self.nodes_rects = {}
        self.hover = None

    def _close(self):
        self.request("BACK", None)

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self._close()
        if event.type == pygame.MOUSEMOTION:
            self.hover = None
            for nid, rr in self.nodes_rects.items():
                if rr.collidepoint(event.pos):
                    self.hover = nid
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.btn_close.click(event.pos)
            for nid, rr in self.nodes_rects.items():
                if rr.collidepoint(event.pos):
                    t = TALENTS[nid]
                    if self.stats.can_buy_node(nid, t.get("prereq",[]), t.get("exclusive",[])):
                        self.stats.buy_node(nid, t.get("effect",{}))
                        mods = (t.get("effect") or {}).get("mods") or {}
                        if "perk_rerolls_add" in mods:
                            self.stats.perk_rerolls += int(mods["perk_rerolls_add"])

    def draw(self, screen):
        if self.game.scene_stack:
            self.game.scene_stack[-1].draw(screen)
        s = pygame.Surface((self.game.w, self.game.h), pygame.SRCALPHA)
        s.fill((0,0,0,210))
        screen.blit(s,(0,0))

        self.btn_close.draw(screen, self.game.fonts)
        title = self.game.fonts.l.render(f"ARBRE DE TALENTS (Pts: {self.stats.talent_pts})", True, (255,215,0))
        screen.blit(title, (self.game.w//2-title.get_width()//2, 60))

        base_x, base_y = 140, 140
        cell_x, cell_y = 150, 120
        self.nodes_rects = {}
        for nid, gx, gy in LAYOUT:
            x = base_x + gx*cell_x
            y = base_y + gy*cell_y
            self.nodes_rects[nid] = pygame.Rect(x, y, 130, 70)

        # links
        for nid, info in TALENTS.items():
            for pre in info.get("prereq", []):
                if pre in self.nodes_rects:
                    pygame.draw.line(screen, (120,120,140), self.nodes_rects[pre].center, self.nodes_rects[nid].center, 3)

        # nodes
        for nid, rr in self.nodes_rects.items():
            info = TALENTS[nid]
            owned = nid in self.stats.talent_nodes
            prereq_ok = all(p in self.stats.talent_nodes for p in info.get("prereq", []))
            blocked = any(e in self.stats.talent_nodes for e in info.get("exclusive", []))
            can_buy = (not owned) and prereq_ok and (not blocked) and self.stats.talent_pts > 0
            col = (70,70,70)
            if owned: col = (70,220,140)
            elif can_buy: col = (255,215,0)
            elif blocked: col = (160,70,70)
            pygame.draw.rect(screen, (26,28,34), rr, border_radius=12)
            pygame.draw.rect(screen, col, rr, 3, border_radius=12)
            name = self.game.fonts.xs.render(info["name"], True, (240,240,240))
            desc = self.game.fonts.xs.render(info["desc"], True, (200,200,200))
            screen.blit(name, (rr.x+10, rr.y+14))
            screen.blit(desc, (rr.x+10, rr.y+40))

        if self.hover:
            info = TALENTS[self.hover]
            mx,my = pygame.mouse.get_pos()
            lines = [info["name"], info["desc"], "Prereq: "+(", ".join(info.get("prereq",[])) or "—")]
            pad=10
            rend=[self.game.fonts.xs.render(l, True, (240,240,240)) for l in lines]
            w = max(r.get_width() for r in rend)+pad*2
            h = sum(r.get_height() for r in rend)+pad*2
            rect = pygame.Rect(mx+12, my+12, w, h)
            pygame.draw.rect(screen, (20,20,24), rect, border_radius=10)
            pygame.draw.rect(screen, (255,215,0), rect, 1, border_radius=10)
            y = rect.y+pad
            for r in rend:
                screen.blit(r, (rect.x+pad, y))
                y += r.get_height()
