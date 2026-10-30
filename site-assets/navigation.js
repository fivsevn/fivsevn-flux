/* The build supplies fluxPostPages; all saved URLs and frame measurements stay per tab. */
(() => {
  const pages = typeof fluxPostPages === 'object' ? fluxPostPages : {};
  const originKey = 'flux-return-origin';
  const pendingKey = 'flux-return-pending';
  const listPath = path => path === '/' || /^\/feed\/\d+\/$/.test(path);
  const own = (object, key) => Object.prototype.hasOwnProperty.call(object, key);
  const relative = url => url.pathname + url.search + url.hash;
  const read = key => { try { return JSON.parse(sessionStorage.getItem(key)); } catch (_) { return null; } };
  const save = (key, value) => { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch (_) {} };
  const remove = key => { try { sessionStorage.removeItem(key); } catch (_) {} };
  const hashId = value => { try { return decodeURIComponent(value.slice(1)); } catch (_) { return ''; } };
  function listURL(value, id) {
    if (typeof value !== 'string' || !value) return null;
    try {
      const url = new URL(value, location.origin);
      if (url.origin !== location.origin || !listPath(url.pathname)) return null;
      if (url.hash && hashId(url.hash) !== id) return null;
      url.hash = id;
      return url;
    } catch (_) { return null; }
  }
  function pendingReturn() {
    const record = read(pendingKey);
    if (!record || typeof record.id !== 'string' || !Number.isFinite(record.top)
        || Math.abs(record.top) > 1000000 || !Number.isFinite(record.at)
        || Math.abs(Date.now() - record.at) > 120000 || !listURL(record.url, record.id)) return null;
    return record;
  }
  const detail = document.querySelector('section[aria-label="single flux"] > article.entry');
  const returnLink = document.querySelector('.return-brand');
  if (detail && returnLink) {
    const origin = read(originKey);
    const target = (origin && origin.id === detail.id && listURL(origin.url, detail.id))
      || listURL(document.referrer, detail.id) || listURL(returnLink.href, detail.id);
    if (!target) return;
    returnLink.href = relative(target);
    const remember = () => save(pendingKey, {
      id: detail.id, url: relative(target), top: detail.getBoundingClientRect().top, at: Date.now()
    });
    returnLink.addEventListener('click', event => {
      if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      remember();
      const previous = listURL(document.referrer, detail.id);
      if (previous && previous.pathname === target.pathname && previous.search === target.search && history.length > 1) {
        event.preventDefault();
        history.back();
      }
    });
    // Native Back also leaves through pagehide, including a bfcache return.
    window.addEventListener('pagehide', remember);
    return;
  }
  if (!listPath(location.pathname)) return;
  document.addEventListener('click', event => {
    if (event.defaultPrevented || event.button > 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = event.target.closest && event.target.closest('.entry-title a');
    const frame = link && link.closest('article.entry');
    if (!frame) return;
    try {
      const url = new URL(link.href, location.origin);
      if (url.origin === location.origin && url.pathname.startsWith('/page/')) {
        save(originKey, {id: frame.id, url: location.pathname + location.search + '#' + encodeURIComponent(frame.id)});
      }
    } catch (_) {}
  });
  // Preserve bookmarks when a post moves to another list page.
  function moveToPage(id, record) {
    if (!own(pages, id) || pages[id] === location.pathname) return false;
    const destination = pages[id] + location.search + '#' + encodeURIComponent(id);
    if (record && record.id === id) save(pendingKey, {...record, url: destination});
    location.replace(destination);
    return true;
  }
  const bookmark = hashId(location.hash);
  const returning = pendingReturn();
  const returningURL = returning && listURL(returning.url, returning.id);
  const returningHere = returningURL && returningURL.pathname === location.pathname && returningURL.search === location.search;
  if (!returningHere && bookmark && moveToPage(bookmark, returning)) return;
  let active = null;
  function alignFrame(frame, record) {
    if (active) active.stop();
    const oldSpacer = document.getElementById('flux-return-spacer');
    if (oldSpacer) oldSpacer.remove();
    let stopped = false, animation = 0, quiet = 0, spacer = null;
    const listeners = [];
    const listen = (target, name, handler, options) => {
      target.addEventListener(name, handler, options);
      listeners.push(() => target.removeEventListener(name, handler, options));
    };
    const images = Array.from(document.images).filter(image => frame.contains(image)
      || Boolean(image.compareDocumentPosition(frame) & Node.DOCUMENT_POSITION_FOLLOWING));
    let observer = null;
    const previousRestoration = history.scrollRestoration;
    try { history.scrollRestoration = 'manual'; } catch (_) {}
    function stop() {
      if (stopped) return;
      stopped = true;
      window.cancelAnimationFrame(animation);
      window.clearTimeout(quiet);
      if (observer) observer.disconnect();
      listeners.forEach(dispose => dispose());
      try { history.scrollRestoration = previousRestoration; } catch (_) {}
      if (active && active.stop === stop) active = null;
    }
    function schedule() {
      if (stopped || animation) return;
      window.clearTimeout(quiet);
      animation = window.requestAnimationFrame(() => {
        animation = window.requestAnimationFrame(() => {
          animation = 0;
          if (stopped || !frame.isConnected) return;
          const top = Math.max(0, window.scrollY + frame.getBoundingClientRect().top - record.top);
          const scroller = document.scrollingElement || document.documentElement;
          const missing = top + window.innerHeight - scroller.scrollHeight;
          if (missing > 0.5) {
            if (!spacer) {
              spacer = document.createElement('div');
              spacer.id = 'flux-return-spacer';
              spacer.setAttribute('aria-hidden', 'true');
              spacer.style.cssText = 'height:0;pointer-events:none;';
              document.body.appendChild(spacer);
            }
            spacer.style.height = ((parseFloat(spacer.style.height) || 0) + Math.ceil(missing)) + 'px';
          }
          if (Math.abs(window.scrollY - top) > 0.5) window.scrollTo({top, left: window.scrollX, behavior: 'instant'});
          if (document.readyState === 'complete' && (!document.fonts || document.fonts.status !== 'loading')
              && images.every(image => image.complete)) quiet = window.setTimeout(stop, 250);
        });
      });
    }
    ['wheel', 'touchstart', 'pointerdown', 'keydown'].forEach(name => listen(window, name, stop, {capture: true, passive: true}));
    listen(window, 'resize', schedule);
    listen(window, 'load', schedule);
    images.forEach(image => { listen(image, 'load', schedule); listen(image, 'error', schedule); });
    if (document.fonts) {
      document.fonts.ready.then(schedule, schedule);
      if (document.fonts.addEventListener) listen(document.fonts, 'loadingdone', schedule);
    }
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(schedule);
      observer.observe(document.body);
      observer.observe(frame);
    }
    active = {stop, schedule};
    schedule();
  }
  function restore() {
    const record = pendingReturn();
    if (!record) { if (active) active.schedule(); return; }
    const expected = listURL(record.url, record.id);
    if (!expected || expected.pathname !== location.pathname || expected.search !== location.search) return;
    const frame = document.getElementById(record.id);
    if (!frame || !frame.matches('article.entry')) {
      if (moveToPage(record.id, record)) return;
      remove(pendingKey);
      return;
    }
    remove(pendingKey);
    try { history.replaceState(history.state, '', relative(expected)); } catch (_) {}
    alignFrame(frame, record);
  }
  window.addEventListener('pageshow', restore);
  window.addEventListener('load', restore);
  document.addEventListener('DOMContentLoaded', restore);
  window.addEventListener('pagehide', () => { if (active) active.stop(); });
  restore();
})();
