"""Tests for :mod:`siphon.cli` — help/version output and error dispatch."""

from __future__ import annotations

import pytest

from siphon import __version__
from siphon.cli import main


class TestCliDispatch:
    def test_help_prints_to_stdout_and_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["--help"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert "siphon" in captured.out.lower()
        assert "usage" in captured.out.lower()

    def test_version_prints_to_stdout_and_exits_zero(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = main(["--version"])
        captured = capsys.readouterr()
        assert exit_code == 0
        assert __version__ in captured.out

    def test_unknown_flag_prints_to_stderr_and_exits_one(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        exit_code = main(["--nope"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "siphon:" in captured.err
        assert "--nope" in captured.err
        assert "siphon --help" in captured.err

    def test_multiple_positionals_error(self, capsys: pytest.CaptureFixture[str]) -> None:
        exit_code = main(["https://a", "https://b"])
        captured = capsys.readouterr()
        assert exit_code == 1
        assert "single url" in captured.err
