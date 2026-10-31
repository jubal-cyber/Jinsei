"""Windows Hello (fingerprint) wrapper.

Windows keeps fingerprint data inside the operating system; no application can
read or copy it. Jinsei asks Windows Hello to verify the person and records only
that fingerprint lock is on for this Windows account.

Everything here is blocking and Qt-free. Call it from a worker thread.
"""
from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class BioResult:
    # "verified" | "available" | "canceled" | "busy" | "retries" | "unavailable" | "error"
    status: str
    message: str = ""


_AVAILABILITY = {0: "AVAILABLE", 1: "DEVICE_NOT_PRESENT", 2: "NOT_CONFIGURED_FOR_USER",
                 3: "DISABLED_BY_POLICY", 4: "DEVICE_BUSY"}
_VERIFICATION = {0: "VERIFIED", 1: "DEVICE_NOT_PRESENT", 2: "NOT_CONFIGURED_FOR_USER",
                 3: "DISABLED_BY_POLICY", 4: "DEVICE_BUSY", 5: "RETRIES_EXHAUSTED", 6: "CANCELED"}

NOT_WINDOWS = "Windows Hello is only available on Windows."
MISSING = "Windows Hello support isn't installed. Run: pip install -r requirements.txt"
NOT_SET_UP = "Windows Hello fingerprint isn't set up on this PC. Add one in Windows Settings \u203a Accounts \u203a Sign-in options."


def _name(value, table: dict) -> str:
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name.upper()
    try:
        return table.get(int(value), str(value))
    except (TypeError, ValueError):
        return str(value).upper()


def _import_winrt():
    from winrt.windows.security.credentials.ui import UserConsentVerifier  # type: ignore
    return UserConsentVerifier


async def _check() -> BioResult:
    verifier = _import_winrt()
    state = _name(await verifier.check_availability_async(), _AVAILABILITY)
    if state == "AVAILABLE":
        return BioResult("available")
    if state == "DEVICE_BUSY":
        return BioResult("busy", "The fingerprint sensor is busy. Try again.")
    if state == "DISABLED_BY_POLICY":
        return BioResult("unavailable", "Windows Hello is turned off by your organisation.")
    return BioResult("unavailable", NOT_SET_UP)


async def _verify(reason: str) -> BioResult:
    verifier = _import_winrt()
    state = _name(await verifier.request_verification_async(reason), _VERIFICATION)
    if state == "VERIFIED":
        return BioResult("verified")
    if state == "CANCELED":
        return BioResult("canceled", "Fingerprint wasn't confirmed.")
    if state == "RETRIES_EXHAUSTED":
        return BioResult("retries", "Too many attempts. Use your password instead.")
    if state == "DEVICE_BUSY":
        return BioResult("busy", "The fingerprint sensor is busy. Try again.")
    if state == "DISABLED_BY_POLICY":
        return BioResult("unavailable", "Windows Hello is turned off by your organisation.")
    return BioResult("unavailable", NOT_SET_UP)


def _run(coro_factory, *args) -> BioResult:
    if sys.platform != "win32":
        return BioResult("unavailable", NOT_WINDOWS)
    try:
        return asyncio.run(coro_factory(*args))
    except ImportError:
        return BioResult("unavailable", MISSING)
    except Exception as exc:  # WinRT raises OSError subclasses
        return BioResult("error", f"Windows Hello couldn't start ({exc}).")


def check_availability() -> BioResult:
    return _run(_check)


def verify(reason: str) -> BioResult:
    return _run(_verify, reason)
