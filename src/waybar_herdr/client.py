from __future__ import annotations

import json
import os
import socket
import time
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO


class HerdrError(RuntimeError):
    """Raised when Herdr rejects a request or closes its socket."""


def resolve_socket_path(
    explicit: str | Path | None = None,
    session: str | None = None,
    *,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    if explicit:
        return Path(explicit).expanduser()

    config_home = Path(env.get("XDG_CONFIG_HOME", (home or Path.home()) / ".config"))
    root = config_home / "herdr"
    if session:
        return (
            root / "herdr.sock"
            if session == "default"
            else root / "sessions" / session / "herdr.sock"
        )
    if env.get("HERDR_SOCKET_PATH"):
        return Path(env["HERDR_SOCKET_PATH"]).expanduser()

    selected_session = env.get("HERDR_SESSION")
    if selected_session and selected_session != "default":
        return root / "sessions" / selected_session / "herdr.sock"
    return root / "herdr.sock"


class Subscription:
    def __init__(self, client: socket.socket, reader: TextIO) -> None:
        self.client = client
        self.reader = reader

    def read_event(self) -> dict[str, Any] | None:
        line = self.reader.readline()
        return json.loads(line) if line else None

    def close(self) -> None:
        self.reader.close()
        self.client.close()

    def __enter__(self) -> Subscription:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class HerdrClient:
    EVENT_TYPES = (
        "pane.agent_detected",
        "pane.closed",
        "pane.exited",
        "pane.moved",
    )

    def __init__(self, socket_path: Path, timeout: float = 3.0) -> None:
        self.socket_path = socket_path
        self.timeout = timeout

    def _connect(self) -> socket.socket:
        client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        client.settimeout(self.timeout)
        client.connect(str(self.socket_path))
        return client

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        request_id = f"waybar-herdr:{os.getpid()}:{time.monotonic_ns()}"
        client = self._connect()
        reader = client.makefile("r", encoding="utf-8")
        try:
            payload = {"id": request_id, "method": method, "params": params or {}}
            client.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
            while line := reader.readline():
                response = json.loads(line)
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    error = response["error"]
                    raise HerdrError(error.get("message", "Herdr API error"))
                return response.get("result", {})
            raise HerdrError("Herdr closed the socket")
        finally:
            reader.close()
            client.close()

    def list_agents(self) -> list[dict[str, Any]]:
        result = self.request("agent.list")
        agents = result.get("agents", [])
        return agents if isinstance(agents, list) else []

    def focus_agent(self, target: str) -> None:
        self.request("agent.focus", {"target": target})

    def subscribe(self, agents: list[dict[str, Any]]) -> Subscription:
        subscriptions: list[dict[str, Any]] = [
            {"type": event_type} for event_type in self.EVENT_TYPES
        ]
        subscriptions.extend(
            {"type": "pane.agent_status_changed", "pane_id": agent["pane_id"]}
            for agent in agents
            if agent.get("pane_id")
        )

        client = self._connect()
        reader = client.makefile("r", encoding="utf-8")
        try:
            request_id = f"waybar-herdr-sub:{os.getpid()}:{time.monotonic_ns()}"
            payload = {
                "id": request_id,
                "method": "events.subscribe",
                "params": {"subscriptions": subscriptions},
            }
            client.sendall((json.dumps(payload, separators=(",", ":")) + "\n").encode())
            while line := reader.readline():
                response = json.loads(line)
                if response.get("id") != request_id:
                    continue
                if "error" in response:
                    error = response["error"]
                    raise HerdrError(error.get("message", "Herdr subscription error"))
                client.settimeout(None)
                return Subscription(client, reader)
            raise HerdrError("Herdr closed the subscription socket")
        except Exception:
            reader.close()
            client.close()
            raise
