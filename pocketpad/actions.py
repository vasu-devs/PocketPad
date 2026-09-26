"""Named gesture actions and how they are executed on each platform.

The phone decides *which* action a gesture maps to (that is where the user's
settings live). The host only knows how to *perform* an action here.

Key name "win" means the Windows key on Windows/Linux and Cmd on macOS.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .injector import Injector
from .keys import parse_combo
from .platform_info import OS


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


def _per_os(win: tuple[str, ...] | None, mac: tuple[str, ...] | None, linux: tuple[str, ...] | None):
    """Pick the combo for this OS; None means the action does nothing here."""
    combo = {"win": win, "mac": mac, "linux": linux}[OS]
    return _combo(*combo) if combo else _nothing


# name, label, windows combo, macOS combo, linux (GNOME defaults) combo
_TABLE: list[tuple[str, str, tuple | None, tuple | None, tuple | None]] = [
    ("taskview", "Task view / Mission Control", ("win", "tab"), ("ctrl", "up"), ("win",)),
    ("showdesktop", "Show desktop", ("win", "d"), ("f11",), ("ctrl", "win", "d")),
    ("hideothers", "Hide everything except the focused app", ("win", "home"), ("win", "alt", "h"), None),
    ("switchapp_next", "Switch to next app", ("alt", "tab"), ("win", "tab"), ("alt", "tab")),
    ("switchapp_prev", "Switch to previous app", ("alt", "shift", "tab"), ("win", "shift", "tab"), ("alt", "shift", "tab")),
    ("desktop_next", "Next virtual desktop", ("ctrl", "win", "right"), ("ctrl", "right"), ("win", "pagedown")),
    ("desktop_prev", "Previous virtual desktop", ("ctrl", "win", "left"), ("ctrl", "left"), ("win", "pageup")),
    ("newdesktop", "New virtual desktop", ("ctrl", "win", "d"), None, None),
    ("closedesktop", "Close virtual desktop", ("ctrl", "win", "f4"), None, None),
    ("search", "Open search", ("win", "s"), ("win", "space"), ("win",)),
    ("notifications", "Notification center", ("win", "n"), None, ("win", "v")),
    ("quicksettings", "Quick settings", ("win", "a"), None, None),
    ("copilot", "Copilot / assistant", ("win", "c"), None, None),
    ("settings", "System settings", ("win", "i"), ("win", ","), None),
    ("explorer", "File manager", ("win", "e"), None, None),
    ("startmenu", "Start menu / Launchpad", ("win",), ("win", "space"), ("win",)),
    ("snap_left", "Snap window left", ("win", "left"), None, ("win", "left")),
    ("snap_right", "Snap window right", ("win", "right"), None, ("win", "right")),
    ("maximize", "Maximize window", ("win", "up"), ("ctrl", "win", "f"), ("win", "up")),
    ("minimize", "Minimize window", ("win", "down"), ("win", "m"), ("win", "h")),
    ("closewindow", "Close window", ("alt", "f4"), ("win", "w"), ("alt", "f4")),
    ("back", "Back", ("alt", "left"), ("win", "["), ("alt", "left")),
    ("forward", "Forward", ("alt", "right"), ("win", "]"), ("alt", "right")),
    ("undo", "Undo", ("ctrl", "z"), ("win", "z"), ("ctrl", "z")),
    ("redo", "Redo", ("ctrl", "y"), ("win", "shift", "z"), ("ctrl", "shift", "z")),
    ("copy", "Copy", ("ctrl", "c"), ("win", "c"), ("ctrl", "c")),
    ("paste", "Paste", ("ctrl", "v"), ("win", "v"), ("ctrl", "v")),
    ("volume_up", "Volume up", ("volumeup",), ("volumeup",), ("volumeup",)),
    ("volume_down", "Volume down", ("volumedown",), ("volumedown",), ("volumedown",)),
    ("mute", "Mute", ("volumemute",), ("volumemute",), ("volumemute",)),
    ("playpause", "Play / pause", ("playpause",), ("playpause",), ("playpause",)),
    ("next_track", "Next track", ("nexttrack",), ("nexttrack",), ("nexttrack",)),
    ("prev_track", "Previous track", ("prevtrack",), ("prevtrack",), ("prevtrack",)),
    ("screenshot", "Screenshot", ("win", "shift", "s"), ("win", "shift", "4"), ("printscreen",)),
    ("lock", "Lock screen", ("win", "l"), ("ctrl", "win", "q"), ("win", "l")),
]

ACTIONS: dict[str, Action] = {"none": Action("none", "Nothing", _nothing)}
for _name, _label, _w, _m, _l in _TABLE:
    ACTIONS[_name] = Action(_name, _label, _per_os(_w, _m, _l))
ACTIONS["middleclick"] = Action("middleclick", "Middle click", _click("middle"))
ACTIONS["rightclick"] = Action("rightclick", "Right click", _click("right"))
ACTIONS["leftclick"] = Action("leftclick", "Left click", _click("left"))

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
