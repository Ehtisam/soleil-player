"""Araçlar / Takvim: Takvim-i Şeb ve miladi takvim (seb.py).

İki takvim aynı seçili tarihi paylaşır; İ (Üst 2) ikisi arasında geçer.

Tuşlar:
  encoder çevirme : önceki / sonraki gece (gün)
  encoder tıklama : bugüne dön
  S (Sol 1)       : önceki ay (Şeb'de ara geceler kendi sayfasında)
  O (Sol 2)       : sonraki ay
  İ (Üst 2)       : diğer takvim
  L (Sol 3)       : geri

Şeb sayfasında ızgara 6 sütun (Akşam ... Tan) x 10 hafta; Tan sütunu ayın
renginde. Artık yıllarda Manolya'da 8 ile 9 arasında Konuk Gece işareti.
Miladi sayfada her günün altında o akşamın Şeb gecesi küçük yazar.
"""

from __future__ import annotations

import datetime as dt

import pygame

from .. import seb
from ..input import Action
from ..lang import N_, _, tr
from ..theme import mix
from .tools import DAYS, MONTHS as GREG_MONTHS, ToolScreen

ROMAN = ["I", "II", "III", "IV", "V", "VI"]
GREG_SHORT = ["PZT", "SAL", "ÇAR", "PER", "CUM", "CMT", "PAZ"]
NEUTRAL = (96, 88, 80)            # ara gece sayfalarının bandı
CREAM = (232, 224, 204)


def text_on(color) -> tuple[int, int, int]:
    """Renkli bandın üstündeki yazı: açık zeminde koyu, koyu zeminde açık."""
    r, g, b = color
    return (24, 18, 16) if 0.299 * r + 0.587 * g + 0.114 * b > 150 else (246, 238, 226)


def greg_text(d: dt.date) -> str:
    return f"{d.day} {tr(GREG_MONTHS[d.month - 1])} {d.year}"


# Şeb yılının sayfaları
PAGES = [("ay", 1), ("ay", 2), ("ay", 3), ("ikiz", 0), ("ay", 4), ("ay", 5), ("ay", 6), ("yelda", 0)]


def page_of(night: seb.Night) -> tuple[str, int]:
    if night.month:
        return ("ay", night.month.number)
    if night.special == seb.GUEST:
        return ("ay", 2)
    return ("ikiz", 0) if night.group == seb.SUMMER_GROUP else ("yelda", 0)


class CalendarScreen(ToolScreen):
    name = N_("Takvim")

    def __init__(self, app, selected: dt.date | None = None) -> None:
        super().__init__(app)
        self.today = self.current_today()
        self.selected = selected or self.today
        self._day = None

    def current_today(self) -> dt.date:
        raise NotImplementedError

    def update(self, dt_: float) -> None:
        today = self.current_today()
        if today != self._day:              # gece yarısı / öğlen geçince
            self._day, self.today = today, today
            self.app.dirty = True

    def handle(self, action: Action) -> None:
        if action in (Action.UP, Action.DOWN):
            self.selected += dt.timedelta(days=-1 if action is Action.UP else 1)
        elif action is Action.SELECT:
            self.selected = self.today
        elif action in (Action.LEFT1, Action.LEFT2):
            self.selected = self.step_page(-1 if action is Action.LEFT1 else 1)
        elif action is Action.TOP2:
            self.app.replace(self.other(self.app, self.selected))
            self.app.calendar_kind = self.other.kind
        else:
            super().handle(action)

    # -- ortak çizim -----------------------------------------------------------

    def draw_band(self, surf, color, left: str, title: str, subtitle: str, right: str) -> pygame.Rect:
        app, L = self.app, self.app.layout
        band = pygame.Rect(L.left, L.header_rule2_y + 7, L.row_box_w + 9, 44)
        surf.fill(color, band)
        ink = text_on(color)
        x = band.x + 8
        if left:
            r = app.text.draw(surf, left, "body", ink, (x, band.centery), "midleft", raw=True)
            x = r.right + 10
        app.text.draw(surf, title, "body", ink, (x, band.y + 14), "midleft")
        app.text.draw(surf, subtitle, "small", ink, (x, band.y + 33), "midleft")
        app.text.draw(surf, right, "medium", ink, (band.right - 8, band.y + 14), "midright")
        return band

    def draw_info(self, surf, line1: str, line2: str, hints) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        y = L.footer_line_y - 60
        surf.fill(t.rule_dim, (L.left, y - 13, L.row_box_w + 9, 1))
        app.text.draw(surf, line1, "medium", t.fg, (L.left + 6, y), "midleft")
        app.text.draw(surf, line2, "small", t.rule, (L.left + 6, y + 19), "midleft")
        self.draw_frame(surf, hints)

    def grid_area(self, top: int) -> pygame.Rect:
        L = self.app.layout
        return pygame.Rect(L.left + 2, top, L.row_box_w + 6, L.footer_line_y - 76 - top)


