from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import TextIO

from .client import HerdrClient, HerdrError
from .render import Theme, render_offline, render_waybar

RECOVERABLE_ERRORS = (ConnectionError, FileNotFoundError, OSError, HerdrError, json.JSONDecodeError)


class WaybarWatcher:
    def __init__(
        self,
        client: HerdrClient,
        theme: Theme,
        output: TextIO,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.theme = theme
        self.output = output
        self.sleep = sleep
        self.previous: str | None = None
        self.connected = False

    def emit(self, state: dict[str, str]) -> None:
        serialized = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        if serialized != self.previous:
            print(serialized, file=self.output, flush=True)
            self.previous = serialized

    def watch(self) -> None:
        backoff = 1.0
        while True:
            self.connected = False
            try:
                self._connected_cycle()
                backoff = 1.0
            except RECOVERABLE_ERRORS:
                if self.connected:
                    backoff = 1.0
                self.emit(render_offline(self.theme))
                self.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    def _connected_cycle(self) -> None:
        agents = self.client.list_agents()
        self.connected = True
        self.emit(render_waybar(agents, self.theme))

        with self.client.subscribe(agents) as subscription:
            refreshed = self.client.list_agents()
            self.emit(render_waybar(refreshed, self.theme))
            subscribed_panes = {agent.get("pane_id") for agent in agents}
            current_panes = {agent.get("pane_id") for agent in refreshed}
            if subscribed_panes != current_panes:
                return

            while subscription.read_event() is not None:
                refreshed = self.client.list_agents()
                self.emit(render_waybar(refreshed, self.theme))
                current_panes = {agent.get("pane_id") for agent in refreshed}
                if current_panes != subscribed_panes:
                    return
            raise HerdrError("Herdr closed the subscription socket")
