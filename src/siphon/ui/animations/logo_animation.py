"""Logo intro-flicker + periodic-sweep math (yoinks F22).

Two independent effects run over the same logo grid:

1. **Intro (900 ms).** Every cell has a per-cell delay in ``[0, 550] ms``. At
   ``t < delay`` the cell shows its *placeholder* state; at
   ``delay ≤ t < delay + SHIMMER_MS`` it shows the shimmer glyph; at
   ``t ≥ delay + SHIMMER_MS`` it locks to the final glyph.

   *Full-cell blocks* (``█``) cycle ``░ → ▒ → █``. *Half-blocks*
   (``▀`` / ``▄``) keep their glyph the whole time but render dimmed while
   they're still in flight.

2. **Sweep (1000 ms, ease-out cubic).** A tilted ``/`` beam sweeps across
   the logo every :data:`SWEEP_INTERVAL_S`. Cells inside the beam band
   (half-width :data:`SWEEP_HALF_WIDTH_CELLS`) lighten: ``█ → ▒``; half-blocks
   simply dim without changing glyph.

Both effects share the segment-merging invariant: consecutive cells with the
same style collapse into a single Rich text span. See
:func:`iter_row_segments` for the coalescer.
"""

from __future__ import annotations

import random
from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

# -------- timing ------------------------------------------------------------
INTRO_TOTAL_S: Final[float] = 0.9
"""Whole intro duration; after this, cells sit at their final glyph."""

INTRO_DELAY_MAX_S: Final[float] = 0.55
"""Upper bound on per-cell reveal delay (uniform random from 0)."""

SHIMMER_S: Final[float] = 0.12
"""How long each full-block cell shows the ``▒`` shimmer glyph before locking in."""

SWEEP_INTERVAL_S: Final[float] = 7.0
"""Idle time between sweeps once the intro has locked in."""

SWEEP_DURATION_S: Final[float] = 1.0
"""How long one sweep takes to cross the logo."""

SWEEP_TILT_CELLS_PER_ROW: Final[float] = 2.0
"""Per-row tilt of the ``/`` beam for a 3-row logo.

For taller logos, :func:`cell_in_beam` scales this so the total tilt span
between the top and bottom rows stays at ``2 * SWEEP_TILT_CELLS_PER_ROW``
cells regardless of height — the beam stays visually diagonal without
running miles ahead of itself on a 9-row logo."""

SWEEP_HALF_WIDTH_CELLS: Final[float] = 2.4
"""Half-width of the beam band; cells within this distance are affected."""


class CellStyle(StrEnum):
    """Style class assigned to a single cell for the frame's render."""

    BOLD = "bold"
    DIM = "dim"
    SHIMMER = "shimmer"  # rendered as bold + one shade dimmer
    PLACEHOLDER = "placeholder"  # rendered dim


@dataclass(frozen=True, slots=True)
class Cell:
    """One rendered cell — the glyph to display and its style."""

    char: str
    style: CellStyle


# ---------------------------------------------------------------------------
# Per-cell delays
# ---------------------------------------------------------------------------
def compute_intro_delays(width: int, height: int, *, seed: int = 42) -> list[list[float]]:
    """Deterministic per-cell reveal delays in seconds ``[0, INTRO_DELAY_MAX_S]``.

    Seeded so tests and re-mounts see identical staggering.
    """
    rng = random.Random(seed)
    return [[rng.random() * INTRO_DELAY_MAX_S for _ in range(width)] for _ in range(height)]


