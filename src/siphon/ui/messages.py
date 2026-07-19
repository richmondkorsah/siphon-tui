"""Textual messages exchanged between widgets, screens, and the App.

Following Textual's convention — a message is a small dataclass-like class
that inherits from :class:`textual.message.Message`. Widgets post messages
via ``self.post_message(SomeMessage(...))`` and parents subscribe via
``on_some_message(self, event)`` handlers.
"""

from __future__ import annotations

from pathlib import Path

from textual.message import Message

from siphon.models.progress import DownloadProgress


class SubmitRequested(Message):
    """User submitted a URL (enter, click on siphon button, or paste-heuristic).

    Emitted by :class:`~siphon.ui.widgets.text_input.SiphonTextInput` and
    :class:`~siphon.ui.widgets.framed_input.FramedInput`. The screen listens
    and transitions to :class:`~siphon.models.phase.ProbingPhase`.
    """

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url


class HomeRequested(Message):
    """User clicked the logo — behave as ``resetToInput`` (yoinks F17)."""


class CancelRequested(Message):
    """User pressed Esc during probing / downloading (yoinks F17).

    The screen aborts the active worker and returns to input with the URL
    preserved.
    """


class ThemeCycled(Message):
    """The app cycled to a new theme mode — screens may refresh their hints."""

    def __init__(self, mode: str) -> None:
        super().__init__()
        self.mode = mode


class ClipboardAccepted(Message):
    """User pressed ⇥ to take the offered clipboard URL."""

    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url


# --------------------------------------------------------------------- download
class DownloadProgressTick(Message):
    """One progress hook tick from the download engine."""

    def __init__(self, progress: DownloadProgress) -> None:
        super().__init__()
        self.progress = progress


class DownloadProcessing(Message):
    """yt-dlp entered a postprocessor stage (Merger, ExtractAudio, …).

    The download bar swaps to the "processing…" indeterminate state until
    the next :class:`DownloadProgressTick` or :class:`DownloadSucceeded`.
    """


class DownloadRefreshing(Message):
    """A stale-info retry is starting — swap the status text to "link expired…"."""


class DownloadSucceeded(Message):
    """Download completed. Carries the final file path for the done screen."""

    def __init__(self, filepath: Path, title: str = "") -> None:
        super().__init__()
        self.filepath = filepath
        self.title = title


class DownloadFailed(Message):
    """The download raised a non-cancellation error. Carries a user-facing message."""

    def __init__(self, message: str) -> None:
        super().__init__()
        self.message = message


# ---------------------------------------------------------------------- update
class UpdateHintAvailable(Message):
    """Background update-check completed with a user-facing hint.

    The screen listens and appends the hint as a dim item in the footer.
    """

    def __init__(self, hint: str) -> None:
        super().__init__()
        self.hint = hint
