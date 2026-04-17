/**
 * Shubham Tradelink — Service Worker
 *
 * Strategy:
 *   • Static assets (CSS, JS, fonts, images) → Cache-first
 *   • HTML pages & API calls                 → Network-first (fresh data always)
 *   • Never aggressively cache business data
 */

const CACHE_NAME = 'tradelink-v1';

// Assets to pre-cache on install (app shell)
const APP_SHELL = [
  '/',
  '/login',
];

// ─── Install: pre-cache app shell ──────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(APP_SHELL).catch(() => {
        // Silently fail if any shell asset can't be fetched (e.g. login redirect)
        console.log('[SW] Some app shell assets could not be cached');
      });
    })
  );
  // Activate immediately without waiting for tabs to close
  self.skipWaiting();
});

// ─── Activate: clean up old caches ─────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      );
    })
  );
  // Take control of all open tabs immediately
  self.clients.claim();
});

// ─── Fetch: smart caching strategy ─────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests (form submissions, POST APIs)
  if (request.method !== 'GET') return;

  // Skip cross-origin requests (CDNs like Tailwind, Google Fonts)
  if (url.origin !== self.location.origin) return;

  // Static assets → Cache-first (fast loads)
  if (isStaticAsset(url.pathname)) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // Everything else (HTML pages, any server routes) → Network-first
  event.respondWith(networkFirst(request));
});

// ─── Helpers ────────────────────────────────────────────────

function isStaticAsset(path) {
  return /\.(?:css|js|png|jpg|jpeg|gif|svg|ico|woff2?|ttf|eot)$/i.test(path)
    || path.startsWith('/static/');
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // If offline and not cached, return a basic offline response
    return new Response('Offline', { status: 503, statusText: 'Offline' });
  }
}

async function networkFirst(request) {
  try {
    const response = await fetch(request);
    // Cache successful HTML responses for offline fallback
    if (response.ok && request.headers.get('accept')?.includes('text/html')) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Offline: try to serve from cache
    const cached = await caches.match(request);
    if (cached) return cached;

    // Last resort: return a simple offline page
    return new Response(
      `<!DOCTYPE html>
       <html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
       <title>Offline — Shubham Tradelink</title>
       <style>body{font-family:Inter,sans-serif;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0;background:#0f172a;color:#e2e8f0;text-align:center}
       .box{padding:2rem}.icon{font-size:3rem;margin-bottom:1rem}h1{font-size:1.5rem;margin-bottom:.5rem}p{color:#94a3b8}</style>
       </head><body><div class="box"><div class="icon">📡</div><h1>You're Offline</h1><p>Please check your internet connection and try again.</p></div></body></html>`,
      { status: 503, headers: { 'Content-Type': 'text/html' } }
    );
  }
}
