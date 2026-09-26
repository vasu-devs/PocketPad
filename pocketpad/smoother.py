"""Motion smoother: turns bursty network deltas into a steady pointer stream.

Touch samples arrive over Wi-Fi in clumps (a few at once, then a gap). If each
delta is injected the moment it arrives the cursor stutters. The smoother
queues incoming deltas and drains them at a high, regular tick, spreading each
sample across the interval until the next one is expected. Cost: at most one
sample interval of extra latency (about 8 to 16 ms).
"""
from __future__ import annotations

import ctypes
import logging
import sys
import threading
import time

from .injector import Injector

log = logging.getLogger(__name__)

TICK_S = 0.002               # target tick period
MIN_HORIZON_S = 0.006        # never drain faster than this after a sample
MAX_HORIZON_S = 0.030        # never stretch a sample beyond this
IDLE_STOP_S = 0.5            # thread parks when no motion for this long


def _enable_fine_timer() -> None:
    """Windows sleeps at 15.6 ms granularity unless the timer period is lowered."""
    if sys.platform == "win32":
        try:
            ctypes.WinDLL("winmm").timeBeginPeriod(1)
        except OSError:
            pass


class MotionSmoother:
    def __init__(self, injector: Injector) -> None:
        self.injector = injector
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._px = 0.0          # pending (undelivered) delta
        self._py = 0.0
        self._rx = 0.0          # sub-pixel remainder after integer emission
        self._ry = 0.0
        self._interval = 0.012  # EMA of time between samples
        self._last_sample = 0.0
        self._stop = False
        self._thread = threading.Thread(target=self._run, name="pocketpad-smoother", daemon=True)
        _enable_fine_timer()
        self._thread.start()

    # ---- producer side (asyncio thread) --------------------------------
    def push(self, dx: float, dy: float) -> None:
        now = time.perf_counter()
        with self._lock:
            if self._last_sample:
                gap = now - self._last_sample
                if gap < 0.1:
                    self._interval = 0.8 * self._interval + 0.2 * gap
            self._last_sample = now
            self._px += dx
            self._py += dy
        self._wake.set()

    def flush(self) -> None:
        """Deliver everything pending right now (end of gesture)."""
        with self._lock:
            x, y = self._px, self._py
            self._px = self._py = 0.0
        self._emit(x, y)

    def stop(self) -> None:
        self._stop = True
        self._wake.set()

    # ---- consumer side (worker thread) ---------------------------------
    def _emit(self, x: float, y: float) -> None:
        self._rx += x
        self._ry += y
        ix, iy = int(self._rx), int(self._ry)
        self._rx -= ix
        self._ry -= iy
        if ix or iy:
            self.injector.move(ix, iy)

    def _run(self) -> None:
        last = time.perf_counter()
        while not self._stop:
            self._wake.wait(timeout=IDLE_STOP_S)
            self._wake.clear()
            last = time.perf_counter()
            # Active loop until the queue is empty and quiet.
            while not self._stop:
                time.sleep(TICK_S)
                now = time.perf_counter()
                dt, last = now - last, now
                with self._lock:
                    px, py = self._px, self._py
                    if not px and not py:
                        if now - self._last_sample > IDLE_STOP_S:
                            break
                        continue
                    horizon = min(MAX_HORIZON_S, max(MIN_HORIZON_S, self._interval))
                    remaining = horizon - (now - self._last_sample)
                    frac = 1.0 if remaining <= dt else dt / remaining
                    ex, ey = px * frac, py * frac
                    self._px -= ex
                    self._py -= ey
                self._emit(ex, ey)
