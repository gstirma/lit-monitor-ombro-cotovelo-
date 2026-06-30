// Service worker da PWA — cache do "shell" para abrir offline e permitir instalar.
// Dados (.json) sempre tentam a rede primeiro, pra manter os artigos atualizados.
const CACHE = "oc-v1";
const SHELL = [
  "./", "./index.html", "./manifest.webmanifest",
  "./icon-192.png", "./icon-512.png",
];

self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Dados: rede primeiro (atualiza), cai pro cache se estiver offline.
  if (url.pathname.endsWith(".json")) {
    e.respondWith(
      fetch(req)
        .then((r) => { const cp = r.clone(); caches.open(CACHE).then((c) => c.put(req, cp)); return r; })
        .catch(() => caches.match(req))
    );
    return;
  }

  // Restante (shell): cache primeiro, rede como reserva.
  e.respondWith(caches.match(req).then((c) => c || fetch(req)));
});
