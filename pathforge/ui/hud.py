from __future__ import annotations
import pygame
from ..settings import C_UI_BG, C_TEXT

def draw_top_bar(
    screen,
    fonts,
    w: int,
    top_h: int,
    stats,
    time_scale: float,
    keywords,
    path_ok: bool,
    fragments: int,
    spell_energy: float,
    spell_energy_max: float,
    plan_preview: str = "",
):
    pygame.draw.rect(screen, C_UI_BG, (0, 0, w, top_h))

    paves = getattr(stats, "paves", 0)
    line1 = f"VAGUE {stats.wave}   $ {stats.gold}   PV {stats.lives}   SH {stats.core_shield}   FRAG {fragments}   RR {getattr(stats, 'perk_rerolls', 0)}   PAVES {paves}"
    t = fonts.l.render(line1, True, C_TEXT)
    screen.blit(t, (80, 14))

    ktxt = " | ".join(list(keywords)[:4])
    kcol = (120, 255, 120) if path_ok else (255, 120, 120)
    extra = f"   |   {plan_preview}" if plan_preview else ""
    t2 = fonts.s.render(f"Prochain assaut: {ktxt}{extra}", True, kcol)
    screen.blit(t2, (80, top_h // 2 + 10))

    # energy bar
    bar_w = 240
    bx = w - bar_w - 220
    by = 16
    pygame.draw.rect(screen, (50, 50, 60), (bx, by, bar_w, 14), border_radius=7)
    fill = int(bar_w * (spell_energy / max(1.0, spell_energy_max)))
    pygame.draw.rect(screen, (120, 200, 255), (bx, by, fill, 14), border_radius=7)
    et = fonts.xs.render("ENERGIE", True, (220, 220, 220))
    screen.blit(et, (bx, by + 16))


def draw_bottom_bar(
    screen,
    fonts,
    w: int,
    game_h: int,
    bottom_h: int,
    mode: str,
    tool: str,
    tower_name: str,
    tower_cost: int,
    wave_multi: int,
    tooltip_line: str,
    tool_extra: str = "",
):
    pygame.draw.rect(screen, C_UI_BG, (0, game_h, w, bottom_h))

    tool_display = tool if not tool_extra else f"{tool} ({tool_extra})"
    left = fonts.s.render(
        f"Mode: {mode}  |  Outil: {tool_display}  |  Tour: {tower_name} (${tower_cost})",
        True,
        (220, 220, 220),
    )
    screen.blit(left, (20, game_h + 16))

    multi = fonts.s.render(f"Assaut x{wave_multi} (difficulté & butin)", True, (255, 215, 0))
    screen.blit(multi, (20, game_h + 44))

    tip = fonts.xs.render(tooltip_line, True, (180, 180, 190))
    screen.blit(tip, (20, game_h + bottom_h - 22))
