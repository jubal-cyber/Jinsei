"""Storage layer: the three sections, listing, adding, opening and deleting files."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
IMAGE_DIR = STORAGE_DIR / "images"
DOCUMENT_DIR = STORAGE_DIR / "documents"
TEXT_DIR = STORAGE_DIR / "text"

IGNORED_NAMES = {"desktop.ini", "thumbs.db", ".ds_store"}


@dataclass(frozen=True)
class Section:
    key: str
    label: str
    noun: str            # "image"
    folder: Path
    dialog_title: str
    dialog_filter: str   # empty for Text (uses a sheet instead)
    empty_title: str
    empty_message: str
    icon: str


SECTIONS: dict[str, Section] = {
    "Images": Section(
        "Images", "Images", "image", IMAGE_DIR, "Add Images",
        "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        "No Images", "Photos you add stay here, private and protected.", "image",
    ),
    "Documents": Section(
        "Documents", "Documents", "document", DOCUMENT_DIR, "Add Documents",
        "Documents (*.pdf *.doc *.docx *.txt)",
        "No Documents", "PDFs and Word files you add stay here, private and protected.", "doc",
    ),
    "Text": Section(
        "Text", "Text", "note", TEXT_DIR, "", "",
        "No Notes", "Write down anything you want to keep private.", "text",
    ),
}
ORDER = ("Images", "Documents", "Text")


@dataclass(frozen=True)
class Item:
    section: str
    path: Path
    name: str
    ext: str
    size: int
    mtime: float

    def meta(self, with_date: bool = False) -> str:
        parts = [self.ext or "FILE", human_size(self.size)]
        if with_date:
            parts.append(human_date(self.mtime))
        return " \u00b7 ".join(parts)


def ensure_storage() -> None:
    for section in SECTIONS.values():
        section.folder.mkdir(parents=True, exist_ok=True)


def human_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.0f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 ** 3):.1f} GB"


def human_date(ts: float) -> str:
    d = datetime.fromtimestamp(ts)
    now = datetime.now()
    if d.year == now.year:
        return d.strftime("%b %d").replace(" 0", " ")
    return d.strftime("%b %d, %Y").replace(" 0", " ")


def list_items(section_key: str) -> list[Item]:
    folder = SECTIONS[section_key].folder
    items: list[Item] = []
    if not folder.exists():
        return items
    for path in folder.iterdir():
        if not path.is_file() or path.name.startswith(".") or path.name.lower() in IGNORED_NAMES:
            continue
        try:
            st = path.stat()
        except OSError:
            continue
        items.append(Item(section_key, path, path.stem, path.suffix.lstrip(".").upper(), st.st_size, st.st_mtime))
    items.sort(key=lambda i: i.mtime, reverse=True)
    return items


def count_items(section_key: str) -> int:
    return len(list_items(section_key))


def unique_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem, suffix = Path(filename).stem, Path(filename).suffix
    n = 2
    while True:
        candidate = folder / f"{stem} {n}{suffix}"
        if not candidate.exists():
            return candidate
        n += 1


def add_files(section_key: str, sources: list[Path]) -> list[Path]:
    """Copy files into a section. Existing names are never overwritten."""
    folder = SECTIONS[section_key].folder
    folder.mkdir(parents=True, exist_ok=True)
    added = []
    for source in sources:
        source = Path(source)
        destination = unique_path(folder, source.name)
        shutil.copy2(source, destination)
        added.append(destination)
    return added


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_filename(title: str) -> str:
    cleaned = _INVALID.sub("", title).strip().rstrip(". ")
    return cleaned[:80].strip() or "Untitled"


def add_text(title: str, body: str) -> Path:
    path = unique_path(TEXT_DIR, safe_filename(title) + ".txt")
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


_preview_cache: dict[tuple[str, float], str] = {}


def text_preview(item: Item, limit: int = 360) -> str:
    key = (str(item.path), item.mtime)
    if key not in _preview_cache:
        try:
            with open(item.path, "rb") as fh:
                raw = fh.read(4096)
            text = raw.decode("utf-8", errors="replace").strip()
        except OSError:
            text = ""
        if len(_preview_cache) > 200:
            _preview_cache.clear()
        _preview_cache[key] = text[:600]
    return _preview_cache[key][:limit]


def delete_item(path: Path) -> None:
    """Permanently delete a file, but only if it lives inside the storage folder."""
    target = Path(path).resolve()
    root = STORAGE_DIR.resolve()
    if not target.is_relative_to(root) or target == root:
        raise PermissionError("Refusing to delete a file outside Jinsei's storage.")
    target.unlink()


def open_item(path: Path) -> None:
    if sys.platform == "win32":
        os.startfile(str(path))  # noqa: S606 - same behaviour as before
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
