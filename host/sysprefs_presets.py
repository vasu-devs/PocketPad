"""Direction maps for the Windows swipe presets. Shared by host and (mirrored in) phone."""

PRESET_MAPS = {
    "apps":     {"up": "taskview", "down": "showdesktop", "left": "switchapp_prev", "right": "switchapp_next"},
    "desktops": {"up": "taskview", "down": "showdesktop", "left": "desktop_prev", "right": "desktop_next"},
    "audio":    {"up": "volume_up", "down": "volume_down", "left": "prev_track", "right": "next_track"},
    "nothing":  {"up": "none", "down": "none", "left": "none", "right": "none"},
}
