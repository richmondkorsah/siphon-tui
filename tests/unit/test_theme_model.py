"""Tests for :mod:`siphon.models.theme` — pure data, no Textual dep."""

from __future__ import annotations

import pytest

from siphon.models.theme import (
    PALETTES,
    THEME_MODES,
    ThemeMode,
    is_theme_mode,
    next_theme_mode,
    palette_for,
)


class TestThemeModeGuards:
    @pytest.mark.parametrize("mode", THEME_MODES)
    def test_accepts_valid_modes(self, mode: str) -> None:
        assert is_theme_mode(mode) is True

    @pytest.mark.parametrize("mode", ["", "sepia", "AUTO", "high-contrast"])
    def test_rejects_invalid_modes(self, mode: str) -> None:
        assert is_theme_mode(mode) is False


class TestNextThemeMode:
    def test_cycle_order_matches_yoinks(self) -> None:
        # auto → light → dark → auto (yoinks parity)
        assert next_theme_mode("auto") == "light"
        assert next_theme_mode("light") == "dark"
        assert next_theme_mode("dark") == "auto"

    def test_full_cycle_returns_to_start(self) -> None:
        seen: list[ThemeMode] = ["auto"]
        for _ in range(3):
            seen.append(next_theme_mode(seen[-1]))
        assert seen[0] == seen[-1] == "auto"


class TestPalettes:
    def test_every_mode_has_a_palette(self) -> None:
        assert set(PALETTES.keys()) == set(THEME_MODES)

    def test_auto_has_no_explicit_background(self) -> None:
        # auto = "let the terminal palette win" — yoinks F19 parity
        assert PALETTES["auto"].background is None

    def test_concrete_modes_have_background(self) -> None:
        assert PALETTES["light"].background == "#fafafa"
        assert PALETTES["dark"].background == "#0f172a"

    def test_palette_for_lookup(self) -> None:
        assert palette_for("dark").primary == "#f1f5f9"
