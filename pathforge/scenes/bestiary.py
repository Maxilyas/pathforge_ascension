from __future__ import annotations
import pygame
from ..core.scene import Scene
from ..ui.widgets import Button

# Small helper: wrapped text drawing
def _wrap_lines(text: str, font: pygame.font.Font, max_w: int) -> list[str]:
    if not text:
        return [""]
    words = text.replace("\n", " \n ").split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        if w == "\n":
            lines.append(cur.rstrip())
            cur = ""
            continue
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur.rstrip())
            cur = w
    if cur:
        lines.append(cur.rstrip())
    return lines or [""]

class BestiaryScene(Scene):
    name = "BESTIARY"

    def enter(self, payload=None):
        w, h = self.game.w, self.game.h
        self.btn_back = Button(pygame.Rect(20, 20, 120, 50), "RETOUR", (70, 80, 90), cb=self._back)

        # Build list of enemies from db
        edb: dict = self.game.enemies_db
        order = [k for k in edb.keys() if k != "BOSS"] + (["BOSS"] if "BOSS" in edb else [])
        self.items = []
        for k in order:
            a = edb[k]
            self.items.append((k, a))

        # selection + scroll
        self.sel = 0
        self.scroll = 0
        self.detail_scroll = 0
        self.row_h = 58
        self.list_pad = 18

        # Precompute tower matchups by dmg_type
        self.towers_by_type = {}
        for tk, t in self.game.towers_db.items():
            dt = t.get("dmg_type", "KINETIC")
            self.towers_by_type.setdefault(dt, []).append((tk, t))

        self.dmg_colors = {
            "KINETIC": (255, 170, 0),
            "PIERCE": (200, 80, 220),
            "ENERGY": (90, 150, 255),
            "FIRE": (255, 90, 70),
            "COLD": (0, 230, 255),
            "EXPLOSIVE": (255, 190, 80),
            "BIO": (120, 240, 120),
        }

        self.dmg_names = {
            "KINETIC": "Cinétique",
            "PIERCE": "Perçant",
            "ENERGY": "Énergie",
            "FIRE": "Feu",
            "COLD": "Cryo",
            "EXPLOSIVE": "Explosif",
            "BIO": "Biologique",
        }

    def _back(self):
        self.request("BACK", None)

    def _clamp_scroll(self):
        list_h = self.game.h - 160
        total_h = len(self.items) * self.row_h
        max_scroll = max(0, total_h - list_h)
        self.scroll = max(0, min(self.scroll, max_scroll))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self._back()
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.sel = min(len(self.items) - 1, self.sel + 1)
                self.detail_scroll = 0
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.sel = max(0, self.sel - 1)
                self.detail_scroll = 0
            elif event.key == pygame.K_PAGEUP:
                self.scroll -= self.row_h * 6
            elif event.key == pygame.K_PAGEDOWN:
                self.scroll += self.row_h * 6
            self._clamp_scroll()

        if event.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            list_rect = pygame.Rect(30, 120, int(self.game.w * 0.38), self.game.h - 160)
            detail_rect = pygame.Rect(list_rect.right + 20, 120, self.game.w - list_rect.right - 50, self.game.h - 160)
            if detail_rect.collidepoint((mx, my)):
                self.detail_scroll -= event.y * 46
            else:
                self.scroll -= event.y * 40
                self._clamp_scroll()


        if event.type == pygame.MOUSEBUTTONDOWN:
            self.btn_back.click(event.pos)

            # click list row
            mx, my = event.pos
            list_rect = pygame.Rect(30, 120, int(self.game.w * 0.38), self.game.h - 160)
            if list_rect.collidepoint((mx, my)):
                rel_y = my - list_rect.y + self.scroll
                idx = int(rel_y // self.row_h)
                if 0 <= idx < len(self.items):
                    self.sel = idx
                    self.detail_scroll = 0
                    self._clamp_scroll()

    def update(self, dt: float):
        # keep selection in view
        list_h = self.game.h - 160
        y = self.sel * self.row_h
        if y < self.scroll:
            self.scroll = y
        elif y > self.scroll + list_h - self.row_h:
            self.scroll = y - (list_h - self.row_h)
        self._clamp_scroll()

    def _tower_score(self, enemy_arch: dict, tower: dict) -> float:
        dt = tower.get("dmg_type", "KINETIC")
        score = 1.0

        # resistances: lower multiplier => harder to kill
        resist = enemy_arch.get("resist") or {}
        try:
            rm = float(resist.get(dt, 1.0))
        except Exception:
            rm = 1.0
        score *= max(0.25, rm)

        # weakness multiplier (from stats default)
        weak = enemy_arch.get("weak")
        try:
            from ..stats import CombatStats
            wm = CombatStats().weakness_mul
        except Exception:
            wm = 1.8
        if weak and dt == weak:
            score *= wm

        armor = float(enemy_arch.get("armor", 0))
        if armor >= 6:
            if dt == "KINETIC":
                score *= 0.65
            elif dt == "PIERCE":
                score *= 1.12

        shield = float(enemy_arch.get("shield", 0))
        if shield >= 50:
            sh_mult = enemy_arch.get("shield_mult") or {}
            try:
                sm = float(sh_mult.get(dt, 1.0))
            except Exception:
                sm = 1.0
            score *= sm
            if dt == "ENERGY":
                score *= 1.10

        tags = set(enemy_arch.get("tags", []) or [])
        if "REGEN" in tags and dt == "FIRE":
            score *= 1.18

        # small heuristics for roles
        role = tower.get("role", "")
        if "FAST" in tags and role in ("CONTROL","AOE","CHAIN"):
            score *= 1.05

        return score

    def _effectiveness_label(self, enemy_arch: dict, tower: dict) -> tuple[str, tuple[int,int,int]]:
        s = self._tower_score(enemy_arch, tower)
        if s >= 2.4:
            return "TRÈS EFFICACE", (120, 240, 160)
        if s >= 1.5:
            return "EFFICACE", (170, 245, 190)
        if s >= 0.95:
            return "OK", (210, 210, 210)
        if s >= 0.70:
            return "FAIBLE", (255, 170, 130)
        return "MAUVAIS", (255, 120, 120)


    def draw(self, screen):
        # If opened as an overlay (e.g., from Pause), draw the base scene behind (avoid recursion).
        if self.game.scene_stack:
            self.game.scene_stack[0].draw(screen)
            s = pygame.Surface((self.game.w, self.game.h), pygame.SRCALPHA)
            s.fill((0, 0, 0, 210))
            screen.blit(s, (0, 0))
        else:
            screen.fill((10, 12, 16))

        w, h = self.game.w, self.game.h

        # header
        title = self.game.fonts.xl.render("BESTIAIRE", True, (255, 215, 0))
        screen.blit(title, (w // 2 - title.get_width() // 2, 34))
        self.btn_back.draw(screen, self.game.fonts)

        # panels
        list_rect = pygame.Rect(30, 120, int(w * 0.38), h - 160)
        detail_rect = pygame.Rect(list_rect.right + 20, 120, w - list_rect.right - 50, h - 160)

        pygame.draw.rect(screen, (18, 22, 28), list_rect, border_radius=14)
        pygame.draw.rect(screen, (60, 70, 80), list_rect, 2, border_radius=14)

        pygame.draw.rect(screen, (18, 22, 28), detail_rect, border_radius=14)
        pygame.draw.rect(screen, (60, 70, 80), detail_rect, 2, border_radius=14)

        # list content (clipped)
        clip_prev = screen.get_clip()
        screen.set_clip(list_rect.inflate(-6, -6))

        y0 = list_rect.y + 10 - self.scroll
        for i, (k, a) in enumerate(self.items):
            row = pygame.Rect(list_rect.x + 10, y0 + i * self.row_h, list_rect.w - 20, self.row_h - 8)
            if row.bottom < list_rect.y or row.top > list_rect.bottom:
                continue

            is_sel = (i == self.sel)
            bg = (32, 38, 48) if is_sel else (24, 28, 36)
            pygame.draw.rect(screen, bg, row, border_radius=12)
            pygame.draw.rect(screen, (90, 110, 130) if is_sel else (50, 60, 70), row, 2, border_radius=12)

            col = tuple(a.get("color", [200, 200, 200]))
            pygame.draw.circle(screen, col, (row.x + 20, row.centery), 10)
            name = a.get("name", k)
            nm = self.game.fonts.m.render(name, True, (240, 240, 240))
            screen.blit(nm, (row.x + 40, row.y + 10))

            tags = a.get("tags", [])
            if tags:
                tg = self.game.fonts.xs.render(" • ".join(tags[:4]), True, (160, 200, 160) if "BOSS" not in tags else (255, 180, 120))
                screen.blit(tg, (row.x + 40, row.y + 32))

        screen.set_clip(clip_prev)


        # details (render to an offscreen surface to support scrolling and avoid overflow)
        if not self.items:
            return
        ek, ea = self.items[self.sel]

        view_pad = 12
        view_rect = detail_rect.inflate(-view_pad*2, -view_pad*2)
        view_w = view_rect.w
        view_h = view_rect.h

        # Build draw ops (two-pass) to compute required height
        ops = []  # (font, text, color, x, y)
        y = 0
        x0 = 0

        def add_text(font, text, color, x, y):
            ops.append((font, text, color, x, y))

        def add_wrap(font, text, color, x, y, max_w):
            yy = y
            for line in _wrap_lines(text, font, max_w):
                add_text(font, line, color, x, yy)
                yy += font.get_linesize()
            return yy

        # header line
        name = ea.get("name", ek)
        col = tuple(ea.get("color", [200, 200, 200]))
        add_text(self.game.fonts.l, f"{name}  ({ek})", (240,240,240), x0 + 34, y)
        # circle marker is drawn on main screen (not on surface) for crispness
        y += self.game.fonts.l.get_linesize() + 10

        def stat(lbl, val, color=(210,210,210)):
            nonlocal y
            add_text(self.game.fonts.s, lbl, (160,170,180), x0, y)
            add_text(self.game.fonts.s, val, color, x0 + 180, y)
            y += self.game.fonts.s.get_linesize() + 2

        hp_mul = float(ea.get("hp", 1.0))
        spd = float(ea.get("spd", 1.0))
        armor = float(ea.get("armor", 0.0))
        shield = float(ea.get("shield", 0.0))
        regen = float(ea.get("regen", 0.0))
        weak = ea.get("weak")

        base_hp = int(30.0 * hp_mul)
        base_sh = int(shield * 12.0)

        stat("PV (base vague 1)", f"{base_hp}  (x{hp_mul:.2f})")
        stat("Vitesse (tuiles/s)", f"{spd:.2f}")
        stat("Armure", f"{armor:.0f}")
        stat("Bouclier (base)", f"{base_sh}  (x{shield:.0f})" if shield else "0")
        stat("Régénération (PV/s)", f"{regen:.0f}")

        y += 6
        # weakness
        try:
            from ..stats import CombatStats
            wm = CombatStats().weakness_mul
        except Exception:
            wm = 1.8
        if weak:
            dmg_name = self.dmg_names.get(weak, weak)
            c = self.dmg_colors.get(weak, (255,215,0))
            stat("Faiblesse", f"{dmg_name} (x{wm:.1f})", c)
        else:
            stat("Faiblesse", "Aucune")

        # Resistances
        y += 8
        add_text(self.game.fonts.m, "Résistances", (255,215,0), x0, y)
        y += self.game.fonts.m.get_linesize() + 4

        resist = (ea.get("resist") or {})
        non_neutral = []
        for k, mult in resist.items():
            try:
                m = float(mult)
            except Exception:
                continue
            if abs(m - 1.0) >= 0.06:
                non_neutral.append((k, m))
        if not non_neutral:
            add_text(self.game.fonts.s, "—", (210,210,210), x0, y)
            y += self.game.fonts.s.get_linesize() + 2
        else:
            non_neutral.sort(key=lambda kv: kv[1])  # most resistant first
            for k, m in non_neutral[:10]:
                pct = int((m - 1.0) * 100)
                lab = f"{k}: {pct:+d}%"
                c = (120,240,160) if m > 1.0 else (255,180,120) if m < 1.0 else (210,210,210)
                add_text(self.game.fonts.s, lab, c, x0, y)
                y += self.game.fonts.s.get_linesize() + 2

        # Shield effectiveness
        sh_mult = (ea.get("shield_mult") or {})
        if sh_mult and float(ea.get("shield", 0)) > 0:
            y += 8
            add_text(self.game.fonts.m, "Bouclier (efficacité)", (255,215,0), x0, y)
            y += self.game.fonts.m.get_linesize() + 4
            for k in ["ENERGY","KINETIC","PIERCE","FIRE","COLD","BIO"]:
                if k in sh_mult:
                    m = float(sh_mult[k])
                    pct = int((m - 1.0) * 100)
                    lab = f"{k}: {pct:+d}%"
                    c = (120,240,160) if m > 1.0 else (255,180,120) if m < 1.0 else (210,210,210)
                    add_text(self.game.fonts.s, lab, c, x0, y)
                    y += self.game.fonts.s.get_linesize() + 2

        # Tags
        tags = ea.get("tags", [])
        y += 10
        add_text(self.game.fonts.m, "Traits", (255,215,0), x0, y)
        y += self.game.fonts.m.get_linesize() + 4
        tags_txt = " • ".join(tags) if tags else "—"
        y = add_wrap(self.game.fonts.s, tags_txt, (210,210,210), x0, y, view_w)

        # Recommended counters (improved)
        y += 12
        add_text(self.game.fonts.m, "Contres recommandés", (255,215,0), x0, y)
        y += self.game.fonts.m.get_linesize() + 6

        def reasons(enemy_arch: dict, tower: dict) -> str:
            dt = tower.get("dmg_type","KINETIC")
            rs = []
            if enemy_arch.get("weak") == dt:
                rs.append("Faiblesse")
            r = float((enemy_arch.get("resist") or {}).get(dt, 1.0))
            if abs(r-1.0) >= 0.06:
                rs.append(f"Résist {int((r-1.0)*100):+d}%")
            if float(enemy_arch.get("shield",0)) > 0:
                sm = float((enemy_arch.get("shield_mult") or {}).get(dt, 1.0))
                if abs(sm-1.0) >= 0.06:
                    rs.append(f"Shield {int((sm-1.0)*100):+d}%")
            if float(enemy_arch.get("armor",0)) >= 6 and dt == "PIERCE":
                rs.append("Perce l'armure")
            if float(enemy_arch.get("armor",0)) >= 6 and dt == "KINETIC":
                rs.append("Armure pénalise")
            return " • ".join(rs[:3])

        scored = []
        for tk, tw in self.game.towers_db.items():
            if tw.get("role") == "SUPPORT":
                continue
            sc = self._tower_score(ea, tw)
            lab, c = self._effectiveness_label(ea, tw)
            why = reasons(ea, tw)
            line = f"• {tw['name']} — {lab}"
            if why:
                line += f" ({why})"
            scored.append((sc, line, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:5]
        low = scored[-2:][::-1]

        for sc, line, c in top:
            y = add_wrap(self.game.fonts.s, line, c, x0, y, view_w)
            y += 2

        y += 10
        add_text(self.game.fonts.s, "À éviter:", (180,180,180), x0, y)
        y += self.game.fonts.s.get_linesize() + 2
        for sc, line, c in low:
            y = add_wrap(self.game.fonts.s, line, (255,150,150), x0, y, view_w)
            y += 2

        # Synergies
        y += 12
        add_text(self.game.fonts.m, "Synergies (forge & build)", (255,215,0), x0, y)
        y += self.game.fonts.m.get_linesize() + 4

        tips = []
        if ea.get("desc"):
            tips.append(str(ea.get("desc")))
        tags_set = set(ea.get("tags", []) or [])
        if "SHIELD" in tags_set:
            tips.append("• Shield: ENERGY draine plus vite. Chemin Conducteur + Tesla = chaînes plus fiables.")
        if "ARMORED" in tags_set:
            tips.append("• Armure: combinez SHRED (Cryo B) + PIERCE (Sniper) au lieu de cadence brute.")
        if "REGEN" in tags_set:
            tips.append("• Regen: BURN réduit la régénération tant qu'il brûle.")
        if "FAST" in tags_set:
            tips.append("• Rapide: contrôle + AOE/CHAIN stabilise; évitez les tirs trop lents.")
        if "FIREPROOF" in tags_set:
            tips.append("• Fireproof: évitez le feu, privilégiez COLD/PIERCE.")
        if "BOSS" in tags_set:
            tips.append("• Boss: cassez le shield d'abord, puis burst avec VULN/SHRED + overclock.")

        for tip in tips[:8]:
            y = add_wrap(self.game.fonts.s, tip, (210,210,210), x0, y, view_w)
            y += 4

        content_h = max(y + 10, view_h)
        surf = pygame.Surface((view_w, int(content_h)), pygame.SRCALPHA)

        # Draw header marker circle on main screen
        pygame.draw.circle(screen, col, (detail_rect.x + 26, detail_rect.y + 28), 10)

        # Render ops
        for font, text, color, x, yy in ops:
            surf.blit(font.render(text, True, color), (x, yy))

        # Clamp detail scroll
        max_scroll = max(0, int(content_h - view_h))
        self.detail_scroll = max(0, min(int(self.detail_scroll), max_scroll))

        # Blit scrolled surface into detail panel
        screen.blit(surf, (view_rect.x, view_rect.y), area=pygame.Rect(0, self.detail_scroll, view_w, view_h))

        # Scrollbar if needed
        if max_scroll > 0:
            bar_x = detail_rect.right - 10
            bar_y = view_rect.y
            bar_h = view_h
            pygame.draw.rect(screen, (50,60,70), (bar_x, bar_y, 4, bar_h), border_radius=3)
            knob_h = max(24, int(bar_h * (view_h / content_h)))
            knob_y = bar_y + int((bar_h - knob_h) * (self.detail_scroll / max_scroll))
            pygame.draw.rect(screen, (120,140,160), (bar_x, knob_y, 4, knob_h), border_radius=3)


