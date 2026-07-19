"""Tests for :func:`siphon.engine.choice_builder.build_choices`.

Feed synthetic ``VideoInfo`` fixtures and assert:
* Video heights are deduplicated and capped at :data:`MAX_VIDEO_CHOICES`.
* mp4 + AVC formats are preferred over webm/vp9 at the same height.
* Video-only formats have the best audio size added for the mux estimate.
* The audio row is always present, even when no video formats exist.
* yt-dlp option payloads carry the expected format strings.
"""

from __future__ import annotations

from typing import Any

import pytest

from siphon.config.constants import MAX_VIDEO_CHOICES
from siphon.engine.choice_builder import build_choices


def _audio(fmt_id: str, abr: float, size: int) -> dict[str, Any]:
    return {
        "format_id": fmt_id,
        "acodec": "opus" if fmt_id == "251" else "mp4a.40.2",
        "vcodec": "none",
        "abr": abr,
        "filesize": size,
    }


def _video(
    fmt_id: str,
    height: int,
    ext: str,
    vcodec: str,
    tbr: float,
    size: int,
    acodec: str = "none",
) -> dict[str, Any]:
    return {
        "format_id": fmt_id,
        "height": height,
        "ext": ext,
        "vcodec": vcodec,
        "acodec": acodec,
        "tbr": tbr,
        "filesize": size,
    }


@pytest.fixture
def yt_info() -> dict[str, Any]:
    """A realistic multi-format YouTube info dict."""
    return {
        "title": "sample",
        "formats": [
            _audio("140", abr=129, size=3_400_000),
            _audio("251", abr=141, size=3_650_000),
            _video("137", 1080, "mp4", "avc1.640028", 4500, 120_000_000),
            _video("248", 1080, "webm", "vp9", 3200, 90_000_000),
            _video("136", 720, "mp4", "avc1.4d401f", 2500, 70_000_000),
            _video("247", 720, "webm", "vp9", 1800, 55_000_000),
            _video("135", 480, "mp4", "avc1.4d401e", 1200, 30_000_000),
            _video("134", 360, "mp4", "avc1.4d401e", 800, 15_000_000),
            _video("133", 240, "mp4", "avc1.4d400c", 400, 8_000_000),
            _video("160", 144, "mp4", "avc1.4d400b", 200, 4_000_000),
        ],
    }


class TestOrderingAndCount:
    def test_heights_sorted_descending(self, yt_info: dict[str, Any]) -> None:
        choices = build_choices(yt_info)
        heights = [c.height for c in choices if c.kind == "video"]
        assert heights == sorted(heights, reverse=True)

    def test_audio_row_is_last(self, yt_info: dict[str, Any]) -> None:
        choices = build_choices(yt_info)
        assert choices[-1].kind == "audio"

    def test_never_returns_empty(self) -> None:
        assert build_choices({}) != []

    def test_caps_at_max_video_choices(self) -> None:
        many_heights = {
            "formats": [_video(f"v{i}", 100 + i, "mp4", "avc1", 500, 1_000_000) for i in range(20)]
        }
        choices = build_choices(many_heights)
        video_choices = [c for c in choices if c.kind == "video"]
        assert len(video_choices) == MAX_VIDEO_CHOICES


class TestPreferenceBias:
    def test_mp4_avc_beats_webm_vp9_at_same_height(self, yt_info: dict[str, Any]) -> None:
        # For 1080p, the mp4+avc format (137) should win over webm/vp9 (248).
        # The chosen size hint corresponds to 137 (120MB) + best audio (3.65MB).
        choices = build_choices(yt_info)
        top = choices[0]
        assert top.height == 1080
        assert top.size_hint_bytes is not None
        # 120 MB video + best audio (3.65 MB) = ~123.65 MB
        assert 120_000_000 <= top.size_hint_bytes <= 130_000_000

    def test_video_only_adds_audio_size_for_mux(self, yt_info: dict[str, Any]) -> None:
        choices = build_choices(yt_info)
        # 480p is video-only 30MB + best audio 3.65MB
        for c in choices:
            if c.height == 480:
                assert c.size_hint_bytes is not None
                assert c.size_hint_bytes > 30_000_000
                break
        else:
            pytest.fail("no 480p choice")


class TestAudioAlways:
    def test_audio_row_present_even_with_no_video_formats(self) -> None:
        info = {"formats": [_audio("140", abr=129, size=3_400_000)]}
        choices = build_choices(info)
        assert any(c.kind == "audio" for c in choices)

    def test_audio_size_reflects_best_audio(self, yt_info: dict[str, Any]) -> None:
        choices = build_choices(yt_info)
        audio = next(c for c in choices if c.kind == "audio")
        assert audio.size_hint_bytes == 3_650_000  # best is opus 141kbps

    def test_audio_uses_ffmpeg_extract_audio(self, yt_info: dict[str, Any]) -> None:
        audio = next(c for c in build_choices(yt_info) if c.kind == "audio")
        pps = audio.ytdlp_opts.get("postprocessors")
        assert isinstance(pps, list) and pps[0]["key"] == "FFmpegExtractAudio"
        assert pps[0]["preferredcodec"] == "mp3"


class TestFallbacks:
    def test_no_formats_yields_best_available_fallback(self) -> None:
        choices = build_choices({"title": "x"})
        video = choices[0]
        assert video.kind == "video"
        assert "best available" in video.label
        assert video.ytdlp_opts["format"] == "bv*+ba/b"

    def test_video_label_format(self, yt_info: dict[str, Any]) -> None:
        choices = build_choices(yt_info)
        assert choices[0].label.startswith("1080p · mp4")

    def test_video_format_string_encodes_height(self, yt_info: dict[str, Any]) -> None:
        choices = build_choices(yt_info)
        top = choices[0]
        assert "[height=1080]" in top.ytdlp_opts["format"]
        assert top.ytdlp_opts["merge_output_format"] == "mp4"
