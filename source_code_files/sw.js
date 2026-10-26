// LABADA LINK · service worker
// Lets the staff app open even when the internet is down.
// Change VERSION whenever you want every device to throw away its old cache.
const VERSION = 'labada-v2';
const SHELL = ['./', 'logo.png', 'vendor/qrcode.min.js', 'vendor/html2canvas.min.js'];

self.addEventListener('install', e => {
  e.waitUntil(
    caches.open(VERSION).then(c => Promise.all(SHELL.map(u => c.add(u).catch(() => {}))))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== VERSION).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

function keep(req, res) {
  // only keep good, direct answers (never redirects or errors)
  if (res && res.ok && !res.redirected) {
    const copy = res.clone();
    caches.open(VERSION).then(c => c.put(req, copy)).catch(() => {});
  }
  return res;
}

function fetchWithTimeout(req, ms) {
  const ctl = new AbortController();
  const t = setTimeout(() => ctl.abort(), ms);
  return fetch(req, { signal: ctl.signal }).finally(() => clearTimeout(t));
}

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Never touch the database or anything else we don't know about
  const sameOrigin = url.origin === self.location.origin;
  const isFont = url.host === 'fonts.googleapis.com' || url.host === 'fonts.gstatic.com';
  if (!sameOrigin && !isFont) return;

  // Pages: newest copy when online (4 s limit), saved copy when not
  if (req.mode === 'navigate') {
    e.respondWith(
      fetchWithTimeout(req, 4000).then(res => keep(req, res)).catch(async () => {
        const hit = await caches.match(req, { ignoreSearch: true });
        if (hit) return hit;
        const page = url.pathname.split('/').pop();
        if (page === '' || page === 'index.html') return caches.match('./');
        return Response.error();
      })
    );
    return;
  }

  // Files and fonts: show the saved copy instantly, refresh it in the background
  e.respondWith(
    caches.match(req).then(hit => {
      const fresh = fetch(req).then(res => keep(req, res)).catch(() => hit);
      return hit || fresh;
    })
  );
});
