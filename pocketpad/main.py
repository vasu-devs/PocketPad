"""PocketPad host entry point.

    pocketpad                     # start on all interfaces, port 8765
    pocketpad --port 9000 --key 123456
    pocketpad --dry-run           # log input instead of injecting it
"""
from __future__ import annotations

import argparse
import logging
import socket
import sys

from aiohttp import web

from .config import APP_NAME, VERSION, HostConfig
from .injector import FakeInjector
from .mouseaccel import MouseAccelGuard
from .netmodes import hotspot_ip, setup_usb, start_hotspot
from .server import create_app

log = logging.getLogger("pocketpad")


def _lan_ips() -> list[str]:
    """Best-effort list of IPv4 addresses a phone on the LAN could reach."""
    ips: list[str] = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))   # no packets are sent for UDP connect
        ips.append(s.getsockname()[0])
        s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except socket.gaierror:
        pass
    return ips or ["127.0.0.1"]


def _print_qr(url: str) -> None:
    try:
        import qrcode  # optional dependency
    except ImportError:
        print("  (pip install qrcode  to get a scannable QR code here)")
        return
    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    try:
        # Block characters need UTF-8; legacy consoles default to cp1252.
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        # Invert for dark terminals: most Windows terminals are dark.
        qr.print_ascii(invert=True)
    except (UnicodeEncodeError, OSError):
        print("  (terminal cannot draw the QR code; type the address instead)")


def _banner(config: HostConfig, prefer_ip: str | None = None, usb: bool = False) -> None:
    ips = _lan_ips()
    if prefer_ip:
        ips = [prefer_ip] + [ip for ip in ips if ip != prefer_ip]
    if usb:
        ips = ["127.0.0.1"] + [ip for ip in ips if ip != "127.0.0.1"]
    primary = ips[0]
    url = f"http://{primary}:{config.port}/?k={config.key}"
    print(f"\n  {APP_NAME} {VERSION}")
    if usb:
        print("  Open this on the phone (USB cable):\n")
    elif prefer_ip:
        print("  Open this on your phone once it has joined the laptop hotspot:\n")
    else:
        print("  Open this on your phone (same Wi-Fi):\n")
    print(f"    {url}\n")
    if len(ips) > 1:
        print("  Other addresses on this PC:")
        for ip in ips[1:]:
            print(f"    http://{ip}:{config.port}/?k={config.key}")
        print()
    _print_qr(url)
    print(f"\n  Pairing key: {config.key}     Press Ctrl+C to stop.\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pocketpad", description=f"{APP_NAME} host")
    p.add_argument("--bind", help="interface to listen on (default 0.0.0.0)")
    p.add_argument("--port", type=int, help="TCP port (default 8765)")
    p.add_argument("--key", help="fixed pairing key instead of a random one")
    p.add_argument("--log-level", help="DEBUG, INFO, WARNING")
    p.add_argument("--dry-run", action="store_true", help="log input events instead of injecting")
    p.add_argument("--usb", action="store_true", help="Android USB mode via adb reverse (no Wi-Fi needed)")
    p.add_argument("--hotspot", action="store_true", help="turn on Windows Mobile Hotspot for a direct link")
    p.add_argument("--no-smoothing", action="store_true", help="inject deltas as they arrive (raw)")
    p.add_argument("--keep-mouse-accel", action="store_true",
                   help="do not pause 'Enhance pointer precision' while running")
    args = p.parse_args(argv)
    config = HostConfig.from_env_and_args(args)

    logging.basicConfig(level=config.log_level.upper(),
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.dry_run or sys.platform != "win32":
        if sys.platform != "win32":
            log.warning("not on Windows: running in dry-run mode")
        injector = _LoggingInjector()
    else:
        from .input_win import WindowsInjector
        injector = WindowsInjector()

    app = create_app(config, injector)

    prefer_ip = None
    usb_ok = False
    if args.hotspot:
        ok, msg = start_hotspot()
        print("\n  " + msg)
        prefer_ip = hotspot_ip() if ok else None
        if ok and not prefer_ip:
            print("  (hotspot address not visible yet; if the phone cannot connect, rerun in a few seconds)")
    if args.usb:
        usb_ok, msg = setup_usb(config.port)
        print("\n  " + msg)
    _banner(config, prefer_ip=prefer_ip, usb=usb_ok)

    guard = MouseAccelGuard()
    if not args.keep_mouse_accel and not args.dry_run:
        if guard.disable():
            print("  'Enhance pointer precision' is paused until you close PocketPad.\n")
    try:
        web.run_app(app, host=config.bind, port=config.port, print=None, access_log=None)
    finally:
        guard.restore()
    return 0


class _LoggingInjector(FakeInjector):
    def __getattribute__(self, name):
        attr = super().__getattribute__(name)
        if name in ("move", "button", "wheel", "key_combo", "key", "type_text"):
            def wrapped(*a, **kw):
                log.info("inject %s %s", name, a)
                self.calls.clear()
            return wrapped
        return attr


if __name__ == "__main__":
    raise SystemExit(main())
