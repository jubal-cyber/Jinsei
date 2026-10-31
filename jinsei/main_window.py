"""Main window: lock screen <-> shell (sidebar + content)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QIcon, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMainWindow, QScrollArea, QStackedLayout,
                               QStackedWidget, QVBoxLayout, QWidget)

from . import auth as auth_mod
from . import icons, library
from .lock import LockScreen
from .motion import Animated, fade_in
from .settings import SettingsPage
from .sheets import ChangePasswordSheet, ConfirmSheet, NewTextSheet
from .theme import theme
from .widgets import (EmptyState, ItemCollection, Segmented, Sheet, SideItem, Text, Toast, make_button)


class Sidebar(QWidget):
    selected = Signal(str)
    lock_requested = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(248)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 20, 14, 14)
        lay.setSpacing(2)

        brand = QHBoxLayout()
        brand.setContentsMargins(6, 0, 0, 0)
        brand.setSpacing(10)
        mark = QLabel()
        mark.setPixmap(icons.brand_pixmap(30, 2.0))
        mark.setFixedSize(30, 30)
        brand.addWidget(mark)
        brand.addWidget(Text("Jinsei", "title3"))
        brand.addStretch()
        lay.addLayout(brand)
        lay.addSpacing(24)
        label = Text("Library", "caption", "tertiary")
        label.setContentsMargins(12, 0, 0, 5)
        lay.addWidget(label)

        self.items: dict[str, SideItem] = {}
        for key in library.ORDER:
            sec = library.SECTIONS[key]
            item = SideItem(key, sec.label, sec.icon, key)
            item.pressed.connect(self.selected.emit)
            self.items[key] = item
            lay.addWidget(item)
        lay.addStretch()
        settings = SideItem("Settings", "Settings", "sliders", "Settings")
        settings.pressed.connect(self.selected.emit)
        self.items["Settings"] = settings
        lock = SideItem("Lock", "Lock Jinsei", "lock", "Settings", selectable=False)
        lock.setToolTip("Lock Jinsei (Ctrl+L)")
        lock.pressed.connect(lambda _k: self.lock_requested.emit())
        lay.addWidget(settings)
        lay.addWidget(lock)

    def set_current(self, key: str) -> None:
        for k, item in self.items.items():
            item.set_checked(k == key)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), theme.color("sidebar"))
        p.setPen(theme.color("sep"))
        p.drawLine(self.width() - 1, 0, self.width() - 1, self.height())


class EdgeLine(QWidget):
    """A hairline under the toolbar that only appears once content scrolls beneath it."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self._amount = Animated(0.0, 180, parent=self)
        self._amount.changed.connect(lambda _v: self.update())

    def set_scrolled(self, scrolled: bool) -> None:
        self._amount.to(1.0 if scrolled else 0.0)

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), QBrush(theme.color_scaled("sep", self._amount.value)))


