from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List, Tuple, Optional
import math

from .status import Status
from ..settings import (
    T_EMPTY, T_END,
    T_PATH_FAST, T_PATH_MUD, T_PATH_CONDUCT, T_PATH_CRYO, T_PATH_MAGMA, T_PATH_RUNE,
)

@dataclass
class EnemyArch:
    key: str
    name: str
    color: Tuple[int,int,int]
    spd: float
    hp: float
    armor: float
    regen: float
    shield: float
    weak: str|None
    tags: List[str]
    resist: Dict[str, float] = field(default_factory=dict)
    shield_mult: Dict[str, float] = field(default_factory=dict)
    desc: str = ""

@dataclass
class Enemy:
    arch: EnemyArch
    path: List[Tuple[int,int]]  # kept for spawn compatibility / legacy
    tile: int
    offset_x: int
    offset_y: int
    wave: int
    weakness_mul: float
    speed_mul: float
    gold_bonus: int = 0

    # movement (branch-capable)
    cell: Tuple[int,int] = (0,0)
    prev_cell: Optional[Tuple[int,int]] = None
    next_cell: Optional[Tuple[int,int]] = None

    idx: int = 0  # used for targeting modes (FIRST/LAST); higher = closer to end
    path_i: int = 0  # legacy fixed-path index (used when branching fails)
    x: float = 0.0
    y: float = 0.0

    hp: float = 1.0
    max_hp: float = 1.0
    shield: float = 0.0
    armor: float = 0.0
    base_speed: float = 1.0

    alive: bool = True
    finished: bool = False

    statuses: Dict[str, Status] = field(default_factory=dict)

    boss_phase: int = 0
    spawn_signals: List[str] = field(default_factory=list)

    reward_gold: int = 5
    tile_gold_bonus: int = 0
    tile_v: int = T_EMPTY

    _sapper_t: float = 0.0

    def __post_init__(self):
        self.x, self.y = self._pos(self.path[0])
        self.cell = self.path[0]
        self.path_i = 0
        tier = 1.0 + 0.23 * (self.wave-1)
        self.max_hp = 30.0 * float(self.arch.hp) * tier
        self.hp = self.max_hp
        self.armor = float(self.arch.armor)
        self.base_armor = self.armor
        self.armor_eff = self.armor
        self.vuln_mult = 1.0
        self.resist = dict(self.arch.resist or {})
        self.shield_mult = dict(self.arch.shield_mult or {})
        self.shield = float(self.arch.shield) * 8.0 * tier  # shield scales slower than HP
        self.base_speed = float(self.arch.spd) * float(self.tile) * float(self.speed_mul)
        self.reward_gold = int(5 + self.wave * 1.6) + int(self.gold_bonus)
        self.tile_gold_bonus = 0
        self.tile_v = T_EMPTY

    def _pos(self, c: Tuple[int,int]):
        return c[0] * self.tile + self.tile/2 + self.offset_x, c[1] * self.tile + self.tile/2 + self.offset_y

    def is_elite(self) -> bool:
        return "ELITE" in self.arch.tags

    def take_damage(self, amt: float, dmg_type: str, weakness_mul: float = 1.8):
        if not self.alive:
            return False

        # terrain interactions (minimal but meaningful)
        if dmg_type == "FIRE" and self.tile_v == T_PATH_CRYO:
            amt *= 0.80

        crit = False

        # vulnerability (VULN status)
        amt *= float(getattr(self, "vuln_mult", 1.0))

        # shield first (with type effectiveness; ENERGY usually drains shield faster)
        if self.shield > 0:
            sm = float((self.shield_mult or {}).get(dmg_type, 1.0))
            eff = amt * sm
            if eff <= self.shield:
                self.shield -= eff
                return crit
            # shield breaks; carry remainder to HP space
            eff_rem = eff - self.shield
            self.shield = 0.0
            amt = eff_rem / max(0.01, sm)

        # armor vs kinetic/pierce/explosive (SHRED reduces armor_eff)
        armor = float(getattr(self, "armor_eff", self.armor))
        if dmg_type in ("KINETIC","PIERCE","EXPLOSIVE"):
            red = armor
            if dmg_type == "PIERCE":
                red *= 0.5
            amt = max(1.0, amt - red)

        # weakness
        if self.arch.weak and dmg_type == self.arch.weak:
            amt *= float(getattr(self, 'weakness_mul', weakness_mul))
            crit = True

        # resistances (final multipliers)
        rm = float((self.resist or {}).get(dmg_type, 1.0))
        amt *= rm

        self.hp -= amt
        if self.hp <= 0 and self.alive:
            self.alive = False
        return crit

    def add_status(self, k: str, dur: float, stacks: int, strength: float):
        s = self.statuses.get(k)
        if not s:
            self.statuses[k] = Status(kind=k, dur=dur, stacks=stacks, strength=strength)
        else:
            s.dur = max(s.dur, dur)
            # Some statuses should refresh / keep the strongest stack, not accumulate every hit.
            if k in ("SLOW","BURN","POISON","SHOCK","STUN"):
                s.stacks = max(s.stacks, stacks)
            else:
                s.stacks = min(10, s.stacks + stacks)
            s.strength = max(s.strength, strength)

    def _apply_tile_effects(self, world, rng):
        # compute tile under current position
        self.tile_v = world.tile_value_at(self.x, self.y) if world else T_EMPTY

        # gold bonus if killed on FAST tiles (risk/reward)
        self.tile_gold_bonus = 2 if self.tile_v == T_PATH_FAST else 0

        # magma applies light burn
        if self.tile_v == T_PATH_MAGMA:
            # soft burn, stacks slowly
            if rng and rng.random() < 0.25:
                self.add_status("BURN", 1.8, 1, 0.0)

        # cryo tiles strengthen slows a bit
        if self.tile_v == T_PATH_CRYO:
            s = self.statuses.get("SLOW")
            if s:
                s.dur = max(0.0, s.dur) + 0.05

        # rune tiles: enemies feel a faint vulnerability (optional)
        if self.tile_v == T_PATH_RUNE:
            if rng and rng.random() < 0.10:
                self.add_status("VULN", 0.7, 1, 0.0)

        # sapper corruption
        if world and "SAPPER" in self.arch.tags:
            self._sapper_t += 1/60.0  # approximate; refined in update()
            # exact dt handled in update; keep for safety

    def update(self, dt: float, world=None, rng=None):
        if not self.alive or self.finished:
            return

        if rng is None and world is not None:
            rng = getattr(world, "rng", None)

        # status timers
        slow = 0.0
        stunned = 0.0
        shred = 0.0
        vuln = 0.0
        burn_dps = 0.0
        poison_dps = 0.0
        shock = False

        for k in list(self.statuses.keys()):
            s = self.statuses[k]
            s.dur -= dt
            if s.dur <= 0:
                del self.statuses[k]
                continue
            if k == "SLOW":
                # strength is the primary slow factor; stacking is capped to avoid immobilization
                cap = 0.40 if ("BOSS" in self.arch.tags) else 0.50
                slow = max(slow, min(cap, float(s.strength) + 0.04*max(0, s.stacks-1)))
            elif k == "STUN":
                stunned = max(stunned, 0.1)
            elif k == "SHRED":
                shred = max(shred, 0.8 * s.stacks)
            elif k == "VULN":
                vuln = max(vuln, 0.12 * s.stacks)
            elif k == "BURN":
                # toned-down burn: strong vs REGEN but not a solo win
                burn_dps += (1.2 + 0.9*s.stacks)
            elif k == "POISON":
                poison_dps += (0.9 + 0.7*s.stacks)
            elif k == "SHOCK":
                shock = True

        # derived defensive modifiers from statuses
        # SHRED reduces armor, VULN increases damage taken.
        self.armor_eff = max(0.0, float(getattr(self, "base_armor", self.armor)) - float(shred))
        self.vuln_mult = 1.0 + float(vuln)

        burn_active = burn_dps > 0.0

        # regen
        if self.arch.regen > 0 and self.hp < self.max_hp:
            self.hp = min(self.max_hp, self.hp + float(self.arch.regen) * dt * (0.4 if burn_active else 1.0))

        # apply DoTs
        if burn_dps > 0:
            self.take_damage(burn_dps*dt, "FIRE")
        if poison_dps > 0:
            self.take_damage(poison_dps*dt, "BIO")

        # boss phases signals
        if "BOSS" in self.arch.tags:
            frac = self.hp / max(1.0, self.max_hp)
            if self.boss_phase == 0 and frac < 0.66:
                self.boss_phase = 1
                self.spawn_signals.append("PHASE1")
            if self.boss_phase == 1 and frac < 0.33:
                self.boss_phase = 2
                self.spawn_signals.append("PHASE2")

        if stunned > 0:
            return

        # tile effects
        if world:
            self._apply_tile_effects(world, rng or getattr(world, "rng", None))

        # movement speed + terrain speed modifiers
        spd = self.base_speed * (1.0 - slow)
        if shock:
            spd *= 0.86

        if world:
            # terrain speed mul
            spd *= float(world.path_speed_mul(self.tile_v))

        # Momentum: long labyrinths shouldn't allow infinite stalling.
        # Enemies gain speed as they progress along the lane (capped; bosses gain less).
        cap = 0.25 if ("BOSS" in self.arch.tags) else 0.40
        spd *= (1.0 + min(cap, 0.004 * float(self.path_i)))

        # branch-capable movement (with robust fallback)
        use_branch = False
        target_cell = None

        if world:
            # If we somehow lost next_cell (cache/path edits/edge), try to recover.
            if self.next_cell is None:
                self.next_cell = world.next_cell(self.cell, self.prev_cell, rng or world.rng)
            target_cell = self.next_cell

        if world and target_cell is not None:
            tx, ty = self._pos(target_cell)
            use_branch = True
        else:
            # legacy fixed-path fallback (DO NOT use self.idx as list index; idx is a progress proxy)
            if self.path_i >= len(self.path) - 1:
                # if we're already at/after the end, finish
                self.finished = True
                return
            tx, ty = self._pos(self.path[self.path_i + 1])

        dx, dy = tx-self.x, ty-self.y
        dist = math.hypot(dx,dy) or 1.0
        step = spd * dt
        if dist <= step:
            self.x, self.y = tx, ty

            if use_branch and world and target_cell is not None:
                # advance along branching lane
                self.prev_cell = self.cell
                self.cell = target_cell

                dmap = world.get_distmap()
                self.idx = -int(dmap.get(self.cell, 9999))

                # reached the end?
                if self.cell == world.gs.end or dmap.get(self.cell, 9999) == 0:
                    self.finished = True
                    return

                self.next_cell = world.next_cell(self.cell, self.prev_cell, rng or world.rng)

            else:
                # advance along fixed path safely
                self.path_i = min(self.path_i + 1, len(self.path) - 1)
                self.prev_cell = self.cell
                self.cell = self.path[self.path_i]

                if world:
                    dmap = world.get_distmap()
                    self.idx = -int(dmap.get(self.cell, 9999))
                    if self.cell == world.gs.end or dmap.get(self.cell, 9999) == 0:
                        self.finished = True
                        return
                    # attempt to re-enter branching logic from here
                    self.next_cell = world.next_cell(self.cell, self.prev_cell, rng or world.rng)
                else:
                    if self.path_i >= len(self.path) - 1:
                        self.finished = True
                        return

            # sapper corruption tick (real dt), regardless of movement mode
            if world and "SAPPER" in self.arch.tags:
                self._sapper_t += dt
                if self._sapper_t >= 2.4:
                    self._sapper_t = 0.0
                    world.corrupt_near(self.cell, rng or world.rng)

        else:
            self.x += (dx/dist)*step
            self.y += (dy/dist)*step