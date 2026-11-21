"""Tuğla Kırma. Raket encoder ile kayar (eski Atari kolları gibi).

Top raketin neresine çarparsa o açıyla seker. Bütün tuğlalar kırılınca
sonraki seviye: top biraz hızlanır. 3 can.
"""

from __future__ import annotations

import math
import random

import pygame

from ...lang import _
from ...input import Action
from ...theme import mix
from .base import GameScreen

COLS, ROWS = 8, 6
BRICK_H = 12
PADDLE_W, PADDLE_H = 50, 6
PADDLE_STEP = 16            # bir encoder adımında raketin hedefi bu kadar kayar
BALL = 6
SPEED = 190.0               # px/sn, seviyeyle artar
LIVES = 3


class Breakout(GameScreen):
    key = "breakout"
    name = "Tuğla Kırma"

    def help_lines(self) -> list[str]:
        return ["ENCODER: RAKET", "TIKLA: TOPU AT"]

    def status(self) -> str:
        return _("CAN {can}  SV {sv}").format(can=self.lives, sv=self.level)

    def reset(self) -> None:
        self.lives = LIVES
        self.level = 1
        f = self.field
        self.paddle_x = float(f.centerx)
        self.paddle_target = self.paddle_x
        self._new_level()

    def _new_level(self) -> None:
        f = self.field
        self.brick_w = (f.w - 4) / COLS
        self.bricks = {(c, r) for c in range(COLS) for r in range(ROWS)}
        self._serve()

    def _serve(self) -> None:
        self.stuck = True           # top rakette bekliyor
        self.vx, self.vy = 0.0, 0.0
        self._place_ball_on_paddle()

    def _place_ball_on_paddle(self) -> None:
        f = self.field
        self.bx = self.paddle_x - BALL / 2
        self.by = f.bottom - 18 - BALL

    def _launch(self) -> None:
        angle = math.radians(random.uniform(-35, 35))
        speed = SPEED * (1 + 0.12 * (self.level - 1))
        self.vx, self.vy = speed * math.sin(angle), -speed * math.cos(angle)
        self.stuck = False

    # -- girdi -------------------------------------------------------------------

    def handle_game(self, action: Action) -> None:
        f = self.field
        if action in (Action.UP, Action.DOWN):
            step = PADDLE_STEP if action is Action.DOWN else -PADDLE_STEP
            half = PADDLE_W / 2
            self.paddle_target = max(f.x + half, min(f.right - half, self.paddle_target + step))
        elif action is Action.SELECT and self.state == "playing" and self.stuck:
            self._launch()

    def start(self) -> None:
        was_ready = self.state in ("ready", "over")
        super().start()
        if was_ready and self.stuck:
            self._launch()

    # -- oyun ----------------------------------------------------------------------

    def step(self, dt: float) -> None:
        # Raket hedefe yumuşak gider
        self.paddle_x += (self.paddle_target - self.paddle_x) * min(1.0, dt * 18)
        if self.stuck:
            self._place_ball_on_paddle()
            return
        # Küçük adımlarla ilerle: hızlı top ince tuğladan geçmesin
        steps = max(1, int(max(abs(self.vx), abs(self.vy)) * dt / 3) + 1)
        for _ in range(steps):
            if self._move(dt / steps):
                break

    def _move(self, dt: float) -> bool:
        f = self.field
        self.bx += self.vx * dt
        self.by += self.vy * dt
        # Duvarlar
        if self.bx < f.x:
            self.bx, self.vx = f.x, abs(self.vx)
        elif self.bx + BALL > f.right:
            self.bx, self.vx = f.right - BALL, -abs(self.vx)
        if self.by < f.y:
            self.by, self.vy = f.y, abs(self.vy)
        # Raket
        paddle = self._paddle_rect()
        ball = pygame.Rect(round(self.bx), round(self.by), BALL, BALL)
        if self.vy > 0 and ball.colliderect(paddle):
            hit = (self.bx + BALL / 2 - paddle.centerx) / (PADDLE_W / 2)   # -1..1
            hit = max(-1.0, min(1.0, hit))
            speed = math.hypot(self.vx, self.vy)
            angle = math.radians(hit * 60)
            self.vx, self.vy = speed * math.sin(angle), -speed * math.cos(angle)
            self.by = paddle.top - BALL
        # Tuğlalar
        for brick in list(self.bricks):
            rect = self._brick_rect(*brick)
            if ball.colliderect(rect):
                self.bricks.discard(brick)
                self.score += 10 * (ROWS - brick[1])
                # Hangi kenardan çarptı: az giren eksende sek
                dx = min(ball.right - rect.left, rect.right - ball.left)
                dy = min(ball.bottom - rect.top, rect.bottom - ball.top)
                if dx < dy:
                    self.vx = -self.vx
                else:
                    self.vy = -self.vy
                break
        if not self.bricks:
            self.level += 1
            self.score += 100
            self._new_level()
            self._launch()
            return True
        # Düştü
        if self.by > f.bottom:
            self.lives -= 1
            if self.lives <= 0:
                self.game_over()
            else:
                self._serve()
            return True
        return False

    # -- çizim ---------------------------------------------------------------------

    def _paddle_rect(self) -> pygame.Rect:
        f = self.field
        return pygame.Rect(round(self.paddle_x - PADDLE_W / 2), f.bottom - 18, PADDLE_W, PADDLE_H)

    def _brick_rect(self, c: int, r: int) -> pygame.Rect:
        f = self.field
        x = f.x + 2 + c * self.brick_w
        y = f.y + 24 + r * (BRICK_H + 3)
        return pygame.Rect(round(x) + 1, y, round(self.brick_w) - 3, BRICK_H)

    def draw_field(self, surf: pygame.Surface, field: pygame.Rect) -> None:
        t = self.app.theme
        for c, r in self.bricks:
            # Üst sıralar parlak, alta doğru soluk
            color = mix(t.fg, t.bg, r * 0.11)
            surf.fill(color, self._brick_rect(c, r))
        paddle = self._paddle_rect()
        surf.fill(t.fg, paddle)
        surf.fill(t.rule, (paddle.x, paddle.bottom, paddle.w, 2))
        surf.fill(t.fg, (round(self.bx), round(self.by), BALL, BALL))
