"""Beğenilen şarkılar: ~/.soleil/begeniler.json

Şarkı bir anahtarla tutulur: yerel dosyada dosya yolu, Spotify'da şarkı
kimliği (bağlantı yapılınca), örnek veride ad + sanatçı. Radyo
istasyonları burada değil, radio.py'deki favorilerde.
"""

from __future__ import annotations

import json

from . import config
from .playback import Track

PATH = config.DATA / "begeniler.json"


def track_key(track: Track) -> str:
    if track.path and not track.live:
        return f"dosya:{track.path}"
    if track.spotify_id:
        return f"spotify:{track.spotify_id}"
    return f"ad:{track.artist}|{track.title}"


class Likes:
    def __init__(self, save: bool = True) -> None:
        self.save_enabled = save
        self.keys: list[str] = []
        if save:
            try:
                data = json.loads(PATH.read_text(encoding="utf-8"))
                self.keys = [k for k in data if isinstance(k, str)]
            except (OSError, ValueError, TypeError):
                pass

    def has(self, track: Track | None) -> bool:
        return track is not None and track_key(track) in self.keys

    def toggle(self, track: Track) -> bool:
        """Beğenir ya da beğeniyi kaldırır; beğenildiyse True."""
        key = track_key(track)
        if key in self.keys:
            self.keys.remove(key)
            liked = False
        else:
            self.keys.append(key)
            liked = True
        if self.save_enabled:
            try:
                PATH.parent.mkdir(parents=True, exist_ok=True)
                PATH.write_text(json.dumps(self.keys, ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
        return liked
