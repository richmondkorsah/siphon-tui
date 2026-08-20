"""Tests for the subtitle picker + opts merging in :mod:`siphon.engine.choice_builder`."""

from __future__ import annotations

from typing import Any

from siphon.engine.choice_builder import apply_subtitle_opts, build_subtitle_choices
from siphon.models.choice import DownloadChoice, SubtitleChoice


def _sample_choice() -> DownloadChoice:
    return DownloadChoice(
        kind="video",
        label="1080p · mp4",
        ytdlp_opts={
            "format": "bv*[height=1080]+ba/b[height=1080]",
            "merge_output_format": "mp4",
            "postprocessors": [{"key": "FFmpegMetadata", "add_chapters": True}],
        },
        height=1080,
    )


class TestBuildSubtitleChoices:
    def test_none_row_always_first(self) -> None:
        rows = build_subtitle_choices({})
        assert rows[0].kind == "none"

    def test_no_tracks_returns_only_the_none_row(self) -> None:
        assert len(build_subtitle_choices({})) == 1

    def test_manual_langs_sorted_by_popularity_first(self) -> None:
        # Popularity ranking: en (0) < es (2) < de (9) < fr (10). Whatever the
        # input order, the picker should surface the more-common language first.
        info = {"subtitles": {"fr": [{}], "de": [{}], "en": [{}], "es": [{}]}}
        rows = build_subtitle_choices(info)
        codes = [r.lang for r in rows if r.kind == "lang"]
        assert codes == ["en", "es", "de", "fr"]

    def test_unknown_langs_appear_after_popular_ones(self) -> None:
        info = {"subtitles": {"zz": [{}], "en": [{}], "aa": [{}]}}
        rows = build_subtitle_choices(info)
        codes = [r.lang for r in rows if r.kind == "lang"]
        assert codes[0] == "en"  # popular first
        assert codes[1:] == ["aa", "zz"]  # unknowns fall to alphabetical after

    def test_regional_variant_inherits_base_lang_rank(self) -> None:
        # ``en-US`` ranks with ``en``, so it beats ``fr``.
        info = {"subtitles": {"fr": [{}], "en-US": [{}]}}
        rows = build_subtitle_choices(info)
        codes = [r.lang for r in rows if r.kind == "lang"]
        assert codes == ["en-US", "fr"]

    def test_auto_captions_appended_after_manual_and_marked_auto(self) -> None:
        info = {
            "subtitles": {"en": [{}]},
            "automatic_captions": {"es": [{}]},
        }
        rows = build_subtitle_choices(info)
        by_lang = {r.lang: r for r in rows if r.kind == "lang"}
        assert by_lang["en"].auto is False
        assert by_lang["es"].auto is True
        assert "auto" in by_lang["es"].label

    def test_auto_skipped_when_manual_covers_same_lang(self) -> None:
        info = {
            "subtitles": {"en": [{}]},
            "automatic_captions": {"en": [{}]},
        }
        rows = build_subtitle_choices(info)
        assert sum(1 for r in rows if r.lang == "en") == 1

    def test_uses_extractor_name_when_present(self) -> None:
        info = {"subtitles": {"en": [{"name": "English (US)"}]}}
        row = next(r for r in build_subtitle_choices(info) if r.kind == "lang")
        assert "English (US)" in row.label
        assert "(en)" in row.label

    def test_falls_back_to_local_name_table(self) -> None:
        info = {"subtitles": {"pt": [{}]}}
        row = next(r for r in build_subtitle_choices(info) if r.kind == "lang")
        assert "Portuguese" in row.label

    def test_regional_code_uses_base_name(self) -> None:
        info = {"subtitles": {"en-US": [{}]}}
        row = next(r for r in build_subtitle_choices(info) if r.kind == "lang")
        assert "English" in row.label
        assert "(en-US)" in row.label

    def test_unknown_code_falls_back_to_raw(self) -> None:
        info = {"subtitles": {"xx": [{}]}}
        row = next(r for r in build_subtitle_choices(info) if r.kind == "lang")
        assert row.label == "xx"


class TestApplySubtitleOpts:
    def test_none_returns_choice_unchanged(self) -> None:
        choice = _sample_choice()
        result = apply_subtitle_opts(choice, SubtitleChoice(kind="none", label="no subtitles"))
        assert result is choice or result == choice

    def test_manual_lang_sets_writesubtitles_flag(self) -> None:
        result = apply_subtitle_opts(
            _sample_choice(),
            SubtitleChoice(kind="lang", label="English (en)", lang="en", auto=False),
        )
        assert result.ytdlp_opts["writesubtitles"] is True
        assert result.ytdlp_opts["writeautomaticsub"] is False
        assert result.ytdlp_opts["subtitleslangs"] == ["en"]

    def test_auto_lang_sets_writeautomaticsub_flag(self) -> None:
        result = apply_subtitle_opts(
            _sample_choice(),
            SubtitleChoice(kind="lang", label="Spanish (es) · auto", lang="es", auto=True),
        )
        assert result.ytdlp_opts["writesubtitles"] is False
        assert result.ytdlp_opts["writeautomaticsub"] is True
        assert result.ytdlp_opts["subtitleslangs"] == ["es"]

    def test_appends_embed_postprocessor_without_clobbering_existing(self) -> None:
        result = apply_subtitle_opts(
            _sample_choice(),
            SubtitleChoice(kind="lang", label="English (en)", lang="en"),
        )
        pps: list[dict[str, Any]] = result.ytdlp_opts["postprocessors"]
        keys = [pp["key"] for pp in pps]
        assert "FFmpegMetadata" in keys  # original chapter-embedder preserved
        assert "FFmpegEmbedSubtitle" in keys

    def test_original_choice_not_mutated(self) -> None:
        choice = _sample_choice()
        before = dict(choice.ytdlp_opts)
        apply_subtitle_opts(choice, SubtitleChoice(kind="lang", label="English (en)", lang="en"))
        assert choice.ytdlp_opts == before
