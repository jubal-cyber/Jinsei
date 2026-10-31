"""Password storage and verification.

The password is never stored. Only a salted scrypt hash is written to
%APPDATA%/Jinsei/auth.json, together with whether fingerprint lock is on and
a persistent failed-attempt counter.
"""
from __future__ import annotations

import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

MIN_PASSWORD_LENGTH = 8
FREE_ATTEMPTS = 5
BASE_LOCKOUT_SECONDS = 30
MAX_LOCKOUT_SECONDS = 15 * 60


def config_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return root / "Jinsei"


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    locked_for: int = 0  # seconds the person must wait, when locked out


def format_wait(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = -(-seconds // 60)
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _derive(password: str, salt: bytes, params: dict) -> bytes:
    pw = unicodedata.normalize("NFC", password).encode("utf-8")
    if params["algo"] == "scrypt":
        return hashlib.scrypt(pw, salt=salt, n=params["n"], r=params["r"], p=params["p"],
                              dklen=32, maxmem=64 * 1024 * 1024)
    return hashlib.pbkdf2_hmac("sha256", pw, salt, params["iterations"], dklen=32)


def _new_record(password: str) -> dict:
    salt = secrets.token_bytes(16)
    if hasattr(hashlib, "scrypt"):
        params = {"algo": "scrypt", "n": 2 ** 14, "r": 8, "p": 1}
    else:  # pragma: no cover - Python built without OpenSSL scrypt
        params = {"algo": "pbkdf2", "iterations": 600_000}
    digest = _derive(password, salt, params)
    return {**params, "salt": _b64(salt), "hash": _b64(digest)}


def _matches(password: str, record: dict) -> bool:
    salt = base64.b64decode(record["salt"])
    expected = base64.b64decode(record["hash"])
    return hmac.compare_digest(_derive(password, salt, record), expected)


def _windows_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return ""


class AuthStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config_dir() / "auth.json"
        self._data = self._read()

    # ---- persistence -------------------------------------------------
    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError):
            try:  # keep the unreadable file, start clean
                self.path.replace(self.path.with_suffix(".json.damaged"))
            except OSError:
                pass
            return {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        try:
            os.chmod(tmp, 0o600)
        except OSError:
            pass
        os.replace(tmp, self.path)

    # ---- state -------------------------------------------------------
    def is_configured(self) -> bool:
        return "password" in self._data

    def biometric_enabled(self) -> bool:
        return bool(self._data.get("biometric", {}).get("enabled"))

    def biometric_user_matches(self) -> bool:
        saved = self._data.get("biometric", {}).get("windows_user", "")
        return not saved or saved == _windows_user()

    @staticmethod
    def password_problem(password: str) -> str | None:
        if len(password) < MIN_PASSWORD_LENGTH:
            return f"Use at least {MIN_PASSWORD_LENGTH} characters."
        return None

    # ---- setup -------------------------------------------------------
    def create_account(self, password: str, biometric: bool) -> None:
        problem = self.password_problem(password)
        if problem:
            raise ValueError(problem)
        self._data = {"version": 1, "password": _new_record(password), "security": {"failed": 0, "locked_until": 0}}
        if biometric:
            self._set_biometric()
        self._save()

    def enable_biometric(self) -> None:
        self._set_biometric()
        self._save()

    def _set_biometric(self) -> None:
        self._data["biometric"] = {
            "enabled": True,
            "windows_user": _windows_user(),
            "enrolled_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    # ---- verification ------------------------------------------------
    def lock_remaining(self) -> int:
        until = self._data.get("security", {}).get("locked_until", 0)
        return max(0, int(round(until - time.time())))

    def verify_password(self, password: str) -> VerifyResult:
        remaining = self.lock_remaining()
        if remaining > 0:
            return VerifyResult(False, remaining)
        security = self._data.setdefault("security", {"failed": 0, "locked_until": 0})
        if _matches(password, self._data["password"]):
            if security.get("failed") or security.get("locked_until"):
                security.update(failed=0, locked_until=0)
                self._save()
            return VerifyResult(True)
        security["failed"] = security.get("failed", 0) + 1
        wait = 0
        if security["failed"] >= FREE_ATTEMPTS:
            wait = min(MAX_LOCKOUT_SECONDS, BASE_LOCKOUT_SECONDS * 2 ** (security["failed"] - FREE_ATTEMPTS))
            security["locked_until"] = time.time() + wait
        self._save()
        return VerifyResult(False, wait)

    def change_password(self, current: str, new: str) -> VerifyResult:
        problem = self.password_problem(new)
        if problem:
            raise ValueError(problem)
        result = self.verify_password(current)
        if result.ok:
            self._data["password"] = _new_record(new)
            self._save()
        return result
