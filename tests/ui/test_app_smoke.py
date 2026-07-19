"""Smoke tests for :class:`siphon.ui.app.SiphonApp`.

Uses Textual's ``Pilot`` (via ``App.run_test()``) to spin up the app in a
headless driver, ensure it mounts, then press ``ctrl+c`` and confirm it
exits without exceptions. This guards against regressions that would leave
the terminal in a broken state after a real-world crash.
"""

from __future__ import annotations

import pytest

from siphon.ui.app import SiphonApp


@pytest.mark.asyncio
async def test_app_mounts_and_quits_cleanly() -> None:
    """The app must mount its main screen and honour ctrl+c."""
    app = SiphonApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.screen is not None
        await pilot.press("ctrl+c")
        await pilot.pause()


@pytest.mark.asyncio
async def test_app_accepts_initial_url_argument() -> None:
    """CLI-provided initial_url must round-trip into the App."""
    app = SiphonApp(initial_url="https://youtu.be/dQw4w9WgXcQ")
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.initial_url == "https://youtu.be/dQw4w9WgXcQ"
        await pilot.press("ctrl+c")
