"""Shared braille spinner frames + a self-animating label widget.

Both the probing status line and the download status meta row want a
``⠋ some text…`` row whose glyph actually spins. Previously they hardcoded
the first frame (``⠋``) and never advanced it — this module is the single
place that owns the frame set and the timing, so every spinner in the app
animates in lockstep.
"""

from __future__ import annotations

from typing import Final

from textual.reactive import reactive
from textual.widgets import Static

SPINNER_FRAMES: Final[tuple[str, ...]] = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
SPINNER_INTERVAL_S: Final[float] = 0.08


class SpinnerLabel(Static):
    """A ``⠋ <label>`` row that advances its glyph on a timer while mounted."""

    frame_index: reactive[int] = reactive(0)

    def __init__(
        self,
        label: str = "",
        *,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(id=id, classes=classes)
        self._label = label

    def on_mount(self) -> None:
        self._render_now()
        self.set_interval(SPINNER_INTERVAL_S, self._advance)

    def _advance(self) -> None:
        self.frame_index = (self.frame_index + 1) % len(SPINNER_FRAMES)

    def watch_frame_index(self, _old: int, _new: int) -> None:
        self._render_now()

    def set_label(self, label: str) -> None:
        """Update the trailing text without resetting the spin phase."""
        self._label = label
        self._render_now()

    def _render_now(self) -> None:
        frame = SPINNER_FRAMES[self.frame_index]
        self.update(f"{frame} {self._label}" if self._label else frame)
