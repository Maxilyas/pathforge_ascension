
from __future__ import annotations
import json, os, random
from dataclasses import asdict
from typing import Dict, Any

from .sim import run_episode
from ..core.balance_profile import PROFILE_FILE

def tune(game, target: str = "humain_solide", episodes: int = 6, seed: int = 123) -> Dict[str,Any]:
    """Simple parameter search to reach a target survival curve.

    Note: This can be slow. By default we sample a subset of the full grid.
    - Set PATHFORGE_BALANCE_EXHAUSTIVE=1 to test the entire grid.
    - Set PATHFORGE_BALANCE_LOG=2 for more verbose logs.
    """
    rng = random.Random(seed)
    log_level = int(os.environ.get("PATHFORGE_BALANCE_LOG", "1"))
    exhaustive = str(os.environ.get("PATHFORGE_BALANCE_EXHAUSTIVE", "0")).strip().lower() in ("1","true","yes","on")
    sample_n = int(os.environ.get("PATHFORGE_BALANCE_SAMPLES", "28"))
    max_waves = int(os.environ.get("PATHFORGE_BALANCE_MAX_WAVES", "25"))

    # desired mean cleared waves
    target_wave = 12 if target == "humain_solide" else 8

    # search space (grid)
    tower_dmg_opts = [0.85, 0.90, 0.95, 1.00, 1.05]
    enemy_hp_opts = [1.00, 1.10, 1.25, 1.40, 1.60]
    enemy_armor_opts = [0, 2, 4, 6]

    combos = [(td, eh, aa) for td in tower_dmg_opts for eh in enemy_hp_opts for aa in enemy_armor_opts]
    if not exhaustive:
        # deterministic sampling
        rng.shuffle(combos)
        combos = combos[:min(sample_n, len(combos))]

    if log_level:
        mode = "EXHAUSTIVE" if exhaustive else f"SAMPLED({len(combos)})"
        print(f"[BAL] tune target={target} target_mean≈{target_wave} episodes={episodes} max_waves={max_waves} mode={mode}")

    best = None
    best_score = 1e9

    def score_mean(mean: float) -> float:
        return abs(mean - target_wave) + (0.4*max(0.0, mean - target_wave))

    def min_possible_score(sum_waves: float, done: int) -> float:
        # remaining episodes can range [0, max_waves]
        left = max(0, episodes - done)
        lo = (sum_waves + 0.0*left) / episodes
        hi = (sum_waves + float(max_waves)*left) / episodes
        # best score over [lo, hi] occurs near target_wave or at boundaries
        cand = [lo, hi, float(target_wave)]
        cand = [x for x in cand if lo <= x <= hi] + [lo, hi]
        return min(score_mean(x) for x in cand)

    for i, (td, eh, aa) in enumerate(combos, start=1):
        t0 = __import__("time").time()
        if log_level:
            print(f"[BAL] [{i:03d}/{len(combos):03d}] td={td:.2f} eh={eh:.2f} aa={aa} ...", flush=True)

        profile = {
            "tower": {"damage_mul": td, "rate_mul": 1.0, "range_mul": 1.0, "cost_mul": 1.0},
            "enemy": {"hp_mul": eh, "armor_add": aa, "speed_mul": 1.0, "regen_mul": 1.0, "shield_mul": 1.0},
        }

        # create copies of dbs
        towers_db = json.loads(json.dumps(game.towers_db))
        enemies_db = json.loads(json.dumps(game.enemies_db))
        from ..core.balance_profile import apply_profile
        apply_profile(towers_db, enemies_db, profile)

        def roll_fn(n, rarity_bias=0.0):
            return game.perk_pool.roll(game._perk_rng, n=n, rarity_bias=rarity_bias)

        waves = []
        sumw = 0.0
        for ep in range(episodes):
            s = rng.randint(0, 1_000_000)
            res = run_episode(towers_db, enemies_db, roll_fn, seed=s, max_waves=max_waves)
            waves.append(res.waves_cleared)
            sumw += float(res.waves_cleared)

            if log_level >= 2:
                print(f"      ep {ep+1}/{episodes}: waves={res.waves_cleared} gold={res.gold_end} lives={res.lives_end}")

            # early pruning: even best possible remaining outcome can't beat current best
            if best is not None and min_possible_score(sumw, ep+1) > best_score:
                if log_level >= 2:
                    print(f"      early-stop: can't beat best_score={best_score:.3f}")
                break

        mean = sum(waves)/len(waves) if waves else 0.0
        sc = score_mean(mean)
        dt_s = __import__("time").time() - t0

        if log_level:
            print(f"      -> mean={mean:.2f} score={sc:.3f} (ran {len(waves)}/{episodes} eps in {dt_s:.2f}s)")

        if sc < best_score:
            best_score = sc
            best = (profile, mean, waves)
            if log_level:
                print(f"[BAL] NEW BEST score={best_score:.3f} mean={mean:.2f} td={td:.2f} eh={eh:.2f} aa={aa}", flush=True)

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
