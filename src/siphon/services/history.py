"""URL history persistence (yoinks F18, upgraded in M7 to JSONL with metadata).

Layout: newline-delimited JSON (``history.jsonl``) at
:func:`siphon.config.paths.history_file`, newest-first, capped at
:data:`~siphon.config.constants.HISTORY_LIMIT`, deduped by URL.

Backwards compat: on startup the loader also accepts the M3 ``history.json``
bare-string-array format. When either is loaded and a write happens, the
loader migrates to JSONL and the legacy file is deleted.

All read errors (missing file, malformed JSON, wrong shape, non-string
entries) return an empty list — history is a *nicety* per yoinks; a corrupt
file must never take down the app. All write errors are swallowed for the
same reason.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import Any

from siphon.config import paths
from siphon.config.constants import HISTORY_LIMIT
from siphon.models.history_entry import HistoryEntry


def history_file_jsonl_path() -> Path:
    """Return the JSONL history path (co-located with the legacy JSON file)."""
    legacy = paths.history_file()
    return legacy.with_name("history.jsonl")


def load_entries() -> list[HistoryEntry]:
    """Return the persisted history as :class:`HistoryEntry` objects.

    Prefers the JSONL format when present; falls back to the legacy JSON
    array. Returns ``[]`` on any parse failure.
    """
    jsonl = history_file_jsonl_path()
    if jsonl.exists():
        return _load_jsonl(jsonl)

    legacy = paths.history_file()
    if legacy.exists():
        return _load_legacy(legacy)

    return []


def load_history() -> list[str]:
    """Backwards-compatible ``list[str]`` view used by the URL input widget."""
    return [entry.url for entry in load_entries()]


def add_to_history(
    url: str,
    existing: list[str] | None = None,
    *,
    title: str | None = None,
    platform: str | None = None,
) -> list[str]:
    """Prepend ``url`` to the history, dedup, cap, and persist.

    ``existing`` seeds the URL-only list for callers that already have it in
    memory. Metadata comes from ``title`` / ``platform`` when the caller
    knows them (e.g. from the probe result).
    """
    current_entries = load_entries()
    filtered = [entry for entry in current_entries if entry.url != url]
    new_entry = HistoryEntry(url=url, title=title, platform=platform)
    updated_entries = [new_entry, *filtered][:HISTORY_LIMIT]

    with contextlib.suppress(OSError):
        _persist(updated_entries)

    # If the caller passed a pre-existing list, respect its order for the
    # returned list (backwards-compat for the M3 caller).
    if existing is not None:
        cur = list(existing)
        cur = [u for u in cur if u != url]
        cur = [url, *cur][:HISTORY_LIMIT]
        return cur
    return [entry.url for entry in updated_entries]


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def _load_jsonl(path: Path) -> list[HistoryEntry]:
    """Parse a JSONL history file, one entry per line."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return []
    entries: list[HistoryEntry] = []
    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            data: Any = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        entry = HistoryEntry.from_dict(data)
        if entry is not None:
            entries.append(entry)
    return entries


def _load_legacy(path: Path) -> list[HistoryEntry]:
    """Parse the M3 bare-array JSON format into :class:`HistoryEntry` objects."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return []
    if not isinstance(raw, list):
        return []
    return [HistoryEntry(url=item) for item in raw if isinstance(item, str) and item]


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
def _persist(entries: list[HistoryEntry]) -> None:
    """Atomically write ``entries`` to the JSONL file; delete the legacy JSON."""
    path = history_file_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = "\n".join(json.dumps(entry.to_dict(), ensure_ascii=False) for entry in entries)
    payload = (lines + "\n") if lines else ""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    tmp.replace(path)

    # Migration cleanup: once the JSONL is safely on disk, drop the legacy JSON.
    legacy = paths.history_file()
    if legacy.exists():
        with contextlib.suppress(OSError):
            legacy.unlink()
