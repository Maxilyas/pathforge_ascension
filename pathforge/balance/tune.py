
from __future__ import annotations
import json, os, random
from dataclasses import asdict
from typing import Dict, Any

from .sim import run_episode
from ..core.balance_profile import PROFILE_FILE

def tune(game, target: str = "humain_solide", episodes: int = 6, seed: int = 123) -> Dict[str,Any]:
    """Simple parameter search to reach a target survival curve.

    Targets:
      - humain_solide: bot clears ~10-14 waves on average with few perks
    Writes saves/balance_profile.json for the main game.
    """
    rng = random.Random(seed)

    # desired mean cleared waves
    target_wave = 12 if target == "humain_solide" else 8

    # search space
    tower_dmg_opts = [0.85, 0.90, 0.95, 1.00, 1.05]
    enemy_hp_opts = [1.00, 1.10, 1.25, 1.40, 1.60]
    enemy_armor_opts = [0, 2, 4, 6]

    best = None
    best_score = 1e9

    for td in tower_dmg_opts:
        for eh in enemy_hp_opts:
            for aa in enemy_armor_opts:
                profile = {
                    "tower": {"damage_mul": td, "rate_mul": 1.0, "range_mul": 1.0, "cost_mul": 1.0},
                    "enemy": {"hp_mul": eh, "armor_add": aa, "speed_mul": 1.0, "regen_mul": 1.0, "shield_mul": 1.0},
                }
                # apply profile temporarily
                # create copies of dbs
                towers_db = json.loads(json.dumps(game.towers_db))
                enemies_db = json.loads(json.dumps(game.enemies_db))

                from ..core.balance_profile import apply_profile
                apply_profile(towers_db, enemies_db, profile)

                def roll_fn(n, rarity_bias=0.0):
                    return game.perk_pool.roll(game._perk_rng, n=n, rarity_bias=rarity_bias)

                waves=[]
                for _ in range(episodes):
                    s = rng.randint(0, 1_000_000)
                    res = run_episode(towers_db, enemies_db, roll_fn, seed=s, max_waves=25)
                    waves.append(res.waves_cleared)

                mean = sum(waves)/len(waves)
                # score distance to target, with slight penalty for too-easy (mean>target)
                score = abs(mean - target_wave) + (0.4*max(0.0, mean - target_wave))
                if score < best_score:
                    best_score = score
                    best = (profile, mean, waves)

    assert best is not None
    profile, mean, waves = best
    profile["meta"] = {"target": target, "episodes": episodes, "mean_waves": mean, "samples": waves}

    os.makedirs(os.path.dirname(PROFILE_FILE), exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    return profile

def main():
    # Import Game in a lightweight way (dummy driver)
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from ..game import Game
    g = Game()
    # tuning uses g.perk_pool etc
    profile = tune(g, target="humain_solide", episodes=5, seed=123)
    print("Wrote", PROFILE_FILE)
    print(json.dumps(profile.get("meta",{}), indent=2))

if __name__ == "__main__":
    main()
