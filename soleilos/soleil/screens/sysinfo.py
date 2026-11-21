"""Sistem bilgisi (telemetri): IP, pil, sıcaklık, bellek, depolama...

Değerler iki saniyede bir yenilenir. Pi'ye özgü olanlar (sıcaklık,
bellek) Linux dosyalarından okunur; PC'de bulunamayanlar "—" görünür.
"""

from __future__ import annotations

import os
import platform
import shutil
import socket
import sys
from typing import Optional

import pygame

from ..lang import N_, _
from .. import __version__, config
from ..input import Action
from ..ui import chrome
from ..ui.listview import draw_back_row
from .base import Screen

REFRESH = 2.0


def local_ip() -> Optional[str]:
    """Yerel ağdaki IP. UDP soketi "bağlamak" paket göndermez, sadece
    hangi ağ arayüzünün kullanılacağını öğrenmeye yarar."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            ip = s.getsockname()[0]
        return None if ip.startswith("127.") else ip
    except OSError:
        return None


def cpu_temp() -> Optional[float]:
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read().strip()) / 1000
    except (OSError, ValueError):
        return None


def memory() -> Optional[tuple[int, int]]:
    """(kullanılan, toplam) bayt; Linux dışında None."""
    try:
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                key, value = line.split(":", 1)
                info[key] = int(value.split()[0]) * 1024
        return info["MemTotal"] - info["MemAvailable"], info["MemTotal"]
    except (OSError, KeyError, ValueError):
        return None


def system_uptime() -> Optional[float]:
    try:
        with open("/proc/uptime") as f:
            return float(f.read().split()[0])
    except (OSError, ValueError):
        return None


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f}{unit}" if unit in ("B", "KB", "MB") else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def duration(seconds: float) -> str:
    s = int(seconds)
    d, s = divmod(s, 86400)
    h, s = divmod(s, 3600)
    m, s = divmod(s, 60)
    return f"{d}g {h:02d}:{m:02d}" if d else f"{h:02d}:{m:02d}:{s:02d}"


def battery_value(status) -> str:
    """3.92V [%84] [ŞARJDA]; voltaj sadece ölçülebiliyorsa."""
    text = f"%{status.battery}"
    if status.voltage is not None:
        text = f"{status.voltage:.2f}V [{text}]"
    if status.charging:
        text += " [ŞARJDA]"
    return text


def cpu_load() -> Optional[float]:
    """Son 1 dakikanın yükü, çekirdek başına yüzde (Linux)."""
    if not hasattr(os, "getloadavg"):
        return None
    return os.getloadavg()[0] / (os.cpu_count() or 1) * 100


class SystemInfo(Screen):
    """Figma'daki düzen: köşeli parantezli grup başlıkları, altında ağaç
    çizgileriyle bağlı "Ad : değer" satırları. Encoder kaydırır, tıklama
    ya da geri çıkar."""

    title = "Sols / Ayarlar / Sistem Bilgisi"
    animating = True
    GROUP_H = 32
    ITEM_H = 25
    KEY_CHARS = 9           # en uzun ad (Bluetooth); ":" hepsinde aynı hizada

    def __init__(self, app) -> None:
        super().__init__(app)
        self.timer = 0.0
        self.top = 0             # en üstte görünen satır
        self.lines: list[tuple] = []
        self._collect()

    def handle(self, action: Action) -> None:
        if action is Action.SELECT:
            self.app.pop()
        elif action is Action.DOWN:
            self.top = min(self.top + 1, self._max_top())
        elif action is Action.UP:
            self.top = max(self.top - 1, 0)
        else:
            super().handle(action)

    def update(self, dt: float) -> None:
        self.timer += dt
        if self.timer >= REFRESH:
            self.timer = 0.0
            self._collect()

    def _collect(self) -> None:
        app, st = self.app, self.app.status
        temp = cpu_temp()
        load = cpu_load()
        mem = memory()
        disk = shutil.disk_usage(config.DATA if config.DATA.exists() else config.ROOT)
        uptime = system_uptime()

        cpu = f"{temp:.0f}°C" if temp is not None else "—"
        if load is not None:
            cpu += " // " + _("Yük: %{n}").format(n=f"{load:.0f}")

        if not st.wifi:
            wifi, ip = "KAPALI", "—"
        else:
            link = app.system.wifi_link()
            wifi = "AÇIK"
            if link:
                ssid, dbm = link
                wifi = ssid + (f" [{dbm} dBm]" if dbm is not None else "")
            ip = local_ip() or "BAĞLI DEĞİL"

        if not st.bluetooth:
            bt = "KAPALI"
        else:
            device = next((d for d in app.bluetooth.paired if d.connected), None)
            bt = device.name if device else "AÇIK"

        self.lines = [
            ("group", N_("Donanım & Güç")),
            ("item", N_("İşlemci"), cpu),
            ("item", N_("Bellek"), f"{human_size(mem[0])} / {human_size(mem[1])}" if mem else "—"),
            ("item", N_("Pil"), battery_value(st)),
            ("group", N_("Ağ & Bağlantı")),
            ("item", N_("IP"), ip),
            ("item", N_("Wi-Fi"), wifi),
            ("item", N_("Bluetooth"), bt),
            ("group", N_("Sistem & Depolama")),
            ("item", N_("Cihaz"), socket.gethostname()[:16]),
            ("item", N_("Sürüm"), f"SoleilOS {__version__}"),
            ("item", N_("Çekirdek"), f"{platform.system()} {platform.release()}"),
            ("item", N_("Ekran"), f"{app.layout.width}x{app.layout.height}"),
            ("item", N_("Depolama"), f"{human_size(disk.used)} / {human_size(disk.total)}"),
            ("item", N_("Çalışma"), duration(uptime if uptime is not None else app.time)),
        ]
        self.top = min(self.top, self._max_top())

    # -- kaydırma --------------------------------------------------------------

    def _height(self, line) -> int:
        return self.GROUP_H if line[0] == "group" else self.ITEM_H

    def _area(self) -> tuple[int, int]:
        L = self.app.layout
        return L.row_cy(0) + L.row_pitch // 2, L.footer_line_y - 8

    def _max_top(self) -> int:
        """Son satır görünene kadar kaydırılabilir."""
        top, bottom = self._area()
        room, n = bottom - top, len(self.lines)
        while n > 0 and room - self._height(self.lines[n - 1]) >= 0:
            room -= self._height(self.lines[n - 1])
            n -= 1
        return n

    # -- çizim -----------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        app, t, L = self.app, self.app.theme, self.app.layout
        chrome.draw_header(app, surf, self.title)
        draw_back_row(app, surf, L.row_cy(0), self.top == 0)

        x = L.left + 4
        tree_x = x + 9
        key_x = tree_x + 10
        colon_x = key_x + round(app.text.pitch("medium") * self.KEY_CHARS)
        value_x = colon_x + round(app.text.pitch("medium") * 1.6)
        right = L.left + L.row_box_w + 3

        y, bottom = self._area()
        for i in range(self.top, len(self.lines)):
            line = self.lines[i]
            h = self._height(line)
            if y + h > bottom:
                break
            cy = y + h // 2
            if line[0] == "group":
                app.text.draw(surf, f"[{line[1]}]", "body", t.fg, (x, cy + 2), "midleft")
            else:
                _, key, value = line
                last = i + 1 >= len(self.lines) or self.lines[i + 1][0] == "group"
                # Ağaç: dikey çizgi bir sonraki satıra uzanır, sonuncuda ortada biter
                surf.fill(t.fg, (tree_x, y, 2, (cy - y + 1) if last else h))
                surf.fill(t.fg, (tree_x, cy, 7, 2))
                app.text.draw(surf, key, "medium", t.fg, (key_x, cy), "midleft")
                app.text.draw(surf, ":", "medium", t.fg, (colon_x, cy), "midleft")
                value = app.text.fit(value, "medium", right - value_x)
                app.text.draw(surf, value, "medium", t.fg, (value_x, cy), "midleft")
            y += h

        max_top = self._max_top()
        if max_top:
            top, bottom = L.scroll_top + 17, L.scroll_bottom - 17
            chrome.draw_scrollbar(app, surf, round(top + (bottom - top) * self.top / max_top))
        chrome.draw_footer(app, surf)
