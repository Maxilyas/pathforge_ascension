from __future__ import annotations
from dataclasses import dataclass
import math

@dataclass
class HeroState:
    x: float
    y: float
    tx: float
    ty: float
    dash_cd: float = 0.0
    shock_cd: float = 0.0

class Hero:
    def __init__(self, x: float, y: float):
        self.state = HeroState(x,y,x,y)
        self.speed = 340.0

    def set_target(self, x: float, y: float):
        self.state.tx, self.state.ty = x, y

    def dash(self, dx: float, dy: float, world):
        if self.state.dash_cd > 0:
            return
        d = math.hypot(dx,dy)
        if d <= 1e-3:
            return
        nx, ny = dx/d, dy/d
        self.state.x += nx * 180
        self.state.y += ny * 180
        self.state.dash_cd = 1.8
        world.fx_ring(self.state.x, self.state.y, world.tile_size*1.2, (255,255,255), 0.18)

    def shock(self, world):
        if self.state.shock_cd > 0:
            return
        r = world.tile_size * 2.2
        hits = world.query_radius(self.state.x, self.state.y, r)
        if not hits:
            world.fx_text(self.state.x, self.state.y-20, "NO TARGET", (180,180,180), 0.6)
        for e in hits:
            e.take_damage(18, "ENERGY")
            e.add_status("SHOCK", 1.0, 1, 0.0)
        world.fx_arc(self.state.x, self.state.y, self.state.x+r*0.4, self.state.y-r*0.2, (120,200,255), 0.12)
        world.fx_ring(self.state.x, self.state.y, r, (120,200,255), 0.18)
        self.state.shock_cd = 6.0

    def update(self, dt: float, keys, world):
        # cooldowns
        self.state.dash_cd = max(0.0, self.state.dash_cd - dt)
        self.state.shock_cd = max(0.0, self.state.shock_cd - dt)

        # keyboard move (ZQSD + arrows)
        ax = (1 if keys[world.k_right] or keys[world.k_right_alt] else 0) - (1 if keys[world.k_left] or keys[world.k_left_alt] else 0)
        ay = (1 if keys[world.k_down] or keys[world.k_down_alt] else 0) - (1 if keys[world.k_up] or keys[world.k_up_alt] else 0)
        if ax or ay:
            d = math.hypot(ax,ay) or 1.0
            ax, ay = ax/d, ay/d
            self.state.x += ax * self.speed * dt
            self.state.y += ay * self.speed * dt
            self.state.tx, self.state.ty = self.state.x, self.state.y
        else:
            # mouse target drift
            dx,dy = self.state.tx - self.state.x, self.state.ty - self.state.y
            dist = math.hypot(dx,dy)
            if dist > 4:
                nx, ny = dx/dist, dy/dist
                self.state.x += nx * self.speed * dt
                self.state.y += ny * self.speed * dt

        # clamp inside play area
        self.state.x = max(10, min(world.w-10, self.state.x))
        self.state.y = max(world.offset_y+10, min(world.h-10, self.state.y))
