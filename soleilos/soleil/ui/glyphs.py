"""Tuş işaretleri: Göktürk (Orhun) harfleri.

Altı işaret birlikte SOLEİL yazar. Sol yandaki üç tuş yukarıdan aşağı
"SOL", üsttekiler "Eİ", encoder da sondaki ince L. Aynı harfler kasada
tuş başlıklarına kazınacak.

  Sol 1   S  (𐰽)     Üst 1    E  (𐰀)
  Sol 2   O  (𐰆)     Üst 2    İ  (𐰃)
  Sol 3   L  (𐰞, kalın L)   encoder  L  (𐰠, ince L)

Fontta yok; köşeli taş yazısı halleri çizgi olarak burada tanımlı. Yazılarla
aynı yumuşaklıkta görünsün diye 4 kat büyük çizilip küçültülüyor.
"""

from __future__ import annotations

import pygame

from ..lang import _, tr
from ..input import Action

# Birim kutuda (0..1, genişlik yüksekliğin 0.7'si) çizgiler
SHAPES = {
    "S": [[(0.30, 0.0), (0.05, 0.25), (0.70, 0.72), (0.45, 1.0)],
          [(0.92, 0.12), (0.55, 0.28), (0.40, 0.50)]],
    "O": [[(0.20, 0.0), (0.80, 0.5), (0.20, 1.0)]],
    "L": [[(0.72, 0.0), (0.72, 1.0), (0.22, 0.66)]],
    "E": [[(0.88, 0.30), (0.50, 0.0), (0.50, 1.0), (0.12, 0.70)]],
    "İ": [[(0.32, 1.0), (0.32, 0.0), (0.78, 0.36)]],
    "L2": [[(0.10, 0.0), (0.50, 0.42), (0.90, 0.0)], [(0.50, 0.42), (0.50, 1.0)]],
}

KEYS = {
    Action.LEFT1: "S",
    Action.LEFT2: "O",
    Action.BACK: "L",
    Action.TOP1: "E",
    Action.TOP2: "İ",
    Action.SELECT: "L2",
    Action.HOLD: "L2",
}


SUPERSAMPLE = 4   # 4 kat büyük çizilip küçültülür: çapraz çizgiler basamaklı olmaz
_masks: dict[tuple, pygame.Surface] = {}
_tinted: dict[tuple, pygame.Surface] = {}


def _mask(name: str, h: int, width: float) -> pygame.Surface:
    """Beyaz, kenarları yumuşatılmış işaret (yazılardaki gibi)."""
    key = (name, h, width)
    if key not in _masks:
        k = SUPERSAMPLE
        pad = width                      # çizgi kalınlığı kutudan taşmasın
        bw = h * 0.7
        out_size = (round(bw + 2 * pad), round(h + 2 * pad))
        big = pygame.Surface((out_size[0] * k, out_size[1] * k), pygame.SRCALPHA)
        w = max(1, round(width * k))
        # Uç noktalar piksel ızgarasına oturur: dikey ve yatay çizgiler bulanık
        # olmaz, sadece çaprazlar yumuşatılır
        half = 0.5 if round(width) % 2 else 0.0

        def snap(v: float) -> float:
            return (round(v - half) + half) * k

        for line in SHAPES[name]:
            pts = [(snap(pad + x * bw), snap(pad + y * h)) for x, y in line]
            pygame.draw.lines(big, (255, 255, 255), False, pts, w)
            for p in pts:   # yuvarlak uç ve köşeler
                pygame.draw.circle(big, (255, 255, 255), p, w / 2)
        _masks[key] = pygame.transform.smoothscale(big, out_size)
    return _masks[key]


def draw(surf: pygame.Surface, key, color, center, h: int = 14, width: float = 2.0) -> pygame.Rect:
    """Bir işareti çizer. key: Action ya da harf adı ("S", "L2"...)."""
    name = KEYS.get(key, key)
    tkey = (name, h, width, tuple(color))
    if tkey not in _tinted:
        img = _mask(name, h, width).copy()
        img.fill((*color, 255), special_flags=pygame.BLEND_RGBA_MULT)
        _tinted[tkey] = img
    img = _tinted[tkey]
    rect = img.get_rect(center=(round(center[0]), round(center[1])))
    surf.blit(img, rect)
    return rect


def draw_hints(app, surf: pygame.Surface, hints, color, pos, anchor: str = "midleft",
               style: str = "small", gap: int = 18) -> pygame.Rect:
    """İşaretli ipucu satırı: [(Action, "SÖZLER"), ...]. Uzun basma için
    yazının başına "UZUN:" eklenir."""
    h = 13 if style == "small" else 15
    parts = []
    for action, label in hints:
        if action is Action.HOLD:
            label = _("UZUN: {label}").format(label=tr(label))
        parts.append((action, label, round(h * 0.7) + 5 + app.text.width(label, style)))
    total = sum(w for *_, w in parts) + gap * (len(parts) - 1)
    rect = pygame.Rect(0, 0, total, h + 4)
    setattr(rect, anchor, pos)
    x = rect.x
    for action, label, w in parts:
        draw(surf, action, color, (x + h * 0.35, rect.centery), h)
        app.text.draw(surf, label, style, color, (x + round(h * 0.7) + 5, rect.centery - 1), "midleft")
        x += w + gap
    return rect
