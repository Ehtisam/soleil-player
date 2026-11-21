"""Testlerde ortak: uygulamayı kurmak, tuşa basmak, zamanı ilerletmek."""

from __future__ import annotations

import time

from soleil.app import App
from soleil.input import Action
from soleil.screens.main_menu import MainMenu

from . import clean_home


def make_app(menu: bool = True) -> App:
    clean_home()
    app = App(headless=True)
    if menu:
        app.push(MainMenu(app))
    return app


def press(app: App, *actions: Action) -> None:
    for a in actions:
        app.handle(a)
        app.tick(1 / 30)


def tick(app: App, seconds: float, real: bool = False) -> None:
    """Uygulama zamanını ilerletir. real=True ise gerçekten de bekler
    (arka plan thread'leri ve mpv için)."""
    steps = max(1, int(seconds * 30))
    for _ in range(steps):
        app.tick(1 / 30)
        if real:
            time.sleep(1 / 30)


def open_section(app: App, index: int) -> None:
    """Ana menüde index'inci bölümü açar (0 = MÜZİK)."""
    while len(app.stack) > 1:
        app.pop()
    menu = app.screen
    menu.selected = index
    press(app, Action.SELECT)


def render_ok(app: App) -> None:
    """Ekranı çizer; hata varsa test düşer."""
    app.render()
