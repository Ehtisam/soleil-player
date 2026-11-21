"""Işık çubukları: ekranın altında, SOLEIL logosunun iki yanında.

Her çubukta 0 numaralı LED logoya en yakın olanıdır.

LedEffects her karede iki çubuğun renklerini hesaplar (Ayarlar > Işık
Çubukları moduna ve o anki duruma göre); sonuç Pi'de WS2812B'ye
(Ws281xStrip), PC'de pencerenin altındaki ön yüz önizlemesine gider.

Modlar:
  KAPALI   : sönük
  SES      : ses seviyesi, logodan dışa doğru dolar
  İLERLEME : şarkının ne kadarı çaldı, soldan sağa (iki çubuk tek çizgi gibi)
  VU METRE : müzik çalarken logodan dışa doğru oynayan seviye (sahte)

Her modda ortak: müzik duraklayınca yavaşça nefes alır, zamanlayıcı
bitince yanıp söner, ekran uyurken söner. Parlaklık düşük tutulur (pil).
"""

from __future__ import annotations

import math
import random
from typing import Optional

from . import pins

Color = tuple[int, int, int]
OFF: Color = (0, 0, 0)
MAX_BRIGHTNESS = 0.35          # tam beyaz yerine (göz ve pil için)


def _scale(c: Color, k: float) -> Color:
    k = max(0.0, min(1.0, k))
    return (round(c[0] * k), round(c[1] * k), round(c[2] * k))


class LedEffects:
    def __init__(self, count: int = pins.LED_PER_BAR) -> None:
        self.count = count
        self.vu = 0.0
        self.vu_target = 0.0
        self.vu_timer = 0.0
        self.flash_until = 0.0
        self.flash_color: Optional[Color] = None
        self.left: list[Color] = [OFF] * count
        self.right: list[Color] = [OFF] * count

    def flash(self, now: float, seconds: float = 4.0, color: Optional[Color] = None) -> None:
        """Dikkat çekmek için yanıp sönme (ör. zamanlayıcı bitti; pil azken kırmızı)."""
        self.flash_until = now + seconds
        self.flash_color = color

    def _fill(self, level: float, color: Color) -> list[Color]:
        """0..1 seviyeyi bir çubuğa böler; son LED kısmi yanar."""
        out = []
        for i in range(self.count):
            k = level * self.count - i
            out.append(_scale(color, max(0.0, min(1.0, k))))
        return out

    def update(self, app, dt: float) -> bool:
        """Renkleri hesaplar; değiştiyse True."""
        old = (self.left, self.right)
        color = app.theme.fg
        p = app.playback
        mode = app.settings.led_mode
        now = app.time

        if now < self.flash_until:       # uyarılar ışıklar kapalıyken de görünür
            on = int(now * 4) % 2 == 0
            left = right = [(self.flash_color or color) if on else OFF] * self.count
        elif app.sleeping or mode == "KAPALI":
            left = right = [OFF] * self.count
        elif mode == "SES":
            level = app.status.volume / 100
            left = right = self._fill(level, color)
        elif mode == "İLERLEME":
            t = p.current
            frac = 1.0 if t and t.live else (p.position / t.duration if t and t.duration else 0.0)
            # İki çubuk soldan sağa tek çizgi: önce sol çubuk (dıştan logoya), sonra sağ
            line = [_scale(color, max(0.0, min(1.0, frac * 2 * self.count - i))) for i in range(2 * self.count)]
            left = list(reversed(line[:self.count]))       # 0 = logoya en yakın
            right = line[self.count:]
        else:   # VU METRE
            self.vu_timer -= dt
            if p.playing:
                if self.vu_timer <= 0:
                    self.vu_timer = random.uniform(0.06, 0.14)
                    self.vu_target = random.uniform(0.35, 1.0)
            else:
                self.vu_target = 0.0
            speed = 14 if self.vu_target > self.vu else 5
            self.vu += (self.vu_target - self.vu) * min(1.0, dt * speed)
            left = self._fill(self.vu, color)
            right = self._fill(max(0.0, self.vu + random.uniform(-0.08, 0.08)) if p.playing else self.vu, color)

        # Müzik duraklamışsa (ve bir şey yüklüyse) hafifçe nefes al
        if p.current and not p.playing and mode not in ("KAPALI",) and not app.sleeping \
                and now >= self.flash_until:
            breath = 0.15 + 0.15 * (1 + math.sin(now * 1.6)) / 2
            left = [_scale(color, breath)] * self.count if mode != "İLERLEME" else [_scale(c, 0.5) for c in left]
            right = [_scale(color, breath)] * self.count if mode != "İLERLEME" else [_scale(c, 0.5) for c in right]

        self.left, self.right = list(left), list(right)
        return (self.left, self.right) != old

    @property
    def active(self) -> bool:
        """Animasyon sürüyor mu (döngü hızlı dönsün)."""
        return any(c != OFF for c in self.left + self.right)


class Ws281xStrip:
    """Pi'de WS2812B: iki çubuk tek şerit gibi seri bağlı (önce sol, sonra sağ).
    Sol çubuk logodan dışa doğru yansın diye ters sırayla yazılır."""

    def __init__(self, count: int = pins.LED_PER_BAR) -> None:
        from rpi_ws281x import PixelStrip
        self.count = count
        self.strip = PixelStrip(count * 2, pins.LED_PIN, 800000, 10, False,
                                round(255 * MAX_BRIGHTNESS), pins.LED_CHANNEL)
        self.strip.begin()

    def show(self, left: list[Color], right: list[Color]) -> None:
        ordered = list(reversed(left)) if pins.LED_REVERSED_LEFT else left
        for i, (r, g, b) in enumerate(ordered + right):
            self.strip.setPixelColorRGB(i, r, g, b)
        self.strip.show()

    def close(self) -> None:
        self.show([OFF] * self.count, [OFF] * self.count)
