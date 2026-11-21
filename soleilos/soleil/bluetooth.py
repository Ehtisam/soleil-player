"""Bluetooth: kulaklık / hoparlör bulma, eşleştirme, bağlanma.

İki uygulaması var, ekranlar ikisini de aynı şekilde kullanır:
- BluezBluetooth (Pi): Linux'un `bluetoothctl` aracı. Komutlar arka planda
  çalışır, ekran donmaz. Ses Bluetooth'a bluez-alsa ile gider: bağlanınca
  mpv'nin çıkışı o cihaza çevrilir. (DENENECEK: gerçek Pi'de)
- FakeBluetooth (PC): sahte cihazlarla taklit; arama, eşleştirme ve
  bağlanma birkaç saniye sürer gibi davranır.

Her ikisinde de işler bitince `version` artar; ekranlar buna bakıp
yenilenir.
"""

from __future__ import annotations

import re
import subprocess
import threading
from dataclasses import dataclass, replace
from typing import Optional

KIND_NAMES = {"audio-headset": "KULAKLIK", "audio-headphones": "KULAKLIK", "audio-card": "HOPARLÖR",
              "phone": "TELEFON", "computer": "BİLGİSAYAR", "input-keyboard": "KLAVYE"}
AUDIO_KINDS = {"KULAKLIK", "HOPARLÖR"}


@dataclass(frozen=True)
class BtDevice:
    address: str
    name: str
    kind: str = ""              # KULAKLIK, HOPARLÖR, TELEFON...
    paired: bool = False
    connected: bool = False

    @property
    def is_audio(self) -> bool:
        return self.kind in AUDIO_KINDS


class Bluetooth:
    """Ortak arayüz. busy: o an süren iş ("ARANIYOR", "BAĞLANIYOR"...)."""

    def __init__(self) -> None:
        self.devices: dict[str, BtDevice] = {}
        self.busy: str = ""
        self.message: Optional[tuple[str, str]] = None    # (başlık, ayrıntı) bildirim
        self.version = 0
        self._lock = threading.Lock()

    # -- ekranların kullandıkları -------------------------------------------------

    @property
    def paired(self) -> list[BtDevice]:
        return sorted((d for d in self.devices.values() if d.paired), key=lambda d: (not d.connected, d.name))

    @property
    def found(self) -> list[BtDevice]:
        return sorted((d for d in self.devices.values() if not d.paired), key=lambda d: d.name)

    @property
    def connected_audio(self) -> Optional[BtDevice]:
        return next((d for d in self.devices.values() if d.connected and d.is_audio), None)

    def refresh(self) -> None: ...
    def scan(self, seconds: float = 12.0) -> None: ...
    def pair_connect(self, address: str) -> None: ...
    def connect(self, address: str) -> None: ...
    def disconnect(self, address: str) -> None: ...
    def forget(self, address: str) -> None: ...
    def update(self, dt: float) -> None: ...

    def take_message(self) -> Optional[tuple[str, str]]:
        with self._lock:
            msg, self.message = self.message, None
        return msg

    # -- iç ------------------------------------------------------------------------

    def _set(self, device: BtDevice) -> None:
        with self._lock:
            self.devices[device.address] = device
            self.version += 1

    def _remove(self, address: str) -> None:
        with self._lock:
            self.devices.pop(address, None)
            self.version += 1

    def _done(self, title: str = "", detail: str = "") -> None:
        with self._lock:
            self.busy = ""
            if title:
                self.message = (title, detail)
            self.version += 1


