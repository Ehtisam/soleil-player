"""Araçlar: saat, takvim (calendar.py), kronometre, zamanlayıcı, hesap makinesi, ekran feneri.

Kronometre ve zamanlayıcı ekrandan çıkınca da çalışır (timers.py);
listede kalan süreleri görünür. Bütün araçlarda L (Sol 3) geri.
"""

from __future__ import annotations

import time

import pygame

from ..lang import _
from .. import calc, seb
from ..input import Action
from ..theme import mix
from ..timers import clock_text, duration_label
from ..ui import chrome, dial, glyphs
from ..ui.listview import ListItem, ListScreen
from .base import Screen


def open_calendar(app):
    from .calendar import open_calendar as open_
    return open_(app)

MONTHS = ["OCAK", "ŞUBAT", "MART", "NİSAN", "MAYIS", "HAZİRAN",
          "TEMMUZ", "AĞUSTOS", "EYLÜL", "EKİM", "KASIM", "ARALIK"]
DAYS = ["PAZARTESİ", "SALI", "ÇARŞAMBA", "PERŞEMBE", "CUMA", "CUMARTESİ", "PAZAR"]


def tools_menu(app) -> ListScreen:
    sw, tm = app.stopwatch, app.timer

    def stopwatch_value() -> str:
        if sw.running or sw.elapsed:
            return f"[{'»' if sw.running else ''}{clock_text(sw.elapsed)}]"
        return ""

    def timer_value() -> str:
        if tm.started:
            return f"[{'»' if tm.running else ''}{clock_text(tm.remaining)}]"
        return f"[{duration_label(tm.duration)}]"

    screen = ListScreen(app, [
        ListItem("Saat", value=lambda: f"[{time.strftime('%H:%M')}]", open=lambda: ClockScreen(app)),
        ListItem("Takvim", value=lambda: f"[{seb.now().short()}]", open=lambda: open_calendar(app)),
        ListItem("Kronometre", value=stopwatch_value, open=lambda: StopwatchScreen(app)),
        ListItem("Zamanlayıcı", value=timer_value, open=lambda: TimerScreen(app)),
        ListItem("Hesap Makinesi", open=lambda: CalculatorScreen(app)),
        ListItem("Ekran Feneri", open=lambda: FlashlightScreen(app)),
    ])
    screen.title = "Sols / Araçlar"
    return screen


