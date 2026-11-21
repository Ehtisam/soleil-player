"""Ekransız mantık: hesap makinesi, zamanlayıcılar, metin, dosyalar,
donanım katmanı (framebuffer, tuşlar, ışıklar), radyo kaydı ayrıştırma."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pygame

from soleil import calc, timers
from soleil.documents import ReadingLog, format_size, parse
from soleil.input import HOLD_TIME, Action

from .yardim import make_app, press


class HesapMakinesi(unittest.TestCase):
    def sonuc(self, expr):
        return calc.format_number(calc.evaluate(expr))

    def test_islem_onceligi_ve_parantez(self):
        self.assertEqual(self.sonuc("1+2×3"), "7")
        self.assertEqual(self.sonuc("(1+2)×3"), "9")
        self.assertEqual(self.sonuc("12+3×(4-1"), "21")      # kapanmamış parantez
        self.assertEqual(self.sonuc("-5+2"), "-3")
        self.assertEqual(self.sonuc("10÷4"), "2.5")
        self.assertEqual(self.sonuc("0.1+0.2"), "0.3")

    def test_hatalar(self):
        for expr in ("5÷0", "3+", "", "1.5.2", "7-"):
            with self.assertRaises(calc.CalcError, msg=expr):
                calc.evaluate(expr)
        self.assertEqual(calc.preview("3+"), "")

    def test_buyuk_sayilar_sigar(self):
        text = self.sonuc("99999999×99999999")
        self.assertLessEqual(len(text), 14)


class Zamanlayicilar(unittest.TestCase):
    def test_saat_yazisi(self):
        self.assertEqual(timers.clock_text(65), "01:05")
        self.assertEqual(timers.clock_text(3723), "1:02:03")
        self.assertEqual(timers.clock_text(65.37, cs=True), "01:05.37")

    def test_kronometre_turlar(self):
        sw = timers.Stopwatch()
        sw.toggle()
        sw.update(10)
        sw.lap()
        sw.update(5)
        sw.lap()
        self.assertEqual(sw.laps, [10, 15])
        sw.toggle()
        sw.update(100)                       # durmuşken ilerlemez
        self.assertEqual(sw.elapsed, 15)
        sw.reset()
        self.assertEqual((sw.elapsed, sw.laps), (0, []))

    def test_geri_sayim(self):
        t = timers.CountdownTimer()
        t.adjust(-4)                         # 300 sn -> 30 sn (en kısa)
        self.assertEqual(t.duration, 30)
        t.toggle()
        self.assertFalse(t.update(29))
        self.assertTrue(t.update(2))         # bitti
        self.assertEqual(t.remaining, 0)
        t.adjust(1)                          # bitmişken süre değişmez (başlamış sayılır)
        t.reset()
        t.adjust(1)
        self.assertEqual(t.duration, 60)


class Metin(unittest.TestCase):
    def test_bloklar(self):
        blocks = parse("# Bölüm\nbir\niki\n\n\nüç\n\n")
        self.assertEqual([b.kind for b in blocks], ["heading", "line", "line", "gap", "line"])
        self.assertEqual(blocks[0].text, "Bölüm")
        self.assertEqual(blocks[4].offset, len("# Bölüm\nbir\niki\n\n\n"))

    def test_satir_bolme(self):
        app = make_app(menu=False)
        rows = app.text.wrap("bir iki üç dört beş altı yedi sekiz", "track", 7.56 * 12)
        self.assertTrue(all(len(r) <= 12 for r in rows))
        self.assertEqual(" ".join(rows).split(), "bir iki üç dört beş altı yedi sekiz".split())
        long = app.text.wrap("x" * 30, "track", 7.56 * 12)
        self.assertEqual("".join(long), "x" * 30)

    def test_boyut_yazisi(self):
        self.assertEqual(format_size(500), "500B")
        self.assertEqual(format_size(2048), "2KB")
        self.assertEqual(format_size(5 * 1024 * 1024), "5MB")

    def test_okuma_kaydi_kapaliyken_yazmaz(self):
        log = ReadingLog.load(enabled=False)
        log.save()                           # hata vermemeli, dosya oluşmamalı


class Framebuffer(unittest.TestCase):
    """Pi'deki SPI ekran çıkışı: dosyaya yazılan görüntü geri okunabilmeli,
    değişmeyen kare yazılmamalı, imleç inince sadece o satırlar yazılmalı."""

    def _display(self, fb_size):
        from soleil.hw.framebuffer import FramebufferDisplay
        path = Path(tempfile.mkdtemp()) / "fb"
        path.write_bytes(b"\0" * fb_size[0] * fb_size[1] * 2)
        return FramebufferDisplay((320, 480), device=path, fb_size=fb_size, stride=fb_size[0] * 2), path

    def _read(self, path, fb_size, rotate):
        raw = np.frombuffer(path.read_bytes(), dtype=np.uint16).reshape(fb_size[1], fb_size[0])
        return np.rot90(raw, 1) if rotate else raw

    def test_geri_okuma_ve_kismi_yazma(self):
        from soleil.hw.framebuffer import to_rgb565
        app = make_app()
        for fb_size in ((320, 480), (480, 320)):
            d, path = self._display(fb_size)
            canvas = app.render()
            d.present(canvas)
            d.file.flush() if hasattr(d.file, "flush") else None
            expected = to_rgb565(canvas)
            self.assertTrue(np.array_equal(self._read(path, fb_size, d.rotate), expected))
            # Aynı kare: hiçbir şey yazılmaz
            written = []
            orig = d.file.write
            d.file.write = lambda b: (written.append(len(b)), orig(b))[1]
            d.present(canvas)
            self.assertEqual(written, [])
            # İmleç bir satır iner: dikey ekranda tam kareden çok az
            press(app, Action.DOWN)
            d.present(app.render())
            if not d.rotate:
                self.assertLess(sum(written), 320 * 480 * 2 / 3)
            press(app, Action.UP)
            d.file.close()

    def test_parlaklik_karartir(self):
        from soleil.hw.framebuffer import to_rgb565
        s = pygame.Surface((4, 4))
        s.fill((200, 200, 200))
        self.assertLess(int(to_rgb565(s, 0.5)[0, 0]), int(to_rgb565(s, 1.0)[0, 0]))


class GpioTuslar(unittest.TestCase):
    def test_tik_uzun_basma_ve_tuslar(self):
        from soleil.hw.gpio_input import GpioInput
        g = GpioInput(use_gpio=False)
        g.rotate(Action.DOWN)
        g.rotate(Action.UP)
        self.assertEqual(g.poll(), [Action.DOWN, Action.UP])
        g.press(Action.SELECT)
        g.release(Action.SELECT)
        self.assertEqual(g.poll(), [Action.SELECT])
        g.press(Action.SELECT)
        start = g.events.queue[-1][2]
        self.assertEqual(g.poll(start + HOLD_TIME / 2), [])
        self.assertEqual(g.poll(start + HOLD_TIME + 0.01), [Action.HOLD])
        g.release(Action.SELECT)
        self.assertEqual(g.poll(start + 1), [])          # uzun basmadan sonra tık gelmez
        g.press(Action.LEFT1)
        g.press(Action.BACK)
        self.assertEqual(g.poll(), [Action.LEFT1, Action.BACK])


class IsikCubuklari(unittest.TestCase):
    def test_modlar(self):
        from soleil.hw.leds import OFF, LedEffects
        from soleil import sample_data
        app = make_app()
        fx = LedEffects(6)
        app.settings.led_mode = "KAPALI"
        fx.update(app, 0.1)
        self.assertTrue(all(c == OFF for c in fx.left + fx.right))

        app.settings.led_mode = "SES"
        app.status.volume = 50
        fx.update(app, 0.1)
        lit = sum(1 for c in fx.left if c == app.theme.fg)
        self.assertEqual(lit, 3)                         # 6 LED'in yarısı
        self.assertEqual(fx.left, fx.right)

        app.settings.led_mode = "İLERLEME"
        app.playback.play_queue(list(sample_data.A_KING.tracks), 0)
        app.playback.seek(app.playback.current.duration * 0.25)
        fx.update(app, 0.1)
        self.assertEqual(fx.right, [OFF] * 6)            # ilk çeyrek: sağ çubuk sönük
        self.assertEqual(fx.left[-1], app.theme.fg)      # sol çubuğun dış ucu dolu

        app.sleeping = True
        fx.update(app, 0.1)
        self.assertFalse(fx.active)

    def test_zamanlayici_yanip_soner(self):
        from soleil.hw.leds import LedEffects
        app = make_app()
        fx = LedEffects(6)
        fx.flash(app.time)
        fx.update(app, 0.01)
        self.assertTrue(fx.active)


class Radyo(unittest.TestCase):
    def test_istasyon_kaydi(self):
        from soleil.radio import station_track
        t = station_track({"name": "Deneme FM 🎵", "url_resolved": "http://x/y", "tags": "pop,rock,jazz",
                           "countrycode": "TR", "codec": "MP3", "bitrate": 128, "stationuuid": "abc"})
        self.assertEqual(t.title, "Deneme FM")           # emoji atıldı
        self.assertTrue(t.live)
        self.assertEqual(t.quality, "MP3 128K")
        self.assertEqual(t.album, "TR · pop · rock")
        self.assertIsNone(station_track({"name": "adressiz"}))
        unknown = station_track({"name": "X", "url": "http://z", "codec": "UNKNOWN"})
        self.assertEqual(unknown.quality, "YAYIN")



DEMO_DIL = {
    "ad": "DENEME",
    "alfabe": {
        "ilk": ["g", "n", "r", "m", "s", "ch", "k", "t"],
        "orta": ["a", "ae", "o", "u", "i"],
        "son": ["k", "n", "l", "m", "ng"],
        "yer": {"a": "sag", "ae": "sag", "i": "sag", "o": "alt", "u": "alt"},
    },
}
DEMO_TABLO = """| Türkçe | Okunuş |
|---|---|
| Sistem Ayarları | simsa narae |
| {n} şarkı | {n} norae |
| Müzik | ummak |
| AÇIK | kin |
| Eski Yazı | |
"""


class Dil(unittest.TestCase):
    """İkinci dil: çeviri tablosu, hece blokları, yazı çizimi, tablo aracı."""

    def setUp(self):
        import json
        from soleil import lang
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "deneme"
        self.folder.mkdir()
        (self.folder / "dil.json").write_text(json.dumps(DEMO_DIL), encoding="utf-8")
        (self.folder / "ceviri.md").write_text(DEMO_TABLO, encoding="utf-8")
        self.lang = lang

    def tearDown(self):
        self.lang.set_language("tr")
        self.tmp.cleanup()

    def test_hece_bloklari(self):
        from soleil import script
        sc = script.load(self.folder)
        self.assertEqual(len(sc.encode("narae")), 2)                    # na-rae
        self.assertEqual(sc.decode(sc.encode("narae")[1]), ("r", "ae", ""))
        self.assertEqual([sc.decode(c) for c in sc.encode("kimchi")], [("k", "i", "m"), ("ch", "i", "")])
        self.assertEqual(sc.romanize(sc.encode("simsa narae")), "simsa narae")
        # Tanınmayan harf, rakam ve {yer tutucu} olduğu gibi kalır
        out = sc.encode("{n} norae 7!")
        self.assertTrue(out.startswith("{n} "))
        self.assertTrue(out.endswith(" 7!"))
        self.assertTrue(all(script.is_block(c) for c in out[4:6]))

    def test_solainwen_heceleri(self):
        from soleil import script
        from soleil.lang import FOLDER
        sc = script.load(FOLDER / "solainwen")
        self.assertIsNotNone(sc)

        def syl(word):
            return [(sc.decode(c), sc.kind(c)) if script.is_block(c) else c for c in sc.encode(word)]

        self.assertEqual(syl("maison"), [(("m", "ai", ""), "standart"), (("s", "o", "n"), "standart+son")])
        self.assertEqual(syl("sento"), [(("s", "e", "n"), "standart+son"), (("t", "o", ""), "standart")])
        self.assertEqual(syl("beau"), [(("b", "eau", ""), "standart")])          # kombin ünlü tek işaret
        self.assertEqual(syl("guer"), [(("g", "ue", "r"), "standart+son")])
        self.assertEqual(syl("ego"), [(("", "e", ""), "unlu"), (("g", "o", ""), "standart")])
        self.assertEqual(syl("teg"), [(("t", "eg", ""), "standart")])           # özel ünlü EG
        self.assertEqual(syl("tegs"), [(("t", "eg", "s"), "standart+son")])
        self.assertEqual(syl("il"), [(("", "i", "l"), "unlu+unsuz")])
        self.assertEqual(syl("ag"), [(("", "a", "g"), "unlu+unsuz")])           # normal ünsüz, ünlü solda
        self.assertEqual(syl("dog"), [(("d", "o", ""), "standart"), "g"])       # G hece sonuna gelmez
        self.assertEqual(syl("strada"), [(("str", "a", ""), "standart"), (("d", "a", ""), "standart")])
        self.assertEqual(syl("sent"), [(("s", "e", "nt"), "standart+son")])     # hece sonu kümesi
        self.assertEqual(syl("Ünda"), [(("", "ü", "n"), "unlu+unsuz"), (("d", "a", ""), "standart")])
        self.assertEqual(sc.romanize(sc.encode("Ego om cra va a maison kun tu.")),
                         "ego om cra va a maison kun tu.")
        self.assertEqual(sc.encode("w")[0], "w")                                 # alfabede W yok
        surf = pygame.Surface((40, 40))
        for ch in sc.encode("maison ego il sent"):
            if script.is_block(ch):
                surf.blit(sc.render(ch, (22, 20), (255, 200, 100), Path(__file__).resolve().parent.parent
                                    / "assets" / "fonts" / "ShareTechMono-Regular.ttf"), (0, 0))

    def test_ceviri(self):
        from soleil.lang import _, tr
        self.assertEqual(tr("Sistem Ayarları"), "Sistem Ayarları")      # Türkçede değişmez
        self.lang.set_language("deneme", self.folder)
        block = tr("Sistem Ayarları")
        self.assertEqual(self.lang.current().script.romanize(block), "simsa narae")
        self.assertEqual(tr("SİSTEM AYARLARI"), block)                    # büyük/küçük fark etmez
        self.assertEqual(tr("Sols / Müzik"), "Sols / " + tr("Müzik"))     # başlık yolu
        self.assertEqual(tr("[AÇIK]"), "[" + tr("AÇIK") + "]")             # köşeli parantez
        self.assertEqual(tr("Eski Yazı"), "Eski Yazı")                    # boş satır: Türkçe
        self.assertEqual(tr("Bilinmeyen"), "Bilinmeyen")
        three = _("{n} şarkı").format(n=3)
        self.assertTrue(three.startswith("3 "))
        self.assertEqual(self.lang.current().script.romanize(three), "3 norae")

    def test_alfabesiz_dil_okunusu_yazar(self):
        import json
        data = dict(DEMO_DIL)
        data.pop("alfabe")
        (self.folder / "dil.json").write_text(json.dumps(data), encoding="utf-8")
        self.lang.set_language("deneme", self.folder)
        self.assertEqual(self.lang.tr("Sistem Ayarları"), "simsa narae")
        self.assertEqual(self.lang.tr("AÇIK"), "KIN")                    # Türkçe büyük harfse büyük

    def test_yazi_olcme_ve_cizim(self):
        from soleil.screens.settings_screen import SettingsScreen
        from soleil.screens.sysinfo import SystemInfo
        from soleil.text import Text
        from .yardim import render_ok
        app = make_app()
        self.lang.set_language("deneme", self.folder)
        text = Text()
        block = self.lang.tr("Müzik")                                     # um-mak: 2 blok
        self.assertEqual(text.width("Müzik", "body"), round(4 * text.pitch("body")))
        cut = text.fit("Sistem Ayarları", "body", text.pitch("body") * 5)
        self.assertTrue(cut.endswith(".."))
        self.assertEqual(text.cells(cut), 4)                              # 1 blok + ".."
        surf = pygame.Surface((320, 40))
        r = text.draw(surf, "Müzik", "body", (255, 200, 100), (0, 0))
        self.assertEqual(r.w, text.width(block, "body", raw=True))
        self.assertTrue(surf.get_bounding_rect().w > 0)                   # taslak bloklar çizildi
        self.assertEqual(text.draw(surf, "Müzik", "body", (255, 0, 0), (0, 0), raw=True).w,
                         round(5 * text.pitch("body")))                   # raw: çevrilmez
        app.push(SettingsScreen(app))
        render_ok(app)
        app.push(SystemInfo(app))
        render_ok(app)

    def test_ayarlarda_dil_secimi(self):
        from soleil import lang
        from soleil.screens.settings_screen import SettingsScreen
        app = make_app()
        codes = [c for c, _ in lang.available()]
        self.assertEqual(codes[0], "tr")
        screen = SettingsScreen(app)
        app.push(screen)
        row = next(i for i, r in enumerate(screen.rows) if r.label == "Dil")
        screen.selected = row
        press(app, Action.SELECT)
        self.assertEqual(app.settings.language, codes[1 % len(codes)])
        self.assertEqual(lang.current().code, codes[1 % len(codes)])

    def test_ceviri_listesi_araci(self):
        import importlib.util
        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location("ceviri_listesi", root / "tools" / "ceviri_listesi.py")
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        texts = tool.collect()
        for expected in ("Sistem Bilgisi", "{n} şarkı", "ÇALAN YOK", "Donanım & Güç", "Tuğla Kırma"):
            self.assertIn(expected, texts)
        self.assertFalse(any(t.startswith("AA:00") for t in texts))       # cihaz adresi
        self.assertNotIn("GABRIELLA RAELYN", texts)                       # örnek şarkı
        # Doldurulmuş satırlar korunur, yeniler eklenir, artık olmayanlar "Eski"ye
        tool.FOLDER = Path(self.tmp.name)
        tool.write("deneme")
        table = (self.folder / "ceviri.md").read_text(encoding="utf-8")
        self.assertIn("| Sistem Ayarları | simsa narae |", table)
        self.assertIn("| Sistem Bilgisi |  |", table)
        self.assertIn("## Eski", table)                                   # "Eski Yazı" kodda yok
        added, _ = tool.write("deneme")
        self.assertEqual(added, 0)



class TakvimiSeb(unittest.TestCase):
    """Kullanıcının gece takvimi; beklenen değerler takvim görselinden."""

    def test_gorseldeki_geceler(self):
        import datetime as dt
        from soleil import seb

        def n(y, m, d):
            x = seb.from_date(dt.date(y, m, d))
            return (x.month.short if x.month else x.special, x.night, x.year)

        self.assertEqual(n(2025, 12, 23), ("AS", 1, 0))
        self.assertEqual(n(2026, 1, 1), ("AS", 10, 0))
        self.assertEqual(n(2026, 2, 1), ("AS", 41, 0))
        self.assertEqual(n(2026, 2, 20), ("AS", 60, 0))
        self.assertEqual(n(2026, 2, 21), ("MA", 1, 0))
        self.assertEqual(n(2026, 3, 1), ("MA", 9, 0))
        self.assertEqual(n(2026, 4, 1), ("MA", 40, 0))
        self.assertEqual(n(2026, 4, 21), ("MA", 60, 0))
        self.assertEqual(n(2026, 4, 22), ("PA", 1, 0))
        self.assertEqual(n(2026, 5, 1), ("PA", 10, 0))
        self.assertEqual(n(2026, 6, 20), ("PA", 60, 0))
        self.assertEqual(n(2026, 6, 21), ("Alaca", 0, 0))
        self.assertEqual(n(2026, 6, 22), ("Ağaran", 0, 0))
        self.assertEqual(n(2026, 6, 23), ("ZA", 1, 0))
        self.assertEqual(n(2026, 8, 21), ("ZA", 60, 0))
        self.assertEqual(n(2026, 8, 22), ("LA", 1, 0))
        self.assertEqual(n(2026, 10, 20), ("LA", 60, 0))
        self.assertEqual(n(2026, 10, 21), ("KA", 1, 0))
        self.assertEqual(n(2026, 12, 19), ("KA", 60, 0))
        self.assertEqual(n(2026, 12, 20), ("Yelda Arifesi", 0, 0))
        self.assertEqual(n(2026, 12, 21), ("Yelda", 0, 0))
        self.assertEqual(n(2026, 12, 22), ("Yelda Ertesi", 0, 0))
        self.assertEqual(n(2026, 12, 23), ("AS", 1, 1))
        self.assertEqual(n(2025, 12, 22), ("Yelda Ertesi", 0, -1))         # İnşa'dan önce: Yıl -1
        # Artık yıl: Konuk Gece 8 ile 9 Manolya arası, haftaya sayılmaz
        self.assertEqual(n(2028, 2, 28), ("MA", 8, 2))
        self.assertEqual(n(2028, 2, 29), ("Konuk Gece", 0, 2))
        self.assertEqual(n(2028, 3, 1), ("MA", 9, 2))
        self.assertEqual(seb.from_date(dt.date(2028, 3, 1)).weekday, "Zifir")
        self.assertEqual(n(2028, 4, 21), ("MA", 60, 2))

    def test_yazim_ve_hafta(self):
        import datetime as dt
        from soleil import seb
        x = seb.from_date(dt.date(2026, 10, 18))
        self.assertEqual(x.daily(), "Tün, 58 Lavanta, Yıl 0")
        self.assertEqual(x.official(), "58 Lavanta 0 BS")
        self.assertEqual(x.short(), "58 LA 0")
        self.assertEqual(x.file_name(), "00-5-58")
        self.assertEqual(seb.from_date(dt.date(2026, 10, 15)).weekday, "Akşam")  # 55 Lavanta
        self.assertEqual(seb.from_date(dt.date(2026, 10, 20)).weekday, "Tan")    # 60
        yelda = seb.from_date(dt.date(2026, 12, 21))
        self.assertEqual((yelda.daily(), yelda.official(), yelda.group), ("Yelda, Yıl 0", "Yelda 0 BS", "Yelda Geceleri"))
        self.assertIsNone(yelda.weekday)

    def test_gece_oglen_degisir(self):
        import datetime as dt
        from soleil import seb
        self.assertEqual(seb.night_date(dt.datetime(2026, 10, 20, 11, 59)), dt.date(2026, 10, 19))
        self.assertEqual(seb.night_date(dt.datetime(2026, 10, 20, 12, 0)), dt.date(2026, 10, 20))
        self.assertEqual(seb.night_date(dt.datetime(2026, 10, 21, 2, 0)), dt.date(2026, 10, 20))

    def test_geri_donusum(self):
        """Her miladi gün bir geceye, her gece tek bir miladi güne (2023-2030)."""
        import datetime as dt
        from soleil import seb
        d = dt.date(2023, 1, 1)
        while d < dt.date(2031, 1, 1):
            x = seb.from_date(d)
            back = seb.to_date(x.year, x.month.number, x.night) if x.month else seb.special_date(x.year, x.special)
            self.assertEqual(back, d, x)
            d += dt.timedelta(days=1)


if __name__ == "__main__":
    unittest.main()
