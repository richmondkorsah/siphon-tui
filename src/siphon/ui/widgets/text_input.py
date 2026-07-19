"""SiphonTextInput — a Textual :class:`~textual.widgets.Input` subclass.

Adds the yoinks-specific behaviours on top of Textual's built-in single-line
editor:

* **History recall** (F5): ``↑`` / ``↓`` walk newest → oldest. The current draft
  is saved on the first ``↑`` and restored when the user comes back past index 0.
* **Clipboard accept** (F4): ``⇥`` fills the field with the previously offered
  clipboard URL when the field is empty.
* **Paste-submit heuristic** (F5): pasting a URL into an *empty* field auto-
  submits, matching "paste. sip. done." — no extra Enter required.

Everything else — cursor, selection, word-jumps, backspace, ^A/^E/^K/^U/^W —
is Textual's native behaviour on :class:`~textual.widgets.Input`.
"""

from __future__ import annotations

from typing import ClassVar

from textual import events
from textual.binding import Binding, BindingType
from textual.widgets import Input

from siphon.services.platforms import is_probably_url
from siphon.ui.messages import ClipboardAccepted, SubmitRequested


class SiphonTextInput(Input):
    """The single-line URL editor shown inside :class:`FramedInput`."""

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("up", "history_prev", "history back", show=False),
        Binding("down", "history_next", "history forward", show=False),
        Binding("tab", "accept_clipboard", "accept clipboard", show=False),
    ]

    def __init__(
        self,
        *,
        history: list[str] | None = None,
        placeholder: str = "",
        id: str | None = None,
    ) -> None:
        super().__init__(placeholder=placeholder, id=id)
        self._history: list[str] = list(history) if history else []
        # -1 means "showing the current draft" (nothing recalled); 0..N-1
        # means "showing history[pos]" with 0 = most recent.
        self._history_pos: int = -1
        # The user's in-progress draft, saved when they first press ↑.
        self._draft: str = ""
        self._clipboard_suggestion: str | None = None

    # ------------------------------------------------------------------ history
    def set_history(self, history: list[str]) -> None:
        """Replace the recallable history without touching the current value."""
        self._history = list(history)
        self._history_pos = -1

    def action_history_prev(self) -> None:
        """Walk backwards in history (newest → oldest). Saves the draft on first press."""
        if not self._history:
            return
        if self._history_pos == -1:
            self._draft = self.value
        self._history_pos = min(self._history_pos + 1, len(self._history) - 1)
        self._set_value_from_history()

    def action_history_next(self) -> None:
        """Walk forwards in history (oldest → newest → back to draft)."""
        if self._history_pos == -1:
            return
        self._history_pos -= 1
        if self._history_pos == -1:
            self.value = self._draft
        else:
            self._set_value_from_history()

    def _set_value_from_history(self) -> None:
        self.value = self._history[self._history_pos]
        # Place cursor at end — matches shell-style history recall UX.
        self.cursor_position = len(self.value)

    # -------------------------------------------------------- clipboard accept
    def set_clipboard_suggestion(self, url: str | None) -> None:
        """Register (or clear) the currently offered clipboard URL."""
        self._clipboard_suggestion = url

    def action_accept_clipboard(self) -> None:
        """Fill the field with the offered clipboard URL, if any and the field is empty."""
        url = self._clipboard_suggestion
        if url and not self.value:
            self.value = url
            self.cursor_position = len(url)
            self.post_message(ClipboardAccepted(url))

    # ----------------------------------------------------------- paste-submit
    def _on_paste(self, event: events.Paste) -> None:
        """Auto-submit if the paste completes a URL into a previously-empty field.

        This is the "paste. sip. done." UX — the user shouldn't have to press
        Enter after pasting a valid URL into an empty box.
        """
        was_empty = not self.value.strip()
        # Let Textual insert the pasted text first.
        super()._on_paste(event)
        if was_empty and is_probably_url(self.value.strip()):
            self.post_message(SubmitRequested(self.value.strip()))

    # --------------------------------------------------------------- submit
    def submit_now(self) -> None:
        """Emit :class:`SubmitRequested` if the current value is non-empty."""
        value = self.value.strip()
        if value:
            self.post_message(SubmitRequested(value))

    async def action_submit(self) -> None:
        """Enter-key handler — delegates to :meth:`submit_now`.

        Textual's own :class:`~textual.widgets.Input.Submitted` message is not
        emitted; we use our own :class:`SubmitRequested` so screen-level
        handlers don't need to disambiguate between "our" and "Textual's"
        submit events.
        """
        self.submit_now()

    # ------------------------------------------------------------- keystroke
    async def _on_key(self, event: events.Key) -> None:
        """Reset history recall when the user starts editing again.

        Once the user types (or hits Backspace, etc.) the ``_history_pos``
        stops tracking a recalled entry — subsequent ``↑`` restarts from the
        current value as the draft.
        """
        if event.key not in ("up", "down", "tab", "enter", "escape"):
            self._history_pos = -1
        await super()._on_key(event)
