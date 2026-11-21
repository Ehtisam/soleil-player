"""Kalıcı ayarlar: ~/.soleil/settings.json

Bir ayar değişince hemen kaydedilir; cihaz kapanıp açılınca aynen gelir.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields

from .lang import _
from . import config

PATH = config.DATA / "settings.json"

BRIGHTNESS_STEPS = (20, 40, 60, 80, 100)
SLEEP_STEPS = (15, 30, 60, 300, 0)          # saniye; 0 = hiç kapanmasın
LED_MODES = ("KAPALI", "SES", "İLERLEME", "VU METRE")
READER_SIZES = ("KÜÇÜK", "ORTA", "BÜYÜK")  # notlar ve e-kitaplardaki yazı


@dataclass
class Settings:
    theme: str = "amber"
    brightness: int = 80          # yüzde; Pi'de ekran ışığı, PC'de önizleme
    sleep_after: int = 60         # saniye boyunca tuşa basılmazsa ekran kapanır
    led_mode: str = "VU METRE"
    boot_animation: bool = True
    wifi: bool = True
    bluetooth: bool = True
    volume: int = 80
    reader_size: str = "ORTA"
    image_tint: bool = False      # görselleri tema renginde tek renk göster
    language: str = "tr"          # arayüz dili: "tr" ya da assets/dil/ altındaki bir klasör

    @classmethod
    def load(cls) -> "Settings":
        try:
            data = json.loads(PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self) -> None:
        try:
            PATH.parent.mkdir(parents=True, exist_ok=True)
            PATH.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            print(f"[ayarlar] kaydedilemedi: {e}")


def next_in(options, current):
    """Seçenekler arasında bir sonrakine geçer (sonda başa döner)."""
    options = list(options)
    i = options.index(current) if current in options else -1
    return options[(i + 1) % len(options)]


def sleep_label(seconds: int) -> str:
    if seconds == 0:
        return "KAPALI"
    return _("{n} SN").format(n=seconds) if seconds < 60 else _("{n} DK").format(n=seconds // 60)
