"""Jinsei - a private locker for images, documents and notes."""
import sys

from PySide6.QtWidgets import QApplication

from jinsei import library, theme
from jinsei.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Jinsei")
    library.ensure_storage()
    theme.install(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
