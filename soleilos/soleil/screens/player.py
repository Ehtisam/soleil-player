"""Oynatıcı ve şarkı sözü ekranları.

Oynatıcıda tuşlar:
  encoder çevirme : ses
  encoder tıklama : oynat / duraklat
  Sol 1 / Sol 2   : önceki / sonraki şarkı
  Üst 1           : şarkı sözleri
  Üst 2           : beğen
  encoder uzun bas: eylem menüsü (karışık, tekrar, sarma...)
  Sol 3           : geri

Söz ekranında encoder satırlar arasında gezer, tıklama o satıra sarar.
"""

from __future__ import annotations

import random

import pygame

from ..lang import _
from ..input import Action
from ..lyrics import current_line
from ..theme import mix
from ..ui import chrome, glyphs, marquee
from ..ui.listview import draw_back_row
from .base import Screen

HEART = (
    ".##...##.",
    "####.####",
    "#########",
    "#########",
    ".#######.",
    "..#####..",
    "...###...",
    "....#....",
)


SOURCE_NAMES = {"SPOTIFY": "Spotify", "YEREL": "Yerel", "DOSYA": "Medya"}
_cover_cache: dict = {}


def player_title(app) -> str:
    t = app.playback.current
    if not t:
        return "Oynatıcı"
    return f"{SOURCE_NAMES.get(t.source, t.source.title())} / {t.title}"


def draw_cover(app, surf: pygame.Surface, rect: pygame.Rect, track=None) -> None:
    """Albüm kapağı: yerel şarkıda dosyanın içindeki ya da klasördeki resim
    (görsel filtresi açıksa tema renginde). Yoksa müzik simgeli boş kare.
    Spotify kapakları bağlantı yapılınca buraya gelecek."""
    t = app.theme
    image = app.covers.get(track) if track is not None else None
    if image is None:
        pygame.draw.rect(surf, t.rule_dim, rect, 2)
        app.icons.draw(surf, "music", t.rule_dim, rect.center, "center")
        return
    tinted = app.settings.image_tint
    key = (track.path, rect.size, tinted, t.name)
    if key not in _cover_cache:
        if len(_cover_cache) > 24:
            _cover_cache.clear()
        scaled = pygame.transform.smoothscale(image, rect.size)
        if tinted:
            from .gallery import tint
            scaled = tint(scaled, t.bg, t.fg)
        _cover_cache[key] = scaled
    surf.blit(_cover_cache[key], rect)
    pygame.draw.rect(surf, t.rule_dim, rect, 1)


def mmss(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 60:02d}:{s % 60:02d}"


REPEAT_NAMES = {"off": "KAPALI", "all": "TÜMÜ", "one": "TEK ŞARKI"}


# -- oynatma komutları: her biri kısa bir bildirim de gösterir ---------------

def toggle_play(app) -> None:
    app.playback.toggle()
    app.toast("OYNATILIYOR" if app.playback.playing else "DURAKLATILDI")


def skip(app, forward: bool) -> None:
    p = app.playback
    p.next() if forward else p.previous()
    app.toast("SONRAKİ" if forward else "ÖNCEKİ", p.current.title if p.current else "")


def seek_by(app, seconds: float) -> None:
    p = app.playback
    if p.live:
        app.toast("CANLI YAYIN", "SARILAMAZ")
    elif p.current:
        p.seek(p.position + seconds)
        sign = "+" if seconds > 0 else "-"
        app.toast(sign + _("{n} SN").format(n=abs(int(seconds))), mmss(p.position), bar=p.position / p.current.duration)


def is_liked(app, track) -> bool:
    """Radyoda beğeni = favori istasyon (kalıcı); diğerlerinde beğeni."""
    if track is None:
        return False
    return app.radio.is_favorite(track) if track.live else app.likes.has(track)


def toggle_like(app) -> None:
    p = app.playback
    if not p.current:
        return
    if p.live:
        added = app.radio.toggle_favorite(p.current)
        app.toast("FAVORİLERE EKLENDİ" if added else "FAVORİLERDEN ÇIKTI", p.current.title)
        return
    liked = app.likes.toggle(p.current)
    app.toast("BEĞENİLDİ" if liked else "BEĞENİ KALDIRILDI", p.current.title)


def toggle_shuffle(app) -> None:
    app.playback.shuffle = not app.playback.shuffle
    app.toast("KARIŞIK: " + ("AÇIK" if app.playback.shuffle else "KAPALI"))


