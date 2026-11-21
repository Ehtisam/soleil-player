"""Örnek veri. Şarkı ve playlist adları Figma'dan; Spotify ve SD kart
bağlanınca bu dosyanın yerini gerçek veri alacak.

Söz satırları gerçek şarkı sözü değil, yer tutucu.
"""

from __future__ import annotations

from dataclasses import dataclass

from .playback import Track

FILLER_LYRICS = (
    "gece yavaşça dönerken",
    "sokak lambası titrer",
    "bir şarkı kalır geriye",
    "adını fısıldar rüzgar",
    "ayak sesleri yankılanır",
    "ışıklar bir bir söner",
    "kimse bilmez nereye",
    "yol uzar karanlıkta",
    "bir nota düşer yere",
    "sabah gelir sessizce",
    "melodi devam eder",
    "ve şehir uyanır",
)


def _timed(duration: float) -> tuple[tuple[float, str], ...]:
    """Yer tutucu satırlara şarkıya yayılmış sahte zamanlar verir."""
    intro = 8.0
    step = (duration - intro - 10) / len(FILLER_LYRICS)
    return tuple((intro + i * step, line) for i, line in enumerate(FILLER_LYRICS))


def _t(title: str, artist: str, duration: float, album: str = "Single") -> Track:
    return Track(title, artist, album, duration, _timed(duration))


@dataclass(frozen=True)
class Playlist:
    name: str
    description: str
    tracks: tuple[Track, ...]


A_KING = Playlist(
    name="A King never doubts,",
    description="A king never yields. A king never relies on others. A king.. never gives up!",
    tracks=(
        _t("choose your fighter", "NewEra", 187),
        _t("Number One", "Shiro SAGISU", 154),
        _t("Judas - 80s Ver.", "GABRIELLA RAELYN", 212),
        _t("L'altra dimensione", "Maneskin", 166),
        _t("GOSSIP (feat. Tom Morello)", "Maneskin", 168),
        _t("I Was Made For Lovin' You", "KISS", 271),
        _t("Billie Jean", "Michael Jackson", 294, album="Thriller"),
        _t("ZITTI E BUONI", "Maneskin", 195),
        _t("Without Me", "Eminem", 290),
        _t("All That Glitters", "Earl", 203),
        _t("Everyday Normal Guy 2", "Jon Lajoie", 219),
    ),
)

# Kütüphanedeki playlistler: (ad, içerik ya da henüz yoksa None)
LIBRARY = [
    ("Beğenilen Şarkılar", None),
    ("A King never doubts", A_KING),
    ("Lead them all", None),
    ("TWO SHOTS", None),
    ("Autistic Burnout", None),
    ("Perfect Lasagna", None),
]
