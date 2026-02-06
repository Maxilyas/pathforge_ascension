# Pathforge Ascension — Patch v4.7.1

This patch is a **hotfix + tooling upgrade** on top of v4.7.0.

## Why GA was stuck at wave 2

Two issues made the headless balance simulation far harsher than the live game:

1. **Enemy HP was scaled by x30** in `Enemy.__post_init__`.
   - With the current `data/enemies.json` (e.g. SOLDIER hp=10), that became 300 HP on wave 1.
   - Result: wave 1–2 became a brick wall for *any* profile.

2. **Kill gold wasn't credited** in the sim.
   - The sim was reading `e.reward` while the Enemy model uses `reward_gold` (+ `tile_gold_bonus`).
   - Result: the bot's economy stalled early and couldn't scale.

## Changes

### Gameplay correctness
- `pathforge/entities/enemy.py`
  - Remove the accidental x30 HP scaling.

- `pathforge/balance/sim.py`
  - Fix kill reward accounting to match GameScene (`reward_gold + tile_gold_bonus`).
  - Set `world.stats = stats` so spawn-time perk debuffs are applied like in the real game.

### Bot stability (for tuning)
- `pathforge/balance/bot.py`
  - Add an early anti-armor tower (SNIPER) to the composition cycle from **wave 2+** when unlocked.
    This prevents the tuning loop from underestimating armored enemies (TANK can appear very early).

### Faster GA (parallel evaluation)
- `pathforge/balance/tune.py`
  - Add multiprocessing evaluation via `ProcessPoolExecutor`.
  - New env vars:
    - `PATHFORGE_BALANCE_WORKERS` (or `PATHFORGE_BALANCE_GA_WORKERS`) : number of processes.
  - Perk RNG is now **deterministic per episode seed**, reducing evaluation noise.

### Version
- `pathforge/__init__.py` → `__version__ = 4.7.1`
- `pathforge/game.py` → window caption `V4.7.1`

## How to use the new parallel GA

Example (PowerShell):

```powershell
$env:PATHFORGE_BALANCE_WORKERS = 6
$env:PATHFORGE_BALANCE_GA_POP = 26
$env:PATHFORGE_BALANCE_GA_GENS = 18
python -m pathforge.balance.tune --target humain_solide
```

Notes:
- Use **processes** (not threads). Start with ~`CPU_CORES - 2`.
- If you see pygame/display issues headless, keep `SDL_VIDEODRIVER=dummy`.
