"""Pilot-driven tests for the M3 input phase.

Covers:
* URL submit → transitions to :class:`ProbingPhase` with detected platform.
* Invalid URL → stays on input phase with a warning.
* Esc during probing → returns to input with the URL preserved.
* History recall (up/down) walks + restores draft.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pyperclip
import pytest

from siphon.config.settings import reset_settings_cache
from siphon.models.phase import InputPhase, ProbingPhase
from siphon.ui.app import SiphonApp
from siphon.ui.screens import main as main_mod
from siphon.ui.widgets.framed_input import FramedInput


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    for name in list(os.environ):
        if name.startswith("SIPHON_"):
            monkeypatch.delenv(name, raising=False)
    # Silence clipboard reads across all tests unless explicitly overridden.
    monkeypatch.setattr(pyperclip, "paste", lambda: "")

    # Stub the probe so no test in this file hits the real yt-dlp / network.
    # The stub blocks forever — tests that need probe completion mock it themselves.
    async def _hang(_url: str, _token: object = None) -> dict:
        await asyncio.sleep(10.0)
        return {}

    monkeypatch.setattr(main_mod, "probe", _hang)

    reset_settings_cache()
    yield
    reset_settings_cache()


async def _type(pilot: object, text: str) -> None:
    for ch in text:
        await pilot.press(ch)  # type: ignore[attr-defined]


class TestSubmitAndCancel:
    async def test_valid_url_transitions_to_probing(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
            await _type(pilot, "https://youtu.be/dQw4w9WgXcQ")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen.phase, ProbingPhase)
            assert app.screen.phase.url == "https://youtu.be/dQw4w9WgXcQ"
            assert app.screen.phase.platform.label == "YouTube"

    async def test_invalid_url_shows_warning(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _type(pilot, "not-a-url")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
            assert app.screen.phase.warning is not None
            assert "link" in app.screen.phase.warning.lower()

    async def test_esc_during_probing_preserves_url(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _type(pilot, "https://example.com/x")
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen.phase, ProbingPhase)
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
            # URL should be back in the input field.
            framed = app.screen.query_one(FramedInput)
            assert framed.input.value == "https://example.com/x"


class TestClipboardOffer:
    async def test_clipboard_url_offered_via_suggestion(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(pyperclip, "paste", lambda: "https://youtu.be/abcd")
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()  # let clipboard worker run
            phase = app.screen.phase
            assert isinstance(phase, InputPhase)
            assert phase.clipboard_url == "https://youtu.be/abcd"

    async def test_tab_accepts_clipboard_suggestion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pyperclip, "paste", lambda: "https://vimeo.com/12345")
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.pause()
            framed = app.screen.query_one(FramedInput)
            assert framed.input.value == ""
            await pilot.press("tab")
            await pilot.pause()
            assert framed.input.value == "https://vimeo.com/12345"


class TestHistoryRecall:
    async def test_up_arrow_recalls_previous_url(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # Submit one URL to seed history.
            await _type(pilot, "https://a.example/1")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("escape")  # back to input
            await pilot.pause()
            # Clear the preserved value first so ↑ has something to overwrite.
            framed = app.screen.query_one(FramedInput)
            framed.input.value = ""
            await pilot.press("up")
            await pilot.pause()
            assert framed.input.value == "https://a.example/1"

    async def test_down_arrow_restores_draft(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await _type(pilot, "https://seed.example/x")
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            framed = app.screen.query_one(FramedInput)
            framed.input.value = "my-draft-in-progress"

            # ↑ saves the draft and recalls history.
            await pilot.press("up")
            await pilot.pause()
            assert framed.input.value == "https://seed.example/x"

            # ↓ walks past position 0 → draft comes back.
            await pilot.press("down")
            await pilot.pause()
            assert framed.input.value == "my-draft-in-progress"


class TestInitialUrl:
    async def test_initial_url_skips_input(self) -> None:
        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen.phase, ProbingPhase)
            assert app.screen.phase.platform.label == "YouTube"

    async def test_invalid_initial_url_falls_back_to_input(self) -> None:
        app = SiphonApp(initial_url="garbage")
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
