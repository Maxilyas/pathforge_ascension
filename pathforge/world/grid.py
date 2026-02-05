from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple
import random
from ..settings import T_EMPTY, T_START, T_END, T_ROCK

Coord = Tuple[int, int]

@dataclass
class GridState:
    cols: int
    rows: int
    grid: List[List[int]]
    start: Coord
    end: Coord

    # Overlays (do NOT live in the grid values)
    relics: List[Coord] = field(default_factory=list)
    runes: List[Coord] = field(default_factory=list)

    seed: int = 0
    biome: str = "HIGHLANDS"


def generate_grid(cols: int, rows: int, biome: str, seed: int, rock_rate: float = 0.20) -> GridState:
    rng = random.Random(seed)
    grid = [[T_EMPTY for _ in range(rows)] for _ in range(cols)]
    start = (1, rows // 2)
    end = (cols - 2, rows // 2)
    grid[start[0]][start[1]] = T_START
    grid[end[0]][end[1]] = T_END

    # rocks
    for x in range(cols):
        for y in range(rows):
            if (x, y) in (start, end):
                continue
            if rng.random() < rock_rate:
                grid[x][y] = T_ROCK

    # clear around start/end to keep early planning readable
    def clear(cx: int, cy: int, rx: int, ry: int):
        for x in range(cx - rx, cx + rx + 1):
            for y in range(cy - ry, cy + ry + 1):
                if 0 <= x < cols and 0 <= y < rows and grid[x][y] == T_ROCK:
                    grid[x][y] = T_EMPTY

    clear(start[0], start[1], 2, 2)
    clear(end[0], end[1], 2, 2)

    # --- overlays ---
    relics: List[Coord] = []
    runes: List[Coord] = []

    # relic nodes (visual + plan bonus when paved through)
    for _ in range(max(2, cols // 8)):
        x = rng.randint(3, cols - 4)
        y = rng.randint(2, rows - 3)
        if grid[x][y] == T_EMPTY:
            relics.append((x, y))

    # rare rune nodes (must be powered by a conductive path tile)
    # 12% chance to get 1 rune, +3% chance to get a 2nd rune
    rune_count = 0
    if rng.random() < 0.12:
        rune_count = 1 + (1 if rng.random() < 0.03 else 0)

    tries = 0
    while len(runes) < rune_count and tries < 80:
        tries += 1
        x = rng.randint(4, cols - 5)
        y = rng.randint(3, rows - 4)
        if grid[x][y] != T_EMPTY:
            continue
        if (x, y) in relics:
            continue
        # keep runes away from start/end clutter
        if abs(x - start[0]) + abs(y - start[1]) < 6:
            continue
        if abs(x - end[0]) + abs(y - end[1]) < 6:
            continue
        runes.append((x, y))

    return GridState(cols=cols, rows=rows, grid=grid, start=start, end=end, relics=relics, runes=runes, seed=seed, biome=biome)


def tile(gs: GridState, c: Coord) -> int:
    return gs.grid[c[0]][c[1]]
