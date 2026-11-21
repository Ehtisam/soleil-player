"""Uygulama: ekran yığını, ana döngü, ortak durum."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Optional

import pygame

from . import config, lang
from .audio import create_engine
from .display import DesktopDisplay
from .hw.framebuffer import FramebufferDisplay
from .hw.gpio_input import GpioInput
from .hw.leds import LedEffects, Ws281xStrip
from .hw.system import PcSystem, PiSystem
from .documents import ReadingLog
from .icons import Icons
from .input import KeyboardInput
from .library import Covers, Library
from .likes import Likes
from .bluetooth import BluezBluetooth, FakeBluetooth, audio_device_for
from .radio import RadioDirectory
from .lyrics import LyricsService
from .playback import Playback
from .screens.base import Screen
from .settings import Settings
from .text import Text
from .timers import CountdownTimer, Stopwatch, duration_label
from .theme import THEMES
from .ui import chrome
from .ui.layout import Layout

SAVE_DELAY = 2.0   # ayar değişikliği bu kadar saniye sonra diske yazılır
BATTERY_WARN = (20, 10, 5)      # bu yüzdelere inince birer kez uyarı
BATTERY_LOW = 10                # altında header'daki simge yanıp söner
BATTERY_EMPTY = 3               # burada cihaz kendini düzgünce kapatır (SD kart için)
BATTERY_CHECK = 30.0            # pil kaç saniyede bir okunur
WARNING_RED = (255, 40, 20)


@dataclass
class Status:
    """Alt bar ve header'da gösterilen cihaz durumu. Ses, Wi-Fi ve
    Bluetooth ayarlardan gelir; pil şimdilik sabit, Pi'de okunacak."""
    volume: int = 80
    bluetooth: bool = True
    wifi: bool = True
    battery: int = 80       # yüzde
    charging: bool = False
    voltage: Optional[float] = None   # pil voltajı; ölçüm modülü (INA219) gelince


@dataclass
class Toast:
    """Kısa süre görünen bildirim: duraklatma, şarkı geçme, ses vb."""
    title: str
    detail: str = ""
    bar: Optional[float] = None   # 0..1 arası doluluk çubuğu (ses, sarma)
    until: float = 0.0


