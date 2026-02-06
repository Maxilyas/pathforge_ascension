# Patch Notes — v4.7.2

## Balance / Simulation
- **WaveDirector early-waves fix**: waves 1–2 no longer include **TANK / ELITE / shielded** units.
  - New progressive roster unlock:
    - W1–2: SOLDIER, SCOUT
    - W3–4: + MUTANT
    - W5–6: + PYRO
    - W7–9: + TANK
    - W10–12: + WISP
    - W13+: + ELITE
- **Theme selection bounded by wave** so "Armored" / "Shields" themes don't appear too early.
- **Early enemy count reduced** (`count = 9 + int(w*1.7)`) to prevent unavoidable leaks before the economy stabilizes.

## Perks
- **Fixed perk grant application**: perks now accept `grants` (plural) as used by the perk DB, while keeping backward-compat with `grant`.

## GA Tuner
- Added seed scheduling mode:
  - `PATHFORGE_BALANCE_GA_SEED_MODE=fixed` (default): common random numbers (less noise, seeds repeat in logs).
  - `rotate`: new episode seeds each generation.
  - `mixed`: stable seeds, but refresh the last seed each generation.
- GA cache key now includes the episode seed tuple (required for rotate/mixed).
- GA prints its seed schedule at gen 1.

## Notes
This patch targets the observed behavior where **every build dies during wave 2**, causing the GA to plateau around ~1 cleared wave.
