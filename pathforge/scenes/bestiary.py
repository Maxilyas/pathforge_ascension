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
            elif event.key in (pygame.K_UP, pygame.K_w):
                self.sel = max(0, self.sel - 1)
            elif event.key == pygame.K_PAGEUP:
                self.scroll -= self.row_h * 6
            elif event.key == pygame.K_PAGEDOWN:
                self.scroll += self.row_h * 6
            self._clamp_scroll()

        if event.type == pygame.MOUSEWHEEL:
            # natural scroll (wheel up -> negative y in pygame?)
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
        score *= (1.0 / max(0.25, rm))

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
                score *= 0.72
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

        # details
        if not self.items:
            return
        ek, ea = self.items[self.sel]

        # top name line
        name = ea.get("name", ek)
        col = tuple(ea.get("color", [200, 200, 200]))
        pygame.draw.circle(screen, col, (detail_rect.x + 26, detail_rect.y + 28), 10)
        head = self.game.fonts.l.render(f"{name}  ({ek})", True, (240, 240, 240))
        screen.blit(head, (detail_rect.x + 46, detail_rect.y + 14))

        # stat block
        left_x = detail_rect.x + 22
        y = detail_rect.y + 62

        def stat_line(lbl: str, val: str, c=(210, 210, 210)):
            nonlocal y
            t1 = self.game.fonts.s.render(lbl, True, (160, 170, 180))
            t2 = self.game.fonts.s.render(val, True, c)
            screen.blit(t1, (left_x, y))
            screen.blit(t2, (left_x + 180, y))
            y += 22

        hp_mul = float(ea.get("hp", 1.0))
        spd = float(ea.get("spd", 1.0))
        armor = float(ea.get("armor", 0.0))
        shield = float(ea.get("shield", 0.0))
        regen = float(ea.get("regen", 0.0))
        weak = ea.get("weak")

        # show meaningful derived values (wave 1 baseline)
        base_hp = int(30.0 * hp_mul)
        base_sh = int(shield * 12.0)

        stat_line("PV (base vague 1)", f"{base_hp}  (x{hp_mul:.2f})")
        stat_line("Vitesse (tuiles/s)", f"{spd:.2f}")
        stat_line("Armure", f"{armor:.0f}")
        stat_line("Bouclier (base)", f"{base_sh}  (x{shield:.0f})" if shield else "0")
        stat_line("Régénération (PV/s)", f"{regen:.0f}")

        # weakness
        y += 8
        if weak:
            dmg_name = self.dmg_names.get(weak, weak)
            c = self.dmg_colors.get(weak, (255, 215, 0))
            mult = getattr(self.game.scenes.get("GAME", None), "stats", None)  # may be absent in menu
            # use default multiplier from stats class if scene not initialized
            try:
                from ..stats import CombatStats
                wm = CombatStats().weakness_mul
            except Exception:
                wm = 1.8
            stat_line("Faiblesse", f"{dmg_name} (x{wm:.1f})", c)
        else:
            stat_line("Faiblesse", "Aucune")

        # resistances section
        y += 6
        t = self.game.fonts.m.render("Résistances", True, (255, 215, 0))
        screen.blit(t, (left_x, y))
        y += 26

        resist = (ea.get("resist") or {})
        # Show only non-neutral multipliers
        non_neutral = []
        for k, mult in resist.items():
            try:
                m = float(mult)
            except Exception:
                continue
            if abs(m - 1.0) >= 0.06:
                non_neutral.append((k, m))

        if not non_neutral:
            screen.blit(self.game.fonts.s.render("—", True, (210,210,210)), (left_x, y))
            y += 20
        else:
            non_neutral.sort(key=lambda kv: kv[1])  # most resistant first
            for k, m in non_neutral[:8]:
                # label: -30% / +20%
                pct = int((m - 1.0) * 100)
                lab = f"{k}: {pct:+d}%"
                c = (120,240,160) if m > 1.0 else (255,180,120) if m < 1.0 else (210,210,210)
                screen.blit(self.game.fonts.s.render(lab, True, c), (left_x, y))
                y += 20

        # shield interaction section (if any)
        sh_mult = (ea.get("shield_mult") or {})
        if sh_mult and float(ea.get("shield", 0)) > 0:
            y += 6
            t = self.game.fonts.m.render("Bouclier (efficacité)", True, (255, 215, 0))
            screen.blit(t, (left_x, y))
            y += 26
            # show key types
            for k in ["ENERGY","KINETIC","PIERCE","FIRE","COLD","BIO"]:
                if k in sh_mult:
                    m = float(sh_mult[k])
                    pct = int((m - 1.0) * 100)
                    lab = f"{k}: {pct:+d}%"
                    c = (120,240,160) if m > 1.0 else (255,180,120) if m < 1.0 else (210,210,210)
                    screen.blit(self.game.fonts.s.render(lab, True, c), (left_x, y))
                    y += 20


        # tags section
        tags = ea.get("tags", [])
        y += 12
        t = self.game.fonts.m.render("Traits", True, (255, 215, 0))
        screen.blit(t, (left_x, y))
        y += 28
        tags_txt = " • ".join(tags) if tags else "—"
        for line in _wrap_lines(tags_txt, self.game.fonts.s, detail_rect.w - 44):
            screen.blit(self.game.fonts.s.render(line, True, (210, 210, 210)), (left_x, y))
            y += 20

        # counters section
        y += 12
        t = self.game.fonts.m.render("Contres (tours)", True, (255, 215, 0))
        screen.blit(t, (left_x, y))
        y += 30

        # score-based counters (strategy-first)
        scored: list[tuple[float, str, tuple[int,int,int]]] = []
        for tk, tw in self.game.towers_db.items():
            if tw.get("role") == "SUPPORT":
                continue
            sc = self._tower_score(ea, tw)
            lab, c = self._effectiveness_label(ea, tw)
            scored.append((sc, f"{tw['name']} — {lab}", c))

        scored.sort(key=lambda x: x[0], reverse=True)

        if not scored:
            scored = [(1.0, "Aucun contre spécifique — adaptez votre build.", (210,210,210))]

        lines: list[tuple[str, tuple[int,int,int]]] = []
        lines.append(("Recommandées", (255, 215, 0)))
        for sc, txt, c in scored[:4]:
            lines.append((f"• {txt}", c))

        lines.append(("", (210,210,210)))
        lines.append(("À éviter", (255, 215, 0)))
        for sc, txt, c in scored[-2:][::-1]:
            lines.append((f"• {txt}", c))

        # draw lines with wrapping
        for txt, c in lines:
            if txt == "":
                y += 10
                continue
            for line in _wrap_lines(txt, self.game.fonts.s, detail_rect.w - 44):
                screen.blit(self.game.fonts.s.render(line, True, c), (left_x, y))
                y += 20
            y += 2

        # synergies / counterplay
        y += 12
        t = self.game.fonts.m.render("Synergies (forge & build)", True, (255, 215, 0))
        screen.blit(t, (left_x, y))
        y += 26

        tips: list[str] = []
        if ea.get("desc"):
            tips.append(str(ea.get("desc")))

        tags_set = set(ea.get("tags", []) or [])
        if "SHIELD" in tags_set:
            tips.append("• Shield: ENERGY draine plus vite. Chemin Conducteur + Tesla = chaînes + efficaces.")
        if "ARMORED" in tags_set:
            tips.append("• Armure: évitez KINETIC pur. Combinez SHRED (Cryo/branch) + PIERCE (Sniper).")
        if "REGEN" in tags_set:
            tips.append("• Regen: BURN (Flame/Mortar/Magma) réduit la régénération à ~40% tant qu'il brûle.")
        if "FAST" in tags_set:
            tips.append("• Rapide: ralentissements (Cryo, boue) et AOE/CHAIN stabilisent la lane.")
        if "BOSS" in tags_set:
            tips.append("• Boss: cassez le shield d'abord (ENERGY + rune/Conducteur), puis burst/DoT + contrôle.")

        if not tips:
            tips = ["—"]

        for tip in tips[:7]:
            for line in _wrap_lines(tip, self.game.fonts.s, detail_rect.w - 44):
                screen.blit(self.game.fonts.s.render(line, True, (210,210,210)), (left_x, y))
                y += 20
            y += 2

        # footer hints
        footer = self.game.fonts.xs.render("Astuce: utilisez la Faiblesse pour choisir le type de dégâts (KINETIC/PIERCE/ENERGY/FIRE/COLD/BIO/EXPLOSIVE).", True, (130, 140, 150))
        screen.blit(footer, (detail_rect.x + 16, detail_rect.bottom - 26))