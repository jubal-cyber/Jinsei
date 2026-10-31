"""Motion helpers.

Principles (Apple, 'Designing Fluid Interfaces'):
  * Every animation starts from the value currently on screen, never the target,
    so it can be interrupted and reversed at any instant.
  * Default curve is critically damped (no overshoot); bounce is for momentum.
  * Reduced motion gets short cross-fades instead of slides.
"""
from __future__ import annotations

import sys

from PySide6.QtCore import QEasingCurve, QObject, QPoint, QPropertyAnimation, QTimer, QVariantAnimation, Signal
from PySide6.QtWidgets import QGraphicsOpacityEffect, QWidget


def reduced_motion() -> bool:
    """True when Windows has 'Animation effects' turned off."""
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        flag = ctypes.c_int(1)
        ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(flag), 0)  # SPI_GETCLIENTAREAANIMATION
        return bool(ok) and not flag.value
    except Exception:
        return False


class Animated(QObject):
    """A float that glides toward a target, restarting from where it currently is."""

    changed = Signal(float)
    settled = Signal(float)

    def __init__(self, value: float = 0.0, duration: int = 240,
                 curve: QEasingCurve.Type = QEasingCurve.Type.OutCubic, parent: QObject | None = None):
        super().__init__(parent)
        self._value = float(value)
        self._target = float(value)
        self._duration = duration
        self._restarting = False
        self._anim = QVariantAnimation(self)
        self._anim.setEasingCurve(QEasingCurve(curve))
        self._anim.valueChanged.connect(self._on_value)
        self._anim.finished.connect(self._on_finished)

    @property
    def value(self) -> float:
        return self._value

    @property
    def target(self) -> float:
        return self._target

    def to(self, target: float, duration: int | None = None) -> None:
        target = float(target)
        self._restarting = True
        self._anim.stop()
        self._restarting = False
        self._target = target
        if abs(target - self._value) < 1e-4:
            self._value = target
            self.changed.emit(self._value)
            self.settled.emit(self._value)
            return
        self._anim.setStartValue(self._value)  # presentation value, not the old target
        self._anim.setEndValue(target)
        self._anim.setDuration(1 if reduced_motion() else int(duration or self._duration))
        self._anim.start()

    def jump(self, value: float) -> None:
        self._restarting = True
        self._anim.stop()
        self._restarting = False
        self._value = self._target = float(value)
        self.changed.emit(self._value)

    def _on_value(self, v) -> None:
        self._value = float(v)
        self.changed.emit(self._value)

    def _on_finished(self) -> None:
        if self._restarting:
            return
        self._value = self._target
        self.changed.emit(self._value)
        self.settled.emit(self._value)


def fade_in(widget: QWidget, ms: int = 220) -> None:
    """Cross-fade a widget in. Safe to call repeatedly; the newest call wins."""
    token = getattr(widget, "_fade_token", 0) + 1
    widget._fade_token = token  # type: ignore[attr-defined]
    effect = QGraphicsOpacityEffect(widget)
    effect.setOpacity(0.0)
    widget.setGraphicsEffect(effect)
    anim = QPropertyAnimation(effect, b"opacity", effect)
    anim.setDuration(max(1, int(ms)))
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))

    def cleanup() -> None:
        def remove() -> None:
            try:
                if getattr(widget, "_fade_token", None) == token:
                    widget.setGraphicsEffect(None)
            except RuntimeError:  # widget already deleted
                pass

        QTimer.singleShot(0, remove)  # never delete an effect from inside its own signal

    anim.finished.connect(cleanup)
    anim.start()


def shake(widget: QWidget, amplitude: int = 10) -> None:
    """The 'no' gesture: a short horizontal wobble that settles back in place."""
    origin = widget.pos()
    anim = QPropertyAnimation(widget, b"pos", widget)
    anim.setDuration(380)
    for t, dx in ((0.0, 0), (0.14, -1.0), (0.3, 0.9), (0.46, -0.7), (0.62, 0.5), (0.8, -0.2), (1.0, 0)):
        anim.setKeyValueAt(t, origin + QPoint(int(dx * amplitude), 0))
    anim.setEasingCurve(QEasingCurve(QEasingCurve.Type.Linear))
    anim.finished.connect(lambda: widget.move(origin))
    anim.start(QPropertyAnimation.DeletionPolicy.DeleteWhenStopped)
