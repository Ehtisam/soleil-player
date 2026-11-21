"""Girdiler: cihazdaki encoder ve 5 buton.

Ekranlar klavyeyi ya da GPIO'yu bilmez, sadece Action alır. Pi'de
butonları okuyan kısım da aynı Action'ları üretecek.

Klavye karşılıkları (PC'de geliştirme için):
  Yukarı / Aşağı, fare tekerleği : encoder çevirme
  Enter, Sağ ok                  : encoder tıklama (basılı tutmak: uzun basma)
  1 / 2                          : Sol 1 / Sol 2
  3, Esc, Backspace, Sol ok      : Sol 3 (geri)
  4 / 5                          : Üst 1 / Üst 2

Tuşların işaretleri Göktürk harfleri (ui/glyphs.py): Sol 1 S, Sol 2 O,
Sol 3 L (kalın), Üst 1 E, Üst 2 İ, encoder L (ince); birlikte SOLEİL.

Encoder tıklaması tuş bırakılınca gelir; 0.5 saniye basılı tutulursa
tıklama yerine HOLD (uzun basma) gelir.
"""

from __future__ import annotations

from enum import Enum, auto
from typing import Optional

import pygame


class Action(Enum):
    UP = auto()        # encoder geri
    DOWN = auto()      # encoder ileri
    SELECT = auto()    # encoder tıklama
    HOLD = auto()      # encoder uzun basma
    LEFT1 = auto()
    LEFT2 = auto()
    BACK = auto()      # Sol 3
    TOP1 = auto()
    TOP2 = auto()


HOLD_TIME = 0.5

SELECT_KEYS = {pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_RIGHT}

KEYMAP = {
    pygame.K_UP: Action.UP,
    pygame.K_DOWN: Action.DOWN,
    pygame.K_1: Action.LEFT1,
    pygame.K_2: Action.LEFT2,
    pygame.K_3: Action.BACK,
    pygame.K_ESCAPE: Action.BACK,
    pygame.K_BACKSPACE: Action.BACK,
    pygame.K_LEFT: Action.BACK,
    pygame.K_4: Action.TOP1,
    pygame.K_5: Action.TOP2,
}


class KeyboardInput:
    def __init__(self) -> None:
        self._select_down: Optional[float] = None   # tıklama tuşuna basıldığı an
        self._held = False                           # bu basışta HOLD gönderildi mi

    def from_event(self, event: pygame.event.Event, now: float) -> list[Action]:
        if event.type == pygame.KEYDOWN and event.key in SELECT_KEYS:
            if self._select_down is None:            # tuş tekrarlarını yok say
                self._select_down, self._held = now, False
            return []
        if event.type == pygame.KEYUP and event.key in SELECT_KEYS:
            was_down, held = self._select_down, self._held
            self._select_down = None
            return [Action.SELECT] if was_down is not None and not held else []
        if event.type == pygame.KEYDOWN and event.key in KEYMAP:
            return [KEYMAP[event.key]]
        if event.type == pygame.MOUSEWHEEL and event.y:
            step = Action.UP if event.y > 0 else Action.DOWN
            return [step] * abs(event.y)
        return []

    def update(self, now: float) -> list[Action]:
        """Basılı tutulan tıklama tuşunu takip eder."""
        if self._select_down is not None and not self._held and now - self._select_down >= HOLD_TIME:
            self._held = True
            return [Action.HOLD]
        return []
