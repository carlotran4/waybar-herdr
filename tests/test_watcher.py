import io
import json

import pytest

from waybar_herdr.render import Theme
from waybar_herdr.watcher import WaybarWatcher


class FakeSubscription:
    def __init__(self, events):
        self.events = iter(events)
        self.closed = False

    def read_event(self):
        return next(self.events, None)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True


class FakeClient:
    def __init__(self, snapshots, events=()):
        self.snapshots = iter(snapshots)
        self.subscription = FakeSubscription(events)
        self.subscribed_agents = None

    def list_agents(self):
        value = next(self.snapshots)
        if isinstance(value, Exception):
            raise value
        return value

    def subscribe(self, agents):
        self.subscribed_agents = agents
        return self.subscription


def make_agent(status: str, pane: str = "w1:p1") -> dict:
    return {"agent_status": status, "pane_id": pane, "name": pane}


def test_connected_cycle_emits_initial_and_event_driven_change() -> None:
    initial = [make_agent("working")]
    changed = [make_agent("blocked", "w1:p2")]
    client = FakeClient([initial, initial, changed], events=[{"event": "changed"}])
    output = io.StringIO()
    watcher = WaybarWatcher(client, Theme.from_environment({}), output)

    watcher._connected_cycle()

    states = [json.loads(line) for line in output.getvalue().splitlines()]
    assert [state["class"] for state in states] == ["working", "blocked"]
    assert client.subscribed_agents == initial
    assert client.subscription.closed


def test_connected_cycle_rebuilds_when_snapshot_races_subscription() -> None:
    initial = [make_agent("working")]
    moved = [make_agent("working", "w1:p2")]
    client = FakeClient([initial, moved])
    watcher = WaybarWatcher(client, Theme.from_environment({}), io.StringIO())
    watcher._connected_cycle()
    assert client.subscription.closed


def test_emit_deduplicates_identical_state() -> None:
    output = io.StringIO()
    watcher = WaybarWatcher(FakeClient([]), Theme.from_environment({}), output)
    state = {"text": "same", "tooltip": "", "class": "idle", "alt": "idle"}
    watcher.emit(state)
    watcher.emit(state)
    assert len(output.getvalue().splitlines()) == 1


def test_backoff_resets_after_a_successful_connection() -> None:
    class StopWatch(RuntimeError):
        pass

    output = io.StringIO()
    watcher = WaybarWatcher(FakeClient([]), Theme.from_environment({}), output)
    attempts = iter(("offline", "connected"))

    def cycle() -> None:
        if next(attempts) == "offline":
            raise FileNotFoundError
        watcher.connected = True
        raise ConnectionError

    delays = []

    def sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) == 2:
            raise StopWatch

    watcher._connected_cycle = cycle
    watcher.sleep = sleep
    with pytest.raises(StopWatch):
        watcher.watch()
    assert delays == [1.0, 1.0]


def test_watch_emits_offline_and_backs_off() -> None:
    class StopWatch(RuntimeError):
        pass

    delays = []

    def stop_after_delay(delay: float) -> None:
        delays.append(delay)
        raise StopWatch

    output = io.StringIO()
    client = FakeClient([FileNotFoundError("offline")])
    watcher = WaybarWatcher(client, Theme.from_environment({}), output, sleep=stop_after_delay)

    with pytest.raises(StopWatch):
        watcher.watch()

    assert json.loads(output.getvalue())["class"] == "offline"
    assert delays == [1.0]
