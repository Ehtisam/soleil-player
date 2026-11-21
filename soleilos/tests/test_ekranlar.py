"""Bütün ekranlar açılıp çizilebiliyor mu, temel akışlar çalışıyor mu."""

from __future__ import annotations

import time
import unittest

import numpy as np

from soleil import config
from soleil.input import Action as A
from soleil.theme import THEMES

from .yardim import make_app, open_section, press, render_ok, tick

SECTIONS = ["MÜZİK", "MEDYA", "OYUNLAR", "E-KİTAP", "NOT DEFTERİ", "SİSTEM AYARLARI", "SES KAYDEDİCİ", "ARAÇLAR"]


def walk_list(test, app, depth=0, max_depth=3):
    """Liste ekranında her satırı açıp çizer, geri döner (ağaç gibi gezer)."""
    from soleil.ui.listview import BACK, ListScreen
    screen = app.screen
    if not isinstance(screen, ListScreen) or depth > max_depth:
        return
    for i, row in enumerate(screen.rows):
        if row is BACK or row.act is not None or row.open is None:
            continue
        screen.selected = i
        before = len(app.stack)
        press(app, A.SELECT)
        render_ok(app)
        if len(app.stack) > before:
            walk_list(test, app, depth + 1, max_depth)
            while len(app.stack) > before:
                app.pop()
        render_ok(app)


