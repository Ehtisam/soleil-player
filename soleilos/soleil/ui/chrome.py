"""Bütün ekranlarda ortak parçalar: header, alt bar, seçili satır,
kaydırma çubuğu, aşağı ok."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..theme import mix
from . import marquee

if TYPE_CHECKING:
    from ..app import App


# Header'daki bağlantı simgeleri, piksel piksel
WIFI = (
    "...#####...",
    ".##.....##.",
    "#...###...#",
    "..##...##..",
    "....###....",
    ".....#.....",
)
BLUETOOTH = (
    "..#..",
    "..##.",
    "#.#.#",
    ".###.",
    "..#..",
    ".###.",
    "#.#.#",
    "..##.",
    "..#..",
)



def draw_bitmap(surf: pygame.Surface, rows, color, center, outline: bool = False) -> None:
    h, w = len(rows), len(rows[0])
    x0, y0 = center[0] - w // 2, center[1] - h // 2

    def on(x, y):
        return 0 <= y < h and 0 <= x < w and rows[y][x] == "#"

    for y in range(h):
        for x in range(w):
            if not on(x, y):
                continue
            if outline and all(on(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                continue
            surf.fill(color, (x0 + x, y0 + y, 1, 1))



# -- header ------------------------------------------------------------------

def draw_header(app: App, surf: pygame.Surface, title: str) -> None:
    t, L = app.theme, app.layout
    surf.fill(t.fg, (L.left, L.header_line1_y, L.content_w, 1))
    surf.fill(t.fg, (L.left, L.header_bar_y, L.content_w, L.header_bar_h))
    bar_cy = L.header_bar_y + L.header_bar_h / 2

    battery_left = draw_battery(app, surf, L.left + L.content_w - 8, round(bar_cy))
    icons_left = draw_connections(app, surf, battery_left - 8, round(bar_cy))
    title_x = L.left + 4
    title = fit_path(app, title, icons_left - 8 - title_x)
    app.text.draw(surf, title, "medium", t.panel, (title_x, bar_cy), "midleft")

    surf.fill(t.fg, (L.left, L.header_line2_y, L.content_w, 1))
    surf.fill(t.rule_dim, (L.left, L.header_rule_y, L.content_w, 2))
    surf.fill(t.rule_dim_soft, (L.left, L.header_rule2_y - 1, L.content_w, 3))
    surf.fill(t.rule_dim, (L.left, L.header_rule2_y, L.content_w, 1))


BATTERY_SEGMENTS = 4

# Şarj şimşeği, piksel piksel
BOLT = (
    "...##",
    "..##.",
    ".##..",
    "##...",
    "#####",
    "...##",
    "..##.",
    ".##..",
    "##...",
)


def draw_battery(app: App, surf: pygame.Surface, right: int, cy: int) -> int:
    """Header'ın sağındaki pil simgesi: 4 dilim, şarj olurken solunda şimşek.
    Simgenin sol kenarını döndürür."""
    color, s = app.theme.panel, app.status
    if getattr(app, "battery_low", False) and int(app.time * 2) % 2:
        color = app.theme.rule              # pil az: simge yanıp söner
    nub = pygame.Rect(right - 2, cy - 3, 2, 6)
    body = pygame.Rect(0, 0, 27, 14)
    body.midright = (nub.left, cy)
    surf.fill(color, nub)
    pygame.draw.rect(surf, color, body, 1)

    filled = min(BATTERY_SEGMENTS, -(-s.battery * BATTERY_SEGMENTS // 100))  # yukarı yuvarla
    for i in range(filled):
        surf.fill(color, (body.x + 2 + i * 6, body.y + 2, 5, body.h - 4))

    if not s.charging:
        return body.x
    x, y = body.x - 9, cy - len(BOLT) // 2
    for row, line in enumerate(BOLT):
        for col, ch in enumerate(line):
            if ch == "#":
                surf.fill(color, (x + col, y + row, 1, 1))
    return x


def fit_path(app: App, title: str, max_w: float) -> str:
    """Sığmayan yolu baştan kısaltır, en derindeki kısım görünsün:
    "Spotify / Kütüphane / A King never doubts" -> "../Kütüphane / A King never doubts"."""
    if app.text.width(title, "medium") <= max_w:
        return title
    parts = title.split(" / ")
    while len(parts) > 1:
        parts.pop(0)
        short = "../" + " / ".join(parts)
        if app.text.width(short, "medium") <= max_w:
            return short
    return app.text.fit("../" + parts[0], "medium", max_w)


def draw_connections(app: App, surf: pygame.Surface, right: int, cy: int) -> int:
    """Bluetooth ve Wi-Fi simgeleri; kapalıyken soluk. Sol kenarı döndürür."""
    t, s = app.theme, app.status
    off = mix(t.panel, t.fg, 0.65)
    x = right
    for rows, on in ((BLUETOOTH, s.bluetooth), (WIFI, s.wifi)):
        w = len(rows[0])
        draw_bitmap(surf, rows, t.panel if on else off, (x - w // 2 - 1, cy))
        x -= w + 7
    return x + 7


# -- alt bar -------------------------------------------------------------------

REPEAT_ICONS = {"off": "repeat", "all": "repeat_on", "one": "repeat_one_on"}


def draw_footer(app: App, surf: pygame.Surface, controls: bool = False) -> None:
    """Menülerde mini oynatıcı; controls=True ise oynatıcı ekranlarındaki
    hali (ses, karışık / oynat / tekrar)."""
    t, L, s = app.theme, app.layout, app.status
    if not controls:
        return _draw_mini_player(app, surf)
    surf.fill(t.rule, (L.left, L.footer_line_y, L.content_w, 2))
    surf.fill(t.panel, (0, L.footer_y, L.width, L.footer_h))

    cy = L.footer_y + L.footer_h // 2
    text_cy = cy - 1
    app.icons.draw(surf, "volume", t.fg, (15, cy), "center")
    app.text.draw(surf, f"[{s.volume}]", "body", t.fg, (24, text_cy), "midleft")

    _draw_controls(app, surf, cy)


_mini = {"track": None, "since": 0.0}


def _draw_mini_player(app: App, surf: pygame.Surface) -> None:
    """Menülerdeki alt bar: çalan şarkı, ses ve üst kenarında ilerleme çizgisi."""
    t, L, s, p = app.theme, app.layout, app.status, app.playback
    surf.fill(t.panel, (0, L.footer_y, L.width, L.footer_h))
    track = p.current
    # Üst kenar çizgisi aynı zamanda ilerleme çubuğu
    surf.fill(t.rule_dim, (L.left, L.footer_line_y, L.content_w, 2))
    if track:
        done = L.content_w if track.live else round(L.content_w * p.position / track.duration)
        surf.fill(t.fg, (L.left, L.footer_line_y, done, 2))

    y1, y2 = L.footer_y + 21, L.footer_y + 45
    right = L.left + L.content_w + 2
    vol = app.text.draw(surf, f"[{s.volume}]", "medium", t.fg, (right, y2), "midright")
    app.icons.draw(surf, "volume", t.fg, (vol.left - 10, y2 + 1), "center")

    if not track:
        note = app.text.draw(surf, "♪", "body", t.rule, (L.left + 4, y1), "midleft")
        app.text.draw(surf, "ÇALAN YOK", "body", t.rule, (note.right + app.text.pitch("body"), y1), "midleft")
        return

    if track is not _mini["track"]:
        _mini["track"], _mini["since"] = track, app.time
    since = app.time - _mini["since"]
    if p.playing:
        surf.fill(t.fg, (L.left + 4, y1 - 6, 3, 13))
        surf.fill(t.fg, (L.left + 10, y1 - 6, 3, 13))
    else:
        app.icons.draw(surf, "play", t.fg, (L.left + 10, y1 + 1), "center")
    marquee.draw(app, surf, track.title, "body", t.fg,
                 pygame.Rect(L.left + 22, y1 - 12, L.content_w - 24, 24), since, y1 - 1)
    times = "CANLI" if track.live else f"{_mmss(p.position)}/{_mmss(track.duration)}"
    tr = app.text.draw(surf, times, "small", t.rule, (vol.left - 22, y2), "midright")
    second = (p.now_playing or track.album) if track.live else track.artist
    marquee.draw(app, surf, second, "medium", t.rule,
                 pygame.Rect(L.left + 22, y2 - 10, tr.left - 8 - (L.left + 22), 20), since, y2 - 1)


def _mmss(seconds: float) -> str:
    sec = int(seconds)
    return f"{sec // 60:02d}:{sec % 60:02d}"


def _draw_controls(app: App, surf: pygame.Surface, cy: int) -> None:
    t, p = app.theme, app.playback
    # Açık olan karışık/tekrar simgeleri Figma'daki gibi dolu kutu; köşeli
    # parantezlere değmesin diye yuvalar biraz geniş
    mid = app.layout.width // 2
    for cx, kind in ((mid - 43, "shuffle"), (mid, "play"), (mid + 43, "repeat")):
        app.text.draw(surf, "[", "body", t.fg, (cx - 21, cy - 1), "midleft")
        app.text.draw(surf, "]", "body", t.fg, (cx + 21, cy - 1), "midright")
        if kind == "shuffle":
            app.icons.draw(surf, "shuffle_on" if p.shuffle else "shuffle", t.fg, (cx, cy), "center")
        elif kind == "repeat":
            app.icons.draw(surf, REPEAT_ICONS[p.repeat], t.fg, (cx, cy), "center")
        elif p.playing:
            surf.fill(t.fg, (cx - 5, cy - 6, 3, 13))
            surf.fill(t.fg, (cx + 2, cy - 6, 3, 13))
        else:
            app.icons.draw(surf, "play", t.fg, (cx + 1, cy), "center")


# -- seçili satır ------------------------------------------------------------

def draw_selection(app: App, surf: pygame.Surface, cy: int) -> None:
    """Seçili satır kutusu. Üstünde ve altında iki çizgi: içteki ana
    renkte, dıştaki soluk; hafif bir ışıma gibi görünüyor."""
    t, L = app.theme, app.layout
    box = pygame.Rect(L.row_box_x, cy - 17, L.row_box_w, 35)
    for gap, color in ((2, t.fg), (4, t.rule)):
        surf.fill(color, (box.x, box.top - gap - 1, box.w, 1))
        surf.fill(color, (box.x, box.bottom + gap, box.w, 1))
    surf.fill(t.fg, box)


# -- bildirim ve açılır panel ------------------------------------------------

def draw_panel(app: App, surf: pygame.Surface, rect: pygame.Rect) -> None:
    """Ekranın üstünde açılan çerçeveli kutu: içte ana renk, dışta soluk çizgi."""
    t = app.theme
    surf.fill(t.rule, rect.inflate(6, 6))
    surf.fill(t.bg, rect.inflate(4, 4))
    surf.fill(t.fg, rect.inflate(2, 2))
    surf.fill(t.bg, rect.inflate(-2, -2))


def draw_toast(app: App, surf: pygame.Surface, toast) -> None:
    t, L = app.theme, app.layout
    h = 40 + (18 if toast.detail else 0) + (16 if toast.bar is not None else 0)
    box = pygame.Rect(0, 0, 232, h)
    box.center = (L.width // 2, (L.header_rule2_y + L.footer_line_y) // 2)
    draw_panel(app, surf, box)

    y = box.y + 20
    app.text.draw(surf, toast.title, "body", t.fg, (box.centerx, y), "center")
    if toast.detail:
        y += 20
        detail = app.text.fit(toast.detail, "medium", box.w - 20)
        app.text.draw(surf, detail, "medium", t.rule, (box.centerx, y), "center")
    if toast.bar is not None:
        y += 18
        bar = pygame.Rect(box.x + 16, y - 3, box.w - 32, 7)
        pygame.draw.rect(surf, t.rule, bar, 1)
        surf.fill(t.fg, (bar.x, bar.y, round(bar.w * max(0.0, min(1.0, toast.bar))), bar.h))


# -- kaydırma çubuğu ve aşağı ok ---------------------------------------------

def draw_scrollbar(app: App, surf: pygame.Surface, thumb_cy: int) -> None:
    """Figma'da tutamak seçili satırın hizasında duruyor, imleç gibi."""
    t, L = app.theme, app.layout
    surf.fill(t.fg, (302, L.scroll_top, 4, L.scroll_bottom - L.scroll_top + 1))
    cy = max(L.scroll_top + 17, min(L.scroll_bottom - 17, thumb_cy))
    surf.fill(t.bg, (297, cy - 17, 14, 35))
    pygame.draw.rect(surf, t.fg, (297, cy - 14, 14, 29), 3)


def draw_chevron(app: App, surf: pygame.Surface) -> None:
    app.icons.draw(surf, "chevron_down", app.theme.rule_dim, (150, app.layout.chevron_cy), "center")