class ToolScreen(Screen):
    """Araç ekranlarının ortak çerçevesi: header, ortada içerik, altta
    işaretli ipuçları ve mini oynatıcı."""
    name = ""

    @property
    def title(self) -> str:
        return f"Sols / Araçlar / {self.name}"

    @property
    def mid_x(self) -> int:
        L = self.app.layout
        return (L.left + L.row_box_w) // 2 + 2

    def draw_frame(self, surf: pygame.Surface, hints) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        chrome.draw_header(app, surf, self.title)
        if hints:
            glyphs.draw_hints(app, surf, hints, t.rule, (L.width // 2, L.footer_line_y - 22), "center")
        chrome.draw_footer(app, surf)

    def draw_big(self, surf, text: str, cy: int, color=None, small_tail: str = "") -> pygame.Rect:
        """Büyük rakamlar ortada; small_tail (ör. salise) yanında küçük."""
        app = self.app
        color = color or app.theme.fg
        tail_w = app.text.width(small_tail, "display")
        style = "clock" if app.text.width(text, "clock") + tail_w <= app.layout.row_box_w else "display"
        w = app.text.width(text, style) + app.text.width(small_tail, "display")
        x = self.mid_x - w // 2
        r = app.text.draw(surf, text, style, color, (x, cy), "midleft")
        if small_tail:
            # Küçük kısım büyük rakamların alt çizgisine hizalı
            app.text.draw(surf, small_tail, "display", color,
                          (r.right, r.bottom - app.text.height(style) * 0.12), "bottomleft")
        return r


# -- saat ----------------------------------------------------------------------

class ClockScreen(ToolScreen):
    """Büyük dijital saat. Pi'de saat Wi-Fi'ye bağlanınca internetten
    ayarlanır (Pi'de pil destekli saat yok)."""
    name = "Saat"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._second = None

    def update(self, dt: float) -> None:
        second = int(time.time())
        if second != self._second:
            self._second = second
            self.app.dirty = True

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        now = time.localtime()
        cx = self.mid_x
        self.draw_big(surf, time.strftime("%H:%M", now), 140)

        # Saniye çubuğu: 60 dilim
        y = 200
        seg_w = (L.row_box_w - 20) / 60
        x0 = cx - seg_w * 30
        for i in range(60):
            h = 10 if i % 5 == 0 else 6
            color = t.fg if i <= now.tm_sec else t.rule_dim
            surf.fill(color, (round(x0 + i * seg_w), y - h // 2, max(1, round(seg_w) - 2), h))
        app.text.draw(surf, f"{now.tm_sec:02d}", "small", t.rule, (cx, y + 18), "center")

        date = f"{now.tm_mday} {MONTHS[now.tm_mon - 1]} {now.tm_year}"
        app.text.draw(surf, date, "body", t.fg, (cx, 256), "center")
        app.text.draw(surf, DAYS[now.tm_wday], "medium", t.rule, (cx, 280), "center")
        # Takvim-i Şeb: gece öğlen değişir
        app.text.draw(surf, seb.now().daily(), "medium", t.fg, (cx, 306), "center")

        # Arkada çalışan kronometre / zamanlayıcı
        y = 346
        surf.fill(t.rule_dim, (L.left, y - 16, L.row_box_w, 1))
        for label, active, value in (
            ("ZAMANLAYICI", app.timer.started, clock_text(app.timer.remaining)),
            ("KRONOMETRE", app.stopwatch.running or app.stopwatch.elapsed > 0, clock_text(app.stopwatch.elapsed)),
        ):
            if active:
                app.text.draw(surf, label, "medium", t.rule, (L.left + 8, y), "midleft")
                app.text.draw(surf, value, "medium", t.fg, (L.left + L.row_box_w - 8, y), "midright")
                y += 24
        self.draw_frame(surf, [])


# -- kronometre ----------------------------------------------------------------

class StopwatchScreen(ToolScreen):
    name = "Kronometre"

    @property
    def animating(self) -> bool:
        return self.app.stopwatch.running

    def handle(self, action: Action) -> None:
        sw = self.app.stopwatch
        if action is Action.SELECT:
            sw.toggle()
        elif action is Action.LEFT2:
            sw.lap()
        elif action is Action.LEFT1:
            if not sw.running:
                sw.reset()
        else:
            super().handle(action)

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        sw = app.stopwatch
        text = clock_text(sw.elapsed)
        self.draw_big(surf, text, 130, small_tail=f".{int(sw.elapsed * 100) % 100:02d}")
        state = "ÇALIŞIYOR" if sw.running else ("DURDU" if sw.elapsed else "HAZIR")
        app.text.draw(surf, state, "small", t.rule, (self.mid_x, 182), "center")

        # Turlar: en yenisi üstte, toplam süre ve bir öncekinden farkı
        y = 214
        surf.fill(t.rule_dim, (L.left, y - 12, L.row_box_w, 1))
        if not sw.laps:
            app.text.draw(surf, "TUR YOK", "small", t.rule_dim, (self.mid_x, y + 12), "center")
        for n in range(len(sw.laps), max(0, len(sw.laps) - 7), -1):
            total = sw.laps[n - 1]
            split = total - (sw.laps[n - 2] if n > 1 else 0.0)
            app.text.draw(surf, _("TUR {n}").format(n=f"{n:02d}"), "track", t.rule, (L.left + 8, y + 8), "midleft")
            app.text.draw(surf, clock_text(total, cs=True), "track", t.fg, (self.mid_x + 10, y + 8), "center")
            app.text.draw(surf, "+" + clock_text(split, cs=True), "track", t.rule,
                          (L.left + L.row_box_w - 8, y + 8), "midright")
            y += 22
        hints = [(Action.SELECT, "DURDUR" if sw.running else "BAŞLAT")]
        hints.append((Action.LEFT2, "TUR") if sw.running else (Action.LEFT1, "SIFIRLA"))
        self.draw_frame(surf, hints)


# -- zamanlayıcı ---------------------------------------------------------------

class TimerScreen(ToolScreen):
    name = "Zamanlayıcı"

    def __init__(self, app) -> None:
        super().__init__(app)
        self._shown = None

    def handle(self, action: Action) -> None:
        tm = self.app.timer
        if action in (Action.UP, Action.DOWN):
            tm.adjust(-1 if action is Action.UP else 1)
        elif action is Action.SELECT:
            tm.toggle()
        elif action is Action.LEFT1:
            tm.reset()
        else:
            super().handle(action)

    @property
    def animating(self) -> bool:
        return self.app.timer.remaining <= 0      # bitince yanıp sönsün

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        tm = app.timer
        done = tm.remaining <= 0
        blink_off = done and int(app.time * 2) % 2
        # Saniyenin kalanını yukarı yuvarla: 4:59.3 -> 05:00 değil 04:60 olmasın
        shown = clock_text(tm.remaining + 0.999 if tm.remaining > 0 else 0)
        self.draw_big(surf, shown, 140, mix(t.fg, t.bg, 0.7) if blink_off else t.fg)

        if done:
            state = "SÜRE DOLDU"
        elif tm.running:
            state = "ÇALIŞIYOR"
        elif tm.started:
            state = "DURAKLADI"
        else:
            state = "SÜRE: " + duration_label(tm.duration)
        app.text.draw(surf, state, "medium", t.fg if done else t.rule, (self.mid_x, 196), "center")

        # Bölmeli ilerleme çubuğu (kalan süre)
        bar = pygame.Rect(L.left + 10, 226, L.row_box_w - 20, 16)
        pygame.draw.rect(surf, t.rule, bar, 1)
        frac = tm.remaining / tm.duration if tm.duration else 0
        segments = (bar.w - 4) // 8
        for i in range(round(segments * frac)):
            surf.fill(t.fg, (bar.x + 3 + i * 8, bar.y + 3, 6, bar.h - 6))

        if not tm.started:
            app.text.draw(surf, "ENCODER: SÜREYİ SEÇ", "small", t.rule, (self.mid_x, 274), "center")
            # Seçilebilen süreler: seçili olan ortada
            from ..timers import TIMER_STEPS
            i = TIMER_STEPS.index(tm.duration) if tm.duration in TIMER_STEPS else 0
            for d in (-2, -1, 0, 1, 2):
                if 0 <= i + d < len(TIMER_STEPS):
                    color = t.fg if d == 0 else mix(t.fg, t.bg, 0.35 + abs(d) * 0.2)
                    label = duration_label(TIMER_STEPS[i + d])
                    app.text.draw(surf, label, "medium" if d == 0 else "small", color,
                                  (self.mid_x + d * 62, 304), "center")
            r = pygame.Rect(0, 0, 64, 24)
            r.center = (self.mid_x, 304)
            pygame.draw.rect(surf, t.fg, r, 1)

        hints = [(Action.SELECT, "DURAKLAT" if tm.running else ("YENİDEN" if done else "BAŞLAT"))]
        if tm.started:
            hints.append((Action.LEFT1, "SIFIRLA"))
        self.draw_frame(surf, hints)


# -- hesap makinesi ------------------------------------------------------------

KEYS = list("0123456789") + [".", "+", "-", "×", "÷", "(", ")"]


class CalculatorScreen(ToolScreen):
    """Kadran şeridinden rakam ve işlem seçilir; O sonucu verir, sonuç yeni
    işlemin başı olur. Yazarken sonuç altta önizlenir."""
    name = "Hesap Makinesi"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.expr = ""
        self.result = ""          # = ile alınan son sonuç
        self.error = False
        self.dial = dial.Dial(1)

    def handle(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            self.dial.turn(-1 if action is Action.UP else 1)
        elif action is Action.SELECT:
            if self.result and KEYS[self.dial.index(len(KEYS))].isdigit():
                self.expr = ""        # sonuçtan sonra rakam: yeni işlem
            self.result, self.error = "", False
            if len(self.expr) < 40:
                self.expr += KEYS[self.dial.index(len(KEYS))]
        elif action is Action.LEFT1:
            self.expr, self.result, self.error = self.expr[:-1], "", False
        elif action is Action.LEFT2:
            self._equals()
        elif action is Action.HOLD:
            self.expr, self.result, self.error = "", "", False
        else:
            super().handle(action)

    def _equals(self) -> None:
        if not self.expr:
            return
        try:
            value = calc.format_number(calc.evaluate(self.expr))
        except calc.CalcError:
            self.error = True
            return
        self.result = value
        self.expr = value if "E" not in value else ""

    def update(self, dt: float) -> None:
        self.animating = self.dial.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        # Ekran kutusu: üstte ifade, altta büyük sonuç
        box = pygame.Rect(L.left, L.row_cy(0) - 18, L.row_box_w, 150)
        chrome.draw_panel(app, surf, box)
        right = box.right - 10
        expr = self.expr or "0"
        max_chars = int((box.w - 20) // app.text.pitch("medium"))
        if len(expr) > max_chars:
            expr = ".." + expr[-(max_chars - 2):]
        app.text.draw(surf, expr, "medium", t.rule if self.result else t.fg, (right, box.y + 22), "midright")

        if self.error:
            big, color = "HATA", t.fg
        elif self.result:
            big, color = self.result, t.fg
        else:
            big, color = calc.preview(self.expr), t.rule
        if big:
            app.text.draw(surf, ("= " if not self.error else "") + big if len(big) < 11 else big,
                          "display", color, (right, box.bottom - 40), "midright")
        surf.fill(t.rule_dim, (box.x + 8, box.y + 44, box.w - 16, 1))

        cx = dial.draw(app, surf, KEYS, self.dial.anim, box.bottom + 80)
        glyphs.draw_hints(app, surf, [(Action.LEFT1, "SİL"), (Action.LEFT2, "="), (Action.HOLD, "TEMİZLE")],
                          t.rule, (cx, box.bottom + 130), "center")
        chrome.draw_header(app, surf, self.title)
        chrome.draw_footer(app, surf)


# -- ekran feneri --------------------------------------------------------------

LIGHTS = [("BEYAZ", (255, 255, 255)), ("SICAK", (255, 214, 160)), ("KIRMIZI", (255, 36, 20))]


class FlashlightScreen(ToolScreen):
    """Ekranı tam parlaklıkta tek renk yakar. Encoder renk değiştirir.
    Açıkken ekran uykuya geçmez; çıkınca parlaklık eski haline döner.
    Pi'de ışık çubukları da aynı renkte yanacak."""
    name = "Ekran Feneri"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.color = 0
        self.saved_brightness = app.settings.brightness
        app.settings.brightness = 100      # kaydedilmez, sadece bu ekranda

    def handle(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN, Action.SELECT):
            self.color = (self.color + (-1 if action is Action.UP else 1)) % len(LIGHTS)
        else:
            super().handle(action)

    def update(self, dt: float) -> None:
        self.app.last_input = self.app.time    # fener açıkken uyuma

    def closed(self) -> None:
        self.app.settings.brightness = self.saved_brightness

    def draw(self, surf: pygame.Surface) -> None:
        name, color = LIGHTS[self.color]
        surf.fill(color)
        hint = mix(color, (0, 0, 0), 0.35)
        L = self.app.layout
        glyphs.draw_hints(self.app, surf, [(Action.SELECT, name), (Action.BACK, "KAPAT")], hint,
                          (L.width // 2, L.height - 18), "center")
