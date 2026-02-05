from __future__ import annotations
import pygame

class Fonts:
    def __init__(self, tile: int):
        self.xl = pygame.font.SysFont("Arial", max(18, int(tile*0.80)), bold=True)
        self.l  = pygame.font.SysFont("Arial", max(16, int(tile*0.52)), bold=True)
        self.m  = pygame.font.SysFont("Arial", max(14, int(tile*0.36)), bold=True)
        self.s  = pygame.font.SysFont("Arial", max(12, int(tile*0.27)))
        self.xs = pygame.font.SysFont("Arial", max(11, int(tile*0.22)))

def make_fonts(tile: int) -> Fonts:
    return Fonts(tile)