class SebCalendar(CalendarScreen):
    kind = "seb"

    def current_today(self) -> dt.date:
        return seb.night_date(dt.datetime.now())

    def step_page(self, step: int) -> dt.date:
        cur = seb.from_date(self.selected)
        i = PAGES.index(page_of(cur)) + step
        year = cur.year + (i // len(PAGES))
        kind, number = PAGES[i % len(PAGES)]
        if kind == "ay":
            keep = cur.night if cur.month else 1
            return seb.to_date(year, number, keep)
        first = seb.SUMMER[0][0] if kind == "ikiz" else seb.WINTER[0][0]
        return seb.special_date(year, first)

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        night = seb.from_date(self.selected)
        kind, number = page_of(night)
        if kind == "ay":
            self._draw_month(surf, night, seb.MONTHS[number - 1])
        else:
            self._draw_special(surf, night, kind)
        if night.special:
            line1, line2 = night.daily(), f"{tr(night.group) + ' · ' if night.group else ''}{greg_text(self.selected)}"
        else:
            line1, line2 = night.daily(), f"{night.official()} · {greg_text(self.selected)}"
        self.draw_info(surf, line1, line2, [(Action.LEFT1, "ÖNCEKİ"), (Action.LEFT2, "SONRAKİ"),
                                            (Action.TOP2, "MİLADİ")])

    def _draw_month(self, surf, night: seb.Night, month: seb.Month) -> None:
        app, t = self.app, self.app.theme
        year = night.year
        start, end = seb.to_date(year, month.number, 1), seb.to_date(year, month.number, 60)
        sub = f"{start.day} {tr(GREG_MONTHS[start.month - 1])} – {end.day} {tr(GREG_MONTHS[end.month - 1])} · {month.short}"
        band = self.draw_band(surf, month.color, ROMAN[month.number - 1], tr(month.name), sub,
                              _("Yıl {n}").format(n=year))

        area = self.grid_area(band.bottom + 26)
        cw, rh = area.w / 6, area.h / 10
        y = band.bottom + 13
        for c, name in enumerate(seb.WEEK):
            cx = round(area.x + (c + 0.5) * cw)
            app.text.draw(surf, name, "small", t.fg if c == 5 else t.rule, (cx, y), "center")
        surf.fill(month.color, (area.x, y + 9, area.w, 1))

        dark = mix(t.bg, t.fg, 0.07)
        tan = mix(t.bg, month.color, 0.38)
        for n in range(1, 61):
            r, c = divmod(n - 1, 6)
            cell = pygame.Rect(round(area.x + c * cw) + 1, round(area.y + r * rh) + 1,
                               round(cw) - 2, round(rh) - 2)
            selected = night.month is month and night.night == n
            fill = month.color if selected else (tan if c == 5 else dark)
            surf.fill(fill, cell)
            if seb.to_date(year, month.number, n) == self.today:
                pygame.draw.rect(surf, t.fg, cell, 2)
            ink = text_on(month.color) if selected else t.fg
            app.text.draw(surf, str(n), "medium", ink, cell.center, "center", raw=True)

        if month.number == 2 and seb.is_leap(year):
            # Konuk Gece: 8 ile 9 arasında (2. hafta, Yatsı ile Zifir arası)
            x = round(area.x + 2 * cw)
            cy = round(area.y + 1.5 * rh)
            on = night.special == seb.GUEST
            radius = 7 if on else 5
            pts = [(x, cy - radius), (x + radius, cy), (x, cy + radius), (x - radius, cy)]
            pygame.draw.polygon(surf, month.color if on else t.fg, pts)
            pygame.draw.polygon(surf, t.bg, pts, 1)

    def _draw_special(self, surf, night: seb.Night, kind: str) -> None:
        app, t = self.app, self.app.theme
        year = night.year
        if kind == "ikiz":
            names, title, sub = seb.SUMMER, seb.SUMMER_GROUP, N_("Yaz gündönümü · aya ve haftaya sayılmaz")
        else:
            names, title, sub = seb.WINTER, seb.WINTER_GROUP, N_("Kış gündönümü · yılın son üç gecesi")
        band = self.draw_band(surf, NEUTRAL, "", tr(title), tr(sub), _("Yıl {n}").format(n=year))
        area = self.grid_area(band.bottom + 14)
        h = min(64, area.h // len(names) - 8)
        for i, (name, _when) in enumerate(names):
            box = pygame.Rect(area.x, area.y + i * (h + 8), area.w, h)
            d = seb.special_date(year, name)
            selected = night.special == name
            longest = name == seb.WINTER[1][0]
            fill = t.fg if selected else (mix(t.bg, CREAM, 0.22) if longest else mix(t.bg, t.fg, 0.07))
            surf.fill(fill, box)
            if d == self.today:
                pygame.draw.rect(surf, t.fg, box, 2)
            ink = t.on_fg if selected else t.fg
            app.text.draw(surf, name, "body", ink, (box.x + 12, box.y + h // 2 - 9), "midleft")
            note = greg_text(d) + (" · " + tr(N_("yılın en uzun gecesi")) if longest else "")
            app.text.draw(surf, note, "small", ink if selected else t.rule, (box.x + 12, box.y + h // 2 + 12), "midleft")


class GregorianCalendar(CalendarScreen):
    kind = "miladi"

    def current_today(self) -> dt.date:
        return dt.date.today()

    def step_page(self, step: int) -> dt.date:
        d = self.selected
        m = d.month - 1 + step
        year, month = d.year + m // 12, m % 12 + 1
        last = (dt.date(year + month // 12, month % 12 + 1, 1) - dt.timedelta(days=1)).day
        return dt.date(year, month, min(d.day, last))

    def draw(self, surf: pygame.Surface) -> None:
        app, t = self.app, self.app.theme
        d = self.selected
        first = d.replace(day=1)
        band = self.draw_band(surf, t.fg, "", f"{tr(GREG_MONTHS[d.month - 1])} {d.year}",
                              _("Miladi takvim"), seb.from_date(d).short())

        area = self.grid_area(band.bottom + 26)
        cw = area.w / 7
        y = band.bottom + 13
        for c, name in enumerate(GREG_SHORT):
            app.text.draw(surf, name, "small", t.rule, (round(area.x + (c + 0.5) * cw), y), "center")
        surf.fill(t.rule, (area.x, y + 9, area.w, 1))

        offset = first.weekday()
        days = (self.step_page_from(first, 1) - first).days
        rows = (offset + days + 6) // 7
        rh = area.h / max(rows, 5)
        dark = mix(t.bg, t.fg, 0.07)
        for i in range(days):
            day = first + dt.timedelta(days=i)
            r, c = divmod(offset + i, 7)
            cell = pygame.Rect(round(area.x + c * cw) + 1, round(area.y + r * rh) + 1,
                               round(cw) - 2, round(rh) - 2)
            selected = day == d
            surf.fill(t.fg if selected else dark, cell)
            if day == self.today:
                pygame.draw.rect(surf, t.fg, cell, 2)
            ink = t.on_fg if selected else (t.rule if c >= 5 else t.fg)
            app.text.draw(surf, str(day.day), "medium", ink, (cell.centerx, cell.centery - 6), "center", raw=True)
            # Altta o akşamın Şeb gecesi: sayı, ara gecede yıldız
            n = seb.from_date(day)
            mark = str(n.night) if n.month else "✦"
            color = ink if selected else (n.month.color if n.month else t.rule)
            app.text.draw(surf, mark, "small", color, (cell.centerx, cell.centery + 9), "center", raw=True)

        n = seb.from_date(d)
        self.draw_info(surf, f"{greg_text(d)}, {tr(DAYS[d.weekday()])}", n.daily(),
                       [(Action.LEFT1, "ÖNCEKİ"), (Action.LEFT2, "SONRAKİ"), (Action.TOP2, "ŞEB")])

    @staticmethod
    def step_page_from(d: dt.date, step: int) -> dt.date:
        m = d.month - 1 + step
        return dt.date(d.year + m // 12, m % 12 + 1, 1)


SebCalendar.other = GregorianCalendar
GregorianCalendar.other = SebCalendar


def open_calendar(app) -> CalendarScreen:
    """Son açılan takvim (oturum boyunca hatırlanır); ilk sefer Şeb."""
    kind = getattr(app, "calendar_kind", "seb")
    return GregorianCalendar(app) if kind == "miladi" else SebCalendar(app)
