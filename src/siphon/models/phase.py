"""The phase discriminated union — the state machine at the heart of the app.

Analog of yoinks' ``Phase`` in ``src/app.tsx``. Each phase carries only the
data it needs — no shared "current URL" field: cancellation semantics differ
between phases, so we keep it explicit per phase.

The union is exported as :data:`Phase`; screens use :func:`isinstance` on the
tag classes to render the appropriate body. All variants are frozen so a
``reactive`` swap always sees a new object identity.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from siphon.models.choice import DownloadChoice
from siphon.models.platform import Platform


@dataclass(frozen=True, slots=True)
class InputPhase:
    """The default landing phase — awaiting a URL from the user."""

    warning: str | None = None
    """Shown as a dim ``✗ …`` line under the input; e.g. ``that doesn't look like a link``."""

    clipboard_url: str | None = None
    """A URL currently on the system clipboard, offered via ⇥."""

    clipboard_accepted: bool = False
    """True after the user pressed ⇥; changes the sub-hint text."""


@dataclass(frozen=True, slots=True)
class ProbingPhase:
    """yt-dlp is extracting metadata for the given URL."""

    url: str
    platform: Platform
    status: str = "warming up…"
    """Displayed as the spinner leading text (e.g. ``fetching video info…``)."""


@dataclass(frozen=True, slots=True)
class PickingPhase:
    """The quality/audio picker shown after a successful probe (yoinks F12)."""

    url: str
    platform: Platform
    title: str
    choices: list[DownloadChoice]
    uploader: str | None = None
    duration_s: int | None = None
    info: dict[str, Any] = field(default_factory=dict)
    """Kept for M5's stale-info retry — the download re-uses this dict instead of re-probing."""


@dataclass(frozen=True, slots=True)
class DownloadingPhase:
    """Active download with progress (yoinks F14).

    Progress ticks arrive as messages and update the mounted status widget
    in place — we do NOT rebuild the ``DownloadingPhase`` on every hook call
    (that would tear down and re-mount the bar 30 times a second).
    """

    url: str
    title: str
    choice: DownloadChoice


@dataclass(frozen=True, slots=True)
class DonePhase:
    """Download finished (yoinks F15) — filepath + display title."""

    filepath: Path
    title: str = ""


@dataclass(frozen=True, slots=True)
class ErrorPhase:
    """Terminal error state (M5)."""

    message: str
    context: dict[str, str] = field(default_factory=dict)


Phase = InputPhase | ProbingPhase | PickingPhase | DownloadingPhase | DonePhase | ErrorPhase
"""The full discriminated union of app phases."""
