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
    DownloadSucceeded,
)

if TYPE_CHECKING:
    from textual.screen import Screen


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
    """Run a download and post the outcome back to ``screen`` as messages."""
    app = screen.app

    def on_progress(progress: DownloadProgress) -> None:
        # Hook fires from the yt-dlp thread; marshal onto the main loop.
        app.call_from_thread(screen.post_message, DownloadProgressTick(progress))

    def on_processing() -> None:
        app.call_from_thread(screen.post_message, DownloadProcessing())

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
        screen.post_message(DownloadFailed(exc.user_message))
        return
    except Exception as exc:  # pragma: no cover — safety net
        screen.post_message(DownloadFailed(str(exc) or "yt-dlp failed"))
        return

    screen.post_message(DownloadSucceeded(filepath, title=title))
