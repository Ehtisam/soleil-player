"""Müzik / Yerel Müzikler ve Medya / Ses.

Yerel Müzikler kütüphaneyi (library.py) gösterir: Tüm Şarkılar,
Sanatçılar, Albümler. Albüm ve şarkı listeleri playlist ekranıyla açılır
(kapak, ad, açıklama, şarkılar); şarkı seçince kuyruk başlar ve oynatıcı
açılır.

Medya / Ses: medya/ses klasöründeki dosyalar (ses kayıtları vb.), sırayla.
"""

from __future__ import annotations

from ..lang import _
from ..documents import AUDIO_EXTENSIONS, list_documents
from ..library import UNKNOWN_ARTIST, Album, read_track
from ..playback import Track
from ..sample_data import Playlist
from ..timers import clock_text
from ..ui.listview import ListItem, ListScreen
from .player import PlayerScreen
from .playlist import PlaylistScreen

TITLE = "Sols / Müzik / Yerel"


def _album_playlist(album: Album) -> Playlist:
    total = sum(t.duration for t in album.tracks)
    parts = [album.artist] + ([album.year] if album.year else []) + \
        [_("{n} şarkı").format(n=len(album.tracks)), clock_text(total)]
    return Playlist(album.name, " · ".join(parts), album.tracks)


def album_screen(app, album: Album, title: str) -> PlaylistScreen:
    return PlaylistScreen(app, _album_playlist(album), f"{title} / {album.name}")


def _albums_screen(app, albums: list[Album], title: str) -> ListScreen:
    screen = ListScreen(app, [
        ListItem(a.name, raw=True, right=f"[{len(a.tracks)}]", open=lambda a=a: album_screen(app, a, title))
        for a in albums
    ])
    screen.title = title
    return screen


def artist_screen(app, name: str, albums: list[Album], title: str):
    """Tek albümlü sanatçı doğrudan albümünü açar."""
    if len(albums) == 1:
        return album_screen(app, albums[0], title)
    return _albums_screen(app, albums, f"{title} / {name}")


class LocalMusicMenu(ListScreen):
    """Tarama sürerken sayılar yüzde olarak görünür, bitince dolar."""
    title = TITLE

    def __init__(self, app) -> None:
        lib = app.library
        lib.ensure_scanned()

        def count(get):
            def value():
                if lib.state != "ready":
                    return f"[%{round(lib.progress * 100)}]"
                return f"[{len(get())}]"
            return value

        def when_ready(make):
            def act():
                if lib.state != "ready":
                    app.toast("TARANIYOR", f"%{round(lib.progress * 100)}")
                elif not lib.tracks:
                    app.toast("MÜZİK YOK", "medya/muzik klasörü boş")
                else:
                    app.push(make())
            return act

        def rescan():
            lib.rescan()
            app.toast("YENİDEN TARANIYOR")

        def liked():
            return [t for t in lib.tracks if app.likes.has(t)]

        def open_liked():
            if lib.state != "ready":
                app.toast("TARANIYOR", f"%{round(lib.progress * 100)}")
                return
            tracks = liked()
            if not tracks:
                app.toast("BEĞENİ YOK", "oynatıcıda İ ile beğen")
                return
            app.push(PlaylistScreen(app, Playlist("Beğenilenler", _("{n} şarkı").format(n=len(tracks)), tuple(tracks)),
                                    f"{TITLE} / Beğenilenler"))

        def search():
            from .search import SearchScreen
            app.push(SearchScreen(app))

        items = [
            ListItem("Ara", act=search),
            ListItem("Beğenilenler", value=count(liked), act=open_liked),
            ListItem("Tüm Şarkılar", value=count(lambda: lib.tracks), act=when_ready(
                lambda: PlaylistScreen(app, Playlist("Tüm Şarkılar", _("{n} şarkı").format(n=len(lib.tracks)),
                                                     tuple(lib.tracks)), f"{TITLE} / Tümü"))),
            ListItem("Sanatçılar", value=count(lambda: lib.artists), act=when_ready(lambda: self._artists())),
            ListItem("Albümler", value=count(lambda: lib.albums), act=when_ready(
                lambda: _albums_screen(app, lib.albums, f"{TITLE} / Albümler"))),
            ListItem("Yeniden Tara", act=rescan),
        ]
        super().__init__(app, items)

    def _artists(self) -> ListScreen:
        app, lib = self.app, self.app.library
        title = f"{TITLE} / Sanatçılar"

        screen = ListScreen(app, [ListItem(name, raw=True, right=f"[{len(albums)}]",
                                           open=lambda n=name, a=albums: artist_screen(app, n, a, title))
                                  for name, albums in lib.artists.items()])
        screen.title = title
        return screen

    def update(self, dt: float) -> None:
        self.animating = self.app.library.state == "scanning"


def media_sounds(app) -> ListScreen:
    docs = list_documents("ses", AUDIO_EXTENSIONS)
    tracks = []
    for doc in docs:
        info = read_track(doc.path, doc.sample) or {}
        artist = info.get("artist", UNKNOWN_ARTIST)
        if artist == UNKNOWN_ARTIST:
            artist = "Ses Kaydı"          # etiketsiz dosya (ör. Ses Kaydedici kayıtları)
        tracks.append(Track(info.get("title") or doc.name, artist, "Medya / Ses",
                            info.get("duration", 0.0) or 1.0, path=doc.path, source="DOSYA",
                            quality=info.get("quality", "")))

    def play(i):
        def act():
            app.playback.play_queue(tracks, i)
            app.push(PlayerScreen(app))
        return act

    screen = ListScreen(app, [ListItem(t.title, raw=True, right=f"[{clock_text(t.duration)}]", act=play(i))
                              for i, t in enumerate(tracks)])
    screen.title = "Sols / Medya / Ses"
    return screen
