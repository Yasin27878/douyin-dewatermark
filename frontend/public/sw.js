// 最小 Service Worker：提供可安装能力 + 应用外壳离线兜底。
// 绝不缓存 /api/ 接口。改版发布时请提升 CACHE 版本号。
const CACHE = "dwm-shell-v1";
const SHELL = ["/", "/index.html", "/manifest.webmanifest", "/icon.svg"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  // 接口请求一律走网络，不缓存
  if (url.pathname.startsWith("/api/")) return;
  if (event.request.method !== "GET") return;

  // 导航请求：网络优先，失败回退到外壳
  if (event.request.mode === "navigate") {
    event.respondWith(fetch(event.request).catch(() => caches.match("/")));
    return;
  }

  // 静态资源：缓存优先，其次网络
  event.respondWith(
    caches.match(event.request).then((hit) => hit || fetch(event.request))
  );
});
