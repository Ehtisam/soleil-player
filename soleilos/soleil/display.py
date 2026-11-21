"""Çizilen kareyi ekrana gönderir (PC). Pi'deki karşılığı hw/framebuffer.py.

Arayüz her zaman ekran çözünürlüğündeki bir yüzeye (canvas) çizilir.
PC'de bu yüzey tam sayı katıyla büyütülüp pencerede gösterilir; pikseller
yumuşatılmadığı için gerçek ekrandaki gibi keskin görünür.

Pencerenin altında cihazın ön yüzü de çizilir: ekranın altındaki bölge,
iki ışık çubuğu ve aralarında SOLEIL logosu. Çubuklar Pi'deki LED'lerle
aynı renkleri gösterir (show).

Büyütme katı verilmezse ekrana sığan en büyük kat seçilir. Windows'ta
uygulama "DPI'dan haberdar" yapılır: yoksa Windows'un %125/%150 büyütmesi
pencereyi bir kez daha büyütüp ekrandan taşırır ve pikselleri bulanıklaştırır.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import pygame

FACE_H = 64                     # ön yüz önizlemesinin yüksekliği (ekran pikseli)
BODY = (30, 25, 23)             # kasa rengi (taslak)
ENGRAVE = (70, 60, 52)          # logonun rengi (kasaya basılı/kazınmış)


TITLE_BAR = 60                  # pencere başlığı ve kenarlar için pay (gerçek piksel)


def fit_scale(w: int, h: int, avail_w: int, avail_h: int) -> int:
    """w x h'lik pencerenin avail_w x avail_h'ye sığan en büyük tam sayı katı."""
    return max(1, min(4, avail_w // w, (avail_h - TITLE_BAR) // h))


def _work_area() -> tuple[int, int]:
    """Görev çubuğu hariç kullanılabilir ekran alanı (gerçek piksel)."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)   # ekran başına DPI
        except (AttributeError, OSError):
            ctypes.windll.user32.SetProcessDPIAware()
        rect = wintypes.RECT()
        if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rect), 0):  # SPI_GETWORKAREA
            return rect.right - rect.left, rect.bottom - rect.top
    w, h = pygame.display.get_desktop_sizes()[0]
    return w, h - 80                # görev çubuğu / menü çubuğu için pay


class DesktopDisplay:
    def __init__(self, size: tuple[int, int], scale: Optional[int], title: str, face: bool = True) -> None:
        self.size = size
        self.face_h = FACE_H if face else 0
        avail = _work_area()
        self.scale = scale or fit_scale(size[0], size[1] + self.face_h, *avail)
        scale = self.scale
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        self.window = pygame.display.set_mode((size[0] * scale, (size[1] + self.face_h) * scale))
        pygame.display.set_caption(title)
        self._shade = pygame.Surface((size[0] * scale, size[1] * scale), pygame.SRCALPHA)
        self._face = pygame.Surface((size[0], self.face_h)) if face else None
        self._leds = ([], [])
        self._font = None

    def present(self, canvas: pygame.Surface, brightness: float = 1.0) -> None:
        screen = self.window.subsurface((0, 0, self.size[0] * self.scale, self.size[1] * self.scale))
        if self.scale == 1:
            screen.blit(canvas, (0, 0))
        else:
            pygame.transform.scale(canvas, screen.get_size(), screen)
        if brightness < 1.0:
            # PC'de parlaklık önizlemesi; Pi'de arka ışık ya da görüntü karartma
            self._shade.fill((0, 0, 0, round(255 * (1 - brightness))))
            screen.blit(self._shade, (0, 0))
        self._draw_face()
        pygame.display.flip()

    def present_off(self) -> None:
        """Uyku: ekran kapalı."""
        self.window.fill((0, 0, 0), (0, 0, self.size[0] * self.scale, self.size[1] * self.scale))
        self._draw_face()
        pygame.display.flip()

    # -- ön yüz ve ışık çubukları ---------------------------------------------------

    def show(self, left, right) -> None:
        """LED renkleri (her çubukta 0 = logoya en yakın)."""
        self._leds = (list(left), list(right))
        if self._face is not None:
            self._draw_face()
            pygame.display.flip()

    def _bar(self, colors, rect: pygame.Rect, outward_left: bool) -> None:
        """Buzlu akrilik arkasında LED'ler: renkler çubuk boyunca yumuşak geçer,
        etrafa hafif ışık vurur."""
        face = self._face
        face.fill((14, 12, 11), rect)                       # yarık
        if not colors or not any(any(c) for c in colors):
            return
        ordered = list(reversed(colors)) if outward_left else colors
        strip = pygame.Surface((len(ordered), 1))
        for i, c in enumerate(ordered):
            strip.set_at((i, 0), c)
        glow = pygame.transform.smoothscale(strip, (rect.w + 16, rect.h + 12))
        glow.set_alpha(70)
        face.blit(glow, (rect.x - 8, rect.y - 6), special_flags=pygame.BLEND_RGB_ADD)
        bar = pygame.transform.smoothscale(strip, rect.size)
        face.blit(bar, rect)

    def _draw_face(self) -> None:
        if self._face is None:
            return
        face, w = self._face, self.size[0]
        face.fill(BODY)
        face.fill((44, 38, 34), (0, 0, w, 2))               # ekranla kasa arası çizgi
        cy = self.face_h // 2 + 2
        left, right = self._leds
        self._bar(left, pygame.Rect(16, cy - 3, 96, 6), outward_left=True)
        self._bar(right, pygame.Rect(w - 16 - 96, cy - 3, 96, 6), outward_left=False)
        if self._font is None:
            from .text import FONT_PATH
            self._font = pygame.font.Font(str(FONT_PATH), 16)
        logo = self._font.render("SOLEIL", True, ENGRAVE)
        face.blit(logo, logo.get_rect(center=(w // 2, cy)))
        pygame.draw.circle(face, (12, 10, 10), (w // 2, self.face_h - 9), 2)   # mikrofon deliği
        target = self.window.subsurface((0, self.size[1] * self.scale, w * self.scale, self.face_h * self.scale))
        pygame.transform.scale(face, target.get_size(), target)

    def close(self) -> None:
        pass
