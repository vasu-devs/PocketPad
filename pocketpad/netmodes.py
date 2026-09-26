"""Connection modes beyond the shared Wi-Fi router.

usb      Android USB debugging + `adb reverse`: the phone reaches the host at
         http://127.0.0.1:<port>. No network at all, sub-millisecond transport.
hotspot  Turn on the laptop's Mobile Hotspot so the phone connects straight to
         the laptop instead of via the router (one hop, no router queueing).
"""
from __future__ import annotations

import io
import logging
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

log = logging.getLogger(__name__)

def _tools_dir() -> Path:
    # Frozen exe: keep downloads next to the exe rather than in the temp unpack dir.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "tools"
    return Path(__file__).resolve().parent.parent / "tools"


TOOLS_DIR = _tools_dir()
PLATFORM_TOOLS_URL = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
HOTSPOT_PREFIX = "192.168.137."   # Windows Internet Connection Sharing / Mobile Hotspot range


def hotspot_ip() -> str | None:
    """Address of this PC on its own Mobile Hotspot, if the hotspot is up."""
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip.startswith(HOTSPOT_PREFIX):
                return ip
    except socket.gaierror:
        pass
    return None


def find_adb() -> str | None:
    found = shutil.which("adb")
    if found:
        return found
    candidates = [
        TOOLS_DIR / "platform-tools" / "adb.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Android" / "platform-tools" / "adb.exe",
        Path.home() / "platform-tools" / "adb.exe",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return None


def download_adb() -> str | None:
    """Fetch Google's platform-tools (about 7 MB) into ./tools. Returns adb path."""
    try:
        print("  Downloading Android platform-tools (one time, about 7 MB)...")
        with urllib.request.urlopen(PLATFORM_TOOLS_URL, timeout=120) as r:
            data = r.read()
        TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(TOOLS_DIR)
    except Exception as e:  # network, zip, disk: report and let the user install manually
        log.warning("platform-tools download failed: %s", e)
        return None
    adb = TOOLS_DIR / "platform-tools" / "adb.exe"
    return str(adb) if adb.is_file() else None


def setup_usb(port: int) -> tuple[bool, str]:
    """Forward phone:localhost:port to this host over USB. Returns (ok, message)."""
    adb = find_adb() or download_adb()
    if not adb:
        return False, ("adb not available and the download failed. Install Android platform-tools "
                       "(https://developer.android.com/tools/releases/platform-tools) and rerun with --usb.")
    try:
        devices = subprocess.run([adb, "devices"], capture_output=True, text=True, timeout=15).stdout
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"adb failed to start: {e}"
    lines = [l for l in devices.splitlines()[1:] if l.strip()]
    if not lines:
        return False, ("No phone visible over USB. On the phone: Settings > About > tap Build number 7 times, "
                       "then Developer options > USB debugging on. Plug in, choose File transfer if asked, "
                       "accept the Allow USB debugging prompt, then rerun with --usb.")
    if any("unauthorized" in l for l in lines):
        return False, "Phone shows 'unauthorized': accept the USB debugging prompt on the phone and rerun."
    r = subprocess.run([adb, "reverse", f"tcp:{port}", f"tcp:{port}"], capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return False, f"adb reverse failed: {r.stderr.strip() or r.stdout.strip()}"
    return True, f"USB link ready. On the phone open  http://127.0.0.1:{port}/"


_HOTSPOT_PS = r"""
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
[Windows.Networking.Connectivity.NetworkInformation,Windows.Networking.Connectivity,ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager,Windows.Networking.NetworkOperators,ContentType=WindowsRuntime] | Out-Null
$profile = [Windows.Networking.Connectivity.NetworkInformation]::GetInternetConnectionProfile()
if ($profile -eq $null) { Write-Output 'ERR no internet connection profile; Windows needs one to start a hotspot'; exit 2 }
$mgr = [Windows.Networking.NetworkOperators.NetworkOperatorTetheringManager]::CreateFromConnectionProfile($profile)
$cfg = $mgr.GetCurrentAccessPointConfiguration()
if ($mgr.TetheringOperationalState -ne 'On') {
  $res = Await ($mgr.StartTetheringAsync()) ([Windows.Networking.NetworkOperators.NetworkOperatorTetheringOperationResult])
  if ($res.Status -ne 'Success') { Write-Output ("ERR " + $res.Status + " " + $res.AdditionalErrorMessage); exit 3 }
}
Write-Output ("OK`t" + $cfg.Ssid + "`t" + $cfg.Passphrase)
"""


def start_hotspot() -> tuple[bool, str]:
    """Turn on Windows Mobile Hotspot. Returns (ok, message with SSID and passphrase)."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", _HOTSPOT_PS],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, f"could not run PowerShell: {e}"
    out = (r.stdout or "").strip().splitlines()
    last = out[-1] if out else (r.stderr or "").strip()
    if last.startswith("OK\t"):
        _, ssid, pw = last.split("\t", 2)
        return True, f"Mobile Hotspot is on. Join Wi-Fi '{ssid}' with password '{pw}' on the phone."
    return False, f"hotspot not started: {last or 'unknown error'}"
