"""Görselleri arka planda yükler (ekran donmasın diye).

Pillow ile açılır: JPEG'ler çözülürken küçültülür (draft, Pi'de büyük
fotoğrafları çok hızlandırır), telefon fotoğraflarının EXIF yönü
düzeltilir, en uzun kenar MAX_SIDE'a indirilir. Ekran 320x480 olduğu için
daha büyüğü gereksiz; bellekte de az yer tutar.

Thread sadece ham pikselleri hazırlar; pygame yüzeyi ana döngüde kurulur.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from pathlib import Path
from typing import Optional

import pygame

MAX_SIDE = 480
CACHE_SIZE = 8


class ImageInfo:
    def __init__(self, size: tuple[int, int], mode: str, data: bytes) -> None:
        self.original_size = size     # dosyadaki çözünürlük
        self.mode = mode
        self.data = data              # küçültülmüş RGB/RGBA pikseller
        self.surface: Optional[pygame.Surface] = None
        self.scaled_size: tuple[int, int] = (0, 0)


def _decode(path: Path):
    from PIL import Image, ImageOps

    with Image.open(path) as img:
        original = img.size
        if img.getexif().get(0x0112) in (5, 6, 7, 8):   # EXIF: 90° dönük çekilmiş
            original = (original[1], original[0])
        img.draft("RGB", (MAX_SIDE, MAX_SIDE))      # sadece JPEG'de etkili
        img = ImageOps.exif_transpose(img)
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.getbands() or "transparency" in img.info else "RGB")
        img.thumbnail((MAX_SIDE, MAX_SIDE))
        return original, img.mode, img.size, img.tobytes()


class ImageLoader:
    """get(path) -> ("loading" | "ok" | "error", ImageInfo|None)."""

    def __init__(self) -> None:
        self._cache: OrderedDict[Path, object] = OrderedDict()
        self._pending: set[Path] = set()
        self._lock = threading.Lock()

    def get(self, path: Path):
        with self._lock:
            entry = self._cache.get(path)
            if entry is not None:
                self._cache.move_to_end(path)
        if entry is None:
            self.preload(path)
            return "loading", None
        if entry == "error":
            return "error", None
        info: ImageInfo = entry
        if info.surface is None:
            fmt = info.mode
            info.surface = pygame.image.frombuffer(info.data, info.scaled_size, fmt).copy()
            info.data = b""
        return "ok", info

    def preload(self, path: Path) -> None:
        with self._lock:
            if path in self._cache or path in self._pending:
                return
            self._pending.add(path)
        threading.Thread(target=self._load, args=(path,), daemon=True).start()

    def _load(self, path: Path) -> None:
        try:
            original, mode, size, data = _decode(path)
            info: object = ImageInfo(original, mode, data)
            info.scaled_size = size
        except Exception:
            info = "error"
        with self._lock:
            self._pending.discard(path)
            self._cache[path] = info
            while len(self._cache) > CACHE_SIZE:
                self._cache.popitem(last=False)

    def busy(self) -> bool:
        with self._lock:
            return bool(self._pending)
