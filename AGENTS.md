# AGENTS.md

## Project overview

`waybar-herdr` is a composable, event-driven Waybar custom module for [Herdr](https://herdr.dev/). It renders Herdr's normalized coding-agent states and focuses the highest-priority existing agent pane when clicked.

The project provides Herdr state and behavior. Users own placement, surrounding modules, and most presentation in their Waybar configuration.

## Important invariants

- Do not poll Herdr on a timer. Keep status updates event-driven through `events.subscribe`.
- Do not create terminals, windows, panes, tabs, or agents from click actions.
- `focus-attention` must call Herdr's `agent.focus` for an existing agent.
- Status and priority logic must remain agent-harness agnostic.
- Compositor-specific behavior belongs behind an optional focus backend.
- Runtime code must use only the Python standard library unless a dependency is strongly justified.
- Preserve Python 3.10 compatibility.
- Do not make the package modify a user's Waybar files automatically.
- Do not move machine-specific layout choices, such as fixed margins or the author's island layout, into package defaults.

## Agent priority

The selection order is:

1. `blocked`
2. `done`
3. `working`
4. `unknown`
5. `idle`

Within the same state, the agent with the most recent `state_change_seq` wins.

## Repository map

```text
src/waybar_herdr/
├── cli.py       # CLI parsing and command orchestration
├── client.py    # Herdr Unix-socket client and event subscriptions
├── focus.py     # Optional compositor window-focus backends
├── render.py    # Priority, theme, tooltip, and Waybar JSON rendering
└── watcher.py   # Event-driven lifecycle and reconnect loop

tests/           # Unit and Unix-socket integration tests
examples/        # Copyable Waybar JSONC and CSS snippets
docs/            # README assets
.github/         # CI, release automation, and Dependabot
```

## Herdr API usage

The module currently depends on:

- `agent.list`
- `agent.focus`
- `events.subscribe`

Subscriptions include global pane lifecycle events and per-pane `pane.agent_status_changed` events. Events are treated as invalidation signals: fetch a fresh `agent.list` snapshot rather than attempting to duplicate Herdr's internal rollup model.

When the known set of agent pane IDs changes, rebuild the subscription. Close socket readers and sockets reliably on every path.

Socket resolution precedence is:

1. `--socket`
2. `HERDR_SOCKET_PATH`
3. `--session`
4. `HERDR_SESSION`
5. the default Herdr socket

## Waybar protocol

`watch` is a long-running process. It writes one compact JSON object per line and flushes immediately. Waybar consumes these fields:

- `text`
- `tooltip`
- `class`
- `alt`

Avoid emitting duplicate states. If Herdr disconnects, emit the offline state once and reconnect with bounded exponential backoff.

Pango markup inserted into `text` or `tooltip` must escape all agent-provided labels and paths.

## Focus behavior

`focus-attention` first selects and focuses an existing Herdr agent. Window raising is separate:

- `none`: focus only inside Herdr
- `hyprland`: focus an existing mapped Herdr window with `hyprctl`
- `auto`: use Hyprland when detected, otherwise behave like `none`

A focus backend must never fall back to launching a terminal. New compositor support should be isolated in `focus.py` and covered by tests.

## Development setup

```bash
uv sync --dev
```

Run the complete local validation suite:

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=waybar_herdr --cov-report=term-missing
uv build
uvx twine check dist/*
```

Coverage must remain at or above 90%. Test behavioral changes at the narrowest useful seam, and include a regression test for bug fixes.

To test against a running local Herdr instance:

```bash
uv run waybar-herdr once | jq

timeout 2 uv run waybar-herdr watch
```

When testing focus behavior, compare Hyprland client and Herdr pane counts before and after. They must not increase.

## Testing guidance

- `test_render.py`: state ordering, escaping, labels, paths, and environment customization.
- `test_client.py`: real temporary Unix sockets for wire-format behavior.
- `test_focus.py`: compositor detection and exact focus dispatches with mocked subprocesses.
- `test_watcher.py`: deduplication, subscription races, reconnects, and backoff.
- `test_cli.py`: command routing, output, and error handling.

CI runs on Python 3.10 through 3.13 and validates both tests and distribution artifacts.

## Documentation expectations

Update `README.md`, examples, tests, and `CHANGELOG.md` when public behavior changes. Keep examples composable and neutral. The transparent island layout in the screenshot is illustrative, not a required layout.

Document any newly required Herdr protocol method and the minimum version known to support it.

## Releases

- Package version lives in `pyproject.toml`.
- `waybar_herdr.__version__` reads installed package metadata.
- Tag releases as `vX.Y.Z`.
- The release workflow builds, validates, and attaches the wheel and source distribution to a GitHub release.
- Do not publish to PyPI until trusted publishing has been configured and explicitly approved.

## Local dogfooding

The author's machine installs this repository as an editable uv tool and the active Waybar configuration invokes:

```text
waybar-herdr watch
waybar-herdr focus-attention
```

Be careful when changing CLI compatibility: it can affect the currently running Waybar immediately after the editable tool or process is restarted. Project code belongs in this repository; personal layout CSS remains in the dotfiles repository.
