# Pathforge Ascension — Patch v4.7.0

## Ce que contient cette version
Base **v4_6_4_1** + patchs de balancing + améliorations "propres".

### 1) Courbes de difficulté (early/late)
Fichier: `pathforge/core/difficulty.py` (appliqué dans `pathforge/entities/enemy.py`).

- **HP**: slope plus doux jusqu'à wave 10, puis slope plus fort après wave 10.
- **Armor**: réduction de l'armure effective waves 1–5, retour progressif à la normale jusqu'à wave 10.
- **Shield**:
  - facteur de base réduit (6.0 au lieu de 8.0)
  - tier plus doux avant wave 10 puis plus fort après wave 10
  - **multiplicateur spécial ELITE/BOSS** réduit waves 1–5 et lissé jusqu'à wave 10
  - **cap du shield** en % de HP (différent pour normal / elite / boss) pour éviter les extrêmes.

### 2) Tuner GA + wide ranges
Fichier: `pathforge/balance/tune.py`.

- Ajout d'un **tuner par algorithme génétique (GA)**:
  - population + générations + mutations (avec "big jumps" pour sortir des minima locaux)
  - seeds d'évaluation fixes pour réduire le bruit
  - pénalité légère sur la variance (std) pour éviter les profils instables
- Le tuner écrit :
  - `saves/balance_profile.json`
  - `saves/balance_profile.md` (rapport enrichi: mean/std/min/median/max + rappel des courbes)
- **Par défaut**: `PATHFORGE_BALANCE_ALGO=GA` (sauf si `PATHFORGE_BALANCE_EXHAUSTIVE=1`).

### 3) Bot de simulation amélioré (compo + killzone)
Fichier: `pathforge/balance/bot.py` + MAJ `pathforge/balance/sim.py`.

- Calcul d'une **killzone** (segment dense du chemin) et priorité de placement autour.
- **Cycle de composition** de tours dépendant de la wave (DPS + AOE + anti-shield + contrôle si disponibles).
- La simulation passe maintenant `wave=...` à `place_towers(...)` pour adapter la compo.

### 4) Nettoyage des artefacts runtime
- Suppression des fichiers `saves/` issus d'exécutions (profil, run, télémétrie) dans le ZIP livré.
- Le dossier `saves/` est conservé (avec `.gitkeep`) pour accueillir les sorties du tuner.

### 5) Versioning
- `pathforge/__init__.py` => `__version__ = 4.7.0`
- `pathforge/game.py` => titre fenêtre `V4.7.0` + télémétrie `v4_7_0`
