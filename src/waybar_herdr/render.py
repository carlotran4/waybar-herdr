from __future__ import annotations

import html
import os
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUS_ORDER = ("blocked", "done", "working", "unknown", "idle")
STATUS_PRIORITY = {status: priority for priority, status in enumerate(STATUS_ORDER)}


@dataclass(frozen=True)
class StatusStyle:
    icon: str
    label: str
    color: str


@dataclass(frozen=True)
class Theme:
    agent_icon: str
    statuses: Mapping[str, StatusStyle]

    @classmethod
    def from_environment(cls, environ: Mapping[str, str] | None = None) -> Theme:
        env = os.environ if environ is None else environ
        defaults = {
            "blocked": StatusStyle("󰀦", "Blocked", "#f7768e"),
            "done": StatusStyle("󰄬", "Done", "#9ece6a"),
            "working": StatusStyle("󰔟", "Working", "#7aa2f7"),
            "unknown": StatusStyle("󰘥", "Unknown", "#e0af68"),
            "idle": StatusStyle("󰒲", "Idle", "#565f89"),
        }
        statuses = {
            status: StatusStyle(
                env.get(f"WAYBAR_HERDR_{status.upper()}_ICON", style.icon),
                style.label,
                env.get(f"WAYBAR_HERDR_{status.upper()}_COLOR", style.color),
            )
            for status, style in defaults.items()
        }
        return cls(env.get("WAYBAR_HERDR_ICON", "󰚩"), statuses)


def normalize_status(agent: Mapping[str, Any]) -> str:
    status = str(agent.get("agent_status", "unknown"))
    return status if status in STATUS_PRIORITY else "unknown"


def shorten_path(raw_path: str | None, home: Path | None = None, max_length: int = 46) -> str:
    if not raw_path:
        return ""
    path = raw_path.replace(str(home or Path.home()), "~", 1)
    if len(path) <= max_length:
        return path
    return f"…/{'/'.join(path.split('/')[-2:])}"


def agent_label(agent: Mapping[str, Any], max_length: int = 30) -> str:
    label = (
        agent.get("name")
        or agent.get("display_agent")
        or agent.get("agent")
        or agent.get("pane_id")
        or "agent"
    )
    text = str(label)
    return text if len(text) <= max_length else f"{text[: max_length - 1]}…"


def select_attention_agent(agents: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not agents:
        return None
    return min(
        agents,
        key=lambda agent: (
            STATUS_PRIORITY[normalize_status(agent)],
            -int(agent.get("state_change_seq", 0)),
        ),
    )


def render_waybar(
    agents: list[dict[str, Any]],
    theme: Theme,
    *,
    include_click_hint: bool = True,
) -> dict[str, str]:
    if not agents:
        return {
            "text": "",
            "tooltip": "Herdr — no active agents",
            "class": "idle",
            "alt": "idle",
        }

    counts = Counter(normalize_status(agent) for agent in agents)
    dominant = min(counts, key=STATUS_PRIORITY.__getitem__)
    segments = [
        f'<span foreground="{theme.statuses[status].color}">'
        f"{html.escape(theme.statuses[status].icon)} {counts[status]}</span>"
        for status in STATUS_ORDER
        if counts[status]
    ]
    text = f"{html.escape(theme.agent_icon)}  " + "  ".join(segments)

    sorted_agents = sorted(
        agents,
        key=lambda agent: (
            STATUS_PRIORITY[normalize_status(agent)],
            agent_label(agent).casefold(),
        ),
    )
    tooltip = [f"Herdr — {len(agents)} agent{'s' if len(agents) != 1 else ''}", ""]
    for agent in sorted_agents:
        status = normalize_status(agent)
        style = theme.statuses[status]
        label = html.escape(agent_label(agent))
        cwd = html.escape(shorten_path(agent.get("foreground_cwd") or agent.get("cwd")))
        line = (
            f'<span foreground="{style.color}">{html.escape(style.icon)}</span> '
            f"{style.label:<7}  {label}"
        )
        if cwd:
            line += f"\n           {cwd}"
        tooltip.append(line)
    if include_click_hint:
        tooltip.extend(["", "Left-click: focus highest-priority agent"])

    return {"text": text, "tooltip": "\n".join(tooltip), "class": dominant, "alt": dominant}


def render_offline(theme: Theme) -> dict[str, str]:
    return {
        "text": html.escape(theme.agent_icon),
        "tooltip": "Herdr is offline — waiting to reconnect",
        "class": "offline",
        "alt": "offline",
    }
