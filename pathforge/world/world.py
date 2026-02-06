from __future__ import annotations
from typing import List, Tuple, Optional, Dict, Any
import pygame, math, random

from ..settings import (
    T_EMPTY, T_TOWER, T_START, T_END, T_ROCK, T_RELIC,
    T_PATH, T_PATH_FAST, T_PATH_MUD, T_PATH_CONDUCT, T_PATH_CRYO, T_PATH_MAGMA, T_PATH_RUNE,
    PATH_TILES,
    C_BG, C_GRID, C_ROCK, C_PATH, C_PATH_FAST, C_PATH_MUD, C_PATH_CONDUCT, C_PATH_CRYO, C_PATH_MAGMA, C_PATH_RUNE,
    C_START, C_END
)
from .pathfinding import bfs_path, distance_map, chain_path
from .grid import GridState, tile
from ..entities.enemy import Enemy, EnemyArch
from ..entities.tower import Tower, TowerDef
from ..entities.hero import Hero
from ..entities.projectile import Projectile

def buildable_for_tower(v: int) -> bool:
    return v in (T_EMPTY,)



# --- Path tile properties (forge pillar) ---
PATH_COLORS = {
    T_PATH: C_PATH,
    T_PATH_FAST: C_PATH_FAST,
    T_PATH_MUD: C_PATH_MUD,
    T_PATH_CONDUCT: C_PATH_CONDUCT,
    T_PATH_CRYO: C_PATH_CRYO,
    T_PATH_MAGMA: C_PATH_MAGMA,
    T_PATH_RUNE: C_PATH_RUNE,
    T_START: C_START,
    T_END: C_END,
}

PATH_COST = {
    T_PATH: 1,
    # premium tiles (expensive but powerful)
    T_PATH_FAST: 6,       # risk/reward lane
    T_PATH_MUD: 6,        # hard slow lane (projectiles less reliable)
    T_PATH_CONDUCT: 8,    # enables ENERGY synergies + runes powering (if on rune cells)
    T_PATH_CRYO: 9,       # extends slows, mitigates FIRE
    T_PATH_MAGMA: 9,      # reliable burn chip, anti-regen
    T_PATH_RUNE: 14,      # high-impact vulnerability lane
}
PATH_SPEED_MUL = {
    T_PATH: 1.00,
    T_PATH_FAST: 1.55,
    T_PATH_MUD: 0.35,
    T_PATH_CONDUCT: 1.00,
    T_PATH_CRYO: 0.85,
    T_PATH_MAGMA: 0.95,
    T_PATH_RUNE: 1.00,
}
def is_path_tile(v: int) -> bool:
    return v in PATH_TILES


