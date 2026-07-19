"""Tests for :class:`siphon.engine.cancellation.CancellationToken`."""

from __future__ import annotations

import threading

import pytest

from siphon.engine.cancellation import CancellationToken, DownloadCancelled


class TestBasics:
    def test_starts_uncancelled(self) -> None:
        token = CancellationToken()
        assert token.cancelled is False

    def test_cancel_latches(self) -> None:
        token = CancellationToken()
        token.cancel()
        assert token.cancelled is True
        token.cancel()  # idempotent
        assert token.cancelled is True

    def test_raise_if_cancelled(self) -> None:
        token = CancellationToken()
        token.raise_if_cancelled()  # no-op when not cancelled
        token.cancel()
        with pytest.raises(DownloadCancelled):
            token.raise_if_cancelled()


class TestThreadSafety:
    def test_cancel_from_another_thread(self) -> None:
        token = CancellationToken()

        def canceller() -> None:
            token.cancel()

        t = threading.Thread(target=canceller)
        t.start()
        t.join(timeout=1.0)
        assert token.cancelled is True

    def test_wait_returns_on_cancel(self) -> None:
        token = CancellationToken()

        def canceller() -> None:
            token.cancel()

        threading.Timer(0.05, canceller).start()
        assert token.wait(timeout=1.0) is True
