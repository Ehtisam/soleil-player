"""Donanım katmanı: PC'de taklit, Pi'de gerçek.

  ekran   : PC penceresi (display.py) | SPI ekranın framebuffer'ı (framebuffer.py)
  tuşlar  : klavye (input.py)         | GPIO tuşlar ve encoder (gpio_input.py)
  ışıklar : penceredeki ön yüz        | WS2812B çubuklar (leds.py)
  sistem  : hiçbir şey yapmaz          | Wi-Fi/BT aç-kapa, kapatma (system.py)

Hangisinin kullanılacağı detect() ile seçilir; main.py --cihaz ile
zorlanabilir.
"""

from __future__ import annotations

from pathlib import Path


def is_raspberry_pi() -> bool:
    try:
        return "raspberry pi" in Path("/proc/device-tree/model").read_text(errors="ignore").lower()
    except OSError:
        return False


def detect() -> str:
    return "pi" if is_raspberry_pi() else "pc"
