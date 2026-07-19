"""Theme model — the three modes and their cycle order.

The concrete colors and Textual registration live in :mod:`siphon.ui.theme`;
this module is pure data and safe to import from anywhere (no Textual dep).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

ThemeMode = Literal["auto", "light", "dark"]

THEME_MODES: Final[tuple[ThemeMode, ...]] = ("auto", "light", "dark")
"""Cycle order for ``ctrl+t`` — matches yoinks: auto → light → dark → auto."""


def is_theme_mode(value: str) -> bool:
    """Type guard: ``True`` iff ``value`` is one of the three theme modes."""
    return value in THEME_MODES


def next_theme_mode(current: ThemeMode) -> ThemeMode:
    """Return the next theme in the cycle."""
    index = THEME_MODES.index(current)
    return THEME_MODES[(index + 1) % len(THEME_MODES)]


@dataclass(frozen=True, slots=True)
class ThemePalette:
    """Concrete colors for a theme mode.

    ``auto`` uses ``None`` for background/primary so terminal palette shows
    through (yoinks parity: ``dimSecondary=True``, ``inverseButton=True``).
    """

    mode: ThemeMode
    background: str | None
    primary: str
    secondary: str
    accent: str
    dim_secondary: bool
    inverse_button: bool


# Siphon-branded swatches. See plan §Visual Identity for rationale.
PALETTES: Final[dict[ThemeMode, ThemePalette]] = {
    "auto": ThemePalette(
        mode="auto",
        background=None,
        primary="default",
        secondary="default",
        accent="default",
        dim_secondary=True,
        inverse_button=True,
    ),
    "light": ThemePalette(
        mode="light",
        background="#fafafa",
        primary="#0f172a",
        secondary="#475569",
        accent="#0369a1",
        dim_secondary=False,
        inverse_button=True,
    ),
    "dark": ThemePalette(
        mode="dark",
        background="#0f172a",
        primary="#f1f5f9",
        secondary="#94a3b8",
        accent="#38bdf8",
        dim_secondary=False,
        inverse_button=True,
    ),
}


def palette_for(mode: ThemeMode) -> ThemePalette:
    """Return the :class:`ThemePalette` associated with ``mode``."""
    return PALETTES[mode]
