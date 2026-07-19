"""Best-effort clipboard reader (yoinks F4).

Uses :mod:`pyperclip` under the hood, wrapping the sync call in
:func:`asyncio.to_thread` with a 500 ms deadline so a hung X11 helper never
freezes the Textual event loop. Any failure — timeout, missing backend,
non-URL content, multi-line — returns an empty string; the UI simply doesn't
offer a clipboard suggestion.

Rules (matching yoinks):

* Reject strings containing any whitespace (multi-line, tabs, spaces).
* Require :func:`siphon.services.platforms.is_probably_url` to accept the
  trimmed content.
"""

from __future__ import annotations

import asyncio
import contextlib

import pyperclip

from siphon.config.constants import CLIPBOARD_READ_TIMEOUT_S
from siphon.services.platforms import is_probably_url


def _has_whitespace(text: str) -> bool:
    """Any Unicode whitespace disqualifies clipboard content as a URL suggestion."""
    return any(ch.isspace() for ch in text)


async def read_clipboard(timeout_s: float = CLIPBOARD_READ_TIMEOUT_S) -> str:
    """Return a clipboard-derived URL, or ``""`` when none is offerable.

    Parameters
    ----------
    timeout_s:
        Maximum time to wait for the clipboard read. Defaults to yoinks'
        500 ms budget. Longer waits risk freezing frame rendering.
    """
    text = ""
    with contextlib.suppress(TimeoutError, pyperclip.PyperclipException, OSError):
        text = await asyncio.wait_for(
            asyncio.to_thread(pyperclip.paste),
            timeout=timeout_s,
        )

    if not text:
        return ""
    # yoinks parity: whitespace-containing clipboard content is skipped
    # (``new URL()`` would silently strip newlines and the URL parsers here
    # would then accept something the user didn't intend).
    if _has_whitespace(text):
        return ""
    if not is_probably_url(text):
        return ""
    return text
