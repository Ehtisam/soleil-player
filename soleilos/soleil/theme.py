"""Renk temaları. Arayüzdeki bütün renkler buradan gelir."""

from __future__ import annotations

import colorsys
from dataclasses import dataclass, fields

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Theme:
    name: str
    bg: Color             # ekran zemini
    fg: Color             # ana renk: yazılar, header, seçili satır
    rule: Color          # seçili satır çizgileri, alt bar çizgisi
    rule_dim: Color       # header altındaki ikinci çizgi, aşağı ok
    rule_dim_soft: Color  # rule_dim'in yumuşatma tonu
    panel: Color          # alt bar zemini, header yazısı
    on_fg: Color          # seçili satırdaki yazı
    on_fg_icon: Color     # seçili satırdaki ikon


# Figma'dan ölçülen renkler (main1)
AMBER = Theme(
    name="amber",
    bg=(20, 15, 15),
    fg=(196, 124, 54),
    rule=(108, 69, 34),
    rule_dim=(62, 43, 24),
    rule_dim_soft=(41, 29, 19),
    panel=(32, 19, 6),
    on_fg=(0, 0, 0),
    on_fg_icon=(20, 15, 15),
)

# Figma'dan ölçülen renkler (main1alt)
PURPLE = Theme(
    name="mor",
    bg=(20, 15, 15),
    fg=(156, 98, 196),
    rule=(88, 56, 105),
    rule_dim=(42, 24, 62),
    rule_dim_soft=(31, 19, 38),
    panel=(29, 16, 36),
    on_fg=(0, 0, 0),
    on_fg_icon=(20, 15, 15),
)


def mix(a: Color, b: Color, t: float) -> Color:
    """a'dan b'ye t oranında geçiş (0 = a, 1 = b)."""
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def _rotate_hue(theme: Theme, name: str, hue: float) -> Theme:
    """Amber temanın tonunu çevirerek yeni tema üretir. Zemin ve
    seçili satır yazısı gibi renksiz alanlar olduğu gibi kalır."""
    keep = {"bg", "on_fg", "on_fg_icon"}
    values = {}
    for f in fields(theme):
        v = getattr(theme, f.name)
        if f.name == "name":
            values[f.name] = name
        elif f.name in keep:
            values[f.name] = v
        else:
            _, l, s = colorsys.rgb_to_hls(*(c / 255 for c in v))
            values[f.name] = tuple(round(c * 255) for c in colorsys.hls_to_rgb(hue, l, s))
    return Theme(**values)


# Taslak: tonlar henüz seçilmedi, amber'den türetildi
RED = _rotate_hue(AMBER, "kırmızı", 0.0)
BLUE = _rotate_hue(AMBER, "mavi", 0.58)

THEMES = {t.name: t for t in (AMBER, PURPLE, RED, BLUE)}
