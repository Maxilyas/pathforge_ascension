from __future__ import annotations

# Window defaults (can toggle fullscreen later)
DEFAULT_W = 1280
DEFAULT_H = 720
FPS = 60

COLS = 22
TOP_BAR_FRAC = 0.12
BOTTOM_BAR_FRAC = 0.18

# tiles
T_EMPTY = 0

# buildable path tiles (variants)
T_PATH  = 1          # standard
T_PATH_FAST = 11     # paved highway: faster enemies, more gold if killed on it
T_PATH_MUD = 12      # mud: slows enemies, but projectile towers may miss more often
T_PATH_CONDUCT = 13  # conductive: boosts ENERGY chaining
T_PATH_CRYO = 14     # cryo: strengthens slows, but reduces FIRE damage
T_PATH_MAGMA = 15    # magma: applies a light burn to enemies
T_PATH_RUNE = 16     # rune: rare tile (powered bonuses; gated by fragments)

T_TOWER = 2
T_START = 3
T_END   = 4
T_RELIC = 7
T_ROCK  = 9

PATH_TILES = {
    T_PATH, T_PATH_FAST, T_PATH_MUD, T_PATH_CONDUCT, T_PATH_CRYO, T_PATH_MAGMA, T_PATH_RUNE,
    T_START, T_END,
}

# colors
C_BG      = (15, 18, 25)
C_UI_BG   = (30, 35, 40)
C_GRID    = (40, 45, 50)
C_ROCK    = (55, 45, 35)

C_PATH    = (85, 85, 95)
C_PATH_FAST = (120, 110, 70)
C_PATH_MUD  = (90, 70, 55)
C_PATH_CONDUCT = (60, 105, 140)
C_PATH_CRYO = (65, 140, 155)
C_PATH_MAGMA = (150, 80, 45)
C_PATH_RUNE = (140, 90, 170)

C_START   = (0, 200, 120)
C_END     = (0, 110, 210)
C_TEXT    = (240, 240, 240)
C_GOLD    = (255, 215, 0)
