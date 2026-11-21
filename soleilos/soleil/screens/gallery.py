"""Medya / Görsel: görsel listesi ve görüntüleyici.

Görüntüleyicide tuşlar:
  encoder çevirme : önceki / sonraki görsel
  encoder tıklama : tam ekran aç / kapa
  O (Sol 2)       : slayt gösterisi (5 sn'de bir sonraki)
  İ (Üst 2)       : 90° döndür
  S (Sol 1)       : filtre: renkli / tema rengi (retro tek renk)
  L (Sol 3)       : tam ekrandaysa çık, değilse geri
  E (Üst 1)       : oynatıcı

Görseller ~/.soleil/medya/gorsel ve assets/ornek/gorsel içinden gelir.
"""

from __future__ import annotations

import numpy as np
import pygame

from ..documents import IMAGE_EXTENSIONS, Document, format_size, list_documents
from ..images import ImageLoader
from ..input import Action
from ..theme import mix
from ..ui import chrome, glyphs
from ..ui.listview import ListItem, ListScreen
from .base import Screen

SLIDE_SECONDS = 5.0
INDEX_SHOW = 1.5            # tam ekranda sıra numarası bu kadar görünür

_loader = ImageLoader()


def images() -> list[Document]:
    return list_documents("gorsel", IMAGE_EXTENSIONS)


def gallery_list(app) -> ListScreen:
    docs = images()
    screen = ListScreen(app, [
        ListItem(doc.name, raw=True, right=f"[{format_size(doc.size)}]",
                 open=lambda i=i: ImageViewer(app, docs, i))
        for i, doc in enumerate(docs)
    ])
    screen.title = "Sols / Medya / Görsel"
    return screen


def tint(surface: pygame.Surface, bg, fg) -> pygame.Surface:
    """Tek renkli, tema renginde kopya: koyu yerler arka plan, açık yerler
    ana renk (eski amber monitörler gibi)."""
    rgb = pygame.surfarray.array3d(surface).astype(np.float32)
    lum = (rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32)) / 255.0
    lum = lum ** 0.9
    bg_arr = np.array(bg, dtype=np.float32)
    fg_arr = np.array(fg, dtype=np.float32)
    out = bg_arr + (fg_arr - bg_arr) * lum[..., None]
    return pygame.surfarray.make_surface(out.clip(0, 255).astype(np.uint8))


