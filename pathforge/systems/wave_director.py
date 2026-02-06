from __future__ import annotations
from dataclasses import dataclass
from typing import List
import random

@dataclass
class WavePlan:
    wave: int
    boss: bool
    keywords: List[str]
    relics_in_path: int

class WaveDirector:
    def __init__(self, rng: random.Random):
        self.rng = rng

    def plan(self, wave: int, relics_in_path: int, ascension: int = 0) -> WavePlan:
        # deterministic keywords for UI
        seed = (wave*73856093) ^ (relics_in_path*19349663) ^ (ascension*83492791) ^ 0xA5A5A5
        lrng = random.Random(seed)
        # Theme rotation is *bounded* by wave to avoid early hard-counters (armor/shields)
        # appearing before the player has the tools to answer them.
        if wave <= 2:
            themes = [["Swarm","Fast"], ["Mixed","Tactical"]]
        elif wave <= 4:
            themes = [["Swarm","Fast"], ["Mixed","Tactical"], ["Regen","Mutant"]]
        elif wave <= 7:
            themes = [["Swarm","Fast"], ["Siege","Armored"], ["Regen","Mutant"], ["Mixed","Tactical"]]
        else:
            themes = [
                ["Swarm","Fast"], ["Siege","Armored"], ["Shields","Elite"],
                ["Regen","Mutant"], ["Mixed","Tactical"],
            ]
        keywords = lrng.choice(themes) + ([f"Relics+{relics_in_path}"] if relics_in_path else [])
        boss = (wave % 10 == 0)
        if boss:
            keywords = ["BOSS", "Apex", "Unstoppable"] + keywords[:1]
        return WavePlan(wave=wave, boss=boss, keywords=keywords, relics_in_path=relics_in_path)

    def spawn_list(self, plan: WavePlan) -> List[str]:
        w = plan.wave

        # Boss waves: boss + a themed escort (hard)
        if plan.boss:
            return ["BOSS","ELITE","TANK","WISP","SCOUT","MUTANT","PYRO","SCOUT"]

        # Progressive roster unlock by tier.
        # IMPORTANT: early waves must not include heavy-armor / shielded units,
        # otherwise every build collapses at wave 1–2 (GA gets stuck at ~1 wave).
        if w <= 2:
            avail = ["SOLDIER", "SCOUT"]
        elif w <= 4:
            avail = ["SOLDIER", "SCOUT", "MUTANT"]
        elif w <= 6:
            avail = ["SOLDIER", "SCOUT", "MUTANT", "PYRO"]
        elif w <= 9:
            avail = ["SOLDIER", "SCOUT", "MUTANT", "PYRO", "TANK"]
        elif w <= 12:
            avail = ["SOLDIER", "SCOUT", "MUTANT", "PYRO", "TANK", "WISP"]
        else:
            avail = ["SOLDIER", "SCOUT", "TANK", "MUTANT", "WISP", "PYRO", "ELITE"]

        # Theme bias based on keywords
        keys = set(plan.keywords or [])
        weights = {k: 1.0 for k in avail}

        if "Fast" in keys or "Swarm" in keys:
            for k in avail:
                if k in ("SCOUT","WISP","SOLDIER"):
                    weights[k] *= 1.45
        if ("Armored" in keys or "Siege" in keys) and w >= 6:
            for k in avail:
                if k in ("TANK","ELITE","PYRO"):
                    weights[k] *= 1.40
        if "Regen" in keys or "Mutant" in keys:
            if "MUTANT" in weights:
                weights["MUTANT"] *= 1.60
        if ("Shields" in keys or "Elite" in keys) and w >= 9:
            for k in avail:
                if k in ("ELITE","WISP"):
                    weights[k] *= 1.55

        # Create a "budget-ish" list: enemy count grows with wave.
        # Keep early waves smaller so the bot has time to stabilize.
        out: List[str] = []
        count = 9 + int(w * 1.7)
        pool = []
        for k, wt in weights.items():
            pool.extend([k] * max(1, int(round(wt*10))))
        for _ in range(count):
            out.append(self.rng.choice(pool))
        return out
