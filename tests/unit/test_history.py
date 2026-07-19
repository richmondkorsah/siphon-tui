"""Tests for :mod:`siphon.services.history` — dedup, cap, error-swallowing."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from siphon.config import paths as paths_mod
from siphon.config.constants import HISTORY_LIMIT
from siphon.services import history as history_mod
from siphon.services.history import add_to_history, load_history


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    for name in list(os.environ):
        if name.startswith("SIPHON_"):
            monkeypatch.delenv(name, raising=False)


class TestLoad:
    def test_missing_file_returns_empty(self) -> None:
        assert load_history() == []

    def test_valid_file_round_trips(self, tmp_path: Path) -> None:
        path = paths_mod.history_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(["https://a", "https://b"]), encoding="utf-8")
        assert load_history() == ["https://a", "https://b"]

    def test_malformed_json_returns_empty(self) -> None:
        path = paths_mod.history_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")
        assert load_history() == []

    def test_non_array_returns_empty(self) -> None:
        path = paths_mod.history_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"nope": True}), encoding="utf-8")
        assert load_history() == []

    def test_non_string_entries_are_filtered(self) -> None:
        path = paths_mod.history_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(["https://a", 123, None, "https://b", {"nested": 1}]),
            encoding="utf-8",
        )
        assert load_history() == ["https://a", "https://b"]


class TestAdd:
    def test_prepends_new_url(self) -> None:
        result = add_to_history("https://a", existing=[])
        assert result == ["https://a"]

    def test_dedupes_existing_entry(self) -> None:
        result = add_to_history("https://a", existing=["https://b", "https://a", "https://c"])
        assert result == ["https://a", "https://b", "https://c"]

    def test_caps_at_history_limit(self) -> None:
        existing = [f"https://u{i}" for i in range(HISTORY_LIMIT)]
        result = add_to_history("https://new", existing=existing)
        assert len(result) == HISTORY_LIMIT
        assert result[0] == "https://new"

    def test_writes_to_disk_as_jsonl(self, tmp_path: Path) -> None:
        add_to_history("https://a", existing=[])
        jsonl = history_mod.history_file_jsonl_path()
        assert jsonl.exists()
        # JSONL: one JSON object per line, at least the URL round-trips.
        lines = jsonl.read_text().splitlines()
        assert lines
        parsed = json.loads(lines[0])
        assert parsed["url"] == "https://a"

    def test_write_failure_still_returns_updated(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Make _persist blow up; the in-memory result should still be returned.
        def boom(_entries: list[object]) -> None:
            raise OSError("disk on fire")

        monkeypatch.setattr(history_mod, "_persist", boom)
        result = add_to_history("https://a", existing=[])
        assert result == ["https://a"]


class TestReloadRoundTrip:
    def test_add_then_load_matches(self) -> None:
        add_to_history("https://one", existing=[])
        add_to_history("https://two", existing=load_history())
        add_to_history("https://one", existing=load_history())  # move to top
        assert load_history() == ["https://one", "https://two"]
