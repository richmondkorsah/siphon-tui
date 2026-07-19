"""Pilot-driven test: ``ctrl+t`` cycles the theme and persists it."""

from __future__ import annotations

from pathlib import Path

import pytest

from siphon.config.settings import SiphonSettings, reset_settings_cache
from siphon.ui.app import SiphonApp
from siphon.ui.theme import theme_name


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    reset_settings_cache()
    yield
    reset_settings_cache()


@pytest.mark.asyncio
async def test_ctrl_t_cycles_theme_forward() -> None:
    """Starting in ``auto``, ctrl+t must advance to ``light``, then ``dark``, then back to ``auto``."""
    app = SiphonApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme_mode == "auto"
        assert app.theme == theme_name("auto")

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.theme_mode == "light"

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.theme_mode == "dark"

        await pilot.press("ctrl+t")
        await pilot.pause()
        assert app.theme_mode == "auto"


@pytest.mark.asyncio
async def test_theme_choice_persists_across_sessions() -> None:
    """The theme mode ``ctrl+t`` selects must survive an App restart."""
    app1 = SiphonApp()
    async with app1.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+t")  # auto → light
        await pilot.press("ctrl+t")  # light → dark
        await pilot.pause()

    # A fresh SiphonSettings load should see the persisted "dark".
    reset_settings_cache()
    reloaded = SiphonSettings.load()
    assert reloaded.theme_mode == "dark"

    # And a fresh App instance should boot into dark.
    app2 = SiphonApp()
    async with app2.run_test() as pilot:
        await pilot.pause()
        assert app2.theme_mode == "dark"


@pytest.mark.asyncio
async def test_env_override_takes_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    """``SIPHON_THEME_MODE=light`` should force the app to launch in light."""
    # Persist dark to disk first, so we can see env win.
    s = SiphonSettings.load()
    s.theme_mode = "dark"
    s.save()
    reset_settings_cache()

    monkeypatch.setenv("SIPHON_THEME_MODE", "light")
    reset_settings_cache()

    app = SiphonApp()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.theme_mode == "light"
