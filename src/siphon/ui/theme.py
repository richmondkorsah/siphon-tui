"""Textual theme registration for Siphon.

Textual 0.83+ exposes a :class:`~textual.theme.Theme` object that maps a name
to a set of color variables (``$primary``, ``$background``, etc.). We register
one theme per mode (``siphon-auto``, ``siphon-light``, ``siphon-dark``); the
App swaps between them via :attr:`~textual.app.App.theme` when the user
presses ``ctrl+t``.

For ``siphon-auto`` we deliberately omit ``background`` / ``primary`` so the
terminal's own palette shows through (yoinks F19 parity).
"""

from __future__ import annotations

from typing import Final

from textual.theme import Theme

from siphon.models.theme import PALETTES, THEME_MODES, ThemeMode

_THEME_PREFIX: Final[str] = "siphon-"


def theme_name(mode: ThemeMode) -> str:
    """The Textual theme identifier for a given Siphon mode."""
    return f"{_THEME_PREFIX}{mode}"


def _build_theme(mode: ThemeMode) -> Theme:
    """Construct a :class:`textual.theme.Theme` from the palette definition."""
    palette = PALETTES[mode]
    is_dark = mode == "dark"

    kwargs: dict[str, str | bool] = {
        "name": theme_name(mode),
        "dark": is_dark,
        # Rich/Textual demands non-None strings for these; use "auto"-safe fallbacks.
        "primary": palette.primary if palette.primary != "default" else "#94a3b8",
        "secondary": palette.secondary if palette.secondary != "default" else "#64748b",
        "accent": palette.accent if palette.accent != "default" else "#38bdf8",
    }

    if palette.background is not None:
        kwargs["background"] = palette.background
        kwargs["foreground"] = palette.primary

    return Theme(**kwargs)  # type: ignore[arg-type]


def all_themes() -> list[Theme]:
    """Return the three Siphon themes, in cycle order."""
    return [_build_theme(mode) for mode in THEME_MODES]
