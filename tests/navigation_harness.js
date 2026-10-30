/* Minimal event/layout doubles; production navigation runs unchanged below. */
const assert = (condition, message) => { if (!condition) throw new Error(message); };
class Events {
  constructor() { this.events = {}; }
  addEventListener(type, handler) { (this.events[type] ||= new Set()).add(handler); }
  removeEventListener(type, handler) { if (this.events[type]) this.events[type].delete(handler); }
  emit(type, values = {}) {
    const event = {button: 0, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...values};
    Array.from(this.events[type] || []).forEach(handler => handler(event));
    return event;
  }
}
class TestURL {
  constructor(value, base = 'https://flux.test') {
    if (typeof value !== 'string') throw new Error('Invalid URL');
    if (value.startsWith('//')) value = 'https:' + value;
    const match = /^(https?:\/\/[^/?#]+)?([^?#]*)(\?[^#]*)?(#.*)?$/.exec(value);
    if (!match) throw new Error('Invalid URL');
    this.origin = match[1] || String(base).replace(/\/$/, '');
    this.pathname = match[2] || '/';
    this.search = match[3] || '';
    this.hash = match[4] || '';
  }
  get hash() { return this._hash; }
  set hash(value) { this._hash = value ? '#' + String(value).replace(/^#/, '') : ''; }
}
const URLType = typeof URL === 'function' ? URL : TestURL;
function storage() {
  const data = new Map();
  return {getItem: key => data.has(key) ? data.get(key) : null,
    setItem: (key, value) => data.set(key, String(value)), removeItem: key => data.delete(key),
    value: key => JSON.parse(data.get(key) || 'null')};
}
function pending(store, values = {}) {
  store.setItem('flux-return-pending', JSON.stringify({id: 'post-b', url: '/feed/2/#post-b', top: 205, at: Date.now(), ...values}));
}
function page(options = {}, store = storage()) {
  const state = {kind: 'list', path: '/feed/2/', id: 'post-b', top: 1500, height: 100,
    scroll: 0, documentHeight: 4000, viewport: 900, fonts: 'loaded', referrer: '', historyLength: 1,
    images: [], ...options};
  const window = new Events(), document = new Events();
  const location = {origin: 'https://flux.test', pathname: state.path, search: state.search || '', hash: state.hash || '',
    replacements: [], replace(value) { this.replacements.push(value); }};
  const frames = new Map(), timers = new Map(), microtasks = [], observers = [];
  let serial = 0, spacer = null;
  window.scrollY = state.scroll; window.scrollX = 0; window.innerHeight = state.viewport; window.scrolls = [];
  window.requestAnimationFrame = fn => { frames.set(++serial, fn); return serial; };
  window.cancelAnimationFrame = id => frames.delete(id);
  window.setTimeout = fn => { timers.set(++serial, fn); return serial; };
  window.clearTimeout = id => timers.delete(id);
  window.scrollTo = ({top}) => {
    const maximum = Math.max(0, state.documentHeight + (spacer ? parseFloat(spacer.style.height) || 0 : 0) - window.innerHeight);
    window.scrollY = Math.min(maximum, Math.max(0, top));
    window.scrolls.push(window.scrollY);
  };
  const frame = new Events();
  Object.assign(frame, {id: state.id, isConnected: true, style: {},
    getBoundingClientRect: () => ({top: state.top - window.scrollY, height: state.height}),
    contains: image => Boolean(image.inFrame), matches: selector => selector === 'article.entry'});
  const link = new Events(); link.href = state.returnHref || '/feed/2/#' + state.id;
  link.closest = selector => selector === 'article.entry' ? frame : null;
  const title = {closest: selector => selector === '.entry-title a' ? link : null};
  if (state.kind === 'list') link.href = '/page/2026/10/' + state.id + '/';
  document.referrer = state.referrer; document.readyState = 'complete';
  document.images = state.images.map(values => Object.assign(new Events(), {complete: false, before: true,
    compareDocumentPosition: () => 4, ...values}));
  document.querySelector = selector => selector === '.return-brand' ? (state.kind === 'detail' ? link : null)
    : selector.startsWith('section[aria-label="single flux"]') && state.kind === 'detail' ? frame : null;
  document.getElementById = id => id === state.id ? frame : id === 'flux-return-spacer' ? spacer : null;
  document.body = new Events(); document.body.appendChild = element => { spacer = element; };
  document.createElement = () => ({id: '', style: {height: '0px'}, attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; }, remove() { spacer = null; }});
  document.documentElement = {};
  Object.defineProperty(document.documentElement, 'scrollHeight', {get: () => state.documentHeight + (spacer ? parseFloat(spacer.style.height) || 0 : 0)});
  document.scrollingElement = document.documentElement;
  document.fonts = new Events(); document.fonts.status = state.fonts;
  const fontCallbacks = [];
  document.fonts.ready = {then(fn) { fontCallbacks.push(fn); if (document.fonts.status !== 'loading') microtasks.push(fn); }};
  const history = {length: state.historyLength, state: null, scrollRestoration: 'auto', backCalls: 0,
    back() { this.backCalls++; }, replaceState(_state, _title, url) {
      const parsed = new URLType(url, location.origin);
      location.pathname = parsed.pathname; location.search = parsed.search; location.hash = parsed.hash;
    }};
  class Observer {
    constructor(callback) { this.callback = callback; this.active = true; observers.push(this); }
    observe() {} disconnect() { this.active = false; }
  }
  new Function('window', 'document', 'location', 'history', 'sessionStorage', 'URL', 'Node', 'ResizeObserver', runtime)(
    window, document, location, history, store, URLType, {DOCUMENT_POSITION_FOLLOWING: 4}, Observer);
  return {state, window, document, frame, link, title, location, history, store,
    get spacer() { return spacer; },
    flush() {
      for (let pass = 0; pass < 20; pass++) {
        microtasks.splice(0).forEach(fn => fn());
        if (!frames.size) return;
        const current = Array.from(frames.values()); frames.clear(); current.forEach(fn => fn());
      }
      throw new Error('Frame queue did not settle');
    },
    finishFonts() { document.fonts.status = 'loaded'; fontCallbacks.forEach(fn => microtasks.push(fn)); document.fonts.emit('loadingdone'); },
    resize() { observers.filter(observer => observer.active).forEach(observer => observer.callback()); window.emit('resize'); },
    finishTimers() { const current = Array.from(timers.values()); timers.clear(); current.forEach(fn => fn()); }};
}
function sameTop(view, top) { view.flush(); assert(Math.abs(view.frame.getBoundingClientRect().top - top) < 0.01, 'Frame top differs: ' + view.frame.getBoundingClientRect().top + ' vs ' + top); }
function runScenario(name) {
  const store = storage();
  if (name === 'detail-offset') {
    store.setItem('flux-return-origin', JSON.stringify({id: 'post-b', url: '/feed/2/#post-b', top: 216}));
    const detail = page({kind: 'detail', top: 205, referrer: 'https://flux.test/feed/2/', historyLength: 2}, store);
    detail.link.emit('click'); assert(store.value('flux-return-pending').top === 205, 'Reused old list click offset');
    assert(detail.history.backCalls === 1, 'Did not return through history');
    const list = page({top: 1500, scroll: 1284}, store); sameTop(list, 205);
  } else if (name === 'direct-detail') {
    const detail = page({kind: 'detail', top: 205}, store);
    const click = detail.link.emit('click');
    assert(detail.link.href === '/feed/2/#post-b', 'Direct detail lost its correct fallback page');
    assert(!click.defaultPrevented && detail.history.backCalls === 0, 'Direct detail incorrectly used history');
    sameTop(page({}, store), 205);
  } else if (name === 'native-back') {
    const list = page({top: 1000, scroll: 784}, store);
    list.document.emit('click', {target: list.title});
    const detail = page({kind: 'detail', top: 205, scroll: 50, referrer: 'https://flux.test/feed/2/', historyLength: 2}, store);
    detail.window.emit('pagehide'); assert(store.value('flux-return-pending').top === 155, 'Native Back did not capture current detail top');
    list.window.emit('pageshow', {persisted: true}); sameTop(list, 155);
  } else if (name === 'layout-settle') {
    pending(store); const list = page({fonts: 'loading', images: [{}]}, store); sameTop(list, 205);
    list.state.top += 320; list.state.documentHeight += 320;
    list.document.images[0].complete = true; list.document.images[0].emit('load'); sameTop(list, 205);
    list.state.top += 17; list.state.documentHeight += 17; list.finishFonts(); list.resize(); sameTop(list, 205);
    list.finishTimers(); assert(list.history.scrollRestoration === 'auto', 'Restoration mode was not released');
  } else if (name === 'user-scroll') {
    pending(store); const list = page({fonts: 'loading', images: [{}]}, store); sameTop(list, 205);
    list.window.emit('wheel'); list.window.scrollY += 40; const calls = list.window.scrolls.length;
    list.state.top += 150; list.state.documentHeight += 150; list.document.images[0].complete = true;
    list.document.images[0].emit('load'); list.finishFonts(); list.resize(); list.flush();
    assert(list.window.scrolls.length === calls, 'Automatic alignment overrode user scrolling');
  } else if (name === 'short-last-post') {
    pending(store); const list = page({top: 1000, height: 100, documentHeight: 1250}, store); sameTop(list, 205);
    assert(list.spacer && parseFloat(list.spacer.style.height) === 445, 'Missing minimal final-page scroll room');
    assert(list.frame.getBoundingClientRect().height === 100 && Object.keys(list.frame.style).length === 0, 'Changed the frame geometry');
    assert(list.spacer.attributes['aria-hidden'] === 'true', 'Scroll spacer is exposed to readers');
  } else if (name === 'bookmark') {
    pending(store, {id: 'post-a', url: '/feed/10/?from=bookmark#post-a'});
    const list = page({path: '/feed/10/', hash: '#post-a', search: '?from=bookmark'}, store);
    assert(list.location.replacements[0] === '/?from=bookmark#post-a', 'Old bookmark did not follow post');
    assert(store.value('flux-return-pending').top === 205 && store.value('flux-return-pending').url === '/?from=bookmark#post-a', 'Bookmark lost pending alignment');
  } else if (name === 'invalid-pending') {
    for (const values of [{url: 'https://evil.test/feed/2/#post-b'}, {at: Date.now() - 120001}]) {
      pending(store, values); const list = page({}, store); list.flush(); assert(list.window.scrolls.length === 0, 'Unrelated pending state was applied');
    }
    const list = page({path: '/feed/10/', hash: '#__proto__'}, storage());
    assert(list.location.replacements.length === 0, 'Prototype name became a bookmark route');
  } else if (name === 'changed-page') {
    pending(store, {url: '/feed/10/#post-b'});
    const old = page({path: '/feed/10/', id: 'unrelated'}, store);
    assert(old.location.replacements[0] === '/feed/2/#post-b', 'Missing pending post did not move to its correct page');
    sameTop(page({}, store), 205);
  } else if (name === 'stale-hash') {
    pending(store);
    const list = page({hash: '#post-a'}, store); sameTop(list, 205);
    assert(list.location.replacements.length === 0, 'A stale hash overrode the returned post');
  } else throw new Error('Unknown scenario: ' + name);
  const output = typeof print === 'function' ? print : console.log;
  output(JSON.stringify({scenario: name, ok: true}));
}
