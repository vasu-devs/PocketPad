"""Wire protocol between phone and host, plus the per-connection pointer state.

Messages are small JSON objects with a one-letter type `t`:

    {"t":"m","x":1.5,"y":-0.25}      relative pointer move (already accelerated)
    {"t":"b","b":"left","s":1}        button down (s=1) or up (s=0)
    {"t":"c","b":"left","n":2}        click n times
    {"t":"s","x":0,"y":-12.5}         two-finger scroll in touch pixels
    {"t":"z","d":1}                   zoom step (+1 in, -1 out)
    {"t":"a","a":"taskview"}          named action (see actions.py)
    {"t":"g","g":"switchapp","p":"start"|"step"|"end","d":1|-1}
                                      live Alt+Tab switcher: Alt is held from start to end
    {"t":"k","k":"enter"}             single key press
    {"t":"txt","s":"hello"}           type unicode text
    {"t":"cfg","scroll":1.0,"natural":true,"notched":false}
    {"t":"ping","id":123}             latency probe, answered with pong
"""
from __future__ import annotations

import json
import logging
import math
import struct
from dataclasses import dataclass, field
from typing import Any

from . import actions
from .config import (
    MAX_MESSAGE_BYTES, MAX_MOVE_PX, MAX_TEXT_CHARS, PIXELS_PER_NOTCH,
    WHEEL_DELTA, ErrorCode,
)
from .injector import Injector
from .keys import is_known_key, normalize_key
from .smoother import MotionSmoother

log = logging.getLogger(__name__)

BUTTONS = {"left", "right", "middle"}
BIN_MOVE, BIN_SCROLL, BIN_MOVE_END = 1, 2, 3


class ProtocolError(ValueError):
    pass


def _num(v: Any, lo: float, hi: float) -> float:
    if not isinstance(v, (int, float)) or isinstance(v, bool) or not math.isfinite(v):
        raise ProtocolError("bad number")
    return max(lo, min(hi, float(v)))


@dataclass
class ScrollSettings:
    speed: float = 1.0        # multiplier
    natural: bool = True      # content follows fingers (touchpad style)
    notched: bool = False     # emit only full 120-unit notches


