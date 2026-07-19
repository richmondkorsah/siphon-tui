"""Application-wide string and numeric constants.

Kept separate from :mod:`siphon.config.settings` because these are compile-time
literals that never change per-user — the tagline, the platform strip, and the
hard-coded limits like ``HISTORY_LIMIT`` from the yoinks spec.
"""

from __future__ import annotations

from typing import Final

TAGLINE: Final[str] = "siphon any video. paste. sip. done."
"""One-line brand promise shown under the logo on every screen."""

PLATFORM_STRIP: Final[str] = "youtube · x · instagram · threads · tiktok · +1800 more"
"""Dim strip advertising supported sites; unchanged from yoinks."""

HISTORY_LIMIT: Final[int] = 50
"""Maximum number of URLs kept in ``history.json`` (yoinks F18 parity)."""

MAX_VIDEO_CHOICES: Final[int] = 8
"""Maximum distinct video heights shown in the picker (yoinks F11 parity)."""

BOX_MIN_WIDTH: Final[int] = 14
BOX_PADDING_COLS: Final[int] = 6
BOX_MAX_WIDTH: Final[int] = 64
"""Framed-input width clamps: ``clamp(BOX_MIN_WIDTH, cols - BOX_PADDING_COLS, BOX_MAX_WIDTH)``."""

CONTENT_MIN_WIDTH: Final[int] = 10
CONTENT_PADDING_COLS: Final[int] = 4
CONTENT_MAX_WIDTH: Final[int] = 78
"""Picker two-column body width clamps."""

CLIPBOARD_READ_TIMEOUT_S: Final[float] = 0.5
"""Deadline for reading the system clipboard (F4)."""
