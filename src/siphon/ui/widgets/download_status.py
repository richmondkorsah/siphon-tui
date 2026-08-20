"""Three-row download status block: bar, gap, meta (yoinks F14).

Layout is *always* three rows tall — even in the "just started" state — so
the surrounding layout never shifts as progress ticks arrive. The meta row
carries one of four permutations:

* **processing** (postprocessor running): bar shows 100 %, meta shows
  ``⠋ processing…``.
* **has_total** (byte totals known): real percentage bar, meta shows
  ``part 1/2   10 MB/s   1:23``.
* **has_bytes** (bytes but no total): spinner, meta shows
  ``5 MB   1.2 MB/s``.
* **no progress yet**: 0 % bar, meta shows ``⠋ starting download…`` (or
  ``⠋ link expired — grabbing a fresh one…`` when refreshing).
"""

from __future__ import annotations

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Center, Vertical
from textual.widget import Widget
from textual.widgets import Static

from siphon.models.progress import DownloadProgress
from siphon.ui.widgets.progress_bar import ProgressBar
from siphon.ui.widgets.spinner import SPINNER_FRAMES, SPINNER_INTERVAL_S
from siphon.utils.format import format_bytes, format_eta, format_speed


class DownloadStatusView(Widget):
    """Composite widget that owns the three progress rows."""

    DEFAULT_CSS = """
    DownloadStatusView {
        height: 3;
        width: 100%;
    }
    DownloadStatusView > Vertical {
        height: 3;
        width: 100%;
    }
    DownloadStatusView #status-bar-row {
        height: 1;
        width: 100%;
    }
    DownloadStatusView #status-gap {
        height: 1;
    }
    DownloadStatusView #status-meta-row {
        height: 1;
        width: 100%;
    }
    DownloadStatusView #status-meta {
        color: $text-muted;
        text-style: dim;
        height: 1;
        width: auto;
    }
    """

    def __init__(self, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self._progress: DownloadProgress | None = None
        self._processing: bool = False
        self._refreshing: bool = False
        self._refreshing_reason: str = "link expired — grabbing a fresh one…"
        self._spinner_frame: int = 0

    def compose(self) -> ComposeResult:
        """Yield the three fixed-height rows."""
        with Vertical():
            with Center(id="status-bar-row"):
                yield ProgressBar(0.0, id="status-bar")
            yield Static("", id="status-gap")
            with Center(id="status-meta-row"):
                yield Static(self._meta_text(), id="status-meta")

    def on_mount(self) -> None:
        self.set_interval(SPINNER_INTERVAL_S, self._advance_spinner)

    def _advance_spinner(self) -> None:
        """Tick the spinner glyph — only repaints while one is actually shown."""
        self._spinner_frame = (self._spinner_frame + 1) % len(SPINNER_FRAMES)
        if self._is_spinning():
            self._refresh_rows()

    def _is_spinning(self) -> bool:
        """True iff the current meta row is showing a spinner glyph."""
        if self._processing:
            return True
        return self._progress is None or not self._progress.has_total

    # ------------------------------------------------------ external state
    def apply_progress(self, progress: DownloadProgress) -> None:
        """A new progress tick arrived — swap into the byte-progress mode."""
        self._progress = progress
        self._processing = False
        self._refreshing = False
        self._refresh_rows()

    def mark_processing(self) -> None:
        """yt-dlp entered a postprocessor — show ``processing…``."""
        self._processing = True
        self._refreshing = False
        self._refresh_rows()

    def mark_refreshing(self, reason: str = "link expired — grabbing a fresh one…") -> None:
        """An automatic retry started — swap the "starting" text to explain why."""
        self._refreshing = True
        self._refreshing_reason = reason
        self._refresh_rows()

    # ------------------------------------------------------ render helpers
    def _refresh_rows(self) -> None:
        try:
            bar = self.query_one("#status-bar", ProgressBar)
            meta = self.query_one("#status-meta", Static)
        except Exception:
            return
        bar.set_fraction(self._fraction())
        meta.update(self._meta_text())

    def _fraction(self) -> float:
        if self._processing:
            return 1.0
        if self._progress is None:
            return 0.0
        return self._progress.fraction

    def _meta_text(self) -> Text:
        """Compose the meta row for the current state."""
        if self._processing:
            return self._spinner_row("processing…")

        p = self._progress
        if p is None:
            return self._spinner_row(
                self._refreshing_reason if self._refreshing else "starting download…"
            )

        if p.has_total:
            # Real bar + "part x/y  <speed>  <eta>"
            speed = format_speed(p.speed).rjust(10) if p.speed else " " * 10
            eta = format_eta(p.eta).ljust(12) if p.eta else " " * 12
            parts = f"part {p.part}/{p.total_parts}" if p.total_parts > 1 else " " * 8
            text = Text(no_wrap=True, overflow="crop")
            text.append(parts.ljust(8))
            text.append("  ")
            text.append(speed)
            text.append("  ")
            text.append(eta)
            return text

        if p.has_bytes:
            # Spinner + "<bytes>  <speed>"
            bytes_str = format_bytes(p.downloaded_bytes).rjust(8)
            speed_str = format_speed(p.speed).ljust(10) if p.speed else " " * 10
            text = Text(no_wrap=True, overflow="crop")
            text.append(f"{SPINNER_FRAMES[self._spinner_frame]} ", style="bold")
            text.append("downloading…", style="dim")
            text.append("  ")
            text.append(bytes_str)
            text.append("  ")
            text.append(speed_str)
            return text

        return self._spinner_row(
            "link expired — grabbing a fresh one…" if self._refreshing else "starting download…"
        )

    def _spinner_row(self, label: str) -> Text:
        """A single row: ``⠋ label`` with the spinner glyph bolded, mid-spin."""
        text = Text(no_wrap=True, overflow="crop")
        text.append(f"{SPINNER_FRAMES[self._spinner_frame]} ", style="bold")
        text.append(label)
        return text
