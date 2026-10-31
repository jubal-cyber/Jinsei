"""Line icons (SF Symbols-style) drawn from inline SVG, tinted at render time."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPainterPath, QPixmap
from PySide6.QtSvg import QSvgRenderer

BODIES = {
    "image": '<rect width="18" height="18" x="3" y="3" rx="3"/><circle cx="9" cy="9" r="2"/>'
             '<path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
    "doc": '<path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/>'
           '<path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/>',
    "text": '<line x1="21" x2="3" y1="6" y2="6"/><line x1="15" x2="3" y1="12" y2="12"/>'
            '<line x1="17" x2="3" y1="18" y2="18"/>',
    "sliders": '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/>'
               '<line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/>'
               '<line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/>'
               '<line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/>'
               '<line x1="16" x2="16" y1="18" y2="22"/>',
    "plus": '<path d="M5 12h14"/><path d="M12 5v14"/>',
    "grid": '<rect width="7" height="7" x="3" y="3" rx="1.5"/><rect width="7" height="7" x="14" y="3" rx="1.5"/>'
            '<rect width="7" height="7" x="14" y="14" rx="1.5"/><rect width="7" height="7" x="3" y="14" rx="1.5"/>',
    "list": '<line x1="8" x2="21" y1="6" y2="6"/><line x1="8" x2="21" y1="12" y2="12"/>'
            '<line x1="8" x2="21" y1="18" y2="18"/><line x1="3" x2="3.01" y1="6" y2="6"/>'
            '<line x1="3" x2="3.01" y1="12" y2="12"/><line x1="3" x2="3.01" y1="18" y2="18"/>',
    "lock": '<rect width="18" height="11" x="3" y="11" rx="2.5"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/>',
    "trash": '<path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/>'
             '<path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>',
    "fingerprint": '<path d="M12 10a2 2 0 0 0-2 2c0 1.02-.1 2.51-.26 4"/><path d="M14 13.12c0 2.38 0 6.38-1 8.88"/>'
                   '<path d="M17.29 21.02c.12-.6.43-2.3.5-3.02"/><path d="M2 12a10 10 0 0 1 18-6"/>'
                   '<path d="M2 16h.01"/><path d="M21.8 16c.2-2 .131-5.354 0-6"/>'
                   '<path d="M5 19.5C5.5 18 6 15 6 12a6 6 0 0 1 .34-2"/><path d="M8.65 22c.21-.66.45-1.32.57-2"/>'
                   '<path d="M9 6.8a6 6 0 0 1 9 5.2v2"/>',
    "key": '<path d="m15.5 7.5 2.3 2.3a1 1 0 0 0 1.4 0l2.1-2.1a1 1 0 0 0 0-1.4L19 4"/>'
           '<path d="m21 2-9.6 9.6"/><circle cx="7.5" cy="15.5" r="5.5"/>',
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "check_circle": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "alert": '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/>'
             '<line x1="12" x2="12.01" y1="16" y2="16"/>',
    "circle": '<circle cx="12" cy="12" r="9"/>',
    "chevron": '<path d="m9 18 6-6-6-6"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/>',
    "eye_off": '<path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 10 8 10 8a13.16 13.16 0 0 1-1.67 2.68"/>'
               '<path d="M6.61 6.61A13.526 13.526 0 0 0 2 12s3 8 10 8a9.74 9.74 0 0 0 5.39-1.61"/>'
               '<path d="M14.12 14.12a3 3 0 1 1-4.24-4.24"/><line x1="2" x2="22" y1="2" y2="22"/>',
}


SECTION_ICON = {"Images": "image", "Documents": "doc", "Text": "text"}


def svg_source(name: str, rgba: tuple[int, int, int, int], stroke: float = 1.75) -> str:
    r, g, b, a = rgba
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="#{r:02x}{g:02x}{b:02x}" stroke-opacity="{a / 255:.3f}" stroke-width="{stroke}" '
        f'stroke-linecap="round" stroke-linejoin="round">{BODIES[name]}</svg>'
    )


@lru_cache(maxsize=512)
def _render(name: str, rgba: tuple, size: int, dpr: float, stroke: float) -> QPixmap:
    renderer = QSvgRenderer(QByteArray(svg_source(name, rgba, stroke).encode("utf-8")))
    px = max(1, int(round(size * dpr)))
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, px, px))
    painter.end()
    pm.setDevicePixelRatio(dpr)
    return pm


def pixmap(name: str, size: int, color: QColor, dpr: float = 1.0, stroke: float = 1.75) -> QPixmap:
    rgba = (color.red(), color.green(), color.blue(), color.alpha())
    return _render(name, rgba, int(size), round(float(dpr), 2), float(stroke))


def icon(name: str, size: int, color: QColor, stroke: float = 1.75) -> QIcon:
    return QIcon(pixmap(name, size, color, 2.0, stroke))


ASSETS = Path(__file__).resolve().parent / "assets"


@lru_cache(maxsize=1)
def _logo_source() -> QPixmap:
    return QPixmap(str(ASSETS / "jinsei.png"))


def brand_pixmap(size: int, dpr: float = 2.0) -> QPixmap:
    """The Jinsei mark: the brush-stroke \u751f on a near-black rounded tile (assets/jinsei.png)."""
    source = _logo_source()
    if source.isNull():
        return _fallback_brand(size, dpr)
    px = max(1, int(size * dpr))
    pm = source.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    pm.setDevicePixelRatio(dpr)
    return pm


def _fallback_brand(size: int, dpr: float) -> QPixmap:
    px = int(size * dpr)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, px, px), px * 0.225, px * 0.225)
    p.fillPath(path, QBrush(QColor("#111113")))
    glyph = int(px * 0.52)
    p.drawPixmap(int((px - glyph) / 2), int((px - glyph) / 2),
                 _render("lock", (255, 255, 255, 255), glyph, 1.0, 1.9))
    p.end()
    pm.setDevicePixelRatio(dpr)
    return pm
