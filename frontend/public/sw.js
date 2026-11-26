const CACHE_NAME = "tradepulse-v2-shell-v1";

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.addAll([
        "/",
        "/manifest.webmanifest",
        "/tradepulse-icon.svg"
      ])
    )
  );

  self.skipWaiting();
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys
          .filter(key => key !== CACHE_NAME)
          .map(key => caches.delete(key))
      )
    )
  );

  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const request = event.request;
  const url = new URL(request.url);

  if (request.method !== "GET") return;

  // Nenhum dado financeiro ou resposta de API e cacheado.
  if (
    url.pathname.startsWith("/api/") ||
    url.port === "3001" ||
    url.origin !== self.location.origin
  ) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request).catch(() =>
        caches.match("/")
      )
    );
    return;
  }

  if (
    url.pathname === "/manifest.webmanifest" ||
    url.pathname === "/tradepulse-icon.svg"
  ) {
    event.respondWith(
      caches.match(request).then(
        cached => cached || fetch(request)
      )
    );
  }
});
