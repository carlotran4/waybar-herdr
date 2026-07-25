from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Mapping
from typing import Any


class FocusError(RuntimeError):
    """Raised when a requested window focus backend cannot focus Herdr."""


def choose_backend(requested: str, environ: Mapping[str, str] | None = None) -> str:
    if requested != "auto":
        return requested
    env = os.environ if environ is None else environ
    if env.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hyprctl"):
        return "hyprland"
    return "none"


def select_herdr_window(clients: list[dict[str, Any]], title: str) -> dict[str, Any] | None:
    expected = title.casefold()
    candidates = [
        client
        for client in clients
        if client.get("mapped")
        and (
            str(client.get("title", "")).casefold() == expected
            or str(client.get("title", "")).casefold().startswith(f"{expected} ")
        )
    ]
    if not candidates:
        return None

    def focus_rank(client: dict[str, Any]) -> int:
        value = client.get("focusHistoryID")
        return int(value) if isinstance(value, int | str) and str(value).isdigit() else 2**31 - 1

    return min(candidates, key=focus_rank)


def focus_herdr_window(backend: str, title: str = "herdr") -> None:
    selected = choose_backend(backend)
    if selected == "none":
        return
    if selected != "hyprland":
        raise FocusError(f"unsupported focus backend: {selected}")

    try:
        result = subprocess.run(
            ["hyprctl", "clients", "-j"],
            check=True,
            capture_output=True,
            text=True,
        )
        clients = json.loads(result.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        raise FocusError("could not inspect Hyprland windows") from error

    window = select_herdr_window(clients, title)
    if window is None:
        raise FocusError(f"no mapped Herdr window matching {title!r}")

    result = subprocess.run(
        ["hyprctl", "dispatch", "focuswindow", f"address:{window['address']}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode:
        raise FocusError("Hyprland refused to focus the Herdr window")
