"""FramedInput — a bordered text field with a forged "siphon" button (yoinks F23).

The visual composition:

.. code-block:: text

    ╭─ Paste a link ─────╮ ▄▄▄▄▄▄▄▄▄▄
    │ https://youtu.be… │   siphon
    ╰────────────────────╯ ▀▀▀▀▀▀▀▀▀▀

The frame uses Textual's native ``border: round`` with a ``border_title``
(reproducing yoinks' hand-drawn title-on-border trick). The forged button is
a three-row :class:`~textual.widgets.Static` with half-block top / bottom
rows so it visually connects with the horizontal border of the frame.

Two visual variants (yoinks F23):

**Bright** (default). Top / bottom rows are bold ``▄`` / ``▀`` in the
primary colour; middle row is a *reversed* label — background painted
primary, foreground the panel's background. This mirrors yoinks'
``inverseButton=True`` mode and reads as a solid solid button on every
terminal that supports SGR reverse.

**Dim** (probing indicator). Every row is dim primary; the middle row is
NOT reversed, only bold on the panel background. Yoinks documented why:
some terminals apply ``dim`` to the SGR-reversed foreground and NOT to
the background, so the button splits into gray/white/gray bands. Dropping
the reverse in dim mode keeps the button as a coherent ghost outline.
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from siphon.ui.messages import SubmitRequested
from siphon.ui.widgets.text_input import SiphonTextInput

# Padding cells added inside the forged button to give the label breathing room.
_BUTTON_INNER_PADDING = 2


class ForgedButton(Static):
    """The three-row half-block button that sits flush against :class:`FramedInput`."""

    DEFAULT_CSS = """
    ForgedButton {
        width: auto;
        height: 3;
        color: $primary;
        padding: 0;
        margin: 0;
        content-align: left top;
    }
    """

    dim = reactive(False)
    """When True, render as a ghost outline (probing state)."""

    def __init__(self, label: str, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._label = label
        self._width = len(label) + _BUTTON_INNER_PADDING * 2

    def render(self) -> Text:
        """Compose the three-row Rich Text for the button.

        The dim variant deliberately drops the ``reverse`` from the middle
        row — see the module docstring for the terminal-quirk background.
        """
        text = Text(no_wrap=True, overflow="crop")
        label = f"{' ' * _BUTTON_INNER_PADDING}{self._label}{' ' * _BUTTON_INNER_PADDING}"

        if self.dim:
            # Ghost outline: every row bold + dim primary. No reverse.
            row_style = "bold dim"
            text.append("▄" * self._width, style=row_style)
            text.append("\n")
            text.append(label, style=row_style)
            text.append("\n")
            text.append("▀" * self._width, style=row_style)
        else:
            # Bright: top/bottom rails bold primary; middle reversed to
            # paint a solid slab. Reverse + bold reads cleanly on every
            # terminal we've seen (unlike reverse + dim).
            text.append("▄" * self._width, style="bold")
            text.append("\n")
            text.append(label, style="reverse bold")
            text.append("\n")
            text.append("▀" * self._width, style="bold")
        return text

    def watch_dim(self, _old: bool, _new: bool) -> None:
        """Repaint when the dim state flips."""
        self.refresh()

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
        margin-left: 0;
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
