"""Wrap ``YoutubeDL.download`` with progress + postprocessor hooks (yoinks F13).

The synchronous entry point is :func:`download`. Callers on the asyncio
event loop schedule it with ``asyncio.to_thread`` (see
:mod:`siphon.workers.download_worker`).

Behaviour parity with yoinks:

* Uses ``progress_hooks`` for byte-level download progress and
  ``postprocessor_hooks`` for Merger / ExtractAudio events — no stdout
  parsing.
* Tracks ``part`` / ``total_parts`` by inspecting ``requested_formats`` and
  by watching for the ``downloaded_bytes`` counter to drop (yt-dlp resets
  it between files during a merge).
* Cancellation: if the token fires, the next hook call raises
  :class:`~siphon.engine.cancellation.DownloadCancelled`, which unwinds
  yt-dlp cleanly and we then remove any partial destination files
  (``dest``, ``dest.part``, ``dest.ytdl``).
* On any :class:`~yt_dlp.utils.DownloadError` that *isn't* a cancellation,
  raises :class:`~siphon.engine.errors.CleanedYtdlpError` carrying the
  user-facing message.

The public API takes ``on_progress`` / ``on_processing`` callbacks; the
worker layer wires those to Textual messages posted via ``call_from_thread``.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from siphon.engine.cancellation import CancellationToken, DownloadCancelled
from siphon.engine.errors import CleanedYtdlpError, clean_ytdlp_error
from siphon.models.choice import DownloadChoice
from siphon.models.progress import DownloadProgress

_logger = logging.getLogger(__name__)


OUT_TEMPLATE = "%(title).60s.%(ext)s"
"""Filename template — 60-char title cap matches yoinks."""


@dataclass
class _HookState:
    """Mutable state threaded through the yt-dlp progress + postprocessor hooks."""

    on_progress: Callable[[DownloadProgress], None] | None
    on_processing: Callable[[], None] | None
    token: CancellationToken | None
    total_parts: int = 1
    current_part: int = 1
    last_downloaded: int = 0
    destinations: list[str] = field(default_factory=list)
    final_filepath: str | None = None

    # ------------------------------------------------------------ progress
    def hook_progress(self, data: dict[str, Any]) -> None:
        """yt-dlp calls this every progress tick (from the download thread)."""
        self._raise_if_cancelled()

        info_dict = data.get("info_dict") or {}
        req = info_dict.get("requested_formats")
        if isinstance(req, list) and len(req) > self.total_parts:
            self.total_parts = len(req)

        status = data.get("status")
        if status == "downloading":
            downloaded = _as_int(data.get("downloaded_bytes"))
            total = _as_int(data.get("total_bytes")) or _as_int(data.get("total_bytes_estimate"))
            speed = _as_float(data.get("speed"))
            eta = _as_float(data.get("eta"))

            # Detect part boundary — yt-dlp resets ``downloaded_bytes`` at
            # the start of each new file during a merge.
            if (
                downloaded is not None
                and downloaded < self.last_downloaded
                and self.current_part < self.total_parts
            ):
                self.current_part += 1
                self.last_downloaded = 0

            if downloaded is not None:
                self.last_downloaded = downloaded

            progress = DownloadProgress(
                downloaded_bytes=downloaded,
                total_bytes=total,
                speed=speed,
                eta=eta,
                part=self.current_part,
                total_parts=self.total_parts,
            )
            if self.on_progress is not None:
                self.on_progress(progress)

        elif status == "finished":
            # One file completed (may be one of several parts during a merge).
            filename = data.get("filename") or info_dict.get("_filename")
            if isinstance(filename, str):
                self.destinations.append(filename)
                # Provisional — postprocessor hook overrides for merged output.
                self.final_filepath = filename

        # ``status == "error"`` is left alone — yt-dlp will raise on its own.

    # --------------------------------------------------------- postprocess
    def hook_processing(self, data: dict[str, Any]) -> None:
        """yt-dlp calls this at Merger / ExtractAudio start / finish."""
        self._raise_if_cancelled()

        status = data.get("status")
        if status in ("started", "processing") and self.on_processing is not None:
            self.on_processing()
        elif status == "finished":
            info = data.get("info_dict") or {}
            filepath = info.get("filepath") or info.get("_filename")
            if isinstance(filepath, str):
                self.final_filepath = filepath
                self.destinations.append(filepath)

    def _raise_if_cancelled(self) -> None:
        if self.token is not None and self.token.cancelled:
            raise DownloadCancelled("download cancelled by user")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def download(
    *,
    url: str,
    choice: DownloadChoice,
    output_dir: Path,
    ffmpeg_location: str | None = None,
    on_progress: Callable[[DownloadProgress], None] | None = None,
    on_processing: Callable[[], None] | None = None,
    token: CancellationToken | None = None,
) -> Path:
    """Blocking. Download ``url`` with ``choice`` to ``output_dir``.

    Returns the final :class:`~pathlib.Path` written by yt-dlp.

    Raises
    ------
    DownloadCancelled
        If the cancellation token fires — partial files are cleaned before
        the exception propagates.
    CleanedYtdlpError
        On any yt-dlp failure. Carries a user-facing single-line message.
    """
    from yt_dlp import YoutubeDL  # noqa: PLC0415 — lazy for startup speed
    from yt_dlp.utils import DownloadError  # noqa: PLC0415

    output_dir.mkdir(parents=True, exist_ok=True)

    state = _HookState(on_progress=on_progress, on_processing=on_processing, token=token)

    opts: dict[str, Any] = {
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "outtmpl": str(output_dir / OUT_TEMPLATE),
        "progress_hooks": [state.hook_progress],
        "postprocessor_hooks": [state.hook_processing],
        "logger": _SilentLogger(),
    }
    if ffmpeg_location:
        opts["ffmpeg_location"] = ffmpeg_location
    # Choice-specific overrides last so they win any collisions.
    opts.update(choice.ytdlp_opts)

    try:
        with YoutubeDL(opts) as ydl:
            ydl.download([url])
    except DownloadCancelled:
        _cleanup_partials(state.destinations)
        raise
    except DownloadError as exc:
        if token is not None and token.cancelled:
            _cleanup_partials(state.destinations)
            raise DownloadCancelled("download cancelled by user") from exc
        raise CleanedYtdlpError(clean_ytdlp_error(str(exc)), original=exc) from exc
    except Exception as exc:  # pragma: no cover — belt-and-braces
        if token is not None and token.cancelled:
            _cleanup_partials(state.destinations)
            raise DownloadCancelled("download cancelled by user") from exc
        _logger.exception("unexpected error downloading %s", url)
        raise CleanedYtdlpError(str(exc) or "yt-dlp failed", original=exc) from exc

    if state.final_filepath is None:
        raise CleanedYtdlpError("yt-dlp completed without emitting a filepath")

    return Path(state.final_filepath)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _cleanup_partials(destinations: list[str]) -> None:
    """Best-effort delete of destination files + ``.part`` / ``.ytdl`` siblings."""
    for dest in destinations:
        p = Path(dest)
        siblings = [
            p,
            Path(str(p) + ".part"),
            Path(str(p) + ".ytdl"),
            Path(str(p) + ".part-Frag1"),  # yt-dlp fragment naming
        ]
        for candidate in siblings:
            with contextlib.suppress(OSError):
                candidate.unlink(missing_ok=True)


def _as_int(value: Any) -> int | None:
    """Coerce a yt-dlp field to int; treat NA/None/non-numeric as ``None``."""
    if value is None or value in ("NA", "None", ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    """Coerce a yt-dlp field to float; treat NA/None/non-numeric as ``None``."""
    if value is None or value in ("NA", "None", ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


class _SilentLogger:
    """Duck-typed logger yt-dlp accepts that discards everything."""

    def debug(self, _msg: str) -> None:
        pass

    def info(self, _msg: str) -> None:
        pass

    def warning(self, _msg: str) -> None:
        pass

    def error(self, _msg: str) -> None:
        pass
