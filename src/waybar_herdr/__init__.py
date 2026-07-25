"""Event-driven Herdr agent status for Waybar."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("waybar-herdr")
except PackageNotFoundError:  # pragma: no cover - only when imported outside a package install
    __version__ = "0+unknown"