def cycle_repeat(app) -> None:
    app.playback.cycle_repeat()
    app.toast("TEKRAR: " + REPEAT_NAMES[app.playback.repeat])


def change_volume(app, step: int) -> None:
    s = app.status
    s.volume = max(0, min(100, s.volume + step))
    app.toast("SES", f"[{s.volume}]", bar=s.volume / 100, seconds=0.9)


class PlayerControls:
    """Oynatıcı ve söz ekranında ortak tuşlar."""

    def handle_playback(self, action: Action) -> bool:
        app = self.app
        if action is Action.SELECT:
            toggle_play(app)
        elif action is Action.LEFT1:
            skip(app, forward=False)
        elif action is Action.LEFT2:
            skip(app, forward=True)
        elif action is Action.TOP2:
            toggle_like(app)
        elif action is Action.HOLD:
            from .action_menu import PlayerActionMenu
            app.push(PlayerActionMenu(app))
        else:
            return False
        return True


class PlayerScreen(PlayerControls, Screen):
    animating = True

    EQ_BARS = 12

    def __init__(self, app) -> None:
        super().__init__(app)
        self.time = 0.0
        self._track, self._track_since = None, 0.0
        self._line, self._line_since = None, 0.0
        self.eq = [0.0] * self.EQ_BARS
        self.eq_target = [0.0] * self.EQ_BARS
        self.eq_timer = 0.0

    @property
    def title(self) -> str:
        return player_title(self.app)

    def handle(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            change_volume(self.app, 5 if action is Action.UP else -5)
        elif action is Action.TOP1:
            if self.app.playback.live:
                self.app.toast("CANLI YAYIN", "SÖZ YOK")
            else:
                self.app.push(LyricsScreen(self.app))
        elif not self.handle_playback(action):
            super().handle(action)

    def update(self, dt: float) -> None:
        self.time += dt
        self.eq_timer -= dt
        playing = self.app.playback.playing
        if self.eq_timer <= 0:
            self.eq_timer = 0.12
            for i in range(self.EQ_BARS):
                # Sahte spektrum: ortadaki bantlar biraz daha yüksek
                base = 0.75 - abs(i - self.EQ_BARS / 2) / self.EQ_BARS * 0.6
                self.eq_target[i] = max(0.08, min(1.0, base + random.uniform(-0.35, 0.3))) if playing else 0.04
        for i in range(self.EQ_BARS):
            speed = 10 if self.eq_target[i] > self.eq[i] else 4
            self.eq[i] += (self.eq_target[i] - self.eq[i]) * min(1.0, dt * speed)

    # -- çizim ---------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L, p = self.app, self.app.theme, self.app.layout, self.app.playback
        track = p.current
        chrome.draw_header(app, surf, self.title)
        if not track:
            chrome.draw_footer(app, surf, controls=True)
            return

        top = L.header_rule2_y + 10
        cover = pygame.Rect(L.left + 4, top, 124, 124)
        draw_cover(app, surf, cover, track)

        # Sağ sütun: sıra, beğeni, ad, albüm, sanatçı, kayan söz
        x0, x1 = cover.right + 10, L.left + L.row_box_w + 9
        y = top + 10
        app.text.draw(surf, f"[{p.index + 1:02d}/{len(p.queue):02d}]", "medium", t.fg, (x0, y), "midleft")
        br = app.text.draw(surf, "]", "medium", t.fg, (x1, y), "midright")
        bl = app.text.draw(surf, "[", "medium", t.fg, (br.left - 14, y), "midright")
        chrome.draw_bitmap(surf, HEART, t.fg, ((bl.right + br.left) // 2 + 1, y + 1), outline=not is_liked(app, track))
        surf.fill(t.fg, (x0, y + 13, x1 - x0, 1))

        # Sığmayan ad, albüm ve sanatçı kayar; şarkı değişince baştan başlar
        if track is not self._track:
            self._track, self._track_since = track, self.time
        since = self.time - self._track_since
        y += 30
        marquee.draw(app, surf, track.title, "body", t.fg, pygame.Rect(x0, y - 12, x1 - x0, 24), since, y, raw=True)
        tree_x = x0 + 5
        surf.fill(t.rule, (tree_x, y + 11, 1, 31))
        # Radyoda: tür ve ülke; çalan şarkı aşağıdaki kayan kutuda
        lines = ("İnternet Radyosu", track.album) if track.live else (track.album, track.artist)
        for i, line in enumerate(lines):
            ly = y + 21 + i * 20
            surf.fill(t.rule, (tree_x, ly, 7, 1))
            area = pygame.Rect(tree_x + 11, ly - 10, x1 - tree_x - 11, 20)
            marquee.draw(app, surf, line, "medium", t.fg, area, since, ly - 1, raw=True)

        self._draw_marquee(surf, pygame.Rect(x0, cover.bottom - 24, x1 - x0, 24))

        # İlerleme
        y = cover.bottom + 14
        surf.fill(t.rule, (L.left, y, L.row_box_w + 9, 1))
        y += 22
        if track.live:
            self._draw_live(surf, y, x1)
        else:
            lt = app.text.draw(surf, mmss(p.position), "medium", t.fg, (L.left + 4, y), "midleft")
            rt = app.text.draw(surf, mmss(track.duration), "medium", t.fg, (x1, y), "midright")
            bl = app.text.draw(surf, "[", "medium", t.fg, (lt.right + 4, y), "midleft")
            br = app.text.draw(surf, "]", "medium", t.fg, (rt.left - 4, y), "midright")
            self._draw_progress(surf, pygame.Rect(bl.right, y - 5, br.left - bl.right, 10),
                                p.position / track.duration)

        # Ekolayzır
        self._draw_eq(surf, pygame.Rect(L.left + 8, y + 24, L.row_box_w - 6, 96))

        # Kaynak ve kalite
        y += 140
        app.text.draw(surf, f"[SRC: {p.source}]", "medium", t.fg, (L.left + 4, y), "midleft")
        app.text.draw(surf, f"[QUAL: {p.quality}]", "medium", t.fg, (x1, y), "midright")
        if track.live:
            hints = [(Action.TOP2, "FAVORİ"), (Action.HOLD, "MENÜ")]
        else:
            hints = [(Action.TOP1, "SÖZLER"), (Action.TOP2, "BEĞEN"), (Action.HOLD, "MENÜ")]
        glyphs.draw_hints(app, surf, hints,
                          t.rule, (L.width // 2, y + 28), "center")

        chrome.draw_footer(app, surf, controls=True)

    def _draw_live(self, surf: pygame.Surface, y: int, x1: int) -> None:
        """Canlı yayında ilerleme çubuğu yerine: CANLI işareti ve dinleme süresi."""
        app, t, L, p = self.app, self.app.theme, self.app.layout, self.app.playback
        on = p.playing and int(self.time * 1.5) % 2 == 0
        dot = pygame.Rect(L.left + 6, y - 4, 8, 8)
        if on:
            surf.fill(t.fg, dot)
        else:
            pygame.draw.rect(surf, t.fg, dot, 1)
        label = app.text.draw(surf, "CANLI" if p.playing else "DURDU", "medium", t.fg,
                              (dot.right + 8, y), "midleft")
        rt = app.text.draw(surf, mmss(p.position), "medium", t.rule, (x1, y), "midright")
        # Ortada yavaşça akan kesik çizgi: yayın sürüyor
        bar = pygame.Rect(label.right + 12, y - 1, rt.left - label.right - 24, 3)
        shift = int(self.time * 12) % 8 if p.playing else 0
        for x in range(bar.x - 8 + shift, bar.right, 8):
            surf.fill(t.rule, pygame.Rect(x, bar.y, 4, bar.h).clip(bar))

    def _draw_marquee(self, surf: pygame.Surface, box: pygame.Rect) -> None:
        """Köşeli kutu içinde o anki söz satırı; sığmazsa kayar."""
        app, t, p = self.app, self.app.theme, self.app.playback
        for x in (box.left, box.right - 1):
            surf.fill(t.fg, (x, box.top, 1, 4))
            surf.fill(t.fg, (x, box.bottom - 4, 1, 4))
        surf.fill(t.fg, (box.left, box.top, box.w, 1))
        surf.fill(t.fg, (box.left, box.bottom - 1, box.w, 1))

        state, lyrics = app.lyrics.get(p.current)
        index = current_line(lyrics, p.position)
        if p.live:
            line = f"♪ {p.now_playing}" if p.now_playing else "canlı yayın"
        elif state == "loading":
            line = "söz aranıyor..."
        elif not lyrics or lyrics.instrumental:
            line = "♪ enstrümantal" if lyrics else "söz bulunamadı"
        elif index < 0:
            line = "♪" if lyrics.synced else lyrics.lines[0][1]
        else:
            line = lyrics.lines[index][1] or "♪"
        if line != self._line:
            self._line, self._line_since = line, self.time
        inner = box.inflate(-8, -4)
        marquee.draw(app, surf, line, "medium", t.fg, inner, self.time - self._line_since, inner.centery - 1, raw=True)

    def _draw_progress(self, surf: pygame.Surface, bar: pygame.Rect, frac: float) -> None:
        t = self.app.theme
        filled = round(bar.w * max(0.0, min(1.0, frac)))
        # Kalan kısım noktalı doku (bir kez çizilip saklanıyor)
        key = (bar.size, t.rule)
        if getattr(self, "_dots_key", None) != key:
            self._dots_key = key
            self._dots = pygame.Surface(bar.size, pygame.SRCALPHA)
            for yy in range(bar.h):
                for xx in range(yy % 2, bar.w, 2):
                    self._dots.set_at((xx, yy), t.rule)
        rest = pygame.Rect(filled + 1, 0, max(0, bar.w - filled - 1), bar.h)
        surf.blit(self._dots, (bar.x + rest.x, bar.y), rest)
        surf.fill(t.fg, (bar.x, bar.y, filled, bar.h))

    def _draw_eq(self, surf: pygame.Surface, area: pygame.Rect) -> None:
        """Bölmeli çubuklar: her bölme 4 px (3 dolu + 1 boşluk)."""
        t = self.app.theme
        n = self.EQ_BARS
        gap = 6
        bw = (area.w - gap * (n - 1)) // n
        x = area.x + (area.w - (bw * n + gap * (n - 1))) // 2
        for value in self.eq:
            segments = max(1, round(value * area.h / 4))
            for s in range(segments):
                surf.fill(t.fg, (x, area.bottom - (s + 1) * 4 + 1, bw, 3))
            x += bw + gap


class LyricsScreen(PlayerControls, Screen):
    """Şarkı sözleri.

    - Üstte şarkı adı, sanatçı, süre, sözlerin kaynağı ve ince bir ilerleme çizgisi
    - Solda her satırın zamanı, sağında söz; uzun satırlar alt satıra kayar
    - Okunan satır kutu içinde ortada, diğerleri uzaklaştıkça soluklaşır
    - Encoder ile elle gezilebilir; 4 saniye dokunulmazsa şarkıyı tekrar takip eder
    - Bir satıra tıklamak şarkıyı o satıra sarar; okunan satıra tıklamak duraklatır
    - Zamansız sözlerde (sadece metin) satırlar elle kaydırılır
    """

    animating = True
    ROW_H = 20           # sarılan satırların aralığı
    GAP = 8              # sözler arası boşluk
    FOLLOW_DELAY = 4.0
    GUTTER = 50          # zaman sütununun genişliği

    def __init__(self, app) -> None:
        super().__init__(app)
        self.cursor = 1              # 0 = Oynatıcı'ya dön satırı, 1.. = sözler
        self.manual = 0.0
        self.offset = None           # yumuşak kaydırma; ilk çizimde yerine oturur
        self._layout_key = None
        self._layout: list[tuple[int, list[str]]] = []   # (y, satırlar) her söz için

    @property
    def title(self) -> str:
        return player_title(self.app)

    def _lyrics(self):
        return self.app.lyrics.get(self.app.playback.current)

    def _build_layout(self, lyrics, width: int) -> None:
        key = (id(lyrics), width)
        if key == self._layout_key:
            return
        self._layout_key = key
        max_chars = max(8, int(width // self.app.text.pitch("medium")))
        y, layout = 0, []
        for _, text in lyrics.lines:
            rows = _wrap(text or "♪", max_chars)
            layout.append((y, rows))
            y += len(rows) * self.ROW_H + self.GAP
        self._layout = layout

    def handle(self, action: Action) -> None:
        p = self.app.playback
        _, lyrics = self._lyrics()
        count = len(lyrics.lines) if lyrics else 0
        if action in (Action.UP, Action.DOWN):
            step = 1 if action is Action.DOWN else -1
            self.cursor = max(0, min(count, self.cursor + step))
            self.manual = self.FOLLOW_DELAY
        elif action is Action.SELECT:
            if self.cursor == 0:
                self.app.pop()
            elif lyrics and lyrics.synced:
                index = self.cursor - 1
                if index == current_line(lyrics, p.position):
                    toggle_play(self.app)
                else:
                    p.seek(lyrics.lines[index][0])
                    self.manual = 0.0
            else:
                toggle_play(self.app)
        elif action is Action.TOP1:
            self.app.pop()
        elif not self.handle_playback(action):
            super().handle(action)

    def update(self, dt: float) -> None:
        _, lyrics = self._lyrics()
        if self.manual > 0:
            self.manual -= dt
        elif lyrics and lyrics.synced:
            self.cursor = max(1, current_line(lyrics, self.app.playback.position) + 1)
        if self._layout and self.cursor > 0:
            target = self._layout[min(self.cursor, len(self._layout)) - 1][0]
            if self.offset is None:
                self.offset = float(target)
            self.offset += (target - self.offset) * min(1.0, dt * 10)

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L, p = self.app, self.app.theme, self.app.layout, self.app.playback
        track = p.current
        chrome.draw_header(app, surf, self.title)
        draw_back_row(app, surf, L.row_cy(0), self.cursor == 0, "Oynatıcı")
        if not track:
            chrome.draw_footer(app, surf, controls=True)
            return
        state, lyrics = self._lyrics()

        # Şarkı bilgisi, kaynak ve ince ilerleme çizgisi
        right = L.left + L.row_box_w + 9
        y = L.row_cy(0) + 30
        times = "CANLI" if track.live else f"{mmss(p.position)}/{mmss(track.duration)}"
        tr = app.text.draw(surf, times, "small", t.fg, (right, y), "midright")
        info = f"{track.title} - {track.artist}"
        if lyrics:
            info = f"[{lyrics.source}] {info}"
        info = app.text.fit(info, "small", tr.left - 10 - (L.left + 4))
        app.text.draw(surf, info, "small", t.rule, (L.left + 4, y), "midleft")
        y += 12
        width = right - L.left
        surf.fill(t.rule_dim, (L.left, y, width, 2))
        surf.fill(t.fg, (L.left, y, width if track.live else round(width * p.position / track.duration), 2))

        view = pygame.Rect(L.left, y + 8, width, L.footer_line_y - 8 - (y + 8))
        message = None
        if state == "loading":
            message = "[ SÖZLER ARANIYOR ]"
        elif not lyrics:
            message = "[ SÖZ BULUNAMADI ]"
        elif lyrics.instrumental or not lyrics.lines:
            message = "[ ENSTRÜMANTAL ]"
        if message:
            app.text.draw(surf, message, "body", t.rule, view.center, "center")
            chrome.draw_footer(app, surf, controls=True)
            return

        gutter_x = view.x + (self.GUTTER if lyrics.synced else 0)
        text_x = gutter_x + 12
        self._build_layout(lyrics, view.right - text_x - 8)
        if self.offset is None:
            self.update(0)
        offset = self.offset or 0
        center = view.y + view.h // 2 - self.ROW_H // 2
        if lyrics.synced:
            surf.fill(t.rule_dim, (gutter_x, view.y, 1, view.h))

        old = surf.get_clip()
        surf.set_clip(view)
        playing = current_line(lyrics, p.position)
        current = self.cursor - 1
        for i, ((start, _), (ly, rows)) in enumerate(zip(lyrics.lines, self._layout)):
            top = round(center + ly - offset)
            height = len(rows) * self.ROW_H
            if top + height < view.top or top > view.bottom:
                continue
            first_cy = top + self.ROW_H // 2
            if lyrics.synced:
                time_color = t.fg if i == playing else t.rule_dim
                app.text.draw(surf, mmss(start), "small", time_color, (view.x + 4, first_cy), "midleft")
                if i == playing:
                    surf.fill(t.fg, (gutter_x - 3, first_cy - 3, 3, 7))

            if i == current and self.cursor > 0:
                w = max(app.text.width(r, "medium") for r in rows) + 14
                surf.fill(t.fg, (text_x - 7, top - 2, w, height + 4))
                color = t.on_fg
            elif i == playing:
                color = t.fg
            else:
                color = mix(t.fg, t.rule_dim, min(1.0, abs(i - max(current, 0)) / 4))
            for r, row in enumerate(rows):
                app.text.draw(surf, row, "medium", color, (text_x, first_cy + r * self.ROW_H - 1), "midleft", raw=True)
        surf.set_clip(old)

        chrome.draw_footer(app, surf, controls=True)


def _wrap(text: str, max_chars: int) -> list[str]:
    rows, row = [], ""
    for word in text.split():
        trial = f"{row} {word}".strip()
        if len(trial) <= max_chars:
            row = trial
        else:
            if row:
                rows.append(row)
            while len(word) > max_chars:
                rows.append(word[:max_chars])
                word = word[max_chars:]
            row = word
    return rows + [row] if row else rows or [""]
