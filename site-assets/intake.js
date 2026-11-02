/* Read the intake page's generation time, independently of Flux publication. */
(() => {
  const bubble = document.querySelector('.arrival-bubble');
  if (!bubble) return;
  const time = bubble.querySelector('.arrival-time');
  const link = bubble.querySelector('a');
  const cacheKey = 'flux-intake-generated-at';
  function show(value) {
    const match = /^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}) UTC$/.exec(value);
    if (!match) return false;
    const iso = match[1] + 'T' + match[2] + '+00:00';
    if (!Number.isFinite(Date.parse(iso))) return false;
    time.textContent = iso;
    time.dateTime = iso;
    return true;
  }
  try { show(localStorage.getItem(cacheKey) || ''); } catch (_) {}
  async function refresh() {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 10000);
    try {
      // The generated header fits in this range; skip the large daily content.
      const response = await fetch(link.href, {
        headers: {Range: 'bytes=0-16383'}, cache: 'no-store',
        credentials: 'omit', signal: controller.signal
      });
      if (!response.ok) throw new Error('Intake unavailable');
      const source = await response.text();
      const end = source.indexOf('</header>');
      if (end < 0) throw new Error('Intake header unavailable');
      const page = new DOMParser().parseFromString(source.slice(0, end + 9), 'text/html');
      const label = Array.from(page.querySelectorAll('header .kicker'))
        .find(node => node.textContent.includes('Shift opened'));
      const value = label && label.nextElementSibling;
      const stamp = value && value.matches('.kicker-value') && value.textContent.trim();
      if (!stamp || !show(stamp)) throw new Error('Intake generation time unavailable');
      time.title = '到店时间（页面生成，UTC）';
      try { localStorage.setItem(cacheKey, stamp); } catch (_) {}
    } catch (_) {
      // Keep the permanent link usable even when the other site cannot be read.
      if (!time.dateTime) time.textContent = '—';
      time.title = time.dateTime ? '上次读取的到店时间（页面生成，UTC）' : '到店时间暂不可用';
    } finally {
      clearTimeout(timeout);
    }
  }
  refresh();
  window.addEventListener('pageshow', event => { if (event.persisted) refresh(); });
})();
