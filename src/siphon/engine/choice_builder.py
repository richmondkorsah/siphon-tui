"""Build the picker choices from a yt-dlp ``VideoInfo`` dict (yoinks F11).

The input is the ``info`` dict returned by ``YoutubeDL.extract_info``. The
output is a list of :class:`~siphon.models.choice.DownloadChoice` in the
order they should appear in the picker: highest video quality first, then
the ``audio only · mp3`` row.

Selection rules (parity with yoinks ``buildChoices``):

* Bucket audio-only formats (``acodec`` set, ``vcodec`` empty/``none``) and
  pick the one with the maximum ``abr`` (fallback to ``tbr``). This is used
  both for the audio choice and for the mux-size estimate.
* Bucket video formats that have a ``height`` set. De-duplicate heights
  descending, keeping the top :data:`~siphon.config.constants.MAX_VIDEO_CHOICES`.
* For each retained height, pick the "best" format by
  :func:`_score_video` — TBR plus 10 000 for mp4 and 5 000 for AVC (H.264),
  biasing towards broadly-compatible files.
* When the chosen video is video-only, add the best audio's size to the
  size hint (they'll be muxed).
* Emit ``format`` selectors:

  * Video @ height H:
    ``bv*[height=H]+ba/b[height=H]/bv*[height<=H]+ba/b`` with
    ``merge_output_format=mp4``.
  * Audio-only: ``ba/b`` with an ``FFmpegExtractAudio`` postprocessor
    (mp3, ``preferredquality='0'`` for max VBR).

* If no video formats are found, emit a single ``best available · mp4``
  fallback and still append the audio row.
"""

from __future__ import annotations

import math
from typing import Any

from siphon.config.constants import MAX_VIDEO_CHOICES
from siphon.models.choice import DownloadChoice
from siphon.utils.format import format_bytes


def build_choices(info: dict[str, Any]) -> list[DownloadChoice]:
    """Return the ordered picker choices for a yt-dlp info dict.

    Never returns an empty list — even for pathological info dicts we always
    append at least the audio-only row (yt-dlp handles the actual selection).
    """
    formats: list[dict[str, Any]] = list(info.get("formats") or [])

    audio_pool = [fmt for fmt in formats if _is_audio_only(fmt)]
    best_audio = max(audio_pool, key=_audio_score, default=None)
    best_audio_size = _format_size(best_audio) if best_audio else None

    video_pool = [fmt for fmt in formats if _has_video_height(fmt)]

    choices: list[DownloadChoice] = []
    if video_pool:
        # Group video formats by their integer height.
        by_height: dict[int, list[dict[str, Any]]] = {}
        for fmt in video_pool:
            by_height.setdefault(int(fmt["height"]), []).append(fmt)

        heights = sorted(by_height.keys(), reverse=True)[:MAX_VIDEO_CHOICES]
        for height in heights:
            best = max(by_height[height], key=_score_video)
            size = _combined_size(best, best_audio_size)
            label = _video_label(height, size)
            choices.append(
                DownloadChoice(
                    kind="video",
                    label=label,
                    ytdlp_opts=_video_ytdlp_opts(height),
                    size_hint_bytes=size,
                    height=height,
                )
            )
    else:
        # Fallback: yt-dlp picks whatever it can.
        choices.append(
            DownloadChoice(
                kind="video",
                label="best available · mp4",
                ytdlp_opts=_video_fallback_opts(),
                size_hint_bytes=None,
                height=None,
            )
        )

    # Always append the audio-only choice.
    audio_size_str = format_bytes(best_audio_size)
    audio_suffix = f" · ~{audio_size_str}" if audio_size_str else ""
    choices.append(
        DownloadChoice(
            kind="audio",
            label=f"audio only · mp3{audio_suffix}",
            ytdlp_opts=_audio_ytdlp_opts(),
            size_hint_bytes=best_audio_size,
            height=None,
        )
    )
    return choices


# ---------------------------------------------------------------------------
# Bucket predicates
# ---------------------------------------------------------------------------
def _is_audio_only(fmt: dict[str, Any]) -> bool:
    """True iff ``fmt`` has audio codec but no video codec."""
    acodec = fmt.get("acodec")
    vcodec = fmt.get("vcodec")
    return bool(acodec) and acodec != "none" and (not vcodec or vcodec == "none")


def _has_video_height(fmt: dict[str, Any]) -> bool:
    """True iff ``fmt`` has a positive numeric height."""
    height = fmt.get("height")
    return isinstance(height, (int, float)) and height > 0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def _score_video(fmt: dict[str, Any]) -> float:
    """Higher = more preferred. mp4 + AVC bonuses to bias towards broad compat."""
    score = _as_float(fmt.get("tbr")) or 0.0
    if fmt.get("ext") == "mp4":
        score += 10_000.0
    vcodec = str(fmt.get("vcodec") or "")
    if vcodec.startswith("avc"):
        score += 5_000.0
    return score


def _audio_score(fmt: dict[str, Any]) -> float:
    """Prefer the highest audio bitrate; fall back to total bitrate."""
    abr = _as_float(fmt.get("abr"))
    if abr is not None:
        return abr
    return _as_float(fmt.get("tbr")) or 0.0


# ---------------------------------------------------------------------------
# yt-dlp option payloads
# ---------------------------------------------------------------------------
def _video_ytdlp_opts(height: int) -> dict[str, Any]:
    """Options for a specific height (with graceful fallback selectors)."""
    return {
        "format": f"bv*[height={height}]+ba/b[height={height}]/bv*[height<={height}]+ba/b",
        "merge_output_format": "mp4",
    }


def _video_fallback_opts() -> dict[str, Any]:
    return {"format": "bv*+ba/b", "merge_output_format": "mp4"}


def _audio_ytdlp_opts() -> dict[str, Any]:
    """Options for the audio-only + mp3 extraction row."""
    return {
        "format": "ba/b",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "0",
            }
        ],
    }


# ---------------------------------------------------------------------------
# Label helpers
# ---------------------------------------------------------------------------
def _video_label(height: int, size: int | None) -> str:
    """Format a video row label: ``1080p · mp4 · ~130 MB``."""
    parts = [f"{height}p", "mp4"]
    size_str = format_bytes(size)
    if size_str:
        parts.append(f"~{size_str}")
    return " · ".join(parts)


def _combined_size(video_fmt: dict[str, Any], audio_size: int | None) -> int | None:
    """Add the audio size to a video-only format's size estimate (they'll be muxed)."""
    video_size = _format_size(video_fmt)
    if video_size is None:
        return None
    acodec = video_fmt.get("acodec")
    if not acodec or acodec == "none":
        # Video-only stream — add audio size for the mux estimate.
        return video_size + (audio_size or 0)
    return video_size


def _format_size(fmt: dict[str, Any]) -> int | None:
    """Return ``filesize`` when present, else ``filesize_approx``."""
    for key in ("filesize", "filesize_approx"):
        value = _as_float(fmt.get(key))
        if value is not None and value > 0:
            return int(value)
    return None


def _as_float(value: Any) -> float | None:
    """Coerce yt-dlp fields that may be ``None`` / ``"NA"`` / ``"None"`` to float or None."""
    if value is None:
        return None
    if isinstance(value, str):
        if value in ("NA", "None", ""):
            return None
        try:
            value = float(value)
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        # Reject NaN — ``math.isnan`` is safer than ``x != x`` (ruff PLR0124).
        if isinstance(value, float) and math.isnan(value):
            return None
        return float(value)
    return None
