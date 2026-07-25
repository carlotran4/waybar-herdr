# Contributing

1. Create a focused branch and keep changes compositor-agnostic unless the feature is isolated behind a backend.
2. Install development tools with `uv sync --dev`.
3. Run `uv run ruff check .`, `uv run ruff format --check .`, and `uv run pytest --cov=waybar_herdr`.
4. Update tests and documentation for user-visible behavior.

Bug reports should include Waybar and Herdr versions, `herdr status`, the module command, and sanitized output from `waybar-herdr once`.
