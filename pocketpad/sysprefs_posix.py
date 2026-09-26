"""Touchpad preferences on macOS and Linux (best effort, defaults otherwise).

macOS reads the global scroll direction and tracking speed with `defaults`.
Linux asks GNOME's gsettings; other desktops fall back to defaults.
"""
from __future__ import annotations

import logging
import os
import platform
import subprocess

from .platform_info import OS

log = logging.getLogger(__name__)


def _run(cmd: list[str]) -> str | None:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def _mac() -> dict:
    natural = _run(["defaults", "read", "-g", "com.apple.swipescrolldirection"])
    scaling = _run(["defaults", "read", "-g", "com.apple.trackpad.scaling"])
    tap = _run(["defaults", "read", "com.apple.AppleMultitouchTrackpad", "Clicking"])
    speed = 10
    try:
        # Tracking speed slider is 0..3 (default 0.6875); map onto 1..20.
        speed = int(round(1 + (float(scaling) / 3.0) * 19)) if scaling else 10
    except ValueError:
        pass
    return {
        "natural": natural is None or natural.strip() != "0",
        "cursorSpeed": max(1, min(20, speed)),
        "taps": tap is None or tap.strip() != "0",
        "threeSlidePreset": "apps",
        "fourSlidePreset": "desktops",
    }


def _linux() -> dict:
    natural = _run(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", "natural-scroll"])
    speed_s = _run(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", "speed"])
    tap = _run(["gsettings", "get", "org.gnome.desktop.peripherals.touchpad", "tap-to-click"])
    speed = 10
    try:
        # GNOME speed is -1..1 with 0 the default.
        speed = int(round(10 + float(speed_s) * 9)) if speed_s else 10
    except ValueError:
        pass
    return {
        "natural": natural is None or natural.strip() == "true",
        "cursorSpeed": max(1, min(20, speed)),
        "taps": tap is None or tap.strip() == "true",
        "threeSlidePreset": "apps",
        "fourSlidePreset": "desktops",
    }


def read_posix_prefs() -> dict:
    from .sysprefs_presets import PRESET_MAPS
    base = _mac() if OS == "mac" else _linux()
    prefs = {
        "host": platform.node() or os.environ.get("HOSTNAME", "this computer"),
        "present": True,
        "cursorSpeed": base["cursorSpeed"],
        "natural": base["natural"],
        "taps": base["taps"],
        "twoFingerTap": True,
        "tapAndDrag": True,
        "zoom": True,
        "pan": True,
        "threeTap": "middleclick",
        "fourTap": "none",
        "threeSlide": {"preset": base["threeSlidePreset"], "map": dict(PRESET_MAPS[base["threeSlidePreset"]])},
        "fourSlide": {"preset": base["fourSlidePreset"], "map": dict(PRESET_MAPS[base["fourSlidePreset"]])},
        "mouseAccel": False,
        "os": OS,
    }
    log.info("touchpad prefs (%s): speed=%s natural=%s", OS, prefs["cursorSpeed"], prefs["natural"])
    return prefs
