# Getting started

## Requirements

- **Python 3.13 or newer.**
- **ffmpeg** (optional). Needed for merging video+audio streams and mp3
  extraction. When it's not on `PATH`, Siphon falls back to the bundled
  `imageio-ffmpeg` binary.

`yt-dlp` itself is bundled as a Python dependency — no separate binary
needed.

## Install

=== "uv (recommended)"

    ```bash
    uv tool install siphon-tui
    ```

=== "pipx"

    ```bash
    pipx install siphon-tui
    ```

=== "pip"

    ```bash
    pip install --user siphon-tui
    ```

## Run it

```bash
siphon                              # opens the TUI
siphon <url>                        # skip input, go straight to probing
siphon --theme dark <url>           # force a theme (auto|light|dark)
siphon --output-dir ~/Videos <url>  # override the download folder
siphon --help
siphon --version
```

## Keybindings

| Key | Action |
|---|---|
| `enter` | siphon the current input / pick the highlighted choice / retry after error |
| `esc` | cancel the current phase (URL preserved when going back from probing / downloading) |
| `tab` | accept the clipboard URL that Siphon offered |
| `↑` / `↓` | history recall in the input field / navigate the picker |
| `j` / `k` | vim-style navigation in the picker |
| `ctrl+r` | open the searchable history modal |
| `ctrl+p` | open the command palette |
| `ctrl+t` | cycle theme (auto → light → dark → auto) |
| `ctrl+c` | quit |

## Files on disk

| Path | What it holds |
|---|---|
| `~/.config/siphon/config.toml` | Persisted settings — theme mode, download dir, update checker toggle. |
| `~/.config/siphon/history.jsonl` | Newest-first, 50-entry cap of past URLs with title / platform / timestamp metadata. |
| `~/Downloads/…` (or your override) | Completed downloads. |

## Config knobs

Every field in `~/.config/siphon/config.toml` can be overridden with an
environment variable prefixed `SIPHON_`, e.g.

```bash
SIPHON_THEME_MODE=dark siphon
SIPHON_DOWNLOAD_DIR=~/Videos siphon
SIPHON_CHECK_UPDATES=false siphon
```

Env vars take precedence over the file for that one invocation.
