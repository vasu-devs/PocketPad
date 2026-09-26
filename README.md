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

Windows setting worth knowing: **Settings > Bluetooth & devices > Mouse >
Additional mouse settings > Pointer Options > "Enhance pointer precision"**.
When it is on, Windows applies its own acceleration on top of PocketPad's, so
lower the Speed slider or turn that option off if the cursor feels jumpy.

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
  main.py        CLI, LAN address discovery, QR banner
  server.py      aiohttp app: static files + /ws channel, pairing check, stuck-key release
  protocol.py    wire format, per-connection accumulators (sub-pixel moves, wheel units)
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

21 tests cover the protocol (accumulators, clamps, rejections), the key table
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
