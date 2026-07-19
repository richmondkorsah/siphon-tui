"""The SIPHON logo widget with intro-flicker + periodic sweep animation.

The animation math lives in :mod:`siphon.ui.animations.logo_animation` so
this file stays UI-adjacent: setting up timers, composing Rich Text from
the computed :class:`Cell` grid, and swallowing the animation entirely on
non-TTY output.
"""

from __future__ import annotations

import sys
import time
from typing import Final

from rich.text import Text
from textual.widget import Widget

from siphon.ui.animations.logo_animation import (
    INTRO_TOTAL_S,
    SWEEP_DURATION_S,
    SWEEP_INTERVAL_S,
    Cell,
    CellStyle,
    cell_in_beam,
    compute_intro_delays,
    intro_cell,
    iter_row_segments,
    sweep_cell,
    sweep_offset,
)

# One glyph per letter: three rows of exactly 4 cells.
# All strings use only "█ ▀ ▄ space" so animation transforms stay simple.
_GLYPHS: Final[dict[str, tuple[str, str, str]]] = {
    "S": ("▒▀▀▀", "▀▀▀▒", "▒▄▄█"),
    "I": ("▀██▀", " ██ ", "▄██▄"),
    "P": ("█▀▀█", "█▀▀▀", "▒   "),
    "H": ("█  █", "▒▄▄█", "█  █"),
    "O": ("█▀▀▒", "▒  █", "▒▄▄█"),
    "N": ("▒▄ █", "▒ ▀█", "▒  █"),
}

_WORD: Final[str] = "SIPHON"
_GLYPH_GAP: Final[str] = " "


def _compose_row(row_index: int) -> str:
    return _GLYPH_GAP.join(_GLYPHS[letter][row_index] for letter in _WORD)


LOGO_LINES: Final[tuple[str, str, str]] = (
    _compose_row(0),
    _compose_row(1),
    _compose_row(2),
)
"""The three fully-composed rows of the SIPHON logo."""

LOGO_WIDTH: Final[int] = len(LOGO_LINES[0])
LOGO_HEIGHT: Final[int] = 3

_FRAME_HZ: Final[float] = 30.0
"""Refresh rate — 30 fps balances smoothness against CPU on slow terminals."""

_STYLE_MAP: Final[dict[CellStyle, str]] = {
    CellStyle.BOLD: "bold",
    CellStyle.DIM: "dim",
    CellStyle.SHIMMER: "bold",
    CellStyle.PLACEHOLDER: "dim",
}


class LogoWidget(Widget):
    """Renders the SIPHON logo with per-cell intro + periodic sweep."""

    DEFAULT_CSS = f"""
    LogoWidget {{
        width: {LOGO_WIDTH};
        height: {LOGO_HEIGHT};
        color: $primary;
        content-align: left top;
    }}
    """

    def __init__(self, *, animate: bool | None = None, id: str | None = None) -> None:
        super().__init__(id=id)
        # ``animate`` defaults to "yes if stdout is a TTY". Tests pass
        # ``animate=False`` when they want deterministic snapshots.
        self._should_animate = animate if animate is not None else sys.stdout.isatty()
        self._start_time: float | None = None
        self._sweep_start: float | None = None
        self._delays = compute_intro_delays(LOGO_WIDTH, LOGO_HEIGHT)

    # ------------------------------------------------------------ lifecycle
    def on_mount(self) -> None:
        """Kick off the intro timer + schedule the first sweep after it."""
        self._start_time = time.monotonic()
        if not self._should_animate:
            return
        # 30 fps refresh — cheap even on a Pi.
        self.set_interval(1.0 / _FRAME_HZ, self._on_tick)
        # After the intro finishes, schedule the recurring sweeps.
        self.set_timer(INTRO_TOTAL_S + SWEEP_INTERVAL_S, self._start_sweep)

    def _on_tick(self) -> None:
        """Ask the compositor to re-render — cheap when nothing has changed."""
        now = time.monotonic()
        intro_elapsed = now - (self._start_time or now)

        # Stop ticking once both intro and sweep are done AND no sweep is running.
        if intro_elapsed >= INTRO_TOTAL_S and self._sweep_start is None:
            return
        self.refresh()

    def _start_sweep(self) -> None:
        """Fire off one sweep and self-reschedule the next."""
        if not self._should_animate or not self.is_mounted:
            return
        self._sweep_start = time.monotonic()
        # Keep ticking for the duration of the sweep — ensures paints happen
        # even if ``_on_tick`` returned early during idle.
        self.set_interval(1.0 / _FRAME_HZ, self._sweep_tick)
        # Schedule the next sweep once this one plus the idle gap elapses.
        self.set_timer(SWEEP_DURATION_S + SWEEP_INTERVAL_S, self._start_sweep)

    def _sweep_tick(self) -> None:
        """Refresh during an in-flight sweep; clear the state when it ends."""
        now = time.monotonic()
        if self._sweep_start is None:
            return
        if now - self._sweep_start >= SWEEP_DURATION_S:
            self._sweep_start = None
            self.refresh()
            return
        self.refresh()

    # -------------------------------------------------------------- render
    def render(self) -> Text:
        """Compose the current frame as Rich Text with coalesced spans."""
        now = time.monotonic()
        intro_elapsed = None
        beam_offset: float | None = None

        if self._should_animate and self._start_time is not None:
            elapsed = now - self._start_time
            if elapsed < INTRO_TOTAL_S:
                intro_elapsed = elapsed
            elif self._sweep_start is not None:
                sweep_elapsed = now - self._sweep_start
                if sweep_elapsed < SWEEP_DURATION_S:
                    beam_offset = sweep_offset(sweep_elapsed / SWEEP_DURATION_S, LOGO_WIDTH)

        text = Text(no_wrap=True, overflow="crop")
        for row_index, line in enumerate(LOGO_LINES):
            row_cells: list[Cell] = []
            for col_index, char in enumerate(line):
                if intro_elapsed is not None:
                    delay = self._delays[row_index][col_index]
                    row_cells.append(intro_cell(char, intro_elapsed, delay))
                elif beam_offset is not None:
                    in_band = cell_in_beam(col_index, row_index, beam_offset)
                    row_cells.append(sweep_cell(char, in_band))
                else:
                    row_cells.append(Cell(char, CellStyle.BOLD))

            for run, style in iter_row_segments(row_cells):
                text.append(run, style=_STYLE_MAP[style])
            if row_index < LOGO_HEIGHT - 1:
                text.append("\n")
        return text

    # ------------------------------------------------------------- events
    def on_click(self) -> None:
        """Clicking the logo posts a ``HomeRequested`` message to the parent."""
        # Import locally so this widget stays UI-lightweight — messages
        # module isn't needed for tests that just render.
        from siphon.ui.messages import HomeRequested  # noqa: PLC0415

        self.post_message(HomeRequested())
