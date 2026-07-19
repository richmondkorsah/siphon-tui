"""Regression tests for :class:`siphon.ui.widgets.framed_input.ForgedButton`.

These focus on the two visual variants (bright / dim) and the terminal-
quirk the ``dim`` variant works around: `reverse + dim` interacting badly
on some emulators. The dim variant deliberately drops the ``reverse`` so
the button reads as a coherent ghost outline rather than banding.
"""

from __future__ import annotations

import pytest
from rich.text import Text

from siphon.ui.widgets.framed_input import ForgedButton


class TestBrightVariant:
    def test_three_rows(self) -> None:
        button = ForgedButton("siphon")
        text = button.render()
        # Rich Text stores line breaks as literal "\n" characters.
        assert str(text).count("\n") == 2

    def test_middle_row_uses_reverse(self) -> None:
        button = ForgedButton("siphon")
        text: Text = button.render()
        # Find any span with the "reverse bold" style — Rich stores styles per span.
        styles = [span.style for span in text.spans]
        assert any("reverse" in str(style) for style in styles)

    def test_top_and_bottom_rails_are_halfblocks(self) -> None:
        button = ForgedButton("siphon")
        rendered = str(button.render())
        rows = rendered.split("\n")
        assert set(rows[0]) == {"▄"}
        assert set(rows[2]) == {"▀"}

    def test_middle_row_contains_label(self) -> None:
        button = ForgedButton("siphon")
        rows = str(button.render()).split("\n")
        assert "siphon" in rows[1]


class TestDimVariant:
    def test_no_reverse_in_dim_state(self) -> None:
        """The dim variant explicitly avoids ``reverse`` to dodge terminal band-splitting."""
        button = ForgedButton("siphon")
        button.dim = True
        text: Text = button.render()
        styles = [str(span.style) for span in text.spans]
        assert not any(
            "reverse" in style for style in styles
        ), "dim button re-introduced 'reverse' — terminals will band-split it"

    def test_all_rows_carry_dim(self) -> None:
        button = ForgedButton("siphon")
        button.dim = True
        text: Text = button.render()
        styles = [str(span.style) for span in text.spans]
        # Every stylised span should include the dim modifier.
        assert all("dim" in style for style in styles)

    def test_click_ignored_in_dim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        button = ForgedButton("siphon")
        button.dim = True
        fired: list[object] = []
        monkeypatch.setattr(button, "post_message", fired.append)
        button.on_click()
        assert fired == []


class TestWidthMath:
    @pytest.mark.parametrize("label", ["siphon", "yoink", "x"])
    def test_button_width_scales_with_label(self, label: str) -> None:
        button = ForgedButton(label)
        rendered = str(button.render()).split("\n")
        # +4 for the 2-cell padding on each side.
        assert len(rendered[0]) == len(label) + 4
