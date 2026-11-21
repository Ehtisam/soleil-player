"""Kayan yazı: sığmayan yazı önce bir an durur, sonuna kadar kayar,
sonunda bir an durur ve başa döner."""

from __future__ import annotations

import pygame

from .. import lang

SPEED = 28        # piksel / saniye
PAUSE_START = 1.2
PAUSE_END = 1.0


def offset(overflow: int, t: float) -> int:
    if overflow <= 0:
        return 0
    travel = overflow / SPEED
    cycle = PAUSE_START + travel + PAUSE_END
    x = t % cycle
    if x < PAUSE_START:
        return 0
    if x < PAUSE_START + travel:
        return round((x - PAUSE_START) * SPEED)
    return overflow


def draw(app, surf: pygame.Surface, text: str, style: str, color,
         rect: pygame.Rect, t: float, cy: int | None = None, raw: bool = False) -> bool:
    """Yazıyı rect içine sola yaslı çizer; sığmıyorsa kaydırır.
    Kayıyorsa True döner (ekranın animasyon gerektirdiğini bilmek için)."""
    cy = rect.centery if cy is None else cy
    if not raw:
        text = lang.tr(text)
    overflow = app.text.width(text, style, raw=True) - rect.w
    old = surf.get_clip()
    surf.set_clip(rect.clip(old) if old else rect)
    app.text.draw(surf, text, style, color, (rect.x - offset(overflow, t), cy), "midleft", raw=True)
    surf.set_clip(old)
    return overflow > 0
