"""Pi'de sistem işleri: Wi-Fi / Bluetooth aç-kapa, güvenli kapatma, pil.

PC'de (PcSystem) hiçbiri bir şey yapmaz; kapatma sadece uygulamadan
çıkar. Pi'de uygulama servis olarak root yetkisiyle çalışır (LED ve
rfkill bunu istiyor), komutlar doğrudan çağrılır.

Pil: kendi yaptığımız LiPo + şarj modülünde ölçüm yok, seviye bilinmiyor
(battery() None döner, header'daki simge sabit kalır). İleride I2C ile
bir ölçüm modülü (ör. MAX17048) ya da PiSugar eklenirse buraya okunur.
"""

from __future__ import annotations

import subprocess
from typing import Optional


def parse_iw_link(out: str) -> Optional[tuple[str, Optional[int]]]:
    ssid, dbm = None, None
    for line in out.splitlines():
        key, _, value = line.strip().partition(":")
        if key == "SSID":
            ssid = value.strip()
        elif key == "signal":
            try:
                dbm = int(value.split()[0])
            except (ValueError, IndexError):
                pass
    return (ssid, dbm) if ssid else None


class PcSystem:
    name = "pc"

    def apply_radios(self, wifi: bool, bluetooth: bool) -> None:
        pass

    def battery(self) -> Optional[tuple[int, bool]]:
        """(yüzde, şarj oluyor mu) ya da ölçülemiyorsa None."""
        return None

    def wifi_link(self) -> Optional[tuple[str, Optional[int]]]:
        """Bağlı Wi-Fi ağı: (ağ adı, sinyal dBm) ya da bağlı değilse None.
        PC'de bilinmiyor (gerçek ağ adı ekran görüntülerine girmesin)."""
        return None

    def shutdown(self) -> None:
        pass                       # PC'de sadece uygulama kapanır


class PiSystem(PcSystem):
    name = "pi"

    def __init__(self) -> None:
        self._radios: Optional[tuple[bool, bool]] = None

    def _run(self, *cmd: str) -> None:
        try:
            subprocess.run(cmd, check=False, timeout=5, capture_output=True)
        except (OSError, subprocess.SubprocessError) as e:
            print(f"[sistem] {' '.join(cmd)}: {e}")

    def wifi_link(self) -> Optional[tuple[str, Optional[int]]]:
        """`iw dev wlan0 link` çıktısından ağ adı ve sinyal (DENENMEDİ).
        Bağlıyken: "SSID: Ev_Agi" ve "signal: -58 dBm" satırları."""
        try:
            out = subprocess.run(["iw", "dev", "wlan0", "link"], capture_output=True,
                                 text=True, timeout=2).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        return parse_iw_link(out)

    def apply_radios(self, wifi: bool, bluetooth: bool) -> None:
        if self._radios == (wifi, bluetooth):
            return
        self._radios = (wifi, bluetooth)
        self._run("rfkill", "unblock" if wifi else "block", "wifi")
        self._run("rfkill", "unblock" if bluetooth else "block", "bluetooth")

    def shutdown(self) -> None:
        # SD kart bozulmasın diye güç anahtarından önce bu yapılmalı
        self._run("systemctl", "poweroff")
