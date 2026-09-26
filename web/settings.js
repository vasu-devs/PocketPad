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
    haptics: 1,            // 0 off, 0.5 light, 1 normal, 2 strong
    inkStyle: 'rings',     // rings | glow | comet | off
    theme: 'graphite',
    accent: '',            // '' = theme default, else #rrggbb
    texture: 'plain',      // plain | grid | dots | carbon
    corners: 'round',      // round | sharp
    keepAwake: true,
    orientation: 'auto',   // auto | portrait | landscape-left | landscape-right
  };

  // Windows cursor speed 1..20 (10 = default) to a pointer multiplier.
  function speedFromWindows(cs) {
    const c = Math.min(20, Math.max(1, Number(cs) || 10));
    return +(0.25 + ((c - 1) / 19) * 2.25).toFixed(2);
  }

  const THEMES = {
    graphite: { label: 'Graphite', bg: '#0b0c0e', pad: '#111317', edge: 'rgba(255,255,255,0.07)', panel: '#15171b', panel2: '#1c1f24', line: 'rgba(255,255,255,0.08)', text: '#ece9e2', muted: '#8d939c', faint: '#5c626b', accent: '#f0b23c' },
    midnight: { label: 'Midnight', bg: '#070b14', pad: '#0d1322', edge: 'rgba(160,190,255,0.10)', panel: '#111a2b', panel2: '#172238', line: 'rgba(160,190,255,0.10)', text: '#e6ecf7', muted: '#8794ab', faint: '#566179', accent: '#5aa9ff' },
    forest:   { label: 'Forest', bg: '#0a0f0c', pad: '#101712', panel: '#141d18', edge: 'rgba(180,255,200,0.08)', panel2: '#1b2620', line: 'rgba(180,255,200,0.08)', text: '#e8efe9', muted: '#8ea095', faint: '#5e6f65', accent: '#7fd18b' },
    rose:     { label: 'Rose', bg: '#120a0e', pad: '#1a1015', panel: '#1f141a', edge: 'rgba(255,190,210,0.09)', panel2: '#2a1a22', line: 'rgba(255,190,210,0.09)', text: '#f3e8ec', muted: '#a48a95', faint: '#6f5a63', accent: '#ff6f91' },
    oled:     { label: 'Pitch black', bg: '#000000', pad: '#050505', panel: '#0d0d0d', edge: 'rgba(255,255,255,0.10)', panel2: '#161616', line: 'rgba(255,255,255,0.09)', text: '#f2f2f2', muted: '#8a8a8a', faint: '#555555', accent: '#e8e8e8' },
    paper:    { label: 'Paper', bg: '#e9e6df', pad: '#f7f5f0', panel: '#f7f5f0', edge: 'rgba(0,0,0,0.08)', panel2: '#e3dfd6', line: 'rgba(0,0,0,0.08)', text: '#1c1b19', muted: '#6b6862', faint: '#9a968e', accent: '#c2410c', light: true },
  };

  function load() {
    let saved = {};
    try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { saved = {}; }
    if (typeof saved.haptics === 'boolean') saved.haptics = saved.haptics ? 1 : 0;
    if (typeof saved.ink === 'boolean') { saved.inkStyle = saved.ink ? 'rings' : 'off'; delete saved.ink; }
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

  window.PocketSettings = { DEFAULTS, SWIPE_PRESETS, SYNCED, THEMES, load, save, presetOf, effective, describeSystem, speedFromWindows };
})();
