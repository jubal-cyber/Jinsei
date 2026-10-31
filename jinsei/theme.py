"""Design tokens + stylesheet. Light and dark follow the system setting."""
from __future__ import annotations

from string import Template

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

RGBA = tuple[int, int, int, int]


def _h(value: str, alpha: int = 255) -> RGBA:
    v = value.lstrip("#")
    return int(v[0:2], 16), int(v[2:4], 16), int(v[4:6], 16), alpha


LIGHT: dict[str, RGBA] = {
    "bg": _h("#F5F5F7"), "sidebar": _h("#EAEAEF"), "surface": _h("#FFFFFF"), "surface_alt": _h("#F2F2F7"),
    "text": _h("#1D1D1F"), "text2": _h("#6E6E73"), "text3": _h("#8E8E93"),
    "fill": (118, 118, 128, 31), "fill_hover": (118, 118, 128, 46), "fill_press": (118, 118, 128, 66),
    "sep": (60, 60, 67, 38),
    "accent": _h("#007AFF"), "accent_hover": _h("#006FE8"), "accent_press": _h("#005BC4"),
    "accent_soft": (0, 122, 255, 30), "accent_ring": (0, 122, 255, 110),
    "danger": _h("#FF3B30"), "danger_hover": _h("#EB2F25"), "danger_press": _h("#C9231A"),
    "danger_soft": (255, 59, 48, 28),
    "success": _h("#34C759"), "on_accent": _h("#FFFFFF"),
    "scrim": (0, 0, 0, 86), "shadow": (0, 0, 0, 60),
    "scroll": (0, 0, 0, 52), "scroll_hover": (0, 0, 0, 96),
    "toast": (36, 36, 38, 238),
    "tint_Images": _h("#FF2D55"), "tint_Documents": _h("#007AFF"), "tint_Text": _h("#FF9500"),
    "tint_Settings": _h("#8E8E93"), "tint_Security": _h("#34C759"), "tint_Key": _h("#007AFF"),
}

DARK: dict[str, RGBA] = {
    **LIGHT,
    "bg": _h("#1C1C1E"), "sidebar": _h("#262628"), "surface": _h("#2C2C2E"), "surface_alt": _h("#242426"),
    "text": _h("#F5F5F7"), "text2": _h("#A1A1A6"), "text3": _h("#8E8E93"),
    "fill": (118, 118, 128, 61), "fill_hover": (118, 118, 128, 77), "fill_press": (118, 118, 128, 102),
    "sep": (84, 84, 88, 140),
    "accent": _h("#0A84FF"), "accent_hover": _h("#2B94FF"), "accent_press": _h("#0070E0"),
    "accent_soft": (10, 132, 255, 56), "accent_ring": (10, 132, 255, 140),
    "danger": _h("#FF453A"), "danger_hover": _h("#FF5C52"), "danger_press": _h("#E0352B"),
    "danger_soft": (255, 69, 58, 46),
    "success": _h("#30D158"),
    "scrim": (0, 0, 0, 140), "shadow": (0, 0, 0, 150),
    "scroll": (255, 255, 255, 56), "scroll_hover": (255, 255, 255, 100),
    "toast": (70, 70, 74, 240),
    "tint_Images": _h("#FF375F"), "tint_Documents": _h("#0A84FF"), "tint_Text": _h("#FF9F0A"),
    "tint_Security": _h("#30D158"), "tint_Key": _h("#0A84FF"),
}


class Theme:
    def __init__(self) -> None:
        self.dark = False
        self._tokens = LIGHT

    def set_dark(self, dark: bool) -> None:
        self.dark = dark
        self._tokens = DARK if dark else LIGHT

    def color(self, name: str, alpha: int | None = None) -> QColor:
        r, g, b, a = self._tokens[name]
        return QColor(r, g, b, a if alpha is None else max(0, min(255, int(alpha))))

    def color_scaled(self, name: str, k: float) -> QColor:
        """A token with its alpha multiplied by k (0..1) - used for hover/press blends."""
        c = self.color(name)
        c.setAlpha(int(c.alpha() * max(0.0, min(1.0, k))))
        return c

    def css(self, name: str) -> str:
        r, g, b, a = self._tokens[name]
        if a == 255:
            return f"#{r:02x}{g:02x}{b:02x}"
        return f"rgba({r}, {g}, {b}, {a})"

    def tint(self, section: str) -> QColor:
        return self.color(f"tint_{section}")


theme = Theme()

TEXT_FAMILIES = ["SF Pro Text", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", "Arial"]
DISPLAY_FAMILIES = ["SF Pro Display", "Segoe UI Variable Display", "Segoe UI", "Helvetica Neue", "Arial"]

# role -> (pixel size, weight, tracking px, display face).
# Tracking is size-specific: large text tightens, small text opens up slightly.
ROLES = {
    "largeTitle": (28, QFont.Weight.Bold, -0.6, True),
    "title": (22, QFont.Weight.Bold, -0.4, True),
    "title3": (17, QFont.Weight.DemiBold, -0.25, True),
    "headline": (14, QFont.Weight.DemiBold, -0.1, False),
    "body": (14, QFont.Weight.Normal, 0.0, False),
    "callout": (13, QFont.Weight.Normal, 0.0, False),
    "caption": (12, QFont.Weight.Normal, 0.1, False),
}


def font_for(role: str, weight: QFont.Weight | None = None) -> QFont:
    px, w, tracking, display = ROLES[role]
    f = QFont()
    f.setFamilies(DISPLAY_FAMILIES if display else TEXT_FAMILIES)
    f.setPixelSize(px)
    f.setWeight(weight or w)
    f.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, tracking)
    return f