class FakeBluetooth(Bluetooth):
    """PC'de taklit. Zaman update(dt) ile ilerler (testlerde de aynı)."""

    NEARBY = [
        BtDevice("AA:00:00:00:00:02", "Soleil Hoparlör", "HOPARLÖR"),
        BtDevice("AA:00:00:00:00:03", "Telefon", "TELEFON"),
        BtDevice("AA:00:00:00:00:04", "Kulak İçi Kulaklık", "KULAKLIK"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._set(BtDevice("AA:00:00:00:00:01", "Kablosuz Kulaklık", "KULAKLIK", paired=True))
        self._jobs: list[tuple[float, callable]] = []
        self._now = 0.0

    def _later(self, seconds: float, fn) -> None:
        self._jobs.append((self._now + seconds, fn))

    def update(self, dt: float) -> None:
        self._now += dt
        due = [j for j in self._jobs if j[0] <= self._now]
        self._jobs = [j for j in self._jobs if j[0] > self._now]
        for _, fn in due:
            fn()

    def scan(self, seconds: float = 12.0) -> None:
        if self.busy:
            return
        self.busy = "ARANIYOR"
        for i, d in enumerate(self.NEARBY):
            if d.address not in self.devices:
                self._later(1.0 + i * 1.5, lambda d=d: self._set(d))
        self._later(min(seconds, 6.0), lambda: self._done())

    def pair_connect(self, address: str) -> None:
        d = self.devices.get(address)
        if not d or self.busy:
            return
        self.busy = "EŞLEŞTİRİLİYOR"
        self.version += 1

        def finish():
            self._disconnect_audio_others(d)
            self._set(replace(d, paired=True, connected=True))
            self._done("BAĞLANDI", d.name)
        self._later(2.0, finish)

    def _disconnect_audio_others(self, d: BtDevice) -> None:
        if d.is_audio:
            for other in list(self.devices.values()):
                if other.connected and other.is_audio:
                    self._set(replace(other, connected=False))

    def connect(self, address: str) -> None:
        d = self.devices.get(address)
        if not d or self.busy:
            return
        self.busy = "BAĞLANIYOR"
        self.version += 1

        def finish():
            self._disconnect_audio_others(d)
            self._set(replace(d, connected=True))
            self._done("BAĞLANDI", d.name)
        self._later(1.5, finish)

    def disconnect(self, address: str) -> None:
        d = self.devices.get(address)
        if d:
            self._set(replace(d, connected=False))
            self._done("BAĞLANTI KESİLDİ", d.name)

    def forget(self, address: str) -> None:
        d = self.devices.get(address)
        if d:
            self._remove(address)
            self._done("UNUTULDU", d.name)


class BluezBluetooth(Bluetooth):
    """Pi'de bluetoothctl ile. Her komut kendi thread'inde çalışır."""

    DEVICE_LINE = re.compile(r"Device ([0-9A-F:]{17}) (.+)")

    def __init__(self) -> None:
        super().__init__()
        self.refresh()

    def _ctl(self, *args: str, timeout: float = 20.0) -> str:
        try:
            out = subprocess.run(["bluetoothctl", *args], capture_output=True, text=True, timeout=timeout)
            return out.stdout
        except (OSError, subprocess.SubprocessError) as e:
            print(f"[bluetooth] {' '.join(args)}: {e}")
            return ""

    def _info(self, address: str, name: str) -> BtDevice:
        info = self._ctl("info", address, timeout=5)
        icon = re.search(r"Icon: (\S+)", info)
        return BtDevice(address, name, KIND_NAMES.get(icon.group(1), "") if icon else "",
                        paired="Paired: yes" in info, connected="Connected: yes" in info)

    def _background(self, label: str, work) -> None:
        if self.busy:
            return
        self.busy = label
        self.version += 1

        def run():
            try:
                work()
            finally:
                if self.busy == label:
                    self._done()
        threading.Thread(target=run, daemon=True).start()

    def _read_devices(self) -> None:
        for line in self._ctl("devices", timeout=5).splitlines():
            m = self.DEVICE_LINE.search(line)
            if m:
                self._set(self._info(m.group(1), m.group(2).strip()))

    def refresh(self) -> None:
        threading.Thread(target=self._read_devices, daemon=True).start()

    def scan(self, seconds: float = 12.0) -> None:
        def work():
            self._ctl("--timeout", str(int(seconds)), "scan", "on", timeout=seconds + 5)
            self._read_devices()
        self._background("ARANIYOR", work)

    def pair_connect(self, address: str) -> None:
        def work():
            name = self.devices.get(address, BtDevice(address, address)).name
            self._ctl("pair", address)
            self._ctl("trust", address, timeout=5)
            out = self._ctl("connect", address)
            self._set(self._info(address, name))
            ok = "Connection successful" in out or self.devices[address].connected
            self._done("BAĞLANDI" if ok else "BAĞLANAMADI", name)
        self._background("EŞLEŞTİRİLİYOR", work)

    def connect(self, address: str) -> None:
        def work():
            name = self.devices[address].name
            out = self._ctl("connect", address)
            self._set(self._info(address, name))
            ok = "Connection successful" in out or self.devices[address].connected
            self._done("BAĞLANDI" if ok else "BAĞLANAMADI", name)
        self._background("BAĞLANIYOR", work)

    def disconnect(self, address: str) -> None:
        def work():
            name = self.devices[address].name
            self._ctl("disconnect", address, timeout=10)
            self._set(self._info(address, name))
            self._done("BAĞLANTI KESİLDİ", name)
        self._background("KESİLİYOR", work)

    def forget(self, address: str) -> None:
        def work():
            name = self.devices[address].name
            self._ctl("remove", address, timeout=10)
            self._remove(address)
            self._done("UNUTULDU", name)
        self._background("SİLİNİYOR", work)


def audio_device_for(device: Optional[BtDevice]) -> str:
    """mpv'nin ses çıkışı: Bluetooth cihazı bağlıysa bluez-alsa, yoksa varsayılan."""
    if device is None:
        return "auto"
    return f"alsa/bluealsa:DEV={device.address},PROFILE=a2dp"
