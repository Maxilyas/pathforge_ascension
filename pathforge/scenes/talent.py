from __future__ import annotations
import pygame
from ..core.scene import Scene
from ..ui.widgets import Button
from ..settings import (
    T_PATH, T_PATH_FAST, T_PATH_MUD, T_PATH_CONDUCT, T_PATH_CRYO, T_PATH_MAGMA, T_PATH_RUNE
)

PATH_NAME = {
    T_PATH: "Standard",
    T_PATH_FAST: "Route",
    T_PATH_MUD: "Boue",
    T_PATH_CONDUCT: "Conducteur",
    T_PATH_CRYO: "Cryo",
    T_PATH_MAGMA: "Magma",
    T_PATH_RUNE: "Rune",
}

# Talent points are earned on boss waves (every 10 waves).
# The tree focuses on UNIQUE unlocks and major playstyle choices.

TALENTS = {
    # --- FORGE (path / terrain) ---
    "F1": {"name":"Essence Amplifiée", "desc":"+40 Pavés immédiatement.", "pos":(-2,0),
           "prereq":[], "exclusive":[], "col":(180,140,80),
           "effect":{"grant":{"paves":40}}},
    "F2": {"name":"Routes de Forge", "desc":"Débloque Route & Boue (tuiles).", "pos":(-2,1),
           "prereq":["F1"], "exclusive":[], "col":(180,140,80),
           "effect":{"unlock_paths":[T_PATH_FAST, T_PATH_MUD]}},
    "F3": {"name":"Conductivité", "desc":"Débloque Chemin Conducteur.", "pos":(-2,2),
           "prereq":["F2"], "exclusive":[], "col":(180,140,80),
           "effect":{"unlock_paths":[T_PATH_CONDUCT]}},
    "F4A": {"name":"Runes Vivantes", "desc":"Débloque Rune (rare) + aura de runes.", "pos":(-2,3),
            "prereq":["F3"], "exclusive":["F4B"], "col":(180,140,80),
            "effect":{"unlock_paths":[T_PATH_RUNE], "mods":{"rune_aura_radius":3, "rune_aura_dmg_mul":1.08, "rune_aura_range_mul":1.06}}},
    "F4B": {"name":"Cryo-Alchimie", "desc":"Débloque Chemin Cryo + ralentissement prolongé.", "pos":(-1,3),
            "prereq":["F3"], "exclusive":["F4A"], "col":(140,190,255),
            "effect":{"unlock_paths":[T_PATH_CRYO], "mods":{"cryo_tile_slow_extend":0.10}}},
    "F5": {"name":"Fonderie Magma", "desc":"Débloque Chemin Magma + brûlure plus fiable.", "pos":(-2,4),
           "prereq":["F3"], "exclusive":[], "col":(230,120,90),
           "effect":{"unlock_paths":[T_PATH_MAGMA], "mods":{"magma_burn_chance":0.35}}},
    "F6": {"name":"Protocole de Reforge", "desc":"Effacer un chemin rend ses pavés.", "pos":(-2,5),
           "prereq":["F5"], "exclusive":[], "col":(180,140,80),
           "effect":{"mods":{"flag_path_reforge_free":True}}},

    # --- ARSENAL (unlock towers / combat roles) ---
    "A1": {"name":"Artillerie", "desc":"Débloque Mortier (zone).", "pos":(0,0),
           "prereq":[], "exclusive":[], "col":(200,200,200),
           "effect":{"unlock_towers":["MORTAR"]}},
    "A2": {"name":"Précision", "desc":"Débloque Sniper (mono-cible).", "pos":(0,1),
           "prereq":["A1"], "exclusive":[], "col":(200,200,200),
           "effect":{"unlock_towers":["SNIPER"]}},
    "A3": {"name":"Relais", "desc":"Débloque Beacon (support).", "pos":(0,2),
           "prereq":["A1"], "exclusive":[], "col":(255,220,120),
           "effect":{"unlock_towers":["BEACON"]}},
    "A4A":{"name":"Munitions Perforantes", "desc":"Sniper +20% dégâts.", "pos":(-1,3),
           "prereq":["A2"], "exclusive":["A4B"], "col":(200,200,200),
           "effect":{"mods":{"tower_bonus":{"SNIPER":{"damage_mul":1.20}}}}},
    "A4B":{"name":"Doctrine Splash", "desc":"Projectiles: mini AOE (global).", "pos":(1,3),
           "prereq":["A2"], "exclusive":["A4A"], "col":(200,200,200),
           "effect":{"mods":{"flag_all_projectiles_splash":True}}},
    "A5": {"name":"Déchiquetage", "desc":"Touches: chance d'appliquer SHRED.", "pos":(0,4),
           "prereq":["A3"], "exclusive":[], "col":(200,200,200),
           "effect":{"mods":{"global_on_hit":{"SHRED":{"dur":2.0,"stacks":1,"chance":0.18}}}}},
    "A6": {"name":"Prime de Boss", "desc":"Boss: récompenses x2.", "pos":(0,5),
           "prereq":["A5"], "exclusive":[], "col":(255,220,120),
           "effect":{"mods":{"flag_boss_bounty":True}}},

    # --- ARCANA (elemental + hero) ---
    "C1": {"name":"Électromancie", "desc":"Débloque Tesla (chain).", "pos":(3,0),
           "prereq":[], "exclusive":[], "col":(120,170,255),
           "effect":{"unlock_towers":["TESLA"]}},
    "C2": {"name":"Cryomancie", "desc":"Débloque Cryo (slow).", "pos":(3,1),
           "prereq":["C1"], "exclusive":[], "col":(120,170,255),
           "effect":{"unlock_towers":["CRYO"], "mods":{"tower_bonus":{"CRYO":{"slow_strength_add":0.04}}}}},
    "C3": {"name":"Pyromancie", "desc":"Débloque Flame (DoT).", "pos":(3,2),
           "prereq":["C1"], "exclusive":[], "col":(255,150,110),
           "effect":{"unlock_towers":["FLAME"]}},
    "C4A":{"name":"Maîtrise des Arcs", "desc":"Tesla: +2 chains, shock plus long.", "pos":(2,3),
           "prereq":["C1"], "exclusive":["C4B"], "col":(120,170,255),
           "effect":{"mods":{"tower_bonus":{"TESLA":{"chains_add":2,"shock_dur_add":0.5}}, "flag_conduct_mastery":True}}},
    "C4B":{"name":"Maîtrise Thermique", "desc":"Flame: +2 stacks brûlure + chance BURN (global).", "pos":(4,3),
           "prereq":["C3"], "exclusive":["C4A"], "col":(255,150,110),
           "effect":{"mods":{"tower_bonus":{"FLAME":{"burn_stacks_add":2}}, "global_on_hit":{"BURN":{"dur":1.4,"stacks":1,"chance":0.10}}}}},
    "C5": {"name":"Onde de Choc", "desc":"Q : rayon +25% et applique VULN.", "pos":(3,4),
           "prereq":["C2"], "exclusive":[], "col":(200,255,255),
           "effect":{"mods":{"hero_shock_radius_mul":1.25, "hero_shock_apply_vuln":True}}},
    "C6": {"name":"Surcadence", "desc":"Overclock durée +20%.", "pos":(3,5),
           "prereq":["C5"], "exclusive":[], "col":(200,255,255),
           "effect":{"mods":{"overclock_dur_mul":1.20}}},
}

