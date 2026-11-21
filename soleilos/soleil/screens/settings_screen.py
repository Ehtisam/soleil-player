"""Sistem ayarları.

Açık/kapalı ve kademeli ayarlar tıklayınca bir sonraki değere geçer,
değer satırın sağında görünür. Tema seçicide encoder çevirdikçe tema
canlı değişir; tıklamak seçer, geri dönmek eski temaya döndürür.
"""

from __future__ import annotations

from .. import lang, settings as S
from ..input import Action
from ..theme import THEMES
from ..ui.listview import ListItem, ListScreen
from .sysinfo import SystemInfo

THEME_NAMES = {"amber": "AMBER", "mor": "MOR", "kırmızı": "KIRMIZI", "mavi": "MAVİ"}


def _on_off(value: bool) -> str:
    return "AÇIK" if value else "KAPALI"


class SettingsScreen(ListScreen):
    title = "Sols / Sistem Ayarları"

    def __init__(self, app) -> None:
        st = app.settings

        def change(**values):
            def act():
                for key, value in values.items():
                    setattr(st, key, value() if callable(value) else value)
                app.settings_changed()
            return act

        # Wi-Fi ve Bluetooth en üstte: en sık kullanılanlar (yeni Figma'daki gibi)
        items = [
            ListItem("Wi-Fi", value=lambda: f"[{_on_off(st.wifi)}]",
                     act=change(wifi=lambda: not st.wifi)),
            ListItem("Bluetooth", value=lambda: f"[{_on_off(st.bluetooth)}]",
                     act=change(bluetooth=lambda: not st.bluetooth)),
            ListItem("Tema", open=lambda: ThemePicker(app),
                     value=lambda: f"[{THEME_NAMES.get(st.theme, st.theme.upper())}]"),
            ListItem("Dil", value=lambda: f"[{dict(lang.available()).get(st.language, 'TÜRKÇE')}]",
                     act=change(language=lambda: S.next_in([c for c, _ in lang.available()], st.language))),
            ListItem("Parlaklık", value=lambda: f"[%{st.brightness}]",
                     act=change(brightness=lambda: S.next_in(S.BRIGHTNESS_STEPS, st.brightness))),
            ListItem("Ekran Uykusu", value=lambda: f"[{S.sleep_label(st.sleep_after)}]",
                     act=change(sleep_after=lambda: S.next_in(S.SLEEP_STEPS, st.sleep_after))),
            ListItem("Işık Çubukları", value=lambda: f"[{st.led_mode}]",
                     act=change(led_mode=lambda: S.next_in(S.LED_MODES, st.led_mode))),
            ListItem("Okuma Yazısı", value=lambda: f"[{st.reader_size}]",
                     act=change(reader_size=lambda: S.next_in(S.READER_SIZES, st.reader_size))),
            ListItem("Açılış Ekranı", value=lambda: f"[{_on_off(st.boot_animation)}]",
                     act=change(boot_animation=lambda: not st.boot_animation)),
            ListItem("Sistem Bilgisi", open=lambda: SystemInfo(app)),
            ListItem("Cihazı Kapat", act=self._power_off,
                     value=lambda: "[EMİN MİSİN?]" if self._confirm_until > app.time else ""),
        ]
        self._confirm_until = -1.0
        super().__init__(app, items)

    def _power_off(self) -> None:
        """İki kez basınca kapanır. Güç anahtarından önce bunu kullanmak
        SD kartı korur."""
        app = self.app
        if self._confirm_until > app.time:
            app.toast("KAPANIYOR")
            app.shutdown()
        else:
            self._confirm_until = app.time + 3.0
            app.toast("KAPATMAK İÇİN", "TEKRAR BAS", seconds=3.0)


class ThemePicker(ListScreen):
    title = "Sols / Ayarlar / Tema"

    def __init__(self, app) -> None:
        self.original = app.theme.name
        names = list(THEMES)
        items = [ListItem(THEME_NAMES.get(n, n.upper()), act=self._choose) for n in names]
        super().__init__(app, items, selected=names.index(self.original))
        self.names = names

    def _choose(self) -> None:
        self.app.set_theme(self.names[self.selected - 1])
        self.app.pop()

    def handle(self, action: Action) -> None:
        super().handle(action)
        if action in (Action.UP, Action.DOWN):
            # Canlı önizleme: GERİ satırındayken eski tema
            name = self.names[self.selected - 1] if self.selected > 0 else self.original
            self.app.theme = THEMES[name]
        elif action is Action.BACK or (action is Action.SELECT and self.selected == 0):
            self.app.theme = THEMES[self.original]   # vazgeçildi
