
from __future__ import annotations
import json, os, random, math, statistics
from dataclasses import asdict, dataclass
from typing import Dict, Any, Tuple

from .sim import run_episode
from ..core.balance_profile import PROFILE_FILE


# ------------------------------
# Genetic algorithm tuner (v4.7.0)
# ------------------------------


@dataclass(frozen=True)
class Genome:
    td: float
    tr: float
    tc: float
    eh: float
    aa: int
    es: float
    er: float
    sh: float

    def as_tuple(self) -> Tuple[float, float, float, float, int, float, float, float]:
        return (self.td, self.tr, self.tc, self.eh, self.aa, self.es, self.er, self.sh)


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else (hi if x > hi else x)


def _rand_genome(rng: random.Random) -> Genome:
    return Genome(
        td=rng.uniform(0.70, 1.30),
        tr=rng.uniform(0.80, 1.25),
        tc=rng.uniform(0.90, 1.15),
        eh=rng.uniform(0.50, 1.80),
        aa=rng.randint(-6, 10),
        es=rng.uniform(0.85, 1.25),
        er=rng.uniform(0.50, 1.30),
        sh=rng.uniform(0.70, 1.40),
    )


def _mutate(g: Genome, rng: random.Random, p_big_jump: float = 0.12) -> Genome:
    """Mutation with occasional "big jumps" to escape local minima."""

    def gauss(x: float, s: float, lo: float, hi: float) -> float:
        return _clamp(x + rng.gauss(0.0, s), lo, hi)

    # occasional reset on one parameter
    if rng.random() < p_big_jump:
        which = rng.choice(["td","tr","tc","eh","aa","es","er","sh"])
        if which == "td": return Genome(**{**g.__dict__, "td": rng.uniform(0.70, 1.30)})
        if which == "tr": return Genome(**{**g.__dict__, "tr": rng.uniform(0.80, 1.25)})
        if which == "tc": return Genome(**{**g.__dict__, "tc": rng.uniform(0.90, 1.15)})
        if which == "eh": return Genome(**{**g.__dict__, "eh": rng.uniform(0.50, 1.80)})
        if which == "aa": return Genome(**{**g.__dict__, "aa": rng.randint(-6, 10)})
        if which == "es": return Genome(**{**g.__dict__, "es": rng.uniform(0.85, 1.25)})
        if which == "er": return Genome(**{**g.__dict__, "er": rng.uniform(0.50, 1.30)})
        if which == "sh": return Genome(**{**g.__dict__, "sh": rng.uniform(0.70, 1.40)})

    # small/medium gaussian drift
    return Genome(
        td=gauss(g.td, 0.06, 0.70, 1.30),
        tr=gauss(g.tr, 0.05, 0.80, 1.25),
        tc=gauss(g.tc, 0.03, 0.90, 1.15),
        eh=gauss(g.eh, 0.10, 0.50, 1.80),
        aa=int(_clamp(g.aa + rng.choice([-2, -1, 0, 0, 1, 2]), -6, 10)),
        es=gauss(g.es, 0.05, 0.85, 1.25),
        er=gauss(g.er, 0.07, 0.50, 1.30),
        sh=gauss(g.sh, 0.07, 0.70, 1.40),
    )


def _crossover(a: Genome, b: Genome, rng: random.Random) -> Genome:
    """Uniform crossover."""
    def pick(x, y):
        return x if rng.random() < 0.5 else y
    return Genome(
        td=pick(a.td, b.td),
        tr=pick(a.tr, b.tr),
        tc=pick(a.tc, b.tc),
        eh=pick(a.eh, b.eh),
        aa=int(pick(a.aa, b.aa)),
        es=pick(a.es, b.es),
        er=pick(a.er, b.er),
        sh=pick(a.sh, b.sh),
    )


def _to_profile(g: Genome) -> Dict[str, Any]:
    return {
        "tower": {"damage_mul": float(g.td), "rate_mul": float(g.tr), "range_mul": 1.0, "cost_mul": float(g.tc)},
        "enemy": {"hp_mul": float(g.eh), "armor_add": int(g.aa), "speed_mul": float(g.es), "regen_mul": float(g.er), "shield_mul": float(g.sh)},
    }


def _score_mean(mean: float, target_wave: float) -> float:
    # symmetric error, slight extra penalty if too hard (mean above target)
    return abs(mean - target_wave) + (0.4 * max(0.0, mean - target_wave))


