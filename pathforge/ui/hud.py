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
    # background
    pygame.draw.rect(screen, C_UI_BG, (0, 0, w, top_h))

    # --- Right-side layout (reserve space) ---
    bar_w = 220
    right_reserved = 210  # room for speed button + icons on the far right
    bx = max(20, w - bar_w - right_reserved)
    by = 12

    # Clip left text so it never overlaps right UI
    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(0, 0, bx - 16, top_h))

    paves = int(getattr(stats, "paves", 0))
    rr = int(getattr(stats, "perk_rerolls", 0))

    # Fit: use L if possible, else M
    line1 = f"VAGUE {stats.wave}   $ {int(stats.gold)}   PV {int(stats.lives)}   SH {int(stats.core_shield)}   FRAG {int(fragments)}   RR {rr}   PAVES {paves}"
    font = fonts.l
    t = font.render(line1, True, C_TEXT)
    if t.get_width() > (bx - 96):
        font = fonts.m
        t = font.render(line1, True, C_TEXT)
    screen.blit(t, (80, 12))

    # plan / preview
    ktxt = " | ".join(list(keywords)[:4])
    kcol = (120, 255, 120) if path_ok else (255, 120, 120)
    extra = f"   |   {plan_preview}" if plan_preview else ""
    t2 = fonts.s.render(f"Prochain assaut: {ktxt}{extra}", True, kcol)
    screen.blit(t2, (80, top_h // 2 + 10))

    screen.set_clip(old_clip)

    # --- energy bar (right) ---
    pygame.draw.rect(screen, (50, 50, 60), (bx, by, bar_w, 14), border_radius=7)
    fill = int(bar_w * (spell_energy / max(1.0, spell_energy_max)))
    pygame.draw.rect(screen, (120, 200, 255), (bx, by, fill, 14), border_radius=7)
    pygame.draw.rect(screen, (90, 90, 105), (bx, by, bar_w, 14), 2, border_radius=7)

    # label inside the bar area
    lbl = fonts.xs.render(f"ENERGIE {int(spell_energy)}/{int(spell_energy_max)}", True, (230, 230, 230))
    lx = bx + bar_w//2 - lbl.get_width()//2
    ly = by + 18
    screen.blit(lbl, (lx, ly))


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

    # Second row: left = wave multiplier info, right = keyboard shortcuts.
    # This prevents vertical overlap and keeps the HUD readable.
    row2_y = game_h + 44
    multi_s = fonts.s.render(f"Assaut x{wave_multi} (difficulté & butin)", True, (255, 215, 0))
    screen.blit(multi_s, (20, row2_y))

    tip_s = fonts.xs.render(tooltip_line, True, (180, 180, 190))
    tip_xmin = 20 + multi_s.get_width() + 24
    tip_area_w = max(0, w - 20 - tip_xmin)

    old_clip = screen.get_clip()
    screen.set_clip(pygame.Rect(0, game_h, w, bottom_h))

    if tip_area_w >= 160:
        # Right-align inside the available space so it doesn't collide with the left text.
        screen.set_clip(pygame.Rect(tip_xmin, game_h, tip_area_w, bottom_h))
        tip_x = tip_xmin + tip_area_w - tip_s.get_width()
        tip_x = max(tip_xmin, tip_x)
        screen.blit(tip_s, (tip_x, row2_y + 2))
    else:
        # Not enough horizontal room -> move to a third row (still above the button row).
        row3_y = row2_y + fonts.s.get_height() + 6
        screen.blit(tip_s, (20, row3_y))

    screen.set_clip(old_clip)
