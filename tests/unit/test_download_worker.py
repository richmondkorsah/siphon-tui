"""Tests for :mod:`siphon.workers.download_worker` — the stale-URL / rate-limit
retry wrapper around :func:`siphon.engine.downloader.download`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from siphon.engine.cancellation import CancellationToken
from siphon.engine.errors import CleanedYtdlpError
from siphon.models.choice import DownloadChoice
from siphon.ui.messages import DownloadFailed, DownloadRefreshing, DownloadSucceeded
from siphon.workers import download_worker
from siphon.workers.download_worker import _looks_rate_limited, _looks_stale, run_download


class _FakeApp:
    def call_from_thread(self, fn: Any, *args: Any, **kwargs: Any) -> None:
        fn(*args, **kwargs)


class _FakeScreen:
    def __init__(self) -> None:
        self.app = _FakeApp()
        self.posted: list[Any] = []

    def post_message(self, message: Any) -> None:
        self.posted.append(message)


def _choice() -> DownloadChoice:
    return DownloadChoice(kind="video", label="1080p · mp4", ytdlp_opts={}, height=1080)


class TestMarkerDetection:
    @pytest.mark.parametrize(
        "message",
        ["HTTP Error 403: Forbidden", "Signature expired", "the URL has expired"],
    )
    def test_looks_stale_matches(self, message: str) -> None:
        assert _looks_stale(message)

    def test_looks_stale_does_not_match_rate_limit(self) -> None:
        assert not _looks_stale("HTTP Error 429: Too Many Requests")

    @pytest.mark.parametrize(
        "message",
        ["HTTP Error 429: Too Many Requests", "Too many requests, try again later"],
    )
    def test_looks_rate_limited_matches(self, message: str) -> None:
        assert _looks_rate_limited(message)

    def test_looks_rate_limited_does_not_match_stale(self) -> None:
        assert not _looks_rate_limited("HTTP Error 403: Forbidden")


class TestRunDownloadRateLimitRetry:
    async def test_retries_once_after_backoff_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A 429 (e.g. a non-English subtitle track) is retried once, after a
        sleep — not immediately, since retrying instantly would just 429 again."""
        calls = {"n": 0}
        sleeps: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            sleeps.append(seconds)

        def fake_download(**kwargs: Any) -> Path:
            calls["n"] += 1
            if calls["n"] == 1:
                raise CleanedYtdlpError("HTTP Error 429: Too Many Requests")
            return Path("/tmp/video.mp4")

        monkeypatch.setattr(download_worker, "download", fake_download)
        monkeypatch.setattr(download_worker.asyncio, "sleep", fake_sleep)

        screen = _FakeScreen()
        await run_download(
            url="https://example.com/watch?v=abc",
            choice=_choice(),
            title="Example",
            output_dir=Path("/tmp"),
            ffmpeg_location=None,
            token=CancellationToken(),
            screen=screen,
        )

        assert calls["n"] == 2
        assert sleeps == [download_worker._RATE_LIMIT_BACKOFF_S]
        refreshing = [m for m in screen.posted if isinstance(m, DownloadRefreshing)]
        assert len(refreshing) == 1
        assert "rate limited" in refreshing[0].reason
        assert any(isinstance(m, DownloadSucceeded) for m in screen.posted)

    async def test_gives_up_after_one_retry(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A second consecutive 429 is a real, sustained rate limit — surface it."""
        calls = {"n": 0}

        async def fake_sleep(_seconds: float) -> None:
            return None

        def fake_download(**kwargs: Any) -> Path:
            calls["n"] += 1
            raise CleanedYtdlpError("HTTP Error 429: Too Many Requests")

        monkeypatch.setattr(download_worker, "download", fake_download)
        monkeypatch.setattr(download_worker.asyncio, "sleep", fake_sleep)

        screen = _FakeScreen()
        await run_download(
            url="https://example.com/watch?v=abc",
            choice=_choice(),
            title="Example",
            output_dir=Path("/tmp"),
            ffmpeg_location=None,
            token=CancellationToken(),
            screen=screen,
        )

        assert calls["n"] == 2  # one retry, then give up
        failed = [m for m in screen.posted if isinstance(m, DownloadFailed)]
        assert len(failed) == 1
