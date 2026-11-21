"""Not Defteri: not listesi ve encoder ile yazı yazma (kadran şeridi).

Yazma ekranında altta eski radyo kadranı gibi bir harf şeridi var: encoder
çevirince harfler kayar, ortadaki kutudaki harf seçilidir, tıklayınca
imlecin yerine yazılır.

Tuşlar:
  encoder çevirme : harf seç (A'nın bir öncesi yeni satır)
  encoder tıklama : harfi yaz
  encoder uzun bas: menü (yeni satır, imleci taşı, adı değiştir, notu sil)
  S (Sol 1)       : sil
  O (Sol 2)       : boşluk
  L (Sol 3)       : geri (not kendiliğinden kaydedilir)
  E (Üst 1)       : oynatıcı
  İ (Üst 2)       : harf seti: abc / ABC / 123 / .,?

"abc" setinde cümle başında harf kendiliğinden büyük yazılır (sekmede
"Abc" görünür). Notlar ~/.soleil/medya/metin içine .txt olarak kaydedilir,
Medya / Metin'deki okuyucuda da açılır.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

import pygame

from ..lang import _
from .. import config
from ..documents import list_documents
from ..input import Action
from ..ui import chrome, dial, glyphs
from ..ui.listview import BACK, ListItem, ListScreen
from .action_menu import MenuItem, OverlayMenu
from .base import Screen

NOTES = config.MEDIA / "metin"
NEWLINE = "\n"
UPPER = "ABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ"
LOWER = "abcçdefgğhıijklmnoöprsştuüvyz"
# Her setin başında yeni satır var: A'dan bir geri çevirince gelir
SETS = [
    ("abc", [NEWLINE] + list(LOWER)),
    ("ABC", [NEWLINE] + list(UPPER)),
    ("123", [NEWLINE] + list("0123456789")),
    (".,?", [NEWLINE] + list(".,!?-:;'\"()/+=%&@#*")),
]
SENTENCE_END = ".!?\n"
AUTOSAVE_AFTER = 5.0      # son değişiklikten bu kadar saniye sonra kaydedilir
BAD_NAME_CHARS = '\\/:*?"<>|'

# Yerleşim
LINE_H = 19
TEXT_STYLE = "track"


def draw_newline(surf: pygame.Surface, color, center, size: int, width: int = 2) -> None:
    """Yeni satır işareti: ↵"""
    cx, cy = center
    s = size / 2
    pts = [(cx + s * 0.6, cy - s * 0.6), (cx + s * 0.6, cy + s * 0.15), (cx - s * 0.6, cy + s * 0.15)]
    pygame.draw.lines(surf, color, False, pts, width)
    tip = pts[-1]
    pygame.draw.lines(surf, color, False, [(tip[0] + s * 0.35, tip[1] - s * 0.35), tip,
                                           (tip[0] + s * 0.35, tip[1] + s * 0.35)], width)


class TextEditor(Screen):
    """Kadran şeridiyle yazı yazma. Kapanırken on_close(metin) çağrılır."""

    def __init__(self, app, title: str, text: str = "",
                 on_close: Optional[Callable[[str], None]] = None,
                 single_line: bool = False, max_len: int = 20000, set_index: int = 0) -> None:
        super().__init__(app)
        self.title = title
        self.text = text
        self.cursor = len(text)
        self.on_close = on_close
        self.single_line = single_line
        self.max_len = max_len
        self.set_index = set_index
        self.dial = dial.Dial(0 if single_line else 1)
        self.moving_cursor = False    # imleç taşıma kipi
        self.first_row = 0
        self.animating = False
        self._blink = 0

    # -- metin -----------------------------------------------------------------

    @property
    def strip(self) -> list[str]:
        items = SETS[self.set_index][1]
        return items[1:] if self.single_line else items

    def _auto_capital(self) -> bool:
        if self.set_index != 0:
            return False
        before = self.text[:self.cursor].rstrip(" ")
        return not before or before[-1] in SENTENCE_END

    def current_char(self) -> str:
        ch = self.strip[self.dial.index(len(self.strip))]
        if ch in LOWER and self._auto_capital():
            ch = UPPER[LOWER.index(ch)]
        return ch

    def insert(self, ch: str) -> None:
        if len(self.text) >= self.max_len or (ch == NEWLINE and self.single_line):
            return
        self.text = self.text[:self.cursor] + ch + self.text[self.cursor:]
        self.cursor += 1
        self.changed()

    def backspace(self) -> None:
        if self.cursor > 0:
            self.text = self.text[:self.cursor - 1] + self.text[self.cursor:]
            self.cursor -= 1
            self.changed()

    def changed(self) -> None:
        """Alt sınıflar kaydetme zamanlamak için kullanır."""

    def next_set(self) -> None:
        old = self.set_index
        self.set_index = (self.set_index + 1) % len(SETS)
        # abc ile ABC aynı sırada; geçince aynı harfte kalınsın
        if {old, self.set_index} != {0, 1}:
            self.dial.jump(0 if self.single_line else 1)

    # -- girdi -----------------------------------------------------------------

    def handle(self, action: Action) -> None:
        if self.moving_cursor:
            if action in (Action.UP, Action.DOWN):
                step = -1 if action is Action.UP else 1
                self.cursor = max(0, min(len(self.text), self.cursor + step))
            elif action in (Action.SELECT, Action.BACK, Action.HOLD):
                self.moving_cursor = False
            elif action is Action.LEFT1:
                self.backspace()
            return
        if action in (Action.UP, Action.DOWN):
            self.dial.turn(-1 if action is Action.UP else 1)
        elif action is Action.SELECT:
            self.insert(self.current_char())
        elif action is Action.LEFT1:
            self.backspace()
        elif action is Action.LEFT2:
            self.insert(" ")
        elif action is Action.TOP2:
            self.next_set()
        elif action is Action.HOLD:
            self.app.push(self.menu())
        else:
            super().handle(action)

    def menu(self) -> OverlayMenu:
        return EditorMenu(self.app)

    def update(self, dt: float) -> None:
        self.animating = self.dial.update(dt)
        blink = int(self.app.time * 2.5) % 2
        if blink != self._blink:        # imleç yanıp söner; sadece o an yeniden çiz
            self._blink = blink
            self.app.dirty = True

    def closed(self) -> None:
        if self.on_close:
            self.on_close(self.text)

    # -- yerleşim --------------------------------------------------------------

    @property
    def text_rect(self) -> pygame.Rect:
        L = self.app.layout
        top = L.row_cy(0) - 14
        return pygame.Rect(L.left, top, L.row_box_w, 244 - top)

    def _rows(self, max_chars: int) -> list[tuple[int, int]]:
        """Metni satırlara böler: (başlangıç, bitiş) karakter aralıkları. Hiçbir
        karakter atılmaz, satır sonundaki boşluk satırda kalır (imleç için)."""
        rows = []
        start = 0
        for para in self.text.split(NEWLINE):
            p0, p = start, 0
            while len(para) - p > max_chars:
                cut = para.rfind(" ", p, p + max_chars + 1)
                end = cut + 1 if cut >= p else p + max_chars
                rows.append((p0 + p, p0 + end))
                p = end
            rows.append((p0 + p, p0 + len(para)))
            start += len(para) + 1
        return rows

    def _cursor_row(self, rows) -> int:
        for i, (a, b) in enumerate(rows):
            nxt = rows[i + 1][0] if i + 1 < len(rows) else None
            if a <= self.cursor <= b and not (self.cursor == b and nxt == b):
                return i
        return len(rows) - 1

    # -- çizim -----------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        chrome.draw_header(app, surf, self.title)
        area = self.text_rect
        self._draw_text(surf, area)

        # Alt çizgi, sağında karakter sayısı
        app.text.draw(surf, self.status_text(), "small", t.rule,
                      (L.left + L.row_box_w - 4, area.bottom + 8), "midright")
        surf.fill(t.rule_dim, (L.left, area.bottom + 18, L.row_box_w, 1))

        if self.moving_cursor:
            self._draw_cursor_mode(surf, area.bottom + 18)
        else:
            self._draw_tabs(surf, area.bottom + 38)
            self._draw_dial(surf, area.bottom + 94)
        chrome.draw_footer(app, surf)

    def status_text(self) -> str:
        return _("{n} KARAKTER").format(n=len(self.text))

    def _draw_text(self, surf: pygame.Surface, area: pygame.Rect) -> None:
        app, t = self.app, self.app.theme
        x = area.x + 4
        max_chars = int((area.w - 8) // app.text.pitch(TEXT_STYLE))
        rows = self._rows(max_chars)
        crow = self._cursor_row(rows)
        visible = area.h // LINE_H
        if crow < self.first_row:
            self.first_row = crow
        elif crow >= self.first_row + visible:
            self.first_row = crow - visible + 1
        for i in range(self.first_row, min(len(rows), self.first_row + visible)):
            a, b = rows[i]
            y = area.y + (i - self.first_row) * LINE_H
            app.text.draw(surf, self.text[a:b], TEXT_STYLE, t.fg, (x, y), raw=True)
            if i == crow:
                cx = x + app.text.width(self.text[a:self.cursor], TEXT_STYLE)
                if self._blink == 0 or self.moving_cursor:
                    surf.fill(t.fg, (cx + 1, y + 1, 2 if self.moving_cursor else 7, 16))
        if not self.text:
            app.text.draw(surf, "[ BOŞ ]" if not self.single_line else "", TEXT_STYLE,
                          t.rule_dim, (x + 12, area.y))
        # Uzun notta kaydırma çubuğu imleci izler
        if len(rows) > visible:
            k = crow / max(1, len(rows) - 1)
            L = self.app.layout
            chrome.draw_scrollbar(app, surf, round(L.scroll_top + 17 + (L.scroll_bottom - L.scroll_top - 34) * k))

    def _draw_tabs(self, surf: pygame.Surface, cy: int) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        x = L.left + 4
        for i, (name, _) in enumerate(SETS):
            if i == 0 and self._auto_capital():
                name = "Abc"
            w = app.text.width(name, "small") + 12
            r = pygame.Rect(x, cy - 9, w, 18)
            if i == self.set_index:
                surf.fill(t.fg, r)
                app.text.draw(surf, name, "small", t.on_fg, r.center, "center")
            else:
                pygame.draw.rect(surf, t.rule_dim, r, 1)
                app.text.draw(surf, name, "small", t.rule, r.center, "center")
            x = r.right + 6
        glyphs.draw_hints(app, surf, [(Action.TOP2, "SET")], t.rule,
                          (L.left + L.row_box_w - 2, cy), "midright")

    def _draw_dial(self, surf: pygame.Surface, cy: int) -> None:
        app, t = self.app, self.app.theme
        cap = self._auto_capital()

        def draw_item(app, surf, ch, color, center, big):
            if ch == NEWLINE:
                draw_newline(surf, color, center, 28 if big else 14, 3 if big else 2)
            else:
                if cap and ch in LOWER:
                    ch = UPPER[LOWER.index(ch)]
                dial.default_item(app, surf, ch, color, center, big)

        cx = dial.draw(app, surf, self.strip, self.dial.anim, cy, draw_item)
        glyphs.draw_hints(app, surf, [(Action.LEFT1, "SİL"), (Action.LEFT2, "BOŞLUK"), (Action.HOLD, "MENÜ")],
                          t.rule, (cx, cy + 50), "center")

    def _draw_cursor_mode(self, surf: pygame.Surface, top: int) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        cx = (L.left + L.row_box_w) // 2 + 2
        app.text.draw(surf, "İMLECİ TAŞI", "body", t.fg, (cx, top + 46), "center")
        app.text.draw(surf, "ENCODER'I ÇEVİR", "small", t.rule, (cx, top + 72), "center")
        glyphs.draw_hints(app, surf, [(Action.SELECT, "TAMAM"), (Action.LEFT1, "SİL")], t.rule,
                          (cx, top + 126), "center")


class EditorMenu(OverlayMenu):
    def _items(self) -> list[MenuItem]:
        ed = self.under
        items = []
        if not ed.single_line:
            items.append(MenuItem("YENİ SATIR", lambda: ed.insert(NEWLINE), closes=True))
        items.append(MenuItem("İMLECİ TAŞI", lambda: setattr(ed, "moving_cursor", True), closes=True))
        items += ed.extra_menu_items() if hasattr(ed, "extra_menu_items") else []
        items.append(MenuItem("KAPAT", lambda: None, closes=True))
        return items


# -- notlar --------------------------------------------------------------------

def _new_note_path() -> Path:
    i = 1
    while (NOTES / f"NOT-{i:02d}.txt").exists():
        i += 1
    return NOTES / f"NOT-{i:02d}.txt"


class NoteEditor(TextEditor):
    """Bir not dosyasını düzenler; kendiliğinden kaydeder."""

    def __init__(self, app, path: Path, on_done: Callable[[], None]) -> None:
        try:
            text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
        except OSError:
            text = ""
        super().__init__(app, "", text)
        self.path = path
        self.on_done = on_done
        self.dirty_since: Optional[float] = None
        self.deleted = False
        self._confirm_delete = False

    @property
    def title(self) -> str:
        return f"Sols / Not Defteri / {self.path.stem}"

    @title.setter
    def title(self, value) -> None:
        pass

    def changed(self) -> None:
        self.dirty_since = self.app.time

    def status_text(self) -> str:
        state = "" if self.dirty_since is None else "* "
        return state + _("{n} KARAKTER").format(n=len(self.text))

    def save(self) -> None:
        if self.deleted or self.dirty_since is None:
            return
        self.dirty_since = None
        if not self.text and not self.path.exists():
            return          # boş yeni not dosya olarak kalmasın
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(self.text, encoding="utf-8")
        except OSError as e:
            self.app.toast("KAYDEDİLEMEDİ", str(e)[:24])

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.dirty_since is not None and self.app.time - self.dirty_since >= AUTOSAVE_AFTER:
            self.save()
            self.app.dirty = True

    def closed(self) -> None:
        self.save()
        self.on_done()

    # -- menü ------------------------------------------------------------------

    def extra_menu_items(self) -> list[MenuItem]:
        delete_label = "EMİN MİSİN? TEKRAR BAS" if self._confirm_delete else "NOTU SİL"
        return [
            MenuItem("ADI DEĞİŞTİR", self._rename, closes=True),
            MenuItem(delete_label, self._delete, closes=self._confirm_delete),
        ]

    def menu(self) -> OverlayMenu:
        self._confirm_delete = False
        return EditorMenu(self.app)

    def _rename(self) -> None:
        def apply(name: str) -> None:
            name = "".join(c for c in name if c not in BAD_NAME_CHARS).strip()
            if not name or name == self.path.stem:
                return
            target = self.path.with_name(f"{name}.txt")
            if target.exists():
                self.app.toast("BU AD KULLANILIYOR", name)
                return
            if self.path.exists():
                try:
                    self.path.rename(target)
                except OSError:
                    self.app.toast("AD DEĞİŞMEDİ")
                    return
            self.path = target
            self.app.toast("AD DEĞİŞTİ", name)

        self.app.push(TextEditor(self.app, f"../{self.path.stem} / Ad", self.path.stem,
                                 on_close=apply, single_line=True, max_len=24, set_index=1))

    def _delete(self) -> None:
        if not self._confirm_delete:
            self._confirm_delete = True
            return
        self.deleted = True
        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass
        self.app.pop()          # editörden listeye
        self.app.toast("NOT SİLİNDİ", self.path.stem)


class NotebookMenu(ListScreen):
    """Not listesi: en üstte yeni not, altta notlar (son düzenlenen üstte)."""
    title = "Sols / Not Defteri"

    def __init__(self, app) -> None:
        self.app = app
        super().__init__(app, self._items())

    def _items(self) -> list[ListItem]:
        app = self.app
        notes = [d for d in list_documents("metin") if not d.sample]
        notes.sort(key=lambda d: d.path.stat().st_mtime if d.path.exists() else 0, reverse=True)
        items = [ListItem("Yeni Not", right="[+]", open=lambda: NoteEditor(app, _new_note_path(), self.refresh))]
        for doc in notes:
            date = time.strftime("%d.%m", time.localtime(doc.path.stat().st_mtime))
            items.append(ListItem(doc.name, raw=True, right=f"[{date}]",
                                  open=lambda doc=doc: NoteEditor(app, doc.path, self.refresh)))
        return items

    def refresh(self) -> None:
        self.rows = [BACK] + self._items()
        self.selected = min(self.selected, len(self.rows) - 1)
        self._scroll_to_selected()
