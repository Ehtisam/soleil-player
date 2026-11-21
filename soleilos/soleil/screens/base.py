from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..input import Action

if TYPE_CHECKING:
    from ..app import App


class Screen:
    """Bütün ekranların temeli. Uygulama ekranları bir yığında tutar:
    yeni ekran açmak push, geri dönmek pop."""

    title = "System // Solshuenshia"
    # Animasyonlu ekranlar True yapar; diğerleri sadece bir şey
    # değişince yeniden çizilir.
    animating = False

    def __init__(self, app: App) -> None:
        self.app = app

    def handle(self, action: Action) -> None:
        if action is Action.BACK:
            self.app.pop()
        elif action is Action.TOP1:
            open_player(self.app)

    def closed(self) -> None:
        """Ekran yığından çıkarken çağrılır (ör. okuma yerini kaydetmek için)."""

    def update(self, dt: float) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:
        pass


def open_player(app: App) -> None:
    """Üst 1: her yerden oynatıcıya geçiş (oynatıcının kendisinde sözleri açar)."""
    from .player import PlayerScreen
    if app.playback.current:
        app.push(PlayerScreen(app))
    else:
        app.toast("ÇALAN YOK", "MÜZİK'TEN ŞARKI SEÇ")
