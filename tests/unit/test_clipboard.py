"""Tests for :mod:`siphon.services.clipboard` — rules + failure-swallow."""

from __future__ import annotations

import asyncio
import time

import pyperclip
import pytest

from siphon.services import clipboard as clip_mod


class TestReadClipboardRules:
    async def test_accepts_valid_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pyperclip, "paste", lambda: "https://youtu.be/xyz")
        assert await clip_mod.read_clipboard() == "https://youtu.be/xyz"

    async def test_rejects_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pyperclip, "paste", lambda: "")
        assert await clip_mod.read_clipboard() == ""

    async def test_rejects_whitespace_containing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Multi-line content (yoinks explicitly skips this — URL parsers
        # silently strip newlines and users end up on the wrong page).
        monkeypatch.setattr(pyperclip, "paste", lambda: "https://a\nhttps://b")
        assert await clip_mod.read_clipboard() == ""

    async def test_rejects_url_with_spaces(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pyperclip, "paste", lambda: "https://a b.example")
        assert await clip_mod.read_clipboard() == ""

    async def test_rejects_non_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(pyperclip, "paste", lambda: "not-a-url")
        assert await clip_mod.read_clipboard() == ""


class TestFailureSwallow:
    async def test_pyperclip_exception_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom() -> str:
            raise pyperclip.PyperclipException("no backend")

        monkeypatch.setattr(pyperclip, "paste", boom)
        assert await clip_mod.read_clipboard() == ""

    async def test_timeout_returns_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def sleepy() -> str:
            time.sleep(2.0)
            return "https://never.gonna.be.seen"

        monkeypatch.setattr(pyperclip, "paste", sleepy)
        result = await asyncio.wait_for(clip_mod.read_clipboard(timeout_s=0.05), timeout=1.0)
        assert result == ""
