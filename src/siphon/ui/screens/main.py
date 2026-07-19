"""The single top-level screen that hosts every phase of the app.

M4 promotes the probe stub to a real ``yt-dlp`` extraction (running on a
background thread) and mounts the picker on success. The picker is a
two-column body: title / uploader / duration on the left, a titled
:class:`~siphon.ui.widgets.panel.Panel` wrapping a
:class:`~siphon.ui.widgets.choice_list.ChoiceList` on the right.
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from textual.app import ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Center, Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Static

from siphon.config.settings import get_settings
from siphon.engine.cancellation import CancellationToken, DownloadCancelled
from siphon.engine.choice_builder import build_choices
from siphon.engine.errors import CleanedYtdlpError
from siphon.models.choice import DownloadChoice
from siphon.models.phase import (
    DonePhase,
    DownloadingPhase,
    ErrorPhase,
    InputPhase,
    Phase,
    PickingPhase,
    ProbingPhase,
)
from siphon.services import ffmpeg_discovery
from siphon.services import history as history_service
from siphon.services.clipboard import read_clipboard
from siphon.services.platforms import detect_platform, is_probably_url
from siphon.ui.messages import (
    CancelRequested,
    ClipboardAccepted,
    DownloadFailed,
    DownloadProcessing,
    DownloadProgressTick,
    DownloadSucceeded,
    HomeRequested,
    SubmitRequested,
    UpdateHintAvailable,
)
from siphon.ui.screens.history import HistoryModal
from siphon.ui.widgets.choice_list import ChoiceList, ChoiceSelected
from siphon.ui.widgets.download_status import DownloadStatusView
from siphon.ui.widgets.framed_input import FramedInput
from siphon.ui.widgets.logo import LogoWidget
from siphon.ui.widgets.panel import Panel
from siphon.ui.widgets.shortcuts import Hint, ShortcutsWidget
from siphon.ui.widgets.tagline import TaglineStrip
from siphon.utils.format import format_duration, shorten_path, truncate
from siphon.workers.download_worker import run_download
from siphon.workers.probe_worker import probe


class MainScreen(Screen[str]):
    """Composes the shared shell around a phase-driven body."""

    DEFAULT_CSS = """
    /* The screen centres a fixed-width chrome column vertically + horizontally
       so the layout always looks intentional regardless of terminal size.
       ``width: 100`` (not ``100%``) is deliberate: a percentage width fills
       its parent and defeats ``align: center``, so the chrome would be
       left-anchored inside MainScreen's padding. A concrete width lets the
       screen actually centre it. */
    MainScreen {
        align: center middle;
        padding: 1 2;
    }

    #chrome-outer {
        width: 100%;
        height: auto;
        align: center top;
    }

    #chrome {
        width: 100;
        height: auto;
        align: center middle;
    }

    /* --- chrome rows: logo, tagline, phase body, shortcuts footer -------- */
    #logo-row {
        width: 100%;
        height: 3;
        content-align: center top;
        align: center top;
    }

    #tagline-row {
        width: 100%;
        height: 2;
        content-align: center top;
        align: center top;
        margin-top: 1;
    }

    /* Phase body sits between the tagline and the shortcuts, always centred. */
    #phase-body {
        width: 100%;
        height: auto;
        min-height: 5;
        align: center middle;
        margin-top: 2;
    }

    /* Shortcuts flow naturally under the body — no ``dock: bottom`` so the
       row moves with the body when the body's height changes phase-to-phase. */
    #shortcuts-row {
        width: 100%;
        height: 1;
        content-align: center middle;
        margin-top: 2;
    }

    .subhint {
        color: $text-muted;
        text-style: dim;
        margin-top: 1;
        width: 100%;
        content-align: center top;
    }

    .subhint.-warning {
        color: $warning;
    }

    .placeholder {
        color: $text-muted;
    }

    /* --- input phase: framed input centred, then optional sub-hint ------- */
    .input-body {
        width: 100%;
        height: auto;
        align: center top;
    }

    /* --- picking phase: two-column body (title/meta left, panel right) --- */
    #picking-body {
        width: 100%;
        max-width: 96;
        height: auto;
        layout: horizontal;
    }
    #picking-left {
        width: 1fr;
        min-width: 30;
        padding: 1 3 1 0;
        height: auto;
    }
    #picking-left .title {
        color: $primary;
        text-style: bold;
        width: 100%;
    }
    #picking-left .meta {
        color: $text-muted;
        text-style: dim;
        margin-top: 1;
        width: 100%;
    }
    #picking-right {
        width: 42;
        height: auto;
    }

    /* --- error phase ------------------------------------------------------ */
    #error-body {
        width: 100%;
        max-width: 72;
        height: auto;
        align: center middle;
    }
    #error-body .error-message {
        color: $primary;
        text-style: bold;
        width: 100%;
        content-align: center middle;
    }

    /* --- downloading phase ------------------------------------------------ */
    #downloading-body {
        width: 100%;
        max-width: 72;
        height: auto;
        align: center middle;
    }
    #downloading-body .header {
        color: $text-muted;
        text-style: dim;
        height: 1;
        margin-bottom: 1;
        width: 100%;
        content-align: center middle;
    }

    /* --- done phase ------------------------------------------------------- */
    #done-body {
        width: 100%;
        max-width: 72;
        height: auto;
        align: center middle;
    }
    #done-body .header {
        color: $primary;
        text-style: bold;
        height: 1;
        width: 100%;
        content-align: center middle;
    }
    #done-body .path {
        color: $foreground;
        margin-top: 1;
        margin-bottom: 1;
        height: 1;
        width: 100%;
        content-align: center middle;
    }
    #done-button {
        border: round $primary;
        padding: 0 3;
        width: auto;
        height: 3;
        color: $primary;
        text-style: bold;
        content-align: center middle;
    }
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "cancel_or_back", "cancel / back", show=False),
        # Enter on the screen: needed for phases with no focused input
        # (error / done). SiphonTextInput handles its own enter when focused.
        Binding("enter", "submit_current", "submit", show=False, priority=False),
        # ^r opens the searchable history modal.
        Binding("ctrl+r", "open_history", "history", show=False),
    ]

    phase: reactive[Phase] = reactive(InputPhase(), layout=True)
    """The current phase — swaps the body when it changes."""

    history: reactive[list[str]] = reactive(list, layout=False)
    """Persisted URL history, newest-first."""

    def __init__(self, *, initial_url: str | None = None) -> None:
        super().__init__()
        self._initial_url = initial_url
        self._probe_token: CancellationToken | None = None
        self._download_token: CancellationToken | None = None
        # Populated by :meth:`on_choice_selected`; the M5 downloader consumes
        # it to actually fetch the file.
        self._last_choice: DownloadChoice | None = None
        # Set when a background update-check finds a stale package.
        self._update_hint: str | None = None

    # --------------------------------------------------------------- compose
    def compose(self) -> ComposeResult:
        """Yield the shared shell (logo, tagline, phase body, shortcuts).

        The Vertical chrome is wrapped in a horizontal Center so it sits in
        the middle of the terminal even when its sibling ``#shortcuts-row``
        spans full-width. (Textual's ``align: center`` on the parent
        skips alignment when *any* child requests 100% width.)
        """
        with Center(id="chrome-outer"), Vertical(id="chrome"):
            with Center(id="logo-row"):
                yield LogoWidget(id="logo")
            with Center(id="tagline-row"):
                yield TaglineStrip(id="tagline")
            yield Container(id="phase-body")
        yield ShortcutsWidget([], id="shortcuts-row")

    # ------------------------------------------------------------------ mount
    def on_mount(self) -> None:
        """Bootstrap history + jump into the correct opening phase."""
        self.history = history_service.load_history()

        if self._initial_url and is_probably_url(self._initial_url):
            platform = detect_platform(self._initial_url)
            self.phase = ProbingPhase(url=self._initial_url, platform=platform)
            self._probe_token = CancellationToken()
            self.run_worker(self._run_probe(self._initial_url, self._probe_token), exclusive=True)
        else:
            self.phase = InputPhase()
            # Fire-and-forget: ask the OS clipboard if it has a URL to offer.
            self.run_worker(self._probe_clipboard(), exclusive=True)

    async def _probe_clipboard(self) -> None:
        """Fetch the clipboard and, if it holds a URL, update the input phase."""
        url = await read_clipboard()
        if not url:
            return
        # Only inject the suggestion if we're still on a blank input phase —
        # the user may have started typing while we were waiting.
        if isinstance(self.phase, InputPhase) and self.phase.warning is None:
            self.phase = InputPhase(clipboard_url=url)
            # Push it into the widget so ⇥ knows what to autocomplete to.
            try:
                framed = self.query_one(FramedInput)
                framed.input.set_clipboard_suggestion(url)
            except Exception:
                pass

    # --------------------------------------------------------- phase swapping
    async def watch_phase(self, _old: Phase, new: Phase) -> None:
        """Rebuild the phase body every time the phase changes."""
        body = self.query_one("#phase-body", Container)
        await body.remove_children()
        shortcuts = self.query_one(ShortcutsWidget)

        if isinstance(new, InputPhase):
            await self._mount_input_phase(body, new)
            shortcuts.set_hints(self._with_update_hint(self._hints_for_input(new)))
        elif isinstance(new, ProbingPhase):
            await self._mount_probing_phase(body, new)
            shortcuts.set_hints(self._with_update_hint(self._hints_for_probing()))
        elif isinstance(new, PickingPhase):
            await self._mount_picking_phase(body, new)
            shortcuts.set_hints(self._with_update_hint(self._hints_for_picking()))
        elif isinstance(new, DownloadingPhase):
            await self._mount_downloading_phase(body, new)
            shortcuts.set_hints(self._with_update_hint(self._hints_for_downloading()))
        elif isinstance(new, DonePhase):
            await self._mount_done_phase(body, new)
            shortcuts.set_hints(self._with_update_hint(self._hints_for_done()))
        elif isinstance(new, ErrorPhase):
            await self._mount_error_phase(body, new)
            shortcuts.set_hints(self._with_update_hint(self._hints_for_error()))
        # Every Phase variant is handled above — the union is closed.

    # ---------------------------------------------------------- input phase UI
    async def _mount_input_phase(self, body: Container, phase: InputPhase) -> None:
        """Mount the input-phase body: framed input + optional sub-hint."""
        framed = FramedInput(history=self.history, id="framed-input")
        await body.mount(framed)
        subhint = self._subhint_for_input(phase)
        if subhint is not None:
            await body.mount(subhint)

        # Configure immediately post-mount. FramedInput's own compose has
        # already run because we `await`ed the mount above.
        if not framed.is_mounted:
            return
        try:
            inp = framed.input
        except NoMatches:
            return
        inp.focus()
        if phase.clipboard_url:
            inp.set_clipboard_suggestion(phase.clipboard_url)
        if phase.clipboard_accepted and phase.clipboard_url:
            inp.value = phase.clipboard_url
            inp.cursor_position = len(phase.clipboard_url)

    def _subhint_for_input(self, phase: InputPhase) -> Static | None:
        """Render the sub-hint line under the frame if the current phase warrants it."""
        if phase.warning:
            static = Static(f"✗ {phase.warning}", classes="subhint -warning", id="subhint")
            return static
        if phase.clipboard_accepted and phase.clipboard_url:
            return Static(
                "from your clipboard — ↵ to siphon it",
                classes="subhint",
                id="subhint",
            )
        if phase.clipboard_url:
            return Static(
                "link in your clipboard — ⇥ to paste it",
                classes="subhint",
                id="subhint",
            )
        return None

    def _hints_for_input(self, phase: InputPhase) -> list[Hint]:
        hints = [Hint(key="↵", label="siphon", action="submit_current")]
        if self.history:
            hints.append(Hint(key="↑", label="history"))
        hints.extend(
            [
                Hint(key="^c", label="quit", action="quit"),
                Hint(key="^t", label=f"theme:{self.app.theme_mode}", action="cycle_theme"),  # type: ignore[attr-defined]
            ]
        )
        return hints

    # ------------------------------------------------------- probing phase UI
    async def _mount_probing_phase(self, body: Container, phase: ProbingPhase) -> None:
        """Mount the probing body: framed input with dim button + status line."""
        frame = FramedInput(
            title=phase.platform.label,
            history=self.history,
            id="framed-input",
        )
        await body.mount(frame)
        await body.mount(Static(f"⠋ {phase.status}", classes="subhint", id="probing-status"))

        if not frame.is_mounted:
            return
        try:
            inp = frame.input
        except NoMatches:
            return
        frame.set_dim(True)
        inp.value = phase.url

    def _hints_for_probing(self) -> list[Hint]:
        return [
            Hint(key="esc", label="cancel", action="cancel_or_back"),
            Hint(key="^c", label="quit", action="quit"),
            Hint(key="^t", label=f"theme:{self.app.theme_mode}", action="cycle_theme"),  # type: ignore[attr-defined]
        ]

    # -------------------------------------------------------- picking phase UI
    async def _mount_picking_phase(self, body: Container, phase: PickingPhase) -> None:
        """Mount the two-column picker: title + meta on the left, choices on the right."""
        row = Horizontal(id="picking-body")
        await body.mount(row)

        left = Vertical(id="picking-left")
        right = Vertical(id="picking-right")
        await row.mount(left)
        await row.mount(right)

        # Word-wrap the title (yoinks parity — long titles flow across lines
        # rather than getting middle-truncated).
        title_text = phase.title.strip() or "(untitled)"
        await left.mount(Static(title_text, classes="title", id="picking-title", markup=False))
        await left.mount(Static(self._picking_meta(phase), classes="meta", id="picking-meta"))

        panel = Panel(title="Download", id="picking-panel")
        await right.mount(panel)
        choice_list = ChoiceList(phase.choices, id="choice-list")
        await panel.mount(choice_list)

        # Focus the list so ↵ and j/k work immediately.
        self.call_after_refresh(choice_list.focus)

    def _picking_meta(self, phase: PickingPhase) -> str:
        """Return ``▸ YouTube · 3:45 · Uploader`` (parts omitted when unknown)."""
        parts: list[str] = [f"▸ {phase.platform.label}"]
        if phase.duration_s:
            parts.append(format_duration(phase.duration_s))
        if phase.uploader:
            parts.append(phase.uploader)
        return " · ".join(parts)

    def _hints_for_picking(self) -> list[Hint]:
        return [
            Hint(key="↑↓", label="choose"),
            Hint(key="↵", label="siphon", action="submit_current"),
            Hint(key="esc", label="back", action="cancel_or_back"),
            Hint(key="^c", label="quit", action="quit"),
            Hint(key="^t", label=f"theme:{self.app.theme_mode}", action="cycle_theme"),  # type: ignore[attr-defined]
        ]

    # -------------------------------------------------- downloading phase UI
    async def _mount_downloading_phase(self, body: Container, phase: DownloadingPhase) -> None:
        """Mount the three-row status block with a header identifying the video."""
        container = Vertical(id="downloading-body")
        await body.mount(container)
        header = f"{truncate(phase.title, 42)} · {phase.choice.display}"
        await container.mount(Static(header, classes="header", id="downloading-header"))
        await container.mount(DownloadStatusView(id="download-status"))

    def _hints_for_downloading(self) -> list[Hint]:
        return [
            Hint(key="esc", label="cancel", action="cancel_or_back"),
            Hint(key="^c", label="quit", action="quit"),
            Hint(key="^t", label=f"theme:{self.app.theme_mode}", action="cycle_theme"),  # type: ignore[attr-defined]
        ]

    # --------------------------------------------------------- done phase UI
    async def _mount_done_phase(self, body: Container, phase: DonePhase) -> None:
        """Header + shortened path + "siphon another" framed button."""
        container = Vertical(id="done-body")
        await body.mount(container)
        await container.mount(
            Static("✓ siphoned! find your file in:", classes="header", id="done-header")
        )
        short = shorten_path(phase.filepath, max_length=60)
        await container.mount(Static(short, classes="path", id="done-path"))
        await container.mount(Static("↵ siphon another", id="done-button"))

    def _hints_for_done(self) -> list[Hint]:
        return [
            Hint(key="↵", label="siphon another", action="cancel_or_back"),
            Hint(key="^c", label="quit", action="quit"),
            Hint(key="^t", label=f"theme:{self.app.theme_mode}", action="cycle_theme"),  # type: ignore[attr-defined]
        ]

    # ---------------------------------------------------------- error phase UI
    async def _mount_error_phase(self, body: Container, phase: ErrorPhase) -> None:
        """Show a single bold ``✗ <message>`` line."""
        vertical = Vertical(id="error-body")
        await body.mount(vertical)
        await vertical.mount(Static(f"✗ {phase.message}", classes="error-message"))

    def _hints_for_error(self) -> list[Hint]:
        return [
            Hint(key="↵", label="try again", action="cancel_or_back"),
            Hint(key="^c", label="quit", action="quit"),
            Hint(key="^t", label=f"theme:{self.app.theme_mode}", action="cycle_theme"),  # type: ignore[attr-defined]
        ]

    # ---------------------------------------------------------- theme updates
    def update_theme_hint(self, mode: str) -> None:
        """Refresh the footer hints for the current phase (also picks up the update hint)."""
        shortcuts = self.query_one(ShortcutsWidget)
        base: list[Hint]
        if isinstance(self.phase, InputPhase):
            base = self._hints_for_input(self.phase)
        elif isinstance(self.phase, ProbingPhase):
            base = self._hints_for_probing()
        elif isinstance(self.phase, PickingPhase):
            base = self._hints_for_picking()
        elif isinstance(self.phase, DownloadingPhase):
            base = self._hints_for_downloading()
        elif isinstance(self.phase, DonePhase):
            base = self._hints_for_done()
        elif isinstance(self.phase, ErrorPhase):
            base = self._hints_for_error()
        shortcuts.set_hints(self._with_update_hint(base))

    def _with_update_hint(self, hints: list[Hint]) -> list[Hint]:
        """Append the dim update hint if a background check flagged staleness."""
        if not self._update_hint:
            return hints
        return [*hints, Hint(key="⚠", label=self._update_hint)]

    # -------------------------------------------------------- message routing
    def on_submit_requested(self, event: SubmitRequested) -> None:
        """URL submitted from the input field, the button, or the paste heuristic."""
        event.stop()
        url = event.url.strip()
        if not is_probably_url(url):
            self.phase = InputPhase(warning="that doesn't look like a link — paste a full url")
            return

        # Persist to history (yoinks records on submit, not on completion).
        self.history = history_service.add_to_history(url, existing=list(self.history))

        platform = detect_platform(url)
        self._probe_token = CancellationToken()
        self.phase = ProbingPhase(url=url, platform=platform, status="warming up…")
        # Launch the real probe. The worker is exclusive so a rapid double-submit
        # cancels the in-flight one before starting a new one.
        self.run_worker(self._run_probe(url, self._probe_token), exclusive=True)

    async def _run_probe(self, url: str, token: CancellationToken) -> None:
        """Coordinate the background probe → picker transition."""
        try:
            info = await probe(url, token)
        except DownloadCancelled:
            return  # user hit Esc; the cancel handler already swapped phases
        except CleanedYtdlpError as exc:
            if token.cancelled:
                return
            self.phase = ErrorPhase(message=exc.user_message)
            return
        except Exception as exc:
            # Defence in depth: any non-Cleaned error we didn't anticipate
            # still funnels into the error phase, so the app doesn't crash.
            if token.cancelled:
                return
            self.phase = ErrorPhase(message=str(exc) or "yt-dlp failed")
            return

        if token.cancelled:
            return

        choices = build_choices(info)
        platform = detect_platform(url)
        title = str(info.get("title") or info.get("id") or url)
        uploader = info.get("uploader") or info.get("channel") or None
        duration_raw = info.get("duration")
        duration_s = int(duration_raw) if isinstance(duration_raw, (int, float)) else None
        self.phase = PickingPhase(
            url=url,
            platform=platform,
            title=title,
            choices=choices,
            uploader=str(uploader) if uploader else None,
            duration_s=duration_s,
            info=info,
        )

    def on_clipboard_accepted(self, event: ClipboardAccepted) -> None:
        """User pressed ⇥ to take the clipboard suggestion.

        Deliberately does *not* trigger a phase re-mount — the input widget
        already holds the URL and the only visible change is the sub-hint
        text ("link in your clipboard — ⇥ to paste it" →
        "from your clipboard — ↵ to siphon it"). Swapping just the sub-hint
        keeps the widget tree stable so external references (e.g. in tests)
        remain valid.
        """
        event.stop()
        if not isinstance(self.phase, InputPhase):
            return
        # Mutate the sub-hint in place instead of re-mounting.
        try:
            subhint = self.query_one("#subhint", Static)
        except NoMatches:
            return
        subhint.update("from your clipboard — ↵ to siphon it")
        subhint.remove_class("-warning")

    def on_home_requested(self, event: HomeRequested) -> None:
        """Logo click — reset to input (yoinks F17)."""
        event.stop()
        if isinstance(self.phase, (ProbingPhase,)):
            self.action_cancel_or_back()
        else:
            self.phase = InputPhase()

    def on_cancel_requested(self, event: CancelRequested) -> None:
        """Explicit cancel message — same handling as Esc."""
        event.stop()
        self.action_cancel_or_back()

    def on_choice_selected(self, event: ChoiceSelected) -> None:
        """A row was picked in the ChoiceList — launch the download worker."""
        event.stop()
        current = self.phase
        if not isinstance(current, PickingPhase):
            return

        self._last_choice = event.choice
        self._download_token = CancellationToken()
        self.phase = DownloadingPhase(
            url=current.url,
            title=current.title,
            choice=event.choice,
        )
        settings = get_settings()
        output_dir = settings.download_dir
        override = getattr(self.app, "output_dir_override", None)
        if isinstance(override, str) and override:
            output_dir = Path(override).expanduser()

        self.run_worker(
            run_download(
                url=current.url,
                choice=event.choice,
                title=current.title,
                output_dir=output_dir,
                ffmpeg_location=ffmpeg_discovery.find_ffmpeg(),
                token=self._download_token,
                screen=self,
            ),
            exclusive=True,
        )

    # -------------------------------------------------- download-thread events
    def on_download_progress_tick(self, event: DownloadProgressTick) -> None:
        """Update the status bar in place — no phase re-mount."""
        event.stop()
        if not isinstance(self.phase, DownloadingPhase):
            return
        try:
            view = self.query_one(DownloadStatusView)
        except NoMatches:
            return
        view.apply_progress(event.progress)

    def on_download_processing(self, event: DownloadProcessing) -> None:
        """yt-dlp entered a merger / audio extractor — flip to processing view."""
        event.stop()
        if not isinstance(self.phase, DownloadingPhase):
            return
        try:
            view = self.query_one(DownloadStatusView)
        except NoMatches:
            return
        view.mark_processing()

    def on_download_succeeded(self, event: DownloadSucceeded) -> None:
        """Download finished; switch to the done screen and remember the outcome."""
        event.stop()
        self.phase = DonePhase(filepath=event.filepath, title=event.title)
        # The CLI prints this after alt-screen exit (see :func:`siphon.cli.main`).
        self.app.final_filepath = str(event.filepath)  # type: ignore[attr-defined]

    def on_download_failed(self, event: DownloadFailed) -> None:
        """Download raised a non-cancellation error."""
        event.stop()
        self.phase = ErrorPhase(message=event.message)

    def on_update_hint_available(self, event: UpdateHintAvailable) -> None:
        """Background update check surfaced a hint — append it to the footer."""
        event.stop()
        self._update_hint = event.hint
        # Re-render the current phase's hints to include the update note.
        self.update_theme_hint(self.app.theme_mode)  # type: ignore[attr-defined]

    # -------------------------------------------------------------- actions
    def action_cancel_or_back(self) -> None:
        """Esc handler — behaviour depends on the current phase (yoinks F17).

        * probing → abort, preserve URL in the input field.
        * downloading → abort + clean partials, preserve URL.
        * picking / error / done → reset to blank input.
        * input → no-op.
        """
        if isinstance(self.phase, ProbingPhase):
            preserved = self.phase.url
            if self._probe_token is not None:
                self._probe_token.cancel()
            self.phase = InputPhase()
            self.call_after_refresh(self._prefill_url, preserved)
        elif isinstance(self.phase, DownloadingPhase):
            preserved = self.phase.url
            if self._download_token is not None:
                self._download_token.cancel()
            self.phase = InputPhase()
            self.call_after_refresh(self._prefill_url, preserved)
        elif isinstance(self.phase, InputPhase):
            return  # nothing to cancel
        else:
            self.phase = InputPhase()

    def action_submit_current(self) -> None:
        """Enter key handler — behaviour depends on the current phase."""
        if isinstance(self.phase, PickingPhase):
            # In the picker, ↵ picks the highlighted row.
            try:
                choice_list = self.query_one(ChoiceList)
            except NoMatches:
                return
            choice_list.action_select_cursor()
            return
        if isinstance(self.phase, (DonePhase, ErrorPhase)):
            # Both terminal phases fall through to a fresh input.
            self.phase = InputPhase()
            return
        try:
            framed = self.query_one(FramedInput)
        except NoMatches:
            return
        framed.input.submit_now()

    def action_open_history(self) -> None:
        """Push the searchable history modal (yoinks M7 ^r extra)."""
        entries = history_service.load_entries()
        if not entries:
            return  # nothing recorded yet — silently no-op
        self.app.push_screen(HistoryModal(entries), self._on_history_picked)

    def _on_history_picked(self, url: str | None) -> None:
        """Modal callback: pre-fill the input field with the chosen URL."""
        if not url:
            return
        # Coming back from the modal, we might not be on InputPhase anymore
        # (in principle) — reset so the URL lands where it can be edited.
        if not isinstance(self.phase, InputPhase):
            self.phase = InputPhase()
            self.call_after_refresh(self._prefill_url, url)
            return
        self._prefill_url(url)

    def _prefill_url(self, url: str) -> None:
        """Restore ``url`` into the input field after a phase reset."""
        try:
            framed = self.query_one(FramedInput)
        except Exception:
            return
        framed.input.value = url
        framed.input.cursor_position = len(url)
