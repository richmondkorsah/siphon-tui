"""Program entrypoint: parse argv, handle help/version, or launch the TUI.

Analog of yoinks' ``src/cli.tsx``. The alt-screen lifecycle is delegated to
Textual (via :class:`siphon.ui.app.SiphonApp`), so this module stays small.
"""

from __future__ import annotations

import sys

from siphon import __version__
from siphon.args import HELP_TEXT, ParsedArgs, parse_args


def _die(message: str) -> int:
    """Print a yoinks-style error to stderr and return exit code 1."""
    sys.stderr.write(f"siphon: {message}\n")
    sys.stderr.write('Try "siphon --help" for usage.\n')
    return 1


def main(argv: list[str] | None = None) -> int:
    """Parse ``argv`` (defaults to ``sys.argv[1:]``) and dispatch.

    Returns the process exit code.
    """
    args: ParsedArgs = parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.error is not None:
        return _die(args.error)

    if args.help:
        sys.stdout.write(HELP_TEXT)
        return 0

    if args.version:
        sys.stdout.write(f"siphon {__version__}\n")
        return 0

    # Import lazily so `--help`/`--version` don't pay Textual's import cost.
    from siphon.ui.app import SiphonApp  # noqa: PLC0415

    app = SiphonApp(
        initial_url=args.initial_url,
        theme_mode_override=args.theme_mode,
        output_dir_override=args.output_dir,
    )
    app.run()

    # If the app captured a completed download path, print it after alt-screen
    # tear-down so the user sees it in their scrollback.
    if app.final_filepath:
        sys.stdout.write(f"✓ siphoned → {app.final_filepath}\n")

    return 0
