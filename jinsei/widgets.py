"""Reusable widgets: type, buttons, segmented control, sidebar items, file tiles, sheets, toasts."""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (QAction, QBrush, QColor, QFont, QFontMetrics, QImageReader, QPainter,
                           QPainterPath, QPen, QPixmap, QTextOption)
from PySide6.QtWidgets import (QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QPushButton, QVBoxLayout, QWidget)

from . import icons, library
from .motion import Animated, shake
from .theme import font_for, theme

ALIGN_LEFT_V = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
ALIGN_CENTER = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter


def draw_text(p: QPainter, rect: QRectF, text: str, align=ALIGN_LEFT_V, wrap: bool = False) -> None:
    opt = QTextOption(align)
    opt.setWrapMode(QTextOption.WrapMode.WordWrap if wrap else QTextOption.WrapMode.NoWrap)
    p.drawText(rect, text, opt)


# --------------------------------------------------------------------------------------
# Type, buttons, fields
# --------------------------------------------------------------------------------------
def set_tone(widget: QWidget, tone: str) -> None:
    widget.setProperty("tone", tone)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class Text(QLabel):
    def __init__(self, text: str = "", role: str = "body", tone: str = "primary",
                 center: bool = False, wrap: bool = False, parent: QWidget | None = None):
        super().__init__(text, parent)
        self.setFont(font_for(role))
        self.setProperty("tone", tone)
        self.setWordWrap(wrap)
        if center:
            self.setAlignment(ALIGN_CENTER)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)


def make_button(text: str, kind: str = "primary", icon: str | None = None, large: bool = False,
                parent: QWidget | None = None) -> QPushButton:
    b = QPushButton(text, parent)
    b.setProperty("kind", kind)
    b.setProperty("size", "lg" if large else "md")
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    b.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # focus ring only for keyboard users
    if icon:
        color = theme.color("on_accent") if kind in ("primary", "danger") else theme.color("text")
        b.setIcon(icons.icon(icon, 16, color, 2.0))
        b.setIconSize(QSize(16, 16))
    return b


def set_invalid(widget: QWidget, invalid: bool) -> None:
    widget.setProperty("invalid", "true" if invalid else "false")
    widget.style().unpolish(widget)
    widget.style().polish(widget)


