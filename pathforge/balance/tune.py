
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
    # keep sim logs aligned with the tuner verbosity
    os.environ.setdefault("PATHFORGE_BALANCE_TRACE", str(log_level))
    exhaustive = str(os.environ.get("PATHFORGE_BALANCE_EXHAUSTIVE", "0")).strip().lower() in ("1","true","yes","on")
    sample_n = int(os.environ.get("PATHFORGE_BALANCE_SAMPLES", "28"))
    max_waves = int(os.environ.get("PATHFORGE_BALANCE_MAX_WAVES", "25"))

    # desired mean cleared waves
    target_wave = 20 if target == "humain_solide" else 12

    # search space
    # We explore a wider space than the initial coarse grid so the tuner can both ease or harden the game.
    # When not exhaustive, we sample continuously (faster, more diverse).
    if exhaustive:
        tower_dmg_opts = [0.70, 0.80, 0.90, 1.00, 1.10, 1.20]
        tower_rate_opts = [0.80, 0.90, 1.00, 1.10, 1.20]
        tower_cost_opts = [0.90, 1.00, 1.10]
        enemy_hp_opts = [0.50, 0.70, 0.85, 1.00, 1.20, 1.40, 1.70]
        enemy_armor_opts = [-4, -2, 0, 2, 4, 6, 8]
        enemy_speed_opts = [0.85, 0.95, 1.00, 1.10, 1.20]
        enemy_regen_opts = [0.50, 0.80, 1.00, 1.20]
        enemy_shield_opts = [0.70, 1.00, 1.30]
        combos = [
            (td, tr, tc, eh, aa, es, er, sh)
            for td in tower_dmg_opts
            for tr in tower_rate_opts
            for tc in tower_cost_opts
            for eh in enemy_hp_opts
            for aa in enemy_armor_opts
            for es in enemy_speed_opts
            for er in enemy_regen_opts
            for sh in enemy_shield_opts
        ]
    else:
        combos = []
        for _ in range(max(1, sample_n)):
            td = rng.uniform(0.70, 1.30)
            tr = rng.uniform(0.80, 1.25)
            tc = rng.uniform(0.90, 1.15)
            eh = rng.uniform(0.50, 1.80)
            aa = rng.randint(-6, 10)
            es = rng.uniform(0.85, 1.25)
            er = rng.uniform(0.50, 1.30)
            sh = rng.uniform(0.70, 1.40)
            combos.append((td, tr, tc, eh, aa, es, er, sh))
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

    for i, (td, tr, tc, eh, aa, es, er, sh) in enumerate(combos, start=1):
        t0 = __import__("time").time()
        if log_level:
            print(f"[BAL] [{i:03d}/{len(combos):03d}] td={td:.2f} tr={tr:.2f} tc={tc:.2f} eh={eh:.2f} aa={aa} es={es:.2f} er={er:.2f} sh={sh:.2f} ...", flush=True)

        profile = {
            "tower": {"damage_mul": td, "rate_mul": tr, "range_mul": 1.0, "cost_mul": tc},
            "enemy": {"hp_mul": eh, "armor_add": aa, "speed_mul": es, "regen_mul": er, "shield_mul": sh},
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
                print(f"[BAL] NEW BEST score={best_score:.3f} mean={mean:.2f} td={td:.2f} tr={tr:.2f} tc={tc:.2f} eh={eh:.2f} aa={aa} es={es:.2f} er={er:.2f} sh={sh:.2f}", flush=True)

    assert best is not None
    profile, mean, waves = best
    profile["meta"] = {"target": target, "episodes": episodes, "mean_waves": mean, "samples": waves}

    os.makedirs(os.path.dirname(PROFILE_FILE), exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)
    # write a human-readable summary alongside the json
    try:
        md_path = PROFILE_FILE.replace(".json", ".md")
        lines = []
        lines.append("# Pathforge Balance Profile\n")
        lines.append(f"- Target: **{target}** (target_mean≈{target_wave})\n")
        lines.append(f"- Episodes: **{episodes}**\n")
        lines.append(f"- Max waves: **{max_waves}**\n")
        lines.append(f"- Result mean waves: **{mean:.2f}**\n")
        lines.append(f"- Samples: `{waves}`\n")
        lines.append("\n## Multipliers\n")
        lines.append("### Towers\n")
        lines.append(f"- damage_mul: `{profile['tower'].get('damage_mul')}`\n")
        lines.append(f"- rate_mul: `{profile['tower'].get('rate_mul')}`\n")
        lines.append(f"- range_mul: `{profile['tower'].get('range_mul')}`\n")
        lines.append(f"- cost_mul: `{profile['tower'].get('cost_mul')}`\n")
        lines.append("\n### Enemies\n")
        lines.append(f"- hp_mul: `{profile['enemy'].get('hp_mul')}`\n")
        lines.append(f"- armor_add: `{profile['enemy'].get('armor_add')}`\n")
        lines.append(f"- speed_mul: `{profile['enemy'].get('speed_mul')}`\n")
        lines.append(f"- regen_mul: `{profile['enemy'].get('regen_mul')}`\n")
        lines.append(f"- shield_mul: `{profile['enemy'].get('shield_mul')}`\n")
        with open(md_path, "w", encoding="utf-8") as mf:
            mf.write("".join(lines))
        if log_level:
            print(f"[BAL] wrote summary {md_path}", flush=True)
    except Exception:
        pass


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
