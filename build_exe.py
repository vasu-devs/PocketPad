"""Build dist/PocketPad.exe with PyInstaller (one file, console window for the QR)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WEB = ROOT / "pocketpad" / "web"


def main() -> int:
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onefile", "--console",
        "--name", "PocketPad",
        "--icon", str(ROOT / "packaging" / "pocketpad.ico"),
        "--add-data", f"{WEB}{';' if sys.platform == 'win32' else ':'}pocketpad/web",
        "--collect-submodules", "pocketpad",
        str(ROOT / "packaging" / "entry.py"),
    ]
    if not (ROOT / "packaging" / "pocketpad.ico").is_file():
        cmd = [c for c in cmd if c != "--icon" and not c.endswith("pocketpad.ico")]
    print(" ".join(cmd))
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    raise SystemExit(main())
