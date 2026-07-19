"""Shortcuts footer — the key/label hint row shown at the bottom of every screen.

Each hint is a ``(key, label)`` pair rendered as ``key label`` with a `` · ``
separator between pairs. The M2 scaffold renders a static Rich renderable;
click-to-fire wiring (each hint becomes a clickable target if its key has an
action) lands in M3 alongside the input phase.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.text import Text
from textual.widget import Widget


@dataclass(frozen=True, slots=True)
class Hint:
    """A single key/label pair to show in the footer.

    ``action`` is the App action name to fire when the hint is clicked; when
    ``None`` the hint is display-only (e.g. ``↑ history`` where the click has
    no meaningful analog).
    """

    key: str
    label: str
    action: str | None = None


class ShortcutsWidget(Widget):
    """Renders a horizontal list of :class:`Hint` pairs at the bottom of the app."""

    DEFAULT_CSS = """
    ShortcutsWidget {
        height: 1;
        width: 100%;
        content-align: center middle;
        color: $text-muted;
    }
    """

    def __init__(
        self,
        hints: list[Hint] | None = None,
        *,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._hints: list[Hint] = hints or []

    @property
    def hints(self) -> list[Hint]:
        """Currently displayed hints (in render order)."""
        return list(self._hints)

    def set_hints(self, hints: list[Hint]) -> None:
        """Replace the hint list and trigger a re-render."""
        self._hints = list(hints)
        self.refresh()

    def render(self) -> Text:
        """Compose ``key label · key label · …`` as a styled Rich Text."""
        text = Text(no_wrap=True, overflow="ellipsis")
        for i, hint in enumerate(self._hints):
            if i > 0:
                text.append("  ·  ", style="dim")
            text.append(hint.key, style="bold")
            text.append(" ")
            text.append(hint.label, style="dim")
        return text
