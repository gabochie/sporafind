/* Sporafind service worker — precache shell, runtime caches, push.
 * Versioned caches; auth'd traffic is NEVER cached. */
const VERSION = 'sf-v2';
const STATIC_CACHE = VERSION + '-static';
const PAGE_CACHE = VERSION + '-pages';
const API_CACHE = VERSION + '-api';
const CDN_CACHE = VERSION + '-cdn';

const PRECACHE = [
  '/',
  '/blog',
  '/offline.html',
  '/manifest.webmanifest',
  '/css/tokens.css',
  '/css/components.css',
  '/js/session.js',
  '/js/pwa.js',
  '/js/pwa-ui.js',
  '/icons/icon-192.png',
  '/icons/icon-512.png',
];

// addAll() is all-or-nothing: one 404 rejects the whole install and the worker
// never activates, so the app silently loses offline support. Cache each entry
// independently and tolerate individual failures.
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then((c) => Promise.all(
        PRECACHE.map((url) => c.add(url).catch((err) => console.warn('[sw] precache miss', url, err)))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

const hasAuth = (req) => {
  try { return !!req.headers.get('authorization'); } catch (e) { return false; }
};

async function networkFirst(req, cacheName, fallback) {
  const cache = await caches.open(cacheName);
  try {
    const res = await fetch(req);
    if (res && res.ok) cache.put(req, res.clone());
    return res;
  } catch (e) {
    const hit = await cache.match(req, { ignoreSearch: cacheName === PAGE_CACHE ? false : true });
    if (hit) return hit;
    if (fallback) {
      const fb = await cache.match(fallback);
      if (fb) return fb;
    }
    throw e;
  }
}

async function staleWhileRevalidate(req, cacheName, maxEntries) {
  const cache = await caches.open(cacheName);
  const hit = await cache.match(req);
  const net = fetch(req).then((res) => {
    if (res && res.ok) {
      cache.put(req, res.clone()).then(() => {
        if (maxEntries) cache.keys().then((ks) => {
          if (ks.length > maxEntries) cache.delete(ks[0]);
        });
      });
    }
    return res;
  }).catch(() => hit);
  return hit || net;
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);
  // Never cache authenticated traffic.
  if (hasAuth(req)) return;
  // Admin/billing/push + authed workspace writes: network only.
  if (/\/api\/(admin|billing|push)\//.test(url.pathname)) return;
  if (url.origin !== self.location.origin) {
    // CDN assets: cache with cap.
    if (/jsdelivr|googleapis|gstatic/.test(url.hostname)) {
      event.respondWith(staleWhileRevalidate(req, CDN_CACHE, 40));
    }
    return;
  }
  if (req.mode === 'navigate') {
    event.respondWith(networkFirst(req, PAGE_CACHE, '/offline.html'));
    return;
  }
  if (url.pathname === '/sw.js' || url.pathname === '/manifest.webmanifest') return;
  // img/ was missing here, so feature photos and OG cards fell through to the
  // network-first catch-all instead of being cached like other static assets.
  if (/^\/(css|js|icons|img)\//.test(url.pathname) || url.pathname === '/favicon.svg' || url.pathname === '/offline.html') {
    event.respondWith(staleWhileRevalidate(req, STATIC_CACHE, 60));
    return;
  }
  if (/^\/api\//.test(url.pathname)) {
    // Public reads (pricing/stats/search w/o key, blog fallbacks via frontend): network-first.
    event.respondWith(networkFirst(req, API_CACHE, null).catch(() =>
      new Response(JSON.stringify({ offline: true }), {
        status: 503, headers: { 'Content-Type': 'application/json' },
      })
    ));
    return;
  }
  // Other same-origin GETs (static html): network-first, offline fallback.
  event.respondWith(networkFirst(req, PAGE_CACHE, '/offline.html'));
});

// Push: show notification, focus/open on click.
self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
  const title = data.title || 'Sporafind';
  event.waitUntil(
    self.registration.showNotification(title, {
      body: data.body || 'New update from Sporafind.',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-192.png',
      data: { url: data.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((wins) => {
      for (const w of wins) {
        if (new URL(w.url).pathname === new URL(url, self.location.origin).pathname) return w.focus();
      }
      return clients.openWindow(url);
    })
  );
});
