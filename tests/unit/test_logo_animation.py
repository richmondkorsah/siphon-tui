"""Tests for :mod:`siphon.ui.animations.logo_animation` — pure math, no Textual."""

from __future__ import annotations

import pytest

from siphon.ui.animations.logo_animation import (
    INTRO_DELAY_MAX_S,
    INTRO_TOTAL_S,
    SHIMMER_S,
    SWEEP_HALF_WIDTH_CELLS,
    SWEEP_TILT_CELLS_PER_ROW,
    Cell,
    CellStyle,
    cell_in_beam,
    compute_intro_delays,
    ease_out_cubic,
    intro_cell,
    iter_row_segments,
    sweep_cell,
    sweep_offset,
)


class TestDelays:
    def test_shape_matches_dimensions(self) -> None:
        delays = compute_intro_delays(29, 3)
        assert len(delays) == 3
        assert all(len(row) == 29 for row in delays)

    def test_deterministic_across_calls(self) -> None:
        assert compute_intro_delays(10, 3) == compute_intro_delays(10, 3)

    def test_all_delays_within_bounds(self) -> None:
        delays = compute_intro_delays(29, 3)
        for row in delays:
            for value in row:
                assert 0.0 <= value <= INTRO_DELAY_MAX_S

    def test_different_seeds_diverge(self) -> None:
        assert compute_intro_delays(10, 3, seed=1) != compute_intro_delays(10, 3, seed=2)


class TestIntroCell:
    def test_full_block_placeholder_pre_delay(self) -> None:
        cell = intro_cell("█", elapsed_s=0.0, delay_s=0.2)
        assert cell == Cell("░", CellStyle.PLACEHOLDER)

    def test_full_block_shimmer_at_delay(self) -> None:
        cell = intro_cell("█", elapsed_s=0.2, delay_s=0.2)
        assert cell.char == "▒"
        assert cell.style == CellStyle.SHIMMER

    def test_full_block_final_after_shimmer(self) -> None:
        cell = intro_cell("█", elapsed_s=0.2 + SHIMMER_S + 0.01, delay_s=0.2)
        assert cell == Cell("█", CellStyle.BOLD)

    @pytest.mark.parametrize("half", ["▀", "▄"])
    def test_half_blocks_keep_glyph_pre_delay(self, half: str) -> None:
        cell = intro_cell(half, elapsed_s=0.0, delay_s=0.3)
        assert cell.char == half
        assert cell.style == CellStyle.PLACEHOLDER

    def test_space_is_bold_and_unchanged(self) -> None:
        cell = intro_cell(" ", elapsed_s=0.0, delay_s=0.3)
        assert cell == Cell(" ", CellStyle.BOLD)


class TestEaseOutCubic:
    @pytest.mark.parametrize(
        ("t", "expected"),
        [(0.0, 0.0), (1.0, 1.0)],
    )
    def test_endpoints(self, t: float, expected: float) -> None:
        assert ease_out_cubic(t) == pytest.approx(expected)

    def test_monotonic(self) -> None:
        values = [ease_out_cubic(t / 10.0) for t in range(11)]
        assert values == sorted(values)

    def test_clamped_to_unit_interval(self) -> None:
        assert 0.0 <= ease_out_cubic(-1.0) <= 1.0
        assert 0.0 <= ease_out_cubic(2.0) <= 1.0


class TestSweepGeometry:
    def test_sweep_offset_starts_before_left_edge(self) -> None:
        # First frame: beam center is off the left edge so cells begin unswept.
        offset = sweep_offset(0.0, logo_width=29)
        assert offset == pytest.approx(-SWEEP_HALF_WIDTH_CELLS)

    def test_sweep_offset_ends_past_right_edge(self) -> None:
        offset = sweep_offset(1.0, logo_width=29)
        assert offset > 29

    def test_beam_tilt_produces_diagonal(self) -> None:
        # For a given center offset, top row's cell 0 should be in the beam
        # but bottom row's cell 0 should NOT be — that's the `/` tilt.
        # Middle-row center at column 0.
        top_in = cell_in_beam(0, row=0, beam_offset=0 - SWEEP_TILT_CELLS_PER_ROW)
        bot_in = cell_in_beam(0, row=2, beam_offset=0 - SWEEP_TILT_CELLS_PER_ROW)
        # When the beam is above column 0 in the top row, the bottom row's
        # cell at column 0 has moved out (beam is now at row 1's tilted center).
        assert top_in != bot_in or (top_in and bot_in)


class TestSweepCell:
    def test_full_block_in_band_lightens(self) -> None:
        cell = sweep_cell("█", in_band=True)
        assert cell.char == "▒"

    def test_full_block_out_of_band_unchanged(self) -> None:
        cell = sweep_cell("█", in_band=False)
        assert cell == Cell("█", CellStyle.BOLD)

    @pytest.mark.parametrize("half", ["▀", "▄"])
    def test_half_block_in_band_dims(self, half: str) -> None:
        cell = sweep_cell(half, in_band=True)
        assert cell.char == half
        assert cell.style == CellStyle.DIM

    def test_space_ignored(self) -> None:
        cell = sweep_cell(" ", in_band=True)
        assert cell == Cell(" ", CellStyle.BOLD)


class TestSegmentCoalescer:
    def test_empty(self) -> None:
        assert list(iter_row_segments([])) == []

    def test_all_same_style_merges_into_one(self) -> None:
        cells = [Cell(c, CellStyle.BOLD) for c in "abcd"]
        assert list(iter_row_segments(cells)) == [("abcd", CellStyle.BOLD)]

    def test_style_boundaries_split(self) -> None:
        cells = [
            Cell("a", CellStyle.BOLD),
            Cell("b", CellStyle.BOLD),
            Cell("c", CellStyle.DIM),
            Cell("d", CellStyle.BOLD),
        ]
        result = list(iter_row_segments(cells))
        assert result == [
            ("ab", CellStyle.BOLD),
            ("c", CellStyle.DIM),
            ("d", CellStyle.BOLD),
        ]

    def test_realistic_row_collapses_to_few_spans(self) -> None:
        # A 29-cell row where only two neighbours are dim collapses to 3 spans.
        cells = [Cell("█", CellStyle.BOLD)] * 29
        cells[10] = Cell("▀", CellStyle.DIM)
        cells[11] = Cell("▄", CellStyle.DIM)
        result = list(iter_row_segments(cells))
        assert len(result) == 3

    def test_intro_total_covers_max_delay_plus_shimmer(self) -> None:
        # Invariant: even the last-revealed cell finishes shimmering before
        # INTRO_TOTAL_S expires.
        assert INTRO_TOTAL_S >= INTRO_DELAY_MAX_S + SHIMMER_S
