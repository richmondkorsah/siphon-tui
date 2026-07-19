"""Cross-thread cancellation token.

The download engine runs synchronous ``yt-dlp`` code in a worker thread while
the UI stays on the asyncio event loop. Neither ``asyncio.Task.cancel`` nor
``asyncio.Event`` are enough on their own — a plain :class:`threading.Event`
would work for the thread side, but then the UI can't ``await`` cancellation.

:class:`CancellationToken` wraps both — the UI sets it via :meth:`cancel`
(sync, thread-safe) and the worker polls it via :attr:`cancelled` at safe
points. When yt-dlp is inside its own I/O we can't interrupt it; instead
our ``progress_hooks`` (M5) raise :class:`DownloadCancelled` on the next
tick to unwind cleanly.
"""

from __future__ import annotations

import threading


class DownloadCancelled(Exception):  # noqa: N818 — mirrors asyncio.CancelledError naming
    """Raised inside a progress hook to unwind yt-dlp when the token fires.

    Named ``Cancelled`` rather than ``CancelledError`` on purpose — mirrors
    :class:`asyncio.CancelledError`'s convention: a cancellation event, not
    a bug.
    """


class CancellationToken:
    """A thread-safe boolean flag that starts unset and latches when cancelled."""

    __slots__ = ("_event",)

    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        """Mark the token as cancelled. Safe to call from any thread."""
        self._event.set()

    @property
    def cancelled(self) -> bool:
        """True once :meth:`cancel` has been invoked."""
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        """Raise :class:`DownloadCancelled` when the token has fired."""
        if self._event.is_set():
            raise DownloadCancelled("operation cancelled")

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the token fires or ``timeout`` elapses. Returns the cancelled state."""
        return self._event.wait(timeout)
