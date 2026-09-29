/* The app's service worker: its alerts and its badge (Jose, Sep 29, 2026).

   The clock (clock/clock.js) sends a push when something happens on his slips;
   this shows it, puts the count of live legs on the icon, and a tap opens the
   board on the slip or the game it is about. */
self.addEventListener("install", function (e) { self.skipWaiting(); });
self.addEventListener("activate", function (e) { e.waitUntil(self.clients.claim()); });

self.addEventListener("push", function (e) {
  var m = {};
  try { m = e.data ? e.data.json() : {}; } catch (err) { m = { title: "Stacked", body: e.data ? e.data.text() : "" }; }
  var work = [self.registration.showNotification(m.title || "Stacked", {
    body: m.body || "", tag: m.tag || undefined, icon: "icon-192.png", badge: "icon-192.png",
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
