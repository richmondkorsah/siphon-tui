# Roadmap

## Shipped

- [x] **M1** — CLI + Textual app skeleton, ruff/black/mypy/pytest baseline.
- [x] **M2** — Theme system (auto/light/dark), SIPHON logo widget, shared chrome.
- [x] **M3** — Input phase, clipboard support, URL validation, platform detection, history.
- [x] **M4** — Real probe via `yt-dlp.YoutubeDL`, choice building, picker UI.
- [x] **M5** — Download engine with `progress_hooks` + `postprocessor_hooks`, done screen, cancellation cleanup.
- [x] **M6** — Logo intro-flicker + periodic sweep animation, ForgedButton dim/inverse polish, snapshot tests.
- [x] **M7** — Persistent settings, auto-update checker, searchable history modal (`ctrl+r`), command palette (`ctrl+p`), MkDocs site, CI.

## Post-MVP (open)

- [ ] **Concurrent downloads / queue** — needs its own screen mode; won't graft cleanly onto the phase state machine.
- [ ] **Session restore** — pick up an interrupted download from its `.part` file after a crash.
- [ ] **OS notifications** — desktop toast when a download finishes.
- [ ] **Custom TCSS themes** — drop `.tcss` files in `~/.config/siphon/themes/` and pick via `--theme <name>`.
- [ ] **PyPI publish** — deferred until the maintainer is ready to reserve the name.
