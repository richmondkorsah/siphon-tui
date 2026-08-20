# Siphon

> siphon any video. paste. sip. done.

A polished terminal UI for downloading videos and audio from ~1,800 sites
supported by `yt-dlp` — YouTube, X/Twitter, Instagram, Threads, TikTok, Vimeo,
Twitch, Reddit, Facebook, and more. Entirely local. No accounts. No telemetry.

Built with [Textual](https://textual.textualize.io/) and
[Rich](https://rich.readthedocs.io/) on Python 3.13+.

```bash
pip install git+https://github.com/richmondkorsah/siphon-tui.git
# or, with uv:
uv tool install git+https://github.com/richmondkorsah/siphon-tui.git

siphon                            # open the TUI
siphon https://youtu.be/…         # skip input, go straight to probing
```

Paste a URL into the field — Siphon auto-submits. Pick a quality
(or `audio only · mp3`), watch a real progress bar, done.

## Highlights

- **All native.** Uses `yt-dlp`'s Python API directly — no subprocess parsing.
- **Cancel-safe.** Escape rolls back any phase and cleans up `.part` files.
- **Resumable retries.** A failed download picks up where it left off on
  retry — no re-probe, no restarting the file from zero.
- **Chapter markers.** Video downloads embed the source's chapters, when the
  site provides them.
- **Subtitle picker.** Pick from available subtitle tracks and embed them
  alongside the video.
- **403-resilient.** A stale signed URL (expired mid-download) triggers one
  automatic re-extract-and-resume, no manual retry needed.
- **Terminal-friendly.** Textual handles alt-screen enter/exit even on crash.
- **Searchable history.** `ctrl+r` opens a fuzzy-filterable list of past URLs.
- **Command palette.** `ctrl+p` lists everything Siphon can do.
- **Themed.** `auto` / `light` / `dark`, cycled with `ctrl+t` and persisted.

## Usage

```bash
siphon                              # opens the TUI
siphon <url>                        # skip input, go straight to probing
siphon --theme dark <url>           # force a theme: auto | light | dark
siphon --output-dir ~/Videos <url>  # override the download folder for this run
siphon --help
siphon --version
```

## Keys

| Key | Action |
|---|---|
| `enter` | siphon / pick / retry (resumes) |
| `esc` | cancel or back |
| `tab` | accept the clipboard URL Siphon offered |
| `↑`/`↓` | history / navigate the picker |
| `j`/`k` | vim-style navigation in the picker |
| `ctrl+r` | history modal |
| `ctrl+p` | command palette |
| `ctrl+t` | cycle theme |
| `ctrl+c` | quit |

## Configuration

Settings persist to `~/.config/siphon/config.toml` (theme mode, download
dir, update-checker toggle) and can be overridden per-invocation with
`SIPHON_`-prefixed env vars:

```bash
SIPHON_THEME_MODE=dark siphon
SIPHON_DOWNLOAD_DIR=~/Videos siphon
SIPHON_CHECK_UPDATES=false siphon
```

URL history lives alongside it at `~/.config/siphon/history.jsonl` (newest
first, capped at 50 entries).

## Docs

Full documentation — install, config, architecture, development — lives at
**[docs/](docs/index.md)** (or `uv run mkdocs serve` for the rendered site).

## Requirements

- Python 3.13 or newer
- `ffmpeg` (optional; falls back to `imageio-ffmpeg` for muxing / mp3 extraction)

`yt-dlp` ships as a Python dependency — no separate binary install.

## Development

```bash
git clone https://github.com/richmondkorsah/siphon-tui.git
cd siphon-tui
uv sync --all-extras
uv run pytest            # 300+ tests
uv run siphon --help
```

## Fair use

Download only content you have the right to keep. Siphon does nothing more
than drive `yt-dlp` locally on your machine.

## License

[PolyForm Noncommercial 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0/).
Free to use, modify, and share for any noncommercial purpose; commercial use
(resale, paid hosting, bundling into a paid product) isn't permitted.
