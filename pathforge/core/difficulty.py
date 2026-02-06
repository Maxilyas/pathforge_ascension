from __future__ import annotations

"""Difficulty curves & early/late balancing knobs.

This module centralizes wave-scaling logic so we don't scatter "magic numbers"
inside gameplay entities.

Design goals (v4.7.0):
- Waves 1–5: easier (less armor baseline, weaker elite shields)
- Waves 6–10: smooth ramp back to baseline
- After wave 10: stronger scaling (to keep late-game pressure)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class DifficultyConfig:
    # --- HP scaling ---
    hp_slope_pre10: float = 0.19
    hp_slope_post10: float = 0.29

    # --- Shield scaling ---
    shield_base_factor: float = 6.0  # was 8.0 in v4_6_4_1
    shield_slope_pre10: float = 0.15
    shield_slope_post10: float = 0.22

    # --- Early armor easing ---
    armor_mul_w1_5: float = 0.78
    armor_mul_w6_10: float = 1.00

    # --- Elite shield easing ---
    elite_shield_mul_w1_5: float = 0.68
    elite_shield_mul_w6_10: float = 0.88
    elite_shield_mul_post10: float = 1.00

    # --- Shield caps (relative to HP) ---
    shield_cap_pct_default: float = 1.25
    shield_cap_pct_elite: float = 0.70
    shield_cap_pct_boss: float = 0.60


CFG = DifficultyConfig()


def _lerp(a: float, b: float, t: float) -> float:
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return a + (b - a) * t


def hp_tier(wave: int) -> float:
    """Piecewise-linear HP tier. Lower slope pre-10, higher slope post-10."""
    w = max(1, int(wave))
    if w <= 10:
        return 1.0 + CFG.hp_slope_pre10 * (w - 1)
    base = 1.0 + CFG.hp_slope_pre10 * 9
    return base + CFG.hp_slope_post10 * (w - 10)


def shield_tier(wave: int) -> float:
    """Piecewise shield tier. Slightly slower than HP early, then catches up."""
    w = max(1, int(wave))
    if w <= 10:
        return 1.0 + CFG.shield_slope_pre10 * (w - 1)
    base = 1.0 + CFG.shield_slope_pre10 * 9
    return base + CFG.shield_slope_post10 * (w - 10)


def armor_multiplier(wave: int, tags: list[str] | None) -> float:
    """Armor baseline easing during early waves (1–5), smooth to baseline by wave 10."""
    w = max(1, int(wave))
    if w <= 5:
        return CFG.armor_mul_w1_5
    if w <= 10:
        # lerp from early easing to baseline across waves 6..10
        t = (w - 6) / 4.0
        return _lerp(CFG.armor_mul_w1_5, CFG.armor_mul_w6_10, t)
    return 1.0


def elite_shield_multiplier(wave: int, tags: list[str] | None) -> float:
    """Extra shield easing for ELITE/BOSS during early waves."""
    tags = tags or []
    if "ELITE" not in tags and "BOSS" not in tags:
        return 1.0
    w = max(1, int(wave))
    if w <= 5:
        return CFG.elite_shield_mul_w1_5
    if w <= 10:
        t = (w - 6) / 4.0
        return _lerp(CFG.elite_shield_mul_w1_5, CFG.elite_shield_mul_w6_10, t)
    return CFG.elite_shield_mul_post10


def shield_cap_pct(tags: list[str] | None) -> float:
    tags = tags or []
    if "BOSS" in tags:
        return CFG.shield_cap_pct_boss
    if "ELITE" in tags:
        return CFG.shield_cap_pct_elite
    return CFG.shield_cap_pct_default
