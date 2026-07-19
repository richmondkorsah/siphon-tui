"""Tests for :mod:`siphon.services.update_check` — version comparison + failure paths."""

from __future__ import annotations

import pytest

from siphon.services import update_check
from siphon.services.update_check import (
    ComponentStatus,
    UpdateStatus,
    _parse_version,
    check_updates,
)


class TestVersionParse:
    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ("1.2.3", (1, 2, 3)),
            ("v1.2.3", (1, 2, 3)),
            ("2026.7.4", (2026, 7, 4)),
            ("0.1.0.dev1", (0, 1, 0)),  # stops at non-numeric
            ("10", (10,)),
        ],
    )
    def test_parses_common_shapes(self, text: str, expected: tuple[int, ...]) -> None:
        assert _parse_version(text) == expected


class TestComponentStatus:
    def test_stale_when_latest_greater(self) -> None:
        status = ComponentStatus(name="x", installed_version="1.0.0", latest_version="1.0.1")
        assert status.is_stale is True

    def test_not_stale_when_equal(self) -> None:
        status = ComponentStatus(name="x", installed_version="1.0.1", latest_version="1.0.1")
        assert status.is_stale is False

    def test_not_stale_when_installed_newer(self) -> None:
        status = ComponentStatus(name="x", installed_version="1.1.0", latest_version="1.0.9")
        assert status.is_stale is False

    def test_never_stale_when_lookup_failed(self) -> None:
        status = ComponentStatus(name="x", installed_version=None, latest_version="1.0.0")
        assert status.is_stale is False
        status = ComponentStatus(name="x", installed_version="1.0.0", latest_version=None)
        assert status.is_stale is False


class TestHintMessage:
    def test_none_when_all_fresh(self) -> None:
        status = UpdateStatus(
            ytdlp=ComponentStatus("yt-dlp", "1.0.0", "1.0.0"),
            siphon=ComponentStatus("siphon", "0.1.0", "0.1.0"),
        )
        assert status.hint_message is None

    def test_names_stale_components(self) -> None:
        status = UpdateStatus(
            ytdlp=ComponentStatus("yt-dlp", "2025.1.1", "2026.1.1"),
            siphon=ComponentStatus("siphon", "0.1.0", "0.1.0"),
        )
        assert status.hint_message is not None
        assert "yt-dlp" in status.hint_message
        assert "2026.1.1" in status.hint_message

    def test_lists_multiple(self) -> None:
        status = UpdateStatus(
            ytdlp=ComponentStatus("yt-dlp", "1.0.0", "1.0.1"),
            siphon=ComponentStatus("siphon", "0.1.0", "0.2.0"),
        )
        assert status.hint_message is not None
        assert "yt-dlp" in status.hint_message
        assert "siphon" in status.hint_message


class TestNetworkFailure:
    async def test_network_failure_returns_none_latest(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(update_check, "_http_get_json", lambda _url: None)
        status = await check_updates()
        assert status.ytdlp.latest_version is None
        assert status.siphon.latest_version is None
        assert status.hint_message is None
