from __future__ import annotations

import pygame

from ..ui.listview import ListScreen


class Placeholder(ListScreen):
    """Henüz yapılmamış bölümler için: sadece seçili bir GERİ satırı."""

    def __init__(self, app, title: str) -> None:
        super().__init__(app, [])
        self.title = title

    def draw(self, surf: pygame.Surface) -> None:
        super().draw(surf)
        L = self.app.layout
        mid = (L.width / 2, (L.header_rule2_y + L.footer_line_y) / 2)
        self.app.text.draw(surf, "[ HAZIRLANIYOR ]", "body", self.app.theme.rule, mid, "center")
