"""Panel — a titled bordered container (yoinks F24).

The panel used on the picking phase to hold the choice list. Textual's
``border: round`` + ``border_title`` machinery matches yoinks' hand-drawn
title-on-border trick without any of the SGR bookkeeping.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container


class Panel(Container):
    """A rounded-bordered container with a title docked on the top border.

    Use like a Container:

    .. code-block:: python

        yield Panel(title="Download") | (child_widgets)
    """

    DEFAULT_CSS = """
    Panel {
        border: round $primary;
        border-title-color: $primary;
        border-title-align: left;
        padding: 0 1;
        height: auto;
        width: auto;
    }
    """

    def __init__(
        self,
        *children: object,
        title: str = "",
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(*children, id=id, classes=classes)  # type: ignore[arg-type]
        self._title = title

    def on_mount(self) -> None:
        """Attach the title to the top border once the widget is in the DOM."""
        self.border_title = self._title

    def compose(self) -> ComposeResult:
        """Yield nothing by default — children come from the parent's compose."""
        return iter(())

    def set_title(self, title: str) -> None:
        """Update the border title after construction."""
        self._title = title
        self.border_title = title
