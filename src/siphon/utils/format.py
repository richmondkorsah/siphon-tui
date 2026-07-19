"""Human-readable formatting helpers (yoinks F26).

All functions are pure and side-effect-free; safe to call from any thread.

The unit boundaries mirror yoinks:
* Bytes: B → KB → MB → GB; 10+ or GB rounds to integer, else one decimal.
* Durations: ``m:ss`` under an hour, ``h:mm:ss`` with padded minutes above.
* Speeds append ``/s`` to the byte formatter output.
* ETAs share the duration formatter.
"""

from __future__ import annotations

import math
from pathlib import Path

_BYTE_UNITS: tuple[tuple[float, str], ...] = (
    (1024**3, "GB"),
    (1024**2, "MB"),
    (1024, "KB"),
)


def format_bytes(n: float | int | None) -> str:
    """Format a byte count as ``"1.5 MB"`` / ``"128 KB"`` / ``"640 B"``.

    ``None`` and non-finite values return an empty string so callers can
    concatenate the result without a guard.
    """
    if n is None:
        return ""
    if isinstance(n, float) and (math.isnan(n) or math.isinf(n)):
        return ""
    if n < 0:
        return ""
    value = float(n)
    for divisor, unit in _BYTE_UNITS:
        if value >= divisor:
            scaled = value / divisor
            # 10+ or GB → integer; else one decimal.
            if scaled >= 10 or unit == "GB":
                return f"{round(scaled)} {unit}"
            return f"{scaled:.1f} {unit}"
    return f"{int(value)} B"


def format_duration(seconds: float | int | None) -> str:
    """Format a duration in seconds as ``m:ss`` or ``h:mm:ss``.

    Under one hour: ``5:04``. One hour or more: ``1:02:03`` (minutes padded
    to two digits when an hour is present, per yoinks).
    """
    if seconds is None:
        return ""
    if isinstance(seconds, float) and (math.isnan(seconds) or math.isinf(seconds)):
        return ""
    if seconds < 0:
        return ""
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def format_speed(bytes_per_s: float | int | None) -> str:
    """Format a transfer speed as ``"1.2 MB/s"``. Empty on ``None`` / non-finite."""
    formatted = format_bytes(bytes_per_s)
    return f"{formatted}/s" if formatted else ""


def format_eta(seconds: float | int | None) -> str:
    """Format an ETA — thin wrapper over :func:`format_duration` for grep-ability."""
    return format_duration(seconds)


def truncate(text: str, max_length: int, *, ellipsis: str = "…") -> str:
    """Trim ``text`` to at most ``max_length`` cells, appending ``ellipsis`` on truncation."""
    if max_length <= 0:
        return ""
    if len(text) <= max_length:
        return text
    if max_length <= len(ellipsis):
        return ellipsis[:max_length]
    return text[: max_length - len(ellipsis)] + ellipsis


def shorten_path(path: Path | str, home: Path | None = None, max_length: int = 60) -> str:
    """Return ``~/…foo.mp4`` — home-relative + middle-truncated, preserving extension."""
    p = Path(path)
    home_dir = home if home is not None else Path.home()
    text = str(p)
    try:
        rel = p.relative_to(home_dir)
        text = f"~/{rel}"
    except ValueError:
        pass  # path lives outside HOME

    if len(text) <= max_length:
        return text

    # Preserve the extension when truncating the middle of a long path.
    ext = p.suffix
    keep_end = min(len(ext) + 8, max_length // 2)  # last 8 chars + ext
    keep_start = max_length - keep_end - 1  # 1 for the ellipsis
    if keep_start < 3:
        return text[: max_length - 1] + "…"
    return f"{text[:keep_start]}…{text[-keep_end:]}"
