"""Pilot-driven tests for the M7 command palette (^p) provider."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pyperclip
import pytest

from siphon.config.settings import reset_settings_cache
from siphon.ui.app import SiphonApp
from siphon.ui.commands import SiphonCommands
from siphon.ui.screens import main as main_mod


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


class TestPaletteBinding:
    async def test_ctrl_p_opens_command_palette(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+p")
            await pilot.pause()
            assert type(app.screen).__name__ == "CommandPalette"

    async def test_esc_closes_palette(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+p")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert type(app.screen).__name__ != "CommandPalette"


class TestProviderCommands:
    async def test_provider_registered_on_app(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            assert SiphonCommands in type(app).COMMANDS

    async def test_theme_hits_exclude_current_mode(self) -> None:
        """The "Switch to X theme" command list omits the current mode."""
        app = SiphonApp(theme_mode_override="dark")
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            # Instantiate the provider standalone — no palette navigation needed.
            # Textual's ``Provider.__init__`` needs a screen + matcher config, so
            # we go through the palette-open path and query its Provider.
            await pilot.press("ctrl+p")
            await pilot.pause()

            # Look for the Siphon-provided hits by discovery.
            provider = None
            for p in app.screen._providers:  # type: ignore[attr-defined]
                if isinstance(p, SiphonCommands):
                    provider = p
                    break
            assert provider is not None
            displays = [c.display async for c in provider.discover()]
            assert "Switch to auto theme" in displays
            assert "Switch to light theme" in displays
            # Current mode is dark → should NOT appear as a switch option.
            assert "Switch to dark theme" not in displays

    async def test_quit_command_present(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+p")
            await pilot.pause()

            provider = None
            for p in app.screen._providers:  # type: ignore[attr-defined]
                if isinstance(p, SiphonCommands):
                    provider = p
                    break
            assert provider is not None
            displays = [c.display async for c in provider.discover()]
            assert "Quit" in displays
            assert "Open history" in displays
            assert "Paste from clipboard" in displays
