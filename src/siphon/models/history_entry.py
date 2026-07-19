"""One row in the persisted history file (M7 JSONL format).

The M3 format was a bare ``list[str]`` of URLs. M7 upgrades to line-per-JSON
with metadata (title, platform label, ISO-8601 timestamp) so the searchable
history modal (``^r``) can render richer rows.

Backwards compat: the loader in :mod:`siphon.services.history` accepts both
formats and migrates on next write.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


def _now_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds")


@dataclass(frozen=True, slots=True)
class HistoryEntry:
    """One recorded URL, optionally enriched with probe-time metadata."""

    url: str
    title: str | None = None
    platform: str | None = None
    timestamp: str = field(default_factory=_now_iso)

    def to_dict(self) -> dict[str, str | None]:
        """Serialise to the JSON line shape."""
        return {
            "url": self.url,
            "title": self.title,
            "platform": self.platform,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, object]) -> HistoryEntry | None:
        """Deserialise one JSON dict. Returns ``None`` on malformed input."""
        url = raw.get("url")
        if not isinstance(url, str) or not url:
            return None
        return cls(
            url=url,
            title=_str_or_none(raw.get("title")),
            platform=_str_or_none(raw.get("platform")),
            timestamp=_str_or_none(raw.get("timestamp")) or _now_iso(),
        )


def _str_or_none(value: object) -> str | None:
    """Return ``value`` if it's a non-empty string; otherwise ``None``."""
    if isinstance(value, str) and value:
        return value
    return None