def tune_ga(game, target: str = "humain_solide", episodes: int = 6, seed: int = 123) -> Dict[str, Any]:
    """Genetic algorithm tuner.

    Focus: wide search, occasional big jumps, mild stability penalty.
    """
    rng = random.Random(seed)
    log_level = int(os.environ.get("PATHFORGE_BALANCE_LOG", "1"))
    os.environ.setdefault("PATHFORGE_BALANCE_TRACE", str(log_level))
    max_waves = int(os.environ.get("PATHFORGE_BALANCE_MAX_WAVES", "25"))

    target_wave = 20 if target == "humain_solide" else 12

    pop_n = int(os.environ.get("PATHFORGE_BALANCE_GA_POP", "26"))
    gens = int(os.environ.get("PATHFORGE_BALANCE_GA_GENS", "18"))
    elitism = int(os.environ.get("PATHFORGE_BALANCE_GA_ELITE", "4"))
    reseed_frac = float(os.environ.get("PATHFORGE_BALANCE_GA_RESEED", "0.12"))

    # Deterministic episode seeds shared by all candidates (reduces noise)
    eval_seeds = [rng.randint(0, 1_000_000) for _ in range(max(2, episodes))]

    cache: Dict[Tuple[float, float, float, float, int, float, float, float], Tuple[float, float, list[int]]] = {}

    def evaluate(genome: Genome) -> Tuple[float, float, list[int]]:
        key = genome.as_tuple()
        if key in cache:
            return cache[key]

        profile = _to_profile(genome)
        towers_db = json.loads(json.dumps(game.towers_db))
        enemies_db = json.loads(json.dumps(game.enemies_db))
        from ..core.balance_profile import apply_profile
        apply_profile(towers_db, enemies_db, profile)

        def roll_fn(n, rarity_bias=0.0):
            return game.perk_pool.roll(game._perk_rng, n=n, rarity_bias=rarity_bias)

        waves: list[int] = []
        for s in eval_seeds[:episodes]:
            res = run_episode(towers_db, enemies_db, roll_fn, seed=int(s), max_waves=max_waves)
            waves.append(int(res.waves_cleared))

        mean = float(sum(waves) / max(1, len(waves)))
        std = float(statistics.pstdev(waves)) if len(waves) >= 2 else 0.0
        cache[key] = (mean, std, waves)
        return mean, std, waves

    def fitness(genome: Genome) -> Tuple[float, float, float, list[int]]:
        mean, std, waves = evaluate(genome)
        sc = _score_mean(mean, target_wave)
        # stability: discourage extreme variance that makes tuning unreliable
        sc2 = sc + 0.12 * std
        return sc2, mean, std, waves

    # Init population
    pop: list[Genome] = [_rand_genome(rng) for _ in range(pop_n)]

    best_g = None
    best_score = 1e18
    best_meta = None

    for gen in range(1, gens + 1):
        scored = []
        for g in pop:
            sc, mean, std, waves = fitness(g)
            scored.append((sc, mean, std, waves, g))
        scored.sort(key=lambda x: x[0])

        if scored and scored[0][0] < best_score:
            best_score = scored[0][0]
            best_g = scored[0][4]
            best_meta = {"mean": scored[0][1], "std": scored[0][2], "waves": scored[0][3], "gen": gen}
            if log_level:
                print(f"[BAL][GA] NEW BEST gen={gen} score={best_score:.3f} mean={best_meta['mean']:.2f} std={best_meta['std']:.2f} {best_g}", flush=True)

        if log_level:
            top = scored[:min(3, len(scored))]
            tmsg = " | ".join([f"{i+1}:{t[0]:.2f} m={t[1]:.1f} sd={t[2]:.1f}" for i, t in enumerate(top)])
            print(f"[BAL][GA] gen {gen:02d}/{gens:02d} best={best_score:.3f} :: {tmsg}", flush=True)

        # Selection (tournament)
        def tournament(k: int = 4) -> Genome:
            cand = [scored[rng.randrange(0, len(scored))] for _ in range(k)]
            cand.sort(key=lambda x: x[0])
            return cand[0][4]

        next_pop: list[Genome] = []
        # Elitism
        for _, _, _, _, g in scored[:max(1, elitism)]:
            next_pop.append(g)

        # Breed
        while len(next_pop) < pop_n:
            if rng.random() < reseed_frac:
                next_pop.append(_rand_genome(rng))
                continue
            a = tournament()
            b = tournament()
            child = _crossover(a, b, rng)
            if rng.random() < 0.90:
                child = _mutate(child, rng)
            next_pop.append(child)
        pop = next_pop

    assert best_g is not None
    profile = _to_profile(best_g)
    # attach metadata
    mean, std, waves = evaluate(best_g)
    profile["meta"] = {
        "algo": "GA",
        "target": target,
        "episodes": episodes,
        "max_waves": max_waves,
        "mean_waves": mean,
        "std_waves": std,
        "samples": waves,
        "best_score": best_score,
        "gen": (best_meta or {}).get("gen"),
    }

    os.makedirs(os.path.dirname(PROFILE_FILE), exist_ok=True)
    with open(PROFILE_FILE, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2)

    # richer markdown report
    try:
        md_path = PROFILE_FILE.replace(".json", ".md")
        from ..core.difficulty import CFG

        lines = []
        lines.append("# Pathforge Balance Profile\n\n")
        lines.append(f"- Algo: **GA**\n")
        lines.append(f"- Target: **{target}** (target_mean≈{target_wave})\n")
        lines.append(f"- Episodes: **{episodes}** (fixed seeds)\n")
        lines.append(f"- Max waves: **{max_waves}**\n")
        lines.append(f"- Result mean waves: **{mean:.2f}** (std={std:.2f})\n")
        lines.append(f"- Samples: `{waves}`\n")
        if waves:
            lines.append(f"- min/median/max: **{min(waves)} / {statistics.median(waves)} / {max(waves)}**\n")
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
        lines.append("\n## Difficulty Curves (baseline v4.7.0)\n")
        lines.append(f"- hp_slope_pre10: `{CFG.hp_slope_pre10}` | hp_slope_post10: `{CFG.hp_slope_post10}`\n")
        lines.append(f"- shield_base_factor: `{CFG.shield_base_factor}` | shield_slope_pre10: `{CFG.shield_slope_pre10}` | shield_slope_post10: `{CFG.shield_slope_post10}`\n")
        lines.append(f"- armor_mul_w1_5: `{CFG.armor_mul_w1_5}` | elite_shield_mul_w1_5: `{CFG.elite_shield_mul_w1_5}`\n")
        lines.append(f"- shield caps (pct HP): default `{CFG.shield_cap_pct_default}`, elite `{CFG.shield_cap_pct_elite}`, boss `{CFG.shield_cap_pct_boss}`\n")

        with open(md_path, "w", encoding="utf-8") as mf:
            mf.write("".join(lines))
        if log_level:
            print(f"[BAL] wrote summary {md_path}", flush=True)
    except Exception:
        pass

    return profile

