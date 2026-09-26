/* PocketPad phone app: connection, ink layer, buttons, keyboard, settings sheet. */
(function () {
  'use strict';

  const $ = id => document.getElementById(id);
  const S = window.PocketSettings;
  let settings = S.load();
  let actionsCatalog = [];

  // ------------------------------------------------------------ connection
  const key = new URLSearchParams(location.search).get('k') || '';
  const wsUrl = (location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws?k=' + encodeURIComponent(key);
  let ws = null, retryTimer = 0, pingTimer = 0, latency = null, lastPingId = 0, lastPingAt = 0;

  const statusEl = $('status'), overlay = $('overlay');

  function setStatus(text, ok) {
    statusEl.textContent = text;
    statusEl.classList.toggle('ok', !!ok);
  }

  function showOverlay(title, body) {
    $('overlay-title').textContent = title;
    $('overlay-body').textContent = body;
    overlay.hidden = false;
  }

  function connect() {
    clearTimeout(retryTimer);
    if (ws) { try { ws.close(); } catch (e) { /* ignore */ } }
    setStatus('Connecting', false);
    ws = new WebSocket(wsUrl);
    ws.onopen = () => {
      overlay.hidden = true;
      setStatus('Connected', true);
      sendCfg();
      clearInterval(pingTimer);
      pingTimer = setInterval(ping, 3000);
      ping();
    };
    ws.onmessage = ev => {
      let msg; try { msg = JSON.parse(ev.data); } catch (e) { return; }
      if (msg.t === 'hello' && Array.isArray(msg.actions)) {
        actionsCatalog = msg.actions;
        if (!$('sheet').hidden) renderSheet();
      } else if (msg.t === 'pong' && msg.id === lastPingId) {
        latency = Math.round(performance.now() - lastPingAt);
        setStatus('Connected, ' + latency + ' ms', true);
      }
    };
    ws.onclose = ev => {
      clearInterval(pingTimer);
      if (ev.code === 1008 || ev.code === 4403) {
        showOverlay('Wrong pairing key', 'Scan the QR code shown by the host again. The key changes every time the host starts.');
        setStatus('Not paired', false);
        return;
      }
      setStatus('Reconnecting', false);
      showOverlay('Lost the PC', 'Reconnecting. Check the host window on the laptop is still open.');
      retryTimer = setTimeout(connect, 1500);
    };
    ws.onerror = () => { /* onclose follows */ };
  }

  function send(obj) {
    if (ws && ws.readyState === 1) ws.send(JSON.stringify(obj));
  }

  function ping() {
    lastPingId += 1; lastPingAt = performance.now();
    send({ t: 'ping', id: lastPingId });
  }

  function sendCfg() {
    send({ t: 'cfg', scroll: 1, natural: settings.natural, notched: settings.notched });
  }

  $('retry-btn').addEventListener('click', connect);

  // ------------------------------------------------------------ haptics
  function buzz(ms) {
    if (settings.haptics && navigator.vibrate) { try { navigator.vibrate(ms); } catch (e) { /* ignore */ } }
  }

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

  function drawInk() {
    inkRaf = 0;
    const r = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, r.width, r.height);
    if (!settings.ink) return;
    const now = performance.now();
    trail = trail.filter(p => now - p.t < 420);
    for (const p of trail) {
      const a = 1 - (now - p.t) / 420;
      ctx.beginPath(); ctx.arc(p.x - r.left, p.y - r.top, 6 + 10 * (1 - a), 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(242,180,65,' + (0.35 * a).toFixed(3) + ')'; ctx.lineWidth = 1.5; ctx.stroke();
    }
    for (const c of contacts) {
      ctx.beginPath(); ctx.arc(c.x - r.left, c.y - r.top, 22, 0, Math.PI * 2);
      ctx.fillStyle = 'rgba(242,180,65,0.14)'; ctx.fill();
      ctx.beginPath(); ctx.arc(c.x - r.left, c.y - r.top, 22, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(242,180,65,0.9)'; ctx.lineWidth = 2; ctx.stroke();
    }
    if (contacts.length || trail.length) inkRaf = requestAnimationFrame(drawInk);
  }

  function setContacts(list) {
    if (!settings.ink) return;
    const now = performance.now();
    for (const c of list) trail.push({ x: c.x, y: c.y, t: now });
    if (trail.length > 400) trail.splice(0, trail.length - 400);
    contacts = list;
    if (!inkRaf) inkRaf = requestAnimationFrame(drawInk);
  }

  // ------------------------------------------------------------ gesture sink
  const hint = $('hint');
  let hinted = false;
  function hideHint() { if (!hinted) { hinted = true; hint.classList.add('gone'); } }

  const sink = {
    move(dx, dy) { hideHint(); send({ t: 'm', x: +dx.toFixed(2), y: +dy.toFixed(2) }); },
    scroll(dx, dy) { hideHint(); send({ t: 's', x: +dx.toFixed(2), y: +dy.toFixed(2) }); },
    scrollEnd() { send({ t: 'se' }); },
    zoom(d) { send({ t: 'z', d }); buzz(6); },
    click(b, n) { hideHint(); send({ t: 'c', b, n }); buzz(8); },
    button(b, down) { send({ t: 'b', b, s: down ? 1 : 0 }); if (down) buzz(12); },
    action(a) { send({ t: 'a', a }); buzz(14); },
    contacts: setContacts,
  };

  const surface = $('surface');
  new window.GestureEngine(surface, sink, () => settings);

  // Fullscreen on the first real touch (Android). iPhones use Add to Home Screen.
  surface.addEventListener('touchend', function goFull() {
    surface.removeEventListener('touchend', goFull);
    const el = document.documentElement;
    if (el.requestFullscreen && !document.fullscreenElement) el.requestFullscreen().catch(() => { /* fine */ });
  });

  // ------------------------------------------------------------ on-screen buttons
  const buttonsEl = $('buttons');
  for (const btn of buttonsEl.querySelectorAll('.mbtn')) {
    const b = btn.dataset.btn;
    btn.addEventListener('touchstart', e => { e.preventDefault(); btn.classList.add('down'); send({ t: 'b', b, s: 1 }); buzz(8); }, { passive: false });
    const up = e => { e.preventDefault(); btn.classList.remove('down'); send({ t: 'b', b, s: 0 }); };
    btn.addEventListener('touchend', up, { passive: false });
    btn.addEventListener('touchcancel', up, { passive: false });
  }

  // ------------------------------------------------------------ keyboard typing
  const typer = $('typer'), kbdBtn = $('kbd-btn');
  const SENTINEL = ' ';
  typer.value = SENTINEL;
  kbdBtn.addEventListener('click', () => {
    if (document.activeElement === typer) { typer.blur(); }
    else { typer.focus(); typer.setSelectionRange(typer.value.length, typer.value.length); }
  });
  typer.addEventListener('focus', () => kbdBtn.classList.add('on'));
  typer.addEventListener('blur', () => kbdBtn.classList.remove('on'));
  typer.addEventListener('beforeinput', e => {
    if (e.inputType === 'insertLineBreak' || e.inputType === 'insertParagraph') {
      e.preventDefault(); send({ t: 'k', k: 'enter' });
    }
  });
  typer.addEventListener('input', () => {
    const v = typer.value;
    if (v.length < SENTINEL.length) {
      send({ t: 'k', k: 'backspace' });
    } else if (v.length > SENTINEL.length) {
      const typed = v.slice(SENTINEL.length);
      if (typed) send({ t: 'txt', s: typed });
    }
    typer.value = SENTINEL;
    typer.setSelectionRange(1, 1);
  });
  typer.addEventListener('keydown', e => {
    const map = { Tab: 'tab', Escape: 'esc', ArrowLeft: 'left', ArrowRight: 'right', ArrowUp: 'up', ArrowDown: 'down', Delete: 'delete' };
    if (map[e.key]) { e.preventDefault(); send({ t: 'k', k: map[e.key] }); }
  });

  // ------------------------------------------------------------ keep awake
  let wakeLock = null;
  async function keepAwake() {
    if (!settings.keepAwake || !('wakeLock' in navigator)) return;
    try { wakeLock = await navigator.wakeLock.request('screen'); } catch (e) { wakeLock = null; }
  }
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible') keepAwake(); });
  keepAwake();

  // ------------------------------------------------------------ settings sheet
  const sheet = $('sheet'), body = $('sheet-body');
  $('settings-btn').addEventListener('click', () => { renderSheet(); sheet.hidden = false; });
  $('sheet-close').addEventListener('click', () => { sheet.hidden = true; });

  function update(patch) {
    settings = Object.assign({}, settings, patch);
    S.save(settings);
    apply();
  }

  function apply() {
    buttonsEl.hidden = !settings.buttons;
    sendCfg();
    if (!settings.ink) { contacts = []; trail = []; drawInk(); }
    resizeCanvas();
  }
  apply();

  function tapOptions(n) {
    const clicks = [['leftclick', 'Left click'], ['rightclick', 'Right click'], ['middleclick', 'Middle click']];
    const rest = actionsCatalog.filter(a => !['leftclick', 'rightclick', 'middleclick'].includes(a.name))
      .map(a => [a.name, a.label]);
    return clicks.concat(rest.length ? rest : [['none', 'Nothing']]);
  }

  function swipeOptions() {
    const list = actionsCatalog.length ? actionsCatalog.map(a => [a.name, a.label]) : [['none', 'Nothing']];
    return list;
  }

  function el(tag, attrs, children) {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs || {})) {
      if (k === 'text') e.textContent = v; else if (k.startsWith('on')) e.addEventListener(k.slice(2), v); else e.setAttribute(k, v);
    }
    for (const c of children || []) e.appendChild(typeof c === 'string' ? document.createTextNode(c) : c);
    return e;
  }

  function group(title, rows) { return el('div', { class: 'group' }, [el('h3', { text: title })].concat(rows)); }

  function slider(label, sub, k, min, max, step, fmt) {
    const val = el('span', { class: 'val', text: fmt(settings[k]) });
    const input = el('input', { type: 'range', min, max, step, value: settings[k],
      oninput: e => { val.textContent = fmt(+e.target.value); },
      onchange: e => update({ [k]: +e.target.value }) });
    return el('div', { class: 'row' }, [el('label', {}, [label, el('span', { class: 'sub', text: sub })]), input, val]);
  }

  function toggle(label, sub, k) {
    const sw = el('button', { class: 'switch', role: 'switch', 'aria-checked': String(!!settings[k]), 'aria-label': label,
      onclick: () => { update({ [k]: !settings[k] }); sw.setAttribute('aria-checked', String(!!settings[k])); } });
    return el('div', { class: 'row' }, [el('label', {}, [label, el('span', { class: 'sub', text: sub })]), sw]);
  }

  function select(label, current, options, onchange) {
    const sel = el('select', { onchange: e => onchange(e.target.value) },
      options.map(([v, t]) => el('option', { value: v, text: t })));
    if (!options.some(([v]) => v === current)) sel.appendChild(el('option', { value: current, text: current }));
    sel.value = current;
    return el('div', { class: 'row' }, [el('label', { text: label }), sel]);
  }

  function swipeGroup(title, k) {
    const map = settings[k];
    const current = S.presetOf(map);
    const chips = el('div', { class: 'presets' }, Object.entries(S.SWIPE_PRESETS).map(([name, p]) =>
      el('button', { class: 'chip' + (current === name ? ' on' : ''), text: p.label,
        onclick: () => { update({ [k]: Object.assign({}, p.map) }); renderSheet(); } })));
    const dirs = el('div', { class: 'dirs' }, ['up', 'down', 'left', 'right'].map(d =>
      select(d[0].toUpperCase() + d.slice(1), map[d], swipeOptions(), v => {
        update({ [k]: Object.assign({}, settings[k], { [d]: v }) }); renderSheet();
      })));
    const custom = el('input', { class: 'custom', placeholder: 'Custom shortcut for Up, e.g. ctrl+shift+t', 'aria-label': 'Custom shortcut',
      onchange: e => { const v = e.target.value.trim(); if (v) { update({ [k]: Object.assign({}, settings[k], { up: 'keys:' + v }) }); renderSheet(); } } });
    return group(title, [chips, dirs, custom,
      el('p', { class: 'note', text: 'Left and right repeat while your fingers keep moving, so you can step through apps or desktops in one swipe.' })]);
  }

  function renderSheet() {
    body.textContent = '';
    body.appendChild(group('Pointer', [
      slider('Speed', 'How far the cursor travels', 'speed', 0.4, 4, 0.1, v => v.toFixed(1) + 'x'),
      slider('Acceleration', 'Fast flicks travel further', 'accel', 0, 1, 0.05, v => Math.round(v * 100) + '%'),
      toggle('Double tap to drag', 'Tap, then tap and hold to drag', 'dragOnDoubleTap'),
      toggle('Three finger drag', 'Replaces three finger swipes', 'threeFingerDrag'),
    ]));
    body.appendChild(group('Scroll and zoom', [
      slider('Scroll speed', 'Two fingers', 'scroll', 0.3, 3, 0.1, v => v.toFixed(1) + 'x'),
      toggle('Natural scrolling', 'Content follows your fingers', 'natural'),
      toggle('Whole notches only', 'For apps that ignore smooth scrolling', 'notched'),
      el('p', { class: 'note', text: 'Pinch with two fingers to zoom. Works anywhere Ctrl plus wheel does.' }),
    ]));
    body.appendChild(group('Taps', [
      select('One finger', settings.tap1, tapOptions(1), v => update({ tap1: v })),
      select('Two fingers', settings.tap2, tapOptions(2), v => update({ tap2: v })),
      select('Three fingers', settings.tap3, tapOptions(3), v => update({ tap3: v })),
      select('Four fingers', settings.tap4, tapOptions(4), v => update({ tap4: v })),
    ]));
    body.appendChild(swipeGroup('Three finger swipes', 'swipe3'));
    body.appendChild(swipeGroup('Four finger swipes', 'swipe4'));
    body.appendChild(group('Surface', [
      toggle('Mouse buttons', 'Left and right buttons under the pad', 'buttons'),
      toggle('Vibrate on clicks', 'Android only', 'haptics'),
      toggle('Show touches', 'Amber rings under your fingers', 'ink'),
      toggle('Keep screen on', 'While this page is open', 'keepAwake'),
      el('div', { class: 'row' }, [el('label', { text: 'Reset everything' }),
        el('button', { class: 'chip danger', text: 'Reset', onclick: () => { update(Object.assign({}, S.DEFAULTS)); renderSheet(); } })]),
    ]));
    if (!actionsCatalog.length) {
      body.appendChild(el('p', { class: 'note', text: 'Action list loads from the PC once connected.' }));
    }
  }

  // ------------------------------------------------------------ start
  if (!key) {
    showOverlay('Open the link from the host', 'The address printed by the host includes a pairing key, for example ?k=123456. Scan its QR code.');
    setStatus('Not paired', false);
  } else {
    connect();
  }
})();
