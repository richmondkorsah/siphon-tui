"""The tagline strip: two lines shown under the logo on every phase."""

from __future__ import annotations

from rich.text import Text
from textual.widget import Widget

from siphon.config.constants import PLATFORM_STRIP, TAGLINE


class TaglineStrip(Widget):
    """Two centred lines: the brand tagline in primary, the platform list dim.

    The widget is intrinsically sized to the *widest* of its two lines, then
    the enclosing ``Center`` container handles horizontal centering. This
    matches the yoinks reference where each line has its own centering
    (tagline aligned relative to itself, platform strip aligned relative to
    itself) — no full-width padding creating an off-centre optical anchor.
    """

    DEFAULT_CSS = """
    TaglineStrip {
        height: 2;
        width: auto;
        content-align: center top;
    }
    """

    def render(self) -> Text:
        """Compose two centred lines, each padded to the widest-line width."""
        width = max(len(TAGLINE), len(PLATFORM_STRIP))
        text = Text(no_wrap=False, justify="center")
        text.append(TAGLINE.center(width), style="bold")
        text.append("\n")
        text.append(PLATFORM_STRIP.center(width), style="dim")
        return text
