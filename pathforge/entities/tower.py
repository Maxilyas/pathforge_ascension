from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Tuple
import math
from ..settings import T_PATH_CONDUCT, T_PATH_MUD
from .projectile import Projectile

TARGET_MODES = ["FIRST","LAST","STRONGEST","CLOSEST","ARMORED"]

@dataclass
class TowerDef:
    key: str
    name: str
    cost: int
    ui_color: Tuple[int,int,int]
    base: Dict[str, Any]
    dmg_type: str
    role: str
    branches: Dict[str, Any]
    overclock: Dict[str, Any]

@dataclass
class Tower:
    gx: int
    gy: int
    defn: TowerDef
    level: int = 1
    spent: int = 0
    cd: float = 0.0
    branch_choice: Optional[str] = None
    target_mode_idx: int = 0
    overclock_time: float = 0.0
    overclock_cd: float = 0.0
    mods: Dict[str, Any] = field(default_factory=dict)  # dynamic mods (perks)

    kills: int = 0  # for scaling perks later

    def __post_init__(self):
        self.spent = self.defn.cost

    def cycle_target_mode(self):
        self.target_mode_idx = (self.target_mode_idx + 1) % len(TARGET_MODES)

    def can_branch(self) -> bool:
        return self.level >= 3 and self.branch_choice is None

    def can_overclock(self) -> bool:
        return self.overclock_cd <= 0 and self.overclock_time <= 0

    def trigger_overclock(self):
        self.overclock_time = float(self.defn.overclock.get("dur", 4.0))
        self.overclock_cd = float(self.defn.overclock.get("cd", 14.0))

    def upgrade_cost(self) -> int:
        # escalating
        return int(self.defn.cost*0.65 + 40*(self.level))

    def upgrade(self):
        self.level += 1
        self.spent += self.upgrade_cost()

    def apply_branch(self, br: str):
        if br not in self.defn.branches: return
        self.branch_choice = br

    def _branch_mods(self) -> Dict[str, Any]:
        if not self.branch_choice: return {}
        return self.defn.branches[self.branch_choice].get("mods") or {}

    def aura(self) -> Dict[str, float]:
        if self.defn.key != "BEACON":
            return {}
        aura = {"dmg_mul":1.0,"rate_mul":1.0,"range_mul":1.0}
        bm = self._branch_mods()
        if "aura" in bm:
            aura.update(bm["aura"])
        # overclock beacon: stronger aura
        if bm.get("aura_overclock") and self.overclock_time > 0:
            aura["dmg_mul"] *= 1.12
            aura["rate_mul"] *= 1.12
            aura["range_mul"] *= 1.08
        return aura

    def _stat(self, key: str, base_val: float, stats, buffs) -> float:
        # base scaling
        v = base_val
        lvl = max(0, self.level - 1)

        # --- progression: mostly linear + caps (avoid exponential runaway) ---
        # Design goal: towers don't become absurd by leveling alone; synergies (paths/runes/perks/branches) matter.
        if key == "damage":
            # +16% per level up to ~lvl9, then +8% per level (diminishing)
            m1 = 1.0 + 0.16 * min(lvl, 9)
            m2 = 1.0 + 0.08 * max(0, lvl - 9)
            v *= (m1 * m2)
            v *= 1.0  # kept for readability
            v = min(v, base_val * 3.0)  # hard cap relative to base
        if key == "range":
            v *= (1.0 + 0.03 * lvl)
            v = min(v, base_val * 1.45)
        if key == "rate":
            v *= (1.0 + 0.06 * lvl)
            v = min(v, base_val * 1.85)


        # global stats
        if key == "damage":
            v *= float(stats.dmg_mul) * float(buffs.get("dmg_mul", 1.0))
        if key == "range":
            v *= float(stats.range_mul) * float(buffs.get("range_mul", 1.0))
        if key == "rate":
            v *= float(stats.rate_mul) * float(buffs.get("rate_mul", 1.0))

        # perk tower_bonus
        bonus = stats.tower_bonus.get(self.defn.key, {})
        if key == "damage" and "damage_mul" in bonus:
            v *= float(bonus["damage_mul"])
        if key == "range" and "range_mul" in bonus:
            v *= float(bonus["range_mul"])
        if key == "rate" and "rate_mul" in bonus:
            v *= float(bonus["rate_mul"])

        # branch mods
        bm = self._branch_mods()
        if key == "damage" and "damage_mul" in bm:
            v *= float(bm["damage_mul"])
        if key == "range" and "range_mul" in bm:
            v *= float(bm["range_mul"])
        if key == "rate" and "rate_mul" in bm:
            v *= float(bm["rate_mul"])

        # overclock mods
        if self.overclock_time > 0:
            oc = self.defn.overclock.get("mods") or {}
            if key == "damage" and "damage_mul" in oc:
                v *= float(oc["damage_mul"])
            if key == "rate" and "rate_mul" in oc:
                v *= float(oc["rate_mul"])
            if key == "range" and "range_mul" in oc:
                v *= float(oc["range_mul"])
        return v

    def update_timers(self, dt: float):
        self.cd = max(0.0, self.cd - dt)
        self.overclock_time = max(0.0, self.overclock_time - dt)
        self.overclock_cd = max(0.0, self.overclock_cd - dt)

    def _pick_target(self, enemies, cx, cy, rng):
        if not enemies:
            return None
        inr = [e for e in enemies if e.alive and (e.x-cx)**2 + (e.y-cy)**2 <= rng*rng]
        if not inr:
            return None
        mode = TARGET_MODES[self.target_mode_idx]
        if mode == "FIRST":
            return max(inr, key=lambda e: e.idx)
        if mode == "LAST":
            return min(inr, key=lambda e: e.idx)
        if mode == "STRONGEST":
            return max(inr, key=lambda e: e.hp + e.shield)
        if mode == "CLOSEST":
            return min(inr, key=lambda e: (e.x-cx)**2 + (e.y-cy)**2)
        if mode == "ARMORED":
            return max(inr, key=lambda e: e.armor)
        return inr[0]

    def update(self, dt: float, world, rng, stats, buffs):
        self.update_timers(dt)

        tile = world.tile
        cx = self.gx*tile + tile/2
        cy = self.gy*tile + tile/2 + world.offset_y

        # beacon pulses only
        if self.defn.key == "BEACON":
            rng_px = self._stat("range", float(self.defn.base["range"])*tile, stats, buffs)
            if self.overclock_time > 0:
                world.fx_ring(cx, cy, rng_px*0.95, (255,215,0), 0.10)
            else:
                if rng.random() < 0.08:
                    world.fx_ring(cx, cy, rng_px*0.75, (255,215,0), 0.08)
            return

        if self.cd > 0:
            return

        rng_px = self._stat("range", float(self.defn.base["range"])*tile, stats, buffs)
        dmg = self._stat("damage", float(self.defn.base["damage"]), stats, buffs)
        rate = self._stat("rate", float(self.defn.base["rate"]), stats, buffs)
        cooldown = max(0.02, 1.0 / max(0.01, rate))

        # specials by tower type
        if self.defn.key == "CRYO":
            # AOE slow around
            targets = world.query_radius(cx, cy, rng_px)
            if not targets:
                return
            strength = 0.35 + float(self._branch_mods().get("slow_strength_add", 0.0)) + float(stats.tower_bonus.get("CRYO", {}).get("slow_strength_add", 0.0))
            for e in targets:
                e.take_damage(dmg, "COLD")
                e.add_status("SLOW", 1.4, 1, strength)
                # optional stun
                bm = self._branch_mods()
                if bm.get("stun_chance") and rng.random() < float(bm["stun_chance"]):
                    e.add_status("STUN", float(bm.get("stun_dur", 0.25)), 1, 0.0)
                # on-hit extras
                for k,v in (bm.get("on_hit", {}) or {}).items():
                    e.add_status(k, float(v.get("dur",1.0)), int(v.get("stacks",1)), float(v.get("strength",0.0)))
            world.fx_ring(cx, cy, rng_px, (0,255,255), 0.18)
            self.cd = cooldown
            return

        if self.defn.key == "FLAME":
            targets = world.query_radius(cx, cy, rng_px)
            if not targets:
                return
            burn_stacks = 1 + int(self._branch_mods().get("burn_stacks_add", 0))
            for e in targets:
                e.take_damage(dmg, "FIRE")
                e.add_status("BURN", 2.2, burn_stacks, 0.0)
                bm = self._branch_mods()
                for k,v in (bm.get("on_hit", {}) or {}).items():
                    e.add_status(k, float(v.get("dur",1.0)), int(v.get("stacks",1)), float(v.get("strength",0.0)))
                # global poison flag from perks can be applied by GameScene setting mods on tower
                for k,v in (self.mods.get("on_hit", {}) or {}).items():
                    e.add_status(k, float(v.get("dur",1.0)), int(v.get("stacks",1)), float(v.get("strength",0.0)))
            # flame particles
            for _ in range(6):
                ang = rng.random()*math.tau
                world.fx_tracer(cx, cy, cx+math.cos(ang)*rng_px*0.7, cy+math.sin(ang)*rng_px*0.7, (255,120,70), 0.06, 2)
            self.cd = cooldown
            return

        if self.defn.key == "TESLA":
            # chain lightning
            first = self._pick_target(world.enemies, cx, cy, rng_px)
            if not first:
                return
            chains = 2 + int(self._branch_mods().get("chains_add", 0)) + int(stats.tower_bonus.get("TESLA", {}).get("chains_add", 0)) + int(buffs.get("tesla_chains_add", 0))
            # conductive tiles let Tesla "branch" more aggressively
            if world.adjacent_path_count(self.gx, self.gy, T_PATH_CONDUCT) > 0:
                chains += 1
            shock_dur = 1.0 + float(self._branch_mods().get("shock_dur_add", 0.0))
            first.take_damage(dmg, "ENERGY", weakness_mul=getattr(world, "weakness_mul", 1.8))
            first.add_status("SHOCK", shock_dur, 1, 0.0)
            world.fx_arc(cx, cy, first.x, first.y, (100,200,255), 0.14)
            used_ids = {id(first)}
            curr = first
            for _ in range(chains):
                near = [e for e in world.query_radius(curr.x, curr.y, tile*3.0) if id(e) not in used_ids]
                if not near:
                    break
                nxt = min(near, key=lambda e: (e.x-curr.x)**2+(e.y-curr.y)**2)
                used_ids.add(id(nxt))
                nxt.take_damage(dmg*0.72, "ENERGY", weakness_mul=getattr(world, "weakness_mul", 1.8))
                nxt.add_status("SHOCK", shock_dur, 1, 0.0)
                world.fx_arc(curr.x, curr.y, nxt.x, nxt.y, (100,200,255), 0.12)
                curr = nxt
            self.cd = cooldown
            return

        # projectile towers
        target = self._pick_target(world.enemies, cx, cy, rng_px)
        if not target:
            return

        # mud lanes reduce projectile accuracy (risk/reward with slow lanes)
        if getattr(target, "tile_v", None) == T_PATH_MUD:
            miss = 0.24
            if self.defn.key == "SNIPER":
                miss = 0.15
            if rng.random() < miss:
                ox = (rng.random() - 0.5) * tile * 0.6
                oy = (rng.random() - 0.5) * tile * 0.6
                world.fx_tracer(cx, cy, target.x + ox, target.y + oy, (160, 160, 170), 0.06, 1)
                world.fx_text(target.x - 10, target.y - 24, "MISS", (190, 190, 205), 0.25)
                self.cd = cooldown
                return

        # base projectile parameters
        spd = float(self.defn.base.get("proj_speed", 12.0)) * tile
        dx, dy = target.x - cx, target.y - cy
        dist = math.hypot(dx,dy) or 1.0
        vx, vy = (dx/dist)*spd, (dy/dist)*spd

        splash = float(self.defn.base.get("splash", 0.0))
        pierce = int(self.defn.base.get("pierce", 0))

        bm = self._branch_mods()
        splash += float(bm.get("splash_add", 0.0))
        pierce += int(bm.get("pierce_add", 0))

        # global flags can force splash
        if world.flag_all_projectiles_splash:
            splash = max(splash, 0.55)

        style = "BULLET"
        if self.defn.key == "SNIPER": style = "SNIPER"
        if self.defn.key == "MORTAR": style = "MORTAR"
        if self.defn.key == "CANNON": style = "SHELL"

        # multishot
        extra = int(bm.get("multishot", 0))
        total = 1 + extra

        for i in range(total):
            spread = (i - (total-1)/2) * 0.07
            svx = vx*math.cos(spread) - vy*math.sin(spread)
            svy = vx*math.sin(spread) + vy*math.cos(spread)

            p = Projectile(
                x=cx, y=cy, vx=svx, vy=svy,
                dmg=dmg, dmg_type=self.defn.dmg_type,
                splash=splash, pierce=pierce, ttl=2.6,
                on_hit=(bm.get("on_hit") or {}),
                style=style
            )
            world.projectiles.append(p)

        # muzzle feedback
        if style == "SNIPER":
            world.fx_tracer(cx, cy, target.x, target.y, (220,220,240), 0.10, 3)
        else:
            world.fx_tracer(cx, cy, target.x, target.y, (255,230,180), 0.05, 2)

        # AP rounds: armor shred via branch
        if bm.get("armor_shred"):
            target.add_status("SHRED", 2.5, 1, 0.0)
            target.armor = max(0, target.armor - float(bm["armor_shred"]))

        # hunter scaling perk placeholder could be added later

        self.cd = cooldown
