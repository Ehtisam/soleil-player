"""Oyunlar menüsü. Yeni oyun eklemek için GAMES listesine bir GameScreen
alt sınıfı koymak yeter."""

from __future__ import annotations

from ...ui.listview import ListItem, ListScreen
from .base import scores
from .breakout import Breakout
from .snake import Snake

GAMES = [Breakout, Snake]


def games_menu(app) -> ListScreen:
    def best(game) -> str:
        score = scores(app).best(game.key)
        return f"[{score}]" if score else ""

    screen = ListScreen(app, [
        ListItem(game.name, value=lambda game=game: best(game), open=lambda game=game: game(app))
        for game in GAMES
    ])
    screen.title = "Sols / Oyunlar"
    return screen
