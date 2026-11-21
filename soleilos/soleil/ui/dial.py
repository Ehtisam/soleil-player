"""Kadran şeridi: eski radyo kadranı gibi kayan seçenekler.

Encoder çevrildikçe öğeler kayar; ortadaki ışımalı kutudaki öğe seçilidir,
yanlara doğru soluklaşır. Not Defteri'nde harf, hesap makinesinde rakam
seçmek için.

Kullanan ekran bir sayaç tutar (sınırsız artar, mod alınır) ve kayma için
yumuşak bir kopyasını (anim) her karede sayaca yaklaştırır: Dial sınıfı.
"""

from __future__ import annotations

import math
from typing import Callable, Optional

import pygame

from ..theme import mix

STEP = 18          # yanlardaki öğeler arası
BOX = (44, 52)     # ortadaki kutu


class Dial:
    def __init__(self, position: int = 0) -> None:
        self.position = position
        self.anim = float(position)

    def turn(self, step: int) -> None:
        self.position += step

    def jump(self, position: int) -> None:
        self.position = position
        self.anim = float(position)

    def index(self, n: int) -> int:
        return self.position % n

    def update(self, dt: float) -> bool:
        """True dönerse hâlâ kayıyor (ekran animasyonda kalmalı)."""
        diff = self.position - self.anim
        if abs(diff) < 0.02:
            self.anim = float(self.position)
            return False
        self.anim += diff * min(1.0, dt * 16)
        return True


def default_item(app, surf, item: str, color, center, big: bool) -> None:
    app.text.draw(surf, item, "display" if big else "body", color,
                  (center[0] + (1 if big else 0), center[1] - 1), "center")


def draw(app, surf: pygame.Surface, items: list, anim: float, cy: int,
         draw_item: Optional[Callable] = None) -> int:
    """Şeridi çizer, ortadaki kutunun x merkezini döndürür."""
    t, L = app.theme, app.layout
    draw_item = draw_item or default_item
    n = len(items)
    cx = (L.left + L.row_box_w) // 2 + 2
    band = pygame.Rect(L.left, cy - 32, L.row_box_w, 64)
    surf.fill(t.rule_dim, (band.x, band.top, band.w, 1))
    surf.fill(t.rule_dim, (band.x, band.bottom, band.w, 1))

    old_clip = surf.get_clip()
    surf.set_clip(band.inflate(0, -2))
    half_box = BOX[0] // 2
    base = math.floor(anim)
    for k in range(base - 8, base + 10):
        dd = k - anim
        dist = abs(dd)
        if dist < 0.5:
            continue
        sign = 1 if dd > 0 else -1
        x = cx + sign * (min(dist, 1) * (half_box + 12) + max(dist - 1, 0) * STEP)
        color = mix(t.fg, t.bg, min(0.85, 0.12 + dist * 0.13))
        draw_item(app, surf, items[k % n], color, (x, cy), False)
    surf.set_clip(old_clip)

    box = pygame.Rect(0, 0, *BOX)
    box.center = (cx, cy)
    for gap, color in ((2, t.fg), (4, t.rule)):
        surf.fill(color, (box.x, box.top - gap - 1, box.w, 1))
        surf.fill(color, (box.x, box.bottom + gap, box.w, 1))
    surf.fill(t.fg, box)
    draw_item(app, surf, items[round(anim) % n], t.on_fg, box.center, True)
    return cx
