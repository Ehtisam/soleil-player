"""Ses Kaydedici.

Tuşlar:
  encoder tıklama : kayda başla / duraklat / devam
  O (Sol 2)       : kaydı bitir ve kaydet
  S (Sol 1)       : kaydı sil (iki kez basınca)
  İ (Üst 2)       : kayıtlar (Medya / Ses)
  L (Sol 3)       : geri; kayıt sürüyorsa önce kaydeder
  E (Üst 1)       : oynatıcı (kayıt arkada sürer)

Kayda başlarken çalan müzik duraklatılır (hoparlör sesi kayda girmesin).
"""

from __future__ import annotations

import pygame

from ..lang import _
from ..input import Action
from ..recorder import Recorder
from ..theme import mix
from ..timers import clock_text
from ..ui import chrome, glyphs
from .local_music import media_sounds
from .tools import ToolScreen

DELETE_WINDOW = 3.0       # silmek için ikinci basışın beklendiği süre


def recorder_of(app) -> Recorder:
    if not hasattr(app, "recorder"):
        app.recorder = Recorder()
    return app.recorder


class RecorderScreen(ToolScreen):
    name = "Ses Kaydedici"

    @property
    def title(self) -> str:
        return "Sols / Ses Kaydedici"

    def __init__(self, app) -> None:
        super().__init__(app)
        self.rec = recorder_of(app)
        self.delete_asked_at = -10.0

    @property
    def animating(self) -> bool:
        return self.rec.state != "idle" or self.rec.encoding

    # -- girdi -------------------------------------------------------------------

    def handle(self, action: Action) -> None:
        app, rec = self.app, self.rec
        if action is Action.SELECT:
            if rec.state == "idle":
                self._start()
            else:
                rec.toggle_pause()
        elif action is Action.LEFT2 and rec.state != "idle":
            self._finish()
        elif action is Action.LEFT1 and rec.state != "idle":
            if app.time - self.delete_asked_at < DELETE_WINDOW:
                rec.stop(save=False)
                app.toast("KAYIT SİLİNDİ")
            else:
                self.delete_asked_at = app.time
                app.toast("SİLMEK İÇİN", "TEKRAR BAS", seconds=DELETE_WINDOW)
        elif action is Action.TOP2 and rec.state == "idle":
            app.push(media_sounds(app))
        elif action is Action.BACK and rec.state != "idle":
            self._finish()
            app.pop()
        else:
            super().handle(action)

    def _start(self) -> None:
        app = self.app
        if app.playback.playing:
            app.playback.toggle()          # müzik kayda girmesin
        if not self.rec.start():
            app.toast("MİKROFON AÇILAMADI", (self.rec.error or "")[:24])

    def _finish(self) -> None:
        path = self.rec.stop(save=True)
        if path:
            self.app.toast("KAYDEDİLDİ", path.stem)
        else:
            self.app.toast("KAYIT ÇOK KISA", "KAYDEDİLMEDİ")

    def update(self, dt: float) -> None:
        if self.rec.state != "idle":
            self.app.last_input = self.app.time      # kayıt sürerken ekran uyumasın

    # -- çizim -------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L, rec = self.app, self.app.theme, self.app.layout, self.rec
        cx = self.mid_x
        self.draw_big(surf, clock_text(rec.elapsed), 118)

        # Durum: kayıtta yanıp sönen kare
        y = 172
        if rec.state == "recording":
            label = "KAYDEDİYOR"
        elif rec.state == "paused":
            label = "DURAKLADI"
        else:
            label = "HAZIR"
        w = app.text.width(label, "medium")
        dot = pygame.Rect(cx - w // 2 - 16, y - 5, 10, 10)
        if rec.state == "recording" and int(app.time * 2) % 2 == 0:
            surf.fill(t.fg, dot)
        else:
            pygame.draw.rect(surf, t.rule if rec.state == "idle" else t.fg, dot, 1)
        app.text.draw(surf, label, "medium", t.fg if rec.state != "idle" else t.rule, (dot.right + 6, y), "midleft")

        # Dalga: son seviyeler, en yenisi sağda, ortadan yukarı-aşağı
        box = pygame.Rect(L.left + 4, 196, L.row_box_w - 4, 84)
        pygame.draw.rect(surf, t.rule_dim, box, 1)
        mid = box.centery
        surf.fill(t.rule_dim, (box.x + 2, mid, box.w - 4, 1))
        levels = list(rec.levels)
        step = 3
        count = (box.w - 6) // step
        levels = levels[-count:]
        x = box.right - 3 - len(levels) * step
        for i, lv in enumerate(levels):
            h = max(1, round(lv * (box.h / 2 - 4)))
            age = (len(levels) - i) / max(1, count)
            color = mix(t.fg, t.rule, min(1.0, age * 1.4))
            surf.fill(color, (x + i * step, mid - h, 2, h * 2))

        # Anlık seviye: bölmeli çubuk ve tepe işareti
        bar = pygame.Rect(L.left + 4, 296, L.row_box_w - 4, 12)
        segments = (bar.w - 2) // 6
        lit = round(rec.level * segments) if rec.state != "idle" else 0
        peak = round(rec.peak * segments) if rec.state != "idle" else -1
        for i in range(segments):
            color = t.fg if i < lit else t.rule_dim
            if i == peak:
                color = t.fg
            surf.fill(color, (bar.x + 1 + i * 6, bar.y, 4, bar.h))
        app.text.draw(surf, "SEVİYE", "small", t.rule, (bar.x, bar.bottom + 12), "midleft")

        # Son kayıt
        if rec.last_saved:
            name = rec.last_saved.stem
            note = "  (sıkıştırılıyor)" if rec.encoding else f"  .{rec.last_saved.suffix[1:].upper()}"
            app.text.draw(surf, _("SON: {ad}").format(ad=f"{name}{note}"), "small", t.rule,
                          (L.left + L.row_box_w, bar.bottom + 12), "midright")

        if rec.state == "idle":
            hints = [(Action.SELECT, "KAYDET"), (Action.TOP2, "KAYITLAR")]
        else:
            hints = [(Action.SELECT, "DURAKLAT" if rec.state == "recording" else "DEVAM"),
                     (Action.LEFT2, "BİTİR"), (Action.LEFT1, "SİL")]
        self.draw_frame(surf, hints)
