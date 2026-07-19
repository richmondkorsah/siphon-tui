"""Tests for :class:`siphon.models.progress.DownloadProgress`."""

from __future__ import annotations

import pytest

from siphon.models.progress import DownloadProgress


class TestPredicates:
    def test_empty_has_no_total(self) -> None:
        assert DownloadProgress().has_total is False
        assert DownloadProgress().has_bytes is False

    def test_zero_total_still_has_no_total(self) -> None:
        assert DownloadProgress(total_bytes=0).has_total is False

    def test_positive_total(self) -> None:
        assert DownloadProgress(total_bytes=10).has_total is True

    def test_has_bytes_only_when_downloaded_reported(self) -> None:
        assert DownloadProgress(downloaded_bytes=1024).has_bytes is True

    def test_zero_downloaded_still_has_bytes(self) -> None:
        # 0 downloaded is a valid tick — yt-dlp fires ``status='downloading'``
        # with 0 bytes when a new file starts.
        assert DownloadProgress(downloaded_bytes=0).has_bytes is True


class TestFraction:
    @pytest.mark.parametrize(
        ("done", "total", "expected"),
        [(0, 100, 0.0), (50, 100, 0.5), (100, 100, 1.0), (200, 100, 1.0)],
    )
    def test_fraction_within_bounds(self, done: int, total: int, expected: float) -> None:
        p = DownloadProgress(downloaded_bytes=done, total_bytes=total)
        assert p.fraction == pytest.approx(expected)

    def test_fraction_without_total_is_zero(self) -> None:
        assert DownloadProgress(downloaded_bytes=1024).fraction == 0.0

    def test_negative_total_yields_zero(self) -> None:
        assert DownloadProgress(downloaded_bytes=10, total_bytes=-1).fraction == 0.0


class TestPercent:
    def test_rounds_to_integer(self) -> None:
        p = DownloadProgress(downloaded_bytes=333, total_bytes=1000)
        assert p.percent == 33

    def test_full_is_100(self) -> None:
        assert DownloadProgress(downloaded_bytes=100, total_bytes=100).percent == 100
