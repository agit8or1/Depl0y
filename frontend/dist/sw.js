// Depl0y Service Worker — offline-only fallback, no asset caching
// NOTE: deploy.sh replaces CACHE_VERSION with a build timestamp on every deploy.
// Bump the fallback here only when testing locally.
const CACHE_VERSION = 'v29';
const CACHE_NAME = `depl0y-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline.html';

// ── Install: pre-cache only the offline fallback page ──────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.add(OFFLINE_URL).catch(() => {});
    })
  );
  // Take over immediately so cache busting works on the first deploy
  self.skipWaiting();
});

// ── Activate: delete ALL old cache versions, claim clients ──────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names.filter((n) => n !== CACHE_NAME).map((n) => caches.delete(n))
      ))
      .then(() => self.clients.claim())
      .then(() => self.clients.matchAll({ type: 'window' }))
      .then((clients) => {
        clients.forEach((c) => c.postMessage({ type: 'SW_UPDATED' }));
      })
  );
});

// ── Fetch: ALL requests use network-first; only fall back to offline page ───
// Do NOT cache JS/CSS/images — Vite content-hashes those filenames, so the
// browser's HTTP cache (immutable for /assets/) is the right layer for that.
// Using a SW cache-first strategy here caused stale assets to be served after
// every deploy while the new build was writing to disk.
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET, cross-origin, and API calls (let them go straight to network)
  if (request.method !== 'GET') return;
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  // Navigation requests: network-first, fall back to offline page only
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(async () => {
        const cached = await caches.match(OFFLINE_URL);
        return cached || new Response('<h1>Offline</h1><p>Please reconnect and try again.</p>', {
          status: 503,
          headers: { 'Content-Type': 'text/html' },
        });
      })
    );
  }
  // All other GET requests (assets, icons, etc.): go straight to network.
  // Do NOT intercept — let the browser's HTTP cache handle immutable assets.
});

// ── Background Sync ───────────────────────────────────────────────────────────
self.addEventListener('sync', (event) => {
  if (event.tag === 'depl0y-offline-actions') {
    event.waitUntil(replayOfflineQueue());
  }
});

async function replayOfflineQueue() {
  let db;
  try {
    db = await openSyncDb();
    const queue = await getAllFromStore(db, 'actions');
    if (!queue.length) return;
    const remaining = [];
    for (const entry of queue) {
      try {
        const res = await fetch(entry.url, {
          method: entry.method,
          headers: entry.headers || { 'Content-Type': 'application/json' },
          body: entry.body || null,
        });
        if (!res.ok) remaining.push(entry);
      } catch {
        remaining.push(entry);
      }
    }
    await clearStore(db, 'actions');
    for (const e of remaining) await putInStore(db, 'actions', e);
    const clients = await self.clients.matchAll({ type: 'window' });
    for (const c of clients) {
      c.postMessage({ type: 'SYNC_COMPLETE', replayed: queue.length - remaining.length, remaining: remaining.length });
    }
  } catch (err) {
    console.warn('[SW] replayOfflineQueue error:', err);
  } finally {
    if (db) db.close();
  }
}

function openSyncDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('depl0y-sync', 1);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('actions')) db.createObjectStore('actions', { keyPath: 'id', autoIncrement: true });
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}
function getAllFromStore(db, s) {
  return new Promise((r, j) => { const req = db.transaction(s, 'readonly').objectStore(s).getAll(); req.onsuccess = (e) => r(e.target.result); req.onerror = (e) => j(e.target.error); });
}
function clearStore(db, s) {
  return new Promise((r, j) => { const req = db.transaction(s, 'readwrite').objectStore(s).clear(); req.onsuccess = () => r(); req.onerror = (e) => j(e.target.error); });
}
function putInStore(db, s, v) {
  return new Promise((r, j) => { const req = db.transaction(s, 'readwrite').objectStore(s).put(v); req.onsuccess = () => r(); req.onerror = (e) => j(e.target.error); });
}

// ── Push notifications ────────────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try { payload = event.data.json(); } catch { payload = { title: 'Depl0y', body: event.data.text() }; }
  event.waitUntil(
    self.registration.showNotification(payload.title || 'Depl0y', {
      body: payload.body || '', icon: '/icon-192.png', badge: '/icon-192.png',
      tag: payload.tag || 'depl0y-notification', data: payload.data || {},
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const c of clients) { if (c.url === url && 'focus' in c) return c.focus(); }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
