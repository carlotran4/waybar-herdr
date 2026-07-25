from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .client import HerdrClient, HerdrError, resolve_socket_path
from .focus import FocusError, focus_herdr_window
from .render import Theme, render_waybar, select_attention_agent
from .watcher import WaybarWatcher


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="waybar-herdr",
        description="Event-driven Herdr agent status module for Waybar",
    )
    parser.add_argument("--socket", type=Path, help="override the Herdr socket path")
    parser.add_argument("--session", help="use a named Herdr session")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("watch", help="stream Waybar JSON when Herdr state changes")
    subparsers.add_parser("once", help="print the current Waybar JSON once")

    focus = subparsers.add_parser(
        "focus-attention",
        help="focus the highest-priority agent and optionally its Herdr window",
    )
    focus.add_argument(
        "--focus-backend",
        choices=("auto", "hyprland", "none"),
        default=os.environ.get("WAYBAR_HERDR_FOCUS_BACKEND", "auto"),
        help="window focus backend (default: auto)",
    )
    focus.add_argument(
        "--window-title",
        default=os.environ.get("WAYBAR_HERDR_WINDOW_TITLE", "herdr"),
        help="Herdr window title used by the Hyprland backend",
    )
    return parser


def make_client(args: argparse.Namespace) -> HerdrClient:
    return HerdrClient(resolve_socket_path(args.socket, args.session))


def focus_attention(client: HerdrClient, backend: str, window_title: str) -> int:
    agents = client.list_agents()
    agent = select_attention_agent(agents)
    if agent is None:
        raise HerdrError("no active agents")
    target = str(agent.get("name") or agent["pane_id"])
    client.focus_agent(target)
    focus_herdr_window(backend, window_title)
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    client = make_client(args)
    theme = Theme.from_environment()
    try:
        if args.command == "watch":
            WaybarWatcher(client, theme, sys.stdout).watch()
            return 0
        if args.command == "once":
            print(json.dumps(render_waybar(client.list_agents(), theme), ensure_ascii=False))
            return 0
        if args.command == "focus-attention":
            return focus_attention(client, args.focus_backend, args.window_title)
    except (HerdrError, FocusError, ConnectionError, FileNotFoundError, OSError) as error:
        print(f"waybar-herdr: {error}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
