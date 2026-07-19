"""Locate an ``ffmpeg`` binary for yt-dlp to use (yoinks F9).

Resolution order:

1. System ``ffmpeg`` on ``PATH`` — returns ``None`` so yt-dlp finds it itself
   (yoinks parity: passing ``None`` to ``--ffmpeg-location`` is equivalent to
   not passing it, which is what we want).
2. ``imageio-ffmpeg``'s bundled binary — resolved lazily via
   :func:`imageio_ffmpeg.get_ffmpeg_exe`.
3. Nothing found — returns ``None``. yt-dlp still works for single-file
   formats that don't need muxing (audio-only extraction requires ffmpeg).

The result is cached at module scope because the lookup is not free
(``imageio_ffmpeg.get_ffmpeg_exe`` triggers a download on first use).
"""

from __future__ import annotations

import shutil
from functools import lru_cache


@lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    """Return an ffmpeg binary path, or ``None`` when the system one is on PATH.

    Distinguish "on PATH" from "not found" via the sentinel ``None``:
    passing ``ffmpeg_location=None`` to ``YoutubeDL`` means "use PATH", while
    passing a concrete path forces yt-dlp to use it directly.
    """
    if shutil.which("ffmpeg") is not None:
        return None
    try:
        import imageio_ffmpeg  # noqa: PLC0415 — lazy for startup speed
    except ImportError:
        return None
    try:
        exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        # imageio may fail for many reasons (missing binary cache, permission
        # error, network error on first-run download). Degrade quietly.
        return None
    return exe if exe else None


def reset_cache() -> None:
    """Drop the cached lookup. Used by tests to swap the environment."""
    find_ffmpeg.cache_clear()
