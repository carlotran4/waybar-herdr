import json
import socket
import threading
from pathlib import Path

import pytest

from waybar_herdr.client import HerdrClient, HerdrError, resolve_socket_path


def serve_once(path: Path, responder) -> tuple[threading.Thread, list[dict]]:
    requests: list[dict] = []
    ready = threading.Event()

    def server() -> None:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            listener.listen(1)
            ready.set()
            connection, _ = listener.accept()
            with connection:
                reader = connection.makefile("r", encoding="utf-8")
                request = json.loads(reader.readline())
                requests.append(request)
                for response in responder(request):
                    connection.sendall((json.dumps(response) + "\n").encode())

    thread = threading.Thread(target=server, daemon=True)
    thread.start()
    assert ready.wait(2)
    return thread, requests


def test_socket_path_resolution(tmp_path: Path) -> None:
    env = {"XDG_CONFIG_HOME": str(tmp_path)}
    assert resolve_socket_path(environ=env) == tmp_path / "herdr/herdr.sock"
    assert (
        resolve_socket_path(session="work", environ=env)
        == tmp_path / "herdr/sessions/work/herdr.sock"
    )
    assert resolve_socket_path(session="default", environ=env) == tmp_path / "herdr/herdr.sock"
    assert resolve_socket_path(environ={**env, "HERDR_SESSION": "remote"}) == (
        tmp_path / "herdr/sessions/remote/herdr.sock"
    )
    override = tmp_path / "override.sock"
    assert resolve_socket_path(override, environ=env) == override
    assert resolve_socket_path(environ={"HERDR_SOCKET_PATH": str(override)}) == override
    assert (
        resolve_socket_path(
            session="work",
            environ={"XDG_CONFIG_HOME": str(tmp_path), "HERDR_SOCKET_PATH": str(override)},
        )
        == tmp_path / "herdr/sessions/work/herdr.sock"
    )


def test_request_and_agent_list_over_real_unix_socket(tmp_path: Path) -> None:
    path = tmp_path / "herdr.sock"

    def responder(request: dict):
        yield {
            "id": request["id"],
            "result": {"type": "agent_list", "agents": [{"pane_id": "w1:p1"}]},
        }

    thread, requests = serve_once(path, responder)
    assert HerdrClient(path).list_agents() == [{"pane_id": "w1:p1"}]
    thread.join(2)
    assert requests[0]["method"] == "agent.list"


def test_closed_socket_becomes_herdr_error(tmp_path: Path) -> None:
    path = tmp_path / "herdr.sock"

    def responder(request: dict):
        return iter(())

    thread, _ = serve_once(path, responder)
    with pytest.raises(HerdrError, match="closed"):
        HerdrClient(path).request("agent.list")
    thread.join(2)


def test_api_error_becomes_herdr_error(tmp_path: Path) -> None:
    path = tmp_path / "herdr.sock"

    def responder(request: dict):
        yield {"id": request["id"], "error": {"code": "nope", "message": "not today"}}

    thread, _ = serve_once(path, responder)
    with pytest.raises(HerdrError, match="not today"):
        HerdrClient(path).request("agent.list")
    thread.join(2)


def test_subscription_contains_lifecycle_and_per_pane_status_events(tmp_path: Path) -> None:
    path = tmp_path / "herdr.sock"

    def responder(request: dict):
        yield {"id": request["id"], "result": {"type": "subscription_started"}}
        yield {"event": "pane_agent_status_changed", "data": {"pane_id": "w1:p1"}}

    thread, requests = serve_once(path, responder)
    with HerdrClient(path).subscribe([{"pane_id": "w1:p1"}]) as subscription:
        assert subscription.read_event()["event"] == "pane_agent_status_changed"
    thread.join(2)
    subscriptions = requests[0]["params"]["subscriptions"]
    assert {"type": "pane.agent_status_changed", "pane_id": "w1:p1"} in subscriptions
    assert {"type": "pane.agent_detected"} in subscriptions


def test_agent_list_rejects_non_list_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = HerdrClient(tmp_path / "missing")
    monkeypatch.setattr(client, "request", lambda *args, **kwargs: {"agents": "invalid"})
    assert client.list_agents() == []


def test_subscription_api_error_closes_resources(tmp_path: Path) -> None:
    path = tmp_path / "herdr.sock"

    def responder(request: dict):
        yield {"id": request["id"], "error": {"message": "cannot subscribe"}}

    thread, _ = serve_once(path, responder)
    with pytest.raises(HerdrError, match="cannot subscribe"):
        HerdrClient(path).subscribe([])
    thread.join(2)


def test_focus_agent_uses_agent_focus_method(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    client = HerdrClient(tmp_path / "missing")
    calls = []
    monkeypatch.setattr(
        client, "request", lambda method, params=None: calls.append((method, params)) or {}
    )
    client.focus_agent("reviewer")
    assert calls == [("agent.focus", {"target": "reviewer"})]
