"""İkon maskelerini yükler ve istenen renge boyar."""

from __future__ import annotations

import pygame

from .config import ASSETS

ICON_DIR = ASSETS / "icons"


class Icons:
    def __init__(self) -> None:
        self._masks: dict[str, pygame.Surface] = {}
        self._tinted: dict[tuple, pygame.Surface] = {}

    def _mask(self, name: str) -> pygame.Surface:
        if name not in self._masks:
            self._masks[name] = pygame.image.load(str(ICON_DIR / f"{name}.png")).convert_alpha()
        return self._masks[name]

    def get(self, name: str, color) -> pygame.Surface:
        key = (name, color)
        if key not in self._tinted:
            surf = self._mask(name).copy()
            surf.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
            self._tinted[key] = surf
        return self._tinted[key]

    def draw(self, surf: pygame.Surface, name: str, color, pos, anchor: str = "topleft") -> pygame.Rect:
        icon = self.get(name, color)
        rect = icon.get_rect(**{anchor: pos})
        surf.blit(icon, rect)
        return rect
