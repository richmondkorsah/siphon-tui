# Architecture

Siphon is deliberately layered so business logic stays Textual-free and
the UI layer stays yt-dlp-free.

```
┌─────────────────────────────────────────────────────────────┐
│ siphon.ui                                                   │
│   app / screens / widgets / messages / animations           │
│   (Textual only — no yt-dlp / requests / threading)         │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ messages / reactive updates
┌─────────────────────────────────────────────────────────────┐
│ siphon.workers                                              │
│   probe_worker · download_worker                            │
│   (asyncio.to_thread bridges to the sync engine below)      │
└─────────────────────────────────────────────────────────────┘
                          ▲
                          │ sync function calls
┌─────────────────────────────────────────────────────────────┐
│ siphon.engine                                               │
│   probe · downloader · choice_builder · cancellation        │
│   (pure business logic — sync yt-dlp calls, threading)      │
└─────────────────────────────────────────────────────────────┘
                          ▲
┌─────────────────────────────────────────────────────────────┐
│ siphon.services · siphon.models · siphon.utils · config     │
│   clipboard · history · platforms · ffmpeg_discovery        │
│   update_check · Phase dataclasses · format helpers · TOML  │
└─────────────────────────────────────────────────────────────┘
```

## The phase state machine

`MainScreen.phase` is a reactive attribute holding a discriminated union:

```
InputPhase        ← the default; awaits a URL
   ↓ submit
ProbingPhase      ← yt-dlp is extracting metadata
   ↓ success                          ↓ failure
PickingPhase                        ErrorPhase
   ↓ choose
DownloadingPhase  ← real download with progress hooks
   ↓ success                          ↓ failure
DonePhase                           ErrorPhase
```

Every arrow is a phase reassignment on the reactive; `watch_phase` swaps
the body widget in the `#phase-body` container and rebuilds the footer
hints. Progress ticks during `DownloadingPhase` do NOT re-mount — they
update the mounted `DownloadStatusView` in place via
:class:`~siphon.ui.messages.DownloadProgressTick` messages.

## Cancellation

`engine.cancellation.CancellationToken` wraps a `threading.Event` — safe
to set from the asyncio side (via the widget's `on_esc` handler) and
poll from the yt-dlp thread (via the progress hooks). When set, the
next hook call raises `DownloadCancelled`, which unwinds yt-dlp
cleanly; the engine then removes any partial destination files.

## Threading model

- The Textual event loop runs on the main thread.
- Each probe or download runs in its own thread via
  `asyncio.to_thread` (Textual's `run_worker` schedules it).
- Hooks fire from that thread and marshal messages back to the UI via
  `App.call_from_thread(screen.post_message, …)`.

This means we never touch widget state from a background thread; every
UI mutation happens on the main thread in response to a message.

## Persistence

- `config.toml` — Pydantic Settings, TOML source. `SIPHON_*` env vars
  win over the file for one invocation.
- `history.jsonl` — one JSON object per line, newest-first. Loader
  falls back to the M3 `history.json` bare-array format and migrates on
  next write.
- Downloaded files land in `~/Downloads` by default (or the configured
  `download_dir`, or `--output-dir <path>`).
