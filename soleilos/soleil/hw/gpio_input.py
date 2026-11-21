"""Pi'de tuşlar ve encoder: GPIO (gpiozero).

gpiozero olayları kendi thread'inde gelir; burada bir kuyruğa yazılır,
ana döngü poll() ile alıp Action'a çevirir. Uzun basma klavyedekiyle
aynı: tık bırakınca SELECT, 0.5 sn basılı kalınca HOLD.

Pin numaraları hw/pins.py'de. PC'de bu dosya kullanılmaz; testte
gpiozero olmadan press()/release()/rotate() elle çağrılabilir.
"""

from __future__ import annotations

import queue
import time
from typing import Optional

from ..input import HOLD_TIME, Action
from . import pins


class GpioInput:
    def __init__(self, use_gpio: bool = True) -> None:
        self.events: queue.Queue = queue.Queue()
        self._select_down: Optional[float] = None
        self._held = False
        self._devices = []
        if use_gpio:
            self._setup()

    def _setup(self) -> None:
        from gpiozero import Button, RotaryEncoder

        enc = RotaryEncoder(pins.ENCODER_A, pins.ENCODER_B, max_steps=0, bounce_time=None)
        forward, back = (Action.UP, Action.DOWN) if pins.ENCODER_INVERT else (Action.DOWN, Action.UP)
        enc.when_rotated_clockwise = lambda: self.rotate(forward)
        enc.when_rotated_counter_clockwise = lambda: self.rotate(back)
        self._devices.append(enc)

        click = Button(pins.ENCODER_BUTTON, pull_up=True, bounce_time=0.02)
        click.when_pressed = lambda: self.press(Action.SELECT)
        click.when_released = lambda: self.release(Action.SELECT)
        self._devices.append(click)

        for pin, action in pins.BUTTONS.items():
            b = Button(pin, pull_up=True, bounce_time=0.03)
            b.when_pressed = lambda action=action: self.press(action)
            self._devices.append(b)

    # -- gpiozero thread'inden çağrılanlar ---------------------------------------

    def rotate(self, action: Action) -> None:
        self.events.put(("tap", action, time.monotonic()))

    def press(self, action: Action) -> None:
        self.events.put(("down", action, time.monotonic()))

    def release(self, action: Action) -> None:
        self.events.put(("up", action, time.monotonic()))

    # -- ana döngü -----------------------------------------------------------------

    def poll(self, now: Optional[float] = None) -> list[Action]:
        now = time.monotonic() if now is None else now
        actions: list[Action] = []
        while True:
            try:
                kind, action, stamp = self.events.get_nowait()
            except queue.Empty:
                break
            if action is Action.SELECT:
                if kind == "down" and self._select_down is None:
                    self._select_down, self._held = stamp, False
                elif kind == "up" and self._select_down is not None:
                    if not self._held:
                        actions.append(Action.SELECT)
                    self._select_down = None
            elif kind in ("tap", "down"):
                actions.append(action)
        if self._select_down is not None and not self._held and now - self._select_down >= HOLD_TIME:
            self._held = True
            actions.append(Action.HOLD)
        return actions

    def close(self) -> None:
        for d in self._devices:
            try:
                d.close()
            except Exception:
                pass
