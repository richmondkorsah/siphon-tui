"""Tests for :mod:`siphon.services.ffmpeg_discovery`."""

from __future__ import annotations

import pytest

from siphon.services import ffmpeg_discovery


@pytest.fixture(autouse=True)
def _reset() -> None:
    ffmpeg_discovery.reset_cache()
    yield
    ffmpeg_discovery.reset_cache()


class TestDiscovery:
    def test_system_ffmpeg_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # None means "use PATH" — matches yoinks F9 semantics.
        monkeypatch.setattr(ffmpeg_discovery.shutil, "which", lambda _name: "/usr/bin/ffmpeg")
        assert ffmpeg_discovery.find_ffmpeg() is None

    def test_falls_back_to_imageio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ffmpeg_discovery.shutil, "which", lambda _name: None)

        import imageio_ffmpeg  # noqa: PLC0415 — test-scoped dependency

        monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", lambda: "/tmp/fake/ffmpeg")
        assert ffmpeg_discovery.find_ffmpeg() == "/tmp/fake/ffmpeg"

    def test_returns_none_when_both_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(ffmpeg_discovery.shutil, "which", lambda _name: None)

        import imageio_ffmpeg  # noqa: PLC0415

        def boom() -> str:
            raise RuntimeError("no bundled binary")

        monkeypatch.setattr(imageio_ffmpeg, "get_ffmpeg_exe", boom)
        assert ffmpeg_discovery.find_ffmpeg() is None
