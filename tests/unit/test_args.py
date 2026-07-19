"""Tests for :mod:`siphon.args`.

Mirrors the coverage of yoinks' ``src/lib/args.test.ts``: theme parsing in
both spaced and equals forms, positional-count enforcement, unknown-flag
rejection, and the shape of :class:`~siphon.args.ParsedArgs`.
"""

from __future__ import annotations

import pytest

from siphon.args import THEME_MODES, ParsedArgs, parse_args


class TestHelpAndVersion:
    def test_short_help(self) -> None:
        result = parse_args(["-h"])
        assert result.help is True
        assert result.error is None

    def test_long_help(self) -> None:
        result = parse_args(["--help"])
        assert result.help is True

    def test_short_version(self) -> None:
        result = parse_args(["-v"])
        assert result.version is True

    def test_long_version(self) -> None:
        result = parse_args(["--version"])
        assert result.version is True


class TestThemeFlag:
    @pytest.mark.parametrize("mode", THEME_MODES)
    def test_spaced_form(self, mode: str) -> None:
        result = parse_args(["--theme", mode])
        assert result.theme_mode == mode
        assert result.error is None

    @pytest.mark.parametrize("mode", THEME_MODES)
    def test_equals_form(self, mode: str) -> None:
        result = parse_args([f"--theme={mode}"])
        assert result.theme_mode == mode

    def test_spaced_with_url_after(self) -> None:
        result = parse_args(["--theme", "dark", "https://example.com/x"])
        assert result.theme_mode == "dark"
        assert result.initial_url == "https://example.com/x"

    def test_equals_after_positional(self) -> None:
        # yoinks compatibility: `url --theme=dark` must still work.
        result = parse_args(["https://example.com/x", "--theme=dark"])
        assert result.theme_mode == "dark"
        assert result.initial_url == "https://example.com/x"

    def test_missing_value(self) -> None:
        result = parse_args(["--theme"])
        assert result.error is not None
        assert "requires a value" in result.error

    def test_unknown_value(self) -> None:
        result = parse_args(["--theme", "sepia"])
        assert result.error is not None
        assert "sepia" in result.error


class TestOutputDirFlag:
    def test_spaced_form(self, tmp_path: object) -> None:
        result = parse_args(["--output-dir", "/tmp/x"])
        assert result.output_dir == "/tmp/x"

    def test_equals_form(self) -> None:
        result = parse_args(["--output-dir=/tmp/x"])
        assert result.output_dir == "/tmp/x"

    def test_missing_value(self) -> None:
        result = parse_args(["--output-dir"])
        assert result.error is not None


class TestPositionals:
    def test_no_positional(self) -> None:
        result = parse_args([])
        assert result.initial_url is None
        assert result.error is None

    def test_single_positional(self) -> None:
        result = parse_args(["https://youtu.be/xyz"])
        assert result.initial_url == "https://youtu.be/xyz"

    def test_multiple_positionals_rejected(self) -> None:
        result = parse_args(["https://a.example", "https://b.example"])
        assert result.error is not None
        assert "single url" in result.error

    def test_unknown_flag_rejected(self) -> None:
        result = parse_args(["--nope"])
        assert result.error is not None
        assert "--nope" in result.error


class TestParsedArgsShape:
    def test_defaults_are_all_falsy(self) -> None:
        result = ParsedArgs()
        assert result.help is False
        assert result.version is False
        assert result.initial_url is None
        assert result.theme_mode is None
        assert result.output_dir is None
        assert result.error is None
