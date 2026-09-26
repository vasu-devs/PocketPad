"""Cross-platform pieces that can be checked anywhere with fakes."""
import importlib
import sys
import types

import pytest

from pocketpad import actions
from pocketpad.injector import FakeInjector


def test_every_action_resolves_on_every_platform(monkeypatch):
    import pocketpad.platform_info as pi
    original = pi.OS
    try:
        for os_name in ("win", "mac", "linux"):
            pi.OS = os_name
            mod = importlib.reload(actions)
            inj = FakeInjector()
            for entry in mod.catalog():
                mod.resolve(entry["name"])(inj)
            names = {e["name"] for e in mod.catalog()}
            assert {"taskview", "switchapp_next", "copy", "leftclick", "none"} <= names
            # taskview must do something on every platform
            inj2 = FakeInjector(); mod.resolve("taskview")(inj2); assert inj2.calls
    finally:
        pi.OS = original
        importlib.reload(actions)


class _FakeKey:
    def __init__(self, name): self.name = name
    def __repr__(self): return f"Key.{self.name}"


def _fake_pynput(calls):
    """A stand-in for the pynput package that records controller calls."""
    kb = types.ModuleType("pynput.keyboard")
    ms = types.ModuleType("pynput.mouse")

    class Key:  # only the attributes the injector asks for
        pass
    for n in ["ctrl", "shift", "alt", "cmd", "enter", "backspace", "tab", "esc", "space", "delete", "home", "end",
              "page_up", "page_down", "left", "up", "right", "down", "caps_lock", "media_volume_up", "f5"]:
        setattr(Key, n, _FakeKey(n))

    class KeyCode:
        def __init__(self, ch): self.ch = ch
        @staticmethod
        def from_char(c): return KeyCode(c)
        def __repr__(self): return f"'{self.ch}'"

    class KController:
        def press(self, k): calls.append(("kdown", repr(k)))
        def release(self, k): calls.append(("kup", repr(k)))
        def type(self, s): calls.append(("type", s))

    class Button:
        left, right, middle = "left", "right", "middle"

    class MController:
        def move(self, dx, dy): calls.append(("move", dx, dy))
        def press(self, b): calls.append(("down", b))
        def release(self, b): calls.append(("up", b))
        def scroll(self, dx, dy): calls.append(("scroll", dx, dy))

    kb.Key, kb.KeyCode, kb.Controller = Key, KeyCode, KController
    ms.Button, ms.Controller = Button, MController
    pkg = types.ModuleType("pynput")
    pkg.keyboard, pkg.mouse = kb, ms
    return {"pynput": pkg, "pynput.keyboard": kb, "pynput.mouse": ms}


def test_pynput_injector_maps_keys_and_scroll(monkeypatch):
    calls = []
    for name, mod in _fake_pynput(calls).items():
        monkeypatch.setitem(sys.modules, name, mod)
    import pocketpad.input_pynput as ip
    importlib.reload(ip)
    inj = ip.PynputInjector()
    inj.move(3, -2)
    inj.button("right", True); inj.button("right", False)
    inj.key_combo(("win", "shift", "t"))
    inj.key("volumeup", True); inj.key("volumeup", False)
    inj.type_text("hi")
    assert ("move", 3, -2) in calls and ("down", "right") in calls and ("up", "right") in calls
    assert ("kdown", "Key.cmd") in calls and ("kdown", "'t'") in calls
    # release order is reversed
    ups = [c for c in calls if c[0] == "kup"]
    assert ups[0] == ("kup", "'t'") and ups[-1][1] in ("Key.cmd", "Key.media_volume_up")
    assert ("type", "hi") in calls
    # wheel: 120 units = one notch = quantum-sized steps, accumulated
    calls.clear()
    q = ip.SCROLL_QUANTUM
    inj.wheel(q - 1)
    assert calls == []
    inj.wheel(1)
    assert calls == [("scroll", 0, 1)]
    inj.wheel(-3 * q, horizontal=True)
    assert calls[-1] == ("scroll", -3, 0)


def test_posix_prefs_shape(monkeypatch):
    import pocketpad.sysprefs_posix as sp
    monkeypatch.setattr(sp, "_run", lambda cmd: None)
    for os_name in ("mac", "linux"):
        monkeypatch.setattr(sp, "OS", os_name)
        p = sp.read_posix_prefs()
        assert p["cursorSpeed"] == 10 and p["natural"] is True and p["threeSlide"]["map"]["up"] == "taskview"
    monkeypatch.setattr(sp, "OS", "mac")
    monkeypatch.setattr(sp, "_run", lambda cmd: "0" if any("swipescrolldirection" in c for c in cmd) else ("3" if any("scaling" in c for c in cmd) else None))
    p = sp.read_posix_prefs()
    assert p["natural"] is False and p["cursorSpeed"] == 20
