"""Açılış sekansı: 3 aşama (Figma'daki Power On -> System Load -> Welcome).

1. Güç  : eski CRT ekranlar gibi ortada bir çizgi parlar (altında Latince
   "SEQUENTIA INITIALIS INCEPTIVA"), sonra ekran açılır
2. Yükleme: BIOS tarzı donanım kontrolü satır satır yazılır, sonra yükleme
   çubuğu ve "CAELUM PROPE. / SYSTEMA PARATUM." (gök yakın, sistem hazır).
   Altta Wang Han'ın "Liangzhou Şarkısı" (Tang, telifsiz) harf harf yazılır
3. Karşılama: güneş simgesi ve SOLEIL logosu, altta pil ve CPU / RAM

Toplam ~4.5 sn. Yükleme çubuğu süsten ibaret değil: açılışta müzik
kütüphanesi taranmaya başlar, çubuk taramanın önüne geçemez. Önbellek
varsa tarama hemen biter; ilk açılışta uzun sürerse en çok BAR_WAIT kadar
beklenir, tarama arka planda sürer (menüde yüzde görünür).

Şiir için Noto Sans SC'nin sadece şiirdeki harfleri içeren küçük bir kopyası
var (assets/fonts/NotoSansSC-siir.ttf, OFL). Şiir değişirse font yeniden
çıkarılmalı; dosya yoksa şiir çizilmez.

Herhangi bir tuş sekansı atlar. Ayarlardan kapatılırsa doğrudan ana menü açılır.
"""

from __future__ import annotations

import math
from typing import Optional

import pygame

from ..lang import _
from .. import __version__
from ..config import ASSETS
from ..theme import mix
from .base import Screen

POWER_LINE = 0.3       # çizgi uzar
POWER_OPEN = 0.65      # çizgi durur, Latince okunur; sonra ekran açılır
POWER_END = 0.9
LOAD_START = POWER_END + 0.05
LINE_STEP = 0.1
BAR_LEN = 0.7          # çubuğun en kısa dolma süresi
BAR_WAIT = 3.0         # kütüphane taraması için en çok bu kadar fazladan beklenir
MOTTO_STEP = 0.25      # Latince iki satırın arası
MOTTO_HOLD = 0.2
WELCOME_LEN = 1.2

POWER_MOTTO = "SEQUENTIA INITIALIS INCEPTIVA"
MOTTO = ["CAELUM PROPE.", "SYSTEMA PARATUM."]
POEM = ["葡萄美酒夜光杯，欲饮琵琶马上催。", "醉卧沙场君莫笑，古来征战几人回？"]
POEM_FONT = ASSETS / "fonts" / "NotoSansSC-siir.ttf"
POEM_SIZE = 13

RAM = "512MB"          # Pi Zero 2 W. /proc/meminfo ekran kartı payı yüzünden daha az gösterir

CHECKS = [
    ("CPU", "ARM CORTEX-A53 x4"),
    ("RAM", "512 MB"),
    ("EKRAN", "320x480 TFT"),
    ("SES", "I2S DAC + AMFİ"),
    ("AĞ", "WI-FI / BT"),
    ("DEPO", "SD KART"),
    ("IŞIK", "2x RGB ÇUBUK"),
]


def cpu_clock() -> str:
    """İşlemcinin en yüksek hızı; okunamazsa Pi Zero 2 W'nin 1.0GHz'i."""
    try:
        with open("/sys/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq") as f:
            return f"{int(f.read().strip()) / 1e6:.1f}GHz"
    except (OSError, ValueError):
        return "1.0GHz"


def battery_line(status) -> str:
    """PİL: %84 [3.92V] [ŞARJDA]. Voltaj sadece ölçülebiliyorsa (INA219)."""
    line = _("PİL: %{n}").format(n=status.battery)
    if status.voltage is not None:
        line += f" [{status.voltage:.2f}V]"
    if status.charging:
        line += " [ŞARJDA]"
    return line


