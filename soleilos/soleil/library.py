"""Yerel müzik kütüphanesi: ~/.soleil/medya/muzik (alt klasörler dahil) ve
assets/ornek/muzik.

Etiketler (ad, sanatçı, albüm, sıra, yıl) ve süre mutagen ile okunur.
Tarama arka planda yapılır; sonuçlar ~/.soleil/cache/kutuphane.json'a
yazılır, değişmeyen dosyalar bir dahaki açılışta tekrar okunmaz (Pi'de
yüzlerce dosyada fark eder).

Kapaklar (covers): önce dosyanın içindeki resim, yoksa klasördeki
cover/folder/front.jpg|png. Arka planda çözülür, 160 px'e küçültülür.
"""

from __future__ import annotations

import base64
import io
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pygame

from . import config
from .documents import AUDIO_EXTENSIONS
from .playback import Track

FOLDERS = [(config.MEDIA / "muzik", False), (config.SAMPLES / "muzik", True)]
CACHE_PATH = config.CACHE / "kutuphane.json"
COVER_NAMES = ("cover", "folder", "front", "kapak", "album")
COVER_SIZE = 160
UNKNOWN_ARTIST = "Bilinmeyen Sanatçı"
UNKNOWN_ALBUM = "Bilinmeyen Albüm"


@dataclass(frozen=True)
class Album:
    name: str
    artist: str
    year: str
    tracks: tuple[Track, ...]


def _first(tags, key: str) -> str:
    try:
        value = tags.get(key)
    except Exception:
        return ""
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value or "").strip()


def _quality(audio, path: Path) -> str:
    ext = path.suffix.lower().lstrip(".").upper()
    info = audio.info
    bitrate = getattr(info, "bitrate", 0) or 0
    if ext in ("FLAC", "WAV"):
        rate = getattr(info, "sample_rate", 0)
        return f"{ext} {rate / 1000:g}K" if rate else ext
    return f"{ext} {round(bitrate / 1000)}K" if bitrate else ext


def read_track(path: Path, sample: bool) -> Optional[dict]:
    import mutagen

    try:
        audio = mutagen.File(path, easy=True)
    except Exception:
        audio = None
    if audio is None or audio.info is None:
        return None
    tags = audio.tags or {}
    number = _first(tags, "tracknumber").split("/")[0]
    return {
        "title": _first(tags, "title") or path.stem,
        "artist": _first(tags, "artist") or _first(tags, "albumartist") or UNKNOWN_ARTIST,
        "album": _first(tags, "album") or UNKNOWN_ALBUM,
        "number": int(number) if number.isdigit() else 0,
        "year": _first(tags, "date")[:4],
        "duration": float(audio.info.length or 0),
        "quality": _quality(audio, path),
        "sample": sample,
    }


class Library:
    def __init__(self, enabled_cache: bool = True) -> None:
        self.enabled_cache = enabled_cache
        self.state = "idle"             # idle, scanning, ready
        self.progress = 0.0
        self.tracks: list[Track] = []
        self.albums: list[Album] = []
        self.artists: dict[str, list[Album]] = {}
        self.version = 0                # her taramada artar (ekranlar yenilensin)
        self._lock = threading.Lock()

    def ensure_scanned(self) -> None:
        with self._lock:
            if self.state != "idle":
                return
            self.state = "scanning"
        threading.Thread(target=self._scan, daemon=True).start()

    def rescan(self) -> None:
        with self._lock:
            if self.state == "scanning":
                return
            self.state = "idle"
        self.ensure_scanned()

    def _scan(self) -> None:
        cache = {}
        if self.enabled_cache:
            try:
                cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cache = {}
        files = []
        for folder, sample in FOLDERS:
            if folder.is_dir():
                files += [(p, sample) for p in folder.rglob("*")
                          if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS]
        new_cache, tracks = {}, []
        for i, (path, sample) in enumerate(files):
            st = path.stat()
            key = str(path)
            stamp = [st.st_mtime, st.st_size]
            entry = cache.get(key)
            if not entry or entry.get("stamp") != stamp:
                info = read_track(path, sample)
                entry = {"stamp": stamp, "info": info}
            new_cache[key] = entry
            if entry["info"]:
                d = entry["info"]
                tracks.append((d, Track(d["title"], d["artist"], d["album"], d["duration"],
                                        path=path, source="YEREL", quality=d["quality"])))
            self.progress = (i + 1) / max(1, len(files))
        if self.enabled_cache:
            try:
                CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                CACHE_PATH.write_text(json.dumps(new_cache, ensure_ascii=False), encoding="utf-8")
            except OSError:
                pass
        self._build(tracks)

    def _build(self, items: list[tuple[dict, Track]]) -> None:
        groups: dict[tuple[str, str], list[tuple[dict, Track]]] = {}
        for d, track in items:
            groups.setdefault((d["album"], d["artist"]), []).append((d, track))
        albums = []
        for (name, artist), entries in groups.items():
            entries.sort(key=lambda e: (e[0]["number"] or 999, str(e[1].path).casefold()))
            year = next((d["year"] for d, _ in entries if d["year"]), "")
            albums.append(Album(name, artist, year, tuple(t for _, t in entries)))
        albums.sort(key=lambda a: (a.artist.casefold(), a.year, a.name.casefold()))
        artists: dict[str, list[Album]] = {}
        for album in albums:
            artists.setdefault(album.artist, []).append(album)
        tracks = [t for album in albums for t in album.tracks]
        with self._lock:
            self.albums, self.artists = albums, dict(sorted(artists.items(), key=lambda kv: kv[0].casefold()))
            self.tracks = sorted(tracks, key=lambda t: t.title.casefold())
            self.state = "ready"
            self.version += 1


