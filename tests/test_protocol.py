import json

import pytest

from pocketpad.injector import FakeInjector
from pocketpad.protocol import ProtocolError, Session


@pytest.fixture
def sess():
    inj = FakeInjector()
    return Session(inj), inj


def test_move_accumulates_fractions(sess):
    s, inj = sess
    for _ in range(4):
        s.handle({"t": "m", "x": 0.5, "y": -0.25})
    moves = [c for c in inj.calls if c[0] == "move"]
    assert sum(m[1] for m in moves) == 2
    assert sum(m[2] for m in moves) == -1


def test_move_ignores_zero(sess):
    s, inj = sess
    s.handle({"t": "m", "x": 0.2, "y": 0.2})
    assert inj.calls == []


def test_move_clamps_and_rejects_garbage(sess):
    s, inj = sess
    s.handle({"t": "m", "x": 1e9, "y": 0})
    assert inj.calls[-1][1] == 4000
    with pytest.raises(ProtocolError):
        s.handle({"t": "m", "x": "nope", "y": 0})
    with pytest.raises(ProtocolError):
        s.handle({"t": "m", "x": float("nan"), "y": 0})


def test_click_and_button(sess):
    s, inj = sess
    s.handle({"t": "c", "b": "right", "n": 2})
    assert inj.calls == [("button", "right", True), ("button", "right", False)] * 2
    inj.calls.clear()
    s.handle({"t": "b", "b": "left", "s": 1})
    assert inj.calls == [("button", "left", True)]
    with pytest.raises(ProtocolError):
        s.handle({"t": "b", "b": "x1", "s": 1})


def test_scroll_natural_smooth(sess):
    s, inj = sess
    # 40 px of finger travel = one notch = 120 units, natural sign kept.
    s.handle({"t": "s", "x": 0, "y": 40})
    assert inj.calls == [("wheel", 120, False)]


def test_scroll_reverse_and_horizontal(sess):
    s, inj = sess
    s.handle({"t": "cfg", "natural": False})
    s.handle({"t": "s", "x": 20, "y": 40})
    assert ("wheel", -120, False) in inj.calls
    assert ("wheel", -60, True) in inj.calls


def test_scroll_notched_waits_for_full_notch(sess):
    s, inj = sess
    s.handle({"t": "cfg", "notched": True})
    s.handle({"t": "s", "x": 0, "y": 30})
    assert inj.calls == []
    s.handle({"t": "s", "x": 0, "y": 10})
    assert inj.calls == [("wheel", 120, False)]


def test_scroll_end_drops_remainder(sess):
    s, inj = sess
    s.handle({"t": "s", "x": 0, "y": 0.1})
    s.handle({"t": "se"})
    s.handle({"t": "s", "x": 0, "y": 0.1})
    assert inj.calls == []


def test_zoom_holds_ctrl(sess):
    s, inj = sess
    s.handle({"t": "z", "d": -1})
    assert inj.calls == [("key", "ctrl", True), ("wheel", -120, False), ("key", "ctrl", False)]


def test_named_action_and_custom_combo(sess):
    s, inj = sess
    s.handle({"t": "a", "a": "taskview"})
    from pocketpad.platform_info import OS
    expected = {"win": ("win", "tab"), "mac": ("ctrl", "up"), "linux": ("win",)}[OS]
    assert inj.calls == [("combo", expected)]
    inj.calls.clear()
    s.handle({"t": "a", "a": "keys:Ctrl+Shift+T"})
    assert inj.calls == [("combo", ("ctrl", "shift", "t"))]
    with pytest.raises(ProtocolError):
        s.handle({"t": "a", "a": "format_disk"})
    with pytest.raises(ProtocolError):
        s.handle({"t": "a", "a": "keys:ctrl+bogus"})


def test_key_and_text(sess):
    s, inj = sess
    s.handle({"t": "k", "k": "Enter"})
    s.handle({"t": "txt", "s": "héllo"})
    assert inj.calls == [("combo", ("enter",)), ("text", "héllo")]
    with pytest.raises(ProtocolError):
        s.handle({"t": "k", "k": "hyperspace"})


def test_ping_replies(sess):
    s, _ = sess
    assert s.handle({"t": "ping", "id": 7}) == {"t": "pong", "id": 7}


def test_raw_guards(sess):
    s, _ = sess
    with pytest.raises(ProtocolError):
        s.handle_raw("not json")
    with pytest.raises(ProtocolError):
        s.handle_raw(json.dumps([1, 2]))
    with pytest.raises(ProtocolError):
        s.handle_raw("x" * 5000)
    with pytest.raises(ProtocolError):
        s.handle({"t": "boom"})
