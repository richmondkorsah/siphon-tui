from __future__ import annotations

from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Markdown

HELP_MD = """
## Global
| Key | Action |
| --- | --- |
| **?** | Show this help screen |
| **ctrl+c** | Quit application |
| **ctrl+t** | Cycle theme (auto/light/dark) |
| **ctrl+p** | Toggle command palette |
| **ctrl+s** | Open settings |

## Input Phase
| Key | Action |
| --- | --- |
| **enter** | Submit URL |
| **ctrl+r** | Search history |
| **up/down** | Navigate recent history inline |

## Navigation
| Key | Action |
| --- | --- |
| **escape** | Cancel / Back / Close modal |
| **enter** | Confirm / Select |
| **tab** | Next focus |
"""


class HelpModal(ModalScreen[None]):
    """A pop-over showing all keyboard shortcuts."""

    DEFAULT_CSS = """
    HelpModal {
        align: center middle;
    }
    HelpModal > VerticalScroll {
        width: 70%;
        max-width: 70;
        height: 80%;
        max-height: 28;
        border: round $primary;
        border-title-color: $primary;
        border-title-align: left;
        padding: 0 1;
        background: $background;
    }
    HelpModal Markdown {
        margin: 1 2;
    }
    HelpModal Center {
        margin-top: 1;
        margin-bottom: 1;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel", "Close", show=True),
        Binding("enter", "cancel", "Close", show=False),
        Binding("?", "cancel", "Close", show=False),
    ]

    def compose(self) -> ComposeResult:
        with VerticalScroll() as container:
            container.border_title = "keyboard shortcuts"
            yield Markdown(HELP_MD)
            with Center():
                yield Button("Close", variant="primary", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
