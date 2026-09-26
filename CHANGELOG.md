# Changelog

## 0.2.0 (2026-09-27)

- Packaged as `pocketpad` (pip / pipx installable, `pocketpad` command) and as a one-file Windows exe.
- Scroll strip on the right edge of the pad with flick momentum.
- Keyboard button is a real on/off toggle; back-gesture dismissal detected.
- Appearance: six themes, custom accent, pad textures, touch effects, corners, vibration strength.
- Rotate button and orientation modes; landscape layout; touch rotation fallback when the OS locks rotation.
- Three-finger horizontal swipe drives the live Windows app switcher (Alt held until lift).
- Hotspot mode prints the laptop's hotspot address first; USB mode downloads platform-tools automatically.
- Host reads Precision Touchpad preferences from the registry and the phone mirrors them.
- Binary motion frames and a host-side motion smoother; Windows pointer-speed and acceleration compensated.

## 0.1.0 (2026-09-26)

- First working version: Python host with SendInput injection, phone web app with the Windows gesture vocabulary.
