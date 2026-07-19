"""Tests for :func:`siphon.engine.errors.clean_ytdlp_error`."""

from __future__ import annotations

import pytest

from siphon.engine.errors import CleanedYtdlpError, clean_ytdlp_error


class TestCleanYtdlpError:
    def test_last_error_line_wins(self) -> None:
        raw = "warning: something\nERROR: [youtube] abc: Video unavailable"
        assert clean_ytdlp_error(raw) == "abc: Video unavailable"

    def test_extractor_prefix_stripped(self) -> None:
        assert clean_ytdlp_error("ERROR: [youtube] Video unavailable") == "Video unavailable"

    def test_no_error_line_falls_back_to_last_line(self) -> None:
        assert clean_ytdlp_error("something went wrong\nkeep-me") == "keep-me"

    def test_empty_input_returns_placeholder(self) -> None:
        assert clean_ytdlp_error("") == "yt-dlp exited without a message"

    @pytest.mark.parametrize("raw", ["ERROR:", "ERROR:  ", "ERROR: [extractor]"])
    def test_empty_message_after_prefix_strip(self, raw: str) -> None:
        # Result should never be empty — we substitute a friendly placeholder.
        assert clean_ytdlp_error(raw) == "yt-dlp failed"


class TestErrorClass:
    def test_carries_user_message(self) -> None:
        err = CleanedYtdlpError("nope")
        assert err.user_message == "nope"
        assert str(err) == "nope"

    def test_wraps_original(self) -> None:
        original = ValueError("underlying")
        err = CleanedYtdlpError("wrapped", original=original)
        assert err.original is original
