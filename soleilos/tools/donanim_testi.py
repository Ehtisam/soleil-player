"""Pi'de parçaları tek tek dener (parçalar gelince, lehimden sonra).

  sudo /opt/soleil/venv/bin/python tools/donanim_testi.py ekran
  sudo /opt/soleil/venv/bin/python tools/donanim_testi.py tuslar
  sudo /opt/soleil/venv/bin/python tools/donanim_testi.py isik
  sudo /opt/soleil/venv/bin/python tools/donanim_testi.py ses
  sudo /opt/soleil/venv/bin/python tools/donanim_testi.py mikrofon

Önce `sudo systemctl stop soleil` (SoleilOS aynı parçaları kullanıyor).
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np  # noqa: E402
import pygame  # noqa: E402


def ekran() -> None:
    """Renk şeritleri ve köşe işaretleri: döndürme ve renk sırası doğru mu?"""
    from soleil.hw.framebuffer import FramebufferDisplay, find_framebuffer
    pygame.init()
    pygame.display.set_mode((1, 1))
    print("framebuffer:", find_framebuffer((320, 480)))
    d = FramebufferDisplay((320, 480))
    print("boyut:", d.fb_size, "döndürme:", d.rotate)
    s = pygame.Surface((320, 480))
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 255), (196, 124, 54)]
    for i, c in enumerate(colors):
        s.fill(c, (0, i * 80, 320, 80))
    s.fill((255, 255, 0), (0, 0, 40, 40))        # sol üst köşe sarı
    font = pygame.font.Font(None, 36)
    s.blit(font.render("UST  (kirmizi)", True, (0, 0, 0)), (50, 25))
    s.blit(font.render("ALT", True, (0, 0, 0)), (130, 440))
    d.present(s)
    print("Beklenen: üstten kırmızı, yeşil, mavi, beyaz, amber; sol üstte sarı kare.")
    print("Renkler karışıksa (kırmızı yerine mavi) sürücü BGR, söyle düzeltelim.")
    time.sleep(10)
    d.present_off()


def tuslar() -> None:
    from soleil.hw.gpio_input import GpioInput
    g = GpioInput()
    print("Tuşlara bas, encoder'ı çevir (Ctrl+C ile çık).")
    try:
        while True:
            for a in g.poll():
                print(" ", a.name)
            time.sleep(0.01)
    except KeyboardInterrupt:
        g.close()


def isik() -> None:
    from soleil.hw.leds import Ws281xStrip
    from soleil.hw import pins
    strip = Ws281xStrip()
    n = pins.LED_PER_BAR
    amber = (196, 124, 54)
    print("Her LED sırayla: önce sol çubuk (logodan dışa), sonra sağ.")
    for side in ("sol", "sag"):
        for i in range(n):
            left = [(0, 0, 0)] * n
            right = [(0, 0, 0)] * n
            (left if side == "sol" else right)[i] = amber
            strip.show(left, right)
            print(f"  {side} {i}")
            time.sleep(0.4)
    strip.close()
    print("Sol çubuk dıştan içe yandıysa pins.LED_REVERSED_LEFT ters çevrilecek.")


def ses() -> None:
    from soleil.audio import create_engine
    import tempfile
    import wave
    sr = 44100
    t = np.arange(sr * 2) / sr
    tone = (0.3 * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    path = Path(tempfile.mkdtemp()) / "ton.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(tone.tobytes())
    eng = create_engine()
    if eng is None:
        print("mpv açılamadı"); return
    eng.set_volume(60)
    eng.load(path)
    print("2 sn 440 Hz ton çalıyor (hoparlör ve kulaklık)...")
    time.sleep(2.5)
    eng.close()


def mikrofon() -> None:
    import sounddevice as sd
    print("Giriş aygıtı:", sd.query_devices(kind="input")["name"])
    print("5 sn seviye (konuş):")
    with sd.InputStream(samplerate=44100, channels=1, dtype="int16") as stream:
        end = time.time() + 5
        while time.time() < end:
            data, _ = stream.read(2048)
            rms = float(np.sqrt(np.mean((data.astype(np.float32) / 32768) ** 2)))
            print("  " + "#" * int(min(1.0, rms * 8) * 40))


TESTS = {"ekran": ekran, "tuslar": tuslar, "isik": isik, "ses": ses, "mikrofon": mikrofon}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in TESTS:
        print(__doc__)
        sys.exit(1)
    TESTS[sys.argv[1]]()
