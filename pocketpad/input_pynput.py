"""Input injection for macOS and Linux through pynput.

macOS: pynput drives Quartz CGEvents (needs Accessibility permission).
Linux: pynput drives X11 XTest (X11 sessions and XWayland apps).

Wheel deltas arrive in Windows units (120 per notch). Each platform gets a
different quantum so scrolling stays smooth without flooding the event queue.
"""
from __future__ import annotations

import logging
from typing import Iterable

from .config import ErrorCode
from .keys import normalize_key
from .platform_info import OS

log = logging.getLogger(__name__)

# Wheel units per emitted scroll step: macOS steps are small pixel scrolls,
# X11 steps are button 4/5 clicks (coarser, so one third of a notch each).
SCROLL_QUANTUM = 8 if OS == "mac" else 40


def _load():
    try:
        from pynput import keyboard, mouse  # noqa: WPS433 (runtime import: needs a display)
    except Exception as e:  # ImportError or Xlib display errors
        raise RuntimeError(
            "pynput is required on this platform: pip install pynput "
            "(and on Linux, an X11 session)") from e
    return keyboard, mouse


class PynputInjector:
    def __init__(self) -> None:
        keyboard, mouse = _load()
        self._kb = keyboard.Controller()
        self._mouse = mouse.Controller()
        self._Button = mouse.Button
        self._Key = keyboard.Key
        self._KeyCode = keyboard.KeyCode
        self._wx = 0.0
        self._wy = 0.0
        self._keymap = self._build_keymap()

    # ---- key names ------------------------------------------------------
    def _build_keymap(self) -> dict:
        K = self._Key
        m = {
            "ctrl": K.ctrl, "shift": K.shift, "alt": K.alt,
            "win": K.cmd,                      # Cmd on macOS, Super on Linux
            "enter": K.enter, "backspace": K.backspace, "tab": K.tab, "esc": K.esc,
            "space": K.space, "delete": K.delete, "home": K.home, "end": K.end,
            "pageup": K.page_up, "pagedown": K.page_down,
            "left": K.left, "up": K.up, "right": K.right, "down": K.down,
            "capslock": K.caps_lock,
        }
        optional = {
            "insert": "insert", "printscreen": "print_screen",
            "volumeup": "media_volume_up", "volumedown": "media_volume_down",
            "volumemute": "media_volume_mute", "playpause": "media_play_pause",
            "nexttrack": "media_next", "prevtrack": "media_previous",
        }
        for name, attr in optional.items():
            if hasattr(K, attr):
                m[name] = getattr(K, attr)
        for n in range(1, 21):
            if hasattr(K, f"f{n}"):
                m[f"f{n}"] = getattr(K, f"f{n}")
        return m

    def _key(self, name: str):
        n = normalize_key(name)
        if n in self._keymap:
            return self._keymap[n]
        if len(n) == 1:
            return self._KeyCode.from_char(n)
        raise KeyError(n)

    # ---- Injector interface ----------------------------------------------
    def move(self, dx: int, dy: int) -> None:
        try:
            self._mouse.move(dx, dy)
        except Exception as e:
            log.error("%s move failed: %s", ErrorCode.INJECT_FAIL, e)

    def button(self, button: str, down: bool) -> None:
        b = {"left": self._Button.left, "right": self._Button.right, "middle": self._Button.middle}[button]
        try:
            (self._mouse.press if down else self._mouse.release)(b)
        except Exception as e:
            log.error("%s button failed: %s", ErrorCode.INJECT_FAIL, e)

    def wheel(self, delta: int, horizontal: bool = False) -> None:
        # Accumulate to whole platform steps; positive delta = up / right like Windows.
        if horizontal:
            self._wx += delta
            steps = int(self._wx / SCROLL_QUANTUM)
            if steps:
                self._wx -= steps * SCROLL_QUANTUM
                self._scroll(steps, 0)
        else:
            self._wy += delta
            steps = int(self._wy / SCROLL_QUANTUM)
            if steps:
                self._wy -= steps * SCROLL_QUANTUM
                self._scroll(0, steps)

    def _scroll(self, dx: int, dy: int) -> None:
        try:
            self._mouse.scroll(dx, dy)
        except Exception as e:
            log.error("%s scroll failed: %s", ErrorCode.INJECT_FAIL, e)

    def key(self, key: str, down: bool) -> None:
        try:
            k = self._key(key)
            (self._kb.press if down else self._kb.release)(k)
        except Exception as e:
            log.error("%s key failed (%s): %s", ErrorCode.INJECT_FAIL, key, e)

    def key_combo(self, keys: Iterable[str]) -> None:
        names = list(keys)
        pressed = []
        try:
            for n in names:
                k = self._key(n)
                self._kb.press(k)
                pressed.append(k)
        except Exception as e:
            log.error("%s combo failed (%s): %s", ErrorCode.INJECT_FAIL, "+".join(names), e)
        finally:
            for k in reversed(pressed):
                try:
                    self._kb.release(k)
                except Exception:
                    pass

    def type_text(self, text: str) -> None:
        try:
            self._kb.type(text)
        except Exception as e:
            log.error("%s type failed: %s", ErrorCode.INJECT_FAIL, e)
