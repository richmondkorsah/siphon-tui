"""Regression tests for :class:`siphon.ui.widgets.framed_input.ForgedButton`.

The button used to be hand-drawn from three rows of half-block characters
to simulate a filled slab — terminal-fragile (some emulators apply ``dim``
to a reversed foreground and not the background, splitting the button into
visibly disconnected bars). It's now a plain ``border: round`` box, matching
the input frame it sits next to and the app's other button (``#done-button``).
These tests cover the dim/bright CSS-class toggle and click behaviour.
"""

from __future__ import annotations

import pytest

from siphon.ui.widgets.framed_input import ForgedButton


class TestBrightVariant:
    def test_renders_label(self) -> None:
        button = ForgedButton("siphon")
        assert str(button.render()) == "siphon"

    def test_not_dim_by_default(self) -> None:
        button = ForgedButton("siphon")
        assert button.dim is False
        assert not button.has_class("-dim")


class TestDimVariant:
    def test_dim_adds_ghost_class(self) -> None:
        button = ForgedButton("siphon")
        button.dim = True
        assert button.has_class("-dim")

    def test_undim_removes_ghost_class(self) -> None:
        button = ForgedButton("siphon")
        button.dim = True
        button.dim = False
        assert not button.has_class("-dim")

    def test_click_ignored_in_dim(self, monkeypatch: pytest.MonkeyPatch) -> None:
        button = ForgedButton("siphon")
        button.dim = True
        fired: list[object] = []
        monkeypatch.setattr(button, "post_message", fired.append)
        button.on_click()
        assert fired == []

    def test_click_fires_when_bright(self, monkeypatch: pytest.MonkeyPatch) -> None:
        button = ForgedButton("siphon")
        fired: list[object] = []
        monkeypatch.setattr(button, "post_message", fired.append)
        button.on_click()
        assert len(fired) == 1


class TestWidthMath:
    @pytest.mark.parametrize("label", ["siphon", "yoink", "x"])
    def test_label_preserved(self, label: str) -> None:
        button = ForgedButton(label)
        assert str(button.render()) == label
