from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any
import math

@dataclass
class Projectile:
    x: float
    y: float
    vx: float
    vy: float
    dmg: float
    dmg_type: str
    splash: float
    pierce: int
    ttl: float
    on_hit: Dict[str, Any]
    style: str = "BULLET"

    def update(self, dt: float):
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.ttl -= dt
