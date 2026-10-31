"""Modal sheets: New Note, Delete confirmation, Change Password."""
from __future__ import annotations

from typing import Callable

from PySide6.QtWidgets import QLineEdit, QPlainTextEdit

from . import auth as auth_mod
from .widgets import Hint, PasswordField, Sheet, Text, set_invalid


class NewTextSheet(Sheet):
    def __init__(self, host, on_save: Callable[[str, str], None]):
        super().__init__(host, 480)
        self._on_save = on_save
        self.add_header("New Note", "Saved privately in Jinsei as a text file.")
        self.title_field = QLineEdit()
        self.title_field.setPlaceholderText("Title")
        self.title_field.setMaxLength(80)
        self.text_field = QPlainTextEdit()
        self.text_field.setPlaceholderText("Write something\u2026")
        self.text_field.setFixedHeight(170)
        self.body.addWidget(self.title_field)
        self.body.addSpacing(10)
        self.body.addWidget(self.text_field)
        _cancel, self.save_button = self.add_buttons("Cancel", "Save")
        self.save_button.setEnabled(False)
        self.title_field.textChanged.connect(lambda t: self.save_button.setEnabled(bool(t.strip())))
        self.title_field.returnPressed.connect(lambda: self.text_field.setFocus())
        self.save_button.clicked.connect(self._submit)

    def present(self) -> None:
        super().present()
        self.title_field.setFocus()

    def _submit(self) -> None:
        title = self.title_field.text().strip()
        if not title or self.closing:
            return
        self._on_save(title, self.text_field.toPlainText())
        self.dismiss()


class ConfirmSheet(Sheet):
    """Used for the one genuinely irreversible action: deleting a file."""

    def __init__(self, host, title: str, message: str, confirm_text: str, on_confirm: Callable[[], None],
                 destructive: bool = True):
        super().__init__(host, 400)
        self._on_confirm = on_confirm
        self.add_header(title, message)
        self.cancel_button, confirm = self.add_buttons("Cancel", confirm_text, "danger" if destructive else "primary")
        confirm.clicked.connect(self._confirm)
        self.set_default_action(self.dismiss)  # Return = the safe choice

    def present(self) -> None:
        super().present()
        self.cancel_button.setFocus()

    def _confirm(self) -> None:
        if self.closing:
            return
        self._on_confirm()
        self.dismiss()


class ChangePasswordSheet(Sheet):
    def __init__(self, host, auth: auth_mod.AuthStore, on_done: Callable[[], None]):
        super().__init__(host, 440)
        self.auth = auth
        self._on_done = on_done
        self.add_header("Change Password", "Enter your current password, then choose a new one.")
        self.current = PasswordField("Current password")
        self.new = PasswordField("New password")
        self.confirm = PasswordField("Confirm new password")
        self.body.addWidget(self.current)
        self.body.addSpacing(14)
        self.body.addWidget(self.new)
        self.body.addSpacing(10)
        self.body.addWidget(self.confirm)
        self.body.addSpacing(12)
        self.hint_len = Hint(f"At least {auth_mod.MIN_PASSWORD_LENGTH} characters")
        self.hint_match = Hint("New passwords match")
        self.hint_diff = Hint("Different from your current password")
        for h in (self.hint_len, self.hint_match, self.hint_diff):
            self.body.addWidget(h)
        self.error = Text("", "callout", "danger")
        self.error.setMinimumHeight(22)  # reserved, so the sheet never changes height
        self.body.addSpacing(4)
        self.body.addWidget(self.error)
        _cancel, self.submit_button = self.add_buttons("Cancel", "Change Password")
        self.submit_button.setEnabled(False)
        for field in (self.current, self.new, self.confirm):
            field.textChanged.connect(self._validate)
        self.current.returnPressed.connect(lambda: self.new.setFocus())
        self.new.returnPressed.connect(lambda: self.confirm.setFocus())
        self.confirm.returnPressed.connect(self._submit)
        self.submit_button.clicked.connect(self._submit)

    def present(self) -> None:
        super().present()
        self.current.setFocus()

    def _validate(self, *_args) -> None:
        cur, new, conf = self.current.text(), self.new.text(), self.confirm.text()
        ok_len = len(new) >= auth_mod.MIN_PASSWORD_LENGTH
        ok_match = bool(conf) and new == conf
        ok_diff = bool(new) and new != cur
        self.hint_len.set_ok(ok_len)
        self.hint_match.set_ok(ok_match)
        self.hint_diff.set_ok(ok_diff)
        self.error.setText("")
        self.submit_button.setEnabled(bool(cur) and ok_len and ok_match and ok_diff)

    def _submit(self) -> None:
        if not self.submit_button.isEnabled() or self.closing:
            return
        try:
            result = self.auth.change_password(self.current.text(), self.new.text())
        except (ValueError, OSError) as exc:
            self.error.setText(str(exc))
            return
        if result.ok:
            self._on_done()
            self.dismiss()
            return
        self.current.clear()
        set_invalid(self.current, True)
        if result.locked_for:
            self.error.setText(f"Too many attempts. Try again in {auth_mod.format_wait(result.locked_for)}.")
        else:
            self.error.setText("Current password is incorrect.")
        self.shake_card()
        self.current.setFocus()
