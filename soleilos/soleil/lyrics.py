"""Şarkı sözü bulma.

Sıra: şarkının yanındaki .lrc dosyası (yerel müzik) → önbellek → LRCLIB →
Spotify'ın iç söz adresi (isteğe bağlı) → örnek satırlar.

- LRCLIB: ücretsiz, anahtar istemiyor. https://lrclib.net
- Spotify: resmi değil, kullanım şartlarına aykırı ve her an bozulabilir.
  Hesabın `sp_dc` çerezi ve `spotifyscraper` paketi gerekir; ikisi de yoksa
  bu adım atlanır. Çerez kodda değil, ~/.soleil/secrets.json içinde durur:
      {"spotify_sp_dc": "..."}
  (ya da SPOTIFY_SP_DC ortam değişkeni)

Arama arka planda yapılır, arayüz beklemez. Bulunan ve bulunamayan sözler
önbelleğe yazılır; aynı şarkı için tekrar internete çıkılmaz.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from . import config
from .playback import Track

USER_AGENT = "SoleilOS/0.1 (personal music player project)"   # HTTP başlığı: sadece ASCII
TIMEOUT = 8
MISSING_RETRY = 24 * 3600   # bulunamayan şarkıyı bir gün sonra tekrar dene

LRC_TIME = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")

Line = tuple[Optional[float], str]   # (başlangıç saniyesi ya da zamansızsa None, satır)


@dataclass(frozen=True)
class Lyrics:
    lines: tuple[Line, ...]
    synced: bool
    source: str
    instrumental: bool = False


def parse_lrc(text: str) -> tuple[Line, ...]:
    """LRC metnini (zaman, satır) listesine çevirir. Bir satırda birden
    fazla zaman olabilir: [00:12.00][01:30.00] nakarat"""
    lines = []
    for raw in text.splitlines():
        stamps = LRC_TIME.findall(raw)
        if not stamps:
            continue
        words = LRC_TIME.sub("", raw).strip()
        for m, s in stamps:
            lines.append((int(m) * 60 + float(s), words))
    lines.sort(key=lambda line: line[0])
    return tuple(lines)


def current_line(lyrics: Optional[Lyrics], position: float) -> int:
    """O an okunan satır: başlangıcı geçilmiş son satır."""
    if not lyrics or not lyrics.synced:
        return -1
    index = -1
    for i, (start, _) in enumerate(lyrics.lines):
        if start is not None and start <= position:
            index = i
    return index


# -- kaynaklar -----------------------------------------------------------------

class LrclibSource:
    name = "LRCLIB"
    URL = "https://lrclib.net/api/get"

    def fetch(self, track: Track) -> Optional[Lyrics]:
        params = {"artist_name": track.artist, "track_name": track.title, "duration": round(track.duration)}
        if track.album and track.album != "Single":
            params["album_name"] = track.album
        req = urllib.request.Request(f"{self.URL}?{urllib.parse.urlencode(params)}",
                                     headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                data = json.load(resp)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            raise
        if data.get("instrumental"):
            return Lyrics((), True, self.name, instrumental=True)
        if data.get("syncedLyrics"):
            return Lyrics(parse_lrc(data["syncedLyrics"]), True, self.name)
        if data.get("plainLyrics"):
            lines = tuple((None, line.strip()) for line in data["plainLyrics"].splitlines())
            return Lyrics(lines, False, self.name)
        return None


class SpotifySource:
    name = "SPOTIFY"

    def __init__(self) -> None:
        self.cookie = os.environ.get("SPOTIFY_SP_DC") or _read_secret("spotify_sp_dc")

    @property
    def available(self) -> bool:
        if not self.cookie:
            return False
        try:
            import spotify_scraper  # noqa: F401
        except ImportError:
            return False
        return True

    def fetch(self, track: Track) -> Optional[Lyrics]:
        if not track.spotify_id or not self.available:
            return None
        from spotify_scraper import SpotifyClient

        try:
            with SpotifyClient(cookies=self.cookie) as client:
                result = client.get_lyrics(track.spotify_id)
        except Exception as e:  # kütüphanenin NotFoundError'ı: şarkının sözü yok
            if type(e).__name__ == "NotFoundError":
                return None
            raise
        synced = result.sync_type == "LINE_SYNCED"
        lines = tuple(((line.start_ms / 1000) if synced else None, line.text) for line in result.lines)
        return Lyrics(lines, synced, self.name)


def _read_secret(key: str) -> Optional[str]:
    try:
        return json.loads(config.SECRETS.read_text(encoding="utf-8")).get(key)
    except (OSError, ValueError):
        return None


def _local_lrc(track: Track) -> Optional[Lyrics]:
    """Yerel şarkının yanında aynı adlı .lrc dosyası varsa onu okur."""
    if not track.path:
        return None
    lrc = track.path.with_suffix(".lrc")
    try:
        text = lrc.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError):
        return None
    lines = parse_lrc(text)
    if lines:
        return Lyrics(lines, True, "LRC DOSYASI")
    plain = tuple((None, line) for line in text.splitlines() if line.strip() and not line.startswith("["))
    return Lyrics(plain, False, "LRC DOSYASI") if plain else None


# -- önbellek ----------------------------------------------------------------

class LyricsCache:
    def __init__(self, folder: Path) -> None:
        self.folder = folder

    def _path(self, track: Track) -> Path:
        key = f"{track.artist}\n{track.title}\n{round(track.duration)}".lower()
        return self.folder / (hashlib.sha1(key.encode()).hexdigest()[:16] + ".json")

    def load(self, track: Track):
        """Lyrics, "missing" (yakın zamanda bulunamadı) ya da None (hiç bakılmadı)."""
        try:
            data = json.loads(self._path(track).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if data.get("missing"):
            return "missing" if time.time() - data["missing"] < MISSING_RETRY else None
        lines = tuple((t, text) for t, text in data["lines"])
        return Lyrics(lines, data["synced"], data["source"], data.get("instrumental", False))

    def save(self, track: Track, lyrics: Optional[Lyrics]) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        if lyrics is None:
            data = {"missing": time.time()}
        else:
            data = {"synced": lyrics.synced, "source": lyrics.source,
                    "instrumental": lyrics.instrumental, "lines": [list(line) for line in lyrics.lines]}
        self._path(track).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# -- servis ------------------------------------------------------------------

class LyricsService:
    """Ekranların kullandığı tek giriş: get(track) -> (durum, Lyrics)

    durum: "loading" (aranıyor), "found", "missing" (hiçbir yerde yok)
    """

    def __init__(self, online: bool = True) -> None:
        self.online = online
        self.cache = LyricsCache(config.CACHE / "lyrics")
        self.sources = [LrclibSource(), SpotifySource()]
        self._results: dict[Track, Optional[Lyrics]] = {}
        self._pending: set[Track] = set()
        self._lock = threading.Lock()

    def get(self, track: Optional[Track]) -> tuple[str, Optional[Lyrics]]:
        if track is None or track.live:     # radyoda söz aranmaz
            return "missing", None
        with self._lock:
            if track in self._results:
                return self._finish(track, self._results[track])
            if track in self._pending:
                return "loading", None

        local = _local_lrc(track)
        if local:
            with self._lock:
                self._results[track] = local
            return "found", local

        cached = self.cache.load(track)
        if isinstance(cached, Lyrics):
            with self._lock:
                self._results[track] = cached
            return "found", cached
        if cached == "missing" or not self.online:
            with self._lock:
                self._results[track] = None
            return self._finish(track, None)

        with self._lock:
            self._pending.add(track)
        threading.Thread(target=self._search, args=(track,), daemon=True).start()
        return "loading", None

    def _finish(self, track: Track, lyrics: Optional[Lyrics]) -> tuple[str, Optional[Lyrics]]:
        if lyrics:
            return "found", lyrics
        if track.lyrics:   # örnek veride yer tutucu satırlar var
            return "found", Lyrics(tuple(track.lyrics), True, "ÖRNEK")
        return "missing", None

    def _search(self, track: Track) -> None:
        found, failed = None, False
        for source in self.sources:
            try:
                found = source.fetch(track)
            except Exception as e:  # ağ hatası, kaynak bozuk vb.
                print(f"[sözler] {source.name}: {e}")
                failed = True
                continue
            if found:
                break
        if found or not failed:
            # Ağ hatasında önbelleğe "yok" yazma, sonra tekrar denensin
            self.cache.save(track, found)
        with self._lock:
            self._results[track] = found
            self._pending.discard(track)