class Ekranlar(unittest.TestCase):
    def test_her_bolum_ve_alt_menuler_cizilir(self):
        app = make_app()
        for theme in THEMES:
            app.set_theme(theme)
            render_ok(app)
        app.set_theme("amber")
        for i, name in enumerate(SECTIONS):
            with self.subTest(bolum=name):
                open_section(app, i)
                render_ok(app)
                walk_list(self, app)

    def test_acilis_sekansi(self):
        from soleil.screens.boot import BootScreen
        from soleil.screens.main_menu import MainMenu
        app = make_app(menu=False)
        app.push(BootScreen(app, lambda: MainMenu(app)))
        for _ in range(8):
            tick(app, 1.0)
            render_ok(app)
        self.assertIsInstance(app.screen, MainMenu)

    def test_acilis_her_karesi_cizilir(self):
        from soleil.screens.boot import BootScreen
        app = make_app(menu=False)
        boot = BootScreen(app, lambda: None)
        app.push(boot)
        self.assertIsNotNone(boot.poem_font)
        k = 0.0
        while k < boot.end:
            boot.t = k
            render_ok(app)
            k += 0.05

    def test_acilis_suresi_ve_kutuphane_beklemesi(self):
        import time
        from soleil.screens.boot import BootScreen
        from soleil.screens.main_menu import MainMenu
        # Tarama hemen biterse ~4.5 sn
        app = make_app(menu=False)
        boot = BootScreen(app, lambda: MainMenu(app))
        app.push(boot)
        deadline = time.time() + 10
        while app.library.state != "ready" and time.time() < deadline:
            time.sleep(0.01)
        tick(app, 4.4)
        self.assertIs(app.screen, boot)
        tick(app, 0.3)
        self.assertIsInstance(app.screen, MainMenu)

        # Tarama sürerken çubuk taramanın önüne geçmez, bitince devam eder
        app = make_app(menu=False)
        app.library.state, app.library.progress = "scanning", 0.4
        boot = BootScreen(app, lambda: MainMenu(app))
        app.push(boot)
        tick(app, boot.poem_end + 1.0)
        self.assertAlmostEqual(boot.bar_frac(), 0.4)
        self.assertIs(app.screen, boot)
        app.library.state = "ready"
        tick(app, 2.0)
        self.assertIsInstance(app.screen, MainMenu)

        # Tarama hiç bitmezse BAR_WAIT kadar bekleyip açılır
        app = make_app(menu=False)
        app.library.state = "scanning"
        boot = BootScreen(app, lambda: MainMenu(app))
        app.push(boot)
        tick(app, 8.0)
        self.assertIsInstance(app.screen, MainMenu)

    def test_acilis_siir_fontunda_butun_harfler_var(self):
        from soleil.screens.boot import POEM, BootScreen
        import pygame
        boot = BootScreen(make_app(menu=False), lambda: None)
        # Fontta olmayan harf "kutu" (notdef) olarak çizilir; "你" fontta yok
        def pixels(ch):
            return pygame.image.tobytes(boot.poem_font.render(ch, False, (255, 255, 255)), "RGB")
        box = pixels("你")
        for ch in "".join(POEM):
            self.assertNotEqual(pixels(ch), box, ch)

    def test_acilis_pil_satiri(self):
        from soleil.app import Status
        from soleil.screens.boot import battery_line
        self.assertEqual(battery_line(Status(battery=84)), "PİL: %84")
        self.assertEqual(battery_line(Status(battery=84, voltage=3.917, charging=True)),
                         "PİL: %84 [3.92V] [ŞARJDA]")

    def test_sistem_bilgisi_gruplar_ve_kaydirma(self):
        from dataclasses import replace
        from soleil.app import Status
        from soleil.hw.system import parse_iw_link
        from soleil.screens.sysinfo import SystemInfo, battery_value
        app = make_app()
        app.system.wifi_link = lambda: ("Ev_Agi_5G", -58)
        bt = app.bluetooth
        bt._set(replace(bt.paired[0], connected=True))
        screen = SystemInfo(app)
        app.push(screen)
        groups = [line[1] for line in screen.lines if line[0] == "group"]
        self.assertEqual(groups, ["Donanım & Güç", "Ağ & Bağlantı", "Sistem & Depolama"])
        values = {line[1]: line[2] for line in screen.lines if line[0] == "item"}
        self.assertEqual(values["Wi-Fi"], "Ev_Agi_5G [-58 dBm]")
        self.assertEqual(values["Bluetooth"], bt.paired[0].name)
        # Kaydırma: sona kadar iner, daha ileri gitmez; tıklama geri çıkar
        render_ok(app)
        for _ in range(30):
            press(app, A.DOWN)
            render_ok(app)
        self.assertGreater(screen.top, 0)
        self.assertEqual(screen.top, screen._max_top())
        press(app, A.SELECT)
        self.assertIsNot(app.screen, screen)
        # Kapalıyken ve değer biçimleri
        app.status.wifi = app.status.bluetooth = False
        screen._collect()
        values = {line[1]: line[2] for line in screen.lines if line[0] == "item"}
        self.assertEqual((values["Wi-Fi"], values["Bluetooth"]), ("KAPALI", "KAPALI"))
        self.assertEqual(battery_value(Status(battery=84)), "%84")
        self.assertEqual(battery_value(Status(battery=84, voltage=3.92, charging=True)),
                         "3.92V [%84] [ŞARJDA]")
        sample = ("Connected to aa:bb (on wlan0)\n\tSSID: Ev Agi\n"
                  "\tfreq: 5180\n\tsignal: -58 dBm\n")
        self.assertEqual(parse_iw_link(sample), ("Ev Agi", -58))
        self.assertIsNone(parse_iw_link("Not connected.\n"))

    def test_takvim(self):
        import datetime as dt
        from soleil import seb
        from soleil.screens.calendar import GregorianCalendar, SebCalendar
        from soleil.screens.tools import tools_menu
        app = make_app()
        menu = tools_menu(app)
        app.push(menu)
        menu.selected = next(i for i, r in enumerate(menu.rows) if r.label == "Takvim")
        press(app, A.SELECT)
        cal = app.screen
        self.assertIsInstance(cal, SebCalendar)
        self.assertEqual(cal.selected, seb.night_date(dt.datetime.now()))
        render_ok(app)
        # Sayfalar: Papatya'dan sonra İkiz Geceler, Karanfil'den sonra Yelda, sonra yeni yıl
        cal.selected = dt.date(2026, 5, 10)                      # 19 Papatya
        press(app, A.LEFT2)
        self.assertEqual(cal.selected, dt.date(2026, 6, 21))     # Alaca
        render_ok(app)
        press(app, A.LEFT2)
        self.assertEqual(seb.from_date(cal.selected).short(), "1 ZA 0")
        cal.selected = dt.date(2026, 11, 1)                      # 12 Karanfil
        press(app, A.LEFT2, A.LEFT2)
        self.assertEqual(seb.from_date(cal.selected).short(), "1 AS 1")
        press(app, A.LEFT1)
        self.assertEqual(cal.selected, dt.date(2026, 12, 20))    # Yelda Arifesi
        render_ok(app)
        press(app, A.DOWN)
        self.assertEqual(seb.from_date(cal.selected).special, "Yelda")
        cal.selected = dt.date(2028, 2, 29)                      # Konuk Gece
        render_ok(app)
        # Miladi takvime geç: aynı tarih, ay ay gezinme
        press(app, A.TOP2)
        greg = app.screen
        self.assertIsInstance(greg, GregorianCalendar)
        self.assertEqual(greg.selected, dt.date(2028, 2, 29))
        render_ok(app)
        press(app, A.LEFT2)
        self.assertEqual(greg.selected, dt.date(2028, 3, 29))
        greg.selected = dt.date(2026, 1, 31)
        press(app, A.LEFT2)
        self.assertEqual(greg.selected, dt.date(2026, 2, 28))   # ayın son günü
        press(app, A.SELECT)
        self.assertEqual(greg.selected, dt.date.today())
        render_ok(app)
        app.pop()
        press(app, A.SELECT)                                     # son açılan takvim hatırlanır
        self.assertIsInstance(app.screen, GregorianCalendar)

    def test_ekran_uykusu_ilk_tus_sadece_uyandirir(self):
        app = make_app()
        app.settings.sleep_after = 15
        tick(app, 16)
        self.assertTrue(app.sleeping)
        selected = app.screen.selected
        press(app, A.DOWN)
        self.assertFalse(app.sleeping)
        self.assertEqual(app.screen.selected, selected)


