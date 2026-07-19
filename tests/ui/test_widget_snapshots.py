"""Cross-theme widget rendering checks — verifies that Panel, FramedInput,
LogoWidget, and the full input phase render without crashing under each of
the three theme modes.

We deliberately do NOT snapshot the SVG output; the pixel-perfect SVG has
too many spurious diffs (timestamps in embedded fonts, subtle SGR flips
between Textual versions). Instead these tests assert *structural* and
*style-set* invariants — enough to catch regressions like "dim button
re-splits into gray/white/gray bands" without breaking on every Textual
patch release.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import pyperclip
import pytest

from siphon.config.settings import reset_settings_cache
from siphon.models.theme import ThemeMode
from siphon.ui.app import SiphonApp
from siphon.ui.screens import main as main_mod
from siphon.ui.widgets.framed_input import ForgedButton, FramedInput
from siphon.ui.widgets.logo import LOGO_LINES, LogoWidget
from siphon.ui.widgets.panel import Panel


@pytest.fixture(autouse=True)
def _isolate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_DOWNLOAD_DIR", str(tmp_path / "downloads"))
    for name in list(os.environ):
        if name.startswith("SIPHON_"):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(pyperclip, "paste", lambda: "")

    async def _hang(_url: str, _token: object = None) -> dict:
        await asyncio.sleep(10.0)
        return {}

    monkeypatch.setattr(main_mod, "probe", _hang)
    reset_settings_cache()
    yield
    reset_settings_cache()


THEMES: list[ThemeMode] = ["auto", "light", "dark"]


class TestInputPhaseAcrossThemes:
    @pytest.mark.parametrize("theme", THEMES)
    async def test_mounts_cleanly(self, theme: ThemeMode) -> None:
        app = SiphonApp(theme_mode_override=theme)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            # Chrome widgets are all present.
            assert app.screen.query_one(LogoWidget) is not None
            assert app.screen.query_one(FramedInput) is not None
            # The forged button starts in its bright variant (not dim).
            button = app.screen.query_one(ForgedButton)
            assert button.dim is False

    @pytest.mark.parametrize("theme", THEMES)
    async def test_ctrl_t_cycles_without_crash(self, theme: ThemeMode) -> None:
        """Pressing ^t must not break the layout no matter the starting theme."""
        app = SiphonApp(theme_mode_override=theme)
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            for _ in range(3):
                await pilot.press("ctrl+t")
                await pilot.pause()
            # After a full cycle back, widgets are still there.
            assert app.screen.query_one(LogoWidget) is not None
            assert app.screen.query_one(FramedInput) is not None


class TestForgedButtonInvariants:
    async def test_dim_flip_changes_styles(self) -> None:
        """Toggling dim swaps the ForgedButton to its dim style palette."""
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            framed = app.screen.query_one(FramedInput)
            button = framed.button

            bright_styles = {str(s.style) for s in button.render().spans}
            framed.set_dim(True)
            await pilot.pause()
            dim_styles = {str(s.style) for s in button.render().spans}
            assert bright_styles != dim_styles

    async def test_bright_uses_reverse_dim_does_not(self) -> None:
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            button = app.screen.query_one(ForgedButton)
            bright_styles = [str(s.style) for s in button.render().spans]
            button.dim = True
            dim_styles = [str(s.style) for s in button.render().spans]
            assert any("reverse" in s for s in bright_styles)
            assert not any("reverse" in s for s in dim_styles)


class TestLogoAnimation:
    async def test_animation_off_gives_final_glyphs(self) -> None:
        """With ``animate=False`` we get the locked-in art directly."""
        widget = LogoWidget(animate=False)
        # Not yet mounted — render still returns the final state.
        text = widget.render()
        rendered = str(text).split("\n")
        assert rendered == list(LOGO_LINES)

    async def test_animated_widget_mounts_and_ticks(self) -> None:
        """The animated widget mounts + refreshes without raising."""
        app = SiphonApp()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            logo = app.screen.query_one(LogoWidget)
            # Give the intro a chance to run through a few frames.
            await pilot.pause(0.2)
            # The widget should not have crashed.
            assert logo.is_mounted


class TestPanelRendersInsidePicker:
    async def test_panel_hosts_choice_list(self, monkeypatch: pytest.MonkeyPatch) -> None:
        async def fake_probe(_url: str, _token: object = None) -> dict:
            return {
                "title": "Fake",
                "formats": [
                    {
                        "format_id": "137",
                        "height": 1080,
                        "ext": "mp4",
                        "vcodec": "avc1",
                        "acodec": "none",
                        "tbr": 4500,
                        "filesize": 100_000_000,
                    },
                    {
                        "format_id": "140",
                        "acodec": "aac",
                        "vcodec": "none",
                        "abr": 129,
                        "filesize": 3_400_000,
                    },
                ],
            }

        monkeypatch.setattr(main_mod, "probe", fake_probe)

        from siphon.models.phase import PickingPhase  # noqa: PLC0415

        app = SiphonApp(initial_url="https://youtu.be/xyz")
        async with app.run_test(size=(120, 30)) as pilot:
            for _ in range(30):
                await pilot.pause()
                if isinstance(app.screen.phase, PickingPhase):
                    break
            assert app.screen.query_one(Panel) is not None
