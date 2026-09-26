# PocketPad

Turn your phone into a Windows precision-style trackpad over Wi-Fi. No app store,
no driver: a small Python host runs on the laptop, and the phone opens a web page.

```
phone browser  --Wi-Fi / WebSocket-->  host (Python, aiohttp)  --SendInput-->  Windows
   gestures, settings                     validates, injects
```

## Quick start

1. On the laptop: double-click `PocketPad.bat` (or `python -m host`). It installs
   `aiohttp` and `qrcode` on first run, then prints a URL and a QR code.
   When Windows asks, allow Python on **private** networks.
2. On the phone (same Wi-Fi): scan the QR code or type the URL. It looks like
   `http://192.168.1.36:8765/?k=123456`. The six-digit `k` is the pairing key
   and changes every time the host starts (fix it with `--key 123456`).
3. Tap once to go full screen. Android: "Add to Home screen" gives an icon that
   opens straight into the pad. iPhone: Share, then "Add to Home Screen".

## It follows your touchpad settings

On connect the host reads your Windows Precision Touchpad preferences
(cursor speed, scroll direction, taps, tap-and-drag, pinch, and the three and
four finger swipe and tap choices) and the phone mirrors them. The settings
sheet shows "Match this PC's touchpad" at the top with a summary of what it
found; turn it off to tune the phone independently. Anyone who connects their
phone to their own PC gets their own feel automatically.

Two Windows mouse settings would otherwise distort injected motion, so the
host handles them:

- **Enhance pointer precision** is paused while the host runs and restored on
  exit (live setting only, the registry is never touched). Use
  `--keep-mouse-accel` to opt out.
- The **mouse pointer speed slider** multiplies every injected move (3.5x at
  the top of the slider). The host cancels that factor so the phone's speed
  means the same thing on every PC.

## Connection modes

| Mode | Command | Latency | Notes |
|---|---|---|---|
| Wi-Fi via router | `PocketPad.bat` | 5-30 ms | default, both devices on the same network |
| Laptop hotspot | `PocketPad.bat --hotspot` | 2-8 ms | turns on Windows Mobile Hotspot and prints its name and password; the phone talks straight to the laptop, no router |
| USB cable (Android) | `PocketPad.bat --usb` | under 1 ms | needs USB debugging and `adb`; the phone opens `http://127.0.0.1:8765/?k=...` |

Motion is sent as 9-byte binary frames, one per touch sample, and the host
runs a motion smoother that spreads each sample evenly until the next one
arrives, so Wi-Fi burstiness does not turn into cursor stutter. Disable it
with `--no-smoothing` to compare.

## Gestures

| Fingers | Gesture | Default |
|---|---|---|
| 1 | move | pointer |
| 1 | tap | left click |
| 1 | tap, then tap and hold | drag (double-tap-drag) |
| 1 | double tap | double click |
| 2 | tap | right click |
| 2 | slide | scroll, natural direction, smooth |
| 2 | pinch | zoom (Ctrl + wheel) |
| 3 | tap | middle click |
| 3 | swipe up / down | Task view / Show desktop |
| 3 | swipe left / right | Switch apps (repeats as you keep sliding) |
| 4 | tap | Notification center |
| 4 | swipe up / down | Task view / Show desktop |
| 4 | swipe left / right | Switch virtual desktops (repeats) |

Everything above is configurable from the settings sheet on the phone (the
menu button at top right). It mirrors the Windows touchpad settings page:
pointer speed and acceleration, scroll speed, natural scrolling, notched
scrolling for legacy apps, tap actions per finger count, the Windows swipe
presets (switch apps, switch desktops, audio and volume, nothing) or a custom
action per direction, three-finger drag, on-screen left and right buttons,
haptics, touch rings, keep-awake. Custom shortcuts are typed as
`ctrl+shift+t`. Settings are stored on the phone.

The **Aa** button opens the phone keyboard and types into whatever has focus
on the PC, including Enter, Backspace, arrows and Unicode.

## Layout

```
host/
  main.py        CLI, LAN address discovery, QR banner, --usb / --hotspot
  server.py      aiohttp app: static files + /ws channel, pairing check, stuck-key release
  protocol.py    wire format (JSON + binary motion frames), per-connection accumulators
  smoother.py    high-rate motion smoother thread
  sysprefs.py    reads Windows Precision Touchpad preferences from the registry
  mouseaccel.py  pauses "Enhance pointer precision", reads the pointer-speed multiplier
  netmodes.py    adb reverse (USB) and Windows Mobile Hotspot
  actions.py     named actions (Task view, volume, snap...) and `keys:` custom combos
  keys.py        virtual-key table, aliases, combo parser
  input_win.py   SendInput via ctypes (mouse, wheel, scan-code keys, Unicode text)
  injector.py    Injector interface + FakeInjector (tests, --dry-run)
  config.py      constants, error codes, HostConfig
web/
  index.html, style.css      phone UI (dark graphite, amber touch ink)
  gestures.js                touch state machine -> semantic events
  settings.js                defaults, presets, localStorage
  app.js                     WebSocket, ink layer, keyboard, settings sheet
tests/                       pytest: protocol, keys/actions, HTTP + WebSocket
```

Design notes:

- The phone owns all preferences and sends *semantic* events
  (`move`, `scroll`, `zoom`, `click`, `action:taskview`). The host is a dumb,
  validated injector. This keeps the host tiny and lets each phone keep its own feel.
- The phone owns preferences but defers to the PC's touchpad settings by default.
- Pointer deltas are floats. The host keeps the fractional remainder so slow
  movements are not lost to integer rounding. Same for wheel units.
- Scroll emits small wheel deltas (smooth scrolling in Edge, Chrome, Explorer,
  Office). "Whole notches only" batches to 120-unit notches for apps that ignore
  partial deltas.
- When a phone disconnects mid-drag the host releases every mouse button and
  modifier so nothing stays stuck.

## Security

- Pairing key required on the WebSocket; wrong key is closed with code 4403
  and never reaches the injector.
- Every message is size-limited, type-checked and clamped. Unknown actions and
  key names are rejected. Text is capped at 512 characters per message.
- Traffic is plain HTTP on your LAN. Anyone on the same network who has the
  key can control the mouse, so treat the key like a password and do not run
  the host on public Wi-Fi. Bind to one interface with `--bind 192.168.1.36`.

## Testing

```
pip install -r requirements.txt
python -m pytest -q
```

29 tests cover the protocol (accumulators, clamps, rejections), the key table
and action catalog, and the HTTP + WebSocket server with a fake injector.
Gesture recognition was verified in an emulated Pixel 7 (Playwright + Chrome
DevTools touch events) for move, tap, two-finger tap, scroll, pinch, three
and four finger swipes with repeat, and double-tap drag. Run the host with
`--dry-run` to log injected events without moving anything.

No caching layer exists; `index.html` is served with `Cache-Control: no-cache`
so phones always pick up host updates.

## Known limits and next steps

- This is input synthesis, not a real Precision Touchpad. Windows does not
  list PocketPad under Touchpad settings, and apps that read raw touchpad
  contacts (Pad2Screen style tools) will not see it. Getting there needs a
  virtual HID driver (UMDF VHF) with a signed package, which is the v2 path.
- Android Chrome gives fullscreen; iOS Safari only via Add to Home Screen.
- Latency is typically 5 to 20 ms on a normal home network; the top bar shows
  the live round-trip time.
- Ideas queued: a tray icon and autostart for the host, mDNS so the phone can
  find the laptop without a QR, USB tethering mode for zero-latency wired use,
  a single-file `.exe` build with PyInstaller.