def _edges():
    out = []
    for nid, t in TALENTS.items():
        for p in t.get("prereq", []):
            out.append((p, nid))
    return out

EDGES = _edges()
START_NODES = [nid for nid, t in TALENTS.items() if not t.get("prereq")]

def _wrap_text(text: str, font, max_w: int) -> list[str]:
    words = (text or "").split()
    if not words:
        return [""]
    lines = []
    cur = words[0]
    for w in words[1:]:
        test = cur + " " + w
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines

class TalentScene(Scene):
    name = "TALENT"

    def __init__(self, game):
        super().__init__(game)
        self.stats = None
        self.btn_close = None

        self.sel = None
        self.hover = None

        # confirmation modal
        self.confirm_node = None
        self.btn_yes = None
        self.btn_no = None

        # layout
        self.node_r = 30
        self.pad = 40

    def enter(self, payload=None):
        self.stats = (payload or {}).get("stats", None)
        w, h = self.game.w, self.game.h
        self.btn_close = Button(pygame.Rect(w-60, 10, 50, 50), "X", (35,40,50), cb=self._close)
        self.sel = None
        self.hover = None
        self.confirm_node = None
        self._build_confirm_buttons()

    def _build_confirm_buttons(self):
        w, h = self.game.w, self.game.h
        mw, mh = 520, 220
        r = pygame.Rect(w//2 - mw//2, h//2 - mh//2, mw, mh)
        by = r.bottom - 64
        self.btn_yes = Button(pygame.Rect(r.x + 30, by, (mw//2) - 45, 44), "CONFIRMER", (60, 170, 120), cb=self._confirm_yes)
        self.btn_no  = Button(pygame.Rect(r.x + (mw//2) + 15, by, (mw//2) - 45, 44), "ANNULER", (170, 70, 70), cb=self._confirm_no)

    def _close(self, *_):
        self.request("BACK", None)

    def _confirm_yes(self, *_):
        if not self.stats or not self.confirm_node:
            self.confirm_node = None
            return
        nid = self.confirm_node
        t = TALENTS.get(nid)
        if not t:
            self.confirm_node = None
            return
        if self.stats.can_buy_node(nid, t.get("prereq", []), t.get("exclusive", [])):
            self.stats.buy_node(nid, t.get("effect", {}))
        self.confirm_node = None

    def _confirm_no(self, *_):
        self.confirm_node = None

    def handle_event(self, e):
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            if self.confirm_node:
                self.confirm_node = None
            else:
                self._close()
            return

        if e.type == pygame.MOUSEMOTION:
            mx, my = e.pos
            self.hover = self._hit_node(mx, my)
            return

        if e.type == pygame.MOUSEBUTTONDOWN:
            if self.btn_close and self.btn_close.click(e.pos):
                return

            # modal confirm
            if self.confirm_node:
                if self.btn_yes and self.btn_yes.click(e.pos):
                    return
                if self.btn_no and self.btn_no.click(e.pos):
                    return
                # click outside => cancel
                self.confirm_node = None
                return

            mx, my = e.pos
            nid = self._hit_node(mx, my)
            if nid and self.stats:
                self.sel = nid
                t = TALENTS[nid]
                # Don't auto-buy: open confirmation if buyable
                if self.stats.can_buy_node(nid, t.get("prereq", []), t.get("exclusive", [])):
                    self.confirm_node = nid
            return

    def _bbox(self):
        xs = [TALENTS[k]["pos"][0] for k in TALENTS]
        ys = [TALENTS[k]["pos"][1] for k in TALENTS]
        return min(xs), min(ys), max(xs), max(ys)

    def _fit_transform(self):
        # Reserve right panel so the tree never hides behind it.
        minx, miny, maxx, maxy = self._bbox()
        bw = (maxx-minx+1) * 140
        bh = (maxy-miny+1) * 110

        panel_w = 420
        reserve_w = panel_w + 40
        avail_w = self.game.w - self.pad*2 - reserve_w
        avail_h = self.game.h - self.pad*2 - 90
        scale = min(avail_w / max(1, bw), avail_h / max(1, bh), 1.0)

        ox = self.pad + (avail_w - bw*scale) / 2
        oy = 90 + (avail_h - bh*scale) / 2
        return ox, oy, scale, minx, miny

    def _node_xy(self, nid):
        ox, oy, scale, minx, miny = self._fit_transform()
        x, y = TALENTS[nid]["pos"]
        sx = ox + ((x - minx) * 140 + 70) * scale
        sy = oy + ((y - miny) * 110 + 55) * scale
        return int(sx), int(sy), max(10, int(self.node_r * scale))

    def _hit_node(self, mx, my):
        for nid in TALENTS:
            x, y, r = self._node_xy(nid)
            if (mx-x)**2 + (my-y)**2 <= r*r:
                return nid
        return None

    def _panel_node(self):
        # Tooltip shows on hover; if nothing hovered, show selected.
        return self.hover or self.sel

    def draw(self, screen):
        # dim backdrop
        s = pygame.Surface((self.game.w, self.game.h), pygame.SRCALPHA)
        s.fill((0,0,0,220))
        screen.blit(s, (0,0))

        if self.btn_close:
            self.btn_close.draw(screen, self.game.fonts)

        title = self.game.fonts.l.render(f"TALENTS  (Pts: {getattr(self.stats,'talent_pts',0)})", True, (240,240,240))
        screen.blit(title, (self.game.w//2 - title.get_width()//2, 20))

        legend = self.game.fonts.s.render("Survole une node pour voir le tooltip. Clique pour demander confirmation.", True, (180,190,205))
        screen.blit(legend, (self.game.w//2 - legend.get_width()//2, 52))

        # edges
        for a, b in EDGES:
            ax, ay, _ = self._node_xy(a)
            bx, by, _ = self._node_xy(b)
            pygame.draw.line(screen, (90,90,100), (ax, ay), (bx, by), 3)

        owned_nodes = set(getattr(self.stats, "talent_nodes", set()) or [])

        # nodes
        for nid, t in TALENTS.items():
            x, y, r = self._node_xy(nid)
            owned = nid in owned_nodes
            can_buy = False
            if self.stats:
                can_buy = self.stats.can_buy_node(nid, t.get("prereq", []), t.get("exclusive", []))
            base = t.get("col", (200,200,200))
            col = base if (owned or can_buy) else (80,80,85)

            pygame.draw.circle(screen, col, (x,y), r)

            # Start marker
            if nid in START_NODES:
                pygame.draw.circle(screen, (255,215,0), (x,y), r+6, 2)
                tag = self.game.fonts.xs.render("DÉPART", True, (255,215,0))
                screen.blit(tag, (x - tag.get_width()//2, y - r - 18))

            # Hover highlight
            if self.hover == nid:
                pygame.draw.circle(screen, (240,240,255), (x,y), r+8, 2)

            pygame.draw.circle(screen, (20,20,25), (x,y), r, 3)
            if owned:
                pygame.draw.circle(screen, (255,215,0), (x,y), max(4, r//4), 0)

        # right info panel
        panel_w = 420
        panel_h = 260
        pr = pygame.Rect(self.game.w - panel_w - 20, self.game.h - panel_h - 20, panel_w, panel_h)
        pygame.draw.rect(screen, (25,30,40), pr, border_radius=14)
        pygame.draw.rect(screen, (120,130,150), pr, 2, border_radius=14)

        nid = self._panel_node()
        if nid and nid in TALENTS and self.stats:
            t = TALENTS[nid]
            owned = nid in owned_nodes
            can_buy = self.stats.can_buy_node(nid, t.get("prereq", []), t.get("exclusive", []))

            name = self.game.fonts.m.render(t["name"], True, (255,215,0) if owned else (240,240,240))
            screen.blit(name, (pr.x+16, pr.y+16))

            y = pr.y+54
            for dl in _wrap_text(t["desc"], self.game.fonts.s, panel_w-32)[:5]:
                desc = self.game.fonts.s.render(dl, True, (200,200,210))
                screen.blit(desc, (pr.x+16, y))
                y += 22

            st = "ACQUIS" if owned else ("ACHETABLE (clique)" if can_buy else "VERROUILLÉ")
            st_col = (120,255,160) if can_buy else ((255,215,0) if owned else (220,120,120))
            stt = self.game.fonts.s.render(st, True, st_col)
            screen.blit(stt, (pr.x+16, pr.y+160))

            eff = t.get("effect", {})
            u_t = eff.get("unlock_towers") or []
            u_p = eff.get("unlock_paths") or []
            yy = pr.y + 190
            if u_t:
                txt = self.game.fonts.s.render("Débloque tours: " + ", ".join(u_t), True, (210,210,220))
                screen.blit(txt, (pr.x+16, yy)); yy += 22
            if u_p:
                txt = self.game.fonts.s.render("Débloque chemins: " + ", ".join(PATH_NAME.get(int(x), str(x)) for x in u_p), True, (210,210,220))
                screen.blit(txt, (pr.x+16, yy)); yy += 22
        else:
            hint = self.game.fonts.s.render("Survole une node pour voir les détails.", True, (200,200,210))
            screen.blit(hint, (pr.x+16, pr.y+16))

        # confirmation modal
        if self.confirm_node and self.confirm_node in TALENTS and self.stats:
            mw, mh = 520, 220
            rr = pygame.Rect(self.game.w//2 - mw//2, self.game.h//2 - mh//2, mw, mh)
            pygame.draw.rect(screen, (15,18,25), rr, border_radius=16)
            pygame.draw.rect(screen, (200,200,210), rr, 2, border_radius=16)

            tt = TALENTS[self.confirm_node]
            h1 = self.game.fonts.m.render("Confirmer l'achat ?", True, (240,240,240))
            screen.blit(h1, (rr.centerx - h1.get_width()//2, rr.y+18))

            nm = self.game.fonts.s.render(f"{tt['name']}  (coût: 1 point)", True, (255,215,0))
            screen.blit(nm, (rr.centerx - nm.get_width()//2, rr.y+64))

            # show remaining points
            pts = getattr(self.stats, "talent_pts", 0)
            ptxt = self.game.fonts.s.render(f"Points restants après achat: {max(0, pts-1)}", True, (180,190,205))
            screen.blit(ptxt, (rr.centerx - ptxt.get_width()//2, rr.y+92))

            # buttons
            if self.btn_yes and self.btn_no:
                self.btn_yes.draw(screen, self.game.fonts)
                self.btn_no.draw(screen, self.game.fonts)
