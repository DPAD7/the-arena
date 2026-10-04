/* The app's service worker: its alerts and its badge (Jose, Sep 29, 2026).

   The clock (clock/clock.js) sends a push when something happens on his slips;
   this shows it, puts the count of live legs on the icon, and a tap opens the
   board on the slip or the game it is about. */
self.addEventListener("install", function (e) { self.skipWaiting(); });
/* a new version of the kept pictures drops the old ones (the $ turned, Oct 3, 2026) */
self.addEventListener("activate", function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return /^stacked-static-/.test(k) && k !== STATIC; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener("push", function (e) {
  var m = {};
  try { m = e.data ? e.data.json() : {}; } catch (err) { m = { title: "Stacked", body: e.data ? e.data.text() : "" }; }
  var work = [self.registration.showNotification(m.title || "Stacked", {
    body: m.body || "", tag: m.tag || undefined, renotify: !!m.tag, icon: "icon-192.png", badge: "icon-192.png",
    data: { url: m.url || "/", type: m.type || "" }
  })];
  if (typeof m.badge === "number" && self.navigator && self.navigator.setAppBadge) {
    work.push(m.badge > 0 ? self.navigator.setAppBadge(m.badge) : self.navigator.clearAppBadge());
  }
  e.waitUntil(Promise.all(work).catch(function () {}));
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var d = e.notification.data || {}, url = d.url || "/";
  e.waitUntil((async function () {
    // counted, so the kinds he never opens can be cut
    try { await fetch("push", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ opened: d.type || "other" }) }); } catch (err) {}
    var all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (var c of all) {
      if ("focus" in c) { c.postMessage({ go: url }); return c.focus(); }
    }
    return self.clients.openWindow(url);
  })());
});

/* ---- instant open (Jose, Sep 29, 2026) ----
   The app itself opens from the copy kept here, at once, and a fresh copy is
   fetched behind it for next time. A new version the board asks for comes
   with ?v= on the address and is always read from the network, so a saved
   copy can never hold an update back. Pictures, fonts and icons are kept;
   prices, marks and every function are always asked of the site. */
var SHELL = "stacked-shell-v1", STATIC = "stacked-static-v3";
self.addEventListener("fetch", function (e) {
  var req = e.request, url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== self.location.origin) return;
  if (req.mode === "navigate") {
    if (url.searchParams.has("v")) {
      e.respondWith(fetch(req).then(function (r) {
        var copy = r.clone();
        caches.open(SHELL).then(function (c) { c.put("/", copy); });
        return r;
      }).catch(function () { return caches.match("/"); }));
      return;
    }
    /* the newest page first: the saved copy only when the network is slow
       or gone. Opening on the saved copy and swapping later left him on an
       old version whenever he started using it at once (Jose, Oct 3, 2026:
       "if we're doing updates it should show us") */
    e.respondWith(caches.open(SHELL).then(function (c) {
      var fresh = fetch("/", { cache: "no-store" }).then(function (r) { if (r.ok) c.put("/", r.clone()); return r; });
      return c.match("/").then(function (hit) {
        if (!hit) return fresh;
        var slow = new Promise(function (res) { setTimeout(function () { res(hit); }, 2500); });
        e.waitUntil(fresh.catch(function () {}));
        return Promise.race([fresh.then(function (r) { return r.ok ? r : hit; }, function () { return hit; }), slow]);
      });
    }));
    return;
  }
  if (/^\/(ico|font|logos|img|launch)\//.test(url.pathname) || /\/(icon-\d+|apple-touch-icon)\.png$/.test(url.pathname)) {
    e.respondWith(caches.open(STATIC).then(function (c) {
      return c.match(req).then(function (hit) {
        return hit || fetch(req).then(function (r) { if (r.ok) c.put(req, r.clone()); return r; });
      });
    }));
  }
});
