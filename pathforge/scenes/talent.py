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

from ..data.talents_db import TALENTS, EDGES, START_NODES, ALL_NODES

NODES = [nid for nid in ALL_NODES if not (TALENTS.get(nid,{}).get('prereq') or [])]

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
