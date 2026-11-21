"""Arayüz dili: Türkçe (asıl dil) ya da assets/dil/ altındaki başka bir dil.

Her dil bir klasör: assets/dil/<kod>/
  dil.json   : adı, alfabesi (script.py), fontu
  ceviri.md  : | Türkçe | Okunuş | tablosu. Obsidian'da doldurulur.
               `tools/ceviri_listesi.py` koddaki yazıları tabloya ekler,
               doldurulmuş satırlara dokunmaz.

Çeviri ekrana çizilirken yapılır (Text sınıfı her yazıyı tr()'den
geçirir): kodda Türkçe yazı olduğu gibi durur, dil değişince her şey
kendiliğinden değişir. Çevirisi olmayan yazı Türkçe görünür.

- Büyük/küçük harf fark etmez: "Sistem Ayarları" çevrilince "SİSTEM
  AYARLARI" da çevrilir.
- Başlık yolları parça parça çevrilir: "Sols / Müzik / Yerel".
- Köşeli parantezli değerlerin içi çevrilir: "[AÇIK]", "[ BOŞ ]".
- İçinde sayı olan yazılar kodda _("{n} şarkı").format(n=3) gibi yazılır;
  tabloya "{n} şarkı" girer, {n} çeviride de aynen kalır.
- Şarkı adı, not gibi kullanıcının yazdıkları çevrilmez (raw=True).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from . import script as script_mod
from .config import ASSETS

FOLDER = ASSETS / "dil"
TURKISH = "tr"


def key(text: str) -> str:
    """Tablo anahtarı: Türkçe küçük harf, baş/son boşluksuz."""
    return text.replace("İ", "i").replace("I", "ı").lower().strip()


def read_table(path: Path) -> dict[str, str]:
    """ceviri.md: | Türkçe | Okunuş | satırları. Okunuşu boş olanlar atlanır."""
    table: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return table
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 2 or set(cells[0]) <= set("-: ") or cells[0] == "Türkçe":
            continue
        if cells[1]:
            table[key(cells[0].replace("\\|", "|"))] = cells[1].replace("\\|", "|")
    return table


@dataclass
class Language:
    code: str
    name: str
    table: dict[str, str] = field(default_factory=dict)
    script: Optional[script_mod.Script] = None
    _cache: dict = field(default_factory=dict, repr=False)

    def lookup(self, text: str) -> Optional[str]:
        """Çeviri (blok karakterleriyle) ya da yoksa None."""
        if text in self._cache:
            return self._cache[text]
        found = self.table.get(key(text))
        if found is not None:
            if self.script:
                found = self.script.encode(found)
            elif text.isupper():
                found = found.upper()        # alfabe yokken Türkçedeki gibi büyük harf
        self._cache[text] = found
        return found


_current = Language(TURKISH, "TÜRKÇE")


def available() -> list[tuple[str, str]]:
    """(kod, ad) listesi; Türkçe hep ilk."""
    out = [(TURKISH, "TÜRKÇE")]
    if FOLDER.is_dir():
        for folder in sorted(p for p in FOLDER.iterdir() if p.is_dir()):
            out.append((folder.name, _meta(folder).get("ad", folder.name.upper())))
    return out


def _meta(folder: Path) -> dict:
    try:
        return json.loads((folder / "dil.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def load(code: str, folder: Optional[Path] = None) -> Language:
    if code == TURKISH:
        return Language(TURKISH, "TÜRKÇE")
    folder = folder or FOLDER / code
    meta = _meta(folder)
    return Language(code, meta.get("ad", code.upper()), read_table(folder / "ceviri.md"),
                    script_mod.load(folder))


def set_language(code: str, folder: Optional[Path] = None) -> Language:
    """Dili değiştirir; klasörü yoksa Türkçeye döner."""
    global _current
    if code != TURKISH and not (folder or FOLDER / code).is_dir():
        code = TURKISH
    _current = load(code, folder)
    return _current


def current() -> Language:
    return _current


def tr(text: str) -> str:
    """Ekrana çizilecek yazının çevirisi (yoksa kendisi)."""
    lang = _current
    if lang.code == TURKISH or not text:
        return text
    found = lang.lookup(text)
    if found is not None:
        return found
    if " / " in text:                    # başlık yolu: parça parça
        parts = text.split(" / ")
        return " / ".join(lang.lookup(p) or p for p in parts)
    if len(text) > 2 and text[0] == "[" and text[-1] == "]":
        inner = text[1:-1]
        found = lang.lookup(inner.strip())
        if found is not None:
            pad = " " if inner.startswith(" ") else ""
            return f"[{pad}{found}{pad}]"
    return text


def _(text: str) -> str:
    """Kodda içinde değer olan yazılar için: _("{n} şarkı").format(n=3).
    Çeviri çizimde değil burada yapılır; tablo aracı bu çağrıları da toplar."""
    return tr(text)


def N_(text: str) -> str:
    """Sadece işaret: çeviri tablosuna girsin diye (ör. sabit başlıklar)."""
    return text
