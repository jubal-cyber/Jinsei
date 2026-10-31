"""Settings page: inset grouped lists in the style of iOS / macOS Settings."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from . import auth as auth_mod
from . import biometrics, icons
from .bio_runner import runner
from .theme import font_for, theme
from .widgets import Text, draw_text


class SettingsRow(QWidget):
    H = 60
    activated = Signal()

    def __init__(self, icon_name: str, tint: str, title: str, subtitle: str = "", value: str = "",
                 value_tone: str = "text2", clickable: bool = False, chevron: bool = False,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self._icon, self._tint = icon_name, tint
        self._title, self._subtitle = title, subtitle
        self._value, self._value_tone = value, value_tone
        self._clickable, self._chevron = clickable, chevron
        self._hover = False
        self._down = False
        self.setFixedHeight(self.H)
        self.setMouseTracking(True)
        self.set_clickable(clickable)

    def set_clickable(self, clickable: bool) -> None:
        self._clickable = clickable
        self.setCursor(Qt.CursorShape.PointingHandCursor if clickable else Qt.CursorShape.ArrowCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus if clickable else Qt.FocusPolicy.NoFocus)
        self.update()

    def set_state(self, subtitle: str, value: str, value_tone: str, clickable: bool, tooltip: str = "") -> None:
        self._subtitle, self._value, self._value_tone = subtitle, value, value_tone
        self.setToolTip(tooltip)
        self.set_clickable(clickable)

    def enterEvent(self, e) -> None:
        self._hover = True
        self.update()
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hover = False
        self._down = False
        self.update()
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if self._clickable and e.button() == Qt.MouseButton.LeftButton:
            self._down = True
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        was = self._down
        self._down = False
        self.update()
        if was and self.rect().contains(e.position().toPoint()):
            self.activated.emit()

    def keyPressEvent(self, e) -> None:
        if self._clickable and e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit()
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        dpr = self.devicePixelRatioF()
        area = QRectF(6, 3, self.width() - 12, self.height() - 6)
        p.setPen(Qt.PenStyle.NoPen)
        if self._clickable and self._down:
            p.setBrush(theme.color("fill_press"))
            p.drawRoundedRect(area, 9, 9)
        elif self._clickable and self._hover:
            p.setBrush(theme.color("fill"))
            p.drawRoundedRect(area, 9, 9)
        if self.hasFocus():
            p.setPen(QPen(theme.color("accent_ring"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(area, 9, 9)

        tile = QRectF(18, (self.height() - 32) / 2, 32, 32)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.tint(self._tint))
        p.drawRoundedRect(tile, 8, 8)
        p.drawPixmap(QPointF(tile.center().x() - 9, tile.center().y() - 9),
                     icons.pixmap(self._icon, 18, QColor(255, 255, 255), dpr, 1.8))

        right = self.width() - (44 if self._chevron else 22)
        value_w = 0
        if self._value:
            vf = font_for("body", QFont.Weight.Medium if self._value_tone == "accent" else QFont.Weight.Normal)
            value_w = QFontMetrics(vf).horizontalAdvance(self._value)
            p.setFont(vf)
            p.setPen(theme.color({"accent": "accent", "success": "success", "text3": "text3"}.get(self._value_tone, "text2")))
            draw_text(p, QRectF(right - value_w - 2, 0, value_w + 4, self.height()), self._value,
                      Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        if self._chevron:
            p.drawPixmap(QPointF(self.width() - 18 - 14, self.height() / 2 - 7),
                         icons.pixmap("chevron", 14, theme.color("text3"), dpr, 2.0))

        text_w = max(60, right - value_w - 12 - 66)
        title_font = font_for("body", QFont.Weight.Medium)
        p.setFont(title_font)
        p.setPen(theme.color("text"))
        if self._subtitle:
            draw_text(p, QRectF(66, 9, text_w, 22), self._title)
            sf = font_for("caption")
            p.setFont(sf)
            p.setPen(theme.color("text2"))
            sub = QFontMetrics(sf).elidedText(self._subtitle, Qt.TextElideMode.ElideRight, int(text_w))
            draw_text(p, QRectF(66, 30, text_w, 20), sub)
        else:
            draw_text(p, QRectF(66, 0, text_w, self.height()), self._title)


class SettingsGroup(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0, 0, 0, 0)
        self._lay.setSpacing(0)
        self._rows: list[SettingsRow] = []

    def add_row(self, row: SettingsRow) -> SettingsRow:
        self._rows.append(row)
        self._lay.addWidget(row)
        return row

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(theme.color("sep"), 1))
        p.setBrush(theme.color("surface"))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 14, 14)
        for row in self._rows[:-1]:
            y = row.geometry().bottom() + 0.5
            p.drawLine(QPointF(66, y), QPointF(self.width() - 1, y))


class SettingsPage(QScrollArea):
    change_password_requested = Signal()

    def __init__(self, auth: auth_mod.AuthStore, notify: Callable[[str, str], None], parent: QWidget | None = None):
        super().__init__(parent)
        self.auth = auth
        self._notify = notify
        self._token: int | None = None
        self.setWidgetResizable(True)
        self.setFrameShape(QScrollArea.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.viewport().setAutoFillBackground(False)

        container = QWidget()
        outer = QVBoxLayout(container)
        outer.setContentsMargins(32, 12, 32, 40)
        inner = QWidget()
        inner.setMaximumWidth(620)
        col = QVBoxLayout(inner)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        outer.addWidget(inner, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        outer.addStretch()

        header = Text("Security", "caption", "tertiary")
        header.setContentsMargins(14, 0, 0, 7)
        col.addWidget(header)
        group = SettingsGroup()
        self.fingerprint_row = group.add_row(SettingsRow("fingerprint", "Security", "Fingerprint"))
        self.password_row = group.add_row(
            SettingsRow("key", "Key", "Change Password", clickable=True, chevron=True))
        col.addWidget(group)
        footer = Text("Your fingerprint is handled by Windows Hello and never leaves this PC. "
                      "Jinsei only remembers that fingerprint lock is on.", "caption", "tertiary", wrap=True)
        footer.setContentsMargins(14, 8, 14, 0)
        col.addWidget(footer)

        self.fingerprint_row.activated.connect(self._set_up_fingerprint)
        self.password_row.activated.connect(self.change_password_requested.emit)
        self.setWidget(container)

    def refresh(self) -> None:
        runner().cancel(self._token)
        self._token = None
        if self.auth.biometric_enabled():
            self.fingerprint_row.set_state("Asked every time you open Jinsei", "On", "success", False)
            return
        self.fingerprint_row.set_state("", "Checking\u2026", "text3", False)
        self._token = runner().run(biometrics.check_availability, callback=self._on_availability)

    def _on_availability(self, res: biometrics.BioResult) -> None:
        self._token = None
        if res.status in ("available", "busy"):
            self.fingerprint_row.set_state("Not set up", "Set Up", "accent", True)
        else:
            self.fingerprint_row.set_state(res.message or "Not available on this PC", "Unavailable", "text3", False,
                                           tooltip=res.message)

    def _set_up_fingerprint(self) -> None:
        self.fingerprint_row.set_state("Waiting for Windows Hello\u2026", "", "text2", False)
        runner().cancel(self._token)
        self._token = runner().run(biometrics.verify, "Register your fingerprint for Jinsei",
                                   callback=self._on_enrolled)

    def _on_enrolled(self, res: biometrics.BioResult) -> None:
        self._token = None
        if res.status == "verified":
            try:
                self.auth.enable_biometric()
            except OSError as exc:
                self._notify(f"Couldn\u2019t save your settings: {exc}", "error")
            else:
                self._notify("Fingerprint turned on", "success")
        else:
            self._notify(res.message or "Fingerprint wasn\u2019t confirmed.", "error")
        self.refresh()
