"""Oyunların ortak çerçevesi: skor şeridi, oyun alanı, başla / duraklat /
bitti katmanları ve en yüksek skorlar (~/.soleil/oyunlar.json).

Bütün oyunlarda:
  encoder tıklama : başla / devam et
  encoder uzun bas: duraklat
  L (Sol 3)       : oynarken duraklatır; duraklamışken ya da oyun bitince çıkar
  E (Üst 1)       : oyunu duraklatıp oynatıcıyı açar
"""

from __future__ import annotations

import json

import pygame

from ...lang import _
from ... import config
from ...input import Action
from ...ui import chrome, glyphs
from ..base import Screen

SCORES_PATH = config.DATA / "oyunlar.json"


class HighScores:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.data: dict[str, int] = {}
        if enabled:
            try:
                data = json.loads(SCORES_PATH.read_text(encoding="utf-8"))
                self.data = {k: int(v) for k, v in data.items()}
            except (OSError, ValueError, AttributeError):
                pass

    def best(self, game: str) -> int:
        return self.data.get(game, 0)

    def submit(self, game: str, score: int) -> bool:
        """Rekor kırıldıysa kaydeder ve True döner."""
        if score <= self.best(game):
            return False
        self.data[game] = score
        if self.enabled:
            try:
                SCORES_PATH.parent.mkdir(parents=True, exist_ok=True)
                SCORES_PATH.write_text(json.dumps(self.data, indent=2), encoding="utf-8")
            except OSError:
                pass
        return True


def scores(app) -> HighScores:
    if not hasattr(app, "_high_scores"):
        app._high_scores = HighScores(enabled=not app.headless)
    return app._high_scores


class GameScreen(Screen):
    """Alt sınıflar: key, name, reset(), step(dt), handle_game(action),
    draw_field(surf, field). Skoru self.score'da tutar, bitince game_over()."""
    key = ""
    name = ""
    animating = True

    def __init__(self, app) -> None:
        super().__init__(app)
        self.state = "ready"        # ready, playing, paused, over
        self.score = 0
        self.record = False
        self.reset()

    @property
    def title(self) -> str:
        return f"Sols / Oyunlar / {self.name}"

    @property
    def field(self) -> pygame.Rect:
        L = self.app.layout
        top = L.header_rule2_y + 30
        return pygame.Rect(L.left + 2, top, L.content_w - 4, L.footer_line_y - 8 - top)

    # -- alt sınıfların dolduracağı yerler ---------------------------------------

    def reset(self) -> None: ...
    def step(self, dt: float) -> None: ...
    def handle_game(self, action: Action) -> None: ...
    def draw_field(self, surf: pygame.Surface, field: pygame.Rect) -> None: ...
    def status(self) -> str:
        return ""

    # -- akış --------------------------------------------------------------------

    def start(self) -> None:
        if self.state == "over":
            self.score, self.record = 0, False
            self.reset()
        self.state = "playing"

    def game_over(self) -> None:
        self.state = "over"
        self.record = scores(self.app).submit(self.key, self.score)

    def handle(self, action: Action) -> None:
        if self.state == "playing":
            if action in (Action.BACK, Action.HOLD):
                self.state = "paused"
            elif action is Action.TOP1:
                self.state = "paused"
                super().handle(action)
            else:
                self.handle_game(action)
            return
        if action is Action.SELECT:
            self.start()
        elif action is Action.BACK:
            self.app.pop()
        elif action is Action.TOP1:
            super().handle(action)
        elif self.state == "ready":
            self.handle_game(action)     # başlamadan da raket oynasın vb.

    def update(self, dt: float) -> None:
        if self.state == "playing":
            self.step(min(dt, 0.05))     # takılmada top duvardan geçmesin
            self.app.last_input = self.app.time    # oynarken ekran uyumasın

    # -- çizim -------------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        chrome.draw_header(app, surf, self.title)
        # Skor şeridi
        y = L.header_rule2_y + 15
        app.text.draw(surf, _("SKOR {n}").format(n=self.score), "medium", t.fg, (L.left + 4, y), "midleft")
        best = max(scores(app).best(self.key), self.score)
        app.text.draw(surf, _("EN İYİ {n}").format(n=best), "small", t.rule, (L.left + L.content_w - 4, y), "midright")
        extra = self.status()
        if extra:
            app.text.draw(surf, extra, "small", t.fg, (L.width // 2 + 10, y), "center")

        field = self.field
        pygame.draw.rect(surf, t.rule_dim, field.inflate(2, 2), 1)
        old_clip = surf.get_clip()
        surf.set_clip(field)
        self.draw_field(surf, field)
        surf.set_clip(old_clip)

        if self.state != "playing":
            self._draw_overlay(surf, field)
        chrome.draw_footer(app, surf)

    def help_lines(self) -> list[str]:
        return []

    def _draw_overlay(self, surf: pygame.Surface, field: pygame.Rect) -> None:
        app, t = self.app, self.app.theme
        shade = pygame.Surface(field.size, pygame.SRCALPHA)
        shade.fill((*t.bg, 170))
        surf.blit(shade, field.topleft)

        lines = []
        if self.state == "ready":
            title, lines = self.name.upper(), self.help_lines()
            hints = [(Action.SELECT, "BAŞLA"), (Action.BACK, "ÇIK")]
        elif self.state == "paused":
            title = "DURAKLADI"
            hints = [(Action.SELECT, "DEVAM"), (Action.BACK, "ÇIK")]
        else:
            title = "OYUN BİTTİ"
            lines = [_("SKOR {n}").format(n=self.score)] + (["YENİ REKOR!"] if self.record else [])
            hints = [(Action.SELECT, "TEKRAR"), (Action.BACK, "ÇIK")]

        box = pygame.Rect(0, 0, 240, 74 + len(lines) * 20)
        box.center = field.center
        chrome.draw_panel(app, surf, box)
        y = box.y + 22
        app.text.draw(surf, title, "body", t.fg, (box.centerx, y), "center")
        y += 26
        for line in lines:
            app.text.draw(surf, line, "small", t.fg if line == "YENİ REKOR!" else t.rule, (box.centerx, y), "center")
            y += 20
        glyphs.draw_hints(app, surf, hints, t.rule, (box.centerx, box.bottom - 16), "center")
