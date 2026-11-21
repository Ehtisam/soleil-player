"""Müzik / Bluetooth: kayıtlı cihazlar, yeni cihaz arama, bağlan / kes / unut.

Bluetooth ayarlardan kapalıysa tek satır çıkar, tıklayınca açılır.
Bir kulaklık ya da hoparlör bağlanınca ses ona gider; kesilince cihazın
kendi çıkışına (kulaklık soketi / hoparlör) döner.
"""

from __future__ import annotations

from ..bluetooth import BtDevice
from ..ui.listview import BACK, ListItem, ListScreen

TITLE = "Sols / Müzik / Bluetooth"


class _LiveList(ListScreen):
    """Bluetooth durumu değiştikçe satırlarını yeniden kuran liste."""

    def __init__(self, app, title: str) -> None:
        self.app = app
        self._key = None
        super().__init__(app, [])
        self.title = title
        self._rebuild()

    def _items(self) -> list[ListItem]:
        return []

    def _signature(self):
        bt = self.app.bluetooth
        return (bt.version, bt.busy, self.app.settings.bluetooth)

    def _rebuild(self) -> None:
        key = self._signature()
        if key == self._key:
            return
        self._key = key
        self.rows = [BACK] + self._items()
        self.selected = min(max(self.selected, 1), len(self.rows) - 1)
        self._scroll_to_selected()

    def update(self, dt: float) -> None:
        self._rebuild()
        self.animating = bool(self.app.bluetooth.busy)


def _state(d: BtDevice) -> str:
    return "[BAĞLI]" if d.connected else (f"[{d.kind}]" if d.kind else "")


class BluetoothMenu(_LiveList):
    def __init__(self, app) -> None:
        super().__init__(app, TITLE)
        app.bluetooth.refresh()

    def _items(self) -> list[ListItem]:
        app, bt = self.app, self.app.bluetooth
        if not app.settings.bluetooth:
            def turn_on():
                app.settings.bluetooth = True
                app.settings_changed()
                app.toast("BLUETOOTH AÇILDI")
            return [ListItem("Bluetooth Kapalı", right="[AÇ]", act=turn_on)]
        busy = f"[{bt.busy}]" if bt.busy else None
        items = [ListItem("Yeni Cihaz Ara", right=busy, open=lambda: ScanScreen(app))]
        for d in bt.paired:
            items.append(ListItem(d.name, raw=True, right=_state(d), open=lambda d=d: DeviceScreen(app, d.address)))
        return items


class ScanScreen(_LiveList):
    """Açılınca aramaya başlar; bulunan cihazlar geldikçe listeye eklenir."""

    def __init__(self, app) -> None:
        super().__init__(app, f"{TITLE} / Ara")
        app.bluetooth.scan()

    def _items(self) -> list[ListItem]:
        app, bt = self.app, self.app.bluetooth
        items = []
        for d in bt.found:
            def pair(d=d):
                bt.pair_connect(d.address)
                app.toast("EŞLEŞTİRİLİYOR", d.name)
            items.append(ListItem(d.name, raw=True, right=f"[{d.kind}]" if d.kind else None, act=pair))
        if bt.busy == "ARANIYOR":
            items.append(ListItem("Aranıyor...", act=lambda: None))
        elif not items:
            items.append(ListItem("Tekrar Ara", right="[CİHAZ YOK]", act=bt.scan))
        else:
            items.append(ListItem("Tekrar Ara", act=bt.scan))
        return items


class DeviceScreen(_LiveList):
    """Kayıtlı bir cihaz: bağlan / bağlantıyı kes / unut (iki kez basınca)."""

    def __init__(self, app, address: str) -> None:
        self.address = address
        self._forget_until = -1.0
        d = app.bluetooth.devices.get(address)
        super().__init__(app, f"{TITLE} / {d.name if d else address}")

    def _signature(self):
        return super()._signature() + (self._forget_until > self.app.time,)

    def _items(self) -> list[ListItem]:
        app, bt = self.app, self.app.bluetooth
        d = bt.devices.get(self.address)
        if d is None:
            return [ListItem("Cihaz Unutuldu", act=app.pop)]
        if bt.busy:
            first = ListItem(bt.busy.title() + "...", act=lambda: None)
        elif d.connected:
            first = ListItem("Bağlantıyı Kes", act=lambda: bt.disconnect(d.address))
        else:
            first = ListItem("Bağlan", act=lambda: bt.connect(d.address))

        def forget():
            if self._forget_until > app.time:
                bt.forget(d.address)
                app.pop()
            else:
                self._forget_until = app.time + 3.0
                app.toast("UNUTMAK İÇİN", "TEKRAR BAS", seconds=3.0)

        return [
            first,
            ListItem("Cihazı Unut", act=forget, value=lambda: "[EMİN MİSİN?]" if self._forget_until > app.time else ""),
            ListItem("Tür", right=f"[{d.kind or 'BİLİNMİYOR'}]", act=lambda: None),
            ListItem("Adres", right=f"[{d.address[-8:]}]", act=lambda: None),
        ]