class Pil(unittest.TestCase):
    def test_uyari_yanip_sonme_ve_kapanma(self):
        from soleil.app import WARNING_RED
        app = make_app()
        app.status.battery = 25
        tick(app, 0.1)
        self.assertIsNone(app.toast_info)
        app.status.battery = 19
        tick(app, 0.1)
        self.assertEqual((app.toast_info.title, app.toast_info.detail), ("PİL AZ", "%19"))
        self.assertEqual(app.leds.flash_color, WARNING_RED)
        app.toast_info = None
        tick(app, 0.1)
        self.assertIsNone(app.toast_info)              # aynı eşikte bir kez
        app.status.battery = 9
        tick(app, 0.1)
        self.assertTrue(app.battery_low)
        render_ok(app)
        app.status.charging = True                     # şarja takılınca uyarılar sıfırlanır
        tick(app, 0.1)
        self.assertFalse(app.battery_low)
        app.status.charging = False
        app.status.battery = 2
        app.running = True
        tick(app, 9)
        self.assertTrue(app.power_off)                 # kendini kapattı
        self.assertFalse(app.running)


class Bluetooth(unittest.TestCase):
    def test_ara_eslestir_baglan_unut(self):
        from soleil.screens.bluetooth import BluetoothMenu, DeviceScreen, ScanScreen
        app = make_app()
        bt = app.bluetooth
        app.push(BluetoothMenu(app))
        tick(app, 0.1)
        labels = [r.label for r in app.screen.rows[1:]]
        self.assertEqual(labels, ["Yeni Cihaz Ara", "Kablosuz Kulaklık"])
        # Kayıtlı kulaklığa bağlan
        app.screen.selected = 2
        press(app, A.SELECT)
        self.assertIsInstance(app.screen, DeviceScreen)
        press(app, A.SELECT)                                   # Bağlan
        tick(app, 2)
        self.assertEqual(app.toast_info.title, "BAĞLANDI")
        self.assertEqual(bt.connected_audio.name, "Kablosuz Kulaklık")
        render_ok(app)
        press(app, A.BACK)
        # Ara: cihazlar geldikçe listeye eklenir, hoparlörü eşleştir
        app.screen.selected = 1
        press(app, A.SELECT)
        self.assertIsInstance(app.screen, ScanScreen)
        tick(app, 7)
        names = [r.label for r in app.screen.rows[1:]]
        self.assertIn("Soleil Hoparlör", names)
        render_ok(app)
        app.screen.selected = names.index("Soleil Hoparlör") + 1
        press(app, A.SELECT)
        tick(app, 3)
        self.assertEqual(bt.connected_audio.name, "Soleil Hoparlör")   # ses tek cihaza gider
        self.assertFalse(bt.devices["AA:00:00:00:00:01"].connected)
        # Hoparlörü unut (iki basış)
        press(app, A.BACK)
        tick(app, 0.1)
        row = [r.label for r in app.screen.rows].index("Soleil Hoparlör")
        app.screen.selected = row
        press(app, A.SELECT)
        app.screen.selected = 2                                # Cihazı Unut
        press(app, A.SELECT, A.SELECT)
        self.assertNotIn("AA:00:00:00:00:02", bt.devices)
        # Bluetooth kapalıyken tek satır
        app.settings.bluetooth = False
        tick(app, 0.1)
        self.assertEqual(app.screen.rows[1].label, "Bluetooth Kapalı")


class Okuyucu(unittest.TestCase):
    def test_kitap_bolumler_ve_yazi_boyutu(self):
        from soleil.screens.reader import ReaderScreen, ReaderMenu
        app = make_app()
        open_section(app, 3)                                   # E-KİTAP
        press(app, A.SELECT)
        reader = app.screen
        self.assertIsInstance(reader, ReaderScreen)
        for _ in range(10):
            press(app, A.DOWN)
        offset = reader.top_offset()
        press(app, A.TOP2)                                     # yazı boyutu
        self.assertEqual(reader.top_offset(), offset)          # aynı yerde kaldı
        press(app, A.HOLD)
        self.assertIsInstance(app.screen, ReaderMenu)
        render_ok(app)
        press(app, A.BACK)
        reader.jump_to(0)
        press(app, A.UP)
        self.assertTrue(reader.on_back)


