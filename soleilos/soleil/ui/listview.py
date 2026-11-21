"""Numaralı menü listesi: ana menü ve alt menülerin ortak ekranı.

Alt menülerde listenin başında numarasız bir "GERİ" satırı olur; encoder
ile oraya çıkıp tıklamak da Sol 3 (geri) tuşu gibi çalışır.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pygame

from ..input import Action
from ..screens.base import Screen
from . import chrome, marquee


@dataclass
class ListItem:
    label: str
    icon: Optional[str] = None
    count: Optional[str] = None                  # etiketin hemen yanında küçük yazı, ör. [21]
    right: Optional[str] = None                  # sağa yaslı küçük yazı, ör. [89MB]
    open: Optional[Callable[[], Screen]] = None  # seçilince açılacak ekran
    act: Optional[Callable[[], None]] = None     # seçilince yapılacak iş (ekran açmadan)
    value: Optional[Callable[[], str]] = None    # sağdaki yazı her çizimde buradan okunur
    raw: bool = False                            # kullanıcının adı (şarkı, not, cihaz): çevrilmez


BACK = ListItem("GERİ", icon="back")


def draw_back_row(app, surf: pygame.Surface, cy: int, selected: bool, label: str = "GERİ") -> None:
    """Alt ekranların başındaki "< GERİ" satırı."""
    t = app.theme
    if selected:
        chrome.draw_selection(app, surf, cy)
    color = t.on_fg if selected else t.fg
    app.icons.draw(surf, "back", t.on_fg_icon if selected else t.fg, (14, cy), "center")
    app.text.draw(surf, label, "body", color, (24, cy - 1), "midleft")


class ListScreen(Screen):
    def __init__(self, app, items: list[ListItem], selected: int = 0,
                 back_row: bool = True) -> None:
        super().__init__(app)
        self.back_row = back_row
        self.rows = ([BACK] if back_row else []) + items
        # selected: ilk gerçek öğeden saymaya başlar (GERİ satırı hariç)
        self.selected = min(selected + (1 if back_row else 0), len(self.rows) - 1)
        self.first = 0
        self.has_icons = any(item.icon for item in items)
        self.selected_at = app.time      # seçimin değiştiği an (kayan yazı için)
        self.animating = False           # seçili yazı sığmıyorsa kayar
        self._scroll_to_selected()

    def _scroll_to_selected(self) -> None:
        visible = self.app.layout.visible_rows
        if self.selected < self.first:
            self.first = self.selected
        elif self.selected >= self.first + visible:
            self.first = self.selected - visible + 1

    def handle(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            step = -1 if action is Action.UP else 1
            self.selected = (self.selected + step) % len(self.rows)
            self.selected_at = self.app.time
            self._scroll_to_selected()
        elif action is Action.SELECT:
            row = self.rows[self.selected]
            if row is BACK:
                self.app.pop()
            elif row.act:
                row.act()
            elif row.open:
                self.app.push(row.open())
        else:
            super().handle(action)

    # -- çizim -------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, L = self.app, self.app.layout
        chrome.draw_header(app, surf, self.title)

        visible = L.visible_rows
        self.animating = False
        for slot, index in enumerate(range(self.first, min(self.first + visible, len(self.rows)))):
            self._draw_row(surf, index, L.row_cy(slot))

        chrome.draw_scrollbar(app, surf, L.row_cy(self.selected - self.first))
        if self.first + visible < len(self.rows):
            chrome.draw_chevron(app, surf)
        chrome.draw_footer(app, surf)

    def _draw_row(self, surf: pygame.Surface, index: int, cy: int) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        row = self.rows[index]
        selected = index == self.selected
        if row is BACK:
            draw_back_row(app, surf, cy, selected)
            return

        if selected:
            chrome.draw_selection(app, surf, cy)
            text_color, icon_color = t.on_fg, t.on_fg_icon
        else:
            text_color, icon_color = t.fg, t.fg
        text_cy = cy - 1

        number = index - (1 if self.back_row else 0) + 1
        app.text.draw(surf, f"[{number:02d}]", "body", text_color, (3.2, text_cy), "midleft")
        if row.icon:
            app.icons.draw(surf, row.icon, icon_color, (64, cy), "center")

        # Sağ taraf: küçük etiket ya da seçiliyse işaret kutusu
        right_edge = L.row_box_x + L.row_box_w - 6
        right = row.value() if row.value else row.right
        if right:
            r = app.text.draw(surf, right, "small", text_color, (right_edge, text_cy), "midright")
            label_end = r.left - 6
        elif selected:
            marker = pygame.Rect(266, cy - 8, 18, 18)
            pygame.draw.rect(surf, t.on_fg, marker, 2)
            surf.fill(t.on_fg, (271, cy - 3, 8, 8))
            label_end = marker.left - 8
        else:
            label_end = right_edge

        label_x = 79 if self.has_icons else 3.2 + 5 * app.text.pitch("body")
        count_w = app.text.width(" " + row.count, "small") if row.count else 0
        if selected:
            # Seçili satırda sığmayan yazı kayar
            area = pygame.Rect(round(label_x), cy - 12, round(label_end - label_x - count_w), 24)
            self.animating = marquee.draw(app, surf, row.label, "body", text_color, area,
                                          app.time - self.selected_at, text_cy, raw=row.raw)
            r = pygame.Rect(area.x, 0, min(area.w, app.text.width(row.label, "body", raw=row.raw)), 0)
        else:
            label = app.text.fit(row.label, "body", label_end - label_x - count_w, raw=row.raw)
            r = app.text.draw(surf, label, "body", text_color, (label_x, text_cy), "midleft", raw=True)
        if row.count:
            app.text.draw(surf, row.count, "small", text_color,
                          (r.right + app.text.pitch("small"), text_cy + 2), "midleft")
