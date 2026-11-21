"""Pi'de SPI ekrana çizim: Linux framebuffer (/dev/fbN).

Ekranı kernel sürücüsü yönetir (config.txt'de `dtoverlay=piscreen` gibi,
bkz. pi/README). Sürücü bir framebuffer dosyası açar; biz her kareyi
RGB565'e çevirip oraya yazarız, sürücü SPI ile ekrana gönderir.

SPI yavaş (32 MHz'de tam ekran ~13 kare/sn), bu yüzden sadece değişen
satırlar yazılır: menüde imleç oynayınca birkaç satır, tam ekran değil.

Parlaklık: çoğu ucuz 3.5" modülde arka ışık hep açık. Arka ışık pini
yoksa parlaklık görüntü karartılarak uygulanır (PC'deki önizleme gibi).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import pygame

# Ekran sürücüsünü adından tanımak için (sırayla denenir)
DRIVER_NAMES = ("ili9486", "piscreen", "fb_ili9486", "waveshare", "mi0283qt", "ili9488")


def find_framebuffer(size: tuple[int, int]) -> Optional[Path]:
    """SPI ekranın framebuffer'ını bulur: önce sürücü adına, sonra boyuta göre."""
    root = Path("/sys/class/graphics")
    if not root.is_dir():
        return None
    candidates = []
    for fb in sorted(root.glob("fb*")):
        try:
            name = (fb / "name").read_text().strip().lower()
            w, h = (int(v) for v in (fb / "virtual_size").read_text().strip().split(","))
        except (OSError, ValueError):
            continue
        by_name = any(n in name for n in DRIVER_NAMES)
        by_size = sorted((w, h)) == sorted(size)
        if by_name or by_size:
            candidates.append((not by_name, Path("/dev") / fb.name))
    return sorted(candidates)[0][1] if candidates else None


def to_rgb565(canvas: pygame.Surface, brightness: float = 1.0) -> np.ndarray:
    """Yüzeyi (satır, sütun) düzeninde 16 bit RGB565 dizisine çevirir."""
    rgb = pygame.surfarray.array3d(canvas).transpose(1, 0, 2)      # (h, w, 3)
    if brightness < 0.999:
        rgb = (rgb.astype(np.uint16) * max(0, min(256, round(brightness * 256))) >> 8).astype(np.uint8)
    r = (rgb[..., 0].astype(np.uint16) >> 3) << 11
    g = (rgb[..., 1].astype(np.uint16) >> 2) << 5
    b = rgb[..., 2].astype(np.uint16) >> 3
    return r | g | b


class FramebufferDisplay:
    def __init__(self, size: tuple[int, int], device: Optional[Path] = None,
                 fb_size: Optional[tuple[int, int]] = None, stride: Optional[int] = None,
                 backlight=None) -> None:
        """device/fb_size/stride verilmezse /sys'den okunur (testte elle verilir)."""
        self.size = size
        self.device = device or find_framebuffer(size)
        if self.device is None:
            raise RuntimeError("SPI ekran bulunamadı (/dev/fb*). config.txt'deki ekran ayarına bak.")
        sysfs = Path("/sys/class/graphics") / self.device.name
        if fb_size is None:
            w, h = (int(v) for v in (sysfs / "virtual_size").read_text().strip().split(","))
            fb_size = (w, h)
            bpp = int((sysfs / "bits_per_pixel").read_text().strip())
            if bpp != 16:
                raise RuntimeError(f"framebuffer {bpp} bit; 16 bit (RGB565) bekleniyordu")
            stride = int((sysfs / "stride").read_text().strip()) if (sysfs / "stride").exists() else w * 2
        self.fb_size = fb_size
        self.stride = stride or fb_size[0] * 2
        # Sürücü yatay açtıysa (480x320) görüntü 90° döndürülür
        self.rotate = fb_size != size and fb_size == (size[1], size[0])
        self.file = open(self.device, "r+b", buffering=0)
        self.previous: Optional[np.ndarray] = None
        self.backlight = backlight            # gpiozero PWMLED ya da None

    def _write(self, data: np.ndarray) -> None:
        if self.rotate:
            data = np.rot90(data, -1)
        data = np.ascontiguousarray(data)
        h, w = data.shape
        if self.previous is not None and self.previous.shape == data.shape:
            changed = np.flatnonzero(np.any(data != self.previous, axis=1))
            if len(changed) == 0:
                return
            y0, y1 = int(changed[0]), int(changed[-1]) + 1
        else:
            y0, y1 = 0, h
        rows = data[y0:y1]
        if self.stride == w * 2:
            self.file.seek(y0 * self.stride)
            self.file.write(rows.tobytes())
        else:
            for i, row in enumerate(rows):
                self.file.seek((y0 + i) * self.stride)
                self.file.write(row.tobytes())
        self.previous = data

    def present(self, canvas: pygame.Surface, brightness: float = 1.0) -> None:
        if self.backlight is not None:
            self.backlight.value = brightness
            brightness = 1.0
        self._write(to_rgb565(canvas, brightness))

    def present_off(self) -> None:
        if self.backlight is not None:
            self.backlight.value = 0
        h, w = self.size[1], self.size[0]
        self._write(np.zeros((h, w), dtype=np.uint16))

    def close(self) -> None:
        try:
            self.file.close()
        except OSError:
            pass