# ---------------------------------------------------------------------------
# Intro
# ---------------------------------------------------------------------------
def intro_cell(final_char: str, elapsed_s: float, delay_s: float) -> Cell:
    """Return the :class:`Cell` for one grid position during the intro.

    Full blocks (``█``) cycle through ``░ → ▒ → █``. Every other glyph
    (``░ ▒ ▓ ▀ ▄``) keeps its character and varies only its style — otherwise
    a light-shade art made of ``░`` cells would flash the heavier ``▒`` glyph
    mid-shimmer and then snap back down to ``░``, which reads as glitchy.
    """
    if final_char == " ":
        return Cell(" ", CellStyle.BOLD)

    if final_char == "█":
        if elapsed_s < delay_s:
            return Cell("░", CellStyle.PLACEHOLDER)
        if elapsed_s < delay_s + SHIMMER_S:
            return Cell("▒", CellStyle.SHIMMER)
        return Cell("█", CellStyle.BOLD)

    if elapsed_s < delay_s:
        return Cell(final_char, CellStyle.PLACEHOLDER)
    if elapsed_s < delay_s + SHIMMER_S:
        return Cell(final_char, CellStyle.DIM)
    return Cell(final_char, CellStyle.BOLD)


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------
def ease_out_cubic(progress: float) -> float:
    """Ease-out cubic curve — matches yoinks' sweep motion."""
    inv = 1.0 - max(0.0, min(1.0, progress))
    return 1.0 - inv * inv * inv


def sweep_offset(progress: float, logo_width: int) -> float:
    """Beam's horizontal offset at ``progress`` in ``[0, 1]``.

    The beam travels from just off the left edge of the logo to just past
    the right edge — accounting for the half-width band and the row-tilt so
    every cell gets swept at some point.
    """
    total_travel = logo_width + 2 * SWEEP_HALF_WIDTH_CELLS + 2 * SWEEP_TILT_CELLS_PER_ROW
    return -SWEEP_HALF_WIDTH_CELLS + ease_out_cubic(progress) * total_travel


def sweep_cell(final_char: str, in_band: bool) -> Cell:
    """Return the :class:`Cell` for a fully-revealed grid position under a sweep.

    Full blocks lighten to ``▒`` when inside the band; half-blocks dim.
    Cells outside the band are drawn bold and unchanged.
    """
    if final_char == " ":
        return Cell(" ", CellStyle.BOLD)
    if not in_band:
        return Cell(final_char, CellStyle.BOLD)
    if final_char == "█":
        return Cell("▒", CellStyle.BOLD)
    if final_char in ("▀", "▄"):
        return Cell(final_char, CellStyle.DIM)
    # ``░`` and ``▒`` are already lighter — leave them alone but dim.
    return Cell(final_char, CellStyle.DIM)


def cell_in_beam(col: int, row: int, beam_offset: float, logo_height: int = 3) -> bool:
    """True iff ``(col, row)`` lies within the tilted beam band.

    Beam is a ``/`` — the top row sees the beam offset positive and the
    bottom row sees it negative. The total tilt span from top to bottom is
    ``2 * SWEEP_TILT_CELLS_PER_ROW`` cells regardless of ``logo_height``,
    so a 9-row logo gets the same diagonal reach as the original 3-row one.
    """
    if logo_height <= 1:
        row_tilt = 0.0
    else:
        center_row = (logo_height - 1) / 2.0
        tilt_per_row = 2.0 * SWEEP_TILT_CELLS_PER_ROW / (logo_height - 1)
        row_tilt = (center_row - row) * tilt_per_row
    beam_center = beam_offset + row_tilt
    return abs(col - beam_center) < SWEEP_HALF_WIDTH_CELLS


# ---------------------------------------------------------------------------
# Segment coalescer
# ---------------------------------------------------------------------------
def iter_row_segments(cells: list[Cell]) -> Iterator[tuple[str, CellStyle]]:
    """Yield ``(run, style)`` pairs where consecutive same-style cells merge.

    A row of 24 cells typically collapses to 3-5 spans (matches yoinks'
    "each row is a few Text spans, not 24" perf note).
    """
    if not cells:
        return
    run: list[str] = [cells[0].char]
    current_style: CellStyle = cells[0].style
    for cell in cells[1:]:
        if cell.style == current_style:
            run.append(cell.char)
        else:
            yield "".join(run), current_style
            run = [cell.char]
            current_style = cell.style
    if run:
        yield "".join(run), current_style
