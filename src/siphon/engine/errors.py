"""Error types raised by the engine layer.

yt-dlp emits verbose error messages that include extractor prefixes and
tracebacks. :class:`CleanedYtdlpError` carries a *user-facing* message
extracted from the raw error (yoinks ``cleanYtDlpError``) so the UI can
present a single readable line.
"""

from __future__ import annotations


class CleanedYtdlpError(Exception):
    """A yt-dlp failure with a user-facing single-line message."""

    def __init__(self, user_message: str, *, original: BaseException | None = None) -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.original = original


def clean_ytdlp_error(raw: str) -> str:
    """Extract the last ``ERROR:`` line from yt-dlp's noisy output.

    Falls back to the whole message when no ``ERROR:`` line is present.
    Strips a leading ``[extractor]`` prefix if any (yoinks parity).
    """
    if not raw:
        return "yt-dlp exited without a message"

    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    error_lines = [line for line in lines if line.startswith("ERROR:")]
    candidate = error_lines[-1] if error_lines else lines[-1]

    # Strip the ``ERROR: `` prefix.
    if candidate.startswith("ERROR:"):
        candidate = candidate[len("ERROR:") :].strip()

    # Strip any ``[extractor]`` prefix, e.g. ``[youtube] abcd:``.
    if candidate.startswith("["):
        rest = candidate.split("]", 1)
        if len(rest) == 2:
            candidate = rest[1].strip()

    # Trim leading colons or dashes that sometimes remain after prefix strip.
    return candidate.lstrip(":- ").strip() or "yt-dlp failed"
