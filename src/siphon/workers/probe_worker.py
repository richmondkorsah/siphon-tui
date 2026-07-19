"""Async wrapper for :func:`siphon.engine.probe.probe_sync`.

Runs the blocking probe on a background thread via :func:`asyncio.to_thread`
so the Textual event loop keeps rendering. On success returns the info dict;
on failure raises :class:`~siphon.engine.errors.CleanedYtdlpError` or
:class:`~siphon.engine.cancellation.DownloadCancelled` as-is, letting the
caller (the screen) map them to phase transitions.
"""

from __future__ import annotations

import asyncio
from typing import Any

from siphon.engine.cancellation import CancellationToken
from siphon.engine.probe import probe_sync


async def probe(url: str, token: CancellationToken | None = None) -> dict[str, Any]:
    """Fetch a yt-dlp info dict for ``url`` off the event loop."""
    return await asyncio.to_thread(probe_sync, url, token)
