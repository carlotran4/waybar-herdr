import json

import pytest

from waybar_herdr import cli
from waybar_herdr.client import HerdrError


class FakeClient:
    def __init__(self, agents=None, error=None):
        self.agents = agents or []
        self.error = error
        self.focused = None

    def list_agents(self):
        if self.error:
            raise self.error
        return self.agents

    def focus_agent(self, target):
        self.focused = target


def test_once_prints_waybar_json(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    client = FakeClient([{"agent_status": "idle", "name": "agent", "pane_id": "p1"}])
    monkeypatch.setattr(cli, "make_client", lambda args: client)
    assert cli.main(["once"]) == 0
    assert json.loads(capsys.readouterr().out)["class"] == "idle"


def test_focus_attention_selects_agent_and_window_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient(
        [
            {"agent_status": "working", "name": "worker", "pane_id": "p1"},
            {"agent_status": "blocked", "name": "reviewer", "pane_id": "p2"},
        ]
    )
    focused = []
    monkeypatch.setattr(
        cli, "focus_herdr_window", lambda backend, title: focused.append((backend, title))
    )
    assert cli.focus_attention(client, "hyprland", "herdr") == 0
    assert client.focused == "reviewer"
    assert focused == [("hyprland", "herdr")]


def test_watch_command_runs_watcher(monkeypatch: pytest.MonkeyPatch) -> None:
    watched = []
    monkeypatch.setattr(cli, "make_client", lambda args: FakeClient())
    monkeypatch.setattr(
        cli,
        "WaybarWatcher",
        lambda client, theme, output: type(
            "Watcher", (), {"watch": lambda self: watched.append(True)}
        )(),
    )
    assert cli.main(["watch"]) == 0
    assert watched == [True]


def test_focus_command_runs_through_main(monkeypatch: pytest.MonkeyPatch) -> None:
    client = FakeClient([{"agent_status": "idle", "name": "agent", "pane_id": "p1"}])
    monkeypatch.setattr(cli, "make_client", lambda args: client)
    monkeypatch.setattr(cli, "focus_herdr_window", lambda backend, title: None)
    assert cli.main(["focus-attention", "--focus-backend", "none"]) == 0
    assert client.focused == "agent"


def test_main_reports_runtime_errors(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(cli, "make_client", lambda args: FakeClient(error=HerdrError("offline")))
    assert cli.main(["once"]) == 1
    assert "offline" in capsys.readouterr().err


def test_focus_attention_requires_an_agent() -> None:
    with pytest.raises(HerdrError, match="no active agents"):
        cli.focus_attention(FakeClient(), "none", "herdr")
