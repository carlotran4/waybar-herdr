import json
import subprocess
from types import SimpleNamespace

import pytest

from waybar_herdr.focus import FocusError, choose_backend, focus_herdr_window, select_herdr_window


def test_choose_backend_auto_detects_hyprland(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("waybar_herdr.focus.shutil.which", lambda command: "/usr/bin/hyprctl")
    assert choose_backend("auto", {"HYPRLAND_INSTANCE_SIGNATURE": "instance"}) == "hyprland"
    assert choose_backend("auto", {}) == "none"
    assert choose_backend("none", {"HYPRLAND_INSTANCE_SIGNATURE": "instance"}) == "none"


def test_selects_most_recent_matching_mapped_window() -> None:
    clients = [
        {"mapped": True, "title": "herdr work", "focusHistoryID": 3, "address": "old"},
        {"mapped": False, "title": "herdr", "focusHistoryID": 0, "address": "hidden"},
        {"mapped": True, "title": "HERDR", "focusHistoryID": 1, "address": "new"},
        {"mapped": True, "title": "other", "focusHistoryID": 0, "address": "other"},
    ]
    assert select_herdr_window(clients, "herdr")["address"] == "new"
    assert select_herdr_window(clients, "missing") is None


def test_hyprland_focus_dispatches_exact_address(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def run(command, **kwargs):
        calls.append(command)
        if command[:3] == ["hyprctl", "clients", "-j"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    [{"mapped": True, "title": "herdr", "focusHistoryID": 0, "address": "0xabc"}]
                ),
            )
        return SimpleNamespace(returncode=0, stdout="")

    monkeypatch.setattr("waybar_herdr.focus.subprocess.run", run)
    focus_herdr_window("hyprland")
    assert calls[-1] == ["hyprctl", "dispatch", "focuswindow", "address:0xabc"]


def test_hyprland_dispatch_failure_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = iter(
        [
            SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    [{"mapped": True, "title": "herdr", "focusHistoryID": 0, "address": "0xabc"}]
                ),
            ),
            SimpleNamespace(returncode=1, stdout=""),
        ]
    )
    monkeypatch.setattr(
        "waybar_herdr.focus.subprocess.run", lambda *args, **kwargs: next(responses)
    )
    with pytest.raises(FocusError, match="refused"):
        focus_herdr_window("hyprland")


def test_none_backend_is_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "waybar_herdr.focus.subprocess.run",
        lambda *args, **kwargs: pytest.fail("subprocess should not run"),
    )
    focus_herdr_window("none")


def test_focus_errors_are_descriptive(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(FocusError, match="unsupported"):
        focus_herdr_window("sway")

    monkeypatch.setattr(
        "waybar_herdr.focus.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout="[]"),
    )
    with pytest.raises(FocusError, match="no mapped"):
        focus_herdr_window("hyprland")

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, args[0])

    monkeypatch.setattr("waybar_herdr.focus.subprocess.run", fail)
    with pytest.raises(FocusError, match="inspect"):
        focus_herdr_window("hyprland")
