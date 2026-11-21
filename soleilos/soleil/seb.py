"""Takvim-i Şeb: kullanıcının gece takvimi.

- Gece sayılır, gün değil. Gece öğlen 12:00'de değişir: öğlenden ertesi
  öğlene kadar, o akşamın miladi tarihiyle anılan gece (night_date).
- Yıl 23 Aralık'ta başlar. Yıl 0 (İnşa) = 23 Aralık 2025 – 22 Aralık 2026.
  Öncesi Yıl -1, -2... Resmî yazımda "BS" (Büyük Buhran, MS gibi).
- 6 ay x 60 gece; 6 gecelik hafta (Akşam, Yatsı, Zifir, Tün, Seher, Tan),
  her ay Akşam ile başlar. Tan dinlenme gecesi.
- Aya ve haftaya sayılmayan ara geceler: İkiz Geceler (Alaca 21 Haziran,
  Ağaran 22 Haziran, yaz gündönümü), Yelda Geceleri (Yelda Arifesi 20,
  Yelda 21, Yelda Ertesi 22 Aralık, kış gündönümü), artık yıllarda Konuk
  Gece (29 Şubat, 8 ile 9 Manolya arası).
- Her miladi gün her yıl aynı geceye denk gelir.

Yazım: "Tün, 58 Lavanta, Yıl 0" (günlük), "58 Lavanta 0 BS" (resmî),
"58 LA 0" (kısa), "00-5-58" (dosya adı).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from .lang import N_, _, tr

EPOCH = 2025              # Yıl 0, 23 Aralık 2025'te başlar
DAY_CHANGE_HOUR = 12      # gece öğlen değişir

WEEK = [N_("Akşam"), N_("Yatsı"), N_("Zifir"), N_("Tün"), N_("Seher"), N_("Tan")]


@dataclass(frozen=True)
class Month:
    number: int           # 1-6
    name: str
    short: str
    start: tuple[int, int]   # (ay, gün) miladi
    color: tuple[int, int, int]


MONTHS = [
    Month(1, N_("Akşamsefası"), "AS", (12, 23), (181, 70, 122)),
    Month(2, N_("Manolya"), "MA", (2, 21), (220, 203, 169)),
    Month(3, N_("Papatya"), "PA", (4, 22), (201, 164, 58)),
    Month(4, N_("Zakkum"), "ZA", (6, 23), (62, 123, 87)),
    Month(5, N_("Lavanta"), "LA", (8, 22), (127, 95, 176)),
    Month(6, N_("Karanfil"), "KA", (10, 21), (184, 58, 71)),
]

# Ara geceler: ad, miladi (ay, gün), hangi grupta
SUMMER = [(N_("Alaca"), (6, 21)), (N_("Ağaran"), (6, 22))]
WINTER = [(N_("Yelda Arifesi"), (12, 20)), (N_("Yelda"), (12, 21)), (N_("Yelda Ertesi"), (12, 22))]
GUEST = N_("Konuk Gece")
SUMMER_GROUP = N_("İkiz Geceler")
WINTER_GROUP = N_("Yelda Geceleri")


def night_date(now: dt.datetime) -> dt.date:
    """Şu anki gecenin adını veren miladi tarih: öğlenden önce dünkü akşam."""
    d = now.date()
    return d - dt.timedelta(days=1) if now.hour < DAY_CHANGE_HOUR else d


def year_of(d: dt.date) -> int:
    return d.year - EPOCH if (d.month, d.day) >= (12, 23) else d.year - EPOCH - 1


def year_start(year: int) -> dt.date:
    return dt.date(EPOCH + year, 12, 23)


def is_leap(year: int) -> bool:
    """Şeb yılı Konuk Gece içeriyor mu (içindeki Şubat 29 çekiyor mu)."""
    y = EPOCH + year + 1
    return y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)


@dataclass(frozen=True)
class Night:
    year: int
    month: Optional[Month]       # ara gecede None
    night: int                   # 1-60; ara gecede 0
    special: str = ""            # ara gecenin adı (Alaca, Yelda, Konuk Gece...)
    date: Optional[dt.date] = None

    @property
    def weekday(self) -> Optional[str]:
        return WEEK[(self.night - 1) % 6] if self.month else None

    @property
    def group(self) -> str:
        """Ara gecenin grubu: İkiz Geceler / Yelda Geceleri / "" (Konuk Gece)."""
        if any(self.special == name for name, _ in SUMMER):
            return SUMMER_GROUP
        if any(self.special == name for name, _ in WINTER):
            return WINTER_GROUP
        return ""

    # -- yazım ---------------------------------------------------------------

    def daily(self) -> str:
        """Tün, 58 Lavanta, Yıl 0"""
        if self.special:
            return f"{tr(self.special)}, {_("Yıl")} {self.year}"
        return f"{tr(self.weekday)}, {self.night} {tr(self.month.name)}, {_("Yıl")} {self.year}"

    def official(self) -> str:
        """58 Lavanta 0 BS"""
        if self.special:
            return f"{tr(self.special)} {self.year} BS"
        return f"{self.night} {tr(self.month.name)} {self.year} BS"

    def short(self) -> str:
        """58 LA 0"""
        if self.special:
            return f"{tr(self.special)} {self.year}"
        return f"{self.night} {self.month.short} {self.year}"

    def file_name(self) -> str:
        """00-5-58; ara gecede ay ve gece yerine adı"""
        year = f"{self.year:02d}" if self.year >= 0 else f"-{-self.year:02d}"
        if self.special:
            return f"{year}-{self.special.lower().replace(' ', '')}"
        return f"{year}-{self.month.number}-{self.night}"


def _on(year: int, month_day: tuple[int, int]) -> dt.date:
    """Şeb yılı içindeki (ay, gün): Aralık'ın 23 ve sonrası başlangıç yılında."""
    m, d = month_day
    base = EPOCH + year if (m, d) >= (12, 23) else EPOCH + year + 1
    return dt.date(base, m, d)


def from_date(d: dt.date) -> Night:
    """Miladi tarihin akşamındaki gece."""
    year = year_of(d)
    md = (d.month, d.day)
    for name, when in SUMMER + WINTER:
        if md == when:
            return Night(year, None, 0, name, d)
    if md == (2, 29):
        return Night(year, None, 0, GUEST, d)
    for month in reversed(MONTHS):
        start = _on(year, month.start)
        if d >= start:
            night = (d - start).days + 1
            if month.number == 2 and d > dt.date(d.year, 2, 28) and is_leap(year):
                night -= 1                      # Konuk Gece sayılmaz
            return Night(year, month, night, "", d)
    raise ValueError(d)                         # buraya gelinmez


def to_date(year: int, month: int, night: int) -> dt.date:
    """Şeb gecesinin (ay 1-6, gece 1-60) akşamının miladi tarihi."""
    m = MONTHS[month - 1]
    d = _on(year, m.start) + dt.timedelta(days=night - 1)
    if m.number == 2 and is_leap(year) and night >= 9:
        d += dt.timedelta(days=1)               # 8 ile 9 arasında Konuk Gece
    return d


def special_date(year: int, name: str) -> dt.date:
    if name == GUEST:
        return dt.date(EPOCH + year + 1, 2, 29)
    when = dict(SUMMER + WINTER)[name]
    return _on(year, when)


def now() -> Night:
    return from_date(night_date(dt.datetime.now()))
