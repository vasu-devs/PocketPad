"""Temporarily switch off Windows "Enhance pointer precision" while the host runs.

Injected relative moves go through the same mouse acceleration as a real
mouse. A touchpad's curve is applied by the touchpad driver instead, so
stacking both makes PocketPad feel twitchy. SystemParametersInfo with
fWinIni=0 changes the live setting only; the registry is untouched and the
original values are restored on exit.
"""
from __future__ import annotations

import ctypes
import logging
import sys

log = logging.getLogger(__name__)

SPI_GETMOUSE = 0x0003
SPI_SETMOUSE = 0x0004
SPI_GETMOUSESPEED = 0x0070

# Windows pointer-speed slider (1..20) to the multiplier it applies to relative moves.
POINTER_SPEED_MULT = {
    1: 0.1, 2: 0.2, 3: 0.3, 4: 0.4, 5: 0.5, 6: 0.6, 7: 0.7, 8: 0.8, 9: 0.9, 10: 1.0,
    11: 1.25, 12: 1.5, 13: 1.75, 14: 2.0, 15: 2.25, 16: 2.5, 17: 2.75, 18: 3.0, 19: 3.25, 20: 3.5,
}


def pointer_multiplier() -> float:
    """Multiplier Windows applies to injected relative motion right now."""
    if sys.platform != "win32":
        return 1.0
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    speed = ctypes.c_int(10)
    if not user32.SystemParametersInfoW(SPI_GETMOUSESPEED, 0, ctypes.byref(speed), 0):
        return 1.0
    return POINTER_SPEED_MULT.get(speed.value, 1.0)


class MouseAccelGuard:
    def __init__(self) -> None:
        self._saved: list[int] | None = None

    def disable(self) -> bool:
        if sys.platform != "win32":
            return False
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        arr = (ctypes.c_int * 3)()
        if not user32.SystemParametersInfoW(SPI_GETMOUSE, 0, arr, 0):
            log.warning("could not read mouse acceleration settings")
            return False
        self._saved = list(arr)
        if self._saved[2] == 0:
            return False  # already off
        off = (ctypes.c_int * 3)(0, 0, 0)
        if not user32.SystemParametersInfoW(SPI_SETMOUSE, 0, off, 0):
            log.warning("could not change mouse acceleration settings")
            self._saved = None
            return False
        log.info("Enhance pointer precision paused while PocketPad runs")
        return True

    def restore(self) -> None:
        if self._saved is None or sys.platform != "win32":
            return
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        arr = (ctypes.c_int * 3)(*self._saved)
        user32.SystemParametersInfoW(SPI_SETMOUSE, 0, arr, 0)
        log.info("mouse acceleration restored")
        self._saved = None
