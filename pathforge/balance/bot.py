from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any
import random

from ..settings import T_EMPTY, T_PATH
from ..data.talents_db import TALENTS

Coord = Tuple[int, int]

@dataclass
class BuildPlan:
    path: List[Coord]
    towers: List[Tuple[int, int, str]]

class AutoBot:
    """Heuristic bot used for balance simulation.

    Goals:
    - Build a long single-lane path within pavés budget
    - Respect unlocks (talents) for towers/paths
    - Place towers near dense path segments
    - Upgrade & pick A/B/C branches once available (lvl>=3)
    - Choose perks by scoring expected value
    - Optionally choose assault multi (risk for better loot)
    """

    def __init__(self, rng: random.Random):
        self.rng = rng
        self._comp_cycle: List[str] = []
        self._comp_cycle_wave: int = 0
        self._comp_i: int = 0

    # ---------------------------
    # Composition + killzone
    # ---------------------------
    def compute_killzone(self, path: List[Coord]) -> Coord:
        """Pick a 'killzone' along the path: a dense segment where towers can cover many tiles."""
        if not path:
            return (0, 0)
        best = path[len(path)//2]
        best_score = -1
        path_set = set(path)
        for (x, y) in path:
            # density within diamond radius 3
            d = 0
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    if abs(dx) + abs(dy) > 3:
                        continue
                    if (x + dx, y + dy) in path_set:
                        d += 1
            if d > best_score:
                best_score = d
                best = (x, y)
        return best

    def choose_composition(self, unlocked_sorted: List[str], wave: int) -> List[str]:
        """Choose a simple tower composition cycle.

        The goal isn't 'perfect play' but stable, repeatable builds for simulation:
        - early: cheap DPS + AOE
        - mid: add anti-shield / control if available
        - late: keep a mix
        """
        unlocked = set(unlocked_sorted)

        def pick(*opts: str) -> str | None:
            for o in opts:
                if o in unlocked:
                    return o
            return None

        core_dps = pick("GATLING", "SNIPER")
        aoe = pick("CANNON", "MORTAR")
        anti_shield = pick("TESLA")
        control = pick("CRYO", "BEACON")
        burn = pick("FLAME")

        cycle: List[str] = []
        if core_dps:
            cycle += [core_dps, core_dps]
        if aoe:
            cycle += [aoe]
        if wave >= 6 and anti_shield:
            cycle += [anti_shield]
        if wave >= 8 and control:
            cycle += [control]
        if wave >= 10 and burn:
            cycle += [burn]

        # fallback to cheapest towers if something went wrong
        if not cycle:
            cycle = unlocked_sorted[:2] or ["GATLING"]

        # small shuffle to avoid fixed identical placement order
        if wave % 2 == 0:
            self.rng.shuffle(cycle)
        return cycle

    # ---------------------------
    # Path building
    # ---------------------------
    def build_path_snake(self, cols: int, rows: int, start: Coord, end: Coord, max_len: int) -> List[Coord]:
        """Generate a non-branching path from start to end with many turns (snake).

        Note: we intentionally avoid revisits (no loops) to keep pathfinding trivial in sim.
        (Maze rebuild / loop strategies can come later.)
        """
        x0, y0 = start
        x1, y1 = end
        left = min(x0, x1)
        right = max(x0, x1)

        # Keep the snake in a corridor around start/end Y so we don't waste steps.
        top = max(1, min(y0, y1) - 3)
        bottom = min(rows - 2, max(y0, y1) + 3)

        path: List[Coord] = [start]
        x, y = start
        y = max(top, min(y, bottom))
        direction = 1  # 1 -> right, -1 -> left

        # Reserve some steps to connect to end cleanly.
        budget = max(0, max_len - 6)

        while len(path) < budget:
            target_x = right if direction == 1 else left
            while x != target_x and len(path) < budget:
                x += direction
                path.append((x, y))
            if len(path) >= budget:
                break
            if y < bottom:
                y += 1
                path.append((x, y))
                direction *= -1
            else:
                break

        # Connect to end via Manhattan.
        ex, ey = end
        while x != ex and len(path) < max_len - 1:
            x += 1 if ex > x else -1
            if (x, y) != path[-1]:
                path.append((x, y))
        while y != ey and len(path) < max_len - 1:
            y += 1 if ey > y else -1
            if (x, y) != path[-1]:
                path.append((x, y))
        if path[-1] != end:
            path.append(end)

        # Remove duplicates (enforce no revisit)
        seen = set()
        filtered: List[Coord] = []
        for c in path:
            if c in seen:
                continue
            seen.add(c)
            filtered.append(c)
        if filtered[0] != start:
            filtered.insert(0, start)
        if filtered[-1] != end:
            filtered.append(end)
        return filtered

    # ---------------------------
    # Talents (unlock towers/paths + build identity)
    # ---------------------------
    def _can_buy_node(self, stats, nid: str) -> bool:
        t = TALENTS.get(nid) or {}
        owned = getattr(stats, "talent_nodes", set()) or set()
        if nid in owned:
            return False
        for ex in (t.get("exclusive") or []):
            if ex in owned:
                return False
        for p in (t.get("prereq") or []):
            if p not in owned:
                return False
        return True

    def score_talent(self, stats, nid: str, wave: int) -> float:
        t = TALENTS.get(nid) or {}
        eff = (t.get("effect") or {})
        mods = (eff.get("mods") or {})
        grant = (eff.get("grant") or {})
        unlock_towers = (eff.get("unlock_towers") or [])
        unlock_paths = (eff.get("unlock_paths") or [])

        s = 0.0

        # Unlock new towers is huge value.
        unlocked = getattr(stats, "unlocked_towers", set()) or set()
        for tk in unlock_towers:
            if tk not in unlocked:
                s += 80.0

        # Unlocking path tiles matters later (rebuild not yet), keep moderate.
        if unlock_paths:
            s += 10.0 + 2.0 * len(unlock_paths)

        # Direct combat scaling
        if "dmg_mul" in mods: s += (float(mods["dmg_mul"]) - 1.0) * 40.0
        if "rate_mul" in mods: s += (float(mods["rate_mul"]) - 1.0) * 32.0
        if "range_mul" in mods: s += (float(mods["range_mul"]) - 1.0) * 18.0

        # tower bonuses / flags
        if "tower_bonus" in mods: s += 18.0
        if "global_on_hit" in mods: s += 14.0
        if any(str(k).startswith("flag_") for k in mods.keys()): s += 8.0

        # Utility / economy
        if "paves" in grant: s += float(grant["paves"]) * 0.20
        if "paves_cap" in grant: s += float(grant["paves_cap"]) * 0.10
        if "talent_pts" in grant: s += 120.0

        # Early game: prioritize unlocks
        if wave <= 6 and unlock_towers:
            s *= 1.2
        return s

    def choose_talent(self, stats, wave: int) -> str | None:
        if getattr(stats, "talent_pts", 0) <= 0:
            return None
        options = [nid for nid in TALENTS.keys() if self._can_buy_node(stats, nid)]
        if not options:
            return None
        scored = [(self.score_talent(stats, nid, wave), nid) for nid in options]
        scored.sort(reverse=True)
        return scored[0][1] if scored else None

    def spend_talents(self, stats, wave: int):
        while getattr(stats, "talent_pts", 0) > 0:
            nid = self.choose_talent(stats, wave)
            if not nid:
                break
            eff = (TALENTS.get(nid) or {}).get("effect") or {}
            stats.buy_node(nid, eff)

    # ---------------------------
    # Assault multiplier (risk/reward)
    # ---------------------------
    def choose_wave_multi(self, stats, wave: int, last_lives_lost: int = 0) -> int:
        lives = int(getattr(stats, "lives", 0))
        gold = int(getattr(stats, "gold", 0))
        if wave < 6:
            return 1
        if last_lives_lost > 0:
            return 1
        if lives >= 18 and gold >= 520 and wave >= 12:
            return 3
        if lives >= 16 and gold >= 320 and wave >= 8:
            return 2
        return 1

    # ---------------------------
    # Tower placement / upgrades
    # ---------------------------
    def place_towers(self, world, stats, wave: int = 1, max_towers: int = 12):
        path = world.get_path()
        if not path:
            return
        path_set = set(path)

        # refresh composition occasionally
        if self._comp_cycle_wave != int(wave) or not self._comp_cycle:
            unlocked = list(getattr(stats, "unlocked_towers", [])) or list(world.towers_db.keys())
            unlocked_sorted = sorted(unlocked, key=lambda k: int(world.towers_db.get(k, {}).get("cost", 999999)))
            self._comp_cycle = self.choose_composition(unlocked_sorted, int(wave))
            self._comp_cycle_wave = int(wave)
            self._comp_i = 0

        killzone = self.compute_killzone(path)

        unlocked = list(getattr(stats, "unlocked_towers", [])) or list(world.towers_db.keys())
        unlocked_sorted = sorted(unlocked, key=lambda k: int(world.towers_db.get(k, {}).get("cost", 999999)))

        # candidate score = coverage - distance to killzone
        candidates: List[Tuple[int,int,int,int]] = []  # (score,cov,gx,gy)
        for gx in range(world.gs.cols):
            for gy in range(world.gs.rows):
                if world.gs.grid[gx][gy] != T_EMPTY:
                    continue
                cov = 0
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        if abs(dx) + abs(dy) > 3:
                            continue
                        if (gx + dx, gy + dy) in path_set:
                            cov += 1
                if cov > 0:
                    dist_kz = abs(gx - killzone[0]) + abs(gy - killzone[1])
                    score = cov * 10 - dist_kz * 3
                    candidates.append((score, cov, gx, gy))
        candidates.sort(reverse=True)

        for score, cov, gx, gy in candidates:
            if len(world.towers) >= max_towers:
                break
            # pick tower key from composition cycle first
            key = None
            if self._comp_cycle:
                key = self._comp_cycle[self._comp_i % len(self._comp_cycle)]
                self._comp_i += 1

            # if not available, fall back to cheapest unlocked
            keys_to_try = [key] if key else []
            keys_to_try += unlocked_sorted

            for key in keys_to_try:
                if not key:
                    continue
                base_cost = int(world.towers_db.get(key, {}).get("cost", 999999))
                cost = int(base_cost * float(getattr(stats, "tower_cost_mul", 1.0)))
                if stats.gold >= cost:
                    t = world.add_tower(gx, gy, key)
                    if t:
                        stats.gold -= cost
                        break

    def choose_branch(self, tower, stats, wave: int) -> str:
        key = getattr(tower.defn, "key", "")
        is_boss = (wave % 10 == 0)
        if key == "GATLING":
            return "B" if wave >= 10 else "A"
        if key == "CANNON":
            return "A"
        if key == "MORTAR":
            return "A"
        if key == "SNIPER":
            return "B" if is_boss else "A"
        if key == "TESLA":
            return "B" if is_boss else "A"
        if key == "CRYO":
            return "C"
        if key == "FLAME":
            return "A"
        if key == "BEACON":
            return "C"
        return "A"

    def upgrade_towers(self, world, stats, wave: int = 1):
        # If any tower can branch, choose for free (lvl>=3)
        for t in list(world.towers):
            if getattr(t, "can_branch", lambda: False)():
                try:
                    t.apply_branch(self.choose_branch(t, stats, wave))
                except Exception:
                    pass

        # Upgrade best value tower (one upgrade per wave for stability)
        best = None
        best_score = -1e18
        path = world.get_path() or []
        for t in world.towers:
            try:
                cost = float(t.upgrade_cost())
            except Exception:
                continue
            if cost <= 0 or stats.gold < cost:
                continue
            px, py = int(t.gx), int(t.gy)
            mind = 99
            for c in path:
                d = abs(int(c[0]) - px) + abs(int(c[1]) - py)
                if d < mind:
                    mind = d
            score = (100 - mind * 10) - cost * 0.06
            if score > best_score:
                best_score = score
                best = t

        if best:
            c = int(best.upgrade_cost())
            if c > 0 and stats.gold >= c:
                stats.gold -= c
                best.upgrade()
                if getattr(best, "can_branch", lambda: False)():
                    try:
                        best.apply_branch(self.choose_branch(best, stats, wave))
                    except Exception:
                        pass

    # ---------------------------
    # Perks
    # ---------------------------
    def score_perk(self, perk: Dict[str, Any], wave: int) -> float:
        mods = perk.get("mods") or {}
        grant = perk.get("grant") or {}
        rarity = perk.get("rarity", "C")
        base = {"C": 1, "R": 1.2, "E": 1.5, "L": 2.0, "SS+": 3.0, "SS++": 4.0, "SSS": 6.0, "Ω": 10.0}.get(rarity, 1.0)

        s = 0.0
        pow_w = 0.8 + min(2.0, wave / 10.0)
        eco_w = 1.2 if wave < 8 else 0.8
        util_w = 0.9

        if "dmg_mul" in mods: s += pow_w * (float(mods["dmg_mul"]) - 1.0) * 10
        if "rate_mul" in mods: s += pow_w * (float(mods["rate_mul"]) - 1.0) * 9
        if "range_mul" in mods: s += util_w * (float(mods["range_mul"]) - 1.0) * 7

        dtm = mods.get("dmg_type_mul")
        if isinstance(dtm, dict):
            for _, mul in dtm.items():
                s += pow_w * (float(mul) - 1.0) * 6

        if "gold_per_kill" in mods: s += eco_w * float(mods["gold_per_kill"]) * 1.6
        if "perk_rerolls_add" in mods: s += eco_w * float(mods["perk_rerolls_add"]) * 2.0
        if "tower_bonus" in mods: s += pow_w * 4.0
        if "global_on_hit" in mods: s += util_w * 3.5

        # enemy debuffs are extremely valuable (your note matches this)
        if "enemy_hp_mul" in mods: s += pow_w * (1.0 - float(mods["enemy_hp_mul"])) * 20
        if "enemy_speed_mul" in mods: s += util_w * (1.0 - float(mods["enemy_speed_mul"])) * 14
        if "enemy_armor_add" in mods: s += pow_w * (-float(mods["enemy_armor_add"])) * 8

        if "paves" in grant: s += util_w * float(grant["paves"]) * 0.7
        if "paves_cap" in grant: s += util_w * float(grant["paves_cap"]) * 0.4
        if "talent_pts" in grant: s += 25.0  # very strong, rare

        return s * base

    def choose_perk(self, options: List[Dict[str, Any]], wave: int) -> int:
        best_i = 0
        best_s = -1e9
        for i, p in enumerate(options):
            sc = self.score_perk(p, wave)
            sc += self.rng.random() * 0.05
            if sc > best_s:
                best_s = sc
                best_i = i
        return best_i
