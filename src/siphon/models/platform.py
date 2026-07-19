"""Platform identity for a URL — used to label the frame in probing / picking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PlatformKey = Literal[
    "youtube",
    "twitter",
    "instagram",
    "threads",
    "tiktok",
    "vimeo",
    "twitch",
    "reddit",
    "facebook",
    "generic",
    "unknown",
]
"""All possible platform identifiers.

``generic`` = valid URL on an unrecognised host (the hostname becomes the label).
``unknown`` = the URL failed to parse at all.
"""


@dataclass(frozen=True, slots=True)
class Platform:
    """A URL's detected platform + a human-readable label for the frame title."""

    key: PlatformKey
    label: str