class Toolbar(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(88)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(32, 14, 32, 10)
        lay.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.title = Text("", "largeTitle")
        self.subtitle = Text("", "callout", "secondary")
        titles.addStretch()
        titles.addWidget(self.title)
        titles.addWidget(self.subtitle)
        titles.addStretch()
        lay.addLayout(titles)
        lay.addStretch()
        self.segmented = Segmented(["grid", "list"])
        self.add_button = make_button("Add", "primary", "plus")
        lay.addWidget(self.segmented, 0, Qt.AlignmentFlag.AlignVCenter)
        lay.addWidget(self.add_button, 0, Qt.AlignmentFlag.AlignVCenter)

    def set_titles(self, title: str, subtitle: str) -> None:
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.subtitle.setVisible(bool(subtitle))

    def set_library_controls(self, visible: bool) -> None:
        self.segmented.setVisible(visible)
        self.add_button.setVisible(visible)


class LibraryPage(QStackedWidget):
    open_requested = Signal(object)
    delete_requested = Signal(object)
    add_requested = Signal()
    scrolled = Signal(bool)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll.viewport().setAutoFillBackground(False)
        self.collection = ItemCollection()
        self.scroll.setWidget(self.collection)
        self.empty = EmptyState()
        self.addWidget(self.scroll)
        self.addWidget(self.empty)
        self.collection.open_requested.connect(self.open_requested.emit)
        self.collection.delete_requested.connect(self.delete_requested.emit)
        self.empty.add_clicked.connect(self.add_requested.emit)
        self.scroll.verticalScrollBar().valueChanged.connect(lambda v: self.scrolled.emit(v > 0))

    def show_items(self, section: library.Section, items: list[library.Item], mode: str) -> None:
        if items:
            self.collection.set_items(items, mode)
            self.setCurrentWidget(self.scroll)
        else:
            self.empty.configure(section)
            self.setCurrentWidget(self.empty)
            self.scrolled.emit(False)


def _plural(noun: str, n: int) -> str:
    return noun if n == 1 else noun + "s"


class Shell(QWidget):
    lock_requested = Signal()

    def __init__(self, auth: auth_mod.AuthStore, host: QWidget, toast: Toast, parent: QWidget | None = None):
        super().__init__(parent)
        self.auth, self.host, self.toast = auth, host, toast
        self.current = "Images"
        self.mode = "grid"

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self.sidebar = Sidebar()
        root.addWidget(self.sidebar)

        right = QWidget()
        col = QVBoxLayout(right)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self.toolbar = Toolbar()
        self.edge = EdgeLine()
        self.pages = QStackedWidget()
        self.library_page = LibraryPage()
        self.settings_page = SettingsPage(auth, self.toast.show_message)
        self.pages.addWidget(self.library_page)
        self.pages.addWidget(self.settings_page)
        col.addWidget(self.toolbar)
        col.addWidget(self.edge)
        col.addWidget(self.pages, 1)
        root.addWidget(right, 1)

        self.sidebar.selected.connect(self.select)
        self.sidebar.lock_requested.connect(self.lock_requested.emit)
        self.toolbar.add_button.clicked.connect(self.add)
        self.toolbar.segmented.changed.connect(self._mode_changed)
        self.library_page.add_requested.connect(self.add)
        self.library_page.open_requested.connect(self._open)
        self.library_page.delete_requested.connect(self._confirm_delete)
        self.library_page.scrolled.connect(self.edge.set_scrolled)
        self.settings_page.change_password_requested.connect(self._change_password)

        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.add)
        QShortcut(QKeySequence("Ctrl+L"), self).activated.connect(self.lock_requested.emit)
        self.select("Images", animate=False)

    # ---------------------------------------------------------------- navigation
    def select(self, key: str, animate: bool = True) -> None:
        self.current = key
        self.sidebar.set_current(key)
        if key == "Settings":
            self.toolbar.set_titles("Settings", "")
            self.toolbar.set_library_controls(False)
            self.edge.set_scrolled(False)
            self.pages.setCurrentWidget(self.settings_page)
            self.settings_page.refresh()
        else:
            self.toolbar.set_library_controls(True)
            self.pages.setCurrentWidget(self.library_page)
            self.refresh()
        if animate:
            fade_in(self.pages, 200)

    def refresh(self) -> None:
        for key in library.ORDER:
            self.sidebar.items[key].set_count(library.count_items(key))
        if self.current == "Settings":
            return
        section = library.SECTIONS[self.current]
        items = library.list_items(self.current)
        n = len(items)
        self.toolbar.set_titles(section.label, f"{n} {_plural(section.noun, n)}" if n else "")
        self.toolbar.add_button.setText("New Note" if self.current == "Text" else "Add")
        self.library_page.show_items(section, items, self.mode)

    def _mode_changed(self, index: int) -> None:
        self.mode = "grid" if index == 0 else "list"
        if self.current != "Settings":
            self.refresh()

    def close_overlays(self) -> None:
        for sheet in self.host.findChildren(Sheet):
            sheet.hide()
            sheet.deleteLater()

    # ---------------------------------------------------------------- add
    def add(self) -> None:
        if self.current == "Settings":
            return
        if self.current == "Text":
            NewTextSheet(self.host, self._save_note).present()
            return
        section = library.SECTIONS[self.current]
        paths, _ = QFileDialog.getOpenFileNames(self, section.dialog_title, "", section.dialog_filter)
        if not paths:
            return
        try:
            added = library.add_files(self.current, [Path(p) for p in paths])
        except OSError as exc:
            self.toast.show_message(f"Couldn\u2019t add the file: {exc.strerror or exc}", "error")
            return
        self.refresh()
        n = len(added)
        self.toast.show_message(f"Added {n} {_plural(section.noun, n)}")

    def _save_note(self, title: str, body: str) -> None:
        try:
            library.add_text(title, body)
        except OSError as exc:
            self.toast.show_message(f"Couldn\u2019t save the note: {exc.strerror or exc}", "error")
            return
        self.refresh()
        self.toast.show_message("Note saved")

    # ---------------------------------------------------------------- open / delete
    def _open(self, item: library.Item) -> None:
        try:
            library.open_item(item.path)
        except Exception as exc:  # unable to launch the default app
            self.toast.show_message(f"Unable to open file: {exc}", "error")

    def _confirm_delete(self, item: library.Item) -> None:
        ConfirmSheet(
            self.host,
            f"Delete \u201c{item.name}\u201d?",
            "This file will be permanently deleted from Jinsei. This can\u2019t be undone.",
            "Delete",
            lambda: self._delete(item),
        ).present()

    def _delete(self, item: library.Item) -> None:
        try:
            library.delete_item(item.path)
        except OSError as exc:
            self.toast.show_message(f"Couldn\u2019t delete \u201c{item.name}\u201d: {exc.strerror or exc}", "error")
            return
        self.refresh()
        self.toast.show_message(f"Deleted \u201c{item.name}\u201d")

    # ---------------------------------------------------------------- settings
    def _change_password(self) -> None:
        ChangePasswordSheet(self.host, self.auth, lambda: self.toast.show_message("Password updated")).present()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Jinsei")
        self.setWindowIcon(QIcon(icons.brand_pixmap(256, 1.0)))
        self.setMinimumSize(900, 600)
        self.resize(1120, 740)

        self.auth = auth_mod.AuthStore()
        root = QWidget()
        root.setObjectName("root")
        self.setCentralWidget(root)
        self.root = root
        stack = QStackedLayout(root)
        stack.setContentsMargins(0, 0, 0, 0)
        self.stack = stack
        self.lock_screen = LockScreen(self.auth)
        self.toast = Toast(root)
        self.shell = Shell(self.auth, root, self.toast)
        stack.addWidget(self.lock_screen)
        stack.addWidget(self.shell)
        self.lock_screen.unlocked.connect(self._unlocked)
        self.shell.lock_requested.connect(self._lock)
        stack.setCurrentWidget(self.lock_screen)
        self.lock_screen.start()

    def _unlocked(self, note: str) -> None:
        self.shell.select("Images", animate=False)
        self.stack.setCurrentWidget(self.shell)
        fade_in(self.shell, 280)
        if note:
            QTimer.singleShot(650, lambda: self.toast.show_message(note, "success"))

    def _lock(self) -> None:
        self.shell.close_overlays()
        self.stack.setCurrentWidget(self.lock_screen)
        fade_in(self.lock_screen, 220)
        self.lock_screen.start()
