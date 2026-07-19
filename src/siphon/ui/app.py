"""The Textual application shell.

Owns the top-level bindings (``ctrl+c`` quit, ``ctrl+t`` theme cycle), mounts
:class:`~siphon.ui.screens.main.MainScreen`, and is the target for messages
from workers. Alt-screen enter/exit and mouse-tracking setup/tear-down are
Textual's job — we do *not* install our own ``atexit``/signal handlers here
(they would race Textual's driver and re-introduce the very crash-restore
problem yoinks had to hand-solve).
"""

from __future__ import annotations

import contextlib
from typing import ClassVar

from textual.app import App
from textual.binding import Binding, BindingType

from siphon.args import ThemeMode
from siphon.config.settings import SiphonSettings, get_settings
from siphon.models.theme import next_theme_mode
from siphon.services.update_check import check_updates
from siphon.ui.commands import SiphonCommands
from siphon.ui.messages import UpdateHintAvailable
from siphon.ui.screens.main import MainScreen
from siphon.ui.theme import all_themes, theme_name


class SiphonApp(App[str]):
    """The Siphon Textual App.

    Parameters
    ----------
    initial_url:
        If set, the app skips the input phase and jumps straight to probing
        (analog of ``yoinks <url>``). M1 accepts and stores the value but
        doesn't yet act on it — that lands in M3.
    theme_mode_override:
        When passed, forces a theme instead of consulting persisted settings.
    output_dir_override:
        When passed, overrides the configured download directory for this
        session only.
    settings:
        Injectable settings object for tests. Defaults to the process-wide
        singleton loaded from ``~/.config/siphon/config.toml``.
    """

    CSS = """
    Screen {
        background: $background;
        color: $foreground;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("ctrl+c", "quit", "quit", show=False, priority=True),
        Binding("ctrl+t", "cycle_theme", "cycle theme", show=False),
        # Discoverable command-palette shortcut in addition to Textual's default.
        Binding("ctrl+p", "command_palette", "command palette", show=False),
    ]

    # Register our custom provider alongside Textual's built-in system commands.
    COMMANDS: ClassVar[set[object]] = App.COMMANDS | {SiphonCommands}  # type: ignore[assignment]

    def __init__(
        self,
        *,
        initial_url: str | None = None,
        theme_mode_override: ThemeMode | None = None,
        output_dir_override: str | None = None,
        settings: SiphonSettings | None = None,
    ) -> None:
        super().__init__()
        self.initial_url = initial_url
        self.output_dir_override = output_dir_override
        self._settings: SiphonSettings = settings if settings is not None else get_settings()
        self._theme_mode: ThemeMode = theme_mode_override or self._settings.theme_mode
        # Set by MainScreen when a download completes; the CLI prints it after
        # alt-screen exit so it's visible in the user's scrollback.
        self.final_filepath: str | None = None

    @property
    def theme_mode(self) -> ThemeMode:
        """The Siphon theme mode currently in effect (``auto`` / ``light`` / ``dark``)."""
        return self._theme_mode

    def on_mount(self) -> None:
        """Register themes, apply the active mode, and mount the main screen."""
        for theme in all_themes():
            self.register_theme(theme)
        self.theme = theme_name(self._theme_mode)
        self.push_screen(MainScreen(initial_url=self.initial_url))

        # Fire-and-forget: check for newer yt-dlp / siphon-tui.
        if self._settings.check_updates:
            self.run_worker(self._check_updates(), exclusive=True, group="updates")

    async def _check_updates(self) -> None:
        """Post an :class:`UpdateHintAvailable` if either package is stale."""
        status = await check_updates()
        message = status.hint_message
        if message and self.screen is not None:
            self.screen.post_message(UpdateHintAvailable(message))

    def action_cycle_theme(self) -> None:
        """Rotate auto → light → dark → auto, apply, and persist."""
        self._theme_mode = next_theme_mode(self._theme_mode)
        self.theme = theme_name(self._theme_mode)

        # Persist the choice — swallow write failures the way yoinks does.
        # Losing a preference file is annoying but never worth crashing over.
        self._settings.theme_mode = self._theme_mode
        with contextlib.suppress(OSError):
            self._settings.save()

        # Reflect the new mode in the footer hint if MainScreen is currently on
        # the stack. ``screen_stack`` is safer than ``self.screen`` — the latter
        # raises when no screen is mounted (e.g. before ``on_mount`` finishes).
        for screen in self.screen_stack:
            if isinstance(screen, MainScreen):
                screen.update_theme_hint(self._theme_mode)
                break
