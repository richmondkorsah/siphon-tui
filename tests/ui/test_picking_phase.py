"""Pilot-driven tests for the M4 probe → picker → cancel flow.

The real yt-dlp is patched out — every test monkeypatches
:func:`siphon.ui.screens.main.probe` with a synchronous fake so we exercise
the state machine without network access.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pyperclip
import pytest

from siphon.config.settings import reset_settings_cache
from siphon.engine.cancellation import DownloadCancelled
from siphon.engine.errors import CleanedYtdlpError
from siphon.models.phase import ErrorPhase, InputPhase, PickingPhase, ProbingPhase
from siphon.ui.app import SiphonApp
from siphon.ui.screens import main as main_mod


def _sample_info() -> dict[str, Any]:
    return {
        "title": "Rick Astley - Never Gonna Give You Up",
        "uploader": "RickAstleyVEVO",
        "duration": 213,
        "formats": [
            {
                "format_id": "140",
                "acodec": "aac",
                "vcodec": "none",
                "abr": 129,
                "filesize": 3_400_000,
            },
            {
                "format_id": "137",
                "height": 1080,
                "ext": "mp4",
                "vcodec": "avc1",
                "acodec": "none",
                "tbr": 4500,
                "filesize": 120_000_000,
            },
            {
                "format_id": "136",
                "height": 720,
                "ext": "mp4",
                "vcodec": "avc1",
                "acodec": "none",
                "tbr": 2500,
                "filesize": 70_000_000,
            },
        ],
    }


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    for name in list(os.environ):
        if name.startswith("SIPHON_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(pyperclip, "paste", lambda: "")
    reset_settings_cache()
    yield
    reset_settings_cache()


async def _await_phase(pilot: object, app: SiphonApp, kind: type, max_pauses: int = 30) -> None:
    """Pause until the app's phase is an instance of ``kind`` or we time out."""
    for _ in range(max_pauses):
        await pilot.pause()  # type: ignore[attr-defined]
        if isinstance(app.screen.phase, kind):  # type: ignore[attr-defined]
            return
    raise AssertionError(f"phase did not become {kind.__name__} in time")


class TestSuccessfulProbe:
    async def test_initial_url_transitions_to_picking(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
            return _sample_info()

        monkeypatch.setattr(main_mod, "probe", fake_probe)

        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            phase = app.screen.phase
            assert isinstance(phase, PickingPhase)
            assert phase.title.startswith("Rick Astley")
            assert phase.uploader == "RickAstleyVEVO"
            assert phase.duration_s == 213
            assert len(phase.choices) == 3  # 1080p, 720p, audio

    async def test_submit_url_transitions_to_picking(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
            return _sample_info()

        monkeypatch.setattr(main_mod, "probe", fake_probe)

        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            for ch in "https://youtu.be/xyz":
                await pilot.press(ch)
            await pilot.press("enter")
            await _await_phase(pilot, app, PickingPhase)

    async def test_choice_selection_launches_download(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """After M5, picking a row transitions to :class:`DownloadingPhase`."""

        async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
            return _sample_info()

        async def hang_download(**kwargs: Any) -> None:
            # Never resolve — we just want to observe the transition.
            token = kwargs["token"]
            while not token.cancelled:
                await asyncio.sleep(0.1)

        monkeypatch.setattr(main_mod, "probe", fake_probe)
        monkeypatch.setattr(main_mod, "run_download", hang_download)

        from siphon.models.phase import DownloadingPhase  # noqa: PLC0415

        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen.phase, DownloadingPhase)
            assert app.screen.phase.choice.kind in ("video", "audio")


class TestErrorPath:
    async def test_cleaned_error_transitions_to_error_phase(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
            raise CleanedYtdlpError("Video unavailable")

        monkeypatch.setattr(main_mod, "probe", fake_probe)

        app = SiphonApp(initial_url="https://youtu.be/nope")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, ErrorPhase)
            assert isinstance(app.screen.phase, ErrorPhase)
            assert "Video unavailable" in app.screen.phase.message

    async def test_error_enter_returns_to_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
            raise CleanedYtdlpError("nope")

        monkeypatch.setattr(main_mod, "probe", fake_probe)

        app = SiphonApp(initial_url="https://youtu.be/nope")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, ErrorPhase)
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)


class TestCancelDuringProbe:
    async def test_esc_during_probe_returns_to_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # A slow probe that respects cancellation.
        async def slow_probe(_url: str, token: object = None) -> dict[str, Any]:
            await asyncio.sleep(2.0)  # long enough for us to cancel
            if token is not None and getattr(token, "cancelled", False):
                raise DownloadCancelled()
            return _sample_info()

        monkeypatch.setattr(main_mod, "probe", slow_probe)

        app = SiphonApp(initial_url="https://slow.example/x")
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert isinstance(app.screen.phase, ProbingPhase)
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
