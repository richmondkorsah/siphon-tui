# Development

## Setup

```bash
git clone https://github.com/siphon-tui/siphon
cd siphon
uv sync --all-extras
```

## Common commands

```bash
uv run siphon --help              # try the CLI
uv run pytest                     # 300+ tests, most under a second each
uv run pytest tests/unit          # unit tests only (fast — no Textual)
uv run mypy src/siphon            # strict typechecks
uv run ruff check .               # lint
uv run black --check .            # format check
uv run black .                    # format
uv run mkdocs serve               # docs preview at http://127.0.0.1:8000
```

## Layout

```
src/siphon/
├── args.py            CLI parser (yoinks F1)
├── cli.py             entrypoint — dispatches to App.run()
├── config/            paths · constants · Pydantic settings
├── models/            Phase discriminated union · Choice · Platform · Progress · HistoryEntry · Theme
├── services/          clipboard · history · platforms · ffmpeg_discovery · update_check
├── engine/            downloader · probe · choice_builder · cancellation · errors
├── workers/           Textual-async wrappers around engine.*
├── ui/                app · theme · commands · messages · screens · widgets · animations
└── utils/             format helpers
```

## Adding a new phase

1. Add a frozen dataclass to `models/phase.py` and extend the
   `Phase` union.
2. In `ui/screens/main.py`:
   - Add a branch to `watch_phase` that mounts the body widget.
   - Add a `_hints_for_<phase>()` method returning the footer hints.
   - Extend `update_theme_hint` and the enter-key dispatch in
     `action_submit_current` if the phase should respond to those.
3. Add a Pilot test under `tests/ui/`.

## Adding a command palette entry

Edit `ui/commands.py` — construct another `_Command` in
`SiphonCommands._commands()` with a callback factory below.

## Testing

Three tiers:

- **Unit** (`tests/unit/`) — pure, sub-millisecond, no Textual.
- **UI** (`tests/ui/`) — Pilot-driven, uses `App.run_test()`.
- **Live** — manual: `uv run siphon <real-url>`.

Every module gets a matching `test_*.py`; the target is that any
regression fails at least one test.
