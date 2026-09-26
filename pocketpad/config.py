"""Central constants and configuration for the PocketPad host."""
from __future__ import annotations

import os
import secrets
import sys
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "PocketPad"
VERSION = "0.2.0"


def _web_dir() -> Path:
    # PyInstaller one-file builds unpack data next to sys._MEIPASS.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    for cand in (base / "pocketpad" / "web", Path(__file__).resolve().parent / "web"):
        if cand.is_dir():
            return cand
    return Path(__file__).resolve().parent / "web"


WEB_DIR = _web_dir()

DEFAULT_PORT = 8765
DEFAULT_BIND = "0.0.0.0"

# Wheel units per notch as defined by Windows (WHEEL_DELTA).
WHEEL_DELTA = 120
# Touch pixels of two-finger travel that equal one wheel notch at scroll speed 1.0.
PIXELS_PER_NOTCH = 40.0

# Message-size guard for the WebSocket channel (bytes).
MAX_MESSAGE_BYTES = 4096
# Maximum characters accepted in one text-typing message.
MAX_TEXT_CHARS = 512
# Hard cap for a single relative pointer move (pixels), guards against garbage.
MAX_MOVE_PX = 4000.0

# Stable error codes for logs.
class ErrorCode:
    BAD_KEY = "PP-AUTH-001"
    BAD_MESSAGE = "PP-PROTO-001"
    UNKNOWN_ACTION = "PP-ACT-001"
    INJECT_FAIL = "PP-INJ-001"
    SERVER_FAIL = "PP-SRV-001"


def _make_key() -> str:
    """Six-digit pairing code; short enough to type, random enough for a LAN."""
    return f"{secrets.randbelow(1_000_000):06d}"


@dataclass(frozen=True)
class HostConfig:
    bind: str = DEFAULT_BIND
    port: int = DEFAULT_PORT
    key: str = field(default_factory=_make_key)
    web_dir: Path = WEB_DIR
    log_level: str = "INFO"
    smoothing: bool = True

    @classmethod
    def from_env_and_args(cls, args) -> "HostConfig":
        return cls(
            bind=args.bind or os.environ.get("POCKETPAD_BIND", DEFAULT_BIND),
            port=int(args.port or os.environ.get("POCKETPAD_PORT", DEFAULT_PORT)),
            key=args.key or os.environ.get("POCKETPAD_KEY") or _make_key(),
            log_level=args.log_level or os.environ.get("POCKETPAD_LOG", "INFO"),
            smoothing=not getattr(args, "no_smoothing", False),
        )