class BootScreen(Screen):
    animating = True

    def __init__(self, app, next_screen) -> None:
        super().__init__(app)
        self.next_screen = next_screen
        self.t = 0.0
        self.lines_end = LOAD_START + 3 * LINE_STEP + len(CHECKS) * LINE_STEP
        self.poem_end = self.lines_end + BAR_LEN
        self.wait_until = self.poem_end + BAR_WAIT
        # Tarama sürerse bu üçü birlikte ileri kayar (update)
        self.bar_end = self.poem_end
        self.welcome_start = self.bar_end + MOTTO_STEP * len(MOTTO) + MOTTO_HOLD
        self.end = self.welcome_start + WELCOME_LEN
        app.library.ensure_scanned()
        self.poem_font: Optional[pygame.font.Font] = None
        if POEM_FONT.exists():
            self.poem_font = pygame.font.Font(str(POEM_FONT), POEM_SIZE)

    def handle(self, action) -> None:
        self._finish()

    def update(self, dt: float) -> None:
        self.t += dt
        if self.t >= self.bar_end and self._waiting():
            self.bar_end += dt
            self.welcome_start += dt
            self.end += dt
        if self.t >= self.end:
            self._finish()

    def _waiting(self) -> bool:
        """Kütüphane taraması bitmedi ve bekleme süresi dolmadı."""
        return self.app.library.state != "ready" and self.t < self.wait_until

    def bar_frac(self) -> float:
        k = min(1.0, max(0.0, (self.t - self.lines_end) / BAR_LEN))
        return min(k, self.app.library.progress) if self._waiting() else k

    def _finish(self) -> None:
        if self.app.screen is self:
            self.app.replace(self.next_screen())

    # -- çizim ---------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill((0, 0, 0) if self.t < POWER_END else self.app.theme.bg)
        if self.t < POWER_END:
            self._draw_power(surf)
        elif self.t < self.welcome_start:
            self._draw_load(surf)
        else:
            self._draw_welcome(surf)

    def _draw_power(self, surf: pygame.Surface) -> None:
        """Ortada yatay bir çizgi uzar, altında Latince belirir, sonra ekran
        dikey olarak açılır."""
        t, L = self.app.theme, self.app.layout
        cy = L.height // 2
        if self.t < POWER_OPEN:
            w = round(L.width * min(1.0, self.t / POWER_LINE))
            surf.fill(t.fg, ((L.width - w) // 2, cy - 1, w, 2))
            if self.t >= POWER_LINE:
                fade = min(1.0, (self.t - POWER_LINE) / 0.2)
                self.app.text.draw(surf, POWER_MOTTO, "small", mix((0, 0, 0), t.rule, fade),
                                   (L.width // 2, cy + 18), "center")
        else:
            h = round(L.height * ((self.t - POWER_OPEN) / (POWER_END - POWER_OPEN)))
            surf.fill(mix(t.fg, t.bg, 0.6), (0, cy - h // 2, L.width, h))
            surf.fill(t.fg, (0, cy - 1, L.width, 2))

    def _draw_load(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        x, right = L.left + 6, L.left + L.content_w - 4
        y = 22
        header = [
            ("SOLSHUENSHIA ELECTRONIX", t.fg),
            (f"SOLEIL PORTABLE  BIOS v{__version__}", t.rule),
            ("", t.rule),
        ]
        k = 0
        for text, color in header:
            if self.t >= LOAD_START + k * LINE_STEP:
                app.text.draw(surf, text, "medium", color, (x, y))
            y += 20
            k += 1

        for name, detail in CHECKS:
            start = LOAD_START + k * LINE_STEP
            if self.t >= start:
                n = app.text.draw(surf, name, "medium", t.rule, (x, y))
                app.text.draw(surf, detail, "medium", t.fg, (x + 62, y))
                ok_shown = self.t >= start + LINE_STEP * 0.7
                status = app.text.draw(surf, "[ OK ]" if ok_shown else "[ .. ]", "medium",
                                       t.fg if ok_shown else t.rule, (right, y), "topright")
                dots_from = x + 62 + app.text.width(detail, "medium") + 6
                for dx in range(dots_from, status.left - 6, 5):
                    surf.fill(t.rule_dim, (dx, y + 13, 2, 1))
            y += 20
            k += 1

        # Yükleme çubuğu: bölmeli
        if self.t >= self.lines_end:
            y += 18
            app.text.draw(surf, "SOLEILOS YÜKLENİYOR", "medium", t.fg, (x, y))
            y += 26
            bar = pygame.Rect(x, y, right - x, 14)
            pygame.draw.rect(surf, t.rule, bar, 1)
            frac = self.bar_frac()
            segments = (bar.w - 4) // 8
            for i in range(round(segments * frac)):
                surf.fill(t.fg, (bar.x + 3 + i * 8, bar.y + 3, 6, bar.h - 6))
            app.text.draw(surf, f"%{round(frac * 100)}", "small", t.rule, (right, bar.bottom + 12), "midright")
            y = bar.bottom + 24

        # Çubuk dolunca Latince: "gök yakın, sistem hazır"
        rule_y = L.height - 52
        motto_y = max(y, rule_y - 58)
        if motto_y + 22 * len(MOTTO) <= rule_y:
            for i, line in enumerate(MOTTO):
                if self.t >= self.bar_end + i * MOTTO_STEP:
                    app.text.draw(surf, line, "medium", t.fg, (x, motto_y + i * 22))

        # Altta şiir harf harf yazılır, sonunda imleç yanıp söner
        surf.fill(t.rule_dim, (x, rule_y, right - x, 1))
        self._draw_poem(surf, x, rule_y + 8)

    def _draw_poem(self, surf: pygame.Surface, x: int, y: int) -> None:
        t = self.app.theme
        frac = min(1.0, max(0.0, (self.t - LOAD_START) / (self.poem_end - LOAD_START)))
        left = round(sum(len(line) for line in POEM) * frac)
        cx, cy = x, y
        for i, line in enumerate(POEM):
            shown = line[:left]
            left -= len(shown)
            if not shown:
                break
            cx, cy = x, y + i * 18
            if self.poem_font:
                img = self.poem_font.render(shown, True, t.rule)
                surf.blit(img, (x, cy))
                cx += img.get_width()
        if int(self.t * 3) % 2 == 0:
            surf.fill(t.fg, (cx + 2, cy + 14, 8, 2))

    def _draw_welcome(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        k = min(1.0, (self.t - self.welcome_start) / 0.6)    # açılma
        cx, cy = L.width // 2, L.height // 2 - 50

        # Güneş: dolu daire ve dönen ışınlar
        r = round(22 * k)
        if r > 0:
            pygame.draw.circle(surf, t.fg, (cx, cy), r)
            spin = (self.t - self.welcome_start) * 0.6
            for i in range(12):
                a = spin + i * math.pi / 6
                r1, r2 = r + 8, r + 8 + (14 if i % 2 == 0 else 8) * k
                p1 = (cx + math.cos(a) * r1, cy + math.sin(a) * r1)
                p2 = (cx + math.cos(a) * r2, cy + math.sin(a) * r2)
                pygame.draw.line(surf, t.fg, p1, p2, 3)

        if k >= 1.0:
            app.text.draw(surf, "SOLEIL", "display", t.fg, (cx + 2, cy + 88), "center")
            surf.fill(t.rule, (cx - 90, cy + 116, 180, 1))
            app.text.draw(surf, "SOLSHUENSHIA // HOŞ GELDİN", "small", t.rule, (cx, cy + 132), "center")

            # Altta pil ve sistem
            x, rule_y = L.left + 6, L.height - 60
            surf.fill(t.rule_dim, (x, rule_y, L.content_w - 10, 1))
            app.text.draw(surf, battery_line(app.status), "small", t.rule, (x, rule_y + 12))
            app.text.draw(surf, f"CPU: {cpu_clock()} // RAM: {RAM}", "small", t.rule, (x, rule_y + 32))
