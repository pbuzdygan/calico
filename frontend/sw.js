// Calico – service worker: powłoka aplikacji offline. Dane (/api) nigdy nie trafiają do cache.
const CACHE = "calico-shell-v8";
const SHELL = [
  "/",
  "/index.html",
  "/styles.css",
  "/js/api.js",
  "/js/auth.js",
  "/js/charts.js",
  "/js/config.js",
  "/js/entry-sheet.js",
  "/js/i18n.js",
  "/js/language.js",
  "/js/locales/en.js",
  "/js/main.js",
  "/js/nav.js",
  "/js/profile-form.js",
  "/js/state.js",
  "/js/ui.js",
  "/js/util.js",
  "/js/views/goals.js",
  "/js/views/log.js",
  "/js/views/settings.js",
  "/js/views/progress.js",
  "/js/views/today.js",
  "/manifest.json",
  "/fonts/inter-latin.woff2",
  "/fonts/inter-latin-ext.woff2",
  "/icons/logo-64.png",
  "/icons/logo-256.png",
  "/icons/banner-720.jpg",
  "/icons/favicon-32.png",
  "/icons/icon-192.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/api/") || url.pathname === "/health") return;
  // Najpierw sieć (świeże pliki po aktualizacji), cache tylko gdy serwer jest niedostępny.
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request).then((cached) => cached || caches.match("/index.html")))
  );
});
