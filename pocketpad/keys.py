"""Key names accepted from the phone, mapped to Windows virtual-key codes."""
from __future__ import annotations

VK: dict[str, int] = {
    # modifiers
    "ctrl": 0x11, "shift": 0x10, "alt": 0x12, "win": 0x5B,
    # navigation / editing
    "enter": 0x0D, "backspace": 0x08, "tab": 0x09, "esc": 0x1B, "space": 0x20,
    "delete": 0x2E, "insert": 0x2D, "home": 0x24, "end": 0x23,
    "pageup": 0x21, "pagedown": 0x22,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "capslock": 0x14, "printscreen": 0x2C,
    # media / system
    "volumeup": 0xAF, "volumedown": 0xAE, "volumemute": 0xAD,
    "playpause": 0xB3, "nexttrack": 0xB0, "prevtrack": 0xB1, "stopmedia": 0xB2,
    "browserback": 0xA6, "browserforward": 0xA7, "browsersearch": 0xAA,
}

# Letters, digits, function keys.
for _c in "abcdefghijklmnopqrstuvwxyz":
    VK[_c] = ord(_c.upper())
for _d in "0123456789":
    VK[_d] = ord(_d)
for _n in range(1, 25):
    VK[f"f{_n}"] = 0x6F + _n

# Keys that Windows flags as "extended" in scan-code terms.
EXTENDED = {
    "win", "insert", "delete", "home", "end", "pageup", "pagedown",
    "left", "up", "right", "down", "printscreen",
    "volumeup", "volumedown", "volumemute", "playpause", "nexttrack",
    "prevtrack", "stopmedia", "browserback", "browserforward", "browsersearch",
}

ALIASES = {
    "control": "ctrl", "escape": "esc", "return": "enter", "windows": "win",
    "super": "win", "meta": "win", "option": "alt", "del": "delete",
    "pgup": "pageup", "pgdn": "pagedown", "bksp": "backspace",
}


def normalize_key(name: str) -> str:
    n = name.strip().lower()
    return ALIASES.get(n, n)


def is_known_key(name: str) -> bool:
    return normalize_key(name) in VK


def parse_combo(spec: str) -> tuple[str, ...]:
    """Parse "ctrl+shift+t" into normalized key names. Raises ValueError."""
    parts = [normalize_key(p) for p in spec.split("+") if p.strip()]
    if not parts or len(parts) > 5:
        raise ValueError(f"bad combo: {spec!r}")
    for p in parts:
        if p not in VK:
            raise ValueError(f"unknown key: {p!r}")
    return tuple(parts)
