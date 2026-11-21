"""Ekran yerleşimi. Başlangıç ölçüleri Figma'daki 320x380 frame'lerden
alındı; 480 yükseklikte header ve alt bar biraz büyütüldü.

Header yerinde kalır, alt bar en alta iner, aradaki yer listeye gider.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Layout:
    width: int
    height: int

    # Yatay sınırlar (içerik x=4..310)
    left: int = 4
    content_w: int = 307

    # Header (Figma'da bar 22 px)
    header_line1_y: int = 2
    header_bar_y: int = 5
    header_bar_h: int = 28

    # Alt bar (Figma'da 58 px)
    footer_h: int = 66

    # Liste
    row_pitch: int = 37       # Figma'da satır aralıkları 34-40 px arası değişiyor, eşitlendi
    row_box_x: int = 4
    row_box_w: int = 287

    # -- header'dan türetilenler -------------------------------------------

    @property
    def header_line2_y(self) -> int:
        return self.header_bar_y + self.header_bar_h + 2

    @property
    def header_rule_y(self) -> int:   # 2 px
        return self.header_line2_y + 8

    @property
    def header_rule2_y(self) -> int:  # 1 px, üstü ve altı yumuşatma tonunda
        return self.header_rule_y + 5

    @property
    def first_row_cy(self) -> int:    # ilk satırın dikey merkezi
        return self.header_rule2_y + 30

    @property
    def scroll_top(self) -> int:
        return self.header_rule2_y + 12

    # -- alt bardan türetilenler -------------------------------------------

    @property
    def footer_y(self) -> int:
        return self.height - self.footer_h

    @property
    def footer_line_y(self) -> int:
        return self.footer_y - 4

    @property
    def chevron_cy(self) -> int:
        return self.footer_line_y - 21

    @property
    def scroll_bottom(self) -> int:
        return self.footer_line_y - 34

    @property
    def last_row_cy_max(self) -> int:
        return self.footer_line_y - 54

    # -- liste ---------------------------------------------------------------

    @property
    def visible_rows(self) -> int:
        return (self.last_row_cy_max - self.first_row_cy) // self.row_pitch + 1

    def row_cy(self, slot: int) -> int:
        return self.first_row_cy + slot * self.row_pitch
