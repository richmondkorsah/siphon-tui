"""Searchable history modal (yoinks M7 extra, bound to ``ctrl+r``).

Renders as a Textual :class:`ModalScreen`: a filter input at top and a
:class:`ListView` of past URLs (with title / platform metadata when the
JSONL history has it). Enter picks the highlighted row and returns the
URL to the caller via :meth:`dismiss`; Esc dismisses with ``None``.

Filtering is case-insensitive substring match across URL, title, and
platform label — deliberately simple. A fuzzy-search library would add a
dependency for marginal benefit on the typical <50-row list.
"""

from __future__ import annotations

import contextlib
from typing import ClassVar

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from siphon.models.history_entry import HistoryEntry


class HistoryRow(ListItem):
    """One row: a rich-rendered URL + optional metadata suffix."""

    DEFAULT_CSS = """
    HistoryRow {
        height: 1;
        padding: 0 1;
        background: transparent;
    }
    HistoryRow > Static {
        width: 100%;
        color: $foreground;
        background: transparent;
    }
    HistoryRow.-highlight,
    HistoryRow.--highlight {
        background: transparent;
    }
    HistoryRow.-highlight > Static,
    HistoryRow.--highlight > Static {
        color: $accent;
        text-style: bold;
    }
    """

    def __init__(self, entry: HistoryEntry) -> None:
        super().__init__(Static(_render_row(entry)))
        self.entry = entry


def _render_row(entry: HistoryEntry) -> Text:
    """Compose ``url  · platform · title`` styled Rich text."""
    text = Text(no_wrap=True, overflow="ellipsis")
    text.append(entry.url, style="")
    tail_parts: list[str] = []
    if entry.platform:
        tail_parts.append(entry.platform)
    if entry.title:
        tail_parts.append(entry.title)
    if tail_parts:
        text.append("  · ", style="dim")
        text.append(" · ".join(tail_parts), style="dim")
    return text


class HistoryModal(ModalScreen[str | None]):
    """A pop-over showing prior URLs; :meth:`dismiss` returns the picked URL or ``None``."""

    DEFAULT_CSS = """
    HistoryModal {
        align: center middle;
    }
    HistoryModal > Vertical {
        width: 90%;
        max-width: 90;
        height: 60%;
        max-height: 24;
        border: round $primary;
        border-title-color: $primary;
        border-title-align: left;
        padding: 1 2;
        background: $background;
    }
    HistoryModal #history-filter {
        border: none;
        padding: 0;
        margin-bottom: 1;
        height: 1;
        background: transparent;
    }
    HistoryModal #history-list {
        height: 1fr;
        background: transparent;
    }
    HistoryModal #history-empty {
        color: $text-muted;
        text-style: dim;
        content-align: center middle;
        height: 1fr;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "cancel", show=False),
        Binding("enter", "pick_current", "pick", show=False, priority=True),
        Binding("down", "focus_list", "list", show=False),
        Binding("up", "focus_list", "list", show=False),
    ]

    def __init__(self, entries: list[HistoryEntry]) -> None:
        super().__init__()
        self._entries = entries

    def compose(self) -> ComposeResult:
        """Yield the framed modal body: filter + list."""
        with Vertical() as container:
            container.border_title = "history"
            yield Input(placeholder="filter urls…", id="history-filter")
            yield ListView(id="history-list")

    def on_mount(self) -> None:
        """Populate and focus the filter input."""
        self._populate("")
        with contextlib.suppress(NoMatches):
            self.query_one(Input).focus()

    # ---------------------------------------------------------------- events
    def on_input_changed(self, event: Input.Changed) -> None:
        """Live-refilter the list as the user types."""
        event.stop()
        self._populate(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Enter in the filter picks the first matching row."""
        event.stop()
        self.action_pick_current()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter (or click) on a row picks it and dismisses the modal."""
        event.stop()
        item = event.item
        if isinstance(item, HistoryRow):
            self.dismiss(item.entry.url)

    # ---------------------------------------------------------------- actions
    def action_cancel(self) -> None:
        """Esc — dismiss without a selection."""
        self.dismiss(None)

    def action_pick_current(self) -> None:
        """Pick whichever row is currently highlighted."""
        try:
            listview = self.query_one(ListView)
        except NoMatches:
            self.dismiss(None)
            return
        item = listview.highlighted_child
        if isinstance(item, HistoryRow):
            self.dismiss(item.entry.url)
        elif listview.children:
            # No highlight yet — pick the first row.
            first = listview.children[0]
            if isinstance(first, HistoryRow):
                self.dismiss(first.entry.url)

    def action_focus_list(self) -> None:
        """↑/↓ in the filter jumps focus into the list."""
        try:
            listview = self.query_one(ListView)
        except NoMatches:
            return
        listview.focus()

    # ----------------------------------------------------------- population
    def _populate(self, query: str) -> None:
        """Rebuild the list with only entries matching ``query``."""
        try:
            listview = self.query_one(ListView)
        except NoMatches:
            return
        listview.clear()

        matches = _filter(self._entries, query)
        if not matches:
            listview.append(ListItem(Static("no matches", id="history-empty")))
            return
        for entry in matches:
            listview.append(HistoryRow(entry))
        # Highlight the first row so ↵ from the input picks something sensible.
        if listview.children:
            listview.index = 0


def _filter(entries: list[HistoryEntry], query: str) -> list[HistoryEntry]:
    """Case-insensitive substring match across url, title, platform."""
    q = query.strip().lower()
    if not q:
        return entries
    result: list[HistoryEntry] = []
    for entry in entries:
        haystack = entry.url.lower()
        if entry.title:
            haystack += " " + entry.title.lower()
        if entry.platform:
            haystack += " " + entry.platform.lower()
        if q in haystack:
            result.append(entry)
    return result
