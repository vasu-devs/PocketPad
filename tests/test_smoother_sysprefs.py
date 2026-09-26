import struct
import time

import pytest

from host import sysprefs
from host.injector import FakeInjector
from host.protocol import ProtocolError, Session
from host.smoother import MotionSmoother


def test_smoother_delivers_everything_eventually():
    inj = FakeInjector()
    sm = MotionSmoother(inj)
    try:
        for _ in range(20):
            sm.push(3.0, -1.5)
            time.sleep(0.008)
        time.sleep(0.1)
        sm.flush()
        sx = sum(c[1] for c in inj.calls if c[0] == "move")
        sy = sum(c[2] for c in inj.calls if c[0] == "move")
        # A sub-pixel remainder may stay behind; everything else must arrive.
        assert abs(sx - 60) <= 1 and abs(sy + 30) <= 1
        # Spread across several ticks rather than one burst per sample.
        assert len([c for c in inj.calls if c[0] == "move"]) >= 20
    finally:
        sm.stop()


def test_binary_frames():
    inj = FakeInjector()
    s = Session(inj)
    s.handle_binary(struct.pack("<Bff", 1, 4.0, 2.0))
    assert inj.calls == [("move", 4, 2)]
    inj.calls.clear()
    s.handle_binary(struct.pack("<Bff", 2, 0.0, 40.0))
    assert inj.calls == [("wheel", 120, False)]
    s.handle_binary(bytes([3]))  # move end, no smoother: no-op
    with pytest.raises(ProtocolError):
        s.handle_binary(b"\x01\x02")
    with pytest.raises(ProtocolError):
        s.handle_binary(struct.pack("<Bff", 9, 1.0, 1.0))
    with pytest.raises(ProtocolError):
        s.handle_binary(struct.pack("<Bff", 1, float("inf"), 1.0))


def test_session_routes_moves_through_smoother():
    inj = FakeInjector()
    sm = MotionSmoother(inj)
    s = Session(inj, smoother=sm)
    try:
        s.handle({"t": "m", "x": 10, "y": 0})
        s.handle({"t": "me"})
        assert sum(c[1] for c in inj.calls if c[0] == "move") == 10
    finally:
        s.close()


def test_sysprefs_defaults(monkeypatch):
    monkeypatch.setattr(sysprefs, "_read_key", lambda path: {})
    p = sysprefs.read_touchpad_prefs()
    assert p["cursorSpeed"] == 10 and p["natural"] is True
    assert p["threeSlide"]["preset"] == "apps" and p["fourSlide"]["preset"] == "desktops"
    assert p["threeSlide"]["map"]["up"] == "taskview"
    assert p["threeTap"] == "search" and p["fourTap"] == "notifications"


def test_sysprefs_custom(monkeypatch):
    raw = {
        "CursorSpeed": 20, "ScrollDirection": 0, "TapsEnabled": 0,
        "ThreeFingerSlideEnabled": 4, "ThreeFingerUp": 12, "ThreeFingerLeft": 1,
        "FourFingerSlideEnabled": 3, "FourFingerTapEnabled": 4,
    }
    monkeypatch.setattr(sysprefs, "_read_key",
                        lambda path: raw if path == sysprefs.PTP_KEY else {"MouseSpeed": 0})
    p = sysprefs.read_touchpad_prefs()
    assert p["cursorSpeed"] == 20 and p["natural"] is False and p["taps"] is False
    assert p["threeSlide"]["preset"] == "custom"
    assert p["threeSlide"]["map"]["up"] == "maximize"
    assert p["threeSlide"]["map"]["left"] == "switchapp_prev"
    assert p["fourSlide"]["map"] == sysprefs.PRESET_MAPS["audio"]
    assert p["fourTap"] == "middleclick" and p["mouseAccel"] is False


def test_session_gain_scales_moves():
    inj = FakeInjector()
    s = Session(inj, gain=0.5)
    s.handle({"t": "m", "x": 10, "y": -4})
    assert inj.calls == [("move", 5, -2)]


def test_pointer_multiplier_table():
    from host.mouseaccel import POINTER_SPEED_MULT
    assert POINTER_SPEED_MULT[10] == 1.0 and POINTER_SPEED_MULT[20] == 3.5
    assert len(POINTER_SPEED_MULT) == 20
