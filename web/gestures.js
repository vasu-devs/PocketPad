/* Gesture engine: raw touches in, semantic pointer events out.

   Sink interface (all methods optional):
     move(dx, dy)          accelerated pointer delta in px
     scroll(dx, dy)        two-finger scroll delta in raw px
     scrollEnd()
     zoom(dir)             +1 in, -1 out
     click(button, n)      tap; button = left|right|middle
     button(button, down)  press / release (drag)
     action(name)          named action from settings
     contacts(list)        [{x, y}] active touches, for the ink layer
*/
(function () {
  'use strict';

  const TAP_MAX_MS = 260;
  const TAP_MAX_MOVE = 12;
  const DOUBLE_TAP_MS = 320;
  const DOUBLE_TAP_RADIUS = 48;
  const SWIPE_TRIGGER = 56;
  const SWIPE_REPEAT = 130;
  const PINCH_TRIGGER = 28;
  const PINCH_STEP = 0.16;
  const SCROLL_TRIGGER = 6;
  const MOVE_DEADZONE = 1.5;

  // Speed in px/ms below which no acceleration applies and above which it maxes out.
  const ACCEL_LOW = 0.12;
  const ACCEL_HIGH = 1.4;

  function smoothstep(lo, hi, x) {
    const t = Math.min(1, Math.max(0, (x - lo) / (hi - lo)));
    return t * t * (3 - 2 * t);
  }

  function gain(speedPxPerMs, s) {
    const base = 0.9 * s.speed;
    const k = smoothstep(ACCEL_LOW, ACCEL_HIGH, speedPxPerMs);
    return base * (1 + 2.2 * s.accel * k);
  }

  function centroid(list) {
    let x = 0, y = 0;
    for (const t of list) { x += t.x; y += t.y; }
    return { x: x / list.length, y: y / list.length };
  }

  function spread(list) {
    if (list.length < 2) return 0;
    const dx = list[0].x - list[1].x, dy = list[0].y - list[1].y;
    return Math.hypot(dx, dy);
  }

  class GestureEngine {
    constructor(el, sink, getSettings) {
      this.el = el;
      this.sink = sink;
      this.getSettings = getSettings;
      this.touches = new Map();
      this.g = null;
      this.lastTap = null;
      this.raf = 0;
      this.pendingMove = { x: 0, y: 0 };

      const opts = { passive: false };
      el.addEventListener('touchstart', e => this.onStart(e), opts);
      el.addEventListener('touchmove', e => this.onMove(e), opts);
      el.addEventListener('touchend', e => this.onEnd(e), opts);
      el.addEventListener('touchcancel', e => this.onEnd(e), opts);
    }

    _emit(name, ...args) {
      const fn = this.sink[name];
      if (fn) fn.apply(this.sink, args);
    }

    _list() { return Array.from(this.touches.values()); }

    _contacts() {
      this._emit('contacts', this._list().map(t => ({ x: t.x, y: t.y })));
    }

    onStart(e) {
      e.preventDefault();
      const now = performance.now();
      for (const t of e.changedTouches) {
        this.touches.set(t.identifier, { x: t.clientX, y: t.clientY, t: now });
      }
      const list = this._list();
      const c = centroid(list);
      if (!this.g) {
        const s = this.getSettings();
        const lt = this.lastTap;
        const dragArmed = !!(s.dragOnDoubleTap && lt && lt.fingers === 1 && list.length === 1 &&
          now - lt.t < DOUBLE_TAP_MS && Math.hypot(c.x - lt.x, c.y - lt.y) < DOUBLE_TAP_RADIUS);
        this.g = {
          start: now, fingersMax: list.length, mode: null, moved: 0,
          origin: c, last: c, lastT: now, spread0: spread(list), lastSpread: spread(list),
          zoomAcc: 0, dragArmed, swipeAxisOrigin: null,
        };
      } else {
        // Extra finger landed: re-anchor so the jump in centroid is not a move.
        this.g.fingersMax = Math.max(this.g.fingersMax, list.length);
        this.g.origin = c; this.g.last = c;
        this.g.spread0 = this.g.lastSpread = spread(list);
        if (this.g.mode === 'move' || this.g.mode === 'scroll' || this.g.mode === 'pinch') {
          // Windows keeps the gesture; we do too but restart the decision.
          if (list.length !== (this.g.mode === 'move' ? 1 : 2)) this.g.mode = null;
        }
      }
      this._contacts();
    }

    onMove(e) {
      e.preventDefault();
      const g = this.g;
      if (!g) return;
      const now = performance.now();
      for (const t of e.changedTouches) {
        const rec = this.touches.get(t.identifier);
        if (rec) { rec.x = t.clientX; rec.y = t.clientY; }
      }
      const list = this._list();
      const n = list.length;
      const c = centroid(list);
      const dx = c.x - g.last.x, dy = c.y - g.last.y;
      const dt = Math.max(1, now - g.lastT);
      g.last = c; g.lastT = now;
      g.moved = Math.max(g.moved, Math.hypot(c.x - g.origin.x, c.y - g.origin.y));
      const s = this.getSettings();
      this._contacts();

      // Decide the mode once movement is unambiguous.
      if (g.mode === null) {
        if (n === 1 && g.fingersMax === 1) {
          if (g.moved > MOVE_DEADZONE) g.mode = g.dragArmed ? 'drag' : 'move';
          if (g.mode === 'drag') this._emit('button', 'left', true);
        } else if (n === 2 && g.fingersMax === 2) {
          const sp = spread(list);
          const dSpread = Math.abs(sp - g.spread0);
          if (dSpread > PINCH_TRIGGER && dSpread > g.moved) { g.mode = 'pinch'; g.lastSpread = sp; }
          else if (g.moved > SCROLL_TRIGGER) g.mode = 'scroll';
        } else if (n >= 3) {
          if (n === 3 && s.threeFingerDrag) {
            if (g.moved > MOVE_DEADZONE) { g.mode = 'drag'; this._emit('button', 'left', true); }
          } else if (g.moved > SWIPE_TRIGGER) {
            g.mode = 'swipe';
            this._fireSwipe(g, c, n >= 4 ? 4 : 3, s);
          }
        } else if (n < g.fingersMax && g.moved > TAP_MAX_MOVE) {
          g.mode = 'dead'; // fingers lifted, then the rest wandered: not a tap
        }
        if (g.mode === null) return;
      }

      switch (g.mode) {
        case 'move':
        case 'drag': {
          const speed = Math.hypot(dx, dy) / dt;
          const k = gain(speed, s);
          this.pendingMove.x += dx * k;
          this.pendingMove.y += dy * k;
          this._flushSoon();
          break;
        }
        case 'scroll':
          this._emit('scroll', dx * s.scroll, dy * s.scroll);
          break;
        case 'pinch': {
          const sp = spread(list);
          if (g.lastSpread > 0 && sp > 0) {
            g.zoomAcc += Math.log(sp / g.lastSpread);
            g.lastSpread = sp;
            while (g.zoomAcc >= PINCH_STEP) { g.zoomAcc -= PINCH_STEP; this._emit('zoom', 1); }
            while (g.zoomAcc <= -PINCH_STEP) { g.zoomAcc += PINCH_STEP; this._emit('zoom', -1); }
          }
          break;
        }
        case 'swipe': {
          // Horizontal swipes repeat as the fingers keep travelling (app / desktop switching).
          if (g.swipeAxisOrigin && g.swipeHorizontal) {
            const travel = c.x - g.swipeAxisOrigin.x;
            if (Math.abs(travel) > SWIPE_REPEAT) this._fireSwipe(g, c, g.swipeFingers, s);
          }
          break;
        }
      }
    }

    _fireSwipe(g, c, fingers, s) {
      const dx = c.x - (g.swipeAxisOrigin ? g.swipeAxisOrigin.x : g.origin.x);
      const dy = c.y - (g.swipeAxisOrigin ? g.swipeAxisOrigin.y : g.origin.y);
      const horizontal = g.swipeAxisOrigin ? g.swipeHorizontal : Math.abs(dx) > Math.abs(dy);
      const dir = horizontal ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up');
      const map = fingers >= 4 ? s.swipe4 : s.swipe3;
      const action = map[dir] || 'none';
      g.swipeAxisOrigin = c; g.swipeHorizontal = horizontal; g.swipeFingers = fingers;
      if (action !== 'none') this._emit('action', action);
    }

    _flushSoon() {
      if (this.raf) return;
      this.raf = requestAnimationFrame(() => {
        this.raf = 0;
        const m = this.pendingMove;
        if (m.x || m.y) { this._emit('move', m.x, m.y); m.x = 0; m.y = 0; }
      });
    }

    onEnd(e) {
      e.preventDefault();
      const now = performance.now();
      for (const t of e.changedTouches) this.touches.delete(t.identifier);
      const g = this.g;
      this._contacts();
      if (!g) return;
      const remaining = this.touches.size;

      if (remaining > 0) {
        // Fingers rarely lift at the same instant. Re-anchor to the ones still
        // down so the centroid jump is not counted as movement, and let the
        // final lift decide whether this was a tap.
        const c = centroid(this._list());
        g.last = c; g.origin = c;
        return;
      }

      const s = this.getSettings();
      const duration = now - g.start;
      const isTap = g.mode === null && duration < TAP_MAX_MS && g.moved < TAP_MAX_MOVE;

      if (g.mode === 'drag') {
        this._flushNow();
        this._emit('button', 'left', false);
      } else if (g.mode === 'scroll') {
        this._emit('scrollEnd');
      } else if (isTap) {
        const n = Math.min(4, g.fingersMax);
        if (n === 1 && g.dragArmed) {
          // Second tap of a double tap that never moved: complete the double click.
          this._emit('click', 'left', 1);
          this.lastTap = null;
        } else {
          this._tapAction(n, s);
          this.lastTap = { t: now, x: g.origin.x, y: g.origin.y, fingers: n };
        }
      } else {
        this._flushNow();
      }
      this.g = null;
    }

    _flushNow() {
      if (this.raf) { cancelAnimationFrame(this.raf); this.raf = 0; }
      const m = this.pendingMove;
      if (m.x || m.y) { this._emit('move', m.x, m.y); m.x = 0; m.y = 0; }
    }

    _tapAction(n, s) {
      const name = s['tap' + n] || 'none';
      if (name === 'leftclick') this._emit('click', 'left', 1);
      else if (name === 'rightclick') this._emit('click', 'right', 1);
      else if (name === 'middleclick') this._emit('click', 'middle', 1);
      else if (name !== 'none') this._emit('action', name);
    }
  }

  window.GestureEngine = GestureEngine;
  window.GestureMath = { gain, smoothstep };
})();
