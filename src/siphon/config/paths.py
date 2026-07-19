"""XDG-aware path resolution.

The runtime layout mirrors yoinks with a ``siphon`` prefix:

* ``$XDG_CONFIG_HOME/siphon/`` — ``config.toml`` and ``history.json`` (later ``history.jsonl``).
* ``$XDG_DOWNLOAD_DIR`` / ``~/Downloads`` — default output directory.
* ``$TMPDIR`` (or the platform equivalent) — probe cache and other short-lived files.

Every helper here returns a :class:`pathlib.Path` and is safe to call before the
directory exists — call sites are expected to ``mkdir(parents=True, exist_ok=True)``
themselves at write time. Reading these values does not touch the filesystem.
"""

from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str) -> Path | None:
    """Return the value of ``$name`` as a Path, or ``None`` when unset/empty."""
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return None
    return Path(raw).expanduser()


def config_dir() -> Path:
    """The Siphon config directory (``$XDG_CONFIG_HOME/siphon`` or ``~/.config/siphon``)."""
    base = _env_path("XDG_CONFIG_HOME") or (Path.home() / ".config")
    return base / "siphon"


def config_file() -> Path:
    """Full path to ``config.toml`` inside :func:`config_dir`."""
    return config_dir() / "config.toml"


def history_file() -> Path:
    """Path to the JSON history file (parity with yoinks)."""
    return config_dir() / "history.json"


def default_download_dir() -> Path:
    """Default download directory.

    Honours ``$XDG_DOWNLOAD_DIR`` first, then falls back to ``~/Downloads``.
    """
    return _env_path("XDG_DOWNLOAD_DIR") or (Path.home() / "Downloads")


def themes_dir() -> Path:
    """Directory for user-supplied TCSS theme files (loaded in M7)."""
    return config_dir() / "themes"
