"""Share Tech Mono ile yazı çizimi.

Harfler tek tek, sabit aralıkla (pitch) yerleştirilir. Figma harf
genişliğini kesirli hesaplıyor; tek seferde render edilen satırlar bundan
kayıyor. Harf harf çizince Figma'daki konumlar tutuyor.

Dil: her yazı çizilmeden (ve ölçülmeden) önce lang.tr()'den geçer;
Türkçede hiçbir şey değişmez. raw=True kullanıcının yazdıkları içindir
(şarkı adı, not), onlar çevrilmez. Başka bir dilin hece blokları
(script.py) iki harf genişliğinde çizilir.
"""

from __future__ import annotations

import pygame

from . import lang
from .config import ASSETS
from .script import is_block

FONT_PATH = ASSETS / "fonts" / "ShareTechMono-Regular.ttf"

# Figma'dan ölçülen boyutlar (px)
STYLES = {
    "small": 13,   # satırlardaki küçük etiketler, ör. [21] [89MB]
    "track": 14,   # playlist'teki şarkı satırları
    "medium": 16,  # header başlığı (Figma'da 13)
    "body": 20,    # menü satırları, alt bar
    "display": 44, # açılış ekranındaki logo
    "clock": 80,   # saat, zamanlayıcı ve kronometredeki büyük rakamlar
}

# Fontta olmayan Türkçe harfler: harf + aksan birleştirilerek üretilir.
# (harf, aksan, büyük harf mi) — büyük harfte aksan yukarı kaydırılır.
COMPOSED = {
    "İ": ("I", "˙", True),
    "Ş": ("S", "¸", False),
    "ş": ("s", "¸", False),
    "Ğ": ("G", "˘", True),
    "ğ": ("g", "˘", False),
}


class Text:
    def __init__(self) -> None:
        self._fonts: dict[int, pygame.font.Font] = {}
        self._glyphs: dict[tuple, pygame.Surface] = {}
        big = pygame.font.Font(str(FONT_PATH), 1000)
        self._advance = big.size("M" * 10)[0] / 10000  # harf genişliği / boyut

    def font(self, size: int) -> pygame.font.Font:
        if size not in self._fonts:
            self._fonts[size] = pygame.font.Font(str(FONT_PATH), size)
        return self._fonts[size]

    def pitch(self, style: str) -> float:
        return self._advance * STYLES[style]

    def height(self, style: str) -> int:
        return self.font(STYLES[style]).get_height()

    @staticmethod
    def cells(text: str) -> int:
        """Kaç harf genişliği: hece blokları iki sayılır."""
        return len(text) + sum(1 for ch in text if is_block(ch))

    def width(self, text: str, style: str, pitch: float | None = None, raw: bool = False) -> int:
        if not raw:
            text = lang.tr(text)
        return round(self.cells(text) * (pitch or self.pitch(style)))

    def fit(self, text: str, style: str, max_w: float, tail: str = "..", raw: bool = False) -> str:
        """Sığmayan yazının sonunu kesip '..' ekler. Çevrilmiş halini döndürür."""
        if not raw:
            text = lang.tr(text)
        max_cells = int(max_w // self.pitch(style))
        if self.cells(text) <= max_cells:
            return text
        out, used = "", 0
        room = max(0, max_cells - len(tail))
        for ch in text:
            w = 2 if is_block(ch) else 1
            if used + w > room:
                break
            out += ch
            used += w
        return out + tail

    def wrap(self, text: str, style: str, max_w: float, raw: bool = False) -> list[str]:
        """Yazıyı kelime kelime satırlara böler; satıra sığmayan uzun
        kelimeyi keser. Baştaki boşluklar (girinti, liste) korunur."""
        if not raw:
            text = lang.tr(text)
        max_chars = max(1, int(max_w // self.pitch(style)))
        indent = text[:len(text) - len(text.lstrip(" "))][:max_chars // 3]
        rows, row = [], indent
        for word in text.split():
            trial = f"{row} {word}" if row.strip() else row + word
            if self.cells(trial) <= max_chars:
                row = trial
                continue
            if row.strip():
                rows.append(row)
            row = indent
            while len(indent) + len(word) > max_chars:
                cut = max_chars - len(indent)
                rows.append(indent + word[:cut])
                word = word[cut:]
            row = indent + word
        if row.strip() or not rows:
            rows.append(row)
        return rows

    def _glyph(self, ch: str, size: int, color) -> pygame.Surface:
        key = (ch, size, color)
        if key not in self._glyphs:
            if ch in COMPOSED:
                self._glyphs[key] = self._compose(ch, size, color)
            else:
                self._glyphs[key] = self.font(size).render(ch, True, color)
        return self._glyphs[key]

    def _compose(self, ch: str, size: int, color) -> pygame.Surface:
        base_ch, accent_ch, capital = COMPOSED[ch]
        font = self.font(size)
        base = font.render(base_ch, True, color)
        accent = font.render(accent_ch, True, color)
        shift = 0
        if capital:
            # Ü ile ü'nün noktaları arasındaki yükseklik farkı kadar
            shift = font.metrics("Ü")[0][3] - font.metrics("ü")[0][3]
            if accent_ch == "˘":
                shift += 1
        out = pygame.Surface(base.get_size(), pygame.SRCALPHA)
        out.blit(base, (0, 0))
        out.blit(accent, ((base.get_width() - accent.get_width()) // 2, -shift))
        return out

    def draw(self, surf: pygame.Surface, text: str, style: str, color,
             pos: tuple[float, float], anchor: str = "topleft",
             pitch: float | None = None, raw: bool = False) -> pygame.Rect:
        """pitch verilirse harf aralığı fontun kendi aralığı yerine o olur."""
        if not raw:
            text = lang.tr(text)
        size = STYLES[style]
        pitch = pitch or self.pitch(style)
        rect = pygame.Rect(0, 0, self.width(text, style, pitch, raw=True), self.height(style))
        setattr(rect, anchor, (round(pos[0]), round(pos[1])))
        x0 = rect.x + (pos[0] - round(pos[0]))
        script = lang.current().script
        cell = 0
        for ch in text:
            if is_block(ch):
                if script:
                    block = script.render(ch, (round(2 * pitch) - 1, size), color, FONT_PATH)
                    top = rect.y + (rect.h - size) // 2
                    surf.blit(block, (round(x0 + cell * pitch), top))
                cell += 2
                continue
            if ch != " ":
                surf.blit(self._glyph(ch, size, color), (round(x0 + cell * pitch), rect.y))
            cell += 1
        return rect
