"""Tests for :mod:`siphon.config.settings` — TOML round-trip + env override."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from siphon.config import paths as paths_mod
from siphon.config.settings import SiphonSettings, reset_settings_cache


@pytest.fixture(autouse=True)
def _isolate_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect XDG_CONFIG_HOME to a per-test tmp dir; drop cached singleton."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    # Clear any SIPHON_* env leftovers from other tests.
    for name in list(os.environ):
        if name.startswith("SIPHON_"):
            monkeypatch.delenv(name, raising=False)
    reset_settings_cache()
    yield
    reset_settings_cache()


class TestDefaults:
    def test_first_run_uses_auto_theme(self) -> None:
        settings = SiphonSettings.load()
        assert settings.theme_mode == "auto"

    def test_first_run_uses_xdg_downloads(self, tmp_path: Path) -> None:
        settings = SiphonSettings.load()
        assert settings.download_dir == tmp_path / "downloads"

    def test_check_updates_defaults_true(self) -> None:
        assert SiphonSettings.load().check_updates is True


class TestPersistence:
    def test_save_and_reload_round_trips(self, tmp_path: Path) -> None:
        s = SiphonSettings.load()
        s.theme_mode = "dark"
        s.check_updates = False
        s.save()

        reset_settings_cache()
        reloaded = SiphonSettings.load()
        assert reloaded.theme_mode == "dark"
        assert reloaded.check_updates is False

    def test_config_file_lands_under_xdg(self, tmp_path: Path) -> None:
        SiphonSettings.load().save()
        assert paths_mod.config_file().parent == tmp_path / "siphon"
        assert paths_mod.config_file().exists()


class TestEnvOverride:
    def test_env_wins_over_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # File says dark, env says light — env should win.
        s = SiphonSettings.load()
        s.theme_mode = "dark"
        s.save()
        reset_settings_cache()

        monkeypatch.setenv("SIPHON_THEME_MODE", "light")
        reset_settings_cache()
        assert SiphonSettings.load().theme_mode == "light"
