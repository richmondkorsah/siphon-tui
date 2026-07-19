"""Tests for :mod:`siphon.utils.format` — boundary values and edge cases."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from siphon.utils.format import (
    format_bytes,
    format_duration,
    format_eta,
    format_speed,
    shorten_path,
    truncate,
)


class TestFormatBytes:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (0, "0 B"),
            (1, "1 B"),
            (1023, "1023 B"),
            (1024, "1.0 KB"),
            (1536, "1.5 KB"),
            (10 * 1024, "10 KB"),
            (1024 * 1024, "1.0 MB"),
            (1024**3, "1 GB"),
            (5 * 1024**3, "5 GB"),
        ],
    )
    def test_boundaries(self, value: int, expected: str) -> None:
        assert format_bytes(value) == expected

    @pytest.mark.parametrize("bad", [None, -1, math.nan, math.inf])
    def test_null_or_bad_returns_empty(self, bad: object) -> None:
        assert format_bytes(bad) == ""  # type: ignore[arg-type]


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (0, "0:00"),
            (5, "0:05"),
            (65, "1:05"),
            (599, "9:59"),
            (3600, "1:00:00"),
            (3661, "1:01:01"),
            (7200, "2:00:00"),
        ],
    )
    def test_boundaries(self, seconds: int, expected: str) -> None:
        assert format_duration(seconds) == expected

    def test_none_returns_empty(self) -> None:
        assert format_duration(None) == ""

    def test_eta_is_alias(self) -> None:
        assert format_eta(75) == format_duration(75)


class TestFormatSpeed:
    def test_appends_per_second(self) -> None:
        assert format_speed(1024) == "1.0 KB/s"

    def test_none_returns_empty(self) -> None:
        assert format_speed(None) == ""


class TestTruncate:
    def test_no_truncation_when_fits(self) -> None:
        assert truncate("hello", 10) == "hello"

    def test_truncates_with_ellipsis(self) -> None:
        result = truncate("hello world", 8)
        assert result.endswith("…")
        assert len(result) <= 8

    def test_zero_max_returns_empty(self) -> None:
        assert truncate("hello", 0) == ""


class TestShortenPath:
    def test_home_relative_short_path(self, tmp_path: Path) -> None:
        # Point HOME at tmp_path so ``~`` resolves cleanly.
        result = shorten_path(tmp_path / "video.mp4", home=tmp_path, max_length=60)
        assert result == "~/video.mp4"

    def test_preserves_extension_when_truncating(self, tmp_path: Path) -> None:
        long_name = "x" * 200 + ".mp4"
        result = shorten_path(tmp_path / long_name, home=tmp_path, max_length=30)
        assert result.endswith(".mp4")
        assert len(result) <= 30

    def test_absolute_path_outside_home_returns_as_is(self, tmp_path: Path) -> None:
        # Path lives outside HOME → not prefixed with ~
        result = shorten_path("/etc/hosts", home=tmp_path, max_length=60)
        assert result == "/etc/hosts"
