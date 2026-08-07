{% load static %}
const CACHE_VERSION = 'inventario-pwa-v1';
const APP_SHELL_CACHE = `${CACHE_VERSION}-shell`;
const RUNTIME_CACHE = `${CACHE_VERSION}-runtime`;
const OFFLINE_URL = "{% url 'inventario:offline' %}";

const APP_SHELL_URLS = [
    "{% url 'inventario:facturacion' %}",
    OFFLINE_URL,
    "{% static 'inventario/css/estilos.css' %}",
    "{% static 'inventario/js/facturacion.js' %}",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css",
    "https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js",
];

const PROTECTED_PATH_PREFIXES = [
    '/inventario/',
    '/historial/',
];

const APP_SHELL_ABSOLUTE_URLS = new Set(
    APP_SHELL_URLS.map((url) => new URL(url, self.location.origin).href)
);

async function cacheAppShell() {
    const cache = await caches.open(APP_SHELL_CACHE);

    await Promise.all(
        APP_SHELL_URLS.map(async (url) => {
            try {
                const request = new Request(url, { cache: 'reload' });
                const response = await fetch(request);

                if (response.ok || response.type === 'opaque') {
                    await cache.put(request, response);
                }
            } catch (error) {
                // Si algun recurso falla durante la instalacion, la PWA sigue activa.
            }
        })
    );
}

async function removeOldCaches() {
    const expectedCaches = [APP_SHELL_CACHE, RUNTIME_CACHE];
    const cacheNames = await caches.keys();

    await Promise.all(
        cacheNames
            .filter((cacheName) => !expectedCaches.includes(cacheName))
            .map((cacheName) => caches.delete(cacheName))
    );
}

async function networkFirstPage(request) {
    const runtimeCache = await caches.open(RUNTIME_CACHE);

    try {
        const response = await fetch(request);

        if (response.ok) {
            await runtimeCache.put(request, response.clone());
        }

        return response;
    } catch (error) {
        const cachedPage = await caches.match(request);
        return cachedPage || caches.match(OFFLINE_URL);
    }
}

async function cacheFirstAsset(request) {
    const cachedResponse = await caches.match(request);

    if (cachedResponse) {
        return cachedResponse;
    }

    const response = await fetch(request);

    if (response.ok || response.type === 'opaque') {
        const runtimeCache = await caches.open(RUNTIME_CACHE);
        await runtimeCache.put(request, response.clone());
    }

    return response;
}

function isProtectedPage(url) {
    return PROTECTED_PATH_PREFIXES.some((prefix) => url.pathname.startsWith(prefix));
}

async function networkOnlyProtectedPage(request) {
    try {
        return await fetch(request);
    } catch (error) {
        return caches.match(OFFLINE_URL);
    }
}

self.addEventListener('install', (event) => {
    event.waitUntil(cacheAppShell().then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
    event.waitUntil(removeOldCaches().then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
    const { request } = event;

    if (request.method !== 'GET') {
        return;
    }

    const url = new URL(request.url);

    if (url.pathname.startsWith('/admin/') || url.pathname.startsWith('/api/')) {
        return;
    }

    if (request.mode === 'navigate' && isProtectedPage(url)) {
        event.respondWith(networkOnlyProtectedPage(request));
        return;
    }

    if (request.mode === 'navigate') {
        event.respondWith(networkFirstPage(request));
        return;
    }

    const isStaticAsset = ['style', 'script', 'image', 'font'].includes(request.destination);

    if (APP_SHELL_ABSOLUTE_URLS.has(request.url) || isStaticAsset) {
        event.respondWith(cacheFirstAsset(request));
    }
});
