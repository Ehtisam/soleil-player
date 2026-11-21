"""Ses motoru: mpv (libmpv) ile dosya ve yayın çalma.

Yerel müzik, Medya / Ses, radyo ve ses kayıtları bunu kullanır. Spotify
ayrı: onu raspotify (librespot) çalacak.

- Windows: libmpv-2.dll ~/.soleil/lib içinde (projede değil, büyük dosya).
- Pi: `sudo apt install libmpv2` + `pip install python-mpv`. Ses I2S DAC'a
  ALSA üzerinden gider.

mpv bulunamazsa create_engine() None döner; çalma sahte devam eder
(süre ilerler, ses çıkmaz) ve uygulama çalışmaya devam eder.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Optional

from . import config

# SOLEIL_HOME değiştirilse de (testler) asıl kullanıcı klasörüne de bakılır
LIB_DIRS = [config.DATA / "lib", Path.home() / ".soleil" / "lib"]


def _import_mpv():
    if sys.platform == "win32":
        for folder in LIB_DIRS:
            if (folder / "libmpv-2.dll").is_file():
                os.add_dll_directory(str(folder))
                os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
                break
    import mpv   # python-mpv
    return mpv


class AudioEngine:
    def __init__(self, mpv_module, silent: bool = False) -> None:
        options = dict(video=False, ytdl=False, input_default_bindings=False,
                       input_vo_keyboard=False, terminal=False, audio_display="no",
                       gapless_audio="weak", keep_open="no", idle=True)
        if silent:
            options["ao"] = "null"          # testlerde ses çıkmasın
        self._mpv = mpv_module.MPV(**options)
        self._ended = threading.Event()
        self.loaded: Optional[Path] = None
        self.prefetched: Optional[Path] = None   # boşluksuz geçiş için sırada bekleyen
        self.error = False

        @self._mpv.event_callback("end-file")
        def _on_end(event):
            data = getattr(event, "data", None)
            reason = getattr(data, "reason", None)
            if reason == mpv_module.MpvEventEndFile.ERROR:
                self.error = True
            # Dosya bitti ya da açılamadı: sıradakine geçilsin. Durdurma
            # (load/stop ile değiştirme) sayılmaz.
            if reason in (mpv_module.MpvEventEndFile.EOF, mpv_module.MpvEventEndFile.ERROR):
                self._ended.set()

    # -- komutlar ------------------------------------------------------------------

    def load(self, path: Path | str, start: float = 0.0, paused: bool = False,
             next_path: Path | str | None = None) -> None:
        self._ended.clear()
        self.error = False
        self.loaded = path
        self.prefetched = None
        self._mpv.pause = paused
        if start > 0:
            self._mpv.loadfile(str(path), start=f"{start:.2f}")
        else:
            self._mpv.loadfile(str(path))
        if next_path:
            self.set_next(next_path)

    def set_next(self, path: Path | str | None) -> None:
        """Sıradaki dosyayı mpv'ye önceden verir: çalan bitince araya
        sessizlik girmeden ona geçer (boşluksuz albüm). None: sıra boş."""
        if path == self.prefetched:
            return
        try:
            self._mpv.command("playlist-clear")     # çalan hariç listeyi temizler
            if path:
                self._mpv.loadfile(str(path), "append")
        except Exception:
            path = None
        self.prefetched = path

    def advanced(self) -> None:
        """mpv önceden verilen dosyaya geçti."""
        self.loaded, self.prefetched = self.prefetched, None

    def stop(self) -> None:
        self.loaded = None
        self.prefetched = None
        self._mpv.command("stop")

    def set_paused(self, paused: bool) -> None:
        self._mpv.pause = paused

    def seek(self, seconds: float) -> None:
        if self.loaded:
            try:
                self._mpv.seek(max(0.0, seconds), reference="absolute", precision="exact")
            except Exception:
                pass

    def set_output(self, device: str) -> None:
        """Ses çıkışı: "auto" (cihazın kendi çıkışı) ya da Bluetooth (bluez-alsa)."""
        try:
            self._mpv.audio_device = device
        except Exception as e:
            print(f"[ses] çıkış değiştirilemedi ({device}): {e}")

    def set_volume(self, volume: int) -> None:
        self._mpv.volume = max(0, min(100, volume))

    # -- durum ---------------------------------------------------------------------

    @property
    def position(self) -> Optional[float]:
        try:
            return self._mpv.time_pos
        except Exception:
            return None

    @property
    def duration(self) -> Optional[float]:
        try:
            return self._mpv.duration
        except Exception:
            return None

    @property
    def stream_title(self) -> str:
        """Radyo yayınının gönderdiği "Sanatçı - Şarkı" (ICY), yoksa boş."""
        try:
            meta = self._mpv.metadata or {}
        except Exception:
            return ""
        for key in ("icy-title", "title", "StreamTitle"):
            for k, v in meta.items():
                if k.lower() == key.lower() and str(v).strip():
                    return str(v).strip()
        return ""

    def take_ended(self) -> bool:
        """Çalan dosya bittiyse bir kez True döner."""
        if self._ended.is_set():
            self._ended.clear()
            return True
        return False

    def close(self) -> None:
        try:
            self._mpv.terminate()
        except Exception:
            pass


def create_engine(silent: bool = False) -> Optional[AudioEngine]:
    try:
        return AudioEngine(_import_mpv(), silent=silent)
    except Exception as e:     # mpv kurulu değil, DLL yok vb.
        print(f"[ses] mpv açılamadı, çalma sahte devam edecek: {e}")
        return None
