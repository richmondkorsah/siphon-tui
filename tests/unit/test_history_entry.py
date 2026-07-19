"""Tests for :class:`siphon.models.history_entry.HistoryEntry`."""

from __future__ import annotations

from siphon.models.history_entry import HistoryEntry


class TestConstruction:
    def test_url_only(self) -> None:
        entry = HistoryEntry(url="https://a")
        assert entry.url == "https://a"
        assert entry.title is None
        assert entry.platform is None
        assert entry.timestamp  # auto-populated ISO string

    def test_full_metadata(self) -> None:
        entry = HistoryEntry(url="https://a", title="A", platform="YouTube")
        assert entry.title == "A"
        assert entry.platform == "YouTube"


class TestSerialisation:
    def test_round_trip_via_dict(self) -> None:
        entry = HistoryEntry(url="https://a", title="A", platform="YouTube")
        reloaded = HistoryEntry.from_dict(entry.to_dict())
        assert reloaded == entry

    def test_from_dict_requires_url(self) -> None:
        assert HistoryEntry.from_dict({}) is None
        assert HistoryEntry.from_dict({"url": ""}) is None
        assert HistoryEntry.from_dict({"url": 123}) is None

    def test_from_dict_strips_empty_optional_fields(self) -> None:
        entry = HistoryEntry.from_dict({"url": "https://a", "title": "", "platform": None})
        assert entry is not None
        assert entry.title is None
        assert entry.platform is None
