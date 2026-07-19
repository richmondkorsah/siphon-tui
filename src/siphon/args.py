"""Hand-rolled CLI argument parser.

Mirrors yoinks' ``lib/args.ts`` semantics rather than relying on ``argparse`` so
we get identical error messages and exit behaviour. Walks ``argv`` left-to-right,
distinguishes flags from positionals, allows at most one positional URL, and
validates the theme value against the three literal modes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ThemeMode = Literal["auto", "light", "dark"]
"""The three theme modes; keep in sync with ``siphon.models.theme``."""

THEME_MODES: tuple[ThemeMode, ...] = ("auto", "light", "dark")

HELP_TEXT = """\
siphon — siphon any video. paste. sip. done.

Usage:
  siphon [options] [url]

Options:
  -h, --help              show this help and exit
  -v, --version           show version and exit
      --theme <mode>      force a theme: auto | light | dark
      --output-dir <path> override the download directory
"""


@dataclass(frozen=True, slots=True)
class ParsedArgs:
    """Result of parsing ``argv``."""

    help: bool = False
    version: bool = False
    initial_url: str | None = None
    theme_mode: ThemeMode | None = None
    output_dir: str | None = None
    error: str | None = None
    _positionals: list[str] = field(default_factory=list, repr=False)


def _is_theme_mode(value: str) -> bool:
    """True iff ``value`` is one of the accepted theme modes."""
    return value in THEME_MODES


def parse_args(argv: list[str]) -> ParsedArgs:
    """Parse a list of command-line arguments (without the program name).

    Returns a :class:`ParsedArgs` with either ``error`` set (caller prints the
    message and exits non-zero) or the successfully parsed fields.
    """
    help_ = False
    version_ = False
    initial_url: str | None = None
    theme_mode: ThemeMode | None = None
    output_dir: str | None = None
    positionals: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]

        if arg in ("-h", "--help"):
            help_ = True
        elif arg in ("-v", "--version"):
            version_ = True
        elif arg == "--theme":
            # Spaced form: needs a value on the next slot.
            if i + 1 >= len(argv):
                return ParsedArgs(error="--theme requires a value (auto|light|dark)")
            i += 1
            value = argv[i]
            if not _is_theme_mode(value):
                return ParsedArgs(error=f"unknown theme '{value}' (auto|light|dark)")
            theme_mode = value  # type: ignore[assignment]
        elif arg.startswith("--theme="):
            value = arg.removeprefix("--theme=")
            if not _is_theme_mode(value):
                return ParsedArgs(error=f"unknown theme '{value}' (auto|light|dark)")
            theme_mode = value  # type: ignore[assignment]
        elif arg == "--output-dir":
            if i + 1 >= len(argv):
                return ParsedArgs(error="--output-dir requires a path")
            i += 1
            output_dir = argv[i]
        elif arg.startswith("--output-dir="):
            output_dir = arg.removeprefix("--output-dir=")
        elif arg.startswith("-"):
            # Any other flag is unknown — yoinks parity.
            return ParsedArgs(error=f"unknown flag {arg}")
        else:
            positionals.append(arg)

        i += 1

    if len(positionals) > 1:
        return ParsedArgs(error="expected a single url")

    if positionals:
        initial_url = positionals[0]

    return ParsedArgs(
        help=help_,
        version=version_,
        initial_url=initial_url,
        theme_mode=theme_mode,
        output_dir=output_dir,
        _positionals=positionals,
    )
