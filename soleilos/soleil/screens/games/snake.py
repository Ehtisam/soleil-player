"""Yılan. Encoder yılanı döndürür: geri çevirmek sola, ileri çevirmek sağa
(yılanın kendi yönüne göre). Yem yedikçe uzar ve hızlanır; duvara ya da
kendine çarpınca biter.
"""

from __future__ import annotations

import random

import pygame

from ...lang import _
from ...input import Action
from ...theme import mix
from .base import GameScreen

CELL = 12
START_LEN = 4
START_SPEED = 6.0           # hücre/sn
MAX_SPEED = 14.0
DIRS = [(1, 0), (0, 1), (-1, 0), (0, -1)]   # sağ, aşağı, sol, yukarı (saat yönünde)


class Snake(GameScreen):
    key = "snake"
    name = "Yılan"

    def help_lines(self) -> list[str]:
        return ["ENCODER: SOLA / SAĞA DÖN", "YEMİ YE, KENDİNE ÇARPMA"]

    def status(self) -> str:
        return _("UZUNLUK {n}").format(n=len(self.body))

    @property
    def grid(self) -> tuple[int, int]:
        f = self.field
        return f.w // CELL, f.h // CELL

    def reset(self) -> None:
        cols, rows = self.grid
        y = rows // 2
        self.body = [(cols // 2 - i, y) for i in range(START_LEN)]   # baş önde
        self.dir = 0
        self.turns: list[int] = []      # sıradaki dönüşler (hızlı çevirmeler kaybolmasın)
        self.timer = 0.0
        self.food = self._place_food()
        self.ate_at = -10.0

    def _place_food(self):
        cols, rows = self.grid
        free = [(x, y) for x in range(cols) for y in range(rows) if (x, y) not in self.body]
        return random.choice(free) if free else None

    @property
    def speed(self) -> float:
        return min(MAX_SPEED, START_SPEED + (len(self.body) - START_LEN) * 0.25)

    def handle_game(self, action: Action) -> None:
        if self.state != "playing":
            return
        if action in (Action.UP, Action.DOWN) and len(self.turns) < 2:
            self.turns.append(-1 if action is Action.UP else 1)

    def step(self, dt: float) -> None:
        self.timer += dt
        interval = 1.0 / self.speed
        while self.timer >= interval and self.state == "playing":
            self.timer -= interval
            self._advance()

    def _advance(self) -> None:
        if self.turns:
            self.dir = (self.dir + self.turns.pop(0)) % 4
        dx, dy = DIRS[self.dir]
        hx, hy = self.body[0]
        head = (hx + dx, hy + dy)
        cols, rows = self.grid
        tail_moves = head != self.food
        body = self.body[:-1] if tail_moves else self.body
        if not (0 <= head[0] < cols and 0 <= head[1] < rows) or head in body:
            self.game_over()
            return
        self.body.insert(0, head)
        if tail_moves:
            self.body.pop()
        else:
            self.score += 10
            self.ate_at = self.app.time
            self.food = self._place_food()
            if self.food is None:          # bütün alanı doldurdu
                self.game_over()

    def draw_field(self, surf: pygame.Surface, field: pygame.Rect) -> None:
        t = self.app.theme
        cols, rows = self.grid
        ox = field.x + (field.w - cols * CELL) // 2
        oy = field.y + (field.h - rows * CELL) // 2
        # Hafif nokta ızgara
        for x in range(cols):
            for y in range(0, rows, 2):
                if (x + y) % 4 == 0:
                    surf.fill(t.rule_dim_soft, (ox + x * CELL + CELL // 2, oy + y * CELL + CELL // 2, 1, 1))

        if self.food:
            fx, fy = self.food
            pulse = int(self.app.time * 3) % 2
            r = pygame.Rect(ox + fx * CELL + 2, oy + fy * CELL + 2, CELL - 4, CELL - 4)
            surf.fill(t.fg, r.inflate(-2, -2) if pulse else r)

        n = len(self.body)
        for i, (x, y) in enumerate(self.body):
            color = t.fg if i == 0 else mix(t.fg, t.rule, min(1.0, i / max(1, n) * 1.2))
            surf.fill(color, (ox + x * CELL + 1, oy + y * CELL + 1, CELL - 2, CELL - 2))
        # Baştaki göz
        hx, hy = self.body[0]
        dx, dy = DIRS[self.dir]
        ex = ox + hx * CELL + CELL // 2 + dx * 2 - 1
        ey = oy + hy * CELL + CELL // 2 + dy * 2 - 1
        surf.fill(t.bg, (ex, ey, 2, 2))
