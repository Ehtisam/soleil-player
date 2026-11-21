"""Çalma durumu: kuyruk, çalan şarkı, süre, karışık/tekrar, beğeniler.

Dosyası olan şarkılar (yerel müzik, Medya / Ses) mpv ile gerçekten çalınır
(audio.py). Dosyası olmayanlar (şimdilik Spotify örnek verisi) ya da mpv
yoksa çalma sahte: süre kendi kendine ilerler, ses çıkmaz. Spotify
bağlanınca aynı arayüzle raspotify/Spotipy'ye komut gönderen kısım
gelecek; ekranlar değişmeyecek.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class Track:
    title: str
    artist: str
    album: str = "Single"
    duration: float = 200.0   # saniye
    # Örnek veri için yer tutucu sözler: (başlangıç saniyesi, satır).
    # Gerçek sözler lyrics.py ile bulunur.
    lyrics: tuple[tuple[float, str], ...] = ()
    spotify_id: Optional[str] = None
    path: Optional[Path | str] = None   # yerel dosya ya da yayın adresi
    source: str = "SPOTIFY"          # oynatıcıda [SRC: ...]
    quality: str = "320 KBPS"        # oynatıcıda [QUAL: ...]
    live: bool = False               # canlı yayın (radyo): süre yok, sarılamaz
    ref: Optional[str] = None        # kaynaktaki kimlik (ör. radyo istasyonu)


REPEAT_MODES = ("off", "all", "one")


@dataclass
class Playback:
    queue: list[Track] = field(default_factory=list)
    index: int = 0
    position: float = 0.0
    playing: bool = False
    shuffle: bool = False
    repeat: str = "off"
    engine: object = None            # audio.AudioEngine ya da None
    volume: int = 80
    stream_lost: bool = False        # canlı yayın kesildi (uygulama bildirim gösterir)
    planned: Optional[int] = None    # şarkı bitince çalacak sıra (None: kuyruk bitti)
    _plan_key: tuple = ()

    @property
    def current(self) -> Track | None:
        return self.queue[self.index] if self.queue else None

    @property
    def source(self) -> str:
        return self.current.source if self.current else ""

    @property
    def quality(self) -> str:
        return self.current.quality if self.current else ""

    @property
    def live(self) -> bool:
        return bool(self.current and self.current.live)

    @property
    def now_playing(self) -> str:
        """Canlı yayında o an çalan şarkı (yayın gönderiyorsa)."""
        if self.live and self._real():
            from .radio import _clean
            return _clean(self.engine.stream_title)
        return ""

    def _real(self, track: Optional[Track] = None) -> bool:
        """Bu şarkı gerçekten mpv ile mi çalıyor?"""
        track = track or self.current
        return bool(self.engine and track and track.path)

    def _plan_next(self) -> Optional[int]:
        """Bu şarkı bitince hangisi çalacak (karışık ve tekrar ayarına göre)."""
        n = len(self.queue)
        if not n:
            return None
        if self.repeat == "one":
            return self.index
        if self.shuffle and n > 1:
            return random.choice([i for i in range(n) if i != self.index])
        if self.index + 1 < n:
            return self.index + 1
        return 0 if self.repeat == "all" else None

    def _refresh_plan(self) -> None:
        """Sıradakini yeniden hesaplar ve gerçek çalmada mpv'ye önceden verir."""
        self._plan_key = (self.index, self.shuffle, self.repeat, len(self.queue))
        self.planned = self._plan_next()
        if self._real() and not self.current.live:
            nxt = self.queue[self.planned] if self.planned is not None else None
            self.engine.set_next(nxt.path if nxt and nxt.path and not nxt.live else None)

    def _start_current(self) -> None:
        """Kuyruktaki şarkıyı baştan başlatır (gerçekse motora yükler)."""
        self.position = 0.0
        if self._real():
            self.engine.load(self.current.path, paused=not self.playing)
            self.engine.set_volume(self.volume)
        elif self.engine and self.engine.loaded:
            self.engine.stop()
        self._refresh_plan()

    # -- komutlar ------------------------------------------------------------------

    def cycle_repeat(self) -> None:
        self.repeat = REPEAT_MODES[(REPEAT_MODES.index(self.repeat) + 1) % len(REPEAT_MODES)]

    def seek(self, seconds: float) -> None:
        t = self.current
        if t and not t.live:
            self.position = max(0.0, min(t.duration, seconds))
            if self._real():
                self.engine.seek(self.position)

    def play_queue(self, tracks: list[Track], index: int) -> None:
        self.queue = list(tracks)
        self.index = index
        self.playing = True
        self._start_current()

    def toggle(self) -> None:
        if not self.queue:
            return
        self.playing = not self.playing
        if self._real():
            if self.engine.loaded != self.current.path:     # bitmiş şarkı: baştan
                self._start_current()
            self.engine.set_paused(not self.playing)

    def set_volume(self, volume: int) -> None:
        self.volume = volume
        if self.engine:
            self.engine.set_volume(volume)

    def next(self) -> None:
        if not self.queue:
            return
        if self.shuffle and len(self.queue) > 1:
            self.index = random.choice([i for i in range(len(self.queue)) if i != self.index])
        else:
            self.index = (self.index + 1) % len(self.queue)
        self._start_current()

    def previous(self) -> None:
        """İlk 3 saniyeden sonra şarkının başına, önce bir önceki şarkıya."""
        if not self.queue:
            return
        if self.position > 3 and not self.live:
            self.seek(0.0)
        else:
            self.index = (self.index - 1) % len(self.queue)
            self._start_current()

    def stop(self) -> None:
        self.playing = False
        if self.engine and self.engine.loaded:
            self.engine.stop()

    # -- zaman ---------------------------------------------------------------------

    def update(self, dt: float) -> None:
        t = self.current
        if not t:
            return
        if (self.index, self.shuffle, self.repeat, len(self.queue)) != self._plan_key:
            self._refresh_plan()          # karışık/tekrar değişti: sıradaki de değişir
        if self._real():
            pos = self.engine.position
            if pos is not None and self.engine.loaded == t.path:
                self.position = pos if t.live else min(t.duration, pos)
            if self.engine.take_ended():
                if t.live:              # yayın kesildi ya da açılamadı
                    self.playing = False
                    self.engine.loaded = None
                    self.stream_lost = True
                else:
                    self._track_finished()
            return
        if not self.playing:
            return
        self.position += dt
        if not t.live and self.position >= t.duration:
            self._track_finished()

    def _track_finished(self) -> None:
        nxt = self.planned
        if nxt is None:                         # kuyruk bitti
            self.position = self.current.duration
            self.playing = False
            if self.engine and self.engine.loaded:
                self.engine.loaded = None       # tekrar oynat'a basılınca baştan
            return
        gapless = (self._real() and self.engine.prefetched is not None
                   and self.engine.prefetched == self.queue[nxt].path)
        self.index = nxt
        if gapless:
            # mpv sıradakine kendisi geçti, yeniden yüklemeye gerek yok
            self.engine.advanced()
            self.position = 0.0
            self._refresh_plan()
        else:
            self._start_current()
