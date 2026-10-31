"""Lock screen: first-run setup (password, then fingerprint) and every later unlock."""
from __future__ import annotations

from PySide6.QtCore import QEasingCurve, QPointF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPen, QPixmap, QRadialGradient
from PySide6.QtWidgets import QLabel, QStackedWidget, QVBoxLayout, QWidget

from . import auth as auth_mod
from . import biometrics, icons
from .bio_runner import runner
from .motion import Animated, fade_in, reduced_motion, shake
from .theme import theme
from .widgets import Hint, PasswordField, Text, make_button, set_invalid, set_tone

PAGE_CREATE, PAGE_ENROLL, PAGE_BIO, PAGE_PASSWORD = range(4)
CENTER = Qt.AlignmentFlag.AlignHCenter

FALLBACK_NOTE = ("Fingerprint isn\u2019t available on this PC, so Jinsei will use your password only. "
                 "You can set it up later in Settings.")


class FingerprintBadge(QWidget):
    """Fingerprint glyph on a soft disc. Pulses while waiting; pops to a check on success."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(136, 136)
        self._state = "idle"
        self._pop = Animated(1.0, 340, parent=self)
        self._pop.changed.connect(lambda _v: self.update())
        self._pulse = QVariantAnimation(self)
        self._pulse.setStartValue(0.0)
        self._pulse.setEndValue(1.0)
        self._pulse.setDuration(1700)
        self._pulse.setLoopCount(-1)
        self._pulse.setEasingCurve(QEasingCurve(QEasingCurve.Type.OutCubic))
        self._pulse.valueChanged.connect(lambda _v: self.update())

    def set_state(self, state: str) -> None:
        self._state = state
        if state == "scanning" and not reduced_motion():
            self._pulse.start()
        else:
            self._pulse.stop()
        if state == "success":
            self._pop.jump(0.65)
            self._pop.to(1.0)
        self.update()

    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(self.width() / 2, self.height() / 2)
        base = {"error": theme.color("danger"), "success": theme.color("success")}.get(self._state, theme.color("accent"))

        glow = QRadialGradient(c, 68)
        top = QColor(base)
        top.setAlpha(60 if theme.dark else 44)
        clear = QColor(base)
        clear.setAlpha(0)
        glow.setColorAt(0.0, top)
        glow.setColorAt(1.0, clear)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QBrush(glow))
        p.drawEllipse(c, 68, 68)

        disc = QColor(base)
        disc.setAlpha(46 if theme.dark else 28)
        p.setBrush(disc)
        p.drawEllipse(c, 46, 46)
        ring = QColor(base)
        ring.setAlpha(120)
        p.setPen(QPen(ring, 1.5))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawEllipse(c, 46, 46)

        if self._state == "scanning" and self._pulse.state() == QVariantAnimation.State.Running:
            t = float(self._pulse.currentValue())
            wave = QColor(base)
            wave.setAlpha(int(150 * (1.0 - t)))
            p.setPen(QPen(wave, 1.5))
            p.drawEllipse(c, 46 + 20 * t, 46 + 20 * t)

        name = "check" if self._state == "success" else "fingerprint"
        size = max(8, int(54 * self._pop.value))
        pm: QPixmap = icons.pixmap(name, size, base, self.devicePixelRatioF(), 1.6)
        p.drawPixmap(QPointF(c.x() - size / 2, c.y() - size / 2), pm)


class LockScreen(QWidget):
    unlocked = Signal(str)  # optional note to show once inside

    def __init__(self, auth: auth_mod.AuthStore, parent: QWidget | None = None):
        super().__init__(parent)
        self.auth = auth
        self._pending_password = ""
        self._token: int | None = None
        self._cooldown = QTimer(self)
        self._cooldown.setInterval(1000)
        self._cooldown.timeout.connect(self._tick_cooldown)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.addStretch(1)
        mark = QLabel()
        mark.setPixmap(icons.brand_pixmap(72, 2.0))
        mark.setFixedSize(72, 72)
        outer.addWidget(mark, 0, CENTER)
        outer.addSpacing(22)
        self.stack = QStackedWidget()
        self.stack.setFixedWidth(360)
        outer.addWidget(self.stack, 0, CENTER)
        outer.addStretch(2)

        self.stack.addWidget(self._build_create())
        self.stack.addWidget(self._build_enroll())
        self.stack.addWidget(self._build_bio())
        self.stack.addWidget(self._build_password())

    # ------------------------------------------------------------------ pages
    @staticmethod
    def _page() -> tuple[QWidget, QVBoxLayout]:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        return page, lay

    def _build_create(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(Text("Welcome to Jinsei", "largeTitle", center=True))
        lay.addSpacing(6)
        lay.addWidget(Text("Create a password to protect your files.", "body", "secondary", center=True, wrap=True))
        lay.addSpacing(28)
        self.new_pw = PasswordField("Password")
        self.new_pw2 = PasswordField("Confirm password")
        lay.addWidget(self.new_pw)
        lay.addSpacing(10)
        lay.addWidget(self.new_pw2)
        lay.addSpacing(14)
        self.hint_len = Hint(f"At least {auth_mod.MIN_PASSWORD_LENGTH} characters")
        self.hint_match = Hint("Passwords match")
        lay.addWidget(self.hint_len)
        lay.addWidget(self.hint_match)
        lay.addSpacing(18)
        self.btn_continue = make_button("Continue", "primary", large=True)
        self.btn_continue.setEnabled(False)
        lay.addWidget(self.btn_continue)
        lay.addStretch()
        self.new_pw.textChanged.connect(self._validate_create)
        self.new_pw2.textChanged.connect(self._validate_create)
        self.new_pw.returnPressed.connect(lambda: self.new_pw2.setFocus())
        self.new_pw2.returnPressed.connect(self._create_continue)
        self.btn_continue.clicked.connect(self._create_continue)
        return page

    def _build_enroll(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(Text("Set Up Fingerprint", "largeTitle", center=True))
        lay.addSpacing(6)
        lay.addWidget(Text("Jinsei will ask for your fingerprint every time you open it.", "body", "secondary",
                           center=True, wrap=True))
        lay.addSpacing(18)
        self.badge_enroll = FingerprintBadge()
        lay.addWidget(self.badge_enroll, 0, CENTER)
        self.enroll_status = Text("", "callout", "secondary", center=True, wrap=True)
        self.enroll_status.setMinimumHeight(40)
        lay.addWidget(self.enroll_status)
        lay.addSpacing(8)
        self.btn_enroll = make_button("Set Up Fingerprint", "primary", large=True)
        self.btn_skip = make_button("Continue with Password Only", "plain")
        self.btn_skip.hide()
        btn_back = make_button("Back", "plain")
        lay.addWidget(self.btn_enroll)
        lay.addSpacing(4)
        lay.addWidget(self.btn_skip)
        lay.addWidget(btn_back)
        lay.addSpacing(10)
        lay.addWidget(Text("Your fingerprint is handled by Windows Hello and never leaves this PC. "
                           "Jinsei doesn\u2019t see or store it.", "caption", "tertiary", center=True, wrap=True))
        lay.addStretch()
        self.btn_enroll.clicked.connect(self._enroll)
        self.btn_skip.clicked.connect(lambda: self._finish_setup(False, FALLBACK_NOTE))
        btn_back.clicked.connect(self._enroll_back)
        return page

    def _build_bio(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(Text("Unlock Jinsei", "largeTitle", center=True))
        lay.addSpacing(6)
        lay.addWidget(Text("Use your fingerprint to continue.", "body", "secondary", center=True))
        lay.addSpacing(18)
        self.badge_unlock = FingerprintBadge()
        lay.addWidget(self.badge_unlock, 0, CENTER)
        self.bio_status = Text("", "callout", "secondary", center=True, wrap=True)
        self.bio_status.setMinimumHeight(40)
        lay.addWidget(self.bio_status)
        lay.addSpacing(8)
        self.btn_retry = make_button("Try Again", "secondary", "fingerprint", large=True)
        self.btn_retry.hide()
        btn_use_pw = make_button("Use Password", "plain")
        lay.addWidget(self.btn_retry)
        lay.addSpacing(4)
        lay.addWidget(btn_use_pw)
        lay.addStretch()
        self.btn_retry.clicked.connect(self._scan_unlock)
        btn_use_pw.clicked.connect(self._show_password_unlock)
        return page

    def _build_password(self) -> QWidget:
        page, lay = self._page()
        lay.addWidget(Text("Enter Password", "largeTitle", center=True))
        lay.addSpacing(6)
        lay.addWidget(Text("Your password unlocks Jinsei.", "body", "secondary", center=True))
        lay.addSpacing(28)
        self.unlock_pw = PasswordField("Password")
        lay.addWidget(self.unlock_pw)
        self.pw_status = Text("", "callout", "danger", center=True, wrap=True)
        self.pw_status.setMinimumHeight(40)
        lay.addSpacing(6)
        lay.addWidget(self.pw_status)
        self.btn_unlock = make_button("Unlock", "primary", large=True)
        self.btn_unlock.setEnabled(False)
        self.btn_use_bio = make_button("Use Fingerprint", "plain", "fingerprint")
        lay.addWidget(self.btn_unlock)
        lay.addSpacing(4)
        lay.addWidget(self.btn_use_bio)
        lay.addStretch()
        self.unlock_pw.textChanged.connect(self._unlock_text_changed)
        self.unlock_pw.returnPressed.connect(self._submit_password)
        self.btn_unlock.clicked.connect(self._submit_password)
        self.btn_use_bio.clicked.connect(self._show_bio_unlock)
        return page

    # ------------------------------------------------------------------ routing
    def start(self) -> None:
        """Called at launch and every time the app is locked."""
        self._cancel_bio()
        self._cooldown.stop()
        self._pending_password = ""
        for field in (self.new_pw, self.new_pw2, self.unlock_pw):
            field.clear()
        if not self.auth.is_configured():
            self._reset_create()
            self._goto(PAGE_CREATE, self.new_pw)
        elif self.auth.biometric_enabled():
            self._show_bio_unlock()
        else:
            self._show_password_unlock()

    def _goto(self, index: int, focus: QWidget | None = None, animate: bool = True) -> None:
        self.stack.setCurrentIndex(index)
        if animate:
            fade_in(self.stack, 220)
        if focus is not None:
            QTimer.singleShot(0, focus.setFocus)

    def _cancel_bio(self) -> None:
        runner().cancel(self._token)
        self._token = None

    def _finish(self, note: str = "") -> None:
        self._cancel_bio()
        self.unlocked.emit(note)

    # ------------------------------------------------------------------ first-run: password
    def _reset_create(self) -> None:
        self.btn_continue.setText("Continue")
        self._validate_create()

    def _validate_create(self, *_args) -> None:
        pw, confirm = self.new_pw.text(), self.new_pw2.text()
        ok_len = len(pw) >= auth_mod.MIN_PASSWORD_LENGTH
        ok_match = bool(confirm) and pw == confirm
        self.hint_len.set_ok(ok_len)
        self.hint_match.set_ok(ok_match)
        busy = self.btn_continue.text() != "Continue"
        self.btn_continue.setEnabled(ok_len and ok_match and not busy)

    def _create_continue(self) -> None:
        if not self.btn_continue.isEnabled():
            return
        self._pending_password = self.new_pw.text()
        self.btn_continue.setText("Checking\u2026")
        self.btn_continue.setEnabled(False)
        self._cancel_bio()
        self._token = runner().run(biometrics.check_availability, callback=self._on_availability)

    def _on_availability(self, res: biometrics.BioResult) -> None:
        self._token = None
        self._reset_create()
        if res.status in ("available", "busy"):
            self.badge_enroll.set_state("idle")
            self.enroll_status.setText("")
            set_tone(self.enroll_status, "secondary")
            self.btn_skip.hide()
            self.btn_enroll.setEnabled(True)
            self._goto(PAGE_ENROLL, self.btn_enroll)
        else:
            self._finish_setup(False, FALLBACK_NOTE)

    # ------------------------------------------------------------------ first-run: fingerprint
    def _enroll(self) -> None:
        self.badge_enroll.set_state("scanning")
        self.enroll_status.setText("Waiting for Windows Hello\u2026")
        set_tone(self.enroll_status, "secondary")
        self.btn_enroll.setEnabled(False)
        self.btn_skip.hide()
        self._cancel_bio()
        self._token = runner().run(biometrics.verify, "Register your fingerprint for Jinsei",
                                   callback=self._on_enroll)

    def _on_enroll(self, res: biometrics.BioResult) -> None:
        self._token = None
        self.btn_enroll.setEnabled(True)
        if res.status == "verified":
            self.badge_enroll.set_state("success")
            self.enroll_status.setText("Fingerprint registered")
            set_tone(self.enroll_status, "success")
            QTimer.singleShot(480, lambda: self._finish_setup(True))
            return
        self.badge_enroll.set_state("error")
        self.enroll_status.setText(res.message or "That didn\u2019t work. Try again.")
        set_tone(self.enroll_status, "danger")
        if res.status in ("unavailable", "error"):
            self.btn_skip.show()

    def _enroll_back(self) -> None:
        self._cancel_bio()
        self.badge_enroll.set_state("idle")
        self._goto(PAGE_CREATE, self.new_pw2)

    def _finish_setup(self, biometric: bool, note: str = "") -> None:
        try:
            self.auth.create_account(self._pending_password, biometric)
        except (ValueError, OSError) as exc:
            self.enroll_status.setText(f"Couldn\u2019t save your settings: {exc}")
            set_tone(self.enroll_status, "danger")
            return
        self._pending_password = ""
        self._finish(note)

    # ------------------------------------------------------------------ unlock: fingerprint
    def _show_bio_unlock(self) -> None:
        self._cancel_bio()
        self.badge_unlock.set_state("idle")
        self.bio_status.setText("")
        self.btn_retry.hide()
        self._goto(PAGE_BIO)
        QTimer.singleShot(350, self._scan_unlock_if_visible)

    def _scan_unlock_if_visible(self) -> None:
        if self.stack.currentIndex() == PAGE_BIO and self._token is None:
            self._scan_unlock()

    def _scan_unlock(self) -> None:
        self.badge_unlock.set_state("scanning")
        self.bio_status.setText("Waiting for fingerprint\u2026")
        set_tone(self.bio_status, "secondary")
        self.btn_retry.hide()
        self._cancel_bio()
        self._token = runner().run(biometrics.verify, "Unlock Jinsei", callback=self._on_unlock_bio)

    def _on_unlock_bio(self, res: biometrics.BioResult) -> None:
        self._token = None
        if res.status == "verified":
            if not self.auth.biometric_user_matches():
                self._bio_failed("This fingerprint lock belongs to another Windows account. Use your password.")
                return
            self.badge_unlock.set_state("success")
            self.bio_status.setText("Unlocked")
            set_tone(self.bio_status, "success")
            QTimer.singleShot(380, lambda: self._finish(""))
        else:
            self._bio_failed(res.message or "Fingerprint not recognised. Try again or use your password.")

    def _bio_failed(self, message: str) -> None:
        self.badge_unlock.set_state("error")
        self.bio_status.setText(message)
        set_tone(self.bio_status, "danger")
        self.btn_retry.show()

    # ------------------------------------------------------------------ unlock: password
    def _show_password_unlock(self) -> None:
        self._cancel_bio()
        self.unlock_pw.clear()
        self.pw_status.setText("")
        self.btn_use_bio.setVisible(self.auth.biometric_enabled())
        self._goto(PAGE_PASSWORD, self.unlock_pw)
        if self.auth.lock_remaining() > 0:
            self._begin_cooldown()

    def _unlock_text_changed(self, text: str) -> None:
        self.btn_unlock.setEnabled(bool(text) and not self._cooldown.isActive())
        if text and not self._cooldown.isActive():
            self.pw_status.setText("")

    def _submit_password(self) -> None:
        password = self.unlock_pw.text()
        if not password or self._cooldown.isActive():
            return
        result = self.auth.verify_password(password)
        if result.ok:
            self.unlock_pw.clear()
            self._finish("")
            return
        self.unlock_pw.clear()
        set_invalid(self.unlock_pw, True)
        if result.locked_for:
            self._begin_cooldown()
        else:
            self.pw_status.setText("Incorrect password.")
        shake(self.unlock_pw)

    def _begin_cooldown(self) -> None:
        self.unlock_pw.setEnabled(False)
        self.btn_unlock.setEnabled(False)
        self._cooldown.start()
        self._tick_cooldown()

    def _tick_cooldown(self) -> None:
        remaining = self.auth.lock_remaining()
        if remaining <= 0:
            self._cooldown.stop()
            self.unlock_pw.setEnabled(True)
            self.pw_status.setText("")
            self.unlock_pw.setFocus()
            return
        self.pw_status.setText(f"Too many attempts. Try again in {auth_mod.format_wait(remaining)}.")

    # ------------------------------------------------------------------ painting
    def paintEvent(self, _e) -> None:
        p = QPainter(self)
        p.fillRect(self.rect(), theme.color("bg"))
        glow = QRadialGradient(QPointF(self.width() / 2, self.height() * 0.36), max(self.width(), self.height()) * 0.55)
        a = theme.color("accent")
        a.setAlpha(46 if theme.dark else 30)
        glow.setColorAt(0.0, a)
        a.setAlpha(0)
        glow.setColorAt(1.0, a)
        p.fillRect(self.rect(), QBrush(glow))
