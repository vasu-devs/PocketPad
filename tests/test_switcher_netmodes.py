import pytest

from pocketpad import netmodes
from pocketpad.injector import FakeInjector
from pocketpad.platform_info import SWITCHER_MOD
from pocketpad.protocol import ProtocolError, Session


def test_switcher_holds_alt_until_end():
    inj = FakeInjector()
    s = Session(inj)
    s.handle({"t": "g", "g": "switchapp", "p": "start", "d": 1})
    s.handle({"t": "g", "g": "switchapp", "p": "step", "d": 1})
    s.handle({"t": "g", "g": "switchapp", "p": "step", "d": -1})
    s.handle({"t": "g", "g": "switchapp", "p": "end"})
    assert inj.calls == [
        ("key", SWITCHER_MOD, True), ("combo", ("tab",)),
        ("combo", ("tab",)),
        ("combo", ("shift", "tab")),
        ("key", SWITCHER_MOD, False),
    ]


def test_switcher_released_on_close():
    inj = FakeInjector()
    s = Session(inj)
    s.handle({"t": "g", "g": "switchapp", "p": "start", "d": 1})
    s.close()
    assert inj.calls[-1] == ("key", SWITCHER_MOD, False)
    s.close()  # idempotent
    assert inj.calls.count(("key", SWITCHER_MOD, False)) == 1


def test_switcher_rejects_garbage():
    s = Session(FakeInjector())
    with pytest.raises(ProtocolError):
        s.handle({"t": "g", "g": "dance", "p": "start"})
    with pytest.raises(ProtocolError):
        s.handle({"t": "g", "g": "switchapp", "p": "maybe"})


def test_hotspot_ip_picks_ics_range(monkeypatch):
    fake = [(0, 0, 0, "", ("192.168.1.36", 0)), (0, 0, 0, "", ("192.168.137.1", 0))]
    monkeypatch.setattr(netmodes.socket, "getaddrinfo", lambda *a, **k: fake)
    assert netmodes.hotspot_ip() == "192.168.137.1"
    monkeypatch.setattr(netmodes.socket, "getaddrinfo", lambda *a, **k: fake[:1])
    assert netmodes.hotspot_ip() is None