class NotDefteri(unittest.TestCase):
    def type_text(self, app, text):
        from soleil.screens import notebook as nb
        ed = app.screen
        for ch in text:
            if ch == " ":
                press(app, A.LEFT2)
                continue
            want = 0 if ch in nb.LOWER else (1 if ch in nb.UPPER else (2 if ch.isdigit() else 3))
            target = ch
            if ch in nb.UPPER and ed.set_index == 0 and ed._auto_capital():
                want, target = 0, nb.LOWER[nb.UPPER.index(ch)]
            while ed.set_index != want:
                press(app, A.TOP2)
            strip = ed.strip
            n = len(strip)
            d = (strip.index(target) - ed.dial.index(n)) % n
            if d > n // 2:
                d -= n
            for _ in range(abs(d)):
                press(app, A.DOWN if d > 0 else A.UP)
            press(app, A.SELECT)

    def test_yaz_kaydet_adlandir_sil(self):
        from soleil.screens import notebook as nb
        app = make_app()
        open_section(app, 4)
        press(app, A.SELECT)                                   # Yeni Not
        self.type_text(app, "Merhaba. dünya 42")
        ed = app.screen
        self.assertEqual(ed.text, "Merhaba. Dünya 42")         # cümle başı büyük
        render_ok(app)
        press(app, A.BACK)
        files = list(nb.NOTES.glob("*.txt"))
        self.assertEqual([f.read_text(encoding="utf-8") for f in files], ["Merhaba. Dünya 42"])
        # Aç, sil (iki adım)
        app.screen.selected = 2
        press(app, A.SELECT, A.HOLD)
        app.screen.selected = 3                                # NOTU SİL
        press(app, A.SELECT, A.SELECT)
        self.assertEqual(list(nb.NOTES.glob("*.txt")), [])


class Araclar(unittest.TestCase):
    def test_hesap_makinesi_kadranla(self):
        from soleil.screens import tools
        app = make_app()
        app.push(tools.CalculatorScreen(app))
        calc = app.screen
        for key in "7×6":
            n = len(tools.KEYS)
            d = (tools.KEYS.index(key) - calc.dial.index(n)) % n
            for _ in range(d):
                press(app, A.DOWN)
            press(app, A.SELECT)
        press(app, A.LEFT2)
        self.assertEqual(calc.result, "42")
        render_ok(app)

    def test_zamanlayici_bitince_bildirim(self):
        app = make_app()
        app.timer.adjust(-4)
        app.timer.toggle()
        tick(app, 31)
        self.assertEqual(app.toast_info.title, "SÜRE DOLDU")

    def test_fener_parlakligi_geri_verir(self):
        from soleil.screens import tools
        app = make_app()
        app.settings.brightness = 40
        app.push(tools.FlashlightScreen(app))
        self.assertEqual(app.settings.brightness, 100)
        press(app, A.BACK)
        self.assertEqual(app.settings.brightness, 40)


class Oyunlar(unittest.TestCase):
    def test_tugla_kirma_ve_yilan(self):
        from soleil.screens.games import Breakout, Snake
        for game in (Breakout, Snake):
            with self.subTest(oyun=game.name):
                app = make_app()
                app.push(game(app))
                g = app.screen
                press(app, A.SELECT)
                self.assertEqual(g.state, "playing")
                tick(app, 1)
                render_ok(app)
                press(app, A.BACK)
                self.assertEqual(g.state, "paused")
                press(app, A.SELECT)
                # Oynamadan bekle: yılan duvara çarpar, tuğlada top düşer
                # (can gidince top rakette bekler, tık yeniden atar)
                for _ in range(60):
                    tick(app, 2)
                    if g.state == "over":
                        break
                    if getattr(g, "stuck", False):
                        press(app, A.SELECT)
                self.assertEqual(g.state, "over")
                render_ok(app)


class SesKaydedici(unittest.TestCase):
    def test_sahte_sesle_kayit(self):
        from soleil import recorder as R
        from soleil.screens.recorder import RecorderScreen, recorder_of
        app = make_app()
        rec = recorder_of(app)

        def fake_start():
            rec.blocks, rec.frames = [], 0
            rec.state = "recording"
            return True
        rec.start = fake_start                                 # gerçek mikrofon açılmaz
        app.push(RecorderScreen(app))
        press(app, A.SELECT)
        block = (np.sin(np.arange(R.BLOCK) / 5) * 8000).astype(np.int16)
        for _ in range(int(2 * R.RATE / R.BLOCK)):
            rec.feed(block)
        press(app, A.SELECT)                                   # duraklat: kayda girmez
        rec.feed(block)
        self.assertAlmostEqual(rec.elapsed, 2.0, delta=0.05)
        render_ok(app)
        press(app, A.LEFT2)                                    # bitir
        rec.wait_encoded()
        files = list((config.MEDIA / "ses").iterdir())
        self.assertEqual(len(files), 1)
        self.assertIn(files[0].suffix, (".ogg", ".wav"))


if __name__ == "__main__":
    unittest.main()
