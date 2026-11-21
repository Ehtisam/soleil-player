"""Ses kaydı: mikrofondan okur, seviye ölçer, kaydı dosyaya yazar.

Mikrofon sounddevice (PortAudio) ile okunur: PC'de bilgisayarın
mikrofonu, Pi'de INMP441 (I2S, ALSA üzerinden) aynı kodla.

Kayıt önce WAV olarak yazılır, sonra arka planda mpv ile OGG'ye
dönüştürülür (dakikası ~5 MB yerine ~0.5 MB). Dönüştürme olmazsa WAV
kalır. Kayıtlar ~/.soleil/medya/ses içine gider: Medya / Ses'te de görünür.
"""

from __future__ import annotations

import threading
import time
import wave
from collections import deque
from pathlib import Path
from typing import Optional

import numpy as np

from . import config

RATE = 44100
BLOCK = 1024                  # ~23 ms; her blokta bir seviye ölçülür
FOLDER = config.MEDIA / "ses"
HISTORY = 160                 # dalga çiziminde tutulan seviye sayısı


def next_name() -> str:
    i = 1
    while any((FOLDER / f"Kayıt {i:03d}{ext}").exists() for ext in (".ogg", ".wav")):
        i += 1
    return f"Kayıt {i:03d}"


def encode_ogg(wav: Path, done=None) -> None:
    """WAV'ı arka planda OGG'ye çevirir; başarılıysa WAV silinir."""
    def work():
        target = wav.with_suffix(".ogg")
        try:
            from .audio import _import_mpv
            mpv = _import_mpv()
            player = mpv.MPV(o=str(target), oac="libvorbis", oacopts="q=4", video=False, terminal=False)
            player.play(str(wav))
            player.wait_for_playback()
            player.terminate()
            if target.exists() and target.stat().st_size > 0:
                wav.unlink(missing_ok=True)
        except Exception as e:
            print(f"[kayıt] ogg'ye çevrilemedi, wav kaldı: {e}")
            target.unlink(missing_ok=True)
        if done:
            done()
    threading.Thread(target=work, daemon=True).start()


class Recorder:
    """state: idle, recording, paused. Bloklar ses kartının thread'inde
    gelir; ekran sadece okur."""

    def __init__(self) -> None:
        self.state = "idle"
        self.blocks: list[np.ndarray] = []
        self.frames = 0
        self.level = 0.0                     # anlık seviye 0..1
        self.peak = 0.0                      # yavaş düşen tepe
        self.levels: deque[float] = deque(maxlen=HISTORY)
        self.error: Optional[str] = None
        self.last_saved: Optional[Path] = None
        self.encoding = False
        self._stream = None
        self._lock = threading.Lock()

    @property
    def elapsed(self) -> float:
        return self.frames / RATE

    # -- akış ----------------------------------------------------------------------

    def start(self) -> bool:
        """Yeni kayıt başlatır. Mikrofon açılamazsa False (error dolu)."""
        self.blocks, self.frames = [], 0
        self.levels.clear()
        self.error = None
        try:
            import sounddevice as sd
            self._stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16",
                                          blocksize=BLOCK, callback=self._callback)
            self._stream.start()
        except Exception as e:
            self._stream = None
            self.error = str(e) or "mikrofon yok"
            return False
        self.state = "recording"
        return True

    def _callback(self, indata, frames, time_info, status) -> None:
        self.feed(indata[:, 0].copy())

    def feed(self, samples: np.ndarray) -> None:
        """Bir blok ses (int16). Testlerde mikrofon yerine elle verilir."""
        rms = float(np.sqrt(np.mean((samples.astype(np.float32) / 32768.0) ** 2))) if len(samples) else 0.0
        level = min(1.0, (rms * 4) ** 0.6)          # konuşma da çubuğu doldursun
        with self._lock:
            self.level = level
            self.peak = max(level, self.peak * 0.97)
            if self.state == "recording":
                self.blocks.append(samples)
                self.frames += len(samples)
                self.levels.append(level)

    def toggle_pause(self) -> None:
        if self.state == "recording":
            self.state = "paused"
        elif self.state == "paused":
            self.state = "recording"

    def stop(self, save: bool = True) -> Optional[Path]:
        """Kaydı bitirir; save ise WAV yazar, OGG'ye çevirmeyi başlatır."""
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        with self._lock:
            blocks, self.blocks = self.blocks, []
            frames = self.frames
            self.state = "idle"
            self.level = self.peak = 0.0
        if not save or frames < RATE // 4:        # çeyrek saniyeden kısa: kaydetme
            return None
        FOLDER.mkdir(parents=True, exist_ok=True)
        path = FOLDER / f"{next_name()}.wav"
        data = np.concatenate(blocks).astype(np.int16)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes(data.tobytes())
        self.last_saved = path
        self.encoding = True

        def done():
            self.encoding = False
            ogg = path.with_suffix(".ogg")
            if ogg.exists() and not path.exists():
                self.last_saved = ogg
        encode_ogg(path, done)
        return path

    def wait_encoded(self, timeout: float = 10.0) -> None:
        end = time.time() + timeout
        while self.encoding and time.time() < end:
            time.sleep(0.05)