@dataclass
class Session:
    """Pointer/scroll accumulators for one phone connection.

    Relative moves arrive as floats; Windows only accepts integers, so we keep
    the fractional remainder and carry it into the next move. Same for wheel.
    """
    injector: Injector
    scroll: ScrollSettings = field(default_factory=ScrollSettings)
    smoother: MotionSmoother | None = None   # None = inject deltas immediately
    gain: float = 1.0                        # undoes the Windows pointer-speed slider
    _alt_held: bool = False
    _rx: float = 0.0
    _ry: float = 0.0
    _wx: float = 0.0
    _wy: float = 0.0

    # ---- pointer -------------------------------------------------------
    def move(self, dx: float, dy: float) -> None:
        dx *= self.gain
        dy *= self.gain
        if self.smoother is not None:
            self.smoother.push(dx, dy)
            return
        self._rx += dx
        self._ry += dy
        ix, iy = int(self._rx), int(self._ry)   # truncate toward zero
        self._rx -= ix
        self._ry -= iy
        if ix or iy:
            self.injector.move(ix, iy)

    # ---- scroll --------------------------------------------------------
    def scroll_px(self, dx: float, dy: float) -> None:
        sign = 1.0 if self.scroll.natural else -1.0
        units_per_px = WHEEL_DELTA / PIXELS_PER_NOTCH * self.scroll.speed
        self._wx += dx * units_per_px * sign
        self._wy += dy * units_per_px * sign
        quantum = WHEEL_DELTA if self.scroll.notched else 1
        for horizontal, attr in ((False, "_wy"), (True, "_wx")):
            acc = getattr(self, attr)
            steps = int(acc / quantum)
            if steps:
                delta = steps * quantum
                setattr(self, attr, acc - delta)
                # Horizontal wheel: positive = scroll right. Finger moving
                # right with natural scrolling should move content right.
                self.injector.wheel(delta if horizontal else delta, horizontal)

    def reset_scroll(self) -> None:
        self._wx = self._wy = 0.0

    def move_end(self) -> None:
        if self.smoother is not None:
            self.smoother.flush()

    def close(self) -> None:
        if self.smoother is not None:
            self.smoother.stop()
        self._switcher("end", 0)

    # ---- live app switcher -----------------------------------------------
    def _switcher(self, phase: str, d: int) -> None:
        inj = self.injector
        if phase in ("start", "step"):
            if not self._alt_held:
                inj.key("alt", True)
                self._alt_held = True
            inj.key_combo(("tab",) if d >= 0 else ("shift", "tab"))
        elif phase == "end" and self._alt_held:
            inj.key("alt", False)
            self._alt_held = False

    # ---- binary fast path -----------------------------------------------
    # <type:u8><dx:f32><dy:f32> little-endian; type 1 = move, 2 = scroll.
    # A single byte 3 means "move ended".
    def handle_binary(self, data: bytes) -> None:
        if len(data) == 1 and data[0] == BIN_MOVE_END:
            self.move_end()
            return
        if len(data) != 9:
            raise ProtocolError("bad binary frame")
        kind, dx, dy = struct.unpack("<Bff", data)
        if not (math.isfinite(dx) and math.isfinite(dy)):
            raise ProtocolError("bad binary number")
        dx = max(-MAX_MOVE_PX, min(MAX_MOVE_PX, dx))
        dy = max(-MAX_MOVE_PX, min(MAX_MOVE_PX, dy))
        if kind == BIN_MOVE:
            self.move(dx, dy)
        elif kind == BIN_SCROLL:
            self.scroll_px(dx, dy)
        else:
            raise ProtocolError("bad binary type")

    # ---- dispatch ------------------------------------------------------
    def handle_raw(self, raw: str) -> dict | None:
        if len(raw) > MAX_MESSAGE_BYTES:
            raise ProtocolError("message too large")
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ProtocolError("bad json") from e
        if not isinstance(msg, dict):
            raise ProtocolError("not an object")
        return self.handle(msg)

    def handle(self, msg: dict) -> dict | None:
        """Apply one message. Returns an optional reply dict."""
        t = msg.get("t")
        inj = self.injector
        if t == "m":
            self.move(_num(msg.get("x"), -MAX_MOVE_PX, MAX_MOVE_PX),
                      _num(msg.get("y"), -MAX_MOVE_PX, MAX_MOVE_PX))
        elif t == "s":
            self.scroll_px(_num(msg.get("x"), -MAX_MOVE_PX, MAX_MOVE_PX),
                           _num(msg.get("y"), -MAX_MOVE_PX, MAX_MOVE_PX))
        elif t == "se":            # scroll end: drop fractional remainder
            self.reset_scroll()
        elif t == "me":            # move end: deliver whatever the smoother holds
            self.move_end()
        elif t == "b":
            b = msg.get("b")
            if b not in BUTTONS:
                raise ProtocolError("bad button")
            inj.button(b, bool(msg.get("s")))
        elif t == "c":
            b = msg.get("b")
            if b not in BUTTONS:
                raise ProtocolError("bad button")
            n = int(_num(msg.get("n", 1), 1, 3))
            for _ in range(n):
                inj.button(b, True)
                inj.button(b, False)
        elif t == "z":
            d = int(_num(msg.get("d"), -1, 1))
            if d:
                inj.key("ctrl", True)
                try:
                    inj.wheel(WHEEL_DELTA * d)
                finally:
                    inj.key("ctrl", False)
        elif t == "a":
            name = msg.get("a")
            if not isinstance(name, str) or len(name) > 64:
                raise ProtocolError("bad action")
            try:
                fn = actions.resolve(name)
            except (KeyError, ValueError) as e:
                log.warning("%s unknown action %r", ErrorCode.UNKNOWN_ACTION, name)
                raise ProtocolError("unknown action") from e
            fn(inj)
        elif t == "g":
            if msg.get("g") != "switchapp" or msg.get("p") not in ("start", "step", "end"):
                raise ProtocolError("bad gesture")
            self._switcher(msg["p"], int(_num(msg.get("d", 1), -1, 1)))
        elif t == "k":
            k = msg.get("k")
            if not isinstance(k, str) or not is_known_key(k):
                raise ProtocolError("bad key")
            inj.key_combo((normalize_key(k),))
        elif t == "txt":
            s = msg.get("s")
            if not isinstance(s, str):
                raise ProtocolError("bad text")
            if s:
                inj.type_text(s[:MAX_TEXT_CHARS])
        elif t == "cfg":
            if "scroll" in msg:
                self.scroll.speed = _num(msg["scroll"], 0.1, 10.0)
            if "natural" in msg:
                self.scroll.natural = bool(msg["natural"])
            if "notched" in msg:
                self.scroll.notched = bool(msg["notched"])
        elif t == "ping":
            return {"t": "pong", "id": msg.get("id")}
        else:
            raise ProtocolError(f"unknown type {t!r}")
        return None
