"""Siphon — a Textual TUI for downloading videos and audio via yt-dlp."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("siphon-tui")
except PackageNotFoundError:  # editable install without metadata, or source tree
    __version__ = "0.0.0+local"

__all__ = ["__version__"]
