"""Müzik / Yerel / Ara: yazdıkça gelen sonuçlar (yeni Figma'daki Spotify / Arama).

Üstte "Arama: Peyk_", ortada sonuçlar ([Sanatçı], [Albüm], [Parça]), altta
tek satırlık harf şeridi: seçili harf köşeli parantez içinde. Şimdilik yerel
kütüphanede arıyor; Spotify bağlanınca aynı ekran kullanılacak.

Tuşlar (yazarken):
  encoder çevirme : harf seç
  encoder tıklama : harfi yaz
  S (Sol 1)       : sil
  O (Sol 2)       : boşluk
  İ (Üst 2)       : sonuçlara geç
  L (Sol 3)       : geri
Sonuçlardayken encoder seçer, tıklama açar (sanatçı / albüm) ya da çalar
(parça); İ ya da L yazmaya döner.

Arama büyük/küçük harfe ve Türkçe harflere duyarsız: "sulusaka" ile
"Suluşaka" bulunur.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pygame

from ..lang import N_, _
from ..input import Action
from ..library import Album
from ..playback import Track
from ..theme import mix
from ..ui import chrome, dial, glyphs
from .base import Screen
from .local_music import TITLE as LOCAL_TITLE, album_screen, artist_screen
from .notebook import LOWER, UPPER
from .player import PlayerScreen

TITLE = f"{LOCAL_TITLE} / Ara"
LETTERS = list(UPPER) + list("0123456789")
MAX_LEN = 24
MAX_RESULTS = 100
ROW_H = 25

_PLAIN = str.maketrans("çğıöşüâîû", "cgiosuaiu")


def normalize(text: str) -> str:
    """Karşılaştırma için: Türkçe küçük harf, aksansız."""
    return text.replace("İ", "i").replace("I", "ı").lower().translate(_PLAIN)


@dataclass
class Result:
    kind: str                        # "Sanatçı", "Albüm", "Parça"
    label: str
    artist: Optional[str] = None     # Sanatçı: adı
    albums: tuple = ()               # Sanatçı: albümleri
    album: Optional[Album] = None
    track: Optional[Track] = None


def search_library(lib, query: str) -> list[Result]:
    """Sanatçılar, albümler, sonra parçalar. Her grupta adı aramayla
    başlayanlar öne gelir. Parça hem adından hem sanatçısından bulunur."""
    q = normalize(query.strip())
    if not q:
        return []

    def ranked(items, key):
        hits = [(normalize(key(x)).find(q), i, x) for i, x in enumerate(items)]
        return [x for pos, i, x in sorted((h for h in hits if h[0] >= 0),
                                          key=lambda h: (h[0] != 0, h[1]))]

    results = [Result(N_("Sanatçı"), name, artist=name, albums=tuple(albums))
               for name, albums in ranked(list(lib.artists.items()), lambda kv: kv[0])]
    results += [Result(N_("Albüm"), f"{a.name} - {a.artist}", album=a)
                for a in ranked(lib.albums, lambda a: a.name)]
    results += [Result(N_("Parça"), f"{t.title} - {t.artist}", track=t)
                for t in ranked(lib.tracks, lambda t: f"{t.title} {t.artist}")]
    return results[:MAX_RESULTS]


class SearchScreen(Screen):
    title = TITLE

    def __init__(self, app) -> None:
        super().__init__(app)
        app.library.ensure_scanned()
        self.query = ""
        self.results: list[Result] = []
        self.dial = dial.Dial(0)
        self.in_results = False       # False: yazıyor, True: sonuçlarda geziyor
        self.selected = 0
        self.first = 0
        self._version = -1
        self._blink = 0
        self.animating = False

    # -- arama -----------------------------------------------------------------

    def _refresh(self) -> None:
        self.results = search_library(self.app.library, self.query)
        self._version = self.app.library.version
        self.selected = self.first = 0
        if not self.results:
            self.in_results = False

    def insert(self, ch: str) -> None:
        if len(self.query) >= MAX_LEN:
            return
        # Kelime başı büyük, gerisi küçük: "Peyk"
        if ch in UPPER and self.query and not self.query.endswith(" "):
            ch = LOWER[UPPER.index(ch)]
        self.query += ch
        self._refresh()

    def backspace(self) -> None:
        if self.query:
            self.query = self.query[:-1]
            self._refresh()

    # -- girdi -----------------------------------------------------------------

    def handle(self, action: Action) -> None:
        if self.in_results:
            if action in (Action.UP, Action.DOWN):
                step = -1 if action is Action.UP else 1
                self.selected = (self.selected + step) % len(self.results)
            elif action is Action.SELECT:
                self.open(self.results[self.selected])
            elif action in (Action.TOP2, Action.BACK):
                self.in_results = False
            else:
                super().handle(action)
            return
        if action in (Action.UP, Action.DOWN):
            self.dial.turn(-1 if action is Action.UP else 1)
        elif action is Action.SELECT:
            self.insert(LETTERS[self.dial.index(len(LETTERS))])
        elif action is Action.LEFT1:
            self.backspace()
        elif action is Action.LEFT2:
            if self.query and not self.query.endswith(" "):
                self.insert(" ")
        elif action is Action.TOP2:
            if self.results:
                self.in_results = True
            elif self.query:
                self.app.toast("SONUÇ YOK")
        else:
            super().handle(action)

    def open(self, result: Result) -> None:
        app = self.app
        if result.kind == "Sanatçı":
            app.push(artist_screen(app, result.artist, list(result.albums), TITLE))
        elif result.kind == "Albüm":
            app.push(album_screen(app, result.album, TITLE))
        else:
            # Sonuçlardaki parçalar sırayla çalar
            tracks = [r.track for r in self.results if r.kind == "Parça"]
            app.playback.play_queue(tracks, tracks.index(result.track))
            app.push(PlayerScreen(app))

    def update(self, dt: float) -> None:
        lib = self.app.library
        if lib.version != self._version and lib.state == "ready":
            self._refresh()           # tarama bitti / yenilendi
        moving = self.dial.update(dt)
        self.animating = moving or lib.state == "scanning"
        blink = int(self.app.time * 2.5) % 2
        if blink != self._blink:
            self._blink = blink
            self.app.dirty = True

    # -- çizim -----------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        chrome.draw_header(app, surf, self.title)
        x, right = L.left + 4, L.left + L.row_box_w
        lib = app.library

        # Arama satırı ve sonuç sayısı
        cy = L.row_cy(0) - 4
        r = app.text.draw(surf, _("Arama: {q}").format(q=self.query), "body", t.fg, (x, cy), "midleft")
        if not self.in_results and self._blink == 0:
            surf.fill(t.fg, (r.right + 2, cy + 8, 10, 2))
        if self.query and lib.state == "ready":
            app.text.draw(surf, f"[{len(self.results)}]", "small", t.rule, (right - 2, cy), "midright")
        line_y = cy + 17
        surf.fill(t.fg, (x - 2, line_y, right - x + 4, 2))

        # Altta: ipuçları, çizgi, harf şeridi
        strip_cy = L.footer_line_y - 22
        strip_line = strip_cy - 20
        hints_cy = strip_line - 12
        if self.in_results:
            hints = [(Action.SELECT, "AÇ"), (Action.TOP2, "YAZ")]
        else:
            hints = [(Action.LEFT1, "SİL"), (Action.LEFT2, "BOŞLUK"), (Action.TOP2, "SONUÇLAR")]
        glyphs.draw_hints(app, surf, hints, t.rule, ((x + right) // 2, hints_cy), "center")
        surf.fill(t.fg, (x - 2, strip_line, right - x + 4, 2))
        self._draw_strip(surf, strip_cy)

        # Sonuçlar
        top, bottom = line_y + 8, hints_cy - 14
        visible = max(1, (bottom - top) // ROW_H)
        if lib.state != "ready":
            app.text.draw(surf, _("TARANIYOR %{n}").format(n=round(lib.progress * 100)), "medium", t.rule,
                          ((x + right) // 2, top + 40), "center")
        elif self.query and not self.results:
            app.text.draw(surf, "[ SONUÇ YOK ]", "medium", t.rule, ((x + right) // 2, top + 40), "center")
        if self.selected < self.first:
            self.first = self.selected
        elif self.selected >= self.first + visible:
            self.first = self.selected - visible + 1
        for slot, i in enumerate(range(self.first, min(len(self.results), self.first + visible))):
            self._draw_result(surf, i, top + slot * ROW_H + ROW_H // 2, x, right)
        if len(self.results) > visible:
            k = self.selected / max(1, len(self.results) - 1) if self.in_results else \
                self.first / max(1, len(self.results) - visible)
            chrome.draw_scrollbar(app, surf, round(top + 17 + (bottom - top - 34) * k))
        chrome.draw_footer(app, surf)

    def _draw_result(self, surf: pygame.Surface, i: int, cy: int, x: int, right: int) -> None:
        app, t = self.app, self.app.theme
        res = self.results[i]
        selected = self.in_results and i == self.selected
        color = t.on_fg if selected else t.fg
        if selected:
            surf.fill(t.fg, (x - 4, cy - ROW_H // 2 + 1, right - x + 6, ROW_H - 2))
        num = app.text.draw(surf, f"[{i + 1:02d}]", "track", color, (x - 2, cy), "midleft")
        kind = app.text.draw(surf, f"[{res.kind}]", "track", color, (right - 2, cy), "midright")
        label_x = num.right + 7
        label = app.text.fit(res.label, "track", kind.left - 7 - label_x, raw=True)
        app.text.draw(surf, label, "track", color, (label_x, cy), "midleft", raw=True)

    def _draw_strip(self, surf: pygame.Surface, cy: int) -> None:
        """Tek satırlık harf şeridi: ABCÇDEFGHIJ[K]LMNOÖPRSTU. Seçili harf
        ortada köşeli parantez içinde; şerit encoder'la kayar."""
        app, t, L = self.app, self.app.theme, self.app.layout
        pitch = app.text.pitch("body")
        cx = (L.left + L.row_box_w) // 2 + 2
        n = len(LETTERS)
        anim = self.dial.anim
        gap = pitch                        # parantezler için boşluk
        reach = (L.row_box_w / 2) - pitch  # kenarda yarım harf kalmasın
        base = int(anim)
        half = int(reach / pitch) + 2
        for k in range(base - half, base + half + 2):
            d = k - anim
            if abs(d) < 0.5:
                continue
            off = d * pitch + (gap if d > 0 else -gap)
            if abs(off) > reach:
                continue
            # Kenarlara doğru son üç harf soluklaşır
            fade = max(0.0, (abs(off) - (reach - 3 * pitch)) / (3 * pitch))
            app.text.draw(surf, LETTERS[k % n], "body", mix(t.fg, t.bg, fade * 0.8), (cx + off, cy), "center")
        sel = LETTERS[round(anim) % n]
        app.text.draw(surf, f"[{sel}]", "body", t.fg, (cx, cy), "center")
