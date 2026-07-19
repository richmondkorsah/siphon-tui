"""End-to-end Pilot walk of the golden path.

Exercises every phase transition with a mocked probe + download so nothing
touches the network. Complements the per-phase tests by asserting that all
the layers wire up when driven from a single user session.
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
from siphon.ui.messages import DownloadProgressTick, DownloadSucceeded
from siphon.ui.screens import main as main_mod
from siphon.ui.widgets.download_status import DownloadStatusView
from siphon.ui.widgets.framed_input import FramedInput


def _sample_info() -> dict[str, Any]:
    return {
        "title": "End-to-end test",
        "uploader": "Test Channel",
        "duration": 42,
        "formats": [
            {
                "format_id": "137",
                "height": 1080,
                "ext": "mp4",
                "vcodec": "avc1",
                "acodec": "none",
                "tbr": 4500,
                "filesize": 100_000_000,
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
    reset_settings_cache()
    yield
    reset_settings_cache()


async def _await_phase(pilot: object, app: SiphonApp, kind: type, max_pauses: int = 40) -> None:
    for _ in range(max_pauses):
        await pilot.pause()  # type: ignore[attr-defined]
        if isinstance(app.screen.phase, kind):  # type: ignore[attr-defined]
            return
    raise AssertionError(f"phase did not become {kind.__name__} in time")


class TestGoldenPath:
    async def test_paste_pick_download_done(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Full walk: launch → type URL → pick 1080p → download → done."""
        completion = asyncio.Event()
        hold_until_release = asyncio.Event()

        async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
            return _sample_info()

        async def fake_download(**kwargs: Any) -> None:
            screen = kwargs["screen"]
            token = kwargs["token"]
            # Emit some progress ticks — completion is gated on an event so
            # the test can pause inside the downloading phase deterministically.
            for i in range(3):
                if token.cancelled:
                    return
                screen.post_message(
                    DownloadProgressTick(
                        DownloadProgress(
                            downloaded_bytes=(i + 1) * 1_000_000,
                            total_bytes=3_000_000,
                            speed=500_000.0,
                            eta=3 - i,
                        )
                    )
                )
                await asyncio.sleep(0.02)
            # Hold at 100% until the test explicitly says "go".
            await hold_until_release.wait()
            screen.post_message(DownloadSucceeded(Path("/tmp/e2e.mp4"), title="End-to-end test"))
            completion.set()

        monkeypatch.setattr(main_mod, "probe", fake_probe)
        monkeypatch.setattr(main_mod, "run_download", fake_download)

        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            # 1) Input phase after mount.
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)

            # 2) Type a URL + submit.
            for ch in "https://youtu.be/e2e":
                await pilot.press(ch)
            await pilot.press("enter")

            # 3) Probing → picking. We may miss the ProbingPhase in the
            # message queue race — the important thing is arriving at picking.
            await _await_phase(pilot, app, PickingPhase)
            picking = app.screen.phase
            assert isinstance(picking, PickingPhase)
            assert len(picking.choices) == 2  # 1080p + audio

            # 4) Pick the first choice (1080p) → downloading.
            await pilot.press("enter")
            await _await_phase(pilot, app, DownloadingPhase)
            view = app.screen.query_one(DownloadStatusView)
            # Give at least one tick time to land.
            await pilot.pause(0.1)
            assert view._progress is not None

            # 5) Release the download hold and wait for done.
            hold_until_release.set()
            await _await_phase(pilot, app, DonePhase)
            done = app.screen.phase
            assert isinstance(done, DonePhase)
            assert str(done.filepath) == "/tmp/e2e.mp4"
            assert app.final_filepath == "/tmp/e2e.mp4"

            # 6) ↵ from done returns to input.
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)

    async def test_cancel_during_download_preserves_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        async def fake_probe(_url: str, _token: object = None) -> dict[str, Any]:
            return _sample_info()

        async def slow_download(**kwargs: Any) -> None:
            token = kwargs["token"]
            while not token.cancelled:
                await asyncio.sleep(0.05)

        monkeypatch.setattr(main_mod, "probe", fake_probe)
        monkeypatch.setattr(main_mod, "run_download", slow_download)

        app = SiphonApp(initial_url="https://youtu.be/preserved")
        async with app.run_test(size=(120, 30)) as pilot:
            await _await_phase(pilot, app, PickingPhase)
            await pilot.press("enter")
            await _await_phase(pilot, app, DownloadingPhase)
            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen.phase, InputPhase)
            framed = app.screen.query_one(FramedInput)
            assert framed.input.value == "https://youtu.be/preserved"
