# Jinsei

A private locker for images, documents and notes.

## Run

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

If `pip` can't find the `winrt-*` packages for your Python version, use Python 3.12 or 3.13.

## First launch

1. Create a password (at least 8 characters).
2. Register your fingerprint with Windows Hello.

After that, Jinsei asks for your fingerprint every time it opens or is locked.
**Use Password** is always available as a fallback if the sensor fails.
If this PC has no fingerprint reader, Jinsei uses the password only, and
Settings offers to turn fingerprint on later if one becomes available.

Five wrong passwords in a row lock password entry for 30 seconds, doubling with each further miss.
The counter survives restarting the app.

## Using it

| | |
|---|---|
| Images / Documents / Text | Sidebar. Counts update live. |
| Add | **Add** button or `Ctrl+N` (Text opens a New Note sheet) |
| Open | Click (opens in your default app, as before) |
| Delete | Hover trash button, right-click, or select + `Delete`. Always asks first. |
| Grid / List | Segmented control, top right |
| Lock now | **Lock Jinsei** in the sidebar, or `Ctrl+L` |
| Change password | Settings > Change Password |

## Where things live

- Your files: `storage/images`, `storage/documents`, `storage/text` (same as before).
- Password hash + fingerprint-lock flag: `%APPDATA%\Jinsei\auth.json`.
  The password itself is never stored (salted scrypt hash only).
  Delete this file to start first-launch setup again.

## Good to know

- **Fingerprints stay in Windows.** No app can read them. Jinsei asks Windows Hello to check
  your finger and stores only "fingerprint lock is on for this Windows account".
  Windows Hello may also accept your Hello PIN or face, depending on how it is set up.
- **Files in `storage/` are not encrypted.** The lock protects opening Jinsei, not the folder on disk.
- Delete is permanent (no Recycle Bin).
- The old hardcoded PIN (`1234`) is gone.

## Layout

```
app.py              entry point
jinsei/theme.py     colours, type, stylesheet (light + dark follow Windows)
jinsei/motion.py    interruptible animations, reduced-motion support
jinsei/widgets.py   tiles, rows, sidebar items, sheets, toast
jinsei/lock.py      first-run setup and unlock
jinsei/settings.py  Settings page
jinsei/sheets.py    New Note, Delete confirmation, Change Password
jinsei/auth.py      password hashing, lockout
jinsei/biometrics.py  Windows Hello wrapper (the one place to adjust if the prompt misbehaves)
jinsei/library.py   file storage
jinsei/assets/      logo: jinsei.png (in-app), jinsei.ico (Windows / PyInstaller)
```
