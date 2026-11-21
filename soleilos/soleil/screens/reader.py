"""Okuyucu: notlar (Medya / TXT) ve e-kitaplar için ortak ekran.

Üstte sabit GERİ satırı, sağında okunma yüzdesi. Altında kayan içerik:
e-kitapta kapak yeri, sonra çift çizgi arasında dosya adı ve metin.

Tuşlar:
  encoder çevirme : 2 satır kaydırır; en üstte bir daha yukarı = GERİ
  encoder tıklama : sonraki sayfa (GERİ seçiliyse geri döner)
  encoder uzun bas: eylem menüsü (başa dön, bölümler, sona git, yazı boyutu)
  Sol 1 / Sol 2   : önceki / sonraki sayfa
  Üst 1           : oynatıcı
  Üst 2           : yazı boyutu (küçük / orta / büyük)
  Sol 3           : geri

Kapanırken en üstte görünen satırın metindeki yeri kaydedilir; yazı boyutu
değişse de aynı yerden açılır.
"""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .. import settings as S
from ..documents import Document, parse
from ..input import Action
from ..ui import chrome
from ..ui.listview import ListItem, ListScreen, draw_back_row
from . import player
from .action_menu import MenuItem, OverlayMenu
from .base import Screen

# Okuma yazısı: (yazı stili, satır yüksekliği)
SIZES = {"KÜÇÜK": ("small", 17), "ORTA": ("track", 19), "BÜYÜK": ("medium", 22)}
STEP_LINES = 2
COVER_W, COVER_H = 72, 96
TITLE_H = 44
HEADING_H = 28


@dataclass(frozen=True)
class Row:
    kind: str     # "cover", "title", "heading", "line"
    text: str
    y: int
    h: int
    offset: int   # metindeki karakter konumu (kapak ve başlıkta -1)