class World:
    def __init__(self, gs: GridState, tile_size: int, offset_x: int, offset_y: int, w: int, h: int, towers_db: dict, enemies_db: dict, rng: random.Random):
        self.gs = gs
        self.tile = tile_size
        self.tile_size = tile_size  # alias for hero/spells/vfx
        self.offset_x = offset_x
        self.offset_y = offset_y
        self.w = w
        self.h = h
        self.towers_db = towers_db
        self.enemies_db = enemies_db
        self.rng = rng

        self.towers: List[Tower] = []
        self.enemies: List[Enemy] = []
        self.projectiles: List[Projectile] = []
        self.fx: List[dict] = []

        self._cached_path: Optional[List[Tuple[int,int]]] = None
        self._cached_dist: Optional[dict] = None
        self._cached_dist_ends: Optional[tuple] = None
        self._cached_reach: Optional[set] = None
        self._cached_powered_runes: Optional[list] = None

        self.hero = Hero(w*0.12, offset_y + (h-offset_y)*0.70)

        # key mapping (set by scene)
        self.k_left = pygame.K_q; self.k_right = pygame.K_d; self.k_up = pygame.K_z; self.k_down = pygame.K_s
        self.k_left_alt = pygame.K_LEFT; self.k_right_alt = pygame.K_RIGHT; self.k_up_alt = pygame.K_UP; self.k_down_alt = pygame.K_DOWN

        # game flags (set by scene)
        self.weakness_mul = 1.8
        self.enemy_speed_mul = 1.0
        self.flag_all_projectiles_splash = False
        self.flag_chain_reaction = False

        # simple spatial (list-based)
        self._spatial: List[Enemy] = []

    # ---- FX helpers ----
    def fx_tracer(self, x1,y1,x2,y2,color=(255,230,180), ttl=0.08, w=2):
        self.fx.append({"t":"TR","x1":x1,"y1":y1,"x2":x2,"y2":y2,"c":color,"ttl":ttl,"life":ttl,"w":w})

    def fx_ring(self, x,y,r,color,ttl=0.18):
        self.fx.append({"t":"R","x":x,"y":y,"r":2,"mr":r,"c":color,"ttl":ttl,"life":ttl})

    def fx_explosion(self, x,y,r,color=(255,150,80), ttl=0.22):
        self.fx.append({"t":"EX","x":x,"y":y,"r":2,"mr":r,"c":color,"ttl":ttl,"life":ttl})

    def fx_arc(self, x1,y1,x2,y2,color=(100,200,255), ttl=0.12):
        pts=[(x1,y1)]
        segs=6
        dx=x2-x1; dy=y2-y1
        dist=math.hypot(dx,dy) or 1.0
        nx,ny=-dy/dist, dx/dist
        for i in range(1,segs):
            t=i/segs
            px=x1+dx*t
            py=y1+dy*t
            j=(self.rng.random()-0.5)*14
            pts.append((px+nx*j, py+ny*j))
        pts.append((x2,y2))
        self.fx.append({"t":"ARC","pts":pts,"c":color,"ttl":ttl,"life":ttl})

    def fx_text(self, x,y,txt,color=(255,255,255), ttl=0.7):
        self.fx.append({"t":"TXT","x":x,"y":y,"txt":txt,"c":color,"ttl":ttl,"life":ttl})

    def update_fx(self, dt: float):
        for f in list(self.fx):
            f["ttl"] -= dt
            if f["t"] in ("R","EX"):
                f["r"] += self.tile*3.2*dt
            if f["ttl"] <= 0:
                self.fx.remove(f)

    # ---- spatial ----
    def rebuild_spatial(self):
        self._spatial = [e for e in self.enemies if e.alive and not e.finished]

    def query_radius(self, x: float, y: float, r: float) -> List[Enemy]:
        rr = r*r
        out=[]
        for e in self._spatial:
            if (e.x-x)**2 + (e.y-y)**2 <= rr:
                out.append(e)
        return out

    # ---- grid/path ----
    def path_valid(self) -> bool:
        p = self.get_path()
        return p is not None and len(p) >= 2

    def get_path(self) -> Optional[List[Tuple[int,int]]]:
        if self._cached_path is None:
            self._cached_path = chain_path(self.gs.grid, self.gs.start, self.gs.end)
        return self._cached_path

    def invalidate_path(self):
        self._cached_path = None
        self._cached_dist = None
        self._cached_dist_ends = None
        self._cached_reach = None
        self._cached_powered_runes = None

    def get_distmap(self):
        """Distance-to-end map for branching lanes (cached)."""
        ends = (self.gs.end,)
        if self._cached_dist is None or self._cached_dist_ends != ends:
            self._cached_dist = distance_map(self.gs.grid, [self.gs.end])
            self._cached_dist_ends = ends
        return self._cached_dist

    def reachable_from_start(self) -> set:
        """Cells reachable from START through any path tiles (cached)."""
        if self._cached_reach is not None:
            return self._cached_reach
        from collections import deque
        seen = set()
        q = deque([self.gs.start])
        seen.add(self.gs.start)
        while q:
            cx, cy = q.popleft()
            for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
                nx, ny = cx+dx, cy+dy
                if 0 <= nx < self.gs.cols and 0 <= ny < self.gs.rows:
                    if (nx, ny) in seen:
                        continue
                    if is_path_tile(self.gs.grid[nx][ny]):
                        seen.add((nx, ny))
                        q.append((nx, ny))
        self._cached_reach = seen
        return seen

    def powered_runes(self) -> list:
        """Runes become active only if: (1) the rune cell is reachable from START through path tiles,
        and (2) the tile on that cell is CONDUCTIVE. This makes conductive path routing a real choice."""
        if self._cached_powered_runes is not None:
            return self._cached_powered_runes
        reach = self.reachable_from_start()
        out = []
        for r in getattr(self.gs, "runes", []):
            if r in reach:
                gx, gy = r
                if self.gs.grid[gx][gy] == T_PATH_CONDUCT:
                    out.append(r)
        self._cached_powered_runes = out
        return out

    def next_cell(self, cell: Tuple[int,int], prev: Optional[Tuple[int,int]], rng: random.Random) -> Optional[Tuple[int,int]]:
        """Pick the next step towards the end. Supports forks/branches."""
        dist = self.get_distmap()
        if cell not in dist:
            return None
        cx, cy = cell
        opts = []
        best = dist[cell]
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx,ny = cx+dx, cy+dy
            if 0<=nx<self.gs.cols and 0<=ny<self.gs.rows and is_path_tile(self.gs.grid[nx][ny]):
                nd = dist.get((nx,ny))
                if nd is None:
                    continue
                if nd < best:
                    opts.append((nx,ny))
        if not opts:
            # no downhill neighbor (dead-end or end)
            return None
        # avoid bouncing back if possible
        if prev in opts and len(opts) > 1:
            opts = [o for o in opts if o != prev]
        return rng.choice(opts)

    def tile_value_at(self, x: float, y: float) -> int:
        tc = self.tile_at_pixel(int(x), int(y))
        if not tc:
            return T_EMPTY
        return self.gs.grid[tc[0]][tc[1]]


    def adjacent_path_count(self, gx: int, gy: int, tile_value: int) -> int:
        c = 0
        for dx, dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nx, ny = gx+dx, gy+dy
            if 0 <= nx < self.gs.cols and 0 <= ny < self.gs.rows:
                if self.gs.grid[nx][ny] == tile_value:
                    c += 1
        return c

    def is_relic(self, gx: int, gy: int) -> bool:
        return (gx, gy) in set(getattr(self.gs, "relics", []))

    def is_rune(self, gx: int, gy: int) -> bool:
        return (gx, gy) in set(getattr(self.gs, "runes", []))


    def path_speed_mul(self, tile_v: int) -> float:
        return float(PATH_SPEED_MUL.get(tile_v, 1.0))

    def path_cost(self, tile_v: int) -> int:
        return int(PATH_COST.get(tile_v, 1))

    def corrupt_near(self, cell: Tuple[int,int], rng: random.Random):
        """Corrupt a nearby path tile (used by sapper-type enemies)."""
        cx, cy = cell
        cand = []
        for dx in (-1,0,1):
            for dy in (-1,0,1):
                nx, ny = cx+dx, cy+dy
                if 0<=nx<self.gs.cols and 0<=ny<self.gs.rows:
                    v = self.gs.grid[nx][ny]
                    if is_path_tile(v) and v not in (T_START, T_END):
                        cand.append((nx,ny))
        if not cand:
            return
        nx, ny = rng.choice(cand)
        v = self.gs.grid[nx][ny]
        # convert any path variant into mud; if already mud, crack into standard
        if v == T_PATH_MUD:
            self.gs.grid[nx][ny] = T_PATH
        else:
            self.gs.grid[nx][ny] = T_PATH_MUD
        self.invalidate_path()
        self.fx_text(self.offset_x + nx*self.tile, ny*self.tile + self.offset_y, "CORRUPTION", (255,160,120), 0.6)

    def build_path_tile(self, gx:int, gy:int, tile_value: int = T_PATH) -> bool:
        v = self.gs.grid[gx][gy]
        # never overwrite terminals/rocks/towers
        if v in (T_START, T_END, T_ROCK, T_TOWER):
            return False
        if v == tile_value:
            return False
        # allow building over empty, relic, or other path variants
        if v in (T_EMPTY, T_RELIC) or is_path_tile(v):
            self.gs.grid[gx][gy] = int(tile_value)
            self.invalidate_path()
            return True
        return False

    def erase_tile(self, gx:int, gy:int):
        v = self.gs.grid[gx][gy]
        if v == T_TOWER:
            t = self.tower_at(gx,gy)
            if t:
                self.remove_tower(t)
            self.gs.grid[gx][gy] = T_EMPTY
            self.invalidate_path()
            return

        if is_path_tile(v) and v not in (T_START, T_END):
            # overlays (relics/runes) live outside the grid, so we just clear the tile
            self.gs.grid[gx][gy] = T_EMPTY
            self.invalidate_path()
            return

    def tile_at_pixel(self, x: int, y: int) -> Optional[Tuple[int,int]]:
        if y < self.offset_y or y >= self.h:
            return None
        x2 = x - self.offset_x
        if x2 < 0 or x2 >= self.gs.cols * self.tile:
            return None
        gx = x2 // self.tile
        gy = (y - self.offset_y) // self.tile
        if 0<=gx<self.gs.cols and 0<=gy<self.gs.rows:
            return gx, gy
        return None

    # ---- towers ----
    def tower_at(self, gx:int, gy:int) -> Optional[Tower]:
        for t in self.towers:
            if t.gx==gx and t.gy==gy:
                return t
        return None

    def add_tower(self, gx:int, gy:int, key: str, allow_on_rock: bool=False) -> Optional[Tower]:
        v = self.gs.grid[gx][gy]
        if not (v == T_EMPTY or (allow_on_rock and v == T_ROCK)):
            return None
        if key not in self.towers_db:
            return None
        td = self.towers_db[key]
        tdef = TowerDef(
            key=key,
            name=td["name"],
            cost=int(td["cost"]),
            ui_color=tuple(td.get("ui_color",[200,200,200])),
            base=td["base"],
            dmg_type=td["dmg_type"],
            role=td.get("role",""),
            branches=td.get("branches",{}),
            overclock=td.get("overclock",{}),
        )
        t = Tower(gx=gx, gy=gy, defn=tdef)
        self.towers.append(t)
        self.gs.grid[gx][gy] = T_TOWER
        self.invalidate_path()
        return t

    def remove_tower(self, t: Tower):
        if t in self.towers:
            self.towers.remove(t)
            if 0<=t.gx<self.gs.cols and 0<=t.gy<self.gs.rows:
                self.gs.grid[t.gx][t.gy] = T_EMPTY
            self.invalidate_path()

    # ---- enemies ----
    def _enemy_arch(self, key: str) -> EnemyArch:
        d = self.enemies_db[key]
        return EnemyArch(
            key=key,
            name=d["name"],
            color=tuple(d["color"]),
            spd=float(d["spd"]),
            hp=float(d["hp"]),
            armor=float(d.get("armor",0)),
            regen=float(d.get("regen",0)),
            shield=float(d.get("shield",0)),
            weak=d.get("weak"),
            tags=list(d.get("tags",[])),
            resist=dict(d.get("resist", {}) or {}),
            shield_mult=dict(d.get("shield_mult", {}) or {}),
            desc=str(d.get("desc", "") or "")
        )

    def spawn_enemy(self, key: str, wave: int, gold_bonus: int = 0):
        p = self.get_path()
        if not p:
            return None
        arch = self._enemy_arch(key)
        e = Enemy(
            arch=arch, path=p, tile=self.tile, offset_x=self.offset_x, offset_y=self.offset_y,
            wave=wave, weakness_mul=self.weakness_mul, speed_mul=self.enemy_speed_mul,
            gold_bonus=gold_bonus
        )
        # branch-capable movement setup
        e.cell = p[0]
        e.prev_cell = None
        e.next_cell = self.next_cell(e.cell, None, self.rng)
        # idx as progress proxy (closer to end => higher)
        dmap = self.get_distmap()
        e.idx = -int(dmap.get(e.cell, 9999))
        self.enemies.append(e)
        return e

    # ---- projectiles ----
    def update_projectiles(self, dt: float):
        self.rebuild_spatial()
        for p in list(self.projectiles):
            p.update(dt)
            if p.ttl <= 0:
                self.projectiles.remove(p)
                continue

            # collision check with nearest in radius
            hit = None
            for e in self._spatial:
                if (e.x-p.x)**2 + (e.y-p.y)**2 < (self.tile*0.35)**2:
                    hit = e; break
            if not hit:
                continue

            # apply hit
            hit.take_damage(p.dmg, p.dmg_type)

            # statuses from on_hit
            for sk, sv in (p.on_hit or {}).items():
                try:
                    chance = float(sv.get("chance", 1.0))
                except Exception:
                    chance = 1.0
                if chance < 1.0 and self.rng.random() > chance:
                    continue
                hit.add_status(sk, float(sv.get("dur", 1.5)), int(sv.get("stacks",1)), float(sv.get("strength",0.0)))

            # splash
            if p.splash and p.splash > 0:
                r = p.splash * self.tile
                targets = self.query_radius(hit.x, hit.y, r)
                for e in targets:
                    if e is hit: 
                        continue
                    e.take_damage(p.dmg*0.55, p.dmg_type)
                # fx
                col = (255,150,80) if p.dmg_type=="FIRE" else (200,210,240)
                self.fx_explosion(hit.x, hit.y, r, col, 0.18)
                if self.flag_chain_reaction:
                    self.fx_explosion(hit.x, hit.y, r*0.45, (255,220,160), 0.12)

            # tracer on hit
            if p.style == "SNIPER":
                self.fx_tracer(p.x, p.y, hit.x, hit.y, (255,255,255), 0.12, 3)

            # pierce
            if p.pierce > 0:
                p.pierce -= 1
            else:
                self.projectiles.remove(p)

    # ---- draw ----
    def draw_map(self, screen, fonts, biome_tint=(24,32,44)):
        screen.fill(C_BG)

        relics = set(getattr(self.gs, 'relics', []))
        runes = set(getattr(self.gs, 'runes', []))
        powered_runes = set(self.powered_runes())

        # grid
        for x in range(self.gs.cols):
            for y in range(self.gs.rows):
                rr = pygame.Rect(self.offset_x + x*self.tile, y*self.tile+self.offset_y, self.tile, self.tile)
                v = self.gs.grid[x][y]
                if v == T_ROCK:
                    pygame.draw.rect(screen, C_ROCK, rr)
                    pygame.draw.circle(screen, (75,65,55), rr.center, self.tile//3)
                else:
                    pygame.draw.rect(screen, C_GRID, rr, 1)

                if is_path_tile(v):
                    colp = PATH_COLORS.get(v, C_PATH)
                    pygame.draw.rect(screen, colp, rr.inflate(-10,-10))
                    # subtle glyphs for special path tiles
                    if v == T_PATH_CONDUCT:
                        pygame.draw.line(screen, (210,235,255), (rr.centerx-rr.w//4, rr.centery), (rr.centerx+rr.w//4, rr.centery), 3)
                    elif v == T_PATH_CRYO:
                        pygame.draw.circle(screen, (220,255,255), rr.center, rr.w//6, 2)
                    elif v == T_PATH_MAGMA:
                        pygame.draw.circle(screen, (255,180,120), rr.center, rr.w//7)
                    elif v == T_PATH_RUNE:
                        pygame.draw.circle(screen, (230,200,255), rr.center, rr.w//5, 2)

                if v == T_RELIC:
                    pygame.draw.rect(screen, (40,55,45), rr.inflate(-10,-10))

                # relic overlay (relics never disappear; they can be paved over)
                if (x,y) in relics:
                    pygame.draw.circle(screen, (255,215,0), rr.center, self.tile//6)
                # rune overlay (rare). Powered runes glow and buff nearby towers.
                if (x,y) in runes:
                    # diamond
                    cx, cy = rr.center
                    s = self.tile//6
                    pts = [(cx, cy-s), (cx+s, cy), (cx, cy+s), (cx-s, cy)]
                    col = (230, 190, 255) if (x,y) in powered_runes else (140, 90, 170)
                    pygame.draw.polygon(screen, col, pts, 0)
                    if (x,y) in powered_runes:
                        pygame.draw.circle(screen, (255, 230, 255), rr.center, self.tile//4, 2)
                        pygame.draw.circle(screen, (255, 230, 255), rr.center, self.tile//3, 1)

                if v == T_START:
                    pygame.draw.rect(screen, C_START, rr)
                if v == T_END:
                    pygame.draw.rect(screen, C_END, rr)

        # towers
        for t in self.towers:
            rr = pygame.Rect(self.offset_x + t.gx*self.tile+4, t.gy*self.tile+self.offset_y+4, self.tile-8, self.tile-8)
            col = t.defn.ui_color
            pygame.draw.rect(screen, col, rr, border_radius=6)
            # make Beacon visually distinct (glyph + ring)
            if t.defn.key == "BEACON":
                pygame.draw.circle(screen, (255,255,255), rr.center, int(self.tile*0.18))
                pygame.draw.circle(screen, (255,255,255), rr.center, int(self.tile*0.34), 2)
                pygame.draw.line(screen, (255,255,255), (rr.centerx, rr.y+8), (rr.centerx, rr.bottom-8), 2)
                pygame.draw.line(screen, (255,255,255), (rr.x+8, rr.centery), (rr.right-8, rr.centery), 2)
            # overclock glow
            if t.overclock_time > 0:
                pygame.draw.circle(screen, (255,240,140), rr.center, int(self.tile*0.55), 2)
                pygame.draw.circle(screen, (255,240,140), rr.center, int(self.tile*0.70), 1)
            # pips (fit within tile, even on small tiles)
            n = min(6, t.level)
            if n > 0:
                pad = 6
                span = max(1, rr.w - pad*2)
                step = span / max(1, n)
                for i in range(n):
                    px = int(rr.x + pad + step*(i+0.5))
                    pygame.draw.circle(screen, (255,255,255), (px, rr.bottom-6), 2)

        # enemies
        for e in self.enemies:
            if not e.alive:
                continue
            r = int(self.tile*0.30) + (10 if "BOSS" in e.arch.tags else 0)
            pygame.draw.circle(screen, e.arch.color, (int(e.x),int(e.y)), r)
            # HP bar
            w = 30 if "BOSS" not in e.arch.tags else 52
            pygame.draw.rect(screen, (220,0,0), (e.x-w//2, e.y-20-r//2, w, 5))
            pygame.draw.rect(screen, (0,220,90), (e.x-w//2, e.y-20-r//2, w*max(0, e.hp/e.max_hp), 5))
            if e.shield > 0:
                pygame.draw.rect(screen, (90,160,255), (e.x-w//2, e.y-26-r//2, w*min(1, e.shield/(e.max_hp*0.6)), 3))

        # hero
        pygame.draw.circle(screen, (240,240,240), (int(self.hero.state.x), int(self.hero.state.y)), int(self.tile*0.22))
        pygame.draw.circle(screen, (120,200,255), (int(self.hero.state.x), int(self.hero.state.y)), int(self.tile*0.22), 2)

        # projectiles
        for p in self.projectiles:
            if p.style in ("MORTAR","SHELL"):
                pygame.draw.circle(screen, (230,230,240), (int(p.x),int(p.y)), 4)
            else:
                pygame.draw.circle(screen, (255,230,180), (int(p.x),int(p.y)), 3)

        # fx
        fx_surf = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        for f in self.fx:
            t = f["t"]
            ttl = max(0.0, f["ttl"])
            life = max(0.001, f["life"])
            a = int(255*min(1.0, ttl/life))
            if t == "TR":
                c = (*f["c"], a)
                pygame.draw.line(fx_surf, c, (f["x1"], f["y1"]), (f["x2"], f["y2"]), int(f.get("w",2)))
            elif t == "R":
                c = (*f["c"], a)
                pygame.draw.circle(fx_surf, c, (int(f["x"]),int(f["y"])), int(f["r"]), 2)
            elif t == "EX":
                c = (*f["c"], a)
                pygame.draw.circle(fx_surf, c, (int(f["x"]),int(f["y"])), int(f["r"]), 0)
            elif t == "ARC":
                c = (*f["c"], a)
                pts = [(int(x),int(y)) for x,y in f["pts"]]
                if len(pts) >= 2:
                    pygame.draw.lines(fx_surf, c, False, pts, 2)
            elif t == "TXT":
                txt = fonts.s.render(f["txt"], True, f["c"])
                fx_surf.blit(txt, (f["x"], f["y"]))
        screen.blit(fx_surf, (0,0))
