"""Download progress snapshot passed from yt-dlp hooks to the UI.

Frozen dataclass so a reactive assignment always sees a new object identity
(Textual's reactive checks by ``!=`` on some paths and by ``is`` on others —
staying immutable dodges both cliffs).

The four fields yt-dlp fills for us during a ``download`` are:

* ``downloaded_bytes`` — cumulative for the *current* file. When yt-dlp moves
  from the video stream to the audio stream (a merged download), this
  counter resets — that's how we know a new part started.
* ``total_bytes`` — total for the current file (may be ``None`` while probing).
* ``speed`` — bytes/second, may be ``None`` between ticks.
* ``eta`` — seconds until finished, ``None`` when unknown.

We also carry ``part`` / ``total_parts`` so the UI can render "part 1/2" when
yt-dlp is muxing.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DownloadProgress:
    """One tick of download progress (F14)."""

    downloaded_bytes: int | None = None
    total_bytes: int | None = None
    speed: float | None = None
    eta: float | None = None
    part: int = 1
    total_parts: int = 1

    @property
    def has_total(self) -> bool:
        """True iff we know how much data the current file will contain."""
        return self.total_bytes is not None and self.total_bytes > 0

    @property
    def has_bytes(self) -> bool:
        """True iff yt-dlp has reported *any* downloaded bytes for this file."""
        return self.downloaded_bytes is not None and self.downloaded_bytes >= 0

    @property
    def fraction(self) -> float:
        """Fraction of the *current* file downloaded, clamped to ``[0, 1]``."""
        if not self.has_total or self.downloaded_bytes is None or self.total_bytes is None:
            return 0.0
        if self.total_bytes <= 0:
            return 0.0
        return max(0.0, min(1.0, self.downloaded_bytes / self.total_bytes))

    @property
    def percent(self) -> int:
        """Percentage 0 to 100 for label display."""
        return round(self.fraction * 100)
