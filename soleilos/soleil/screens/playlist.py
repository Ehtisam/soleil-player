"""Playlist ekranı: kapak, ad, açıklama ve şarkı listesi.

Üstte sabit bir GERİ satırı, altında kayan içerik. Aşağı inildikçe kapak
ve açıklama yukarı kayıp kaybolur, şarkılar ekranı doldurur.
"""

from __future__ import annotations

import pygame

from ..input import Action
from ..sample_data import Playlist
from ..ui import chrome, marquee
from ..ui.listview import draw_back_row
from .base import Screen
from .player import PlayerScreen, draw_cover

TRACK_H = 22
COVER = 88


class PlaylistScreen(Screen):
    def __init__(self, app, playlist: Playlist, title: str) -> None:
        super().__init__(app)
        self.playlist = playlist
        self.title = title
        self.selected = 1          # 0 = GERİ, 1.. = şarkılar
        self.scroll = 0
        self.selected_at = app.time
        self.animating = False     # seçili şarkının adı sığmıyorsa kayar
        desc_lines = self._wrap(playlist.description)
        self.desc = desc_lines[:2]
        self.head_h = 4 + COVER + 12 + 24 + 6 + len(self.desc) * 16 + 10

    # -- yerleşim ------------------------------------------------------------

    @property
    def view(self) -> pygame.Rect:
        L = self.app.layout
        top = L.row_cy(0) + 24
        bottom = L.chevron_cy - 16   # aşağı oka yer bırak
        return pygame.Rect(L.left, top, L.row_box_w, bottom - top)

    def _wrap(self, text: str) -> list[str]:
        max_chars = int(self.app.layout.row_box_w // self.app.text.pitch("small"))
        lines, line = [], ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if len(trial) <= max_chars:
                line = trial
            else:
                lines.append(line)
                line = word
        return lines + [line] if line else lines

    def _track_y(self, i: int) -> int:
        return self.head_h + i * TRACK_H

    def _keep_visible(self) -> None:
        if self.selected <= 1:
            self.scroll = 0
            return
        y = self._track_y(self.selected - 1)
        h = self.view.height
        self.scroll = min(max(self.scroll, y + TRACK_H - h), y)
        content_h = self._track_y(len(self.playlist.tracks))
        self.scroll = max(0, min(self.scroll, content_h - h))

    # -- girdi ---------------------------------------------------------------

    def handle(self, action: Action) -> None:
        n = len(self.playlist.tracks) + 1
        if action in (Action.UP, Action.DOWN):
            self.selected = (self.selected + (1 if action is Action.DOWN else -1)) % n
            self.selected_at = self.app.time
            self._keep_visible()
        elif action is Action.SELECT:
            if self.selected == 0:
                self.app.pop()
            else:
                self.app.playback.play_queue(list(self.playlist.tracks), self.selected - 1)
                self.app.push(PlayerScreen(self.app))
        else:
            super().handle(action)

    # -- çizim ---------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        chrome.draw_header(app, surf, self.title)
        draw_back_row(app, surf, L.row_cy(0), self.selected == 0)

        view = self.view
        old_clip = surf.get_clip()
        surf.set_clip(view)
        y0 = view.y - self.scroll

        # Kapak, ad, açıklama
        cover = pygame.Rect(0, y0 + 4, COVER, COVER)
        cover.centerx = view.centerx
        draw_cover(app, surf, cover, self.playlist.tracks[0] if self.playlist.tracks else None)
        y = cover.bottom + 12
        surf.fill(t.rule, (view.x, y, view.w, 1))
        app.text.draw(surf, self.playlist.name, "medium", t.fg, (view.x + 2, y + 12), "midleft", raw=True)
        y += 24
        surf.fill(t.rule, (view.x, y, view.w, 1))
        y += 6
        for line in self.desc:
            app.text.draw(surf, line, "small", t.rule, (view.x + 2, y))
            y += 16

        # Şarkılar
        self.animating = False
        playing = app.playback.current
        for i, track in enumerate(self.playlist.tracks):
            ty = y0 + self._track_y(i)
            if ty + TRACK_H < view.y or ty > view.bottom:
                continue
            selected = self.selected == i + 1
            color = t.on_fg if selected else t.fg
            box = pygame.Rect(view.x, ty + 1, view.w, TRACK_H - 2)
            label_w = box.w - 8
            if selected:
                surf.fill(t.fg, box)
                marker = pygame.Rect(box.right - 16, box.centery - 6, 12, 12)
                pygame.draw.rect(surf, t.on_fg, marker, 1)
                surf.fill(t.on_fg, marker.inflate(-6, -6))
                label_w -= 20
            mark = "»" if track == playing and app.playback.playing else ""
            label = f"[{i + 1:02d}]{mark}{track.title} - {track.artist}"
            if selected:
                area = pygame.Rect(box.x + 2, box.y, label_w, box.h).clip(view)
                self.animating = marquee.draw(app, surf, label, "track", color, area,
                                              app.time - self.selected_at, box.centery - 1, raw=True)
            else:
                label = app.text.fit(label, "track", label_w, raw=True)
                app.text.draw(surf, label, "track", color, (box.x + 2, box.centery - 1), "midleft", raw=True)

        surf.set_clip(old_clip)

        # Kaydırma çubuğu: tutamak seçili satırın hizasında
        if self.selected == 0:
            thumb = L.row_cy(0)
        else:
            thumb = y0 + self._track_y(self.selected - 1) + TRACK_H // 2
        chrome.draw_scrollbar(app, surf, thumb)
        if self.scroll + view.height < self._track_y(len(self.playlist.tracks)):
            chrome.draw_chevron(app, surf)
        chrome.draw_footer(app, surf)
