"""Background version-freshness check for yt-dlp and Siphon itself.

Compares :func:`importlib.metadata.version` against the latest published
version:

* **yt-dlp** — ``https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest``.
* **siphon-tui** — ``https://pypi.org/pypi/siphon-tui/json``.

This never installs anything and never asks the user for confirmation — it
just returns an :class:`UpdateStatus` the UI can use to show a dim footer
hint. Any network failure returns "unknown" and the UI shows nothing.

The design lets us drop this into a background worker on app start-up
without slowing the golden path: a lookup that fails or times out costs
nothing user-visible.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from urllib.error import URLError
from urllib.request import Request, urlopen

_logger = logging.getLogger(__name__)

_YTDLP_URL = "https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest"
_SIPHON_URL = "https://pypi.org/pypi/siphon-tui/json"
_UA = "siphon-tui/update-check"
_TIMEOUT_S = 3.0


@dataclass(frozen=True, slots=True)
class ComponentStatus:
    """The freshness state of one installed package.

    ``latest_version`` and ``installed_version`` are best-effort strings;
    ``None`` means the lookup failed and no hint should be shown.
    """

    name: str
    installed_version: str | None
    latest_version: str | None

    @property
    def is_stale(self) -> bool:
        """True iff both versions are known and the latest > installed."""
        if not self.installed_version or not self.latest_version:
            return False
        return _parse_version(self.installed_version) < _parse_version(self.latest_version)


@dataclass(frozen=True, slots=True)
class UpdateStatus:
    """Combined result of the update check.

    :attr:`hint_message` is ``None`` when nothing needs updating (or the
    check silently failed); a short string when the UI should surface it.
    """

    ytdlp: ComponentStatus
    siphon: ComponentStatus

    @property
    def hint_message(self) -> str | None:
        stale = [c for c in (self.ytdlp, self.siphon) if c.is_stale]
        if not stale:
            return None
        parts = [f"{c.name} {c.latest_version} available" for c in stale]
        return " · ".join(parts)


async def check_updates() -> UpdateStatus:
    """Run both checks in parallel; never raises."""
    ytdlp_installed = _safe_installed_version("yt_dlp")
    siphon_installed = _safe_installed_version("siphon-tui")

    ytdlp_latest, siphon_latest = await asyncio.gather(
        _fetch_ytdlp_latest(),
        _fetch_siphon_latest(),
    )

    return UpdateStatus(
        ytdlp=ComponentStatus(
            name="yt-dlp",
            installed_version=ytdlp_installed,
            latest_version=ytdlp_latest,
        ),
        siphon=ComponentStatus(
            name="siphon",
            installed_version=siphon_installed,
            latest_version=siphon_latest,
        ),
    )


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------
async def _fetch_ytdlp_latest() -> str | None:
    payload = await asyncio.to_thread(_http_get_json, _YTDLP_URL)
    if payload is None:
        return None
    tag = payload.get("tag_name")
    return str(tag) if isinstance(tag, str) else None


async def _fetch_siphon_latest() -> str | None:
    payload = await asyncio.to_thread(_http_get_json, _SIPHON_URL)
    if payload is None:
        return None
    info = payload.get("info")
    if not isinstance(info, dict):
        return None
    v = info.get("version")
    return str(v) if isinstance(v, str) else None


def _http_get_json(url: str) -> dict[str, object] | None:
    """Blocking HTTP GET returning parsed JSON dict, or ``None`` on any failure.

    ``url`` is a compile-time constant defined in this module, so the
    :func:`urllib.request.urlopen` call is not user-controllable.
    """
    try:
        req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
        with urlopen(req, timeout=_TIMEOUT_S) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError) as exc:
        _logger.debug("update check network error for %s: %s", url, exc)
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _safe_installed_version(pkg: str) -> str | None:
    """Return the installed version of ``pkg``, or ``None`` when not installed."""
    try:
        return version(pkg)
    except PackageNotFoundError:
        return None


# ---------------------------------------------------------------------------
# Version comparison
# ---------------------------------------------------------------------------
def _parse_version(text: str) -> tuple[int, ...]:
    """Parse a version string into a tuple of ints for ordering.

    yt-dlp uses calendar versioning (``2026.7.4``) and Siphon uses semver-ish
    (``0.1.0``). Both flatten to a tuple of numeric components. Parsing stops
    at the first non-purely-numeric chunk so pre-release suffixes are
    conservatively ignored (``0.1.0.dev1`` → ``(0, 1, 0)``, treated as
    "pre-1.0" rather than "greater than 0.1.0").
    """
    parts: list[int] = []
    for chunk in text.strip().lstrip("v").split("."):
        if not chunk or not chunk.isdigit():
            break
        parts.append(int(chunk))
    return tuple(parts)
