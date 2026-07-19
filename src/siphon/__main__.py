"""Entrypoint for ``python -m siphon``."""

from __future__ import annotations

from siphon.cli import main

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
