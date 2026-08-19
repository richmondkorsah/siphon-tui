"""ChoiceList — a keyboard/mouse-navigable list of :class:`DownloadChoice` rows.

Backed by Textual's :class:`~textual.widgets.ListView`. Each row shows the
choice's ``prefix + label`` (``▶ 1080p · mp4 · ~130 MB`` / ``♪ audio only``).

Selection fires a :class:`ChoiceSelected` message which the parent screen
maps to a download start (M5) or, for now, a return-to-input.

Key bindings inherit from ``ListView`` (``up`` / ``down`` / ``home`` /
``end`` / ``enter``); we add ``j``/``k`` for vim-flavoured navigation to
match yoinks parity.
"""

from __future__ import annotations

from typing import ClassVar

from rich.text import Text
from textual.binding import Binding, BindingType
from textual.message import Message
from textual.widgets import ListItem, ListView, Static

from siphon.models.choice import DownloadChoice, SubtitleChoice


class ChoiceSelected(Message):
    """User picked a :class:`DownloadChoice` from the picker."""

    def __init__(self, choice: DownloadChoice, index: int) -> None:
        super().__init__()
        self.choice = choice
        self.index = index


class SubtitleChoiceSelected(Message):
    """User picked a :class:`SubtitleChoice` from the subtitle picker."""

    def __init__(self, choice: SubtitleChoice, index: int) -> None:
        super().__init__()
        self.choice = choice
        self.index = index


class ChoiceRow(ListItem):
    """One row in the ChoiceList — renders a single :class:`DownloadChoice`.

    Textual's ``ListView`` paints the highlighted item with ``$accent`` as a
    background by default. We instead render the highlighted row by tinting
    the *foreground* (accent color, bold) and keeping the panel background
    intact — matches the yoinks reference where the current choice reads as
    coloured text, not an inverted rectangle.
    """

    DEFAULT_CSS = """
    ChoiceRow {
        height: 1;
        padding: 0 1;
        background: transparent;
    }
    ChoiceRow > Static {
        width: 100%;
        color: $foreground;
        background: transparent;
    }
    ChoiceRow.-highlight,
    ChoiceRow.--highlight {
        background: transparent;
    }
    ChoiceRow.-highlight > Static,
    ChoiceRow.--highlight > Static {
        color: $accent;
        text-style: bold;
    }
    """

    def __init__(self, choice: DownloadChoice) -> None:
        super().__init__(Static(self._render_text(choice)))
        self.choice = choice

    @staticmethod
    def _render_text(choice: DownloadChoice) -> Text:
        """Build the Rich Text for one row: prefix in accent, label plain."""
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append(choice.prefix, style="bold")
        text.append(choice.label)
        return text


class ChoiceList(ListView):
    """A ListView of :class:`DownloadChoice` rows with vim-style j/k support."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("enter", "select_cursor", "select", show=False),
    ]

    DEFAULT_CSS = """
    ChoiceList {
        height: auto;
        width: 1fr;
        background: transparent;
    }
    """

    def __init__(self, choices: list[DownloadChoice], *, id: str | None = None) -> None:
        super().__init__(
            *(ChoiceRow(c) for c in choices),
            id=id,
        )
        self._choices = list(choices)

    @property
    def choices(self) -> list[DownloadChoice]:
        """The choices currently displayed."""
        return list(self._choices)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Translate ``ListView.Selected`` into our typed :class:`ChoiceSelected`."""
        event.stop()
        item = event.item
        if isinstance(item, ChoiceRow):
            self.post_message(ChoiceSelected(item.choice, self.index or 0))


class SubtitleChoiceRow(ListItem):
    """One row in the SubtitleChoiceList — mirrors :class:`ChoiceRow`'s styling."""

    DEFAULT_CSS = ChoiceRow.DEFAULT_CSS.replace("ChoiceRow", "SubtitleChoiceRow")

    def __init__(self, choice: SubtitleChoice) -> None:
        super().__init__(Static(self._render_text(choice)))
        self.choice = choice

    @staticmethod
    def _render_text(choice: SubtitleChoice) -> Text:
        text = Text(no_wrap=True, overflow="ellipsis")
        text.append(choice.prefix, style="bold")
        text.append(choice.label)
        return text


class SubtitleChoiceList(ListView):
    """A ListView of :class:`SubtitleChoice` rows — same vim keys as :class:`ChoiceList`."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("j", "cursor_down", "down", show=False),
        Binding("k", "cursor_up", "up", show=False),
        Binding("enter", "select_cursor", "select", show=False),
    ]

    DEFAULT_CSS = """
    SubtitleChoiceList {
        height: auto;
        max-height: 12;
        width: 1fr;
        background: transparent;
        scrollbar-size-vertical: 1;
    }
    """
    """Caps at 12 rows so a long language list scrolls in place instead of
    pushing the shortcuts row off-screen; ``ListView`` handles arrow-key
    cursor movement and auto-scroll natively."""

    def __init__(self, choices: list[SubtitleChoice], *, id: str | None = None) -> None:
        super().__init__(
            *(SubtitleChoiceRow(c) for c in choices),
            id=id,
        )
        self._choices = list(choices)

    @property
    def choices(self) -> list[SubtitleChoice]:
        return list(self._choices)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        event.stop()
        item = event.item
        if isinstance(item, SubtitleChoiceRow):
            self.post_message(SubtitleChoiceSelected(item.choice, self.index or 0))
