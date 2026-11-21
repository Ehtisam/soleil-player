"""Kronometre ve zamanlayıcı. Ekranlarından çıkınca da çalışmaya devam
ederler (App.tick her karede ilerletir); zamanlayıcı bitince her ekranda
bildirim çıkar."""

from __future__ import annotations

from .lang import _

# Zamanlayıcıda encoder ile seçilen süreler (saniye)
TIMER_STEPS = (30, 60, 120, 180, 300, 600, 900, 1200, 1500, 1800, 2700, 3600, 5400, 7200)


def clock_text(seconds: float, cs: bool = False) -> str:
    """01:05, 1:02:03; cs=True ise salise de: 01:05.37"""
    total = int(seconds)
    h, m, s = total // 3600, total // 60 % 60, total % 60
    text = f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"
    if cs:
        text += f".{int(seconds * 100) % 100:02d}"
    return text


def duration_label(seconds: int) -> str:
    if seconds < 60:
        return _("{n} SN").format(n=seconds)
    if seconds % 3600 == 0:
        return _("{n} SA").format(n=seconds // 3600)
    if seconds > 3600:
        return _("{n} SA").format(n=seconds // 3600) + " " + _("{n} DK").format(n=seconds // 60 % 60)
    return _("{n} DK").format(n=seconds // 60)


class Stopwatch:
    def __init__(self) -> None:
        self.elapsed = 0.0
        self.running = False
        self.laps: list[float] = []     # her turun bittiği an (toplam süre)

    def toggle(self) -> None:
        self.running = not self.running

    def lap(self) -> None:
        if self.running:
            self.laps.append(self.elapsed)

    def reset(self) -> None:
        self.running = False
        self.elapsed = 0.0
        self.laps.clear()

    def update(self, dt: float) -> None:
        if self.running:
            self.elapsed += dt


class CountdownTimer:
    def __init__(self) -> None:
        self.duration = 300
        self.remaining = 300.0
        self.running = False

    @property
    def started(self) -> bool:
        """Çalışıyor ya da yarıda duraklatılmış."""
        return self.running or self.remaining < self.duration

    def adjust(self, step: int) -> None:
        """Süreyi bir sonraki/önceki adıma getirir (sadece başlamamışken)."""
        if self.started:
            return
        steps = list(TIMER_STEPS)
        i = steps.index(self.duration) if self.duration in steps else 4
        self.duration = steps[max(0, min(len(steps) - 1, i + step))]
        self.remaining = float(self.duration)

    def toggle(self) -> None:
        if self.remaining <= 0:
            self.reset()
        self.running = not self.running

    def reset(self) -> None:
        self.running = False
        self.remaining = float(self.duration)

    def update(self, dt: float) -> bool:
        """Süre o karede bittiyse True."""
        if not self.running:
            return False
        self.remaining -= dt
        if self.remaining <= 0:
            self.remaining = 0.0
            self.running = False
            return True
        return False
