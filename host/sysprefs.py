"""Read the user's Windows Precision Touchpad preferences.

Windows keeps them under
HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\PrecisionTouchPad and only
writes a value once the user changes it, so missing values mean "Windows
default". The phone receives this block on connect and mirrors it.

Enumerations below follow the order shown in Settings > Bluetooth & devices >
Touchpad. Values the host cannot map are reported as-is so they show up in logs.
"""
from __future__ import annotations

import logging
import os
import sys
from typing import Any

from .sysprefs_presets import PRESET_MAPS

log = logging.getLogger(__name__)

PTP_KEY = r"Software\Microsoft\Windows\CurrentVersion\PrecisionTouchPad"
MOUSE_KEY = r"Control Panel\Mouse"

# Three / four finger swipe presets (…SlideEnabled).
SLIDE_PRESETS = {0: "nothing", 1: "apps", 2: "desktops", 3: "audio", 4: "custom"}

# Three / four finger tap (…TapEnabled).
TAP_ACTIONS = {
    0: "none", 1: "search", 2: "notifications", 3: "playpause",
    4: "middleclick", 5: "back", 6: "forward", 7: "custom",
}

# Per-direction custom swipe (ThreeFingerUp, FourFingerLeft, ...), "Advanced gestures" list order.
DIRECTION_ACTIONS = {
    0: "none", 1: "switchapp_next", 2: "taskview", 3: "showdesktop", 4: "desktop_next",
    5: "hideothers", 6: "newdesktop", 7: "closedesktop", 8: "forward", 9: "back",
    10: "snap_left", 11: "snap_right", 12: "maximize", 13: "minimize",
    14: "next_track", 15: "prev_track", 16: "volume_up", 17: "volume_down", 18: "mute",
    19: "custom",
}

# Defaults Windows applies when a value is absent.
DEFAULTS: dict[str, Any] = {
    "CursorSpeed": 10, "ScrollDirection": 1, "TapsEnabled": 1, "TwoFingerTapEnabled": 1,
    "TapAndDrag": 1, "ZoomEnabled": 1, "PanEnabled": 1,
    "ThreeFingerSlideEnabled": 1, "FourFingerSlideEnabled": 2,
    "ThreeFingerTapEnabled": 1, "FourFingerTapEnabled": 2,
}


def _read_key(path: str) -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    import winreg
    out: dict[str, Any] = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as k:
            i = 0
            while True:
                try:
                    name, value, _ = winreg.EnumValue(k, i)
                except OSError:
                    break
                out[name] = value
                i += 1
    except OSError:
        pass
    return out


def _flag(v: Any) -> bool:
    # Windows stores "on" as 0xFFFFFFFF (or 1) and "off" as 0.
    try:
        return int(v) != 0
    except (TypeError, ValueError):
        return bool(v)


def _direction_map(raw: dict[str, Any], prefix: str, fallback_preset: str) -> dict[str, str]:
    out = dict(PRESET_MAPS.get(fallback_preset, PRESET_MAPS["nothing"]))
    for d in ("Up", "Down", "Left", "Right"):
        v = raw.get(f"{prefix}{d}")
        if v is None:
            continue
        name = DIRECTION_ACTIONS.get(int(v), f"unknown:{v}")
        if d == "Left" and name == "switchapp_next":
            name = "switchapp_prev"
        if d == "Left" and name == "desktop_next":
            name = "desktop_prev"
        out[d.lower()] = name
    return out


def read_touchpad_prefs() -> dict[str, Any]:
    """Return a JSON-friendly snapshot of the user's touchpad preferences."""
    raw = _read_key(PTP_KEY)
    mouse = _read_key(MOUSE_KEY)
    merged = {**DEFAULTS, **raw}

    def slide(prefix: str) -> dict[str, Any]:
        preset = SLIDE_PRESETS.get(int(merged[f"{prefix}SlideEnabled"]), "custom")
        return {"preset": preset, "map": _direction_map(raw, prefix, preset)}

    prefs = {
        "host": os.environ.get("COMPUTERNAME", "this PC"),
        "present": bool(raw),                       # key exists at all
        "cursorSpeed": int(merged["CursorSpeed"]),  # 1..20, 10 = default
        "natural": _flag(merged["ScrollDirection"]),
        "taps": _flag(merged["TapsEnabled"]),
        "twoFingerTap": _flag(merged["TwoFingerTapEnabled"]),
        "tapAndDrag": _flag(merged["TapAndDrag"]),
        "zoom": _flag(merged["ZoomEnabled"]),
        "pan": _flag(merged["PanEnabled"]),
        "threeTap": TAP_ACTIONS.get(int(merged["ThreeFingerTapEnabled"]), "none"),
        "fourTap": TAP_ACTIONS.get(int(merged["FourFingerTapEnabled"]), "none"),
        "threeSlide": slide("ThreeFinger"),
        "fourSlide": slide("FourFinger"),
        "mouseAccel": _flag(mouse.get("MouseSpeed", 1)),
    }
    log.info("touchpad prefs: speed=%s natural=%s 3f=%s 4f=%s", prefs["cursorSpeed"],
             prefs["natural"], prefs["threeSlide"]["preset"], prefs["fourSlide"]["preset"])
    return prefs
