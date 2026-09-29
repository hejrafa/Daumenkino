const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync(require('node:path').join(__dirname, '../flipbook.js'), 'utf8');
const flush = () => new Promise(resolve => setImmediate(resolve));

function setup({ reduced = false, fail = false, pending = false, hover = true } = {}) {
  const listeners = {}, timers = new Map(), images = [], frames = [];
  let onView;
  let id = 0;
  const motion = { matches: reduced, addEventListener: (_, cb) => { motion.change = cb; } };
  const card = { dataset: { flipbook: '["a","b"]' }, hidden: false,
    addEventListener: (name, cb) => { listeners[name] = cb; }, append: frame => frames.push(frame) };
  const document = { hidden: false, querySelectorAll: () => [card], addEventListener() {} };
  class Image {
    constructor() { images.push(this); }
    setAttribute() {}
    decode() { return Promise.resolve(); }
    set src(value) {
      if (!pending) queueMicrotask(() => fail ? this.onerror?.() : this.onload?.());
    }
  }
  vm.runInNewContext(source, { document, navigator: {}, Image, window: { addEventListener() {} },
    matchMedia: query => query.includes('reduce') ? motion : { matches: hover, addEventListener() {} },
    setTimeout: (cb, ms) => { timers.set(++id, { cb, ms }); return id; }, clearTimeout: id => timers.delete(id),
    IntersectionObserver: class { constructor(cb) { onView = cb; } observe() {} }, MutationObserver: class { observe() {} } });
  return { card, frames, images, motion, timers,
    enter: (pointerType = 'mouse') => listeners.pointerenter({ pointerType }),
    leave: () => listeners.pointerleave(),
    view: () => onView([{ target: card, isIntersecting: true }]),
    tick: () => {
      const next = [...timers].find(([, value]) => value.ms === 650);
      if (next) { timers.delete(next[0]); next[1].cb(); }
    } };
}

test('flips immediately on hover, once, and restores cover', async () => {
  const h = setup();
  assert.equal(h.images.length, 0);
  await h.enter();
  assert.equal(h.frames[0].hidden, false);
  h.tick(); assert.equal(h.frames[0].hidden, true); assert.equal(h.frames[1].hidden, false);
  h.tick(); assert.ok(h.frames.every(frame => frame.hidden)); assert.equal(h.timers.size, 0);
  await h.enter(); assert.equal(h.frames[0].hidden, false); h.leave();
  assert.equal(h.images.length, 2); // Reuse already decoded stills.
  assert.ok(h.frames.every(frame => frame.hidden)); assert.equal(h.timers.size, 0);
});

test('stills preload when a card nears the screen, only on mouse devices', async () => {
  const h = setup(); h.view(); assert.equal(h.images.length, 2);
  await h.enter(); assert.equal(h.images.length, 2); assert.equal(h.frames[0].hidden, false);
  const touchOnly = setup({ hover: false }); touchOnly.view(); assert.equal(touchOnly.images.length, 0);
  const reduced = setup({ reduced: true }); reduced.view(); assert.equal(reduced.images.length, 0);
});

test('touch and reduced motion do not download extra images', async () => {
  const touch = setup(); await touch.enter('touch'); assert.equal(touch.images.length, 0);
  const reduced = setup({ reduced: true }); await reduced.enter(); assert.equal(reduced.images.length, 0);
});

test('leaving while images load cannot start a stale animation', async () => {
  const h = setup({ pending: true });
  const start = h.enter(); h.leave();
  h.images.forEach(image => image.onload());
  await start; await flush();
  assert.ok(h.frames.every(frame => frame.hidden)); assert.equal(h.timers.size, 0);
});

test('failed images retain cover; changing motion preference stops playback', async () => {
  const failed = setup({ fail: true }); await failed.enter();
  assert.equal(failed.frames.length, 0); assert.equal(failed.timers.size, 0);
  const h = setup(); await h.enter(); h.motion.matches = true; h.motion.change();
  assert.ok(h.frames.every(frame => frame.hidden)); assert.equal(h.timers.size, 0);
});
