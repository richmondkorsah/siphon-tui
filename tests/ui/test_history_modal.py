"""Pilot-driven tests for the ``^r`` history modal."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pyperclip
import pytest

from siphon.config.settings import reset_settings_cache
from siphon.models.history_entry import HistoryEntry
from siphon.services import history as history_mod
from siphon.ui.app import SiphonApp
from siphon.ui.screens import main as main_mod
from siphon.ui.screens.history import HistoryModal, HistoryRow
from siphon.ui.widgets.framed_input import FramedInput


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    for name in list(os.environ):
        if name.startswith("SIPHON_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(pyperclip, "paste", lambda: "")

    async def _hang(_url: str, _token: object = None) -> dict:
        await asyncio.sleep(10.0)
        return {}

    monkeypatch.setattr(main_mod, "probe", _hang)

    reset_settings_cache()
    yield
    reset_settings_cache()


def _seed_history(entries: list[HistoryEntry]) -> None:
    """Persist ``entries`` to the JSONL history before the app starts."""
    import json  # noqa: PLC0415

    path = history_mod.history_file_jsonl_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(e.to_dict()) for e in entries) + "\n",
        encoding="utf-8",
    )


class TestOpenAndCancel:
    async def test_ctrl_r_opens_modal(self) -> None:
        _seed_history(
            [
                HistoryEntry(url="https://a.example/1"),
                HistoryEntry(url="https://b.example/2", title="Two", platform="X"),
            ]
        )
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            assert isinstance(app.screen, HistoryModal)

    async def test_esc_cancels_without_prefilling(self) -> None:
        _seed_history([HistoryEntry(url="https://only.example")])
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            # Back on main screen; input still empty.
            framed = app.screen.query_one(FramedInput)
            assert framed.input.value == ""

    async def test_no_op_when_history_empty(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            # No modal was pushed — main screen still on top.
            assert not isinstance(app.screen, HistoryModal)


class TestSelection:
    async def test_enter_from_filter_picks_first_row(self) -> None:
        _seed_history(
            [
                HistoryEntry(url="https://first.example"),
                HistoryEntry(url="https://second.example"),
            ]
        )
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            framed = app.screen.query_one(FramedInput)
            assert framed.input.value == "https://first.example"

    async def test_filter_narrows_to_matching_rows(self) -> None:
        _seed_history(
            [
                HistoryEntry(url="https://youtube.com/watch?v=1"),
                HistoryEntry(url="https://vimeo.com/12345"),
                HistoryEntry(url="https://tiktok.com/@u/2"),
            ]
        )
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            for ch in "vimeo":
                await pilot.press(ch)
            await pilot.pause()
            # The list should show only one HistoryRow.
            modal = app.screen
            assert isinstance(modal, HistoryModal)
            rows = modal.query(HistoryRow)
            assert len(rows) == 1
            await pilot.press("enter")
            await pilot.pause()
            framed = app.screen.query_one(FramedInput)
            assert framed.input.value == "https://vimeo.com/12345"

    async def test_matches_title_and_platform(self) -> None:
        _seed_history(
            [
                HistoryEntry(url="https://a", title="Never Gonna Give You Up", platform="YouTube"),
                HistoryEntry(url="https://b", title="Unrelated", platform="Vimeo"),
            ]
        )
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+r")
            await pilot.pause()
            for ch in "never":
                await pilot.press(ch)
            await pilot.pause()
            modal = app.screen
            assert isinstance(modal, HistoryModal)
            rows = modal.query(HistoryRow)
            assert len(rows) == 1
