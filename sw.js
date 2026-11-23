// BladeFlix service worker: offline app shell, fresh video feed.
// The shell (HTML/CSS/JS/icons) is cached first; videos.json is
// network-first so the feed stays current, with a cache fallback
// when offline. Third-party requests (YouTube embeds, thumbnails,
// the hit counter) always go straight to the network.

const CACHE = 'bladeflix-v2';
const CORE_ASSETS = [
  '/',
  '/index.html',
  '/styles.css',
  '/app.js',
  '/manifest.webmanifest',
  '/images/icon-192.png',
  '/images/icon-512.png',
  '/images/icon-maskable-512.png',
  '/images/favicon.png',
  '/images/logo.png'
];

self.addEventListener('install', (event) => {
  // Cache each asset individually: cache.addAll() is atomic, so one
  // flaky fetch would fail the whole install and leave the worker
  // unregistered. A partial shell still beats no worker.
  event.waitUntil(
    caches.open(CACHE)
      .then((cache) => Promise.allSettled(
        CORE_ASSETS.map((url) => cache.add(url))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return; // third-party: pass through

  // The video feed: network first, cache fallback.
  if (url.pathname === '/data/videos.json') {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // App shell: cache first, network fallback.
  if (CORE_ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
