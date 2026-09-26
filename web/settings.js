/* Settings model.

   Two layers:
     user     what the person set on this phone (persisted)
     system   what the PC's Precision Touchpad settings say (sent on connect)
   effective() merges them: with matchPC on, the PC wins for everything it
   knows about; the phone-only knobs (acceleration, haptics, ink) stay local. */
(function () {
  'use strict';

  const KEY = 'pocketpad.settings.v2';

  const SWIPE_PRESETS = {
    apps:     { label: 'Switch apps', map: { up: 'taskview', down: 'showdesktop', left: 'switchapp_prev', right: 'switchapp_next' } },
    desktops: { label: 'Switch desktops', map: { up: 'taskview', down: 'showdesktop', left: 'desktop_prev', right: 'desktop_next' } },
    audio:    { label: 'Audio and volume', map: { up: 'volume_up', down: 'volume_down', left: 'prev_track', right: 'next_track' } },
    nothing:  { label: 'Nothing', map: { up: 'none', down: 'none', left: 'none', right: 'none' } },
  };

  const DEFAULTS = {
    matchPC: true,
    speed: 1.3,
    accel: 0.5,
    scroll: 1.0,
    natural: true,
    notched: false,
    pan: true,
    zoom: true,
    tap1: 'leftclick',
    tap2: 'rightclick',
    tap3: 'search',
    tap4: 'notifications',
    swipe3: Object.assign({}, SWIPE_PRESETS.apps.map),
    swipe4: Object.assign({}, SWIPE_PRESETS.desktops.map),
    dragOnDoubleTap: true,
    threeFingerDrag: false,
    buttons: false,
    haptics: true,
    ink: true,
    keepAwake: true,
    orientation: 'auto',   // auto | portrait | landscape-left | landscape-right
  };

  // Windows cursor speed 1..20 (10 = default) to a pointer multiplier.
  function speedFromWindows(cs) {
    const c = Math.min(20, Math.max(1, Number(cs) || 10));
    return +(0.25 + ((c - 1) / 19) * 2.25).toFixed(2);
  }

  function load() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { saved = {}; }
    const s = Object.assign({}, DEFAULTS, saved);
    s.swipe3 = Object.assign({}, DEFAULTS.swipe3, saved.swipe3 || {});
    s.swipe4 = Object.assign({}, DEFAULTS.swipe4, saved.swipe4 || {});
    return s;
  }

  function save(s) {
    try { localStorage.setItem(KEY, JSON.stringify(s)); } catch (e) { /* private mode */ }
  }

  function presetOf(map) {
    for (const [k, p] of Object.entries(SWIPE_PRESETS)) {
      if (['up', 'down', 'left', 'right'].every(d => p.map[d] === map[d])) return k;
    }
    return 'custom';
  }

  function usable(name) {
    return typeof name === 'string' && name !== 'custom' && !name.startsWith('unknown:');
  }

  function mergeSwipe(userMap, sysSlide) {
    if (!sysSlide || !sysSlide.map) return userMap;
    const out = Object.assign({}, userMap);
    for (const d of ['up', 'down', 'left', 'right']) {
      if (usable(sysSlide.map[d])) out[d] = sysSlide.map[d];
    }
    return out;
  }

  // Which keys the PC decides when matchPC is on (for the "from PC" tags).
  const SYNCED = ['speed', 'natural', 'pan', 'zoom', 'tap1', 'tap2', 'tap3', 'tap4', 'swipe3', 'swipe4', 'dragOnDoubleTap'];

  function effective(user, system) {
    if (!user.matchPC || !system) return Object.assign({}, user, { synced: [] });
    const e = Object.assign({}, user);
    e.speed = speedFromWindows(system.cursorSpeed);
    e.natural = !!system.natural;
    e.pan = !!system.pan;
    e.zoom = !!system.zoom;
    e.dragOnDoubleTap = !!system.tapAndDrag;
    e.tap1 = system.taps ? 'leftclick' : 'none';
    e.tap2 = system.taps && system.twoFingerTap ? 'rightclick' : 'none';
    if (usable(system.threeTap)) e.tap3 = system.threeTap;
    if (usable(system.fourTap)) e.tap4 = system.fourTap;
    e.swipe3 = mergeSwipe(user.swipe3, system.threeSlide);
    e.swipe4 = mergeSwipe(user.swipe4, system.fourSlide);
    e.synced = SYNCED;
    return e;
  }

  function describeSystem(system) {
    if (!system) return 'Not connected yet.';
    const parts = [
      'speed ' + system.cursorSpeed + ' of 20',
      system.natural ? 'natural scrolling' : 'reverse scrolling',
      'three fingers: ' + (SWIPE_PRESETS[system.threeSlide.preset] || { label: 'custom' }).label.toLowerCase(),
      'four fingers: ' + (SWIPE_PRESETS[system.fourSlide.preset] || { label: 'custom' }).label.toLowerCase(),
    ];
    return 'Following ' + system.host + ': ' + parts.join(', ') + '.';
  }

  window.PocketSettings = { DEFAULTS, SWIPE_PRESETS, SYNCED, load, save, presetOf, effective, describeSystem, speedFromWindows };
})();
