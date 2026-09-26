"""PocketPad host entry point.

    python -m host                # start on all interfaces, port 8765
    python -m host --port 9000 --key 123456
    python -m host --dry-run      # log input instead of injecting it
"""
from __future__ import annotations

import argparse
import logging
import socket
import sys

from aiohttp import web

from .config import APP_NAME, VERSION, HostConfig
from .injector import FakeInjector
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


def _banner(config: HostConfig) -> None:
    ips = _lan_ips()
    primary = ips[0]
    url = f"http://{primary}:{config.port}/?k={config.key}"
    print(f"\n  {APP_NAME} {VERSION}")
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
    _banner(config)
    web.run_app(app, host=config.bind, port=config.port, print=None, access_log=None)
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