class ImageViewer(Screen):
    def __init__(self, app, docs: list[Document], index: int) -> None:
        super().__init__(app)
        self.docs = docs
        self.index = index
        self.rotation: dict = {}       # yol -> 0/90/180/270 (sadece bu açılışta)
        self.full = False
        self.slideshow = False
        self.slide_timer = 0.0
        self.changed_at = app.time
        self._scaled: dict = {}        # (yol, döndürme, filtre, tema, kutu) -> yüzey
        self.animating = False

    @property
    def doc(self) -> Document:
        return self.docs[self.index]

    @property
    def title(self) -> str:
        return f"Sols / Medya / Görsel / {self.doc.name}"

    @property
    def tinted(self) -> bool:
        return self.app.settings.image_tint

    # -- girdi -----------------------------------------------------------------

    def go(self, step: int) -> None:
        self.index = (self.index + step) % len(self.docs)
        self.changed_at = self.app.time
        self.slide_timer = 0.0
        if len(self._scaled) > 12:
            self._scaled.clear()

    def handle(self, action: Action) -> None:
        app = self.app
        if action in (Action.UP, Action.DOWN):
            self.go(-1 if action is Action.UP else 1)
        elif action is Action.SELECT:
            self.full = not self.full
            self.changed_at = app.time
        elif action is Action.LEFT2:
            self.slideshow = not self.slideshow
            self.slide_timer = 0.0
            app.toast("SLAYT GÖSTERİSİ", "AÇIK" if self.slideshow else "KAPALI", seconds=0.9)
        elif action is Action.TOP2:
            path = self.doc.path
            self.rotation[path] = (self.rotation.get(path, 0) + 90) % 360
        elif action is Action.LEFT1:
            app.settings.image_tint = not app.settings.image_tint
            app.settings_changed()
            app.toast("FİLTRE", "TEMA RENGİ" if self.tinted else "RENKLİ", seconds=0.9)
        elif action is Action.BACK and self.full:
            self.full = False
        else:
            super().handle(action)

    def update(self, dt: float) -> None:
        app = self.app
        if self.slideshow:
            self.slide_timer += dt
            if self.slide_timer >= SLIDE_SECONDS:
                self.go(1)
            app.last_input = app.time          # slayt sürerken ekran uyumasın
        # Komşuları önceden yükle: geçiş beklemesin
        n = len(self.docs)
        for d in (1, -1):
            _loader.preload(self.docs[(self.index + d) % n].path)
        status, _ = _loader.get(self.doc.path)
        index_visible = self.full and app.time - self.changed_at < INDEX_SHOW + 0.5
        self.animating = status == "loading" or self.slideshow or index_visible

    # -- çizim -----------------------------------------------------------------

    def _surface_for(self, info, box: pygame.Rect) -> pygame.Surface:
        path = self.doc.path
        rot = self.rotation.get(path, 0)
        t = self.app.theme
        key = (path, rot, self.tinted, t.name, box.size)
        if key not in self._scaled:
            src = info.surface
            if rot:
                src = pygame.transform.rotate(src, -rot)
            if src.get_bitsize() == 32 and src.get_flags() & pygame.SRCALPHA:
                flat = pygame.Surface(src.get_size())
                flat.fill(t.bg)                  # saydam yerler arka plan renginde
                flat.blit(src, (0, 0))
                src = flat
            w, h = src.get_size()
            k = min(box.w / w, box.h / h)
            size = (max(1, round(w * k)), max(1, round(h * k)))
            img = pygame.transform.smoothscale(src, size) if k < 1 else pygame.transform.scale(src, size)
            if self.tinted:
                img = tint(img, t.bg, t.fg)
            self._scaled[key] = img
        return self._scaled[key]

    def _draw_image(self, surf: pygame.Surface, box: pygame.Rect, frame: bool):
        app, t = self.app, self.app.theme
        status, info = _loader.get(self.doc.path)
        if status != "ok":
            msg = "YÜKLENİYOR" if status == "loading" else "AÇILAMADI"
            app.text.draw(surf, msg, "medium", t.rule, box.center, "center")
            return None
        img = self._surface_for(info, box)
        r = img.get_rect(center=box.center)
        surf.blit(img, r)
        if frame:
            pygame.draw.rect(surf, t.rule, r.inflate(4, 4), 1)
        return info

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        n = len(self.docs)
        if self.full:
            surf.fill((0, 0, 0))
            self._draw_image(surf, surf.get_rect(), frame=False)
            since = app.time - self.changed_at
            if since < INDEX_SHOW + 0.5:
                k = min(1.0, max(0.0, (INDEX_SHOW + 0.5 - since) / 0.5))
                color = mix((0, 0, 0), t.fg, k)
                app.text.draw(surf, f"{self.index + 1:02d}/{n:02d}", "small", color, (L.width - 8, 10), "topright")
            if self.slideshow:
                surf.fill(t.rule_dim, (0, L.height - 2, L.width, 2))
                surf.fill(t.fg, (0, L.height - 2, round(L.width * self.slide_timer / SLIDE_SECONDS), 2))
            return

        chrome.draw_header(app, surf, self.title)
        box = pygame.Rect(L.left + 4, L.header_rule2_y + 12, L.content_w - 8, L.footer_line_y - 92 - L.header_rule2_y)
        info = self._draw_image(surf, box, frame=True)

        y = box.bottom + 20
        app.text.draw(surf, f"{self.index + 1:02d}/{n:02d}", "medium", t.fg, (L.left + 6, y), "midleft")
        if info:
            w, h = info.original_size
            detail = f"{w}x{h}  {format_size(self.doc.size)}"
            app.text.draw(surf, detail, "small", t.rule, (L.left + L.content_w - 6, y), "midright")
        if self.slideshow:
            bar = pygame.Rect(L.left + 60, y - 1, 60, 3)
            surf.fill(t.rule_dim, bar)
            surf.fill(t.fg, (bar.x, bar.y, round(bar.w * self.slide_timer / SLIDE_SECONDS), bar.h))
        glyphs.draw_hints(app, surf, [(Action.SELECT, "TAM EKRAN"), (Action.LEFT2, "SLAYT"),
                                      (Action.TOP2, "DÖNDÜR"), (Action.LEFT1, "FİLTRE")],
                          t.rule, (L.width // 2, L.footer_line_y - 22), "center", gap=12)
        chrome.draw_footer(app, surf)
