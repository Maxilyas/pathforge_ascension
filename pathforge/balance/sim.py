
from __future__ import annotations
import os, random, json

TRACE = int(os.environ.get('PATHFORGE_BALANCE_TRACE','0'))
from dataclasses import dataclass
from typing import Dict, Any, Optional

# Force dummy video driver for pygame headless runs
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame

from ..settings import COLS, ROWS, DEFAULT_W, DEFAULT_H, TOP_BAR_FRAC, BOTTOM_BAR_FRAC, T_PATH
from ..world.grid import generate_grid
from ..world.world import World
from ..world.pathfinding import chain_path
from ..stats import CombatStats
from .bot import AutoBot

@dataclass
class EpisodeResult:
    seed: int
    waves_cleared: int
    gold_end: int
    lives_end: int

def _pick_enemy_key(enemies_db: Dict[str,Any], wave:int, rng: random.Random, boss: bool=False) -> str:
    keys = list(enemies_db.keys())
    # prefer explicit boss key
    if boss:
        for k in keys:
            if "BOSS" in k:
                return k
        return keys[-1]
    # progressive unlock: early waves use first few enemies
    # heuristics: keys are sorted by design (SOLDIER, SCOUT, TANK...)
    order = [k for k in keys if "BOSS" not in k]
    order = sorted(order)
    tier = min(len(order)-1, max(1, wave//3))
    pool = order[:tier+1]
    return pool[rng.randrange(0, len(pool))]

def _make_wave_plan(enemies_db: Dict[str,Any], wave:int, rng: random.Random) -> list[str]:
    boss = (wave % 10 == 0)
    if boss:
        # boss + escorts
        plan=[_pick_enemy_key(enemies_db, wave, rng, boss=True)]
        for _ in range(10 + wave//2):
            plan.append(_pick_enemy_key(enemies_db, wave, rng, boss=False))
        return plan
    # regular wave
    n = 14 + int(wave*2.2)
    plan=[]
    for _ in range(n):
        plan.append(_pick_enemy_key(enemies_db, wave, rng, boss=False))
    rng.shuffle(plan)
    return plan

def run_episode(towers_db: Dict[str,Any], enemies_db: Dict[str,Any], perks_roll_fn, seed:int=0, max_waves:int=35) -> EpisodeResult:
    pygame.init()
    pygame.display.set_mode((1,1))

    w,h = DEFAULT_W, DEFAULT_H
    game_h = h - int(h*BOTTOM_BAR_FRAC)
    tile = max(12, min(w // COLS, int(((h - int(h*BOTTOM_BAR_FRAC)) - int(h*TOP_BAR_FRAC)) // ROWS)))
    offset_x = 0
    offset_y = int(h*TOP_BAR_FRAC)

    rng = random.Random(seed)
    gs = generate_grid(COLS, ROWS, biome="PLAINS", seed=seed, rock_rate=0.0)
    world = World(gs, tile_size=tile, offset_x=offset_x, offset_y=offset_y, w=w, h=game_h, towers_db=towers_db, enemies_db=enemies_db, rng=rng)

    stats = CombatStats()
    bot = AutoBot(rng)

    # Spend starting talent points (may unlock towers/paths)
    try:
        bot.spend_talents(stats, wave=1)
    except Exception:
        pass

    # Align start paves with in-game rule: just above Start->End distance
    sx, sy = gs.start
    ex, ey = gs.end
    dist = abs(ex - sx) + abs(ey - sy)
    base_paves = int(dist * 1.12) + 2
    stats.paves = int(base_paves)
    stats.paves_cap = int(base_paves + 16)

    # Path building: use almost all paves to make a long snake
    max_len = max(10, int(getattr(stats, "paves", 0)))
    path = bot.build_path_snake(gs.cols, gs.rows, gs.start, gs.end, max_len=max_len)
    # mark grid tiles
    for x in range(gs.cols):
        for y in range(gs.rows):
            if (x,y) not in (gs.start, gs.end) and world.gs.grid[x][y] not in (0,):  # keep empties / towers
                pass
    used_paves = 0
    for c in path:
        x,y=c
        if c == gs.start:
            continue
        if c == gs.end:
            continue
        world.gs.grid[x][y] = T_PATH
        used_paves += 1
    world.invalidate_path()
    # consume paves (standard)
    stats.paves = max(0, int(stats.paves) - int(used_paves))

    # ensure valid chain
    if not world.get_path():
        # fallback: straight line
        x,y=gs.start
        ex,ey=gs.end
        while x!=ex:
            x += 1 if ex>x else -1
            if (x,y) not in (gs.start, gs.end):
                world.gs.grid[x][y]=T_PATH
        while y!=ey:
            y += 1 if ey>y else -1
            if (x,y) not in (gs.start, gs.end):
                world.gs.grid[x][y]=T_PATH
        world.invalidate_path()

    # economy start: place basic towers
    bot.place_towers(world, stats, max_towers=10)

    waves_cleared = 0
    dt = 1/60.0
    last_lives_lost = 0

    for wave in range(1, max_waves+1):
        if TRACE:
            print(f"[SIM] seed={seed} wave={wave} start gold={stats.gold} lives={stats.lives} paves={getattr(stats,'paves',0)} towers={len(world.towers)}")
        lives_before = int(stats.lives)
        # periodic upgrades/build
        multi = bot.choose_wave_multi(stats, wave, last_lives_lost)
        bot.upgrade_towers(world, stats, wave=wave)
        bot.place_towers(world, stats, max_towers=12 + wave//6)

        # spawn plan (supports assault multi)
        queue: list[tuple[str,int]] = []
        for i in range(max(1, int(multi))):
            wv = int(wave + i)
            for k in _make_wave_plan(enemies_db, wv, rng):
                queue.append((k, wv))
        rng.shuffle(queue)
        spawn_cd = 0.0

        # simulate until wave done
        t_acc = 0.0
        ticks = 0
        while (queue or world.enemies) and stats.lives > 0 and ticks < 20000:
            ticks += 1
            t_acc += dt
            spawn_cd -= dt
            if queue and spawn_cd <= 0.0:
                key, wv = queue.pop()
                world.spawn_enemy(key, wave=wv, gold_bonus=getattr(stats, "gold_per_kill", 0))
                spawn_cd = 0.28

            # compute buffs (minimal)
            buffs = {"dmg_mul":1.0, "rate_mul":1.0, "range_mul":1.0}

            # enemies update
            for e in list(world.enemies):
                e.update(dt, world=world, rng=rng)
                if getattr(e, "finished", False):
                    stats.lives -= 1
                    try:
                        world.enemies.remove(e)
                    except ValueError:
                        pass
                elif not getattr(e, "alive", True):
                    # reward
                    stats.gold += int(getattr(e, "reward", 0))
                    try:
                        world.enemies.remove(e)
                    except ValueError:
                        pass

            # towers update
            for t in list(world.towers):
                t.update(dt, world, rng, stats, buffs)

        if ticks >= 20000 and (queue or world.enemies):
            if TRACE:
                print(f"[SIM] wave={wave} TIMEOUT ticks={ticks} remaining_enemies={len(world.enemies)} remaining_queue={len(queue)}")
            # Treat as fail to avoid hanging tune() for too long
            stats.lives = 0

        if stats.lives <= 0:
            break

        # wave cleared
        waves_cleared += 1
        last_lives_lost = max(0, int(lives_before) - int(stats.lives))

        # end wave reward similar to GameScene (multi gives risk/reward)
        base = 85 + int(wave*7)
        multi_reward = 1.0 + 0.55*max(0, int(multi)-1)
        stats.gold += int(base * multi_reward)
        stats.end_wave_income(0)
        # boss => +1 talent point
        if wave % 10 == 0:
            stats.talent_pts += 1
            try:
                bot.spend_talents(stats, wave=wave)
            except Exception:
                pass

        # perk choice
        bias = min(0.60, 0.03*wave) + 0.12*max(0, int(multi)-1)
        bias = min(0.85, max(0.0, bias))
        options = perks_roll_fn(3, rarity_bias=bias)
        pick = bot.choose_perk(options, wave=wave)
        stats.apply_perk(options[pick])
        # if perk granted talent points, spend them
        try:
            bot.spend_talents(stats, wave=wave)
        except Exception:
            pass

    pygame.quit()
    return EpisodeResult(seed=seed, waves_cleared=waves_cleared, gold_end=stats.gold, lives_end=stats.lives)