class App:
    def __init__(self, height: int = config.HEIGHT, theme: Optional[str] = None,
                 scale: Optional[int] = None, headless: bool = False, device: str = "pc",
                 face: bool = True) -> None:
        """device: "pc" (pencere + klavye) ya da "pi" (SPI ekran, GPIO, LED).
        headless: ekransız (testler, araçlar)."""
        self.device = "headless" if headless else device
        if self.device != "pc":
            os.environ["SDL_VIDEODRIVER"] = "dummy"       # pencere yok
        pygame.init()
        self.size = (config.WIDTH, height)
        if self.device == "pc":
            self.display = DesktopDisplay(self.size, scale, "SoleilOS", face=face)
        else:
            pygame.display.set_mode((1, 1))
            self.display = FramebufferDisplay(self.size) if self.device == "pi" else None
        pygame.key.set_repeat(300, 60)

        # Araçlar (headless) kayıtlı ayarlara dokunmaz, internete çıkmaz
        self.headless = headless
        self.settings = Settings() if headless else Settings.load()
        if theme:
            self.settings.theme = theme
        lang.set_language(self.settings.language)
        self.status = Status(volume=self.settings.volume, wifi=self.settings.wifi,
                             bluetooth=self.settings.bluetooth)

        self.canvas = pygame.Surface(self.size)
        self.layout = Layout(*self.size)
        self.theme = THEMES.get(self.settings.theme, THEMES["amber"])
        self.text = Text()
        self.icons = Icons()
        # Ses motoru (mpv). headless (testler, araçlar) sessiz çalışır
        self.audio = create_engine(silent=headless)
        self.playback = Playback(engine=self.audio, volume=self.settings.volume)
        self.library = Library(enabled_cache=not headless)
        self.covers = Covers()
        self.radio = RadioDirectory(online=not headless, save=not headless)
        self.likes = Likes(save=not headless)
        self.bluetooth = BluezBluetooth() if self.device == "pi" else FakeBluetooth()
        self._bt_version = -1
        self._bt_audio = None
        self._library_version = 0
        self.lyrics = LyricsService(online=not headless)
        self.reading = ReadingLog.load(enabled=not headless)
        self.stopwatch = Stopwatch()
        self.timer = CountdownTimer()
        self._timer_second = None
        self.input = KeyboardInput()
        # Donanım: Pi'de GPIO tuşlar ve WS2812B, PC'de penceredeki ön yüz
        self.gpio = GpioInput() if self.device == "pi" else None
        self.system = PiSystem() if self.device == "pi" else PcSystem()
        self.leds = LedEffects()
        self.led_out = None
        if self.device == "pi":
            try:
                self.led_out = Ws281xStrip()
            except Exception as e:      # LED takılı değil, kütüphane yok vb.
                print(f"[ışık] LED çubukları açılamadı: {e}")
        elif self.display is not None:
            self.led_out = self.display
        self.power_off = False
        self._battery_check = 0.0
        self._battery_warned = 101
        self._shutdown_at: Optional[float] = None
        self.stack: list[Screen] = []
        self.time = 0.0                 # uygulama açıldığından beri geçen saniye
        self.last_input = 0.0
        self.sleeping = False
        self.toast_info: Optional[Toast] = None
        self._save_at: Optional[float] = None
        self.dirty = True
        self.running = False

    # -- ekran yığını ------------------------------------------------------

    @property
    def screen(self) -> Screen:
        return self.stack[-1]

    def push(self, screen: Screen) -> None:
        self.stack.append(screen)
        self.dirty = True

    def pop(self) -> None:
        if len(self.stack) > 1:
            self.stack.pop().closed()
            self.dirty = True

    def replace(self, screen: Screen) -> None:
        """En üstteki ekranı değiştirir (ör. açılış ekranından ana menüye)."""
        self.stack[-1].closed()
        self.stack[-1] = screen
        self.dirty = True

    def toast(self, title: str, detail: str = "", bar: Optional[float] = None,
              seconds: float = 1.2) -> None:
        self.toast_info = Toast(title, detail, bar, self.time + seconds)
        self.dirty = True

    @property
    def animating(self) -> bool:
        return not self.sleeping and (self.screen.animating or self.toast_info is not None)

    # -- ayarlar -------------------------------------------------------------

    def set_theme(self, name: str) -> None:
        self.theme = THEMES[name]
        self.settings.theme = name
        self.settings_changed()

    def next_theme(self) -> None:
        names = list(THEMES)
        self.set_theme(names[(names.index(self.theme.name) + 1) % len(names)])

    def settings_changed(self) -> None:
        """Ayar değişti: durumu eşitle, kısa bir süre sonra diske yaz."""
        s, st = self.settings, self.status
        st.wifi, st.bluetooth = s.wifi, s.bluetooth
        self.system.apply_radios(s.wifi, s.bluetooth)
        if lang.current().code != s.language:
            lang.set_language(s.language)
        self._save_at = self.time + SAVE_DELAY
        self.dirty = True

    def _sync_status(self) -> None:
        # Ses oynatıcıdan değişiyor; ayarlara da yansısın
        if self.status.volume != self.settings.volume:
            self.settings.volume = self.status.volume
            self.playback.set_volume(self.status.volume)
            self._save_at = self.time + SAVE_DELAY
        if self._save_at is not None and self.time >= self._save_at:
            self._save_at = None
            if not self.headless:
                self.settings.save()

    # -- çizim ve döngü ----------------------------------------------------

    def render(self) -> pygame.Surface:
        self.canvas.fill(self.theme.bg)
        self.screen.draw(self.canvas)
        if self.toast_info:
            chrome.draw_toast(self, self.canvas, self.toast_info)
        return self.canvas

    def screenshot(self) -> None:
        config.SCREENSHOTS.mkdir(exist_ok=True)
        path = config.SCREENSHOTS / time.strftime("soleil-%Y%m%d-%H%M%S.png")
        pygame.image.save(self.canvas, str(path))
        print(f"Ekran görüntüsü: {path}")

    def _handle_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.running = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_F12:
            self.screenshot()
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_t:
            self.next_theme()
        for action in self.input.from_event(event, self.time):
            self.handle(action)

    def handle(self, action) -> None:
        self.last_input = self.time
        if self.sleeping:
            # Uyuyan ekranı uyandıran tuş başka bir şey yapmasın
            self.sleeping = False
            self.dirty = True
            return
        self.screen.handle(action)
        self.dirty = True

    def tick(self, dt: float) -> None:
        """Zamanla ilerleyen her şey: uzun basma, çalma, ekran, bildirim, uyku."""
        self.time += dt
        for action in self.input.update(self.time):
            self.handle(action)
        if self.gpio:
            for action in self.gpio.poll():
                self.handle(action)
        self.playback.update(dt)
        if self.playback.stream_lost:
            self.playback.stream_lost = False
            self.toast("YAYIN KESİLDİ", self.playback.current.title if self.playback.current else "")
        if self.radio.changed:
            self.radio.changed = False
            self.dirty = True
        # Arka planda hazırlanan kapak ya da kütüphane taraması bitti: yeniden çiz
        if self.covers.changed or self.library.version != self._library_version:
            self.covers.changed = False
            self._library_version = self.library.version
            self.dirty = True
        self._update_timers(dt)
        self._update_battery()
        self._update_bluetooth(dt)
        self.screen.update(dt)
        if self.toast_info and self.time >= self.toast_info.until:
            self.toast_info = None
            self.dirty = True
        self._sync_status()
        limit = self.settings.sleep_after
        if limit and not self.sleeping and self.time - self.last_input >= limit:
            self.sleeping = True
            self.dirty = True

    def _update_bluetooth(self, dt: float) -> None:
        bt = self.bluetooth
        bt.update(dt)
        message = bt.take_message()
        if message:
            self.toast(*message)
        if bt.version != self._bt_version:
            self._bt_version = bt.version
            self.dirty = True
            # Kulaklık/hoparlör bağlanınca ses ona, kesilince cihazın kendi çıkışına
            audio = bt.connected_audio
            if (audio and audio.address) != self._bt_audio:
                self._bt_audio = audio.address if audio else None
                if self.audio and self.device == "pi":
                    self.audio.set_output(audio_device_for(audio))

    @property
    def battery_low(self) -> bool:
        return self.status.battery <= BATTERY_LOW and not self.status.charging

    def _update_battery(self) -> None:
        """Pili okur (ölçüm varsa), azalınca uyarır, bitince kapatır."""
        s = self.status
        if self.time >= self._battery_check:
            self._battery_check = self.time + BATTERY_CHECK
            value = self.system.battery()
            if value is not None:
                s.battery, s.charging = value
                self.dirty = True
        if s.charging:
            self._battery_warned = 101
            self._shutdown_at = None
            return
        for level in BATTERY_WARN:
            if s.battery <= level < self._battery_warned:
                self._battery_warned = level
                self.toast("PİL AZ", f"%{s.battery}", seconds=3)
                self.leds.flash(self.time, 2.0, WARNING_RED)
                self.sleeping = False
                break
        if s.battery <= BATTERY_EMPTY and self._shutdown_at is None:
            self._shutdown_at = self.time + 8
            self.toast("PİL BİTTİ", "KAPANIYOR", seconds=8)
            self.leds.flash(self.time, 8.0, WARNING_RED)
            self.sleeping = False
        if self._shutdown_at is not None and self.time >= self._shutdown_at:
            self.shutdown()
        if self.battery_low and int(self.time * 2) != int((self.time - 1 / 30) * 2):
            self.dirty = True          # simge yanıp sönsün

    def _update_timers(self, dt: float) -> None:
        self.stopwatch.update(dt)
        if self.timer.update(dt):
            # Süre doldu: hangi ekrandaysa bildirim, ekran uyuyorsa uyanır.
            # Pi'de ışık çubukları ve ses de eklenecek.
            self.toast("SÜRE DOLDU", duration_label(self.timer.duration), seconds=6)
            self.leds.flash(self.time)
            self.sleeping = False
            self.last_input = self.time
        # Listelerdeki kalan süre saniyede bir güncellensin
        second = (int(self.timer.remaining), int(self.stopwatch.elapsed))
        if (self.timer.running or self.stopwatch.running) and second != self._timer_second:
            self.dirty = True
        self._timer_second = second

    def shutdown(self) -> None:
        """Cihazı kapat: kaydedip çıkar, Pi'de sistemi kapatır (SD kart için)."""
        self.power_off = True
        self.running = False

    def _update_leds(self, dt: float) -> None:
        if self.leds.update(self, dt) and self.led_out is not None:
            self.led_out.show(self.leds.left, self.leds.right)

    def run(self) -> None:
        clock = pygame.time.Clock()
        self.running = True
        self.system.apply_radios(self.settings.wifi, self.settings.bluetooth)
        while self.running:
            dt = clock.get_time() / 1000
            for event in pygame.event.get():
                self._handle_event(event)
            self.tick(dt)
            self._update_leds(dt)

            if self.dirty or self.animating:
                if self.sleeping:
                    self.display.present_off()
                else:
                    self.render()
                    self.display.present(self.canvas, self.settings.brightness / 100)
                self.dirty = False
            fast = self.animating or self.leds.active
            clock.tick(config.FPS_ACTIVE if fast else config.FPS_IDLE)
        for screen in reversed(self.stack):
            screen.closed()
        if self._save_at is not None and not self.headless:
            self.settings.save()
        if self.audio:
            self.audio.close()
        for part in (self.led_out, self.gpio, self.display):
            if part is not None:
                try:
                    part.close()
                except Exception:
                    pass
        pygame.quit()
        if self.power_off:
            self.system.shutdown()
