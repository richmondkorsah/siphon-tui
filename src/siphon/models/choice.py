"""DownloadChoice — one row in the picker.

A choice is the *user-visible* option ("1080p · mp4 · ~130 MB",
"audio only · mp3 · ~4 MB") plus the yt-dlp option overrides that will
realise it when the download engine actually runs.

Keeping the ``ytdlp_opts`` inside the choice means the picker screen never
has to know about format strings or postprocessors — it just picks a choice
and hands it to the download worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

ChoiceKind = Literal["video", "audio"]


@dataclass(frozen=True, slots=True)
class DownloadChoice:
    """One selectable download option in the picker (yoinks F11)."""

    kind: ChoiceKind
    """Whether the choice yields a video file or an audio-only extraction."""

    label: str
    """The human-readable summary shown in the ListView (without the ▶/♪ prefix)."""

    ytdlp_opts: dict[str, Any] = field(default_factory=dict)
    """Options merged into the ``YoutubeDL`` constructor when this choice is downloaded.

    Video choices set ``format`` and ``merge_output_format``. Audio choices set
    ``format`` plus ``postprocessors`` for FFmpegExtractAudio → mp3.
    """

    size_hint_bytes: int | None = None
    """Best-effort estimate used to render the ``~130 MB`` suffix in the label."""

    height: int | None = None
    """Video height in pixels — ``None`` for audio-only or fallback choices."""

    @property
    def prefix(self) -> str:
        """The single-char icon rendered before the label (``▶ `` or ``♪ ``)."""
        return "▶ " if self.kind == "video" else "♪ "

    @property
    def display(self) -> str:
        """The full row text (prefix + label)."""
        return f"{self.prefix}{self.label}"
