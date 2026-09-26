/* PocketPad phone app: connection, ink, dock, keyboard, settings sheet, picker. */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const S = window.PocketSettings;
  let user = S.load();          // what this phone stores
  let system = null;            // what the PC reports
  let eff = S.effective(user, system);
  let actionsCatalog = [];

  // ------------------------------------------------------------ connection
  const key = new URLSearchParams(location.search).get('k') || '';
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws?k=' + encodeURIComponent(key);
  let ws = null, retryTimer = 0, pingTimer = 0, lastPingId = 0, lastPingAt = 0;
  const statusEl = $('status'), overlay = $('overlay');

  function setStatus(text, ok) { statusEl.textContent = text; statusEl.classList.toggle('ok', !!ok); }
  function showOverlay(title, body) { $('overlay-title').textContent = title; $('overlay-body').textContent = body; overlay.hidden = false; }

  function connect() {
    clearTimeout(retryTimer);
    if (ws) { try { ws.onclose = null; ws.close(); } catch (e) { /* ignore */ } }
    setStatus('Connecting', false);
    ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    ws.onopen = () => {
      overlay.hidden = true;
      setStatus('Connected', true);
      sendCfg();
      clearInterval(pingTimer);
      pingTimer = setInterval(ping, 3000);
      ping();
    };
    ws.onmessage = ev => {
      if (typeof ev.data !== 'string') return;
      let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.t === 'hello') {
        if (Array.isArray(msg.actions)) actionsCatalog = msg.actions;
        if (msg.system) { system = msg.system; recompute(); }
        if (!$('sheet').hidden) renderSheet();
      } else if (msg.t === 'pong' && msg.id === lastPingId) {
        setStatus(Math.round(performance.now() - lastPingAt) + ' ms', true);
      }
    };
    ws.onclose = ev => {
      clearInterval(pingTimer);
      if (ev.code === 4403) {
        showOverlay('Wrong pairing key', 'Scan the QR code from the host again. The key changes each time the host starts.');
        setStatus('Not paired', false);
        return;
      }
      setStatus('Reconnecting', false);
      showOverlay('Lost the PC', 'Reconnecting. Check the host window on the laptop is still open.');
      retryTimer = setTimeout(connect, 1500);
    };
  }

  function send(obj) { if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj)); }

  const bin = new ArrayBuffer(9), binView = new DataView(bin);
  const binEnd = new Uint8Array([3]);
  function sendDelta(kind, dx, dy) {
    if (!ws || ws.readyState !== 1) return;
    binView.setUint8(0, kind); binView.setFloat32(1, dx, true); binView.setFloat32(5, dy, true);
    ws.send(bin);
  }

  function ping() { lastPingId += 1; lastPingAt = performance.now(); send({ t: 'ping', id: lastPingId }); }
  function sendCfg() { send({ t: 'cfg', scroll: 1, natural: eff.natural, notched: eff.notched }); }
  $('retry-btn').addEventListener('click', connect);

  function buzz(ms) { const k = Number(eff.haptics) || 0; if (k && navigator.vibrate) { try { navigator.vibrate(Math.max(1, Math.round(ms * k))); } catch (e) { /* ignore */ } } }

  // ------------------------------------------------------------ ink layer
  const canvas = $('ink'), ctx = canvas.getContext('2d');
  let contacts = [], trail = [], inkRaf = 0;
  function resizeCanvas() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const r = canvas.getBoundingClientRect();
    canvas.width = Math.round(r.width * dpr); canvas.height = Math.round(r.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resizeCanvas);
  resizeCanvas();

  let inkRGB = '240,178,60';
  function drawInk() {
    inkRaf = 0;
    const r = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, r.width, r.height);
    const style = eff.inkStyle || 'rings';
    if (style === 'off') return;
    const now = performance.now();
    const life = style === 'comet' ? 650 : 380;
    trail = trail.filter(p => now - p.t < life);
    if (style === 'rings') {
      ctx.lineWidth = 1.25;
      for (const p of trail) {
        const a = 1 - (now - p.t) / life;
        ctx.beginPath(); ctx.arc(p.x - r.left, p.y - r.top, 5 + 9 * (1 - a), 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(' + inkRGB + ',' + (0.3 * a).toFixed(3) + ')'; ctx.stroke();
      }
      for (const c of contacts) {
        ctx.beginPath(); ctx.arc(c.x - r.left, c.y - r.top, 18, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + inkRGB + ',0.12)'; ctx.fill();
        ctx.lineWidth = 1.5; ctx.strokeStyle = 'rgba(' + inkRGB + ',0.85)'; ctx.stroke();
      }
    } else if (style === 'glow') {
      for (const c of contacts) {
        const x = c.x - r.left, y = c.y - r.top;
        const g = ctx.createRadialGradient(x, y, 0, x, y, 70);
        g.addColorStop(0, 'rgba(' + inkRGB + ',0.45)'); g.addColorStop(1, 'rgba(' + inkRGB + ',0)');
        ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, 70, 0, Math.PI * 2); ctx.fill();
      }
    } else if (style === 'comet') {
      for (const p of trail) {
        const a = 1 - (now - p.t) / life;
        ctx.beginPath(); ctx.arc(p.x - r.left, p.y - r.top, 2 + 6 * a, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + inkRGB + ',' + (0.55 * a).toFixed(3) + ')'; ctx.fill();
      }
      for (const c of contacts) {
        ctx.beginPath(); ctx.arc(c.x - r.left, c.y - r.top, 7, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(' + inkRGB + ',0.95)'; ctx.fill();
      }
    }
    if (contacts.length || trail.length) inkRaf = requestAnimationFrame(drawInk);
  }
  function setContacts(list) {
    if ((eff.inkStyle || 'rings') === 'off') return;
    const now = performance.now();
    for (const c of list) trail.push({ x: c.x, y: c.y, t: now });
    if (trail.length > 300) trail.splice(0, trail.length - 300);
    contacts = list;
    if (!inkRaf) inkRaf = requestAnimationFrame(drawInk);
  }

  // ------------------------------------------------------------ gestures
  const hint = $('hint');
  let hinted = false;
  function hideHint() { if (!hinted) { hinted = true; hint.classList.add('gone'); } }

  const sink = {
    move(dx, dy) { hideHint(); sendDelta(1, dx, dy); },
    moveEnd() { if (ws && ws.readyState === 1) ws.send(binEnd); },
    scroll(dx, dy) { hideHint(); sendDelta(2, dx, dy); },
    scrollEnd() { send({ t: 'se' }); },
    zoom(d) { send({ t: 'z', d }); buzz(6); },
    click(b, n) { hideHint(); send({ t: 'c', b, n }); buzz(8); },
    button(b, down) { send({ t: 'b', b, s: down ? 1 : 0 }); if (down) buzz(12); },
    action(a) { send({ t: 'a', a }); buzz(14); },
    switcher(p, d) { send({ t: 'g', g: 'switchapp', p, d }); if (p !== 'end') buzz(10); },
    contacts: setContacts,
  };
  const surface = $('surface');
  const engine = new window.GestureEngine(surface, sink, () => eff);

  // ------------------------------------------------------------ orientation
  // 'auto' trusts the OS. A manual choice first asks the browser to lock the
  // screen; if that is refused (rotation locked, iPhone Safari) the page stays
  // as it is and touch coordinates are rotated instead, so holding the phone
  // sideways still moves the cursor the way your hand moves.
  const ROTATE = {
    'landscape-left':  (x, y) => ({ x: -y, y: x }),   // top of the phone points left
    'landscape-right': (x, y) => ({ x: y, y: -x }),   // top of the phone points right
  };
  function pageIsLandscape() { return window.innerWidth > window.innerHeight; }
  async function applyOrientation() {
    const want = eff.orientation || 'auto';
    const so = screen.orientation;
    document.body.dataset.orientation = want;
    if (want === 'auto') {
      engine.setTransform(null);
      if (so && so.unlock) { try { so.unlock(); } catch (e) { /* ignore */ } }
      return;
    }
    const target = want === 'portrait' ? 'portrait-primary' : (want === 'landscape-left' ? 'landscape-primary' : 'landscape-secondary');
    if (so && so.lock) { try { await so.lock(target); } catch (e) { /* not allowed here */ } }
    // Did the page end up the way the user wants? Then no transform is needed.
    const wantLandscape = want !== 'portrait';
    if (pageIsLandscape() === wantLandscape) { engine.setTransform(null); return; }
    engine.setTransform(wantLandscape ? ROTATE[want] : null);
  }
  const ORIENT_CYCLE = ['auto', 'landscape-left', 'landscape-right', 'portrait'];
  const ORIENT_LABEL = { auto: 'Rotates with the phone', 'landscape-left': 'Landscape, top to the left', 'landscape-right': 'Landscape, top to the right', portrait: 'Portrait' };
  const rotateBtn = $('rotate-btn');
  let statusHold = 0;
  function paintRotate() { rotateBtn.classList.toggle('on', (eff.orientation || 'auto') !== 'auto'); }
  rotateBtn.addEventListener('click', () => {
    const cur = eff.orientation || 'auto';
    const next = ORIENT_CYCLE[(ORIENT_CYCLE.indexOf(cur) + 1) % ORIENT_CYCLE.length];
    update({ orientation: next });
    buzz(8);
    clearTimeout(statusHold);
    const keep = statusEl.textContent, ok = statusEl.classList.contains('ok');
    setStatus(ORIENT_LABEL[next], false);
    statusHold = setTimeout(() => setStatus(keep, ok), 1400);
  });
  window.addEventListener('resize', () => { applyOrientation(); });
  document.addEventListener('fullscreenchange', () => { applyOrientation(); });

  surface.addEventListener('touchend', function goFull() {
    surface.removeEventListener('touchend', goFull);
    const el = document.documentElement;
    if (el.requestFullscreen && !document.fullscreenElement) el.requestFullscreen().catch(() => { /* fine */ });
  });

  // ------------------------------------------------------------ scroll strip
  // One finger in the lane on the right edge scrolls; a flick keeps going.
  const strip = $('strip'), stripThumb = $('strip-thumb');
  let stripY = 0, stripT = 0, stripV = 0, stripRaf = 0, stripTouch = null;
  const stripGain = () => 1.6 * (eff.scroll || 1);
  function stripStop() { if (stripRaf) { cancelAnimationFrame(stripRaf); stripRaf = 0; } }
  function stripCoast() {
    stripRaf = 0;
    const now = performance.now(), dt = Math.min(40, now - stripT); stripT = now;
    const dy = stripV * dt;
    if (Math.abs(stripV) < 0.05) { sink.scrollEnd(); strip.classList.remove('active'); return; }
    sendDelta(2, 0, dy * stripGain());
    stripV *= Math.pow(0.93, dt / 16);
    stripRaf = requestAnimationFrame(stripCoast);
  }
  function stripPlaceThumb(clientY) {
    const r = strip.getBoundingClientRect();
    const y = Math.min(r.height - 30, Math.max(30, clientY - r.top));
    stripThumb.style.top = y + 'px';
  }
  strip.addEventListener('touchstart', e => {
    e.preventDefault(); e.stopPropagation();
    if (stripTouch !== null) return;
    stripStop();
    const t = e.changedTouches[0];
    stripTouch = t.identifier; stripY = t.clientY; stripT = performance.now(); stripV = 0;
    strip.classList.add('active'); stripPlaceThumb(t.clientY); hideHint();
  }, { passive: false });
  strip.addEventListener('touchmove', e => {
    e.preventDefault(); e.stopPropagation();
    for (const t of e.changedTouches) {
      if (t.identifier !== stripTouch) continue;
      const now = performance.now(), dt = Math.max(1, now - stripT);
      const dy = t.clientY - stripY;
      stripV = 0.6 * stripV + 0.4 * (dy / dt);
      stripY = t.clientY; stripT = now;
      stripPlaceThumb(t.clientY);
      sendDelta(2, 0, dy * stripGain());
    }
  }, { passive: false });
  const stripEnd = e => {
    e.preventDefault(); e.stopPropagation();
    for (const t of e.changedTouches) {
      if (t.identifier !== stripTouch) continue;
      stripTouch = null;
      if (Math.abs(stripV) > 0.15 && e.type === 'touchend') { stripT = performance.now(); stripRaf = requestAnimationFrame(stripCoast); }
      else { sink.scrollEnd(); strip.classList.remove('active'); }
    }
  };
  strip.addEventListener('touchend', stripEnd, { passive: false });
  strip.addEventListener('touchcancel', stripEnd, { passive: false });

  // ------------------------------------------------------------ physical buttons
  const buttonsEl = $('buttons');
  for (const btn of buttonsEl.querySelectorAll('.mbtn')) {
    const b = btn.dataset.btn;
    btn.addEventListener('touchstart', e => { e.preventDefault(); btn.classList.add('down'); send({ t: 'b', b, s: 1 }); buzz(8); }, { passive: false });
    const up = e => { e.preventDefault(); btn.classList.remove('down'); send({ t: 'b', b, s: 0 }); };
    btn.addEventListener('touchend', up, { passive: false });
    btn.addEventListener('touchcancel', up, { passive: false });
  }

  // ------------------------------------------------------------ keyboard
  const typer = $('typer'), kbdBtn = $('kbd-btn');
  const SENTINEL = ' ';
  typer.value = SENTINEL;
  // Explicit on/off state. Tapping the button must not steal focus first,
  // otherwise the blur would read as "closed" and the tap would reopen it.
  let kbdOn = false;
  function setKeyboard(on) {
    kbdOn = on;
    kbdBtn.classList.toggle('on', on);
    if (on) { typer.focus({ preventScroll: true }); typer.setSelectionRange(1, 1); }
    else typer.blur();
  }
  // Toggle on touchend (still a user gesture, so focus() may open the keyboard)
  // and cancel the follow-up click; on desktop the click path is used instead.
  kbdBtn.addEventListener('mousedown', e => e.preventDefault());
  kbdBtn.addEventListener('touchend', e => { e.preventDefault(); setKeyboard(!kbdOn); }, { passive: false });
  kbdBtn.addEventListener('click', () => setKeyboard(!kbdOn));
  // Dismissed with the phone's back gesture: the viewport grows back, focus may linger.
  if (window.visualViewport) {
    let lastH = window.visualViewport.height;
    window.visualViewport.addEventListener('resize', () => {
      const h = window.visualViewport.height;
      if (kbdOn && h > lastH + 120) setKeyboard(false);
      lastH = h;
    });
  }
  typer.addEventListener('blur', () => { if (kbdOn) kbdBtn.classList.remove('on'); });
  typer.addEventListener('beforeinput', e => {
    if (e.inputType === 'insertLineBreak' || e.inputType === 'insertParagraph') { e.preventDefault(); send({ t: 'k', k: 'enter' }); }
  });
  typer.addEventListener('input', () => {
    const v = typer.value;
    if (v.length < SENTINEL.length) send({ t: 'k', k: 'backspace' });
    else if (v.length > SENTINEL.length) { const typed = v.slice(SENTINEL.length); if (typed) send({ t: 'txt', s: typed }); }
    typer.value = SENTINEL; typer.setSelectionRange(1, 1);
  });
  typer.addEventListener('keydown', e => {
    const map = { Tab: 'tab', Escape: 'esc', ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Delete: 'delete' };
    if (map[e.key]) { e.preventDefault(); send({ t: 'k', k: map[e.key] }); }
  });

  // ------------------------------------------------------------ keep awake
  async function keepAwake() {
    if (!eff.keepAwake || !('wakeLock' in navigator)) return;
    try { await navigator.wakeLock.request('screen'); } catch (e) { /* not granted */ }
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') keepAwake(); });
  keepAwake();

  // ------------------------------------------------------------ settings state
  function hexToRgb(hex) {
    const m = /^#?([0-9a-f]{6})$/i.exec(hex || '');
    if (!m) return null;
    const n = parseInt(m[1], 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }
  function applyTheme() {
    const t = S.THEMES[eff.theme] || S.THEMES.graphite;
    const accent = hexToRgb(eff.accent) ? eff.accent : t.accent;
    const rgb = hexToRgb(accent) || [240, 178, 60];
    const lum = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
    const rs = document.documentElement.style;
    rs.setProperty('--bg', t.bg); rs.setProperty('--pad', t.pad); rs.setProperty('--pad-edge', t.edge); rs.setProperty('--edge', t.edge);
    rs.setProperty('--panel', t.panel); rs.setProperty('--panel-2', t.panel2); rs.setProperty('--line', t.line);
    rs.setProperty('--text', t.text); rs.setProperty('--muted', t.muted); rs.setProperty('--faint', t.faint);
    rs.setProperty('--accent', accent);
    rs.setProperty('--accent-soft', 'rgba(' + rgb.join(',') + ',0.16)');
    rs.setProperty('--accent-ink', lum > 0.6 ? '#141414' : '#ffffff');
    inkRGB = rgb.join(',');
    document.body.dataset.texture = eff.texture || 'plain';
    document.body.dataset.corners = eff.corners || 'round';
    if (t.light) document.body.dataset.light = ''; else delete document.body.dataset.light;
    const meta = document.querySelector('meta[name="theme-color"]'); if (meta) meta.setAttribute('content', t.bg);
  }
  function recompute() {
    eff = S.effective(user, system);
    buttonsEl.hidden = !eff.buttons;
    strip.hidden = eff.scrollStrip === false;
    document.body.dataset.strip = strip.hidden ? 'off' : 'on';
    sendCfg();
    applyTheme();
    if ((eff.inkStyle || 'rings') === 'off') { contacts = []; trail = []; drawInk(); }
    resizeCanvas();
    if (typeof applyOrientation === 'function') { applyOrientation(); paintRotate(); }
  }
  function update(patch) { user = Object.assign({}, user, patch); S.save(user); recompute(); }
  recompute();

  // ------------------------------------------------------------ DOM helpers
  const checkIcon = () => $('tpl-check').content.firstElementChild.cloneNode(true);
  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'text') e.textContent = v;
      else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
      else if (v === false || v == null) continue;
      else e.setAttribute(k, v === true ? '' : v);
    }
    for (const c of children || []) if (c) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    return e;
  }
  const labelOf = name => {
    if (name === 'leftclick') return 'Left click';
    if (name === 'rightclick') return 'Right click';
    if (name === 'middleclick') return 'Middle click';
    if (typeof name === 'string' && name.startsWith('keys:')) return 'Shortcut ' + name.slice(5);
    const a = actionsCatalog.find(x => x.name === name);
    return a ? a.label : (name === 'none' ? 'Nothing' : String(name));
  };
  const synced = k => eff.synced && eff.synced.includes(k);
  const tagPC = k => synced(k) ? el('span', { class: 'tag', text: 'PC' }) : null;

  function lbl(title, sub, k) {
    return el('div', { class: 'lbl' }, [el('b', {}, [title, tagPC(k)]), sub ? el('small', { text: sub }) : null]);
  }
  function group(title, rows) {
    return el('div', {}, [el('p', { class: 'group-title', text: title }), el('div', { class: 'group' }, rows)]);
  }
  function toggle(title, sub, k) {
    const dis = synced(k);
    const sw = el('button', { class: 'switch', role: 'switch', 'aria-checked': String(!!eff[k]), 'aria-label': title, disabled: dis,
      onclick: () => { update({ [k]: !user[k] }); sw.setAttribute('aria-checked', String(!!eff[k])); } });
    return el('div', { class: 'row' }, [lbl(title, sub, k), sw]);
  }
  function slider(title, sub, k, min, max, step, fmt) {
    const dis = synced(k);
    const val = el('span', { class: 'val', text: fmt(eff[k]) });
    const input = el('input', { type: 'range', min, max, step, value: eff[k], disabled: dis, 'aria-label': title });
    const paint = () => input.style.setProperty('--pct', ((input.value - min) / (max - min) * 100) + '%');
    input.addEventListener('input', () => { val.textContent = fmt(+input.value); paint(); });
    input.addEventListener('change', () => update({ [k]: +input.value }));
    paint();
    return el('div', { class: 'row' }, [el('div', { class: 'slider' }, [
      el('div', { class: 'slider-top' }, [lbl(title, sub, k), val]), input])]);
  }
  function choice(title, k, current, options, onpick) {
    const dis = synced(k);
    const btn = el('button', { class: 'vbtn', disabled: dis, onclick: () => openPicker(title, current, options, onpick) },
      [el('span', { text: labelOf(current) })]);
    return el('div', { class: 'row' }, [lbl(title, null, k), btn]);
  }

  // ------------------------------------------------------------ picker
  const picker = $('picker'), pickerList = $('picker-list');
  function openPicker(title, current, options, onpick) {
    $('picker-title').textContent = title;
    pickerList.textContent = '';
    for (const [value, text] of options) {
      pickerList.appendChild(el('button', { class: 'opt' + (value === current ? ' on' : ''), role: 'option', 'aria-selected': String(value === current),
        onclick: () => { picker.hidden = true; onpick(value); renderSheet(); } }, [el('span', { text }), checkIcon()]));
    }
    picker.hidden = false;
  }
  $('picker-close').addEventListener('click', () => { picker.hidden = true; });

  const clickOptions = [['leftclick', 'Left click'], ['rightclick', 'Right click'], ['middleclick', 'Middle click']];
  function tapOptions() {
    const rest = actionsCatalog.filter(a => !['leftclick', 'rightclick', 'middleclick'].includes(a.name)).map(a => [a.name, a.label]);
    return clickOptions.concat(rest.length ? rest : [['none', 'Nothing']]);
  }
  function swipeOptions() { return actionsCatalog.length ? actionsCatalog.map(a => [a.name, a.label]) : [['none', 'Nothing']]; }

  // ------------------------------------------------------------ sheet
  const sheet = $('sheet'), body = $('sheet-body');
  $('settings-btn').addEventListener('click', () => { renderSheet(); sheet.hidden = false; });
  $('sheet-close').addEventListener('click', () => { sheet.hidden = true; picker.hidden = true; });

  function matchBlock() {
    const sw = el('button', { class: 'switch', role: 'switch', 'aria-checked': String(!!user.matchPC), 'aria-label': 'Match this PC',
      onclick: () => { update({ matchPC: !user.matchPC }); renderSheet(); } });
    const desc = user.matchPC ? S.describeSystem(system) : 'Off. Using the settings below.';
    return el('div', { class: 'match' }, [el('div', { class: 'lbl' }, [el('b', { text: 'Match this PC’s touchpad' }), el('small', { text: desc })]), sw]);
  }

  function swipeGroup(title, k) {
    const map = eff[k];
    const current = S.presetOf(map);
    const dis = synced(k);
    const segs = el('div', { class: 'segs' }, Object.entries(S.SWIPE_PRESETS).map(([name, p]) =>
      el('button', { class: 'seg' + (current === name ? ' on' : ''), text: p.label, disabled: dis,
        onclick: () => { update({ [k]: Object.assign({}, p.map) }); renderSheet(); } })));
    const dirs = el('div', { class: 'dirs' }, ['up', 'down', 'left', 'right'].map(d =>
      choice(d[0].toUpperCase() + d.slice(1), k, map[d], swipeOptions(), v => update({ [k]: Object.assign({}, user[k], { [d]: v }) }))));
    const custom = dis ? null : el('input', { class: 'textfield', placeholder: 'Shortcut for Up, e.g. ctrl+shift+t', 'aria-label': 'Custom shortcut',
      onchange: e => { const v = e.target.value.trim(); if (v) { update({ [k]: Object.assign({}, user[k], { up: 'keys:' + v }) }); renderSheet(); } } });
    return group(title, [segs, dirs, custom]);
  }

  function segs(k, options, cls) {
    return el('div', { class: 'segs ' + (cls || '') }, options.map(([v, text]) =>
      el('button', { class: 'seg' + (String(eff[k]) === String(v) ? ' on' : ''), text, onclick: () => { update({ [k]: v }); renderSheet(); } })));
  }
  function appearanceGroup() {
    const swatches = el('div', { class: 'swatches' }, Object.entries(S.THEMES).map(([name, t]) => {
      const b = el('button', { class: 'swatch' + (eff.theme === name ? ' on' : ''), text: t.label,
        onclick: () => { update({ theme: name, accent: '' }); renderSheet(); } });
      b.style.setProperty('--sw-bg', t.pad); b.style.setProperty('--sw-text', t.text); b.style.setProperty('--sw-accent', t.accent);
      return b;
    }));
    const t = S.THEMES[eff.theme] || S.THEMES.graphite;
    const color = el('input', { type: 'color', value: hexToRgb(eff.accent) ? eff.accent : t.accent, 'aria-label': 'Accent colour',
      onchange: e => { update({ accent: e.target.value }); renderSheet(); } });
    const reset = eff.accent ? el('button', { class: 'link', text: 'Use theme colour', onclick: () => { update({ accent: '' }); renderSheet(); } }) : null;
    return group('Appearance', [
      swatches,
      el('div', { class: 'row' }, [lbl('Accent colour', 'Touch ink, switches, highlights'), el('div', { class: 'colorwrap' }, [reset, color])]),
      el('div', { class: 'row' }, [lbl('Pad surface')]),
      segs('texture', [['plain', 'Plain'], ['grid', 'Grid'], ['dots', 'Dots'], ['carbon', 'Carbon']], 'four'),
      el('div', { class: 'row' }, [lbl('Touch effect')]),
      segs('inkStyle', [['rings', 'Rings'], ['glow', 'Glow'], ['comet', 'Comet'], ['off', 'Off']], 'four'),
      el('div', { class: 'row' }, [lbl('Corners')]),
      segs('corners', [['round', 'Round'], ['sharp', 'Sharp']], ''),
      el('div', { class: 'row' }, [lbl('Vibration', 'Android only')]),
      segs('haptics', [[0, 'Off'], [0.5, 'Light'], [1, 'Normal'], [2, 'Strong']], 'four'),
    ]);
  }
  function renderSheet() {
    body.textContent = '';
    body.appendChild(matchBlock());
    body.appendChild(group('Pointer', [
      slider('Speed', null, 'speed', 0.25, 3.5, 0.05, v => v.toFixed(2) + '×'),
      slider('Acceleration', 'Fast flicks travel further', 'accel', 0, 1, 0.05, v => Math.round(v * 100) + '%'),
      toggle('Double tap to drag', 'Tap, then tap and hold', 'dragOnDoubleTap'),
      toggle('Three finger drag', 'Replaces three finger swipes', 'threeFingerDrag'),
    ]));
    body.appendChild(group('Scroll and zoom', [
      toggle('Two finger scroll', null, 'pan'),
      slider('Scroll speed', null, 'scroll', 0.3, 3, 0.1, v => v.toFixed(1) + '×'),
      toggle('Natural scrolling', 'Content follows your fingers', 'natural'),
      toggle('Pinch to zoom', null, 'zoom'),
      toggle('Whole notches only', 'For apps that ignore smooth scrolling', 'notched'),
    ]));
    body.appendChild(group('Taps', [
      choice('One finger', 'tap1', eff.tap1, [['leftclick', 'Left click'], ['none', 'Nothing']], v => update({ tap1: v })),
      choice('Two fingers', 'tap2', eff.tap2, tapOptions(), v => update({ tap2: v })),
      choice('Three fingers', 'tap3', eff.tap3, tapOptions(), v => update({ tap3: v })),
      choice('Four fingers', 'tap4', eff.tap4, tapOptions(), v => update({ tap4: v })),
    ]));
    body.appendChild(swipeGroup('Three finger swipes', 'swipe3'));
    body.appendChild(swipeGroup('Four finger swipes', 'swipe4'));
    const ORIENT = [['auto', 'Rotate with the phone'], ['portrait', 'Portrait'], ['landscape-left', 'Landscape, top to the left'], ['landscape-right', 'Landscape, top to the right']];
    const orientRow = choice('Orientation', 'orientation', eff.orientation || 'auto', ORIENT, v => update({ orientation: v }));
    orientRow.querySelector('.vbtn span').textContent = (ORIENT.find(o => o[0] === (eff.orientation || 'auto')) || ORIENT[0])[1];
    body.appendChild(appearanceGroup());
    body.appendChild(group('Surface', [
      orientRow,
      toggle('Scroll strip', 'Lane on the right edge; flick to coast', 'scrollStrip'),
      toggle('Mouse buttons', 'Left and right under the pad', 'buttons'),
      toggle('Keep screen on', null, 'keepAwake'),
      el('div', { class: 'row' }, [lbl('Reset phone settings', 'PC sync stays on'), el('button', { class: 'link-danger', text: 'Reset',
        onclick: () => { update(Object.assign({}, S.DEFAULTS)); renderSheet(); } })]),
    ]));
    if (!actionsCatalog.length) body.appendChild(el('p', { class: 'note', text: 'The action list arrives from the PC once connected.' }));
  }

  // ------------------------------------------------------------ start
  if (!key) {
    showOverlay('Open the link from the host', 'The address printed by the host includes a pairing key such as ?k=123456. Scan its QR code.');
    setStatus('Not paired', false);
  } else {
    connect();
  }
})();
