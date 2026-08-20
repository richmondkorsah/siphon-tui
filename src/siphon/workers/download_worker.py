"""Async wrapper around :func:`siphon.engine.downloader.download`.

Runs the blocking yt-dlp call in a background thread via
:func:`asyncio.to_thread`, and pipes progress + terminal events back to the
:class:`~textual.screen.Screen` as Textual messages.

Hook thread-safety: the ``on_progress`` / ``on_processing`` callbacks passed
to the engine are invoked *inside the yt-dlp thread*. We use
:meth:`App.call_from_thread` to marshal each event onto the main event loop
before posting a message — that's the only safe way to touch widget state
from a background thread.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from siphon.engine.cancellation import CancellationToken, DownloadCancelled
from siphon.engine.downloader import download
from siphon.engine.errors import CleanedYtdlpError
from siphon.models.choice import DownloadChoice
from siphon.models.progress import DownloadProgress
from siphon.ui.messages import (
    DownloadFailed,
    DownloadProcessing,
    DownloadProgressTick,
    DownloadRefreshing,
    DownloadSucceeded,
)

if TYPE_CHECKING:
    from textual.screen import Screen


_STALE_URL_MARKERS = ("http error 403", "forbidden", "expired", "signature")
"""Substrings in a yt-dlp error that indicate the signed URL went stale.

A stale URL means yt-dlp extracted a signed media URL, but by the time the
CDN was hit the token had expired (or was rejected by a different edge).
Re-entering :func:`download` runs a fresh ``extract_info``, which produces
a new signed URL; ``continuedl=True`` then resumes the ``.part``."""

_RATE_LIMIT_MARKERS = ("http error 429", "too many requests")
"""Substrings indicating YouTube rate-limited a request — most commonly the
translation endpoint behind a non-English subtitle track, which is throttled
far more aggressively than the video/audio CDN. Unlike a stale URL, retrying
*immediately* would just get 429'd again, so this path backs off first."""

_RATE_LIMIT_BACKOFF_S = 5.0
"""Pause before retrying a rate-limited download — long enough that YouTube's
short-window limiter has typically reset."""


def _looks_stale(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _STALE_URL_MARKERS)


def _looks_rate_limited(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _RATE_LIMIT_MARKERS)


async def run_download(
    *,
    url: str,
    choice: DownloadChoice,
    title: str,
    output_dir: Path,
    ffmpeg_location: str | None,
    token: CancellationToken,
    screen: Screen[str],
) -> None:
    """Run a download and post the outcome back to ``screen`` as messages.

    Retries the download once on stale-URL errors (403 / expired signature):
    the second call re-extracts and resumes the ``.part`` file, which is the
    fix for the common "signed URL expired mid-download" 403.

    Separately, retries once on a rate-limit error (429 — most often the
    translation endpoint behind a non-English subtitle track) after a short
    backoff: retrying *immediately*, like the stale-URL path does, would
    just get 429'd again since the limiter hasn't had time to reset.
    """
    app = screen.app

    def on_progress(progress: DownloadProgress) -> None:
        # Hook fires from the yt-dlp thread; marshal onto the main loop.
        app.call_from_thread(screen.post_message, DownloadProgressTick(progress))

    def on_processing() -> None:
        app.call_from_thread(screen.post_message, DownloadProcessing())

    stale_retries_left = 1
    rate_limit_retries_left = 1
    while True:
        try:
            filepath = await asyncio.to_thread(
                download,
                url=url,
                choice=choice,
                output_dir=output_dir,
                ffmpeg_location=ffmpeg_location,
                on_progress=on_progress,
                on_processing=on_processing,
                token=token,
            )
        except DownloadCancelled:
            # UI has already reset — no message needed.
            return
        except CleanedYtdlpError as exc:
            if rate_limit_retries_left > 0 and _looks_rate_limited(exc.user_message):
                if token.cancelled:
                    return
                rate_limit_retries_left -= 1
                screen.post_message(
                    DownloadRefreshing(reason="rate limited — pausing before retry…")
                )
                await asyncio.sleep(_RATE_LIMIT_BACKOFF_S)
                if token.cancelled:
                    return
                continue
            if stale_retries_left > 0 and _looks_stale(exc.user_message):
                if token.cancelled:
                    return
                stale_retries_left -= 1
                screen.post_message(DownloadRefreshing())
                continue
            screen.post_message(DownloadFailed(exc.user_message))
            return
        except Exception as exc:  # pragma: no cover — safety net
            screen.post_message(DownloadFailed(str(exc) or "yt-dlp failed"))
            return
        break

    screen.post_message(DownloadSucceeded(filepath, title=title))
