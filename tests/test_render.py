from pathlib import Path

from waybar_herdr.render import (
    Theme,
    agent_label,
    render_offline,
    render_waybar,
    select_attention_agent,
    shorten_path,
)


def agent(status: str, name: str, seq: int = 0, cwd: str = "/tmp/project") -> dict:
    return {
        "agent_status": status,
        "name": name,
        "pane_id": f"p-{name}",
        "state_change_seq": seq,
        "cwd": cwd,
    }


def test_render_mixed_states_in_priority_order_and_escapes_markup() -> None:
    theme = Theme.from_environment({})
    state = render_waybar(
        [
            agent("idle", "idle-agent"),
            agent("working", "work<&>"),
            agent("blocked", "blocked-agent"),
            agent("done", "done-agent"),
            agent("unexpected", "unknown-agent"),
        ],
        theme,
    )

    assert state["class"] == "blocked"
    assert state["alt"] == "blocked"
    positions = [state["text"].index(theme.statuses[name].icon) for name in theme.statuses]
    assert positions == sorted(positions)
    assert "work&lt;&amp;&gt;" in state["tooltip"]
    assert "Unknown" in state["tooltip"]
    assert "Left-click: focus highest-priority agent" in state["tooltip"]


def test_render_empty_and_offline() -> None:
    theme = Theme.from_environment({})
    assert render_waybar([], theme) == {
        "text": "",
        "tooltip": "Herdr — no active agents",
        "class": "idle",
        "alt": "idle",
    }
    assert render_offline(theme)["class"] == "offline"


def test_theme_can_be_configured_with_environment() -> None:
    theme = Theme.from_environment(
        {
            "WAYBAR_HERDR_ICON": "H",
            "WAYBAR_HERDR_BLOCKED_ICON": "B",
            "WAYBAR_HERDR_BLOCKED_COLOR": "#ff0000",
        }
    )
    assert theme.agent_icon == "H"
    assert theme.statuses["blocked"].icon == "B"
    assert theme.statuses["blocked"].color == "#ff0000"


def test_attention_priority_then_most_recent_transition() -> None:
    agents = [
        agent("working", "working", 99),
        agent("blocked", "old-blocked", 2),
        agent("blocked", "new-blocked", 3),
        agent("done", "done", 100),
    ]
    assert select_attention_agent(agents)["name"] == "new-blocked"
    assert select_attention_agent([]) is None


def test_labels_and_paths_have_stable_fallbacks_and_limits() -> None:
    assert agent_label({"display_agent": "Claude"}) == "Claude"
    assert agent_label({"pane_id": "w1:p1"}) == "w1:p1"
    assert agent_label({}) == "agent"
    assert agent_label({"name": "x" * 40}).endswith("…")
    assert shorten_path("/home/test/project", Path("/home/test")) == "~/project"
    long_path = "/home/test/" + "/".join(["very-long"] * 8)
    assert shorten_path(long_path, Path("/home/test")).startswith("…/")
    assert shorten_path(None) == ""
