"""FramedInput — a bordered text field with a "siphon" submit button (yoinks F23).

The visual composition:

.. code-block:: text

    ╭─ Paste a link ─────╮ ╭────────╮
    │ https://youtu.be… │ │ siphon │
    ╰────────────────────╯ ╰────────╯

Both boxes use Textual's native ``border: round`` so they read as one
matched pair regardless of terminal/font — the button used to be hand-drawn
from half-block (``▄``/``▀``) rows to *simulate* a filled slab, but that
approach is terminal-fragile (some terminals apply ``dim`` to a reversed
foreground and not the background, splitting the middle row from its rails
into visibly disconnected bars). A plain matching border sidesteps the
whole class of bug.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from siphon.ui.messages import SubmitRequested
from siphon.ui.widgets.text_input import SiphonTextInput


class ForgedButton(Static):
    """The bordered submit button that sits flush against :class:`FramedInput`."""

    DEFAULT_CSS = """
    ForgedButton {
        width: auto;
        height: 3;
        border: round $primary;
        padding: 0 2;
        color: $primary;
        text-style: bold;
        content-align: center middle;
    }
    ForgedButton.-dim {
        color: $text-muted;
        text-style: dim bold;
    }
    """

    dim = reactive(False)
    """When True, render as a ghost outline (probing state)."""

    def __init__(self, label: str, *, id: str | None = None) -> None:
        super().__init__(label, id=id)

    def watch_dim(self, _old: bool, new: bool) -> None:
        """Toggle the ghost-outline style when the dim state flips."""
        self.set_class(new, "-dim")

    def on_click(self) -> None:
        """Clicking the button submits the current input value."""
        if self.dim:
            return  # ghost state — not clickable
        self.post_message(_ButtonClicked())


class _ButtonClicked(SubmitRequested):
    """Internal signal from :class:`ForgedButton` — the parent :class:`FramedInput` handles it."""

    def __init__(self) -> None:
        super().__init__(url="")


class FramedInput(Widget):
    """Composite widget: bordered text field on the left, forged button on the right."""

    DEFAULT_CSS = """
    FramedInput {
        height: 3;
        width: 100%;
        max-width: 96;
        layout: horizontal;
    }
    FramedInput > #frame {
        border: round $primary;
        border-title-color: $primary;
        border-title-align: left;
        padding: 0 1;
        width: 1fr;
        min-width: 30;
        height: 3;
    }
    FramedInput > #frame > SiphonTextInput {
        border: none;
        padding: 0;
        background: transparent;
        color: $foreground;
        height: 1;
    }
    FramedInput > ForgedButton {
        margin-left: 1;
    }
    """

    def __init__(
        self,
        *,
        title: str = "Paste a link",
        button_label: str = "siphon",
        placeholder: str = "https://youtube.com/watch?v=…",
        history: list[str] | None = None,
        id: str | None = None,
    ) -> None:
        super().__init__(id=id)
        self._title = title
        self._button_label = button_label
        self._placeholder = placeholder
        self._history = list(history) if history else []

    def compose(self) -> ComposeResult:
        """Compose the frame + input on the left, forged button on the right."""
        with Container(id="frame") as frame:
            frame.border_title = self._title
            yield SiphonTextInput(
                history=self._history,
                placeholder=self._placeholder,
                id="url-input",
            )
        yield ForgedButton(self._button_label, id="siphon-button")

    # --------------------------------------------- convenience for the screen
    @property
    def input(self) -> SiphonTextInput:
        """The inner :class:`SiphonTextInput`."""
        return self.query_one(SiphonTextInput)

    @property
    def button(self) -> ForgedButton:
        """The forged submit button."""
        return self.query_one(ForgedButton)

    def set_title(self, title: str) -> None:
        """Update the border title (e.g. from ``Paste a link`` to a platform label)."""
        self._title = title
        self.query_one("#frame", Container).border_title = title

    def set_dim(self, dim: bool) -> None:
        """Toggle the button's dim state (probing indicator)."""
        self.button.dim = dim

    def on_focus(self) -> None:
        """Delegate focus to the inner input so typing "just works"."""
        self.input.focus()

    # ------------------------------------------------ message re-broadcasting
    def on__button_clicked(self, event: _ButtonClicked) -> None:
        """Rewrite an internal button-click into a real :class:`SubmitRequested`."""
        event.stop()
        self.input.submit_now()
