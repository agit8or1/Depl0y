// Depl0y Service Worker
const CACHE_VERSION = 'v19';
const CACHE_NAME = `depl0y-${CACHE_VERSION}`;
const STATIC_CACHE = `depl0y-static-${CACHE_VERSION}`;
const OFFLINE_URL = '/offline.html';

// Static assets to pre-cache on install
const PRECACHE_URLS = [
  '/',
  '/offline.html',
  '/manifest.json',
];

// ── Install: pre-cache static shell ────────────────────────────────────────
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(PRECACHE_URLS).catch(() => {
        // Non-fatal: offline.html may not exist during dev
      });
    })
  );
  self.skipWaiting();
});

// ── Activate: clean up old cache versions ───────────────────────────────────
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME && name !== STATIC_CACHE)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// ── Fetch: strategy dispatch ─────────────────────────────────────────────────
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests entirely (POST/PUT/PATCH/DELETE go straight to network)
  if (request.method !== 'GET') return;

  // Skip cross-origin requests
  if (url.origin !== self.location.origin) return;

  // ── API calls: network-first with JSON offline fallback ──
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirstApi(request));
    return;
  }

  // ── Static assets (JS/CSS/images/fonts): cache-first ──
  if (url.pathname.match(/\.(js|css|png|jpg|jpeg|gif|svg|ico|woff|woff2|ttf|eot)$/)) {
    event.respondWith(cacheFirstStatic(request));
    return;
  }

  // ── HTML navigation (SPA routes): network-first, offline fallback ──
  if (request.mode === 'navigate') {
    event.respondWith(networkFirstNav(request));
    return;
  }
});

// ── Strategy: network-first for API ─────────────────────────────────────────
async function networkFirstApi(request) {
  try {
    const response = await fetch(request);
    return response;
  } catch {
    return new Response(
      JSON.stringify({ error: 'Offline — API unavailable', offline: true }),
      {
        status: 503,
        headers: {
          'Content-Type': 'application/json',
          'X-Depl0y-Offline': '1',
        },
      }
    );
  }
}

// ── Strategy: cache-first for static assets ──────────────────────────────────
async function cacheFirstStatic(request) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Return nothing — browser will show its own error for assets
    return new Response('', { status: 408 });
  }
}

// ── Strategy: network-first for SPA navigation ───────────────────────────────
async function networkFirstNav(request) {
  try {
    const response = await fetch(request);
    if (response && response.status === 200) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // Try cached SPA shell first, then dedicated offline page
    const cachedShell = await caches.match('/');
    if (cachedShell) return cachedShell;
    const offlinePage = await caches.match(OFFLINE_URL);
    if (offlinePage) return offlinePage;
    return new Response('<h1>Offline</h1><p>Please reconnect and try again.</p>', {
      status: 503,
      headers: { 'Content-Type': 'text/html' },
    });
  }
}

// ── Background Sync: retry queued offline actions ────────────────────────────
// Registered actions are stored in IndexedDB under the key 'sync-queue'.
// Components can register a sync tag via:
//   navigator.serviceWorker.ready.then(sw => sw.sync.register('depl0y-offline-actions'))
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
        const response = await fetch(entry.url, {
          method: entry.method,
          headers: entry.headers || { 'Content-Type': 'application/json' },
          body: entry.body || null,
        });
        if (!response.ok) {
          // Keep in queue if server returned an error (network was up but request failed)
          remaining.push(entry);
        }
        // Successfully replayed — drop from queue
      } catch {
        // Network still down — keep in queue
        remaining.push(entry);
      }
    }

    await clearStore(db, 'actions');
    for (const entry of remaining) {
      await putInStore(db, 'actions', entry);
    }

    // Notify open clients of sync result
    const clients = await self.clients.matchAll({ type: 'window' });
    for (const client of clients) {
      client.postMessage({
        type: 'SYNC_COMPLETE',
        replayed: queue.length - remaining.length,
        remaining: remaining.length,
      });
    }
  } catch (err) {
    console.warn('[SW] replayOfflineQueue error:', err);
  } finally {
    if (db) db.close();
  }
}

// ── IndexedDB helpers ─────────────────────────────────────────────────────────
function openSyncDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open('depl0y-sync', 1);
    req.onupgradeneeded = (e) => {
      const db = e.target.result;
      if (!db.objectStoreNames.contains('actions')) {
        db.createObjectStore('actions', { keyPath: 'id', autoIncrement: true });
      }
    };
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

function getAllFromStore(db, storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readonly');
    const req = tx.objectStore(storeName).getAll();
    req.onsuccess = (e) => resolve(e.target.result);
    req.onerror = (e) => reject(e.target.error);
  });
}

function clearStore(db, storeName) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).clear();
    req.onsuccess = () => resolve();
    req.onerror = (e) => reject(e.target.error);
  });
}

function putInStore(db, storeName, value) {
  return new Promise((resolve, reject) => {
    const tx = db.transaction(storeName, 'readwrite');
    const req = tx.objectStore(storeName).put(value);
    req.onsuccess = () => resolve();
    req.onerror = (e) => reject(e.target.error);
  });
}

// ── Push notifications (stub) ─────────────────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;
  let payload;
  try {
    payload = event.data.json();
  } catch {
    payload = { title: 'Depl0y', body: event.data.text() };
  }
  event.waitUntil(
    self.registration.showNotification(payload.title || 'Depl0y', {
      body: payload.body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      tag: payload.tag || 'depl0y-notification',
      data: payload.data || {},
    })
  );
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if (client.url === url && 'focus' in client) return client.focus();
      }
      if (self.clients.openWindow) return self.clients.openWindow(url);
    })
  );
});