class ReaderScreen(Screen):
    def __init__(self, app, doc: Document, title: str) -> None:
        super().__init__(app)
        self.doc = doc
        self.title = title
        try:
            text = doc.read()
        except OSError:
            text = ""
        self.blocks = parse(text)
        self.chapters = [b for b in self.blocks if b.kind == "heading"]
        self.on_back = False
        self.animating = False
        self._build()
        saved = app.reading.get(doc)
        self.target = self._y_for_offset(saved[0]) if saved else 0
        self.scroll = float(self.target)

    # -- yerleşim ------------------------------------------------------------

    @property
    def view(self) -> pygame.Rect:
        L = self.app.layout
        top = L.row_cy(0) + 24
        return pygame.Rect(L.left, top, L.row_box_w, L.footer_line_y - 6 - top)

    @property
    def size(self) -> str:
        size = self.app.settings.reader_size
        return size if size in SIZES else "ORTA"

    def _build(self) -> None:
        """Metni ekran genişliğine göre satırlara böler, her satırın yerini hesaplar."""
        app = self.app
        style, line_h = SIZES[self.size]
        self.style, self.line_h = style, line_h
        width = self.view.w - 6
        rows: list[Row] = []
        y = 4
        if self.doc.kind == "kitap":
            rows.append(Row("cover", "", y, COVER_H, -1))
            y += COVER_H + 12
        rows.append(Row("title", self.doc.name, y, TITLE_H, -1))
        y += TITLE_H + 10
        for block in self.blocks:
            if block.kind == "gap":
                y += line_h // 2 + 2
            elif block.kind == "heading":
                if rows[-1].kind == "line":
                    y += line_h // 2
                rows.append(Row("heading", app.text.fit(block.text, "medium", width, raw=True), y, HEADING_H, block.offset))
                y += HEADING_H + 6
            else:
                pos = 0
                for part in app.text.wrap(block.text, style, width, raw=True):
                    # Satırın ilk kelimesinin metindeki yeri
                    words = part.split()
                    found = block.text.find(words[0], pos) if words else -1
                    pos = found if found >= 0 else pos
                    rows.append(Row("line", part, y, line_h, block.offset + pos))
                    pos += len(" ".join(words))
                    y += line_h
        if not self.blocks:
            rows.append(Row("line", "[ BOŞ DOSYA ]", y, line_h, 0))
            y += line_h
        self.rows = rows
        self.content_h = y + 8

    @property
    def max_scroll(self) -> int:
        return max(0, self.content_h - self.view.h)

    def _clamp(self, y: float) -> int:
        return round(max(0, min(self.max_scroll, y)))

    def _text_rows(self) -> list[Row]:
        return [r for r in self.rows if r.offset >= 0]

    def top_offset(self) -> int:
        """En üstte görünen metin satırının dosyadaki yeri."""
        for row in self._text_rows():
            if row.y + row.h > self.target + 2:
                return row.offset
        return 0

    def _y_for_offset(self, offset: int) -> int:
        text_rows = self._text_rows()
        if not text_rows or offset <= text_rows[0].offset:
            return 0
        for row in text_rows:
            if row.offset >= offset:
                return self._clamp(row.y - 2)
        return self.max_scroll

    @property
    def progress(self) -> float:
        """Başta %0, sonda %100; tek ekrana sığan dosya açılınca okunmuş sayılır."""
        if self.max_scroll == 0:
            return 1.0
        return min(1.0, self.target / self.max_scroll)

    def chapter_index(self) -> int:
        """Okunan bölüm (bölüm yoksa -1)."""
        offset = self.top_offset()
        index = -1
        for i, chapter in enumerate(self.chapters):
            if chapter.offset <= offset:
                index = i
        return index

    # -- komutlar ------------------------------------------------------------

    def scroll_to(self, y: float, instant: bool = False) -> None:
        self.target = self._clamp(y)
        if instant:
            self.scroll = float(self.target)
        self.on_back = False

    def page(self, step: int) -> None:
        if step > 0 and self.target >= self.max_scroll:
            self.app.toast("SON", self.doc.name)
            return
        self.scroll_to(self.target + step * (self.view.h - 2 * self.line_h))

    def jump_to(self, offset: int) -> None:
        self.scroll_to(self._y_for_offset(offset), instant=True)

    def cycle_size(self) -> None:
        offset = self.top_offset()
        st = self.app.settings
        st.reader_size = S.next_in(S.READER_SIZES, self.size)
        self.app.settings_changed()
        self._build()
        self.scroll_to(self._y_for_offset(offset), instant=True)
        self.app.toast("YAZI BOYUTU", st.reader_size)

    def handle(self, action: Action) -> None:
        if action is Action.UP:
            if self.target <= 0:
                self.on_back = True
            else:
                self.scroll_to(self.target - STEP_LINES * self.line_h)
        elif action is Action.DOWN:
            if self.on_back:
                self.on_back = False
            else:
                self.scroll_to(self.target + STEP_LINES * self.line_h)
        elif action is Action.SELECT:
            if self.on_back:
                self.app.pop()
            else:
                self.page(1)
        elif action in (Action.LEFT1, Action.LEFT2):
            self.page(-1 if action is Action.LEFT1 else 1)
        elif action is Action.TOP2:
            self.cycle_size()
        elif action is Action.HOLD:
            self.app.push(ReaderMenu(self.app))
        else:
            super().handle(action)

    def update(self, dt: float) -> None:
        diff = self.target - self.scroll
        if abs(diff) < 0.5:
            self.scroll = float(self.target)
            self.animating = False
        else:
            self.scroll += diff * min(1.0, dt * 14)
            self.animating = True

    def closed(self) -> None:
        self.app.reading.set(self.doc, self.top_offset(), self.progress)
        self.app.reading.save()

    # -- çizim ---------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        chrome.draw_header(app, surf, self.title)

        # GERİ satırı ve sağında okunma durumu
        cy = L.row_cy(0)
        draw_back_row(app, surf, cy, self.on_back)
        info = f"[%{round(self.progress * 100)}]"
        if self.chapters and self.chapter_index() >= 0:
            info = f"[B{self.chapter_index() + 1}/{len(self.chapters)}] {info}"
        app.text.draw(surf, info, "small", t.on_fg if self.on_back else t.rule,
                      (L.row_box_x + L.row_box_w - 6, cy - 1), "midright")

        view = self.view
        old_clip = surf.get_clip()
        surf.set_clip(view)
        y0 = view.y - round(self.scroll)
        x = view.x + 2
        for row in self.rows:
            y = y0 + row.y
            if y + row.h < view.y or y > view.bottom:
                continue
            if row.kind == "cover":
                self._draw_cover(surf, pygame.Rect(view.centerx - COVER_W // 2, y, COVER_W, COVER_H))
            elif row.kind == "title":
                self._draw_title(surf, row.text, view, y)
            elif row.kind == "heading":
                app.text.draw(surf, row.text, "medium", t.fg, (x, y + row.h // 2 - 2), "midleft", raw=True)
                surf.fill(t.rule_dim, (view.x, y + row.h - 3, view.w, 1))
            else:
                app.text.draw(surf, row.text, self.style, t.fg, (x, y + row.h // 2 - 1), "midleft", raw=True)
        surf.set_clip(old_clip)

        # Kaydırma çubuğu: tutamak metindeki yeri gösterir
        k = self.scroll / self.max_scroll if self.max_scroll else 0.0
        thumb = L.scroll_top + 17 + (L.scroll_bottom - L.scroll_top - 34) * k
        chrome.draw_scrollbar(app, surf, round(thumb))
        chrome.draw_footer(app, surf)

    def _draw_cover(self, surf: pygame.Surface, rect: pygame.Rect) -> None:
        t = self.app.theme
        pygame.draw.rect(surf, t.rule_dim, rect, 2)
        surf.fill(t.rule_dim, (rect.x + 8, rect.y, 2, rect.h))   # kitap sırtı
        self.app.icons.draw(surf, "book", t.rule_dim, (rect.centerx + 4, rect.centery), "center")

    def _draw_title(self, surf: pygame.Surface, name: str, view: pygame.Rect, y: int) -> None:
        """Figma'daki gibi üstte ve altta çift çizgi arasında dosya adı."""
        app, t = self.app, self.app.theme
        surf.fill(t.fg, (view.x, y, view.w, 2))
        surf.fill(t.rule, (view.x, y + 5, view.w, 1))
        label = app.text.fit(name, "body", view.w - 6, raw=True)
        app.text.draw(surf, label, "body", t.fg, (view.x + 2, y + TITLE_H // 2), "midleft", raw=True)
        surf.fill(t.rule, (view.x, y + TITLE_H - 6, view.w, 1))
        surf.fill(t.fg, (view.x, y + TITLE_H - 2, view.w, 2))


class ReaderMenu(OverlayMenu):
    def _items(self) -> list[MenuItem]:
        app, reader = self.app, self.under
        items = [MenuItem("BAŞA DÖN", lambda: reader.jump_to(0), closes=True)]
        if reader.chapters:
            items.append(MenuItem("BÖLÜMLER", lambda: app.push(ChapterList(app, reader)),
                                  f"{len(reader.chapters)}", closes=True))
        items += [
            MenuItem("SONA GİT", lambda: reader.scroll_to(reader.max_scroll, instant=True), closes=True),
            MenuItem("YAZI BOYUTU", reader.cycle_size, reader.size),
        ]
        if app.playback.current:
            playing = app.playback.playing
            items.append(MenuItem("MÜZİĞİ DURAKLAT" if playing else "MÜZİĞİ OYNAT",
                                  lambda: player.toggle_play(app)))
        items.append(MenuItem("KAPAT", lambda: None, closes=True))
        return items


class ChapterList(ListScreen):
    """E-kitabın bölümleri; seçilen bölüme atlar."""

    def __init__(self, app, reader: ReaderScreen) -> None:
        def jump(offset):
            def act():
                reader.jump_to(offset)
                app.pop()
            return act

        items = [ListItem(c.text, raw=True, act=jump(c.offset)) for c in reader.chapters]
        super().__init__(app, items, selected=max(0, reader.chapter_index()))
        self.title = f"{reader.title} / Bölümler"
