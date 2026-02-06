from __future__ import annotations
import pygame, random
from typing import Optional

from ..core.scene import Scene
from ..settings import COLS, ROWS, TOP_BAR_FRAC, BOTTOM_BAR_FRAC, T_EMPTY, T_ROCK, T_PATH, T_PATH_FAST, T_PATH_MUD, T_PATH_CONDUCT, T_PATH_CRYO, T_PATH_MAGMA, T_PATH_RUNE, T_TOWER, T_START, T_END, T_RELIC
from ..stats import CombatStats
from ..world.grid import generate_grid, tile
from ..world.world import World
from ..systems.wave_director import WaveDirector
from ..ui.widgets import Button
from ..ui.hud import draw_top_bar, draw_bottom_bar
from ..spells import Spellbook

TOWER_KEYS = ["GATLING","SNIPER","TESLA","CRYO","MORTAR","CANNON","BEACON","FLAME"]

RARITY_WEIGHT = {"C": 66, "R": 22, "E": 9, "L": 2, "SS+": 0.8, "SS++": 0.2}

def tower_color(db, key: str):
    return tuple(db[key].get("ui_color",[200,200,200]))

class GameScene(Scene):
    name="GAME"
    def enter(self, payload=None):
        self.stats = CombatStats()
        self.spells = Spellbook()

        # load run if continue
        run = None
        if payload and not payload.get("new", True):
            run = self.game.saves.load_run()

        self.w, self.h = self.game.w, self.game.h
        self.top_h = int(self.h * TOP_BAR_FRAC)
        self.bottom_h = int(self.h * BOTTOM_BAR_FRAC)
        self.game_h = self.h - self.bottom_h
        self.offset_y = self.top_h

        self.cols = COLS
        self.rows = ROWS
        tile_w = self.w // self.cols
        tile_h = max(12, (self.game_h - self.offset_y) // self.rows)
        self.tile = max(12, min(tile_w, tile_h))
        self.offset_x = max(0, (self.w - self.cols * self.tile) // 2)
        # world seed/biome
        seed = random.randrange(1,2_000_000_000)
        biome = "HIGHLANDS"
        if run:
            seed = int(run.get("seed", seed))
            biome = run.get("biome", biome)
        brate = 0.0  # rocks disabled for labyrinth maps
        gs = generate_grid(self.cols, self.rows, biome=biome, seed=seed, rock_rate=brate)

        self.rng = random.Random(seed)
        self.world = World(gs, tile_size=self.tile, offset_x=self.offset_x, offset_y=self.offset_y, w=self.w, h=self.game_h,
                           towers_db=self.game.towers_db, enemies_db=self.game.enemies_db, rng=self.rng)

        # --- PAVÉS: ressource rare au départ (juste un peu plus que la distance Start->End) ---
        if not run:
            sx, sy = self.world.gs.start
            ex, ey = self.world.gs.end
            dist = abs(ex - sx) + abs(ey - sy)
            base_paves = int(dist * 1.12) + 2  # ~ +10-15% buffer
            self.stats.paves = int(base_paves)
            self.stats.paves_cap = int(base_paves + 16)  # cap bas => le chemin reste un choix
        

        self.director = WaveDirector(self.rng)

        self.mode = "BUILD"
        self.tool = "PATH"
        self.selected_tower_key = next(iter(sorted(getattr(self.stats, "unlocked_towers", {"GATLING"}))), "GATLING")
        self.dd_open = False
        self.selected_tower = None

        # path variants (cycle with V) + pave costs
        
        self.all_path_variants = [
            (T_PATH, "Standard", 1),
            (T_PATH_FAST, "Route", 6),
            (T_PATH_MUD, "Boue", 6),
            (T_PATH_CONDUCT, "Conducteur", 8),
            (T_PATH_CRYO, "Cryo", 9),
            (T_PATH_MAGMA, "Magma", 9),
            (T_PATH_RUNE, "Rune", 14),
        ]
        self.path_cost_by_tile = {t: c for (t, _n, c) in self.all_path_variants}
        self.path_tiles_all = set(self.path_cost_by_tile.keys())
        self.path_variant_idx = 0
        self.path_variants = []
        self.path_tile = T_PATH
        self._rebuild_path_variants()
        # multi wave = difficulty multiplier (doesn't skip wave numbers)
        self.wave_multi = 1

        # UI
        bw = self.w // 5
        bh = self.bottom_h//2 - 12
        by = self.game_h + 12 + bh

        self.btn_menu = Button(pygame.Rect(12,12,54,54), "", (30,35,40), cb=self._pause, icon="MENU")
        self.btn_speed = Button(pygame.Rect(self.w-178, 16, 106, 34), "x1", (70,80,90), cb=self._speed)
        self.btn_talents = Button(pygame.Rect(self.w-58, 12, 46, 46), "", (30,35,40), cb=self._talents, icon="STAR")

        self.btn_path = Button(pygame.Rect(12, by, bw, bh), "CHEMIN", (70,80,90), cb=self._set_tool, arg="PATH")
        self.btn_tow  = Button(pygame.Rect(24+bw, by, bw, bh), "TOUR", tower_color(self.game.towers_db, self.selected_tower_key), cb=self._toggle_dd)
        self.btn_ers  = Button(pygame.Rect(36+bw*2, by, bw, bh), "GOMME", (150,60,60), cb=self._set_tool, arg="ERASE")

        bx_as = 48+bw*3
        self.btn_m_minus = Button(pygame.Rect(bx_as, by, bh, bh), "-", (70,80,90), cb=self._multi, arg=-1)
        self.btn_go = Button(pygame.Rect(bx_as+bh+6, by, bw-bh*2-12, bh), "ASSAUT", (70,220,140), cb=self._start_wave)
        self.btn_m_plus = Button(pygame.Rect(bx_as+bw-bh, by, bh, bh), "+", (70,80,90), cb=self._multi, arg=1)

        self.ui_btns = [self.btn_path,self.btn_tow,self.btn_ers,self.btn_m_minus,self.btn_go,self.btn_m_plus]

        self.dd_btns = []
        self._dd_keys = []
        self._rebuild_tower_dropdown()

        # wave state
        self.wave_queue = []
        self.spawn_timer = 0.0

        # load run content
        if run:
            self._load(run)

        self._recalc_plan()

    def _pause(self):
        self.request("PAUSE", None)

    def _talents(self):
        self.request("TALENT", {"stats": self.stats})

    def _speed(self):
        self.game.clock.cycle_speed()
        self.btn_speed.text = f"x{int(self.game.clock.time_scale)}"

    def _set_tool(self, t):
        self.tool = t
        self.dd_open = False
        self.selected_tower = None

    def _toggle_dd(self):
        self.dd_open = not self.dd_open

    def _pick_tower(self, k):
        self.selected_tower_key = k
        self.tool = "TOWER"
        self.dd_open = False







    def _rebuild_path_variants(self):
        allowed = set(getattr(self.stats, "unlocked_path_tiles", {T_PATH}))
        allowed.add(T_PATH)
        self.path_variants = [pv for pv in self.all_path_variants if pv[0] in allowed]
        if not self.path_variants:
            self.path_variants = [(T_PATH, "Standard", 1)]
        self.path_variant_idx = max(0, min(self.path_variant_idx, len(self.path_variants) - 1))
        self.path_tile = self.path_variants[self.path_variant_idx][0]

    def _rebuild_tower_dropdown(self):
        allowed = set(getattr(self.stats, "unlocked_towers", set(TOWER_KEYS)))
        keys = [k for k in TOWER_KEYS if k in allowed]
        if not keys:
            keys = ["GATLING"]
        if self.selected_tower_key not in keys:
            self.selected_tower_key = keys[0]
        bw = self.btn_tow.rect.w
        self.dd_btns = []
        for i, k in enumerate(keys):
            td = self.game.towers_db[k]
            rr = pygame.Rect(self.btn_tow.rect.x, self.btn_tow.rect.y - (i + 1) * 52 - 6, bw, 52)
            self.dd_btns.append(
                Button(rr, f"{td['name']} ${int(td['cost'] * self.stats.tower_cost_mul)}", tuple(td.get("ui_color", [200, 200, 200])), cb=self._pick_tower, arg=k)
            )
        self._dd_keys = keys

    def _sync_world_from_stats(self):
        self.world.weakness_mul = float(getattr(self.stats, "weakness_mul", 1.8))
        self.world.enemy_speed_mul = float(getattr(self.stats, "enemy_speed_mul", 1.0))
        self.world.rune_vuln_chance = float(getattr(self.stats, "rune_vuln_chance", 0.10))
        self.world.magma_burn_chance = float(getattr(self.stats, "magma_burn_chance", 0.25))
        self.world.cryo_tile_slow_extend = float(getattr(self.stats, "cryo_tile_slow_extend", 0.05))
        self.world.hero_shock_radius_mul = float(getattr(self.stats, "hero_shock_radius_mul", 1.0))
        self.world.hero_shock_apply_vuln = bool(getattr(self.stats, "hero_shock_apply_vuln", False))

    def _wrap_text(self, font, text: str, max_w: int) -> list[str]:
        words = (text or "").split()
        if not words:
            return [""]
        out = []
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            if font.size(test)[0] <= max_w:
                line = test
            else:
                if line:
                    out.append(line)
                line = w
        if line:
            out.append(line)
        return out

    def _draw_tower_tooltip(self, screen, tower_key: str, menu_rect: pygame.Rect, hover_rect: pygame.Rect):
        td = self.game.towers_db.get(tower_key)
        if not td:
            return

        base = td.get("base", {})
        dmg = float(base.get("damage", 0))
        rate = float(base.get("rate", 0))
        rng = float(base.get("range", 0))
        dps = dmg * rate

        role = td.get("role", "")
        dmg_type = td.get("dmg_type", "")
        cost = int(td.get("cost", 0))
        ui_col = tuple(td.get("ui_color", [200, 200, 200]))

        # specials
        specials = []
        splash = float(base.get("splash", 0.0))
        pierce = int(base.get("pierce", 0))
        if splash > 0:
            specials.append(f"AOE: {splash:.1f} cases")
        if pierce > 0:
            specials.append(f"Perce: {pierce}")
        if tower_key == "TESLA":
            specials.append("Synergie: chemin conducteur (+chains)")
        if tower_key == "BEACON":
            specials.append("Aura: buff tours proches")

        branches = td.get("branches") or {}

        panel_w = 380
        # dynamic height (estimate)
        content_lines = 0
        content_lines += 4  # stat rows
        content_lines += max(1, min(4, len(specials))) + (1 if specials else 0)
        content_lines += 1  # branches header
        for key in ("A","B","C"):
            b = branches.get(key)
            if not b:
                continue
            # name line + wrapped desc
            content_lines += 1
            content_lines += len(self._wrap_text(self.game.fonts.xs, b.get("desc",""), panel_w - 32))
        panel_h = 64 + 16 + content_lines * 16 + 18
        panel_h = max(240, min(420, panel_h))

        # placement: right of menu, aligned to hovered item
        x = menu_rect.right + 14
        y = hover_rect.top - 10
        if x + panel_w > self.w - 12:
            x = menu_rect.left - panel_w - 14
        # keep inside game area (not into bottom bar)
        y_min = max(80, self.offset_y + 10)
        y_max = self.game_h - 12 - panel_h
        y = max(y_min, min(y, y_max))

        rr = pygame.Rect(int(x), int(y), panel_w, panel_h)

        # shadow + panel
        sh = pygame.Surface((rr.w + 14, rr.h + 14), pygame.SRCALPHA)
        pygame.draw.rect(sh, (0, 0, 0, 120), (10, 10, rr.w, rr.h), border_radius=16)
        screen.blit(sh, (rr.x - 10, rr.y - 10))
        pygame.draw.rect(screen, (22, 22, 26), rr, border_radius=16)
        pygame.draw.rect(screen, (90, 90, 105), rr, 2, border_radius=16)

        # header strip
        head = pygame.Rect(rr.x, rr.y, rr.w, 56)
        pygame.draw.rect(screen, (28, 30, 36), head, border_radius=16)
        pygame.draw.rect(screen, ui_col, (rr.x + 14, rr.y + 18, 18, 18), border_radius=6)

        title = self.game.fonts.m.render(f"{td.get('name','?')}  ({role})", True, (245, 245, 245))
        screen.blit(title, (rr.x + 42, rr.y + 12))
        sub = self.game.fonts.xs.render(f"{dmg_type}  •  Coût {cost}$", True, (200, 200, 200))
        screen.blit(sub, (rr.x + 42, rr.y + 34))

        y0 = rr.y + 68

        def stat_row(label, value, yy):
            lab = self.game.fonts.xs.render(label, True, (200, 200, 200))
            val = self.game.fonts.xs.render(value, True, (240, 240, 240))
            screen.blit(lab, (rr.x + 16, yy))
            screen.blit(val, (rr.x + 170, yy))

        stat_row("Dégâts", f"{int(dmg)}", y0)
        stat_row("Cadence", f"{rate:.1f}/s", y0 + 18)
        stat_row("Portée", f"{rng:.1f}", y0 + 36)
        stat_row("DPS (base)", f"{int(dps)}", y0 + 54)

        yy = y0 + 78
        if specials:
            lab = self.game.fonts.xs.render("Spécial", True, (200, 200, 200))
            screen.blit(lab, (rr.x + 16, yy))
            yy += 18
            for ex in specials[:4]:
                t = self.game.fonts.xs.render("• " + ex, True, (220, 220, 220))
                screen.blit(t, (rr.x + 16, yy))
                yy += 16
            yy += 6

        bt = self.game.fonts.xs.render("Branches (choix A / B / C)", True, (200, 200, 200))
        screen.blit(bt, (rr.x + 16, yy))
        yy += 18

        for key in ("A","B","C"):
            b = branches.get(key)
            if not b:
                continue
            name = b.get("name","")
            hdr = self.game.fonts.xs.render(f"{key}: {name}", True, (235, 235, 235))
            screen.blit(hdr, (rr.x + 16, yy))
            yy += 16
            desc_lines = self._wrap_text(self.game.fonts.xs, b.get("desc",""), panel_w - 32)
            for dl in desc_lines[:3]:
                t = self.game.fonts.xs.render("   " + dl, True, (200, 200, 200))
                screen.blit(t, (rr.x + 16, yy))
                yy += 16
            yy += 6

    def _multi(self, d):
        self.wave_multi = max(1, min(5, self.wave_multi + int(d)))

    def _recalc_plan(self):
        p = self.world.get_path()
        relics = 0
        if p:
            s = set(p)
            relics = sum(1 for r in self.world.gs.relics if r in s)
        self.plan = self.director.plan(self.stats.wave, relics_in_path=relics, ascension=self.game.meta.ascension)

    def _perk_bias(self) -> float:
        # more waves at once => higher rarity
        return 0.12 * (self.wave_multi - 1)

    def _roll_perks(self, n: int) -> list[dict]:
        # weights with bias
        b = self._perk_bias()
        w = dict(RARITY_WEIGHT)
        w["C"] *= (1.0 - 0.65*b)
        w["R"] *= (1.0 - 0.35*b)
        w["E"] *= (1.0 + 0.60*b)
        w["L"] *= (1.0 + 1.25*b)
        w["SS+"] *= (1.0 + 2.00*b)
        w["SS++"] *= (1.0 + 2.50*b)

        pool = []
        for p in self.game.perks_db:
            rar = p.get("rarity","C")
            k = max(1, int(w.get(rar,1.0)*10))
            pool.extend([p]*k)

        out=[]
        for _ in range(n):
            out.append(self.rng.choice(pool))
        return out

    def _start_wave(self):
        if self.mode != "BUILD":
            return
        if not self.world.path_valid():
            self.world.fx_text(80, self.offset_y+10, "Chemin invalide!", (255,120,120), 0.8)
            return
        self.mode = "WAVE"
        self.wave_queue.clear()
        self.spawn_timer = 0.0
        self.world.enemies.clear()
        self.world.projectiles.clear()

        base_list = self.director.spawn_list(self.plan)
        mult = 1.0 + 0.65*(self.wave_multi-1)
        count = max(1, int(len(base_list)*mult))
        for _ in range(count):
            self.wave_queue.append(self.rng.choice(base_list))
        if self.plan.boss and "BOSS" not in self.wave_queue:
            self.wave_queue.insert(0,"BOSS")
        self.rng.shuffle(self.wave_queue)

        # telemetry
        try:
            self.stats._telemetry_towers = len(self.world.towers)
            if getattr(self.game, 'telemetry', None):
                self.game.telemetry.wave_start(self.stats.wave, bool(self.plan.boss), int(self.wave_multi), self.stats)
        except Exception:
            pass

    def _end_wave(self):
        base = 85 + int(self.stats.wave*7)
        relic_bonus = 1 + int(0.20*(self.plan.relics_in_path))
        multi_bonus = 1 + int(0.25*(self.wave_multi-1))
        reward = int(base * relic_bonus * multi_bonus)
        if self.plan.boss and self.stats.has_flag("flag_boss_bounty"):
            reward *= 2
        self.stats.gold += reward
        self.stats.end_wave_income(self.plan.relics_in_path)
        # pave regeneration (forge essence): makes path placement a real resource
        self.stats.paves = min(int(getattr(self.stats, 'paves_cap', 80)), int(self.stats.paves + 1 + min(2, self.plan.relics_in_path//2) + (3 if self.plan.boss else 0)))

        # Talent points: +1 every 5 waves, plus +1 bonus on boss waves (killed)
        gained = 0
        if self.stats.wave % 5 == 0:
            gained += 1
        if self.plan.boss:
            gained += 1
        if gained:
            self.stats.talent_pts += gained

        # save
        self.game.request_save = True

        # telemetry
        try:
            if getattr(self.game,'telemetry',None):
                self.game.telemetry.wave_end(self.stats)
                self.game.telemetry.flush_waves()
        except Exception:
            pass

        # perk selection
        bias = self._perk_bias()
        options = self.game.roll_perks(3, rarity_bias=bias)
        self.request("PERK", {"options": options, "stats": self.stats, "rng": self.rng, "rarity_bias": bias})

        # wave increments by 1 ONLY (no skipping bosses)
        self.stats.wave += 1
        self.mode = "BUILD"
        self._recalc_plan()

    def _serialize(self) -> dict:
        gs = self.world.gs
        flat=[]
        for y in range(gs.rows):
            for x in range(gs.cols):
                flat.append(gs.grid[x][y])
        tw=[]
        for t in self.world.towers:
            tw.append({
                "gx":t.gx,"gy":t.gy,"key":t.defn.key,
                "level":t.level,"spent":t.spent,
                "branch":t.branch_choice,
                "target":t.target_mode_idx,
                "oc_cd":t.overclock_cd,"oc_t":t.overclock_time
            })
        return {
            "seed": gs.seed,
            "biome": gs.biome,
            "grid":{"cols":gs.cols,"rows":gs.rows,"flat":flat,"start":list(gs.start),"end":list(gs.end),"relics":[list(r) for r in gs.relics]},
            "towers": tw,
            "hero":{"x":self.world.hero.state.x,"y":self.world.hero.state.y,"dash_cd":self.world.hero.state.dash_cd,"shock_cd":self.world.hero.state.shock_cd},
            "stats": {
                "gold": self.stats.gold, "fragments": self.stats.fragments, "paves": self.stats.paves, "lives": self.stats.lives, "core_shield": self.stats.core_shield,
                "wave": self.stats.wave, "talent_pts": self.stats.talent_pts, "talent_nodes": list(self.stats.talent_nodes),
                "unlocked_towers": list(getattr(self.stats, "unlocked_towers", [])),
                "unlocked_path_tiles": list(getattr(self.stats, "unlocked_path_tiles", [])),
                "perks": list(getattr(self.stats, "perks", [])),
                "global_on_hit": getattr(self.stats, "global_on_hit", {}),
                "rune_vuln_chance": getattr(self.stats, "rune_vuln_chance", 0.10),
                "magma_burn_chance": getattr(self.stats, "magma_burn_chance", 0.25),
                "cryo_tile_slow_extend": getattr(self.stats, "cryo_tile_slow_extend", 0.05),
                "rune_aura_dmg_mul": getattr(self.stats, "rune_aura_dmg_mul", 1.06),
                "rune_aura_range_mul": getattr(self.stats, "rune_aura_range_mul", 1.05),
                "rune_aura_radius": getattr(self.stats, "rune_aura_radius", 2),
                "hero_shock_radius_mul": getattr(self.stats, "hero_shock_radius_mul", 1.0),
                "hero_shock_apply_vuln": getattr(self.stats, "hero_shock_apply_vuln", False),
                "perk_rerolls": self.stats.perk_rerolls,
                "dmg_mul": self.stats.dmg_mul, "rate_mul": self.stats.rate_mul, "range_mul": self.stats.range_mul,
                "gold_per_kill": self.stats.gold_per_kill, "frag_chance": self.stats.frag_chance, "interest": self.stats.interest,
                "weakness_mul": self.stats.weakness_mul, "enemy_speed_mul": self.stats.enemy_speed_mul,
                "tower_cost_mul": self.stats.tower_cost_mul, "sell_refund": self.stats.sell_refund,
                "overclock_dur_mul": self.stats.overclock_dur_mul,
                "spell_cd_mul": self.stats.spell_cd_mul, "spell_energy_regen_mul": self.stats.spell_energy_regen_mul, "spell_double_chance": self.stats.spell_double_chance,
                "flags": self.stats.flags, "tower_bonus": self.stats.tower_bonus, "spell_bonus": self.stats.spell_bonus
            }
        }

    def _load(self, run: dict):
        # stats
        s = run.get("stats") or {}
        for k,v in s.items():
            if hasattr(self.stats, k):
                setattr(self.stats, k, v)
        # migrate / sanitize types from JSON
        self.stats._ensure_talent_nodes_set()
        self.stats._ensure_unlock_sets()
        try:
            self.stats.gold = int(self.stats.gold)
            self.stats.fragments = int(self.stats.fragments)
            self.stats.paves = int(getattr(self.stats,'paves',0))
            self.stats.lives = int(self.stats.lives)
            self.stats.core_shield = int(self.stats.core_shield)
            self.stats.wave = int(self.stats.wave)
            self.stats.talent_pts = int(self.stats.talent_pts)
        except:
            pass
        # grid
        g = run.get("grid") or {}
        flat = g.get("flat") or []
        if len(flat) == self.cols*self.rows:
            for y in range(self.rows):
                for x in range(self.cols):
                    self.world.gs.grid[x][y] = int(flat[y*self.cols+x])
        self.world.gs.relics = [tuple(r) for r in g.get("relics",[])]
        self.world.invalidate_path()

        # towers
        self.world.towers.clear()
        for td in (run.get("towers") or []):
            gx,gy = int(td["gx"]), int(td["gy"])
            key = td["key"]
            # allow placing into already T_TOWER cells
            self.world.gs.grid[gx][gy] = T_EMPTY
            t = self.world.add_tower(gx,gy,key, allow_on_rock=True)
            if not t: 
                continue
            t.level = int(td.get("level",1))
            t.spent = int(td.get("spent", t.spent))
            t.target_mode_idx = int(td.get("target",0))
            br = td.get("branch")
            if br:
                t.apply_branch(br)
            t.overclock_cd = float(td.get("oc_cd",0.0))
            t.overclock_time = float(td.get("oc_t",0.0))

        # hero
        h = run.get("hero") or {}
        self.world.hero.state.x = float(h.get("x", self.world.hero.state.x))
        self.world.hero.state.y = float(h.get("y", self.world.hero.state.y))
        self.world.hero.state.dash_cd = float(h.get("dash_cd",0.0))
        self.world.hero.state.shock_cd = float(h.get("shock_cd",0.0))

    def handle_event(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: self._pause()
            if event.key == pygame.K_f: self._speed()

            # build tool hotkeys
            if event.key == pygame.K_c: self._set_tool("PATH")
            if event.key == pygame.K_b: self._set_tool("TOWER")
            if event.key == pygame.K_x: self._set_tool("ERASE")
            if event.key == pygame.K_g: self._start_wave()

            if event.key == pygame.K_v and self.tool == "PATH":
                self.path_variant_idx = (self.path_variant_idx + 1) % len(self.path_variants)
                self.path_tile = self.path_variants[self.path_variant_idx][0]
                _, nm, cost = self.path_variants[self.path_variant_idx]
                self.world.fx_text(80, self.offset_y + 18, f"Chemin: {nm} (coût {cost})", (255,215,0), 0.8)

            # hero skills
            if event.key == pygame.K_SPACE:
                mx,my = pygame.mouse.get_pos()
                self.world.hero.dash(mx-self.world.hero.state.x, my-self.world.hero.state.y, self.world)
            if event.key == pygame.K_a:
                self.world.rebuild_spatial()
                self.world.hero.shock(self.world)

            # tower targeting/overclock
            if self.selected_tower and event.key == pygame.K_TAB:
                self.selected_tower.cycle_target_mode()
            if self.selected_tower and event.key == pygame.K_e:
                if self.selected_tower.can_overclock():
                    self.selected_tower.trigger_overclock()
                    self.selected_tower.overclock_time *= float(self.stats.overclock_dur_mul)
                    self.world.fx_text(self.offset_x + self.selected_tower.gx*self.tile, self.selected_tower.gy*self.tile+self.offset_y, "OVERCLOCK", (255,215,0), 0.7)

            # spells
            if event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                key = {pygame.K_1:"METEOR", pygame.K_2:"FREEZE", pygame.K_3:"REPAIR", pygame.K_4:"DRONE"}[event.key]
                mx,my = pygame.mouse.get_pos()
                self.world.rebuild_spatial()
                self.spells.cast(key, self.world, self.stats, (mx,my))

        if event.type == pygame.MOUSEBUTTONDOWN:
            mx,my = event.pos
            if event.button == 3:
                self.world.hero.set_target(mx,my)
                return

            if self.btn_menu.click(event.pos): return
            if self.btn_speed.click(event.pos): return
            if self.btn_talents.click(event.pos): return

            if self.dd_open:
                hit=False
                for b in self.dd_btns:
                    if b.click(event.pos):
                        hit=True
                if not hit:
                    self.dd_open = False
                return

            # tower panel interaction
            if self.selected_tower:
                # IMPORTANT: keep these rects in sync with the draw() panel.
                panel = pygame.Rect(self.w - 390, self.offset_y + 30, 370, 280)
                panel.bottom = min(panel.bottom, self.game_h - 12)

                upg = pygame.Rect(panel.x + 20, panel.bottom - 58, 170, 44)
                sell = pygame.Rect(panel.x + 210, panel.bottom - 58, 140, 44)

                if upg.collidepoint(event.pos):
                    if self.stats.has_flag("flag_lock_upgrades"):
                        self.world.fx_text(panel.x+30, panel.y+10, "Upgrades bloqués!", (255,120,120), 0.9)
                        return
                    cost = self.selected_tower.upgrade_cost()
                    if self.stats.gold >= cost:
                        self.stats.gold -= cost
                        try:
                            if getattr(self.game,'telemetry',None):
                                self.game.telemetry.tower_placed(self.selected_tower_key)
                        except Exception:
                            pass
                        self.selected_tower.upgrade()
                        try:
                            if getattr(self.game,'telemetry',None):
                                self.game.telemetry.tower_upgraded(self.selected_tower.defn.key)
                        except Exception:
                            pass
                    else:
                        self.world.fx_text(panel.x+30, panel.y+10, "Or insuffisant!", (255,120,120), 0.9)
                    return
                if sell.collidepoint(event.pos):
                    self.stats.gold += int(self.selected_tower.spent * float(self.stats.sell_refund))
                    self.world.remove_tower(self.selected_tower)
                    self.selected_tower = None
                    return

                if self.selected_tower.can_branch():
                    for i,br in enumerate(["A","B","C"]):
                        rr = pygame.Rect(panel.x + 20, panel.y + 84 + i * 44, 330, 38)
                        if rr.collidepoint(event.pos):
                            self.selected_tower.apply_branch(br)
                            return

                tc = self.world.tile_at_pixel(mx,my)
                if tc:
                    t = self.world.tower_at(*tc)
                    self.selected_tower = t
                else:
                    self.selected_tower = None
                return

            for b in self.ui_btns:
                if b.click(event.pos):
                    return

            # map interaction
            tc = self.world.tile_at_pixel(mx,my)
            if not tc or self.mode != "BUILD":
                return
            gx,gy = tc
            v = self.world.gs.grid[gx][gy]
            tow = self.world.tower_at(gx,gy)
            if tow:
                self.selected_tower = tow
                self.tool = "NONE"
                return

            if self.tool == "TOWER":
                cost = int(self.game.towers_db[self.selected_tower_key]["cost"] * float(self.stats.tower_cost_mul))
                allow_rock = self.stats.has_flag("flag_build_on_rocks")
                can_build = (v == T_EMPTY) or (allow_rock and v == T_ROCK)
                if can_build and self.stats.gold >= cost:
                    # if building on rock, temporarily set empty for placement
                    if allow_rock and v == T_ROCK:
                        self.world.gs.grid[gx][gy] = T_EMPTY
                    t = self.world.add_tower(gx,gy,self.selected_tower_key, allow_on_rock=allow_rock)
                    if t:
                        self.stats.gold -= cost
                        try:
                            if getattr(self.game,'telemetry',None):
                                self.game.telemetry.tower_placed(self.selected_tower_key)
                        except Exception:
                            pass
                    else:
                        # restore if failed
                        if allow_rock and v == T_ROCK:
                            self.world.gs.grid[gx][gy] = T_ROCK

            elif self.tool == "PATH":
                tile_val, nm, cost = self.path_variants[self.path_variant_idx]
                if self.stats.paves < cost:
                    self.world.fx_text(80, self.offset_y+18, "Plus de pavés!", (255,80,80), 0.7)
                else:
                    if self.world.build_path_tile(gx,gy, tile_value=tile_val):
                        self.stats.paves -= cost
            elif self.tool == "ERASE":
                # refund pavés when removing a standard path tile (prevents softlock)
                try:
                    if v == T_PATH:
                        self.stats.paves = min(int(getattr(self.stats, "paves_cap", 999999)), int(self.stats.paves) + 1)
                except Exception:
                    pass
                self.world.erase_tile(gx,gy)

        if event.type == pygame.MOUSEMOTION:
            if pygame.mouse.get_pressed()[0] and self.tool == "PATH" and self.mode == "BUILD" and not self.dd_open and not self.selected_tower:
                tc = self.world.tile_at_pixel(*event.pos)
                if tc:
                    tile_val, nm, cost = self.path_variants[self.path_variant_idx]
                    if self.stats.paves >= cost:
                        if self.world.build_path_tile(*tc, tile_value=tile_val):
                            self.stats.paves -= cost

    def update(self, dt: float):
        dt = self.game.clock.scaled_dt(dt)


        # world tuning & unlock-driven UI
        self._sync_world_from_stats()
        self.world.flag_all_projectiles_splash = self.stats.has_flag("flag_all_projectiles_splash")
        self.world.flag_chain_reaction = self.stats.has_flag("flag_chain_reaction")

        sig = (frozenset(getattr(self.stats, "unlocked_towers", set())), frozenset(getattr(self.stats, "unlocked_path_tiles", set())))
        if getattr(self, "_unlock_sig", None) != sig:
            self._rebuild_path_variants()
            self._rebuild_tower_dropdown()
            self._unlock_sig = sig

        # spell regen
        self.spells.tick(dt, self.stats.spell_energy_regen_mul)

        # hero
        keys = pygame.key.get_pressed()
        self.world.hero.update(dt, keys, self.world)

        # build spatial
        self.world.rebuild_spatial()

        if self.mode == "WAVE":
            self.spawn_timer += dt
            spawn_gap = max(0.14, 0.34 - 0.03*(self.wave_multi-1))
            if self.wave_queue and self.spawn_timer >= spawn_gap:
                self.spawn_timer = 0.0
                key = self.wave_queue.pop(0)
                self.world.spawn_enemy(key, wave=self.stats.wave, gold_bonus=self.stats.gold_per_kill)

            # update enemies
            for e in list(self.world.enemies):
                e.update(dt)
                # boss phases spawn adds
                while e.spawn_signals:
                    sig = e.spawn_signals.pop(0)
                    if sig == "PHASE1":
                        self.world.fx_text(self.w//2-60, self.offset_y+40, "BOSS PHASE 1", (255,215,0), 0.9)
                        for _ in range(4 + self.wave_multi):
                            ne = self.world.spawn_enemy("SCOUT", wave=self.stats.wave, gold_bonus=self.stats.gold_per_kill)
                            if ne:
                                ne.x, ne.y = e.x, e.y
                                ne.idx = max(0, e.idx-1)
                    if sig == "PHASE2":
                        self.world.fx_text(self.w//2-60, self.offset_y+40, "BOSS PHASE 2", (255,120,80), 0.9)
                        for _ in range(2 + self.wave_multi):
                            ne = self.world.spawn_enemy("ELITE", wave=self.stats.wave, gold_bonus=self.stats.gold_per_kill)
                            if ne:
                                ne.x, ne.y = e.x, e.y
                                ne.idx = max(0, e.idx-1)

                if e.finished:
                    try:
                        if getattr(self.game,'telemetry',None):
                            self.game.telemetry.enemy_leaked(e.arch.key)
                    except Exception:
                        pass
                    if self.stats.core_shield > 0:
                        self.stats.core_shield -= 1
                    else:
                        self.stats.lives -= 1
                    self.world.enemies.remove(e)
                    if self.stats.lives <= 0:
                        self.request("MENU", None)
                elif not e.alive:
                    try:
                        if getattr(self.game,'telemetry',None):
                            self.game.telemetry.enemy_killed(e.arch.key)
                    except Exception:
                        pass
                    gold = e.reward_gold + int(getattr(e, 'tile_gold_bonus', 0))
                    if self.plan.boss and self.stats.has_flag("flag_boss_bounty") and "BOSS" in e.arch.tags:
                        gold *= 2
                    self.stats.gold += gold
                    if self.rng.random() < self.stats.frag_chance + (0.12 if e.is_elite() else 0.0):
                        self.stats.fragments += 1 + (1 if e.is_elite() else 0)
                    self.world.enemies.remove(e)

            # towers
            buffs = {"dmg_mul":1.0,"rate_mul":1.0,"range_mul":1.0}
            # beacon aura stacks
            for t in self.world.towers:
                a = t.aura()
                if a:
                    buffs["dmg_mul"] *= float(a.get("dmg_mul", 1.0))
                    buffs["rate_mul"] *= float(a.get("rate_mul", 1.0))
                    buffs["range_mul"] *= float(a.get("range_mul", 1.0))

            powered_runes = set(self.world.powered_runes())
            aura_r = int(getattr(self.stats, "rune_aura_radius", 2))

            for t in self.world.towers:
                # global on-hit statuses from perks
                if self.stats.global_on_hit:
                    oh = t.mods.setdefault("on_hit", {})
                    for sk, sv in self.stats.global_on_hit.items():
                        oh[sk] = dict(sv)
                # legacy flag: global poison
                if self.stats.has_flag("flag_global_poison_on_hit"):
                    t.mods.setdefault("on_hit", {}).setdefault("POISON", {"dur":2.0,"stacks":1})
                local_buffs = dict(buffs)
                if powered_runes:
                    for rx, ry in powered_runes:
                        if max(abs(t.gx-rx), abs(t.gy-ry)) <= aura_r:
                            local_buffs["dmg_mul"] *= float(getattr(self.stats, "rune_aura_dmg_mul", 1.06))
                            local_buffs["range_mul"] *= float(getattr(self.stats, "rune_aura_range_mul", 1.05))
                            break
                t.update(dt, self.world, self.rng, self.stats, local_buffs)

            self.world.update_projectiles(dt)
            self.world.update_fx(dt)

            if not self.wave_queue and not any(e.alive and not e.finished for e in self.world.enemies):
                self._end_wave()

        else:
            # build mode: just fx/projectiles
            self.world.update_projectiles(dt)
            self.world.update_fx(dt)
            self._recalc_plan()

        # autosave
        if self.game.request_save:
            self.game.request_save = False
            self.game.saves.save_run(self._serialize())


    def draw(self, screen):
        tint = tuple(self.game.biomes.get(self.world.gs.biome, {}).get("tint", [24, 32, 44]))
        self.world.draw_map(screen, self.game.fonts, biome_tint=tint)

        self._recalc_plan()
        path_ok = self.world.path_valid()

        draw_top_bar(
            screen,
            self.game.fonts,
            self.w,
            self.top_h,
            self.stats,
            self.game.clock.time_scale,
            self.plan.keywords,
            path_ok,
            self.stats.fragments,
            self.spells.energy,
            self.spells.energy_max,
            plan_preview=(('BOSS' if self.plan.boss else '') + (f"Relics+{self.plan.relics_in_path}" if self.plan.relics_in_path else '')),
        )

        cost = int(self.game.towers_db[self.selected_tower_key]["cost"] * float(self.stats.tower_cost_mul))
        tool_extra = ""
        if self.tool == "PATH":
            _, nm, c = self.path_variants[self.path_variant_idx]
            tool_extra = f"{nm} coût {c} | PAVES {int(self.stats.paves)}"

        draw_bottom_bar(
            screen,
            self.game.fonts,
            self.w,
            self.game_h,
            self.bottom_h,
            self.mode,
            self.tool,
            self.game.towers_db[self.selected_tower_key]["name"],
            cost,
            self.wave_multi,
            tooltip_line="C chemin | B tours | X gomme | G assaut | TAB ciblage | E overclock | SPACE dash | A choc | 1..4 spells | F vitesse | V variante chemin",
            tool_extra=tool_extra,
        )

        # update button visuals
        self.btn_speed.text = f"x{int(self.game.clock.time_scale)}"
        self.btn_tow.text = self.game.towers_db[self.selected_tower_key]["name"]
        self.btn_tow.col = tower_color(self.game.towers_db, self.selected_tower_key)
        self.btn_go.text = f"ASSAUT x{self.wave_multi}" if self.mode == "BUILD" else "EN COURS..."
        self.btn_go.disabled = (self.mode != "BUILD") or (not path_ok)

        # --- bottom buttons (always visible) ---
        for b in self.ui_btns:
            b.draw(screen, self.game.fonts)

        # --- tower dropdown + tooltip ---
        if self.dd_open:
            mx, my = pygame.mouse.get_pos()
            menu_bg = pygame.Rect(
                self.btn_tow.rect.x,
                self.btn_tow.rect.y - len(self.dd_btns) * 52 - 12,
                self.btn_tow.rect.w,
                len(self.dd_btns) * 52 + 12,
            )

            # dropdown panel shadow
            sh = pygame.Surface((menu_bg.w + 12, menu_bg.h + 12), pygame.SRCALPHA)
            pygame.draw.rect(sh, (0, 0, 0, 110), (8, 8, menu_bg.w, menu_bg.h), border_radius=14)
            screen.blit(sh, (menu_bg.x - 8, menu_bg.y - 8))
            pygame.draw.rect(screen, (22, 22, 26), menu_bg, border_radius=14)
            pygame.draw.rect(screen, (90, 90, 105), menu_bg, 2, border_radius=14)

            hover_key = None
            hover_rect = None
            for b in self.dd_btns:
                b.draw(screen, self.game.fonts)
                if b.rect.collidepoint(mx, my):
                    hover_key = b.arg
                    hover_rect = b.rect
                    pygame.draw.rect(screen, (255, 255, 255), b.rect, 2, border_radius=10)

            if hover_key and hover_rect:
                self._draw_tower_tooltip(screen, hover_key, menu_bg, hover_rect)

        # --- tower inspect / upgrade panel ---
        if self.selected_tower:
            t = self.selected_tower
            panel = pygame.Rect(self.w - 390, self.offset_y + 30, 370, 280)
            # keep inside the playable area
            panel.bottom = min(panel.bottom, self.game_h - 12)

            pygame.draw.rect(screen, (22, 22, 26), panel, border_radius=14)
            pygame.draw.rect(screen, (255, 215, 0), panel, 2, border_radius=14)

            lines = [
                f"{t.defn.name}  Lvl {t.level} [{t.defn.role}]",
                f"Ciblage: {['FIRST','LAST','STRONGEST','CLOSEST','ARMORED'][t.target_mode_idx]}",
                f"Branche: {t.branch_choice or '—'}",
                f"Overclock: {'ACTIF' if t.overclock_time>0 else ('READY' if t.can_overclock() else 'CD')}  ({t.overclock_time:.1f}s)",
            ]
            y = panel.y + 14
            for line in lines:
                s = self.game.fonts.s.render(line, True, (240, 240, 240))
                screen.blit(s, (panel.x + 14, y))
                y += 22

            if t.can_branch():
                br_defs = t.defn.branches
                for i, br in enumerate(["A", "B", "C"]):
                    rr = pygame.Rect(panel.x + 20, panel.y + 84 + i * 44, 330, 38)
                    pygame.draw.rect(screen, (60, 70, 80), rr, border_radius=10)
                    pygame.draw.rect(screen, (255, 215, 0), rr, 1, border_radius=10)
                    name = br_defs[br]["name"]
                    desc = br_defs[br]["desc"]
                    txt = self.game.fonts.xs.render(f"{br}: {name} — {desc}", True, (255, 215, 0))
                    screen.blit(txt, (rr.x + 10, rr.y + 11))

            upg = pygame.Rect(panel.x + 20, panel.bottom - 58, 170, 44)
            sell = pygame.Rect(panel.x + 210, panel.bottom - 58, 140, 44)
            pygame.draw.rect(screen, (70, 220, 140), upg, border_radius=10)
            pygame.draw.rect(screen, (220, 90, 90), sell, border_radius=10)
            upg_t = self.game.fonts.s.render(f"UPG ${t.upgrade_cost()}", True, (20, 20, 20))
            screen.blit(upg_t, (upg.centerx - upg_t.get_width() // 2, upg.centery - upg_t.get_height() // 2))
            sell_t = self.game.fonts.s.render(f"SELL ${int(t.spent * float(self.stats.sell_refund))}", True, (20, 20, 20))
            screen.blit(sell_t, (sell.centerx - sell_t.get_width() // 2, sell.centery - sell_t.get_height() // 2))

        # --- top buttons ---
        self.btn_menu.draw(screen, self.game.fonts)
        self.btn_speed.draw(screen, self.game.fonts)
        self.btn_talents.draw(screen, self.game.fonts)
