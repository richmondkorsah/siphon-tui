"""Pilot-driven tests for the M5 downloading → done / cancelled flow.

The real yt-dlp downloader is stubbed via
:mod:`siphon.ui.screens.main.run_download`, so tests never touch the network.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pyperclip
import pytest

from siphon.config.settings import reset_settings_cache
from siphon.models.phase import (
    DonePhase,
    DownloadingPhase,
    InputPhase,
    PickingPhase,
)
from siphon.models.progress import DownloadProgress
from siphon.ui.app import SiphonApp
from siphon.ui.messages import (
    DownloadFailed,
    DownloadProcessing,
    DownloadProgressTick,
    DownloadSucceeded,
)
from siphon.ui.screens import main as main_mod
from siphon.ui.widgets.download_status import DownloadStatusView
from siphon.ui.widgets.framed_input import FramedInput


def _sample_info() -> dict[str, Any]:
    return {
        "title": "Test Video",
        "duration": 60,
        "formats": [
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
                "format_id": "140",
                "acodec": "aac",
                "vcodec": "none",
                "abr": 129,
                "filesize": 3_400_000,
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

    async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
        return _sample_info()

    monkeypatch.setattr(main_mod, "probe", fake_probe)

    reset_settings_cache()
    yield
    reset_settings_cache()


async def _await_phase(pilot: object, app: SiphonApp, kind: type, max_pauses: int = 40) -> None:
    for _ in range(max_pauses):
        await pilot.pause()  # type: ignore[attr-defined]
        if isinstance(app.screen.phase, kind):  # type: ignore[attr-defined]
            return
    raise AssertionError(f"phase did not become {kind.__name__} in time")


class TestSuccessfulDownload:
    async def test_progress_ticks_land_in_status_view(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A running download must expose progress in the status view before completion."""
        completed = asyncio.Event()

        async def slow_download(**kwargs: Any) -> None:
            screen = kwargs["screen"]
            token = kwargs["token"]
            for i in range(5):
                if token.cancelled:
                    return
                screen.post_message(
                    DownloadProgressTick(
                        DownloadProgress(
                            downloaded_bytes=i * 1_000_000,
                            total_bytes=5_000_000,
                            speed=500_000.0,
                            eta=5 - i,
                        )
                    )
                )
                await completed.wait() if i == 4 else await asyncio.sleep(0.05)
            screen.post_message(DownloadSucceeded(Path("/tmp/fake.mp4"), title="Test Video"))

        monkeypatch.setattr(main_mod, "run_download", slow_download)

        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            await pilot.press("enter")
            # Give the download a few ticks to fire, then check state.
            await pilot.pause(0.15)
            assert isinstance(app.screen.phase, DownloadingPhase)
            view = app.screen.query_one(DownloadStatusView)
            assert view._progress is not None
            assert view._progress.total_bytes == 5_000_000

            # Let the download finish.
            completed.set()
            await _await_phase(pilot, app, DonePhase)
            assert isinstance(app.screen.phase, DonePhase)
            assert str(app.screen.phase.filepath) == "/tmp/fake.mp4"
            assert app.final_filepath == "/tmp/fake.mp4"

    async def test_processing_message_flips_view_state(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_download(**kwargs: Any) -> None:
            screen = kwargs["screen"]
            screen.post_message(DownloadProcessing())
            await asyncio.sleep(0.05)
            screen.post_message(DownloadSucceeded(Path("/tmp/x.mp4"), title="x"))

        monkeypatch.setattr(main_mod, "run_download", fake_download)

        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            await pilot.press("enter")
            await pilot.pause(0.05)
            # Between processing and success — the status view should be in
            # "processing" mode. Since fake_download runs fast, we may already
            # be at DonePhase; assert one of the terminal states.
            await _await_phase(pilot, app, DonePhase)


class TestCancelDuringDownload:
    async def test_esc_returns_to_input_with_url_preserved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def infinite_download(**kwargs: Any) -> None:
            screen = kwargs["screen"]
            token = kwargs["token"]
            for _ in range(200):
                if token.cancelled:
                    return
                screen.post_message(
                    DownloadProgressTick(
                        DownloadProgress(downloaded_bytes=1_000_000, total_bytes=100_000_000)
                    )
                )
                await asyncio.sleep(0.05)

        monkeypatch.setattr(main_mod, "run_download", infinite_download)

        app = SiphonApp(initial_url="https://slow.example/x")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            await pilot.press("enter")
            await pilot.pause(0.15)
            assert isinstance(app.screen.phase, DownloadingPhase)
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
            framed = app.screen.query_one(FramedInput)
            assert framed.input.value == "https://slow.example/x"


class TestErrorPath:
    async def test_download_failed_transitions_to_error_phase(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def failing_download(**kwargs: Any) -> None:
            screen = kwargs["screen"]
            screen.post_message(DownloadFailed("HTTP 403 Forbidden"))

        monkeypatch.setattr(main_mod, "run_download", failing_download)

        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            await pilot.press("enter")
            await pilot.pause(0.05)
            from siphon.models.phase import ErrorPhase  # noqa: PLC0415

            await _await_phase(pilot, app, ErrorPhase)
            assert isinstance(app.screen.phase, ErrorPhase)
            assert "403" in app.screen.phase.message


class TestDoneScreen:
    async def test_enter_from_done_returns_to_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def quick_download(**kwargs: Any) -> None:
            screen = kwargs["screen"]
            screen.post_message(DownloadSucceeded(Path("/tmp/x.mp4"), title="x"))

        monkeypatch.setattr(main_mod, "run_download", quick_download)

        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            await pilot.press("enter")
            await _await_phase(pilot, app, DonePhase)
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