# -- kapaklar ------------------------------------------------------------------

def _embedded_cover(path: Path) -> Optional[bytes]:
    import mutagen

    try:
        audio = mutagen.File(path)
    except Exception:
        return None
    if audio is None:
        return None
    tags = audio.tags
    pictures = getattr(audio, "pictures", None)        # FLAC
    if pictures:
        return pictures[0].data
    if tags is None:
        return None
    if hasattr(tags, "getall"):                         # MP3 (ID3)
        apic = tags.getall("APIC")
        if apic:
            return apic[0].data
    for key in ("metadata_block_picture", "METADATA_BLOCK_PICTURE"):   # OGG
        try:
            values = tags.get(key)
        except Exception:
            values = None
        if values:
            from mutagen.flac import Picture
            return Picture(base64.b64decode(values[0])).data
    covr = tags.get("covr") if hasattr(tags, "get") else None          # M4A
    if covr:
        return bytes(covr[0])
    return None


def _folder_cover(path: Path) -> Optional[bytes]:
    for p in path.parent.iterdir():
        if p.is_file() and p.stem.lower() in COVER_NAMES and p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            return p.read_bytes()
    return None


class Covers:
    """get(track) -> pygame.Surface (kare, COVER_SIZE) ya da None (yok / hazırlanıyor)."""

    def __init__(self) -> None:
        self._done: dict[Path, Optional[tuple[bytes, tuple[int, int]]]] = {}
        self._surfaces: dict[Path, Optional[pygame.Surface]] = {}
        self._pending: set[Path] = set()
        self._lock = threading.Lock()
        self.changed = False            # yeni kapak hazır: ekran yeniden çizilsin

    @staticmethod
    def _key(track: Track) -> Optional[Path]:
        return track.path if track and track.path else None

    def get(self, track: Track) -> Optional[pygame.Surface]:
        key = self._key(track)
        if key is None:
            return None
        if key in self._surfaces:
            return self._surfaces[key]
        with self._lock:
            if key in self._done:
                raw = self._done.pop(key)
                surf = pygame.image.frombuffer(raw[0], raw[1], "RGB").copy() if raw else None
                self._surfaces[key] = surf
                return surf
            if key in self._pending:
                return None
            self._pending.add(key)
        threading.Thread(target=self._load, args=(key,), daemon=True).start()
        return None

    def _load(self, path: Path) -> None:
        result = None
        try:
            data = _embedded_cover(path) or _folder_cover(path)
            if data:
                from PIL import Image, ImageOps
                img = Image.open(io.BytesIO(data)).convert("RGB")
                img = ImageOps.fit(img, (COVER_SIZE, COVER_SIZE))
                result = (img.tobytes(), img.size)
        except Exception:
            result = None
        with self._lock:
            self._pending.discard(path)
            self._done[path] = result
            self.changed = True
