"""Tests for the M3→M7 history migration (JSON array → JSONL with metadata)."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from siphon.config import paths as paths_mod
from siphon.services import history as history_mod


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    for name in list(os.environ):
        if name.startswith("SIPHON_"):
            monkeypatch.delenv(name, raising=False)


class TestJsonlLoad:
    def test_empty_file_returns_empty(self) -> None:
        jsonl = history_mod.history_file_jsonl_path()
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        jsonl.write_text("", encoding="utf-8")
        assert history_mod.load_entries() == []

    def test_valid_jsonl_round_trips(self) -> None:
        jsonl = history_mod.history_file_jsonl_path()
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        jsonl.write_text(
            json.dumps({"url": "https://a", "title": "A", "platform": "X"})
            + "\n"
            + json.dumps({"url": "https://b", "title": "B", "platform": "YouTube"})
            + "\n",
            encoding="utf-8",
        )
        entries = history_mod.load_entries()
        assert [e.url for e in entries] == ["https://a", "https://b"]
        assert entries[1].platform == "YouTube"

    def test_malformed_lines_skipped(self) -> None:
        jsonl = history_mod.history_file_jsonl_path()
        jsonl.parent.mkdir(parents=True, exist_ok=True)
        jsonl.write_text(
            'not-json\n{"url": "https://a"}\n{"missing-url": true}\n',
            encoding="utf-8",
        )
        entries = history_mod.load_entries()
        assert len(entries) == 1
        assert entries[0].url == "https://a"


class TestLegacyMigration:
    def test_legacy_json_loaded_when_jsonl_absent(self) -> None:
        legacy = paths_mod.history_file()
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps(["https://one", "https://two"]), encoding="utf-8")
        entries = history_mod.load_entries()
        assert [e.url for e in entries] == ["https://one", "https://two"]

    def test_writing_after_legacy_load_migrates_and_removes_legacy(self) -> None:
        legacy = paths_mod.history_file()
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps(["https://one"]), encoding="utf-8")

        history_mod.add_to_history("https://two", existing=None)

        # JSONL is now the source of truth.
        jsonl = history_mod.history_file_jsonl_path()
        assert jsonl.exists()
        assert not legacy.exists()
        reloaded = history_mod.load_entries()
        # Deduped + newest-first.
        assert [e.url for e in reloaded][:2] == ["https://two", "https://one"]

    def test_jsonl_takes_priority_over_legacy(self) -> None:
        # If both exist, JSONL wins.
        legacy = paths_mod.history_file()
        jsonl = history_mod.history_file_jsonl_path()
        legacy.parent.mkdir(parents=True, exist_ok=True)
        legacy.write_text(json.dumps(["https://legacy"]), encoding="utf-8")
        jsonl.write_text(json.dumps({"url": "https://modern"}) + "\n", encoding="utf-8")

        entries = history_mod.load_entries()
        assert [e.url for e in entries] == ["https://modern"]


class TestMetadataOnAdd:
    def test_title_and_platform_persisted(self) -> None:
        history_mod.add_to_history(
            "https://a", existing=None, title="Some Title", platform="YouTube"
        )
        entries = history_mod.load_entries()
        assert entries[0].title == "Some Title"
        assert entries[0].platform == "YouTube"
