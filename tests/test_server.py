import json

import pytest
from aiohttp import WSMsgType
from aiohttp.test_utils import TestClient, TestServer

from host.config import HostConfig
from host.injector import FakeInjector
from host.server import WS_CLOSE_BAD_KEY, create_app


@pytest.fixture(autouse=True)
def unit_pointer_speed(monkeypatch):
    # The real machine's pointer-speed slider must not leak into the assertions.
    monkeypatch.setattr("host.server.pointer_multiplier", lambda: 1.0)


@pytest.fixture
async def client():
    inj = FakeInjector()
    app = create_app(HostConfig(key="424242", smoothing=False), inj)
    async with TestClient(TestServer(app)) as c:
        c.injector = inj
        yield c


async def test_index_and_static(client):
    r = await client.get("/")
    assert r.status == 200 and "PocketPad" in await r.text()
    r = await client.get("/static/app.js")
    assert r.status == 200
    r = await client.get("/api/info")
    body = await r.json()
    assert body["app"] == "PocketPad" and body["actions"]


async def test_ws_rejects_wrong_key(client):
    ws = await client.ws_connect("/ws?k=000000")
    msg = await ws.receive()
    assert msg.type == WSMsgType.CLOSE and msg.data == WS_CLOSE_BAD_KEY
    assert client.injector.calls == []


async def test_ws_roundtrip(client):
    ws = await client.ws_connect("/ws?k=424242")
    hello = json.loads((await ws.receive()).data)
    assert hello["t"] == "hello" and hello["actions"]
    assert "cursorSpeed" in hello["system"] and "threeSlide" in hello["system"]
    await ws.send_str(json.dumps({"t": "m", "x": 3, "y": 4}))
    await ws.send_str(json.dumps({"t": "ping", "id": 1}))
    pong = json.loads((await ws.receive()).data)
    assert pong == {"t": "pong", "id": 1}
    assert ("move", 3, 4) in client.injector.calls
    # Bad messages are logged and skipped, not fatal.
    await ws.send_str("garbage")
    await ws.send_str(json.dumps({"t": "ping", "id": 2}))
    assert json.loads((await ws.receive()).data)["id"] == 2
    # A dropped connection releases held buttons and modifiers.
    await ws.send_str(json.dumps({"t": "b", "b": "left", "s": 1}))
    await ws.close()
    await client.server.app.shutdown()
    assert ("button", "left", False) in client.injector.calls


async def test_ws_binary_frames_with_smoothing():
    import struct
    inj = FakeInjector()
    app = create_app(HostConfig(key="1"), inj)
    async with TestClient(TestServer(app)) as c:
        ws = await c.ws_connect("/ws?k=1")
        await ws.receive()
        await ws.send_bytes(struct.pack("<Bff", 1, 12.0, 0.0))
        await ws.send_bytes(bytes([3]))
        await ws.send_str(json.dumps({"t": "ping", "id": 1}))
        await ws.receive()
        await ws.close()
    assert sum(cl[1] for cl in inj.calls if cl[0] == "move") == 12
