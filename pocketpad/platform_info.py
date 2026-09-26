"""Which OS the host is running on, and the platform-specific knobs that follow."""
from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    OS = "win"
elif sys.platform == "darwin":
    OS = "mac"
else:
    OS = "linux"

# Modifier that keeps the app switcher open (Alt+Tab on Windows/Linux, Cmd+Tab on macOS).
SWITCHER_MOD = "win" if OS == "mac" else "alt"   # "win" maps to Cmd on macOS

# Modifier for keyboard shortcuts such as copy/paste.
PRIMARY_MOD = "win" if OS == "mac" else "ctrl"


def session_notes() -> list[str]:
    """Human hints printed at startup for the current platform."""
    notes: list[str] = []
    if OS == "mac":
        notes.append("macOS: allow the terminal (or PocketPad) under System Settings > Privacy & Security > "
                     "Accessibility, otherwise clicks and keys are silently dropped.")
    elif OS == "linux":
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            notes.append("Linux: this is a Wayland session. Pointer injection uses X11 (XTest) and only reaches "
                         "XWayland apps. Log into an X11 session for full control, or wait for the uinput backend.")
        else:
            notes.append("Linux: input goes through X11 XTest. Shortcuts follow GNOME defaults; change them in Settings.")
    return notes
