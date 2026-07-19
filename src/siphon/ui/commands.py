"""Command palette provider — the ``ctrl+p`` menu (yoinks M7 extra).

Textual ships a fuzzy-searching command palette out of the box; registering
a :class:`~textual.command.Provider` on the App populates it. The palette
opens with the default ``ctrl+backslash`` binding; we add ``ctrl+p`` in
:class:`~siphon.ui.app.SiphonApp` for a more discoverable shortcut.

Exposed commands:

* **Switch theme** (three separate hits — one per mode).
* **Open history** — same as ``^r``.
* **Paste from clipboard** — fills the input with the current clipboard URL.
* **Check for updates** — refires the background update check.
* **Quit** — same as ``^c``.

Each command is a thin closure over an action name on the app or the main
screen; keeping them here (rather than as ad-hoc ``action_*`` methods) lets
us present a curated list without cluttering the phase state machine.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator, Callable
from typing import TYPE_CHECKING, cast

from textual.command import DiscoveryHit, Hit, Provider

from siphon.models.theme import THEME_MODES, ThemeMode
from siphon.ui.theme import theme_name

if TYPE_CHECKING:
    from siphon.ui.app import SiphonApp

# Textual expects a plain zero-arg callable (sync or async) for command callbacks.
Callback = Callable[[], None]


class SiphonCommands(Provider):
    """Palette provider exposing Siphon-specific actions."""

    async def discover(self) -> AsyncIterator[DiscoveryHit]:
        """Yield the default command list shown when the palette opens empty."""
        for command in self._commands():
            yield DiscoveryHit(display=command.display, command=command.callback, help=command.help)

    async def search(self, query: str) -> AsyncIterator[Hit]:
        """Fuzzy-match ``query`` against the registered commands."""
        matcher = self.matcher(query)
        for command in self._commands():
            score = matcher.match(command.display)
            if score <= 0:
                continue
            yield Hit(
                score=score,
                match_display=matcher.highlight(command.display),
                command=command.callback,
                help=command.help,
            )

    def _commands(self) -> list[_Command]:
        """Assemble the current command list.

        Instantiated per-search so it captures the up-to-date app state (e.g.
        the currently active theme is excluded from the "switch to …" hits).
        """
        # ``self.app`` is typed ``App[object]`` on the Provider base but at
        # runtime is always our ``SiphonApp``. Cast so mypy accepts the
        # attribute access below.
        from siphon.ui.app import SiphonApp  # noqa: PLC0415

        app = cast(SiphonApp, self.app)
        current_theme = getattr(app, "theme_mode", None)
        commands: list[_Command] = []

        for mode in THEME_MODES:
            if mode == current_theme:
                continue
            commands.append(
                _Command(
                    display=f"Switch to {mode} theme",
                    help=f"Apply the '{mode}' Siphon theme.",
                    callback=_switch_theme_callback(app, mode),
                )
            )

        commands.append(
            _Command(
                display="Open history",
                help="Show past URLs (same as ctrl+r).",
                callback=_action_callback(app, "open_history"),
            )
        )
        commands.append(
            _Command(
                display="Paste from clipboard",
                help="Fill the input with the current clipboard URL, if any.",
                callback=_paste_from_clipboard_callback(app),
            )
        )
        commands.append(
            _Command(
                display="Check for updates",
                help="Re-run the background version check for yt-dlp and Siphon.",
                callback=_check_updates_callback(app),
            )
        )
        commands.append(
            _Command(
                display="Quit",
                help="Exit Siphon (same as ctrl+c).",
                callback=_quit_callback(app),
            )
        )
        return commands


class _Command:
    """A single palette entry — display text, help, and a zero-arg callback."""

    __slots__ = ("callback", "display", "help")

    def __init__(self, *, display: str, help: str, callback: Callback) -> None:
        self.display = display
        self.help = help
        self.callback = callback


# ---------------------------------------------------------------------------
# Callback factories — each returns a bound zero-arg callable.
# ---------------------------------------------------------------------------
def _switch_theme_callback(app: SiphonApp, mode: ThemeMode) -> Callback:
    def _switch() -> None:
        app._theme_mode = mode
        app.theme = theme_name(mode)
        # Persist and refresh the footer hint via the standard cycle path.
        app._settings.theme_mode = mode
        with contextlib.suppress(OSError):
            app._settings.save()
        for screen in app.screen_stack:
            if hasattr(screen, "update_theme_hint"):
                screen.update_theme_hint(mode)

    return _switch


def _action_callback(app: SiphonApp, action_name: str) -> Callback:
    """Fire an action on whichever screen currently exposes it."""

    def _fire() -> None:
        for screen in reversed(app.screen_stack):
            handler = getattr(screen, f"action_{action_name}", None)
            if callable(handler):
                handler()
                return

    return _fire


def _paste_from_clipboard_callback(app: SiphonApp) -> Callback:
    def _paste() -> None:
        from siphon.services.clipboard import read_clipboard  # noqa: PLC0415

        async def _do() -> None:
            url = await read_clipboard()
            if not url:
                return
            for screen in reversed(app.screen_stack):
                prefill = getattr(screen, "_prefill_url", None)
                if callable(prefill):
                    prefill(url)
                    return

        app.run_worker(_do(), exclusive=False)

    return _paste


def _check_updates_callback(app: SiphonApp) -> Callback:
    def _check() -> None:
        checker = getattr(app, "_check_updates", None)
        if callable(checker):
            app.run_worker(checker(), exclusive=True, group="updates")

    return _check


def _quit_callback(app: SiphonApp) -> Callback:
    def _quit() -> None:
        app.exit()

    return _quit
