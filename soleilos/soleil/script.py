"""Hece blokları: Latin okunuşu Solainwen gibi blok yazılarına çevirip çizer.

Çeviriler Latin harfli okunuşla yazılır ("maison de ego"). Dilin
`dil.json` dosyasında harfleri varsa okunuş hecelere bölünür; her hece tek
bir blok olur ve özel kullanım alanındaki (Unicode PUA-A, U+F0000'dan
sonrası) tek bir karakterle tutulur. Böylece yazı uzunluğu = blok sayısı;
kesme, kaydırma, f-string hepsi bozulmadan çalışır. Text sınıfı bu
karakterleri görünce bloğu buradan çizer.

Üç blok tipi (Solainwen):
- Standart  : üstte solda ünsüz, sağda ünlü; hece ünsüzle bitiyorsa altta
              boydan boya özel ünsüz. Ünlü hiçbir zaman alta inmez.
- Sadece ünlü: ünlü bloğun tamamını kaplar ("ego"daki e).
- Ünlüyle başlayan: dikey ikiye bölünür, solda ünlü, sağda ünsüz (AN, IL).
              Buradaki ünsüz özel ünsüz de olabilir, normal ünsüz de (AG).

Harfler: "ilk" hece başındaki ünsüzler (kümeler dahil: STR, PH), "orta"
ünlüler (kombin ünlüler dahil: EAU, UAI), "son" hece sonundaki özel
ünsüzler (kümeler dahil: NT, NG). Her biri tek işaret; en uzun eşleşmeyle
okunur.

Hece kuralı: iki ünlü arasındaki ünsüzlerden olabilecek en uzun kısım
sonraki hecenin başına geçer, kalanı önceki hecenin sonu olur
("sento" → sen-to, "maison" → mai-son). Hiçbir heceye bağlanamayan
ünsüz, tanınmayan harf (W), rakam ve noktalama olduğu gibi Latin kalır.

Blok çizimi:
- Font varsa (dil.json "font"): ilk sesler U+E000+i, ünlüler U+E100+i,
  özel ünsüzler U+E200+i (listelerdeki sırayla). Harfler bloktaki
  yerlerine ölçeklenip yerleştirilir.
- Font yoksa: aynı yerlere küçük Latin harfler yazılır (taslak). Alfabe
  dijitale geçmeden blok düzenini görmek için.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pygame

BASE = 0xF0000            # hece blokları burada başlar
JAMO = {"ilk": 0xE000, "orta": 0xE100, "son": 0xE200}   # fonttaki harfler

# Bloğun içindeki yerler: (x, y, genişlik, yükseklik), bloğun oranı olarak.
# Üst orta yuva (standart blokta ünsüzle ünlü arası) şimdilik kullanılmıyor.
LAYOUTS = {
    "standart": {"ilk": (0.0, 0.0, 0.5, 1.0), "orta": (0.5, 0.0, 0.5, 1.0)},
    "standart+son": {"ilk": (0.0, 0.0, 0.5, 0.58), "orta": (0.5, 0.0, 0.5, 0.58),
                     "son": (0.0, 0.62, 1.0, 0.38)},
    "unlu": {"orta": (0.0, 0.0, 1.0, 1.0)},
    "unlu+unsuz": {"orta": (0.0, 0.0, 0.5, 1.0), "son": (0.5, 0.0, 0.5, 1.0)},
}
SCALE = 4                 # harfler 4 kat büyük çizilip küçültülür (yumuşak kenar)


def is_block(ch: str) -> bool:
    return ord(ch) >= BASE


@dataclass
class Script:
    """dil.json'daki "alfabe" bölümü."""
    onsets: list[str]                    # hece başı ünsüzler
    vowels: list[str]                    # ünlüler
    codas: list[str]                     # özel ünsüzler (hece sonu)
    layouts: dict = field(default_factory=lambda: dict(LAYOUTS))
    font_path: Optional[Path] = None
    _cache: dict = field(default_factory=dict, repr=False)
    _fonts: dict = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        # Kodlamadaki son ses listesi: önce özel ünsüzler, sonra ünlüyle
        # başlayan blokta kullanılabilen normal ünsüzler (AG). 0. eleman "yok".
        self._finals = [""] + self.codas + [o for o in self.onsets if o not in self.codas]
        self._vowel_set = set(self.vowels)
        self._letters = set("".join(self.onsets + self.codas))
        self._longest_vowel = max((len(v) for v in self.vowels), default=1)

    @classmethod
    def from_json(cls, data: dict, folder: Path, font: Optional[str] = None) -> "Script":
        layouts = dict(LAYOUTS)
        layouts.update(data.get("yerlesim", {}))
        path = folder / font if font else None
        return cls([x for x in data.get("ilk", []) if x], [x for x in data.get("orta", []) if x],
                   [x for x in data.get("son", []) if x], layouts,
                   path if path and path.exists() else None)

    # -- okunuş -> bloklar -------------------------------------------------------

    def _tokens(self, word: str) -> list[tuple[str, str]]:
        """("v", ünlü) / ("c", ünsüz dizisi) / ("x", tanınmayan harf)."""
        out: list[tuple[str, str]] = []
        i = 0
        while i < len(word):
            for n in range(min(self._longest_vowel, len(word) - i), 0, -1):
                part = word[i:i + n]
                # Ünsüzle biten ünlü (EG): ardından ünlü geliyorsa ünsüz sonraki
                # hecenin başına geçer ("ego" = e-go); "eg" sonda ya da ünsüzden önce EG
                if part[-1] in self._letters and self._starts_vowel(word, i + n):
                    continue
                if part in self._vowel_set:
                    out.append(("v", word[i:i + n]))
                    i += n
                    break
            else:
                ch = word[i]
                if ch in self._letters:
                    if out and out[-1][0] == "c":
                        out[-1] = ("c", out[-1][1] + ch)
                    else:
                        out.append(("c", ch))
                else:
                    out.append(("x", ch))
                i += 1
        return out

    def _starts_vowel(self, word: str, i: int) -> bool:
        return any(word.startswith(v, i) for v in self.vowels)

    def _final_ok(self, final: str, has_onset: bool) -> bool:
        if not final:
            return True
        return final in self.codas or (not has_onset and final in self.onsets)

    def _split(self, run: str, has_onset: bool) -> Optional[tuple[str, str]]:
        """İki ünlü arasındaki ünsüzler: (önceki hecenin sonu, sonraki hecenin başı).
        Sonraki hecenin başı olabildiğince uzun tutulur."""
        for k in range(len(run) + 1):
            final, onset = run[:k], run[k:]
            if (not onset or onset in self.onsets) and self._final_ok(final, has_onset):
                if onset or k == len(run):
                    return final, onset
        return None

    def encode(self, text: str) -> str:
        """Okunuşu blok karakterlerine çevirir. {süslü} parantez içi
        (yer tutucular) ve tanınmayan harfler olduğu gibi kalır."""
        out, i = [], 0
        while i < len(text):
            if text[i] == "{":
                j = text.find("}", i)
                j = len(text) if j < 0 else j + 1
                out.append(text[i:j])
                i = j
                continue
            j = i
            while j < len(text) and text[j] != "{":
                j += 1
            out.append(self._encode_plain(text[i:j]))
            i = j
        return "".join(out)

    def _encode_plain(self, text: str) -> str:
        lower = text.replace("İ", "i").lower()
        tokens = self._tokens(lower)
        out: list[str] = []
        onset = ""
        i = 0
        while i < len(tokens):
            kind, value = tokens[i]
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ("", "")
            if kind == "x":
                out.append(value)
                i += 1
            elif kind == "c":
                # Hece başı: ardından ünlü gelmeli ve geçerli bir ilk ses olmalı
                if nxt[0] == "v" and value in self.onsets:
                    onset = value
                else:
                    out.append(value)            # bağlanamayan ünsüz: Latin kalır
                i += 1
            else:
                vowel, final = value, ""
                i += 1
                if i < len(tokens) and tokens[i][0] == "c":
                    run = tokens[i][1]
                    after = tokens[i + 1] if i + 1 < len(tokens) else ("", "")
                    if after[0] == "v":
                        split = self._split(run, bool(onset))
                        if split:
                            final, next_onset = split
                            tokens[i] = ("c", next_onset) if next_onset else ("x", "")
                            if not next_onset:
                                i += 1
                    elif self._final_ok(run, bool(onset)):
                        final = run
                        i += 1
                out.append(self._block(onset, vowel, final))
                onset = ""
        return "".join(out)

    def _block(self, onset: str, vowel: str, final: str) -> str:
        o = self.onsets.index(onset) + 1 if onset else 0
        v = self.vowels.index(vowel)
        c = self._finals.index(final)
        return chr(BASE + (o * len(self.vowels) + v) * len(self._finals) + c)

    def decode(self, ch: str) -> tuple[str, str, str]:
        """(ilk ses, ünlü, son ses)"""
        n, c = divmod(ord(ch) - BASE, len(self._finals))
        o, v = divmod(n, len(self.vowels))
        return (self.onsets[o - 1] if o else ""), self.vowels[v], self._finals[c]

    def kind(self, ch: str) -> str:
        """Blok tipi: standart, standart+son, unlu, unlu+unsuz."""
        onset, _, final = self.decode(ch)
        if onset:
            return "standart+son" if final else "standart"
        return "unlu+unsuz" if final else "unlu"

    def romanize(self, text: str) -> str:
        """Blokları tekrar okunuşa çevirir (testler ve hata ayıklama için)."""
        return "".join("".join(self.decode(ch)) if is_block(ch) else ch for ch in text)

    # -- çizim -----------------------------------------------------------------

    def render(self, ch: str, size: tuple[int, int], color, fallback_font) -> pygame.Surface:
        """Bir bloğu çizer. fallback_font: taslakta kullanılacak Latin font yolu."""
        key = (ch, size, color)
        if key in self._cache:
            return self._cache[key]
        w, h = size
        big = pygame.Surface((w * SCALE, h * SCALE), pygame.SRCALPHA)
        parts = dict(zip(("ilk", "orta", "son"), self.decode(ch)))
        for slot, (fx, fy, fw, fh) in self.layouts[self.kind(ch)].items():
            letter = parts.get(slot)
            if not letter:
                continue
            rect = pygame.Rect(round(fx * w * SCALE), round(fy * h * SCALE),
                               max(1, round(fw * w * SCALE)), max(1, round(fh * h * SCALE)))
            glyph = self._letter(slot, letter, rect.h, color, fallback_font)
            if glyph is None:
                continue
            if self.font_path is not None:
                glyph = pygame.transform.smoothscale(glyph, rect.size)   # yerine sığdır
            else:
                # Taslak: yüksekliği doldur, sığmazsa yatayda sıkıştır
                gw, gh = glyph.get_size()
                w2 = min(rect.w, round(gw * rect.h / gh))
                glyph = pygame.transform.smoothscale(glyph, (max(1, w2), rect.h))
            big.blit(glyph, glyph.get_rect(center=rect.center))
        out = pygame.transform.smoothscale(big, size)
        self._cache[key] = out
        return out

    def _letter(self, slot: str, letter: str, height: int, color, fallback_font):
        if self.font_path is not None:
            if slot == "son" and letter not in self.codas:
                cp = JAMO["ilk"] + self.onsets.index(letter)       # ünlüyle başlayan blokta normal ünsüz
            else:
                cp = JAMO[slot] + {"ilk": self.onsets, "orta": self.vowels, "son": self.codas}[slot].index(letter)
            surf = self._font(self.font_path, height).render(chr(cp), True, color)
        else:
            surf = self._font(fallback_font, max(8, height)).render(letter, True, color)
        bounds = surf.get_bounding_rect()
        return surf.subsurface(bounds).copy() if bounds.w and bounds.h else None

    def _font(self, path, size: int) -> pygame.font.Font:
        key = (str(path), size)
        if key not in self._fonts:
            self._fonts[key] = pygame.font.Font(str(path), size)
        return self._fonts[key]


def load(folder: Path) -> Optional[Script]:
    path = folder / "dil.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    alphabet = data.get("alfabe")
    if not alphabet or not alphabet.get("orta"):
        return None
    return Script.from_json(alphabet, folder, data.get("font"))
