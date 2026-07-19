# Siphon

> siphon any video. paste. sip. done.

A polished terminal UI for downloading videos and audio from ~1,800 sites
supported by `yt-dlp` — YouTube, X/Twitter, Instagram, Threads, TikTok, Vimeo,
Twitch, Reddit, Facebook, and more. Entirely local, no accounts, no telemetry.

Built with [Textual](https://textual.textualize.io/) and
[Rich](https://rich.readthedocs.io/) on Python 3.13+.

## The golden path

```
paste  →  siphon  →  done
```

Open Siphon, paste a URL into the field, pick a quality, watch a real progress
bar, get your file dropped into `~/Downloads`. Pasting into an empty field
auto-submits — you never need to press Enter.

## Highlights

- **All native.** Uses `yt-dlp`'s Python API directly (no subprocess parsing),
  with `progress_hooks` and `postprocessor_hooks` driving the UI.
- **Cancel-safe.** Escape at any point rolls the phase back and cleans up
  half-written `.part` / `.ytdl` files.
- **Terminal-friendly.** Textual owns alt-screen entry/exit, so a crash
  never leaves your shell in a broken state.
- **Themed.** `auto` / `light` / `dark` cycled with `ctrl+t`, persisted to
  `~/.config/siphon/config.toml`.
- **Searchable history.** `ctrl+r` opens a modal you can fuzzy-filter to
  re-open a URL you siphoned before.
- **Command palette.** `ctrl+p` lists everything Siphon can do.

Continue to [Getting started](getting-started.md) to install it.
