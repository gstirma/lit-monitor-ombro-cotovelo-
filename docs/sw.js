// Service worker da PWA — cache do "shell" para abrir offline e permitir instalar.
// Dados (.json) sempre tentam a rede primeiro, pra manter os artigos atualizados.
const CACHE = "oc-v2";
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

  // HTML/navegação e dados (.json): REDE PRIMEIRO — garante interface e artigos
  // sempre atualizados quando há internet; cai pro cache só se estiver offline.
  const isHTML = req.mode === "navigate" || url.pathname === "/" ||
                 url.pathname.endsWith("/") || url.pathname.endsWith(".html");
  if (isHTML || url.pathname.endsWith(".json")) {
    e.respondWith(
      fetch(req)
        .then((r) => { const cp = r.clone(); caches.open(CACHE).then((c) => c.put(req, cp)); return r; })
        .catch(() => caches.match(req).then((c) => c || caches.match("./index.html")))
    );
    return;
  }

  // Ícones/manifest e demais estáticos: cache primeiro, rede como reserva.
  e.respondWith(caches.match(req).then((c) => c || fetch(req)));
});
