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
    ``merge_output_format=mp4`` and an ``FFmpegMetadata`` postprocessor
    (``add_chapters=True``) to embed source chapter markers.
  * Audio-only: ``ba/b`` with an ``FFmpegExtractAudio`` postprocessor
    (mp3, ``preferredquality='0'`` for max VBR).

* If no video formats are found, emit a single ``best available · mp4``
  fallback and still append the audio row.
"""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

from siphon.config.constants import MAX_VIDEO_CHOICES
from siphon.models.choice import DownloadChoice, SubtitleChoice
from siphon.utils.format import format_bytes

# Common subtitle language codes → human-readable names. Only used when the
# extractor didn't ship a ``name`` for the track; falls back to the code itself.
_LANG_NAMES: dict[str, str] = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "ru": "Russian", "ja": "Japanese",
    "ko": "Korean", "zh": "Chinese", "ar": "Arabic", "hi": "Hindi",
    "nl": "Dutch", "sv": "Swedish", "no": "Norwegian", "da": "Danish",
    "fi": "Finnish", "pl": "Polish", "tr": "Turkish", "th": "Thai",
    "vi": "Vietnamese", "id": "Indonesian", "he": "Hebrew", "cs": "Czech",
    "el": "Greek", "hu": "Hungarian", "ro": "Romanian", "uk": "Ukrainian",
    "bn": "Bengali", "ur": "Urdu", "fa": "Persian", "ms": "Malay",
    "sw": "Swahili", "ta": "Tamil", "te": "Telugu", "mr": "Marathi",
}  # fmt: skip


# Popularity ordering for the subtitle picker — sorted roughly by combined
# native + second-language speaker counts / global web-content share. Codes
# not in this list fall to alphabetical order after all popular ones. Regional
# variants (``en-US``, ``pt-BR``) inherit the rank of their base code and are
# then broken ties alphabetically, keeping ``en`` above ``en-GB`` above ``en-US``.
_LANG_POPULARITY: tuple[str, ...] = (
    "en", "zh", "es", "hi", "ar", "pt", "bn", "ru", "ja", "de",
    "fr", "ko", "it", "tr", "ur", "id", "vi", "pl", "fa", "uk",
    "nl", "th", "ms", "ta", "te", "mr", "sw", "he", "el", "cs",
    "hu", "ro", "sv", "no", "da", "fi",
)  # fmt: skip


def _popularity_rank(code: str) -> int:
    """Rank ``code`` for the subtitle picker. Lower = more popular = shown first."""
    base = code.split("-", 1)[0].lower()
    try:
        return _LANG_POPULARITY.index(base)
    except ValueError:
        return len(_LANG_POPULARITY)


def _lang_sort_key(code: str) -> tuple[int, str]:
    """Sort key: popularity first, alphabetical within the same rank."""
    return (_popularity_rank(code), code)


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
        "postprocessors": [_embed_chapters_pp()],
    }


def _video_fallback_opts() -> dict[str, Any]:
    return {
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "postprocessors": [_embed_chapters_pp()],
    }


def _embed_chapters_pp() -> dict[str, Any]:
    """Postprocessor entry matching yt-dlp's ``--embed-chapters`` CLI flag.

    yt-dlp only writes a chapters atom/element when the extractor actually
    found chapters — no-op otherwise, so it's safe to always include.
    """
    return {"key": "FFmpegMetadata", "add_chapters": True}


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


def build_subtitle_choices(info: dict[str, Any]) -> list[SubtitleChoice]:
    """Return the subtitle-picker rows for a yt-dlp info dict.

    Always starts with a ``no subtitles`` row (the default). Manual subtitle
    languages come next, ordered by :func:`_lang_sort_key` — popular languages
    (English, Chinese, Spanish, …) first, unknown codes alphabetical after —
    then auto-generated captions for any language a manual track didn't
    already cover, in the same order, each labelled ``… · auto``.
    """
    choices: list[SubtitleChoice] = [SubtitleChoice(kind="none", label="no subtitles")]

    manual = info.get("subtitles") or {}
    auto = info.get("automatic_captions") or {}

    for code in sorted(manual.keys(), key=_lang_sort_key):
        formats = manual[code] if isinstance(manual[code], list) else []
        choices.append(
            SubtitleChoice(
                kind="lang",
                label=_lang_label(code, formats),
                lang=code,
                auto=False,
            )
        )

    for code in sorted(auto.keys(), key=_lang_sort_key):
        if code in manual:
            continue  # a manual track already covers this language
        formats = auto[code] if isinstance(auto[code], list) else []
        choices.append(
            SubtitleChoice(
                kind="lang",
                label=f"{_lang_label(code, formats)} · auto",
                lang=code,
                auto=True,
            )
        )

    return choices


def apply_subtitle_opts(choice: DownloadChoice, sub: SubtitleChoice) -> DownloadChoice:
    """Return a copy of ``choice`` with subtitle-embedding opts merged in.

    ``kind="none"`` returns the choice unchanged. For a language pick, sets
    ``writesubtitles``/``writeautomaticsub`` + ``subtitleslangs``, and appends
    an ``FFmpegEmbedSubtitle`` postprocessor so the track ends up muxed into
    the final mp4.
    """
    if sub.kind == "none" or sub.lang is None:
        return choice

    opts = dict(choice.ytdlp_opts)
    opts["writesubtitles"] = not sub.auto
    opts["writeautomaticsub"] = sub.auto
    opts["subtitleslangs"] = [sub.lang]

    postprocessors = list(opts.get("postprocessors", []))
    postprocessors.append({"key": "FFmpegEmbedSubtitle", "already_have_subtitle": False})
    opts["postprocessors"] = postprocessors

    return replace(choice, ytdlp_opts=opts)


def _lang_label(code: str, formats: list[dict[str, Any]]) -> str:
    """Human label for a subtitle language: ``English (en)``.

    Prefers the ``name`` the extractor advertises on any format; otherwise
    looks the base code (before any ``-region`` suffix) up in the local
    common-languages table; falls back to the raw code.
    """
    for fmt in formats:
        name = fmt.get("name")
        if isinstance(name, str) and name.strip():
            return f"{name.strip()} ({code})"
    base = code.split("-", 1)[0].lower()
    name = _LANG_NAMES.get(base, code)
    return f"{name} ({code})" if name != code else code


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