def tune(game, target: str = "humain_solide", episodes: int = 6, seed: int = 123) -> Dict[str,Any]:
    """Simple parameter search to reach a target survival curve.

    Note: This can be slow. By default we sample a subset of the full grid.
    - Set PATHFORGE_BALANCE_EXHAUSTIVE=1 to test the entire grid.
    - Set PATHFORGE_BALANCE_LOG=2 for more verbose logs.
    """
    # Default algorithm for v4.7.0 is GA (wider exploration, escapes local minima).
    algo = str(os.environ.get("PATHFORGE_BALANCE_ALGO", "GA")).strip().upper()
    # If user explicitly requests GA, use it unless exhaustive grid is requested.
    if algo in ("GA", "GENETIC", "GENETIC_ALGO") and str(os.environ.get("PATHFORGE_BALANCE_EXHAUSTIVE", "0")).strip().lower() not in ("1","true","yes","on"):
        return tune_ga(game, target=target, episodes=episodes, seed=seed)

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
        from ..core.difficulty import CFG
        lines = []
        lines.append("# Pathforge Balance Profile\n\n")
        lines.append(f"- Algo: **RANDOM_SEARCH**\n")
        lines.append(f"- Target: **{target}** (target_mean≈{target_wave})\n")
        lines.append(f"- Episodes: **{episodes}**\n")
        lines.append(f"- Max waves: **{max_waves}**\n")
        lines.append(f"- Result mean waves: **{mean:.2f}**\n")
        lines.append(f"- Samples: `{waves}`\n")
        if waves:
            try:
                std = statistics.pstdev(waves) if len(waves) >= 2 else 0.0
                lines.append(f"- std/min/median/max: **{std:.2f} / {min(waves)} / {statistics.median(waves)} / {max(waves)}**\n")
            except Exception:
                pass
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
        lines.append("\n## Difficulty Curves (baseline v4.7.0)\n")
        lines.append(f"- hp_slope_pre10: `{CFG.hp_slope_pre10}` | hp_slope_post10: `{CFG.hp_slope_post10}`\n")
        lines.append(f"- shield_base_factor: `{CFG.shield_base_factor}` | shield_slope_pre10: `{CFG.shield_slope_pre10}` | shield_slope_post10: `{CFG.shield_slope_post10}`\n")
        lines.append(f"- armor_mul_w1_5: `{CFG.armor_mul_w1_5}` | elite_shield_mul_w1_5: `{CFG.elite_shield_mul_w1_5}`\n")
        lines.append(f"- shield caps (pct HP): default `{CFG.shield_cap_pct_default}`, elite `{CFG.shield_cap_pct_elite}`, boss `{CFG.shield_cap_pct_boss}`\n")
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
