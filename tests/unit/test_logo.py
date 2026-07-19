"""Tests for :mod:`siphon.ui.widgets.logo` — glyph geometry + character set."""

from __future__ import annotations

import pytest

from siphon.ui.widgets.logo import LOGO_LINES, LOGO_WIDTH


class TestLogoGeometry:
    def test_three_rows(self) -> None:
        assert len(LOGO_LINES) == 3

    def test_rows_all_same_width(self) -> None:
        widths = {len(line) for line in LOGO_LINES}
        assert len(widths) == 1
        assert next(iter(widths)) == LOGO_WIDTH

    def test_reported_width_matches(self) -> None:
        assert len(LOGO_LINES[0]) == LOGO_WIDTH


class TestLogoCharacterSet:
    """Only block glyphs and spaces are permitted.

    Full block ``█``, half-blocks ``▀`` / ``▄``, and the two lighter shades
    ``▒`` / ``░`` are all valid — the animation transforms already know how
    to handle every glyph in this set (``█`` → ``▒`` under sweep, ``▒`` stays
    dim, etc.). Quarter-blocks or other Unicode art would need new transform
    rules and are explicitly disallowed.
    """

    ALLOWED: frozenset[str] = frozenset({"█", "▓", "▒", "░", "▀", "▄", " "})

    @pytest.mark.parametrize("line_index", [0, 1, 2])
    def test_only_allowed_chars(self, line_index: int) -> None:
        line = LOGO_LINES[line_index]
        offenders = {c for c in line if c not in self.ALLOWED}
        assert not offenders, f"row {line_index} contains {offenders!r}"

    def test_no_leading_or_trailing_whitespace_stripped_at_edges(self) -> None:
        # Each row must have at least one non-space character.
        for line in LOGO_LINES:
            assert line.strip() != ""
