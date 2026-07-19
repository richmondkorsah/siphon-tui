"""Persisted user settings.

Backed by :class:`pydantic_settings.BaseSettings` with a TOML source at
:func:`siphon.config.paths.config_file`. All fields have safe defaults, so a
first-run user sees a working app with no file on disk.

Environment variables prefixed with ``SIPHON_`` override the file (useful in
tests and for one-shot invocations such as ``SIPHON_THEME_MODE=dark siphon``).
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any

import tomli_w
from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from siphon.config import paths
from siphon.models.theme import ThemeMode


class SiphonSettings(BaseSettings):
    """User-facing configuration persisted across runs."""

    model_config = SettingsConfigDict(
        env_prefix="SIPHON_",
        env_file=None,
        case_sensitive=False,
        extra="ignore",
    )

    theme_mode: ThemeMode = Field(
        default="auto",
        description="Preferred theme mode; cycled with ctrl+t and persisted here.",
    )

    download_dir: Path = Field(
        default_factory=paths.default_download_dir,
        description="Where completed downloads land. --output-dir overrides per invocation.",
    )

    check_updates: bool = Field(
        default=True,
        description="Whether to fire a background check for newer yt-dlp / Siphon releases.",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Order of precedence: constructor args → env vars → TOML file → defaults."""
        toml_file = paths.config_file()
        toml_source = TomlConfigSettingsSource(settings_cls, toml_file=toml_file)
        return (init_settings, env_settings, toml_source, file_secret_settings)

    def save(self) -> None:
        """Persist current values to :func:`siphon.config.paths.config_file`.

        Writes are atomic (temp-file + rename). Failures propagate; callers
        should log/swallow if the write is non-critical.
        """
        path = paths.config_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = self.model_dump(mode="json")
        # Paths serialise as strings; keep them as strings in TOML.
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(tomli_w.dumps(payload).encode("utf-8"))
        tmp.replace(path)

    @classmethod
    def load(cls) -> SiphonSettings:
        """Convenience alias for ``SiphonSettings()`` — reads the current file + env."""
        return cls()


@lru_cache(maxsize=1)
def get_settings() -> SiphonSettings:
    """Process-wide singleton so we don't re-parse the TOML on every access."""
    return SiphonSettings.load()


def reset_settings_cache() -> None:
    """Drop the cached singleton; used by tests that write a fresh config."""
    get_settings.cache_clear()


def _load_raw_toml() -> dict[str, Any]:
    """Return the raw TOML contents as a dict, or ``{}`` if the file is missing."""
    path = paths.config_file()
    if not path.exists():
        return {}
    return tomllib.loads(path.read_text(encoding="utf-8"))
