"""Tests for :mod:`siphon.services.platforms` — URL validation + platform detection."""

from __future__ import annotations

import pytest

from siphon.services.platforms import detect_platform, is_probably_url


class TestIsProbablyUrl:
    @pytest.mark.parametrize(
        "url",
        [
            "https://youtube.com/watch?v=abc",
            "http://example.com",
            "https://x.com/user/status/123",
            "https://youtu.be/xyz",
            "  https://a.b.c  ",  # whitespace trimmed
        ],
    )
    def test_accepts_http_and_https(self, url: str) -> None:
        assert is_probably_url(url) is True

    @pytest.mark.parametrize(
        "value",
        [
            "",
            "   ",
            "youtube.com",
            "//youtube.com",
            "ftp://example.com/file",
            "file:///etc/passwd",
            "javascript:alert(1)",
            "not a url",
            "https://",
            "http://",
        ],
    )
    def test_rejects_non_http_and_malformed(self, value: str) -> None:
        assert is_probably_url(value) is False


class TestDetectPlatform:
    @pytest.mark.parametrize(
        ("url", "expected_key", "expected_label"),
        [
            ("https://youtube.com/watch?v=abc", "youtube", "YouTube"),
            ("https://www.youtube.com/watch?v=abc", "youtube", "YouTube"),
            ("https://youtu.be/xyz", "youtube", "YouTube"),
            ("https://music.youtube.com/watch?v=abc", "youtube", "YouTube Music"),
            ("https://mobile.music.youtube.com/x", "youtube", "YouTube Music"),
            ("https://twitter.com/user/status/1", "twitter", "X"),
            ("https://x.com/user/status/1", "twitter", "X"),
            ("https://mobile.twitter.com/x", "twitter", "X"),
            ("https://www.instagram.com/reel/x", "instagram", "Instagram"),
            ("https://www.threads.net/@user/post/x", "threads", "Threads"),
            ("https://www.threads.com/@user/post/x", "threads", "Threads"),
            ("https://www.tiktok.com/@u/video/1", "tiktok", "TikTok"),
            ("https://vimeo.com/12345", "vimeo", "Vimeo"),
            ("https://www.twitch.tv/videos/1", "twitch", "Twitch"),
            ("https://www.reddit.com/r/x/comments/1", "reddit", "Reddit"),
            ("https://www.facebook.com/watch/?v=1", "facebook", "Facebook"),
            ("https://fb.watch/xyz", "facebook", "Facebook"),
        ],
    )
    def test_known_hosts(self, url: str, expected_key: str, expected_label: str) -> None:
        platform = detect_platform(url)
        assert platform.key == expected_key
        assert platform.label == expected_label

    def test_generic_host_uses_hostname_as_label(self) -> None:
        platform = detect_platform("https://example.com/some/path")
        assert platform.key == "generic"
        assert platform.label == "example.com"

    @pytest.mark.parametrize("url", ["", "  ", "not a url"])
    def test_malformed_urls_become_unknown(self, url: str) -> None:
        platform = detect_platform(url)
        assert platform.key == "unknown"
        assert platform.label == "Unknown site"

    def test_case_insensitive_host_match(self) -> None:
        assert detect_platform("https://YOUTUBE.com/watch?v=abc").key == "youtube"
