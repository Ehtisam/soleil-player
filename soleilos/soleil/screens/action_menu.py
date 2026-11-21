"""Encoder'a uzun basınca açılan eylem menüsü (oynatıcıda, okuyucuda).

Arkadaki ekran (oynatıcı ya da sözler) soluklaşmış halde çalışmaya devam
eder. Encoder ile gezilir, tıklayınca uygulanır; uzun basma ya da Sol 3
menüyü kapatır. Açık/kapalı ayarlar menü açıkken değiştirilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pygame

from ..input import Action
from ..ui import chrome, glyphs
from . import player
from .base import Screen


@dataclass
class MenuItem:
    label: str
    run: Callable[[], None]
    value: Optional[str] = None
    closes: bool = False


class OverlayMenu(Screen):
    """Arkadaki ekranın üstünde açılan menü. Alt sınıflar _items() verir."""
    animating = True
    ROW_H = 26
    WIDTH = 252

    def __init__(self, app) -> None:
        super().__init__(app)
        self.under = app.screen
        self.selected = 0

    @property
    def title(self) -> str:
        return self.under.title

    def _items(self) -> list[MenuItem]:
        return []

    def handle(self, action: Action) -> None:
        items = self._items()
        if action in (Action.UP, Action.DOWN):
            step = 1 if action is Action.DOWN else -1
            self.selected = (self.selected + step) % len(items)
        elif action is Action.SELECT:
            item = items[self.selected]
            if item.closes:
                self.app.pop()
            item.run()
            if not item.closes:
                self.app.toast_info = None   # değer menüde zaten görünüyor
        elif action in (Action.HOLD, Action.BACK):
            self.app.pop()

    def update(self, dt: float) -> None:
        self.under.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        self.under.draw(surf)

        # Arkayı soluklaştır
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((*t.bg, 190))
        surf.blit(shade, (0, 0))

        items = self._items()
        box = pygame.Rect(0, 0, self.WIDTH, 34 + len(items) * self.ROW_H + 6)
        box.center = (L.width // 2, (L.header_rule2_y + L.footer_line_y) // 2)
        chrome.draw_panel(app, surf, box)

        title = pygame.Rect(box.x + 4, box.y + 4, box.w - 8, 22)
        surf.fill(t.fg, title)
        app.text.draw(surf, "EYLEMLER", "medium", t.panel, (title.x + 6, title.centery), "midleft")
        glyphs.draw_hints(app, surf, [(Action.HOLD, "KAPAT")], t.panel, (title.right - 6, title.centery), "midright")

        y = title.bottom + 6
        for i, item in enumerate(items):
            row = pygame.Rect(box.x + 4, y, box.w - 8, self.ROW_H - 2)
            selected = i == self.selected
            color = t.on_fg if selected else t.fg
            if selected:
                surf.fill(t.fg, row)
            app.text.draw(surf, item.label, "medium", color, (row.x + 8, row.centery - 1), "midleft")
            if item.value:
                app.text.draw(surf, f"[{item.value}]", "small", color,
                              (row.right - 8, row.centery - 1), "midright")
            y += self.ROW_H


class PlayerActionMenu(OverlayMenu):
    def _items(self) -> list[MenuItem]:
        app, p = self.app, self.app.playback
        in_lyrics = isinstance(self.under, player.LyricsScreen)
        liked = player.is_liked(app, p.current)
        if p.live:
            return [
                MenuItem("DURAKLAT" if p.playing else "OYNAT", lambda: player.toggle_play(app)),
                MenuItem("SONRAKİ İSTASYON", lambda: player.skip(app, True)),
                MenuItem("ÖNCEKİ İSTASYON", lambda: player.skip(app, False)),
                MenuItem("FAVORİ", lambda: player.toggle_like(app), "EVET" if liked else "HAYIR"),
                MenuItem("KAPAT", lambda: None, closes=True),
            ]
        return [
            MenuItem("DURAKLAT" if p.playing else "OYNAT", lambda: player.toggle_play(app)),
            MenuItem("10 SN İLERİ", lambda: player.seek_by(app, 10)),
            MenuItem("10 SN GERİ", lambda: player.seek_by(app, -10)),
            MenuItem("KARIŞIK", lambda: player.toggle_shuffle(app), "AÇIK" if p.shuffle else "KAPALI"),
            MenuItem("TEKRAR", lambda: player.cycle_repeat(app), player.REPEAT_NAMES[p.repeat]),
            MenuItem("BEĞEN", lambda: player.toggle_like(app), "EVET" if liked else "HAYIR"),
            MenuItem("OYNATICI" if in_lyrics else "SÖZLER", self._switch_view, closes=True),
            MenuItem("KAPAT", lambda: None, closes=True),
        ]

    def _switch_view(self) -> None:
        if isinstance(self.under, player.LyricsScreen):
            self.app.pop()                                    # sözlerden oynatıcıya
        else:
            self.app.push(player.LyricsScreen(self.app))
