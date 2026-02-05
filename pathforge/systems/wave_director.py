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
        themes = [
            ["Swarm","Fast"], ["Siege","Armored"], ["Shields","Elite"], ["Regen","Mutant"], ["Mixed","Tactical"]
        ]
        keywords = lrng.choice(themes) + ([f"Relics+{relics_in_path}"] if relics_in_path else [])
        boss = (wave % 10 == 0)
        if boss:
            keywords = ["BOSS", "Apex", "Unstoppable"] + keywords[:1]
        return WavePlan(wave=wave, boss=boss, keywords=keywords, relics_in_path=relics_in_path)

    def spawn_list(self, plan: WavePlan) -> List[str]:
        w = plan.wave
        if plan.boss:
            # boss + support
            return ["BOSS","ELITE","TANK","SCOUT","MUTANT","SCOUT"]
        # progressive roster
        max_tier = min(4, w//3)
        base = ["SOLDIER","SCOUT","TANK","MUTANT","ELITE"]
        avail = base[:max(2, max_tier+2)]
        # budget-ish list
        out = []
        count = 10 + w*2
        for _ in range(count):
            out.append(self.rng.choice(avail))
        return out