_QSS = Template(r"""
QWidget#root { background: $bg; }
QLabel { background: transparent; color: $text; }
QLabel[tone="secondary"] { color: $text2; }
QLabel[tone="tertiary"] { color: $text3; }
QLabel[tone="accent"] { color: $accent; }
QLabel[tone="danger"] { color: $danger; }
QLabel[tone="success"] { color: $success; }

QLineEdit, QPlainTextEdit {
    background: $fill; color: $text; border: 2px solid transparent; border-radius: 11px;
    selection-background-color: $accent_soft; selection-color: $text;
}
QLineEdit { padding: 0 14px; min-height: 42px; font-size: 15px; }
QPlainTextEdit { padding: 8px 10px; font-size: 14px; }
QLineEdit:focus, QPlainTextEdit:focus { border: 2px solid $accent_ring; background: $surface; }
QLineEdit[invalid="true"] { border: 2px solid $danger; }
QLineEdit:disabled { color: $text3; }

QPushButton { border: 2px solid transparent; background: transparent; outline: none; }
QPushButton[kind] { border-radius: 11px; padding: 0 18px; min-height: 36px; font-size: 14px; font-weight: 600; }
QPushButton[kind][size="lg"] { min-height: 44px; font-size: 15px; border-radius: 12px; }
QPushButton[kind]:focus { border-color: $accent_ring; }
QPushButton[kind="primary"] { background: $accent; color: $on_accent; }
QPushButton[kind="primary"]:hover { background: $accent_hover; }
QPushButton[kind="primary"]:pressed { background: $accent_press; }
QPushButton[kind="secondary"] { background: $fill; color: $text; }
QPushButton[kind="secondary"]:hover { background: $fill_hover; }
QPushButton[kind="secondary"]:pressed { background: $fill_press; }
QPushButton[kind="danger"] { background: $danger; color: $on_accent; }
QPushButton[kind="danger"]:hover { background: $danger_hover; }
QPushButton[kind="danger"]:pressed { background: $danger_press; }
QPushButton[kind="plain"] { background: transparent; color: $accent; font-weight: 500; }
QPushButton[kind="plain"]:hover { background: $accent_soft; }
QPushButton[kind="plain"]:pressed { background: $fill_press; }
QPushButton[kind]:disabled { background: $fill; color: $text3; }

QFrame#sheetCard { background: $surface; border: 1px solid $sep; border-radius: 20px; }

QScrollArea { background: transparent; border: none; }
QScrollArea > QWidget > QWidget { background: transparent; }
QScrollBar:vertical { background: transparent; width: 12px; margin: 2px; }
QScrollBar::handle:vertical { background: $scroll; border-radius: 3px; min-height: 36px; margin: 0 3px; }
QScrollBar::handle:vertical:hover { background: $scroll_hover; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

QMenu { background: $surface; border: 1px solid $sep; border-radius: 10px; padding: 6px; color: $text; font-size: 13px; }
QMenu::item { padding: 7px 26px 7px 14px; border-radius: 6px; }
QMenu::item:selected { background: $accent; color: $on_accent; }
QMenu::separator { height: 1px; background: $sep; margin: 5px 8px; }
QToolTip { background: $surface; color: $text; border: 1px solid $sep; padding: 5px 8px; }
""")


def stylesheet() -> str:
    keys = {name: theme.css(name) for name in LIGHT}
    return _QSS.substitute(keys)


def _palette() -> QPalette:
    pal = QPalette()
    c = theme.color
    for role, name in (
        (QPalette.ColorRole.Window, "bg"), (QPalette.ColorRole.WindowText, "text"),
        (QPalette.ColorRole.Base, "surface"), (QPalette.ColorRole.AlternateBase, "surface_alt"),
        (QPalette.ColorRole.Text, "text"), (QPalette.ColorRole.Button, "fill"),
        (QPalette.ColorRole.ButtonText, "text"), (QPalette.ColorRole.Highlight, "accent"),
        (QPalette.ColorRole.HighlightedText, "on_accent"), (QPalette.ColorRole.PlaceholderText, "text3"),
        (QPalette.ColorRole.ToolTipBase, "surface"), (QPalette.ColorRole.ToolTipText, "text"),
    ):
        pal.setColor(role, c(name))
    return pal


def _system_is_dark() -> bool:
    hints = QGuiApplication.styleHints()
    scheme = getattr(hints, "colorScheme", None)
    return bool(scheme and scheme() == Qt.ColorScheme.Dark)


def apply(app: QApplication) -> None:
    theme.set_dark(_system_is_dark())
    app.setPalette(_palette())
    app.setStyleSheet(stylesheet())


def install(app: QApplication) -> None:
    """Fusion + our stylesheet, and re-theme live when the system switches light/dark."""
    app.setStyle("Fusion")
    app.setFont(font_for("body"))
    apply(app)
    signal = getattr(QGuiApplication.styleHints(), "colorSchemeChanged", None)
    if signal is not None:
        signal.connect(lambda *_: apply(app))
