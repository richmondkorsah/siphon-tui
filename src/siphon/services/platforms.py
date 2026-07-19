"""URL classification and validation.

Mirrors yoinks' ``lib/platforms.ts`` — a hard-coded list of hosts mapped to
labels, plus a subdomain matcher (``foo.example.com`` matches ``example.com``).
Unknown hosts become ``generic`` with the hostname as label; malformed URLs
become ``unknown``.
"""

from __future__ import annotations

from typing import Final
from urllib.parse import urlparse

from siphon.models.platform import Platform, PlatformKey

# Host → (key, label). Order does not matter: the matcher picks the
# most-specific host (longest matching suffix) so ``music.youtube.com``
# beats ``youtube.com``.
_HOSTS: Final[tuple[tuple[str, PlatformKey, str], ...]] = (
    ("youtube.com", "youtube", "YouTube"),
    ("youtu.be", "youtube", "YouTube"),
    ("music.youtube.com", "youtube", "YouTube Music"),
    ("twitter.com", "twitter", "X"),
    ("x.com", "twitter", "X"),
    ("instagram.com", "instagram", "Instagram"),
    ("threads.net", "threads", "Threads"),
    ("threads.com", "threads", "Threads"),
    ("tiktok.com", "tiktok", "TikTok"),
    ("vimeo.com", "vimeo", "Vimeo"),
    ("twitch.tv", "twitch", "Twitch"),
    ("reddit.com", "reddit", "Reddit"),
    ("facebook.com", "facebook", "Facebook"),
    ("fb.watch", "facebook", "Facebook"),
)

_UNKNOWN_PLATFORM: Final[Platform] = Platform(key="unknown", label="Unknown site")


def is_probably_url(text: str) -> bool:
    """True iff ``text`` parses as an ``http://`` or ``https://`` URL.

    Matches yoinks' F6: parse via :func:`urllib.parse.urlparse`, require the
    scheme be exactly ``http`` or ``https``, and require a non-empty netloc.
    """
    trimmed = text.strip()
    if not trimmed:
        return False
    try:
        parsed = urlparse(trimmed)
    except (ValueError, AttributeError):
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _matches(hostname: str, host: str) -> bool:
    """True iff ``hostname`` equals ``host`` or is a subdomain of it."""
    return hostname == host or hostname.endswith("." + host)


def detect_platform(url: str) -> Platform:
    """Return the :class:`Platform` for ``url``.

    Falls back to ``generic`` (label = hostname) for unrecognised hosts, and
    to ``unknown`` for URLs that fail to parse.
    """
    try:
        parsed = urlparse(url.strip())
    except (ValueError, AttributeError):
        return _UNKNOWN_PLATFORM
    hostname = (parsed.hostname or "").lower()
    if not hostname:
        return _UNKNOWN_PLATFORM

    # Find the most-specific host (longest suffix match) so
    # ``music.youtube.com`` overrides ``youtube.com``.
    best: tuple[str, PlatformKey, str] | None = None
    for entry in _HOSTS:
        host = entry[0]
        if _matches(hostname, host) and (best is None or len(host) > len(best[0])):
            best = entry

    if best is not None:
        return Platform(key=best[1], label=best[2])

    return Platform(key="generic", label=hostname)
