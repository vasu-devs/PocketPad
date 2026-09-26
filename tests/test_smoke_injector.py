"""Real-injector smoke test. Runs only when POCKETPAD_SMOKE=1 (CI does this on
Windows, macOS and Linux under Xvfb) because it moves the actual pointer."""
import os
import platform
import time

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("POCKETPAD_SMOKE") != "1", reason="set POCKETPAD_SMOKE=1 to move the real pointer")


def _pointer():
    if platform.system() == "Windows":
        import ctypes
        from ctypes import wintypes

        class P(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]
        p = P()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(p))
        return p.x, p.y
    from pynput import mouse
    return mouse.Controller().position


def test_real_injector_moves_pointer():
    from pocketpad.protocol import Session
    if platform.system() == "Windows":
        from pocketpad.input_win import WindowsInjector as Inj
    else:
        from pocketpad.input_pynput import PynputInjector as Inj
    inj = Inj()
    s = Session(inj)
    if platform.system() != "Windows":
        from pynput import mouse
        mouse.Controller().position = (200, 200)
        time.sleep(0.05)
    before = _pointer()
    for _ in range(10):
        s.handle({"t": "m", "x": 5, "y": 3})
    time.sleep(0.1)
    after = _pointer()
    moved = (after[0] - before[0], after[1] - before[1])
    if platform.system() == "Darwin" and moved == (0, 0):
        pytest.skip("macOS runner has no Accessibility permission for synthetic events")
    assert moved[0] > 0 and moved[1] > 0, f"pointer did not move: {before} -> {after}"
    # scroll and keys must not raise
    s.handle({"t": "s", "x": 0, "y": 40})
    s.handle({"t": "a", "a": "none"})
