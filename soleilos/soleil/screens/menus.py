"""Alt menüler. Başlıklarda Solshuenshia "Sols" diye kısaltılır.

Spotify ve medya listelerindeki veriler şimdilik örnek (sample_data.py);
ileride Spotify'dan ve SD karttan okunacak. Notlar ve e-kitaplar gerçek
dosyalardan geliyor (documents.py).
"""

from __future__ import annotations

from .. import sample_data
from ..documents import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, format_size, list_documents
from ..ui.listview import ListItem, ListScreen
from . import gallery
from .placeholder import Placeholder
from .bluetooth import BluetoothMenu
from .local_music import LocalMusicMenu, media_sounds
from .playlist import PlaylistScreen
from .radio import radio_menu
from .reader import ReaderScreen


def _menu(app, title: str, items: list[ListItem]) -> ListScreen:
    screen = ListScreen(app, items)
    screen.title = title
    return screen


def _todo(app, title: str):
    return lambda: Placeholder(app, title)


# -- Müzik --------------------------------------------------------------------

def music_menu(app) -> ListScreen:
    t = "Sols / Müzik"
    return _menu(app, t, [
        ListItem("Yerel Müzikler", right="[SD-CARD]", open=lambda: LocalMusicMenu(app)),
        ListItem("Spotify", right="[WI-FI]", open=lambda: spotify_menu(app)),
        ListItem("Bluetooth", right="[BT]", open=lambda: BluetoothMenu(app)),
        ListItem("Radyo", right="[WI-FI]", open=lambda: radio_menu(app)),
    ])


def spotify_menu(app) -> ListScreen:
    t = "Sols / Müzik / Spotify"
    return _menu(app, t, [
        ListItem("Arama", open=_todo(app, "Spotify / Arama")),
        ListItem("Kütüphane", open=lambda: spotify_library(app)),
        ListItem("Haftalık Keşif", open=_todo(app, "Spotify / Haftalık Keşif")),
        ListItem("Dinlenenler", open=_todo(app, "Spotify / Dinlenenler")),
    ])


def spotify_library(app) -> ListScreen:
    t = "Spotify / Kütüphane"

    def opener(name, playlist):
        if playlist is None:
            return _todo(app, f"{t} / {name}")
        return lambda: PlaylistScreen(app, playlist, f"{t} / {name}")

    return _menu(app, t, [ListItem(name, raw=True, open=opener(name, pl)) for name, pl in sample_data.LIBRARY])


# -- Medya --------------------------------------------------------------------

def media_menu(app) -> ListScreen:
    t = "Sols / Medya"
    texts = list_documents("metin")
    text_size = format_size(sum(d.size for d in texts))
    pics = gallery.images()
    pic_size = format_size(sum(d.size for d in pics))
    videos = list_documents("video", VIDEO_EXTENSIONS)
    sounds = list_documents("ses", AUDIO_EXTENSIONS)

    def total(docs):
        return format_size(sum(d.size for d in docs))

    return _menu(app, t, [
        ListItem("Görsel", count=f"[{len(pics):02d}]", right=f"[{pic_size}]", open=lambda: gallery.gallery_list(app)),
        ListItem("Video", count=f"[{len(videos):02d}]", right=f"[{total(videos)}]", open=_todo(app, f"{t} / Video")),
        ListItem("Ses", count=f"[{len(sounds):02d}]", right=f"[{total(sounds)}]", open=lambda: media_sounds(app)),
        ListItem("Metin", count=f"[{len(texts):02d}]", right=f"[{text_size}]", open=lambda: text_files(app)),
    ])


def _documents(app, title: str, kind: str) -> ListScreen:
    """Dosya listesi; sağda okunma yüzdesi (hiç açılmadıysa YENİ)."""
    def opener(doc):
        return lambda: ReaderScreen(app, doc, f"{title} / {doc.name}")

    return _menu(app, title, [
        ListItem(doc.name, raw=True, value=lambda doc=doc: app.reading.label(doc), open=opener(doc))
        for doc in list_documents(kind)
    ])


def text_files(app) -> ListScreen:
    return _documents(app, "Sols / Medya / TXT", "metin")


# -- E-Kitap ------------------------------------------------------------------

def ebook_menu(app) -> ListScreen:
    return _documents(app, "Sols / E-Kitap", "kitap")
