"""Tests for :mod:`siphon.engine.downloader` hook state machine.

These do NOT call yt-dlp — we exercise the private ``_HookState`` directly
with synthetic hook payloads that mirror what yt-dlp actually emits.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from siphon.engine.cancellation import CancellationToken, DownloadCancelled
from siphon.engine.downloader import _cleanup_partials, _HookState
from siphon.models.progress import DownloadProgress


class TestProgressHook:
    def test_emits_progress_on_downloading_tick(self) -> None:
        received: list[DownloadProgress] = []
        state = _HookState(on_progress=received.append, on_processing=None, token=None)
        state.hook_progress(
            {
                "status": "downloading",
                "downloaded_bytes": 100,
                "total_bytes": 1000,
                "speed": 50.0,
                "eta": 20,
                "info_dict": {},
            }
        )
        assert received == [
            DownloadProgress(
                downloaded_bytes=100, total_bytes=1000, speed=50.0, eta=20, part=1, total_parts=1
            )
        ]

    def test_detects_total_parts_from_requested_formats(self) -> None:
        received: list[DownloadProgress] = []
        state = _HookState(on_progress=received.append, on_processing=None, token=None)
        state.hook_progress(
            {
                "status": "downloading",
                "downloaded_bytes": 100,
                "total_bytes": 1000,
                "info_dict": {"requested_formats": [{"format_id": "137"}, {"format_id": "140"}]},
            }
        )
        assert received[-1].total_parts == 2

    def test_increments_part_when_downloaded_drops(self) -> None:
        received: list[DownloadProgress] = []
        state = _HookState(on_progress=received.append, on_processing=None, token=None)
        # First file, 900 of 1000 bytes.
        state.hook_progress(
            {
                "status": "downloading",
                "downloaded_bytes": 900,
                "total_bytes": 1000,
                "info_dict": {"requested_formats": [{"format_id": "137"}, {"format_id": "140"}]},
            }
        )
        assert received[-1].part == 1
        # yt-dlp moves to the second file — counter resets.
        state.hook_progress(
            {
                "status": "downloading",
                "downloaded_bytes": 100,
                "total_bytes": 500,
                "info_dict": {"requested_formats": [{"format_id": "137"}, {"format_id": "140"}]},
            }
        )
        assert received[-1].part == 2

    def test_finished_records_destination(self) -> None:
        state = _HookState(on_progress=None, on_processing=None, token=None)
        state.hook_progress({"status": "finished", "filename": "/tmp/out.mp4", "info_dict": {}})
        assert state.destinations == ["/tmp/out.mp4"]
        assert state.final_filepath == "/tmp/out.mp4"

    def test_non_numeric_values_become_none(self) -> None:
        received: list[DownloadProgress] = []
        state = _HookState(on_progress=received.append, on_processing=None, token=None)
        state.hook_progress(
            {
                "status": "downloading",
                "downloaded_bytes": "NA",
                "total_bytes": "None",
                "speed": None,
                "eta": None,
                "info_dict": {},
            }
        )
        p = received[-1]
        assert p.downloaded_bytes is None
        assert p.total_bytes is None
        assert p.speed is None
        assert p.eta is None


class TestCancellation:
    def test_hook_raises_on_cancelled_token(self) -> None:
        token = CancellationToken()
        token.cancel()
        state = _HookState(on_progress=None, on_processing=None, token=token)
        with pytest.raises(DownloadCancelled):
            state.hook_progress({"status": "downloading", "info_dict": {}})

    def test_processing_hook_raises_on_cancelled_token(self) -> None:
        token = CancellationToken()
        token.cancel()
        state = _HookState(on_progress=None, on_processing=None, token=token)
        with pytest.raises(DownloadCancelled):
            state.hook_processing({"status": "started", "info_dict": {}})


class TestProcessingHook:
    def test_processing_status_fires_callback(self) -> None:
        calls: list[str] = []
        state = _HookState(on_progress=None, on_processing=lambda: calls.append("p"), token=None)
        state.hook_processing({"status": "processing", "info_dict": {}})
        assert calls == ["p"]

    def test_finished_captures_final_filepath(self) -> None:
        state = _HookState(on_progress=None, on_processing=None, token=None)
        state.hook_processing({"status": "finished", "info_dict": {"filepath": "/tmp/final.mp4"}})
        assert state.final_filepath == "/tmp/final.mp4"


class TestCleanupPartials:
    def test_removes_destination_and_siblings(self, tmp_path: Path) -> None:
        dest = tmp_path / "video.mp4"
        part = tmp_path / "video.mp4.part"
        ytdl = tmp_path / "video.mp4.ytdl"
        for p in (dest, part, ytdl):
            p.write_text("stub")

        _cleanup_partials([str(dest)])

        assert not dest.exists()
        assert not part.exists()
        assert not ytdl.exists()

    def test_missing_files_are_silently_ignored(self, tmp_path: Path) -> None:
        # Should not raise even if none of the paths exist.
        _cleanup_partials([str(tmp_path / "does-not-exist.mp4")])
