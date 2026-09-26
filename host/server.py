"""aiohttp application: serves the phone web app and the WebSocket channel."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from aiohttp import WSMsgType, web

from . import actions
from .config import APP_NAME, VERSION, ErrorCode, HostConfig
from .injector import Injector
from .mouseaccel import pointer_multiplier
from .protocol import ProtocolError, Session
from .smoother import MotionSmoother
from .sysprefs import read_touchpad_prefs

log = logging.getLogger(__name__)

WS_CLOSE_BAD_KEY = 4403

INJECTOR_KEY = web.AppKey("injector", object)
CONFIG_KEY = web.AppKey("config", HostConfig)


def create_app(config: HostConfig, injector: Injector) -> web.Application:
    app = web.Application()
    app[INJECTOR_KEY] = injector
    app[CONFIG_KEY] = config
    app.router.add_get("/", _index)
    app.router.add_get("/ws", _websocket)
    app.router.add_get("/api/info", _info)
    app.router.add_get("/favicon.ico", _favicon)
    app.router.add_static("/static/", path=config.web_dir, show_index=False)
    return app


async def _index(request: web.Request) -> web.StreamResponse:
    index: Path = request.app[CONFIG_KEY].web_dir / "index.html"
    return web.FileResponse(index, headers={"Cache-Control": "no-cache"})


async def _favicon(request: web.Request) -> web.StreamResponse:
    return web.FileResponse(request.app[CONFIG_KEY].web_dir / "icon.svg")


async def _info(request: web.Request) -> web.Response:
    return web.json_response({
        "app": APP_NAME, "version": VERSION, "actions": actions.catalog(),
    })


def _authorized(request: web.Request) -> bool:
    return request.query.get("k") == request.app[CONFIG_KEY].key


async def _websocket(request: web.Request) -> web.StreamResponse:
    peer = request.remote
    ws = web.WebSocketResponse(heartbeat=20, max_msg_size=8192)
    await ws.prepare(request)
    if not _authorized(request):
        # Close after the upgrade so the phone can read a specific close code.
        log.warning("%s rejected connection from %s (wrong key)", ErrorCode.BAD_KEY, peer)
        await ws.close(code=WS_CLOSE_BAD_KEY, message=b"wrong pairing key")
        return ws
    injector = request.app[INJECTOR_KEY]
    smoother = MotionSmoother(injector) if request.app[CONFIG_KEY].smoothing else None
    # Injected motion is scaled by the Windows mouse pointer-speed slider; cancel that
    # so the phone's speed setting means the same thing on every PC.
    session = Session(injector, smoother=smoother, gain=1.0 / pointer_multiplier())
    log.info("phone connected from %s", peer)
    await ws.send_str(json.dumps({"t": "hello", "app": APP_NAME, "version": VERSION,
                                  "actions": actions.catalog(),
                                  "system": read_touchpad_prefs()}))
    bad = 0
    try:
        async for msg in ws:
            if msg.type == WSMsgType.BINARY:
                try:
                    session.handle_binary(msg.data)
                except ProtocolError as e:
                    bad += 1
                    log.warning("%s bad binary frame from %s: %s", ErrorCode.BAD_MESSAGE, peer, e)
                continue
            if msg.type != WSMsgType.TEXT:
                if msg.type == WSMsgType.ERROR:
                    log.error("%s websocket error: %s", ErrorCode.SERVER_FAIL, ws.exception())
                continue
            try:
                reply = session.handle_raw(msg.data)
            except ProtocolError as e:
                bad += 1
                log.warning("%s bad message from %s: %s", ErrorCode.BAD_MESSAGE, peer, e)
                if bad > 50:
                    await ws.close(code=1008, message=b"too many bad messages")
                    break
                continue
            if reply is not None:
                await ws.send_str(json.dumps(reply))
    finally:
        session.close()
        # Never leave a button or modifier stuck if the phone drops mid-drag.
        inj = request.app[INJECTOR_KEY]
        for b in ("left", "right", "middle"):
            inj.button(b, False)
        for k in ("ctrl", "shift", "alt", "win"):
            inj.key(k, False)
        log.info("phone disconnected from %s", peer)
    return ws
