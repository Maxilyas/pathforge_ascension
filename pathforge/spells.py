from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
import random

@dataclass
class Spell:
    key: str
    name: str
    cost: float
    cd: float

class Spellbook:
    def __init__(self):
        self.energy_max = 100.0
        self.energy = 60.0
        self.regen = 10.0
        self.cooldowns: Dict[str, float] = {}
        self.spells = {
            "METEOR": Spell("METEOR","Météore", 40, 10),
            "FREEZE": Spell("FREEZE","Gel", 35, 14),
            "REPAIR": Spell("REPAIR","Réparation", 25, 18),
            "DRONE":  Spell("DRONE","Drone Strike", 45, 16),
        }

    def tick(self, dt: float, regen_mul: float = 1.0):
        self.energy = min(self.energy_max, self.energy + self.regen*regen_mul*dt)
        for k in list(self.cooldowns.keys()):
            self.cooldowns[k] = max(0.0, self.cooldowns[k] - dt)

    def ready(self, key: str, stats) -> bool:
        s = self.spells[key]
        if self.cooldowns.get(key, 0.0) > 0: return False
        if stats.has_flag("flag_spells_free"): return True
        return self.energy >= s.cost

    def cast(self, key: str, world, stats, pos: Optional[Tuple[int,int]]):
        if key not in self.spells:
            return False
        s = self.spells[key]
        if not self.ready(key, stats):
            world.fx_text(40, world.offset_y+10, "Pas assez d'énergie", (255,120,120), 0.8)
            return False

        # apply cooldown scaling
        self.cooldowns[key] = s.cd * float(stats.spell_cd_mul)
        if not stats.has_flag("flag_spells_free"):
            self.energy -= s.cost

        def dmg_mul(spell_key: str) -> float:
            return float((stats.spell_bonus.get(spell_key) or {}).get("dmg_mul", 1.0))

        # effects
        if key == "METEOR" and pos:
            x,y = pos
            r = world.tile*2.4
            for e in world.query_radius(x,y,r):
                e.take_damage(70*dmg_mul("METEOR"), "FIRE", src="SPELL")
                e.add_status("BURN", 2.5, 2, 0.0)
            world.fx_explosion(x,y,r, (255,150,80), 0.28)

        elif key == "FREEZE" and pos:
            x,y = pos
            r = world.tile*3.0
            for e in world.query_radius(x,y,r):
                e.add_status("SLOW", 2.8, 2, 0.55)
            world.fx_ring(x,y,r,(0,255,255),0.28)

        elif key == "REPAIR":
            stats.core_shield += 12
            stats.lives = min(30, stats.lives + 1)
            world.fx_text(80, world.offset_y+20, "+Shield +Life", (120,255,120), 0.9)

        elif key == "DRONE" and pos:
            x,y = pos
            r = world.tile*1.8
            for e in world.query_radius(x,y,r):
                e.take_damage(85*dmg_mul("DRONE"), "ENERGY", src="SPELL")
                e.add_status("SHOCK", 1.2, 1, 0.0)
            world.fx_ring(x,y,r,(120,200,255),0.22)

        # double cast chance
        if stats.spell_double_chance > 0 and random.random() < stats.spell_double_chance:
            # recast with reduced intensity, no extra cost/cd
            if pos and key in ("METEOR","DRONE","FREEZE"):
                if key == "METEOR":
                    x,y = pos
                    r = world.tile*2.0
                    for e in world.query_radius(x,y,r):
                        e.take_damage(40*dmg_mul("METEOR"), "FIRE", src="SPELL")
                    world.fx_explosion(x,y,r,(255,180,120),0.20)
                if key == "DRONE":
                    x,y = pos
                    r = world.tile*1.5
                    for e in world.query_radius(x,y,r):
                        e.take_damage(50*dmg_mul("DRONE"), "ENERGY", src="SPELL")
                    world.fx_ring(x,y,r,(160,220,255),0.18)
                if key == "FREEZE":
                    x,y = pos
                    r = world.tile*2.4
                    for e in world.query_radius(x,y,r):
                        e.add_status("SLOW", 1.8, 1, 0.45)
                    world.fx_ring(x,y,r,(0,255,255),0.20)

        return True
