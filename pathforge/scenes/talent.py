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
        # draw the previous scene as background (if present)
        if self.game.scene_stack:
            self.game.scene_stack[-1].draw(screen)

        dim = pygame.Surface((self.game.w, self.game.h), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 210))
        screen.blit(dim, (0, 0))

        self.btn_close.draw(screen, self.game.fonts)
        title = self.game.fonts.l.render(f"ARBRE DE TALENTS (Pts: {self.stats.talent_pts})", True, (255, 215, 0))
        screen.blit(title, (self.game.w // 2 - title.get_width() // 2, 60))

        # --- Layout (auto-fit with safe margins) ---
        cell_x, cell_y = 170, 125
        node_w, node_h = 150, 74
        pad = 32

        # Build logical rects
        logical = {}
        for nid, gx, gy in LAYOUT:
            x = gx * cell_x
            y = gy * cell_y
            logical[nid] = pygame.Rect(x, y, node_w, node_h)

        minx = min(r.x for r in logical.values())
        miny = min(r.y for r in logical.values())
        maxx = max(r.right for r in logical.values())
        maxy = max(r.bottom for r in logical.values())
        bbox_w = max(1, (maxx - minx) + pad * 2)
        bbox_h = max(1, (maxy - miny) + pad * 2)

        # Keep a safe view that never touches screen edges
        view = pygame.Rect(80, 130, self.game.w - 160, self.game.h - 280)
        scale = min(1.0, view.w / bbox_w, view.h / bbox_h) * 0.95

        draw_w = bbox_w * scale
        draw_h = bbox_h * scale
        ox = view.x + (view.w - draw_w) / 2
        oy = view.y + (view.h - draw_h) / 2

        # Compute screen-space rects
        self.nodes_rects = {}
        for nid, rr in logical.items():
            sx = ox + ((rr.x - minx) + pad) * scale
            sy = oy + ((rr.y - miny) + pad) * scale
            sw = rr.w * scale
            sh = rr.h * scale
            self.nodes_rects[nid] = pygame.Rect(int(sx), int(sy), int(sw), int(sh))

        # links
        for nid, info in TALENTS.items():
            for pre in info.get("prereq", []):
                if pre in self.nodes_rects and nid in self.nodes_rects:
                    pygame.draw.line(
                        screen,
                        (90, 90, 105),
                        self.nodes_rects[pre].center,
                        self.nodes_rects[nid].center,
                        max(2, int(3 * scale)),
                    )

        # nodes
        for nid, rr in self.nodes_rects.items():
            info = TALENTS[nid]
            owned = nid in self.stats.talent_nodes
            prereq_ok = all(p in self.stats.talent_nodes for p in info.get("prereq", []))
            blocked = any(e in self.stats.talent_nodes for e in info.get("exclusive", []))
            can_buy = (not owned) and prereq_ok and (not blocked) and self.stats.talent_pts > 0

            border = (70, 70, 70)
            if owned:
                border = (70, 220, 140)
            elif can_buy:
                border = (255, 215, 0)
            elif blocked:
                border = (160, 70, 70)

            # shadow
            shad = pygame.Surface((rr.w + 8, rr.h + 8), pygame.SRCALPHA)
            pygame.draw.rect(shad, (0, 0, 0, 90), (6, 6, rr.w, rr.h), border_radius=max(10, int(12 * scale)))
            screen.blit(shad, (rr.x - 6, rr.y - 6))

            pygame.draw.rect(screen, (26, 28, 34), rr, border_radius=max(10, int(12 * scale)))
            pygame.draw.rect(screen, border, rr, max(2, int(3 * scale)), border_radius=max(10, int(12 * scale)))

            # hover highlight
            if self.hover == nid:
                pygame.draw.rect(screen, (255, 255, 255), rr, 1, border_radius=max(10, int(12 * scale)))

            # text
            fn_name = self.game.fonts.s if scale >= 0.92 else self.game.fonts.xs
            fn_desc = self.game.fonts.xs
            name = fn_name.render(info["name"], True, (240, 240, 240))
            desc = fn_desc.render(info["desc"], True, (200, 200, 200))
            screen.blit(name, (rr.x + 10, rr.y + int(10 * scale)))
            screen.blit(desc, (rr.x + 10, rr.y + int(40 * scale)))

