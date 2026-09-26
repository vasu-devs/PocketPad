"""Named gesture actions and how they are executed on Windows.

The phone decides *which* action a gesture maps to (that is where the
user's settings live). The host only knows how to *perform* an action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .injector import Injector
from .keys import parse_combo


@dataclass(frozen=True)
class Action:
    name: str
    label: str
    run: Callable[[Injector], None]


def _combo(*keys: str) -> Callable[[Injector], None]:
    return lambda inj: inj.key_combo(keys)


def _click(button: str) -> Callable[[Injector], None]:
    def run(inj: Injector) -> None:
        inj.button(button, True)
        inj.button(button, False)
    return run


def _nothing(_: Injector) -> None:
    return None


ACTIONS: dict[str, Action] = {
    a.name: a for a in [
        Action("none", "Nothing", _nothing),
        Action("taskview", "Task view", _combo("win", "tab")),
        Action("showdesktop", "Show desktop", _combo("win", "d")),
        Action("hideothers", "Hide everything except the focused app", _combo("win", "home")),
        Action("switchapp_next", "Switch to next app", _combo("alt", "tab")),
        Action("switchapp_prev", "Switch to previous app", _combo("alt", "shift", "tab")),
        Action("desktop_next", "Next virtual desktop", _combo("ctrl", "win", "right")),
        Action("desktop_prev", "Previous virtual desktop", _combo("ctrl", "win", "left")),
        Action("newdesktop", "New virtual desktop", _combo("ctrl", "win", "d")),
        Action("closedesktop", "Close virtual desktop", _combo("ctrl", "win", "f4")),
        Action("search", "Open search", _combo("win", "s")),
        Action("notifications", "Notification center", _combo("win", "n")),
        Action("quicksettings", "Quick settings", _combo("win", "a")),
        Action("copilot", "Copilot", _combo("win", "c")),
        Action("settings", "Windows settings", _combo("win", "i")),
        Action("explorer", "File Explorer", _combo("win", "e")),
        Action("startmenu", "Start menu", _combo("win",)),
        Action("snap_left", "Snap window left", _combo("win", "left")),
        Action("snap_right", "Snap window right", _combo("win", "right")),
        Action("maximize", "Maximize window", _combo("win", "up")),
        Action("minimize", "Minimize window", _combo("win", "down")),
        Action("closewindow", "Close window", _combo("alt", "f4")),
        Action("back", "Back", _combo("alt", "left")),
        Action("forward", "Forward", _combo("alt", "right")),
        Action("undo", "Undo", _combo("ctrl", "z")),
        Action("redo", "Redo", _combo("ctrl", "y")),
        Action("copy", "Copy", _combo("ctrl", "c")),
        Action("paste", "Paste", _combo("ctrl", "v")),
        Action("volume_up", "Volume up", _combo("volumeup",)),
        Action("volume_down", "Volume down", _combo("volumedown",)),
        Action("mute", "Mute", _combo("volumemute",)),
        Action("playpause", "Play / pause", _combo("playpause",)),
        Action("next_track", "Next track", _combo("nexttrack",)),
        Action("prev_track", "Previous track", _combo("prevtrack",)),
        Action("middleclick", "Middle click", _click("middle")),
        Action("rightclick", "Right click", _click("right")),
        Action("leftclick", "Left click", _click("left")),
        Action("screenshot", "Screenshot (Snipping Tool)", _combo("win", "shift", "s")),
        Action("lock", "Lock PC", _combo("win", "l")),
    ]
}

CUSTOM_PREFIX = "keys:"


def resolve(name: str) -> Callable[[Injector], None]:
    """Return a callable for an action name, or raise KeyError/ValueError.

    `keys:ctrl+shift+t` executes an arbitrary key combination.
    """
    if name.startswith(CUSTOM_PREFIX):
        combo = parse_combo(name[len(CUSTOM_PREFIX):])
        return _combo(*combo)
    return ACTIONS[name].run


def catalog() -> list[dict[str, str]]:
    """Action list sent to the phone so its settings sheet can offer them."""
    return [{"name": a.name, "label": a.label} for a in ACTIONS.values()]
