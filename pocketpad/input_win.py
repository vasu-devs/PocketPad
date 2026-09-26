"""Windows input injection through user32.SendInput (ctypes, no extra deps).

Scan codes are used for keys so that games and low-level hooks accept them,
and KEYEVENTF_UNICODE is used for free text so any character can be typed.
"""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes
from typing import Iterable

from .config import ErrorCode
from .keys import EXTENDED, VK, normalize_key

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)

INPUT_MOUSE = 0
INPUT_KEYBOARD = 1

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_HWHEEL = 0x1000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

MAPVK_VK_TO_VSC = 0

ULONG_PTR = ctypes.c_size_t


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", ULONG_PTR)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                ("wParamH", wintypes.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


user32.SendInput.argtypes = (wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
user32.SendInput.restype = wintypes.UINT
user32.MapVirtualKeyW.argtypes = (wintypes.UINT, wintypes.UINT)
user32.MapVirtualKeyW.restype = wintypes.UINT

_BUTTON_FLAGS = {
    "left": (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "right": (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}


def _send(inputs: list[INPUT]) -> None:
    if not inputs:
        return
    arr = (INPUT * len(inputs))(*inputs)
    sent = user32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))
    if sent != len(inputs):
        err = ctypes.get_last_error()
        log.error("%s SendInput sent %d/%d (winerr=%d)", ErrorCode.INJECT_FAIL,
                  sent, len(inputs), err)


def _mouse(dx: int = 0, dy: int = 0, data: int = 0, flags: int = 0) -> INPUT:
    inp = INPUT(type=INPUT_MOUSE)
    inp.mi = MOUSEINPUT(dx, dy, ctypes.c_uint32(data & 0xFFFFFFFF).value, flags, 0, 0)
    return inp


def _key_input(name: str, down: bool) -> INPUT:
    vk = VK[name]
    scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)
    flags = KEYEVENTF_SCANCODE
    if name in EXTENDED:
        flags |= KEYEVENTF_EXTENDEDKEY
    if not down:
        flags |= KEYEVENTF_KEYUP
    inp = INPUT(type=INPUT_KEYBOARD)
    # Keep wVk populated too: some apps (and Win+X shortcuts) look at it.
    inp.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return inp


def _unicode_unit(unit: int, down: bool) -> INPUT:
    flags = KEYEVENTF_UNICODE | (0 if down else KEYEVENTF_KEYUP)
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.ki = KEYBDINPUT(0, unit, flags, 0, 0)
    return inp


class WindowsInjector:
    """Real injector. All methods are synchronous and cheap."""

    def move(self, dx: int, dy: int) -> None:
        _send([_mouse(dx, dy, 0, MOUSEEVENTF_MOVE)])

    def button(self, button: str, down: bool) -> None:
        d, u = _BUTTON_FLAGS[button]
        _send([_mouse(flags=d if down else u)])

    def wheel(self, delta: int, horizontal: bool = False) -> None:
        _send([_mouse(data=delta, flags=MOUSEEVENTF_HWHEEL if horizontal else MOUSEEVENTF_WHEEL)])

    def key(self, key: str, down: bool) -> None:
        _send([_key_input(normalize_key(key), down)])

    def key_combo(self, keys: Iterable[str]) -> None:
        names = [normalize_key(k) for k in keys]
        downs = [_key_input(n, True) for n in names]
        ups = [_key_input(n, False) for n in reversed(names)]
        _send(downs + ups)

    def type_text(self, text: str) -> None:
        inputs: list[INPUT] = []
        for ch in text:
            if ch == chr(10):
                inputs += [_key_input("enter", True), _key_input("enter", False)]
                continue
            # KEYEVENTF_UNICODE takes UTF-16 code units; astral characters
            # (emoji) become two units, sent as a surrogate pair.
            units = ch.encode("utf-16-le")
            for i in range(0, len(units), 2):
                unit = int.from_bytes(units[i:i + 2], "little")
                inputs += [_unicode_unit(unit, True), _unicode_unit(unit, False)]
        _send(inputs)
