"""İnternet radyosu: istasyon listeleri ve favoriler.

İstasyonlar Radio Browser dizininden gelir (https://www.radio-browser.info):
ücretsiz, anahtar istemiyor, topluluk güncel tutuyor; bozuk yayınlar
işaretli olduğu için ayıklanıyor. Listeler arka planda çekilir ve bir gün
önbellekte tutulur (internet yoksa eski liste gösterilir).

Favoriler ~/.soleil/radyo.json içinde. Yayınları mpv çalar (audio.py).
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

from . import config
from .lyrics import USER_AGENT
from .playback import Track

MIRRORS = ["de1.api.radio-browser.info", "de2.api.radio-browser.info",
           "fi1.api.radio-browser.info", "nl1.api.radio-browser.info"]
TIMEOUT = 8
LIMIT = 60
CACHE_DIR = config.CACHE / "radyo"
CACHE_TTL = 24 * 3600
FAVORITES_PATH = config.DATA / "radyo.json"

# Hazır listeler: anahtar -> arama parametreleri
LISTS = {
    "tr": {"countrycode": "TR"},
    "world": {},
}


def _clean(text: str) -> str:
    """Fontta olmayan karakterleri (emoji vb.) atar."""
    text = "".join(ch for ch in text if ch.isprintable() and ord(ch) < 0x250)
    return " ".join(text.split())


def station_track(s: dict) -> Optional[Track]:
    url = s.get("url_resolved") or s.get("url")
    name = _clean(s.get("name", ""))
    if not url or not name:
        return None
    tags = [_clean(t) for t in s.get("tags", "").split(",") if _clean(t)]
    country = s.get("countrycode") or ""
    codec = (s.get("codec") or "").upper()
    if codec == "UNKNOWN":
        codec = ""
    bitrate = s.get("bitrate") or 0
    quality = f"{codec} {bitrate}K".strip() if bitrate else (codec or "YAYIN")
    album = " · ".join(([country] if country else []) + tags[:2]) or "Radyo"
    return Track(name, country or "Radyo", album, 0.0, path=url, source="RADYO",
                 quality=quality, live=True, ref=s.get("stationuuid") or url)


def _fetch(params: dict) -> list[dict]:
    query = {"order": "clickcount", "reverse": "true", "limit": str(LIMIT), "hidebroken": "true", **params}
    last_error = None
    for host in MIRRORS:
        url = f"https://{host}/json/stations/search?" + urllib.parse.urlencode(query)
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:      # sunucu kapalı: sıradakini dene
            last_error = e
    raise last_error or OSError("radyo dizinine ulaşılamadı")


class RadioDirectory:
    """get(anahtar) -> (durum, istasyonlar). durum: loading, ready, error.
    Anahtar: "tr", "world" ya da "ara:<sorgu>"."""

    def __init__(self, online: bool = True, save: bool = True) -> None:
        self.online = online
        self.save = save
        self._lists: dict[str, tuple[str, list[Track]]] = {}
        self._raw: dict[str, dict] = {}      # istasyon kimliği -> dizindeki ham kayıt
        self._lock = threading.Lock()
        self.changed = False
        self.favorites: list[Track] = self._load_favorites()

    # -- listeler ------------------------------------------------------------------

    def _cache_path(self, key: str) -> Path:
        return CACHE_DIR / (hashlib.sha1(key.encode()).hexdigest()[:12] + ".json")

    def get(self, key: str) -> tuple[str, list[Track]]:
        with self._lock:
            if key in self._lists:
                return self._lists[key]
            self._lists[key] = ("loading", [])
        threading.Thread(target=self._load, args=(key,), daemon=True).start()
        return "loading", []

    def _load(self, key: str) -> None:
        path = self._cache_path(key)
        cached = None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            cached = data["stations"]
            fresh = time.time() - data["time"] < CACHE_TTL
        except (OSError, ValueError, KeyError):
            fresh = False
        stations = cached
        if not fresh and self.online:
            params = {"name": key[4:]} if key.startswith("ara:") else LISTS.get(key, {})
            try:
                stations = _fetch(params)
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"time": time.time(), "stations": stations}, ensure_ascii=False),
                                encoding="utf-8")
            except Exception as e:
                print(f"[radyo] liste alınamadı: {e}")
        if stations is None:
            result = ("error", [])
        else:
            tracks, seen = [], set()
            for s in stations:
                t = station_track(s)
                if t and t.path not in seen:
                    seen.add(t.path)
                    tracks.append(t)
                    self._raw[t.ref] = s
            result = ("ready", tracks)
        with self._lock:
            self._lists[key] = result
            self.changed = True

    def forget(self, key: str) -> None:
        with self._lock:
            self._lists.pop(key, None)

    # -- favoriler -----------------------------------------------------------------

    def _load_favorites(self) -> list[Track]:
        try:
            data = json.loads(FAVORITES_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return []
        tracks = []
        for s in data if isinstance(data, list) else []:
            t = station_track(s)
            if t:
                tracks.append(t)
                self._raw[t.ref] = s
        return tracks

    def is_favorite(self, track: Track) -> bool:
        return any(f.ref == track.ref for f in self.favorites)

    def toggle_favorite(self, track: Track) -> bool:
        """Favorilere ekler ya da çıkarır; eklendiyse True."""
        if self.is_favorite(track):
            self.favorites = [f for f in self.favorites if f.ref != track.ref]
            added = False
        else:
            self.favorites.append(track)
            added = True
        if self.save:
            raw = [self._raw.get(f.ref, {"name": f.title, "url_resolved": f.path, "stationuuid": f.ref})
                   for f in self.favorites]
            try:
                FAVORITES_PATH.parent.mkdir(parents=True, exist_ok=True)
                FAVORITES_PATH.write_text(json.dumps(raw,
                                                     ensure_ascii=False, indent=2), encoding="utf-8")
            except OSError:
                pass
        return added
