"""Müzik: kütüphane taraması, kapaklar, .lrc sözler ve mpv ile gerçek çalma
(sessiz). mpv bulunamazsa gerçek çalma testleri atlanır."""

from __future__ import annotations

import time
import unittest

from soleil.input import Action as A

from .yardim import make_app, press, render_ok, tick


def wait(cond, timeout=10.0, app=None):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        if app:
            app.tick(1 / 30)
        time.sleep(0.02)
    return False


def ready_library(app):
    app.library.ensure_scanned()
    assert wait(lambda: app.library.state == "ready")
    return app.library


class Kutuphane(unittest.TestCase):
    def test_tarama_etiketler_kapak_sozler(self):
        app = make_app()
        lib = ready_library(app)
        self.assertEqual(len(lib.tracks), 4)
        self.assertEqual(sorted(a.name for a in lib.albums), ["Amber Kasetler", "Gece Modu"])
        amber = next(a for a in lib.albums if a.name == "Amber Kasetler")
        self.assertEqual([t.title for t in amber.tracks], ["Gün Doğumu", "Kadran", "Amber Işık"])
        self.assertTrue(amber.tracks[2].quality.startswith("FLAC"))
        for t in lib.tracks:                         # gömülü ve klasör kapakları
            self.assertTrue(wait(lambda: app.covers.get(t) is not None), t.title)
        gece = next(a for a in lib.albums if a.name == "Gece Modu").tracks[0]
        state, lyrics = app.lyrics.get(gece)
        self.assertEqual((state, lyrics.source, lyrics.synced), ("found", "LRC DOSYASI", True))

    def test_menu_ve_oynatici_cizilir(self):
        from soleil.screens.local_music import LocalMusicMenu
        app = make_app()
        ready_library(app)
        menu = LocalMusicMenu(app)
        app.push(menu)
        for i in (1, 2, 3, 4, 5):
            menu.selected = i
            press(app, A.SELECT)
            render_ok(app)
            if app.screen is not menu:      # Beğenilenler boşken sadece bildirim çıkar
                app.pop()

    def test_arama(self):
        from soleil.screens.player import PlayerScreen
        from soleil.screens.playlist import PlaylistScreen
        from soleil.screens.search import LETTERS, SearchScreen, normalize, search_library
        app = make_app()
        lib = ready_library(app)
        # Türkçe harfe ve büyük/küçüğe duyarsız; parça adı ve sanatçıdan bulunur
        self.assertEqual(normalize("Amber IŞIK İz"), "amber isik iz")
        hits = search_library(lib, "isik")
        self.assertIn("Amber Işık", [r.track.title for r in hits if r.kind == "Parça"])
        self.assertEqual(search_library(lib, "   "), [])
        kinds = [r.kind for r in search_library(lib, "amber")]
        self.assertEqual(kinds, sorted(kinds, key=["Sanatçı", "Albüm", "Parça"].index))

        screen = SearchScreen(app)
        app.push(screen)
        for ch in "AMBER":                 # kadranı harfe çevirip tıklar
            screen.dial.jump(LETTERS.index(ch))
            press(app, A.SELECT)
        press(app, A.LEFT1)
        screen.dial.jump(LETTERS.index("R"))
        press(app, A.SELECT)
        self.assertEqual(screen.query, "Amber")      # kelime başı büyük, gerisi küçük
        render_ok(app)
        self.assertTrue(screen.results)
        press(app, A.TOP2)                           # sonuçlara geç
        self.assertTrue(screen.in_results)
        render_ok(app)
        album = next(i for i, r in enumerate(screen.results) if r.kind == "Albüm")
        screen.selected = album
        press(app, A.SELECT)
        self.assertIsInstance(app.screen, PlaylistScreen)
        app.pop()
        track = next(i for i, r in enumerate(screen.results) if r.kind == "Parça")
        screen.selected = track
        press(app, A.SELECT)
        self.assertIsInstance(app.screen, PlayerScreen)
        self.assertEqual(app.playback.current, screen.results[track].track)
        app.pop()
        press(app, A.BACK)                           # sonuçlardan yazmaya döner
        self.assertFalse(screen.in_results)
        self.assertIs(app.screen, screen)


@unittest.skipUnless(make_app(menu=False).audio, "mpv (libmpv) yok")
class GercekCalma(unittest.TestCase):
    def test_cal_duraklat_sar_sonraki(self):
        app = make_app()
        lib = ready_library(app)
        p = app.playback
        album = next(a for a in lib.albums if a.name == "Amber Kasetler")
        p.play_queue(list(album.tracks), 0)
        self.assertTrue(wait(lambda: p.position > 0.5, app=app))
        p.toggle()                                               # duraklat
        pos = p.position
        tick(app, 0.5, real=True)
        self.assertAlmostEqual(p.position, pos, delta=0.1)
        p.toggle()
        p.seek(p.current.duration - 1.0)
        self.assertTrue(wait(lambda: p.index == 1, timeout=8, app=app), "sıradaki şarkıya geçmedi")
        p.next()
        self.assertEqual(p.current.title, "Amber Işık")
        self.assertTrue(wait(lambda: p.position > 0.3, app=app))
        p.stop()

    def test_bosluksuz_gecis(self):
        """Şarkı bitince mpv önceden verilen sıradakine kendisi geçmeli:
        dosya yeniden yüklenmez, araya sessizlik girmez."""
        app = make_app()
        lib = ready_library(app)
        p, eng = app.playback, app.audio
        album = next(a for a in lib.albums if a.name == "Amber Kasetler")
        loads = []
        orig = eng.load
        eng.load = lambda *a, **k: (loads.append(a[0]), orig(*a, **k))[1]
        p.play_queue(list(album.tracks), 0)
        self.assertEqual(eng.prefetched, album.tracks[1].path)
        self.assertTrue(wait(lambda: p.position > 0.3, app=app))
        p.seek(p.current.duration - 0.8)
        self.assertTrue(wait(lambda: p.index == 1, timeout=8, app=app))
        self.assertEqual(len(loads), 1, "sıradaki şarkı yeniden yüklendi (boşluklu)")
        self.assertEqual(eng.loaded, album.tracks[1].path)
        self.assertEqual(eng.prefetched, album.tracks[2].path)
        self.assertTrue(wait(lambda: p.position > 0.3, app=app))
        # Tekrar "tek şarkı" olunca sıradaki aynı şarkı olur
        p.repeat = "one"
        app.tick(1 / 30)
        self.assertEqual(eng.prefetched, album.tracks[1].path)
        p.stop()


class Begeniler(unittest.TestCase):
    def test_kaydedilir_ve_geri_okunur(self):
        from soleil.likes import Likes
        app = make_app()
        lib = ready_library(app)
        likes = Likes(save=True)                     # test klasörüne yazar
        track = lib.tracks[0]
        self.assertTrue(likes.toggle(track))
        self.assertTrue(Likes(save=True).has(track))  # dosyadan geri okundu
        self.assertFalse(likes.toggle(track))
        self.assertFalse(Likes(save=True).has(track))


if __name__ == "__main__":
    unittest.main()
