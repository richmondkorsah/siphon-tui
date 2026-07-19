"""Block-character progress bar (yoinks F14).

The bar is a fixed-width row of ``█`` (filled) + ``░`` (empty) with a padded
percentage suffix. Fixed width matters — yoinks explicitly went out of its
way to keep the line width constant so the surrounding meta line never
re-flows on every tick.
"""

from __future__ import annotations

import math
from typing import Final

from rich.text import Text
from textual.widget import Widget

BAR_WIDTH: Final[int] = 30
"""Cells occupied by the bar itself (excluding the ``  100%`` suffix)."""

_FILLED = "█"
_EMPTY = "░"


class ProgressBar(Widget):
    """A fixed-width block bar. Updates via :meth:`set_fraction` + :meth:`refresh`."""

    DEFAULT_CSS = f"""
    ProgressBar {{
        width: {BAR_WIDTH + 6};
        height: 1;
    }}
    """

    def __init__(self, fraction: float = 0.0, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._fraction = _clamp01(fraction)

    def set_fraction(self, fraction: float) -> None:
        """Update the fill ratio and repaint."""
        new_fraction = _clamp01(fraction)
        if new_fraction != self._fraction:
            self._fraction = new_fraction
            self.refresh()

    def render(self) -> Text:
        """Return ``█████░░░░░  45%``-style Rich Text."""
        filled = round(self._fraction * BAR_WIDTH)
        empty = BAR_WIDTH - filled
        percent = round(self._fraction * 100)
        text = Text(no_wrap=True, overflow="crop")
        text.append(_FILLED * filled, style="bold")
        text.append(_EMPTY * empty, style="dim")
        text.append(f" {percent:>3}%", style="bold")
        return text


def _clamp01(value: float) -> float:
    """Clamp ``value`` into ``[0.0, 1.0]``. NaN maps to 0.0."""
    if math.isnan(value):
        return 0.0
    return max(0.0, min(1.0, value))
