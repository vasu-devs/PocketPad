/* Settings model: defaults, persistence, and swipe presets.
   Everything the user can tune lives on the phone. The host only performs. */
(function () {
  'use strict';

  const KEY = 'pocketpad.settings.v1';

  const SWIPE_PRESETS = {
    apps:     { label: 'Switch apps and show desktop',
                map: { up: 'taskview', down: 'showdesktop', left: 'switchapp_prev', right: 'switchapp_next' } },
    desktops: { label: 'Switch desktops and show desktop',
                map: { up: 'taskview', down: 'showdesktop', left: 'desktop_prev', right: 'desktop_next' } },
    audio:    { label: 'Change audio and volume',
                map: { up: 'volume_up', down: 'volume_down', left: 'prev_track', right: 'next_track' } },
    nothing:  { label: 'Nothing',
                map: { up: 'none', down: 'none', left: 'none', right: 'none' } },
  };

  const DEFAULTS = {
    speed: 1.6,          // pointer speed multiplier
    accel: 0.5,          // 0 = linear, 1 = strong acceleration
    scroll: 1.0,         // scroll speed multiplier
    natural: true,       // content follows fingers
    notched: false,      // whole wheel notches only (legacy apps)
    tap1: 'leftclick',
    tap2: 'rightclick',
    tap3: 'middleclick',
    tap4: 'notifications',
    swipe3: Object.assign({}, SWIPE_PRESETS.apps.map),
    swipe4: Object.assign({}, SWIPE_PRESETS.desktops.map),
    dragOnDoubleTap: true,
    threeFingerDrag: false,
    buttons: false,      // on-screen left/right buttons
    haptics: true,
    ink: true,           // draw touch contacts
    keepAwake: true,
  };

  function load() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { saved = {}; }
    const s = Object.assign({}, DEFAULTS, saved);
    s.swipe3 = Object.assign({}, DEFAULTS.swipe3, saved.swipe3 || {});
    s.swipe4 = Object.assign({}, DEFAULTS.swipe4, saved.swipe4 || {});
    return s;
  }

  function save(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode: keep in memory */ }
  }

  function presetOf(map) {
    for (const [k, p] of Object.entries(SWIPE_PRESETS)) {
      if (['up', 'down', 'left', 'right'].every(d => p.map[d] === map[d])) return k;
    }
    return 'custom';
  }

  window.PocketSettings = { DEFAULTS, SWIPE_PRESETS, load, save, presetOf };
})();
