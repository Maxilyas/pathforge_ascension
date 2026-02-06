
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional
import random
import math

from ..settings import T_EMPTY, T_TOWER, T_PATH, PATH_TILES
from ..world.pathfinding import chain_path

Coord = Tuple[int,int]

@dataclass
class BuildPlan:
    path: List[Coord]
    towers: List[Tuple[int,int,str]]
    # simple placement intent

class AutoBot:
    """Heuristic bot:
    - Build a long snake-like single lane using available paves
    - Spend gold on towers near dense path segments
    - Upgrade cheapest high-coverage towers
    - Choose perks by scoring their expected value
    """

    def __init__(self, rng: random.Random):
        self.rng = rng

    def build_path_snake(self, cols:int, rows:int, start:Coord, end:Coord, max_len:int) -> List[Coord]:
        """Generate a non-branching path from start to end with many turns (snake)."""
        # Create a rectangular corridor between start and end
        x0, y0 = start
        x1, y1 = end
        left = min(x0, x1)
        right = max(x0, x1)
        top = 1
        bot = rows-2

        # We'll snake across the rectangle from left to right, then down, then right to left, etc,
        # ensuring we end near the end coord.
        path: List[Coord] = [start]
        x, y = start
        direction = 1  # 1 -> right, -1 -> left
        # reserve some steps to connect to end cleanly
        budget = max(0, max_len - 6)

        while len(path) < budget:
            target_x = right if direction == 1 else left
            while x != target_x and len(path) < budget:
                x += direction
                path.append((x, y))
            if len(path) >= budget:
                break
            # move down if possible
            if y < bot:
                y += 1
                path.append((x, y))
                direction *= -1
            else:
                break

        # Connect to end via Manhattan path, without creating branches:
        ex, ey = end
        # Horizontal towards ex
        while x != ex and len(path) < max_len-1:
            x += 1 if ex > x else -1
            if (x,y) != path[-1]:
                path.append((x,y))
        # Vertical towards ey
        while y != ey and len(path) < max_len-1:
            y += 1 if ey > y else -1
            if (x,y) != path[-1]:
                path.append((x,y))
        # Ensure last is end
        if path[-1] != end:
            path.append(end)

        # Remove duplicates while preserving a valid chain
        # (snake can revisit; chain_path would reject revisits that form loops).
        # We'll enforce simple: no revisit.
        seen=set()
        filtered=[]
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

    def place_towers(self, world, stats, max_towers:int=12):
        """Place towers greedily near the path based on coverage."""
        # candidate tiles: empty, near any path tile (manhattan <=2)
        path = world.get_path()
        if not path:
            return
        path_set=set(path)

        unlocked = list(getattr(stats, "unlocked_towers", [])) or list(world.towers_db.keys())
        # prefer cheaper core towers early
        unlocked_sorted = sorted(unlocked, key=lambda k: int(world.towers_db.get(k,{}).get("cost", 9999)))

        candidates=[]
        for gx in range(world.gs.cols):
            for gy in range(world.gs.rows):
                if world.gs.grid[gx][gy] != T_EMPTY:
                    continue
                # coverage score by count of path cells within 2
                cov=0
                for dx in range(-2,3):
                    for dy in range(-2,3):
                        if abs(dx)+abs(dy) > 3:
                            continue
                        if (gx+dx, gy+dy) in path_set:
                            cov+=1
                if cov>0:
                    candidates.append((cov, gx, gy))
        candidates.sort(reverse=True)

        # place while gold
        for cov,gx,gy in candidates:
            if len(world.towers) >= max_towers:
                break
            # pick best affordable tower for this spot
            for key in unlocked_sorted:
                cost = int(world.towers_db.get(key,{}).get("cost",999999))
                cost = int(cost * float(getattr(stats, "tower_cost_mul", 1.0)))
                if stats.gold >= cost:
                    t = world.add_tower(gx, gy, key)
                    if t:
                        stats.gold -= cost
                        break

    def upgrade_towers(self, world, stats):
        # upgrade the cheapest (by upgrade cost) tower that has good coverage
        best=None
        best_score=-1
        for t in world.towers:
            cost = t.upgrade_cost()
            if cost <= 0 or stats.gold < cost:
                continue
            # score: low cost and close to path
            px, py = t.gx, t.gy
            path = world.get_path() or []
            mind = 99
            for c in path:
                d = abs(c[0]-px)+abs(c[1]-py)
                if d < mind: mind = d
            score = 100 - mind*10 - cost*0.05
            if score > best_score:
                best_score = score
                best = t
        if best:
            stats.gold -= best.upgrade_cost()
            best.upgrade()

    def score_perk(self, perk: Dict[str,Any], wave:int) -> float:
        mods = perk.get("mods") or {}
        grant = perk.get("grant") or {}
        rarity = perk.get("rarity","C")
        base = {"C":1,"R":1.2,"E":1.5,"L":2.0,"SS+":3.0,"SS++":4.0,"SSS":6.0,"Ω":10.0}.get(rarity,1.0)
        s = 0.0
        # power scales with wave
        pow_w = 0.8 + min(2.0, wave/10.0)
        eco_w = 1.2 if wave < 8 else 0.8
        util_w = 0.9

        if "dmg_mul" in mods: s += pow_w * (float(mods["dmg_mul"]) - 1.0) * 10
        if "rate_mul" in mods: s += pow_w * (float(mods["rate_mul"]) - 1.0) * 9
        if "range_mul" in mods: s += util_w * (float(mods["range_mul"]) - 1.0) * 7
        dtm = mods.get("dmg_type_mul")
        if isinstance(dtm, dict):
            # value specialization slightly less than global
            for _,mul in dtm.items():
                s += pow_w * (float(mul)-1.0) * 6
        if "gold_per_kill" in mods: s += eco_w * float(mods["gold_per_kill"]) * 1.6
        if "perk_rerolls_add" in mods: s += eco_w * float(mods["perk_rerolls_add"]) * 2.0
        if "tower_bonus" in mods: s += pow_w * 4.0
        if "global_on_hit" in mods: s += util_w * 3.5

        if "paves" in grant: s += util_w * float(grant["paves"]) * 0.7
        if "paves_cap" in grant: s += util_w * float(grant["paves_cap"]) * 0.4
        if "talent_pts" in grant: s += 25.0  # very strong

        return s * base

    def choose_perk(self, options: List[Dict[str,Any]], wave:int) -> int:
        best_i=0
        best_s=-1e9
        for i,p in enumerate(options):
            sc=self.score_perk(p, wave)
            # tiny noise to avoid deterministic loops
            sc += self.rng.random()*0.05
            if sc > best_s:
                best_s=sc
                best_i=i
        return best_i
