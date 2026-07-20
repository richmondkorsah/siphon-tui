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
- **Terminal-friendly.** Textual handles alt-screen enter/exit even on crash.
- **Searchable history.** `ctrl+r` opens a fuzzy-filterable list of past URLs.
- **Command palette.** `ctrl+p` lists everything Siphon can do.
- **Themed.** `auto` / `light` / `dark`, cycled with `ctrl+t` and persisted.

## Keys

| Key | Action |
|---|---|
| `enter` | siphon / pick / try again |
| `esc` | cancel or back |
| `tab` | accept the clipboard URL Siphon offered |
| `↑`/`↓` | history / navigate |
| `ctrl+r` | history modal |
| `ctrl+p` | command palette |
| `ctrl+t` | cycle theme |
| `ctrl+c` | quit |

## Docs

Full documentation — install, config, architecture, development — lives at
**[docs/](docs/index.md)** (or `uv run mkdocs serve` for the rendered site).

## Requirements

- Python 3.13 or newer
- `ffmpeg` (optional; falls back to `imageio-ffmpeg` for muxing / mp3 extraction)

`yt-dlp` ships as a Python dependency — no separate binary install.

## Development

```bash
git clone https://github.com/richmondkorsah/siphon-cli
cd siphon-cli
uv sync --all-extras
uv run pytest            # 300+ tests
uv run siphon --help
```

## Fair use

Download only content you have the right to keep. Siphon does nothing more
than drive `yt-dlp` locally on your machine.

## License

MIT.
