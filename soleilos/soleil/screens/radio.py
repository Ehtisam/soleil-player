"""Müzik / Radyo: favoriler, Türkiye ve dünyadan popüler istasyonlar, arama.

İstasyon seçince çalmaya başlar ve oynatıcı açılır; oynatıcıda Sol 1 / Sol 2
listedeki önceki / sonraki istasyon, İ favorilere ekler.
"""

from __future__ import annotations

from ..ui.listview import BACK, ListItem, ListScreen
from .notebook import TextEditor
from .player import PlayerScreen

TITLE = "Sols / Müzik / Radyo"


class StationList(ListScreen):
    """İstasyon listesi; liste arka planda gelirken "YÜKLENİYOR" görünür."""

    def __init__(self, app, title: str, key: str = "", favorites: bool = False) -> None:
        self.app = app
        self.key = key
        self.favorites = favorites
        self._state = None
        super().__init__(app, [])
        self.title = title
        self._refresh()

    def _source(self):
        if self.favorites:
            return "ready", list(self.app.radio.favorites)
        return self.app.radio.get(self.key)

    def _refresh(self) -> None:
        state, tracks = self._source()
        signature = (state, tuple(t.ref for t in tracks))
        if signature == self._state:          # değişen yok
            return
        self._state = signature
        app = self.app
        if not tracks:
            label = {"loading": "YÜKLENİYOR...", "error": "BAĞLANTI YOK"}.get(state, "İSTASYON YOK")
            items = [ListItem(label, act=lambda: None)]
        else:
            def play(i):
                def act():
                    app.playback.play_queue(tracks, i)
                    if not app.audio:
                        app.toast("SES MOTORU YOK", "mpv kurulu değil")
                    app.push(PlayerScreen(app))
                return act
            items = [ListItem(t.title, raw=True, right=f"[{t.quality.split(' ')[-1]}]" if " " in t.quality else None,
                              act=play(i)) for i, t in enumerate(tracks)]
        self.rows = [BACK] + items
        self.selected = min(max(self.selected, 1), len(self.rows) - 1)
        self._scroll_to_selected()

    def update(self, dt: float) -> None:
        self._refresh()
        super().update(dt)


def radio_menu(app) -> ListScreen:
    radio = app.radio

    def search():
        def done(query: str) -> None:
            query = query.strip()
            if query:
                key = f"ara:{query.lower()}"
                radio.forget(key)
                app.push(StationList(app, f"{TITLE} / Ara: {query}", key))
        app.push(TextEditor(app, f"{TITLE} / Ara", "", on_close=done, single_line=True, max_len=30))

    screen = ListScreen(app, [
        ListItem("Favoriler", value=lambda: f"[{len(radio.favorites)}]",
                 open=lambda: StationList(app, f"{TITLE} / Favoriler", favorites=True)),
        ListItem("Türkiye", right="[POPÜLER]", open=lambda: StationList(app, f"{TITLE} / Türkiye", "tr")),
        ListItem("Dünya", right="[POPÜLER]", open=lambda: StationList(app, f"{TITLE} / Dünya", "world")),
        ListItem("Ara", act=search),
    ])
    screen.title = TITLE
    return screen