class PasswordField(QLineEdit):
    def __init__(self, placeholder: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setPlaceholderText(placeholder)
        self.setEchoMode(QLineEdit.EchoMode.Password)
        self.setMaxLength(128)
        self._reveal = QAction(self)
        self._reveal.setIcon(icons.icon("eye", 18, theme.color("text3")))
        self._reveal.setToolTip("Show password")
        self._reveal.triggered.connect(self._toggle)
        self.addAction(self._reveal, QLineEdit.ActionPosition.TrailingPosition)
        self.textChanged.connect(lambda _t: set_invalid(self, False))

    def _toggle(self) -> None:
        showing = self.echoMode() == QLineEdit.EchoMode.Normal
        self.setEchoMode(QLineEdit.EchoMode.Password if showing else QLineEdit.EchoMode.Normal)
        self._reveal.setIcon(icons.icon("eye" if showing else "eye_off", 18, theme.color("text3")))
        self._reveal.setToolTip("Show password" if showing else "Hide password")


class Hint(QWidget):
    """One line of inline validation: an empty circle that becomes a green check."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._text = text
        self._ok = False
        self.setFixedHeight(22)

    def set_ok(self, ok: bool) -> None:
        if ok != self._ok:
            self._ok = ok
            self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = theme.color("success") if self._ok else theme.color("text3")
        p.drawPixmap(QPointF(0, 3), icons.pixmap("check_circle" if self._ok else "circle", 16, color,
                                                 self.devicePixelRatioF(), 1.9))
        p.setFont(font_for("caption"))
        p.setPen(theme.color("text2") if self._ok else theme.color("text3"))
        draw_text(p, QRectF(24, 0, self.width() - 24, self.height()), self._text)


# --------------------------------------------------------------------------------------
# Segmented control (grid / list)
# --------------------------------------------------------------------------------------
class Segmented(QWidget):
    changed = Signal(int)

    def __init__(self, icon_names: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._icons = icon_names
        self._index = 0
        self._thumb = Animated(0.0, 240, parent=self)
        self._thumb.changed.connect(lambda _v: self.update())
        self.setFixedSize(40 * len(icon_names) + 4, 32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def index(self) -> int:
        return self._index

    def set_index(self, i: int, emit: bool = False) -> None:
        i = max(0, min(len(self._icons) - 1, i))
        if i == self._index:
            return
        self._index = i
        self._thumb.to(i)
        if emit:
            self.changed.emit(i)

    def mousePressEvent(self, e) -> None:  # respond on press, not release
        seg = (self.width() - 4) / len(self._icons)
        self.set_index(int((e.position().x() - 2) // seg), emit=True)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.color("fill"))
        p.drawRoundedRect(QRectF(self.rect()), 9, 9)
        seg = (self.width() - 4) / len(self._icons)
        thumb = QRectF(2 + self._thumb.value * seg, 2, seg, self.height() - 4)
        p.setBrush(QColor(0, 0, 0, 22))
        p.drawRoundedRect(thumb.translated(0, 1), 7, 7)
        p.setBrush(theme.color("surface"))
        p.drawRoundedRect(thumb, 7, 7)
        for i, name in enumerate(self._icons):
            active = abs(self._thumb.value - i) < 0.5
            pm = icons.pixmap(name, 16, theme.color("text" if active else "text2"), self.devicePixelRatioF(), 1.9)
            p.drawPixmap(QPointF(2 + seg * (i + 0.5) - 8, self.height() / 2 - 8), pm)


# --------------------------------------------------------------------------------------
# Sidebar item
# --------------------------------------------------------------------------------------
class SideItem(QWidget):
    pressed = Signal(str)

    def __init__(self, key: str, label: str, icon_name: str, tint_key: str,
                 selectable: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self.key, self._label, self._icon, self._tint = key, label, icon_name, tint_key
        self._selectable = selectable
        self._checked = False
        self._down = False
        self._count: int | None = None
        self._hover = Animated(0.0, 150, parent=self)
        self._hover.changed.connect(lambda _v: self.update())
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)

    def set_checked(self, checked: bool) -> None:
        self._checked = checked
        self.update()

    def set_count(self, count: int | None) -> None:
        self._count = count
        self.update()

    def enterEvent(self, e) -> None:
        self._hover.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hover.to(0.0)
        super().leaveEvent(e)

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._down = True
            self.update()
            self.pressed.emit(self.key)  # commit on press: the sidebar should feel instant

    def mouseReleaseEvent(self, _e) -> None:
        self._down = False
        self.update()

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.pressed.emit(self.key)
        else:
            super().keyPressEvent(e)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tint = theme.tint(self._tint)
        rect = QRectF(self.rect())
        if self._checked:
            bg = QColor(tint)
            bg.setAlpha(46 if theme.dark else 36)
        elif self._down:
            bg = theme.color("fill_press")
        else:
            bg = theme.color_scaled("fill_hover", self._hover.value)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(rect, 9, 9)
        if self.hasFocus():
            p.setPen(QPen(theme.color("accent_ring"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 9, 9)
        p.drawPixmap(QPointF(12, (self.height() - 19) / 2),
                     icons.pixmap(self._icon, 19, tint, self.devicePixelRatioF(), 1.7))
        f = font_for("body", QFont.Weight.DemiBold if self._checked else QFont.Weight.Normal)
        p.setFont(f)
        p.setPen(theme.color("text"))
        draw_text(p, QRectF(42, 0, self.width() - 80, self.height()), self._label)
        if self._count is not None:
            p.setFont(font_for("caption"))
            p.setPen(theme.color("text3"))
            draw_text(p, QRectF(self.width() - 48, 0, 36, self.height()), str(self._count),
                      Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


# --------------------------------------------------------------------------------------
# Thumbnails (loaded one at a time so scrolling and typing never stall)
# --------------------------------------------------------------------------------------
class _ThumbLoader(QObject):
    loaded = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._cache: dict[tuple, QPixmap | bool] = {}
        self._queue: list[tuple] = []
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._step)

    def get(self, item: library.Item, w: int, h: int, dpr: float) -> QPixmap | None:
        key = (str(item.path), item.mtime, w, h, round(dpr, 2))
        hit = self._cache.get(key)
        if isinstance(hit, QPixmap):
            return hit
        if hit is None:
            self._cache[key] = False  # pending / failed marker, so we only queue once
            self._queue.append(key)
            if not self._timer.isActive():
                self._timer.start(1)
        return None

    def _step(self) -> None:
        if not self._queue:
            return
        key = self._queue.pop(0)
        path, _mtime, w, h, dpr = key
        pm = self._load(path, w, h, dpr)
        if pm is not None:
            if len(self._cache) > 600:
                self._cache.clear()
            self._cache[key] = pm
            self.loaded.emit()
        if self._queue:
            self._timer.start(1)

    @staticmethod
    def _load(path: str, w: int, h: int, dpr: float) -> QPixmap | None:
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        img = reader.read()
        if img.isNull():
            return None
        pw, ph = max(1, int(w * dpr)), max(1, int(h * dpr))
        img = img.scaled(pw, ph, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                         Qt.TransformationMode.SmoothTransformation)
        img = img.copy((img.width() - pw) // 2, (img.height() - ph) // 2, pw, ph)
        pm = QPixmap.fromImage(img)
        pm.setDevicePixelRatio(dpr)
        return pm


_loader: _ThumbLoader | None = None


def thumbs() -> _ThumbLoader:
    global _loader
    if _loader is None:
        _loader = _ThumbLoader()
    return _loader


def styled_menu(parent: QWidget) -> QMenu:
    menu = QMenu(parent)
    menu.setWindowFlags(menu.windowFlags() | Qt.WindowType.FramelessWindowHint | Qt.WindowType.NoDropShadowWindowHint)
    menu.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
    return menu


def _paint_trash_chip(p: QPainter, rect: QRectF, hot: bool, opacity: float, on_photo: bool, dpr: float) -> None:
    if opacity <= 0.01:
        return
    p.save()
    p.setOpacity(opacity)
    p.setPen(Qt.PenStyle.NoPen)
    if hot:
        p.setBrush(theme.color("danger"))
        glyph = QColor(255, 255, 255)
    elif on_photo:
        p.setBrush(QColor(0, 0, 0, 120))
        glyph = QColor(255, 255, 255)
    else:
        p.setBrush(theme.color("fill_hover"))
        glyph = theme.color("text2")
    p.drawEllipse(rect)
    p.drawPixmap(QPointF(rect.center().x() - 8, rect.center().y() - 8), icons.pixmap("trash", 16, glyph, dpr, 1.8))
    p.restore()


def _open_menu(widget: QWidget, item: library.Item, global_pos, on_open, on_delete) -> None:
    menu = styled_menu(widget)
    menu.addAction("Open").triggered.connect(on_open)
    menu.addSeparator()
    menu.addAction("Delete\u2026").triggered.connect(on_delete)
    menu.exec(global_pos)


# --------------------------------------------------------------------------------------
# File tile (grid) and row (list)
# --------------------------------------------------------------------------------------
class FileTile(QWidget):
    W, H = 176, 190
    PREVIEW_H = 118
    open_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, item: library.Item, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self._hover = Animated(0.0, 160, parent=self)
        self._press = Animated(0.0, 120, parent=self)
        self._hover.changed.connect(lambda _v: self.update())
        self._press.changed.connect(lambda _v: self.update())
        self._trash_hot = False
        self._down_on_trash = False
        self.setFixedSize(self.W, self.H)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip(item.name)
        thumbs().loaded.connect(self.update)

    def _inner(self) -> QRectF:
        return QRectF(8, 6, self.width() - 16, self.height() - 14)

    def _trash_rect(self) -> QRectF:
        i = self._inner()
        return QRectF(i.right() - 36, i.top() + 8, 28, 28)

    # events
    def enterEvent(self, e) -> None:
        self._hover.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hover.to(0.0)
        if self._trash_hot:
            self._trash_hot = False
            self.update()
        super().leaveEvent(e)

    def mouseMoveEvent(self, e) -> None:
        hot = self._trash_rect().contains(e.position())
        if hot != self._trash_hot:
            self._trash_hot = hot
            self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._down_on_trash = self._trash_rect().contains(e.position())
            if not self._down_on_trash:
                self._press.to(1.0)

    def mouseReleaseEvent(self, e) -> None:
        self._press.to(0.0)
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            if self._down_on_trash and self._trash_rect().contains(e.position()):
                self.delete_requested.emit(self.item)
            elif not self._down_on_trash:
                self.open_requested.emit(self.item)
        self._down_on_trash = False

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.open_requested.emit(self.item)
        elif e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit(self.item)
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e) -> None:
        _open_menu(self, self.item, e.globalPos(),
                   lambda: self.open_requested.emit(self.item), lambda: self.delete_requested.emit(self.item))

    # painting
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        dpr = self.devicePixelRatioF()
        hover, press = self._hover.value, self._press.value
        inner = self._inner()
        scale = 1.0 - 0.03 * press
        c = inner.center()
        p.translate(c)
        p.scale(scale, scale)
        p.translate(-c.x(), -c.y())

        p.setPen(Qt.PenStyle.NoPen)
        for grow, a in ((6, 5), (3.5, 8), (1.5, 11)):
            alpha = int(a * (1.0 + hover * 0.9) * (1.7 if theme.dark else 0.8))
            p.setBrush(QColor(0, 0, 0, alpha))
            r = inner.adjusted(-grow, -grow + 3, grow, grow + 3)
            p.drawRoundedRect(r, 14 + grow, 14 + grow)

        path = QPainterPath()
        path.addRoundedRect(inner, 14, 14)
        p.fillPath(path, QBrush(theme.color("surface")))
        p.save()
        p.setClipPath(path)
        preview = QRectF(inner.x(), inner.y(), inner.width(), self.PREVIEW_H)
        on_photo = self._paint_preview(p, preview, dpr)
        p.restore()
        p.setPen(QPen(theme.color("sep"), 1))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(inner, 14, 14)

        fm_font = font_for("headline")
        p.setFont(fm_font)
        p.setPen(theme.color("text"))
        name = QFontMetrics(fm_font).elidedText(self.item.name, Qt.TextElideMode.ElideMiddle, int(inner.width() - 24))
        p.drawText(QPointF(inner.x() + 12, preview.bottom() + 23), name)
        p.setFont(font_for("caption"))
        p.setPen(theme.color("text2"))
        p.drawText(QPointF(inner.x() + 12, preview.bottom() + 42), self.item.meta())

        _paint_trash_chip(p, self._trash_rect(), self._trash_hot, hover, on_photo, dpr)
        if self.hasFocus():
            p.setPen(QPen(theme.color("accent_ring"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(inner.adjusted(-1, -1, 1, 1), 15, 15)

    def _paint_preview(self, p: QPainter, rect: QRectF, dpr: float) -> bool:
        """Draws the top area of the tile. Returns True when a photo is behind the trash chip."""
        section = self.item.section
        tint = theme.tint(section)
        if section == "Images":
            pm = thumbs().get(self.item, int(rect.width()), int(rect.height()), dpr)
            if pm is not None:
                p.drawPixmap(rect.topLeft(), pm)
                return True
            p.fillRect(rect, theme.color("fill"))
            glyph = icons.pixmap("image", 40, theme.color("text3"), dpr, 1.4)
            p.drawPixmap(QPointF(rect.center().x() - 20, rect.center().y() - 20), glyph)
            return False
        if section == "Documents":
            bg = QColor(tint)
            bg.setAlpha(46 if theme.dark else 24)
            p.fillRect(rect, bg)
            p.drawPixmap(QPointF(rect.center().x() - 24, rect.center().y() - 28), icons.pixmap("doc", 48, tint, dpr, 1.4))
            ext = (self.item.ext or "FILE")[:5]
            f = font_for("caption", QFont.Weight.DemiBold)
            p.setFont(f)
            w = QFontMetrics(f).horizontalAdvance(ext) + 14
            pill = QRectF(rect.left() + 10, rect.bottom() - 28, w, 18)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(tint)
            p.drawRoundedRect(pill, 9, 9)
            p.setPen(QColor(255, 255, 255))
            draw_text(p, pill, ext, ALIGN_CENTER)
            return False
        p.fillRect(rect, theme.color("surface_alt"))
        body = library.text_preview(self.item, 220)
        text = body or "Empty note"
        p.setFont(font_for("caption"))
        p.setPen(theme.color("text2" if body else "text3"))
        p.save()
        p.setClipRect(rect)
        draw_text(p, rect.adjusted(14, 12, -14, -8), text, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, True)
        p.restore()
        return False


class FileRow(QWidget):
    H = 60
    open_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, item: library.Item, parent: QWidget | None = None):
        super().__init__(parent)
        self.item = item
        self._hover = Animated(0.0, 140, parent=self)
        self._hover.changed.connect(lambda _v: self.update())
        self._trash_hot = False
        self._down = False
        self._down_on_trash = False
        self.setFixedHeight(self.H)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        thumbs().loaded.connect(self.update)

    def _trash_rect(self) -> QRectF:
        return QRectF(self.width() - 18 - 28, (self.height() - 28) / 2, 28, 28)

    def enterEvent(self, e) -> None:
        self._hover.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e) -> None:
        self._hover.to(0.0)
        self._trash_hot = False
        self.update()
        super().leaveEvent(e)

    def mouseMoveEvent(self, e) -> None:
        hot = self._trash_rect().contains(e.position())
        if hot != self._trash_hot:
            self._trash_hot = hot
            self.update()

    def mousePressEvent(self, e) -> None:
        if e.button() == Qt.MouseButton.LeftButton:
            self._down_on_trash = self._trash_rect().contains(e.position())
            self._down = not self._down_on_trash
            self.update()

    def mouseReleaseEvent(self, e) -> None:
        was_down = self._down
        self._down = False
        self.update()
        if e.button() == Qt.MouseButton.LeftButton and self.rect().contains(e.position().toPoint()):
            if self._down_on_trash and self._trash_rect().contains(e.position()):
                self.delete_requested.emit(self.item)
            elif was_down:
                self.open_requested.emit(self.item)
        self._down_on_trash = False

    def keyPressEvent(self, e) -> None:
        if e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.open_requested.emit(self.item)
        elif e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit(self.item)
        else:
            super().keyPressEvent(e)

    def contextMenuEvent(self, e) -> None:
        _open_menu(self, self.item, e.globalPos(),
                   lambda: self.open_requested.emit(self.item), lambda: self.delete_requested.emit(self.item))

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        dpr = self.devicePixelRatioF()
        hover = self._hover.value
        tint = theme.tint(self.item.section)
        area = QRectF(6, 3, self.width() - 12, self.height() - 6)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.color("fill_press") if self._down else theme.color_scaled("fill", hover))
        p.drawRoundedRect(area, 9, 9)
        if self.hasFocus():
            p.setPen(QPen(theme.color("accent_ring"), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRoundedRect(area, 9, 9)

        tile = QRectF(18, (self.height() - 40) / 2, 40, 40)
        path = QPainterPath()
        path.addRoundedRect(tile, 10, 10)
        pm = thumbs().get(self.item, 40, 40, dpr) if self.item.section == "Images" else None
        if pm is not None:
            p.save()
            p.setClipPath(path)
            p.drawPixmap(tile.topLeft(), pm)
            p.restore()
        else:
            bg = QColor(tint)
            bg.setAlpha(60 if theme.dark else 34)
            p.fillPath(path, QBrush(bg))
            glyph = icons.SECTION_ICON[self.item.section]
            p.drawPixmap(QPointF(tile.center().x() - 11, tile.center().y() - 11),
                         icons.pixmap(glyph, 22, tint, dpr, 1.7))

        name_font = font_for("body", QFont.Weight.Medium)
        p.setFont(name_font)
        p.setPen(theme.color("text"))
        right = 80 if hover > 0.01 else 24
        name = QFontMetrics(name_font).elidedText(self.item.name, Qt.TextElideMode.ElideMiddle,
                                                  max(40, self.width() - 70 - right))
        p.drawText(QPointF(70, self.height() / 2 - 2), name)
        p.setFont(font_for("caption"))
        p.setPen(theme.color("text2"))
        p.drawText(QPointF(70, self.height() / 2 + 15), self.item.meta(with_date=True))
        _paint_trash_chip(p, self._trash_rect(), self._trash_hot, hover, False, dpr)


class ItemCollection(QWidget):
    """Lays out tiles (grid) or rows (inset list) by hand so the grid reflows smoothly."""

    MARGIN = 32
    open_requested = Signal(object)
    delete_requested = Signal(object)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._items: list[library.Item] = []
        self._mode = "grid"
        self._widgets: list[QWidget] = []

    def set_items(self, items: list[library.Item], mode: str | None = None) -> None:
        if mode:
            self._mode = mode
        self._items = list(items)
        for w in self._widgets:
            w.hide()
            w.deleteLater()
        self._widgets = []
        cls = FileTile if self._mode == "grid" else FileRow
        for item in self._items:
            w = cls(item, self)
            w.open_requested.connect(self.open_requested.emit)
            w.delete_requested.connect(self.delete_requested.emit)
            w.show()
            self._widgets.append(w)
        self._relayout()
        self.update()

    def resizeEvent(self, e) -> None:
        super().resizeEvent(e)
        self._relayout()

    def _relayout(self) -> None:
        m, w = self.MARGIN, max(self.width(), 1)
        n = len(self._widgets)
        if self._mode == "grid":
            cols = max(1, (w - 2 * m + 16) // FileTile.W)
            for i, wid in enumerate(self._widgets):
                r, c = divmod(i, cols)
                wid.setGeometry(m - 8 + c * FileTile.W, 8 + r * FileTile.H, FileTile.W, FileTile.H)
            rows = -(-n // cols) if n else 0
            total = 8 + rows * FileTile.H + 24
        else:
            for i, wid in enumerate(self._widgets):
                wid.setGeometry(m, 12 + i * FileRow.H, w - 2 * m, FileRow.H)
            total = 12 + n * FileRow.H + 24
        if self.minimumHeight() != total:
            self.setMinimumHeight(total)

    def paintEvent(self, _e) -> None:
        if self._mode != "list" or not self._widgets:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        m, n = self.MARGIN, len(self._widgets)
        card = QRectF(m, 12, self.width() - 2 * m, n * FileRow.H)
        p.setPen(QPen(theme.color("sep"), 1))
        p.setBrush(theme.color("surface"))
        p.drawRoundedRect(card, 14, 14)
        for i in range(1, n):
            y = 12 + i * FileRow.H
            p.drawLine(QPointF(m + 70, y), QPointF(card.right(), y))


# --------------------------------------------------------------------------------------
# Empty state
# --------------------------------------------------------------------------------------
class _TintCircle(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._icon, self._tint = "image", "Images"
        self.setFixedSize(92, 92)

    def configure(self, icon_name: str, tint: str) -> None:
        self._icon, self._tint = icon_name, tint
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        tint = theme.tint(self._tint)
        bg = QColor(tint)
        bg.setAlpha(54 if theme.dark else 30)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawEllipse(QRectF(self.rect()))
        p.drawPixmap(QPointF(self.width() / 2 - 20, self.height() / 2 - 20),
                     icons.pixmap(self._icon, 40, tint, self.devicePixelRatioF(), 1.5))


class EmptyState(QWidget):
    add_clicked = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(40, 0, 40, 60)
        lay.setSpacing(0)
        self._circle = _TintCircle()
        self._title = Text("", "title", center=True)
        self._message = Text("", "body", "secondary", center=True, wrap=True)
        self._message.setMaximumWidth(340)
        self._button = make_button("Add", "primary", "plus", large=True)
        self._button.clicked.connect(self.add_clicked.emit)
        lay.addStretch()
        lay.addWidget(self._circle, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(18)
        lay.addWidget(self._title)
        lay.addSpacing(6)
        lay.addWidget(self._message, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addSpacing(22)
        lay.addWidget(self._button, 0, Qt.AlignmentFlag.AlignHCenter)
        lay.addStretch()

    def configure(self, section: library.Section) -> None:
        self._circle.configure(section.icon, section.key)
        self._title.setText(section.empty_title)
        self._message.setText(section.empty_message)
        self._button.setText(f"Add {section.noun.capitalize()}")


# --------------------------------------------------------------------------------------
# Sheet (modal overlay) and toast
# --------------------------------------------------------------------------------------
class Sheet(QWidget):
    """A card that drops in from the top of the window, over a dimmed scrim.

    It enters and leaves along the same path, and can be dismissed mid-entrance
    without waiting: the progress value always continues from where it is.
    """

    dismissed = Signal()

    def __init__(self, host: QWidget, width: int = 420, dismissable: bool = True):
        super().__init__(host)
        self._host = host
        self._dismissable = dismissable
        self._closing = False
        self._default_action = None
        self._progress = Animated(0.0, 360, parent=self)
        self._progress.changed.connect(self._apply)
        self._progress.settled.connect(self._on_settled)

        self.card = QFrame(self)
        self.card.setObjectName("sheetCard")
        self.card.setFixedWidth(width)
        shadow = QGraphicsDropShadowEffect(self.card)
        shadow.setBlurRadius(64)
        shadow.setOffset(0, 20)
        shadow.setColor(theme.color("shadow"))
        self.card.setGraphicsEffect(shadow)
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(24, 24, 24, 20)
        self.body.setSpacing(0)

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        host.installEventFilter(self)
        self.hide()

    # ---- building blocks ----
    def add_header(self, title: str, subtitle: str = "") -> None:
        self.body.addWidget(Text(title, "title3", wrap=True))
        if subtitle:
            self.body.addSpacing(4)
            self.body.addWidget(Text(subtitle, "body", "secondary", wrap=True))
        self.body.addSpacing(16)

    def add_buttons(self, cancel_text: str, confirm_text: str, confirm_kind: str = "primary"):
        row = QHBoxLayout()
        row.setSpacing(10)
        cancel = make_button(cancel_text, "secondary", large=True)
        confirm = make_button(confirm_text, confirm_kind, large=True)
        cancel.clicked.connect(self.dismiss)
        row.addWidget(cancel, 1)
        row.addWidget(confirm, 1)
        self.body.addSpacing(18)
        self.body.addLayout(row)
        return cancel, confirm

    def set_default_action(self, fn) -> None:
        self._default_action = fn

    # ---- presenting ----
    def _fit_card(self) -> None:
        lay = self.card.layout()
        w = self.card.width()
        h = lay.totalHeightForWidth(w) if lay.hasHeightForWidth() else lay.sizeHint().height()
        self.card.resize(w, max(h, lay.minimumSize().height()))

    def _target_y(self) -> int:
        return max(28, int((self.height() - self.card.height()) * 0.30))

    def _apply(self, v: float = 0.0) -> None:
        start = -self.card.height() - 60
        y = int(start + (self._target_y() - start) * self._progress.value)
        self.card.move((self.width() - self.card.width()) // 2, y)
        self.update()

    def present(self) -> None:
        self.setGeometry(self._host.rect())
        self._fit_card()
        self._progress.jump(0.0)
        self.show()
        self.raise_()
        self._apply()
        self.setFocus()
        self._progress.to(1.0)

    def dismiss(self) -> None:
        if self._closing:
            return
        self._closing = True
        self._progress.to(0.0, 260)  # same path out as in

    def _on_settled(self, v: float) -> None:
        if self._closing and v == 0.0:
            self._host.removeEventFilter(self)
            self.hide()
            self.deleteLater()
            self.dismissed.emit()

    def shake_card(self) -> None:
        shake(self.card)

    @property
    def closing(self) -> bool:
        return self._closing

    # ---- events ----
    def eventFilter(self, obj, ev) -> bool:
        if obj is self._host and ev.type() == QEvent.Type.Resize:
            self.setGeometry(self._host.rect())
            self._apply()
        return False

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        c = theme.color("scrim")
        c.setAlpha(int(c.alpha() * self._progress.value))
        p.fillRect(self.rect(), c)

    def mousePressEvent(self, e) -> None:
        if self._dismissable and not self.card.geometry().contains(e.position().toPoint()):
            self.dismiss()
        e.accept()

    def keyPressEvent(self, e) -> None:
        if e.key() == Qt.Key.Key_Escape and self._dismissable:
            self.dismiss()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self._default_action and not self._closing:
            self._default_action()
        else:
            super().keyPressEvent(e)


class Toast(QWidget):
    def __init__(self, host: QWidget):
        super().__init__(host)
        self._host = host
        self._text, self._kind = "", "success"
        self._progress = Animated(0.0, 260, parent=self)
        self._progress.changed.connect(self._apply)
        self._progress.settled.connect(lambda v: self.hide() if v == 0.0 else None)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self._progress.to(0.0, 220))
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.hide()

    def show_message(self, text: str, kind: str = "success") -> None:
        self._text, self._kind = text, kind
        fm = QFontMetrics(font_for("headline"))
        width = min(fm.horizontalAdvance(text) + 14 + 18 + 12 + 18, max(200, self._host.width() - 48))
        self.resize(width, 42)
        self.show()
        self.raise_()
        self._apply()
        self._progress.to(1.0)
        self._timer.start(2800 if kind == "error" else 2200)

    def _apply(self, _v: float = 0.0) -> None:
        v = self._progress.value
        self.move((self._host.width() - self.width()) // 2,
                  self._host.height() - self.height() - 28 + int((1 - v) * 16))
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setOpacity(self._progress.value)
        rect = QRectF(self.rect())
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(theme.color("toast"))
        p.drawRoundedRect(rect, rect.height() / 2, rect.height() / 2)
        name, color = ("check_circle", theme.color("success")) if self._kind == "success" else ("alert", theme.color("danger"))
        p.drawPixmap(QPointF(14, (rect.height() - 18) / 2), icons.pixmap(name, 18, color, self.devicePixelRatioF(), 1.8))
        f = font_for("headline")
        p.setFont(f)
        p.setPen(QColor(255, 255, 255))
        text = QFontMetrics(f).elidedText(self._text, Qt.TextElideMode.ElideRight, int(rect.width() - 48))
        draw_text(p, QRectF(40, 0, rect.width() - 48, rect.height()), text)
