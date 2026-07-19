"""Wrap ``YoutubeDL.extract_info`` in a cancellable, error-cleaned probe.

The synchronous entry point is :func:`probe_sync` — it runs
``extract_info(url, download=False)`` on the *calling* thread and returns
the info dict. Callers on the asyncio event loop should schedule it with
``asyncio.to_thread`` or a Textual thread worker.

Errors are wrapped in :class:`~siphon.engine.errors.CleanedYtdlpError` so
the UI can present a single-line message without doing its own regex
extraction.
"""

from __future__ import annotations

import contextlib
import io
import logging
from typing import Any

from siphon.engine.cancellation import CancellationToken, DownloadCancelled
from siphon.engine.errors import CleanedYtdlpError, clean_ytdlp_error

_logger = logging.getLogger(__name__)


def probe_sync(url: str, token: CancellationToken | None = None) -> dict[str, Any]:
    """Fetch a yt-dlp info dict for ``url``. Blocking.

    Parameters
    ----------
    url:
        A validated ``http(s)://`` URL.
    token:
        Optional cancellation token; when set before the extraction runs,
        raises :class:`DownloadCancelled` without hitting the network.

    Raises
    ------
    DownloadCancelled
        If ``token`` was cancelled prior to starting the extraction.
    CleanedYtdlpError
        On any yt-dlp failure — carries a user-facing ``.user_message``.
    """
    if token is not None and token.cancelled:
        raise DownloadCancelled("probe cancelled before start")

    # Local import so pytest collection doesn't pay yt-dlp's ~1s import cost
    # for tests that don't need it.
    from yt_dlp import YoutubeDL  # noqa: PLC0415
    from yt_dlp.utils import DownloadError  # noqa: PLC0415

    stderr_buf = io.StringIO()
    opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "logger": _SilentLogger(),
    }

    try:
        with contextlib.redirect_stderr(stderr_buf), YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as exc:
        message = clean_ytdlp_error(str(exc) or stderr_buf.getvalue())
        raise CleanedYtdlpError(message, original=exc) from exc
    except Exception as exc:  # pragma: no cover — defensive catch-all
        _logger.exception("unexpected error probing %s", url)
        raise CleanedYtdlpError(str(exc) or "yt-dlp failed", original=exc) from exc

    if not isinstance(info, dict):
        raise CleanedYtdlpError("Could not parse video info from yt-dlp.")

    # yt-dlp may return a "playlist" info dict with an ``entries`` list even
    # when ``noplaylist=True`` for certain URLs — pick the first entry so the
    # picker still has formats to render.
    if "formats" not in info and info.get("entries"):
        first = next((entry for entry in info["entries"] if isinstance(entry, dict)), None)
        if first is not None:
            info = first

    return info


class _SilentLogger:
    """A minimal logger yt-dlp accepts that discards everything."""

    def debug(self, _msg: str) -> None:
        pass

    def info(self, _msg: str) -> None:
        pass

    def warning(self, _msg: str) -> None:
        pass

    def error(self, _msg: str) -> None:
        pass
