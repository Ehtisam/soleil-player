from __future__ import annotations

from ..input import Action
from ..ui.listview import ListItem, ListScreen
from . import games, menus, tools
from .notebook import NotebookMenu
from .recorder import RecorderScreen
from .placeholder import Placeholder
from .settings_screen import SettingsScreen

# (etiket, ikon, alt menüyü kuran fonksiyon ya da henüz yoksa başlığı)
SECTIONS = [
    ("MÜZİK", "music", menus.music_menu),
    ("MEDYA", "monitor", menus.media_menu),
    ("OYUNLAR", "games", games.games_menu),
    ("E-KİTAP", "book", menus.ebook_menu),
    ("NOT DEFTERİ", "notes", NotebookMenu),
    ("SİSTEM AYARLARI", "settings", SettingsScreen),
    ("SES KAYDEDİCİ", "mic", RecorderScreen),
    ("ARAÇLAR", "tools", tools.tools_menu),
]


class MainMenu(ListScreen):
    title = "System // Solshuenshia"

    def __init__(self, app, selected: int = 0) -> None:
        items = []
        for label, icon, target in SECTIONS:
            if callable(target):
                opener = lambda target=target: target(app)
            else:
                opener = lambda name=target: Placeholder(app, f"Sols / {name}")
            items.append(ListItem(label, icon, open=opener))
        super().__init__(app, items, selected, back_row=False)

    def handle(self, action) -> None:
        # Ana menüden geri gidilecek yer yok
        if action is not Action.BACK:
            super().handle(action)
