/* The board's own marks, kept on the site instead of in each browser.

   Hidden games, placed prices and the slip lived in localStorage, so the
   phone, the iPad and the desktop each had their own and none of them
   agreed. There is one reader here, so there is one blob: whatever the last
   device wrote.

   GET  /state?k=<key>   -> { hidden: {...}, placed: {...}, picks: {...}, at: <ms> }
   POST /state?k=<key>   <- the same shape, stored whole

   The key is a secret on the Pages project (STATE_KEY), not in the page: the
   site is public, and without it anybody who found this address could empty
   the hidden shelf. A device is given the key once, by a link, and keeps it.
   No key set on the project and nothing is served, so the page falls back to
   its own storage and nothing breaks (Jose, Sep 19, 2026).
*/
const SLOT = "board";

function ok(body, extra) {
  return new Response(JSON.stringify(body), {
    headers: Object.assign({
      "content-type": "application/json",
      "cache-control": "no-store"
    }, extra || {})
  });
}

function allowed(request, env) {
  if (!env.STATE_KEY) return false;
  const url = new URL(request.url);
  const said = url.searchParams.get("k") || request.headers.get("x-arena-key") || "";
  return said === env.STATE_KEY;
}

export async function onRequest({ request, env }) {
  if (!env.ARENA) return ok({ error: "no store" }, { "x-arena": "unbound" });
  if (!allowed(request, env)) return new Response("no", { status: 403 });

  if (request.method === "GET") {
    const held = await env.ARENA.get(SLOT);
    return ok(held ? JSON.parse(held) : { hidden: {}, placed: {}, picks: {}, at: 0 });
  }

  if (request.method === "POST" || request.method === "PUT") {
    let body = null;
    try {
      body = await request.json();
    } catch (e) {
      return new Response("bad", { status: 400 });
    }
    const keep = {
      hidden: body && body.hidden && typeof body.hidden === "object" ? body.hidden : {},
      placed: body && body.placed && typeof body.placed === "object" ? body.placed : {},
      picks: body && body.picks && typeof body.picks === "object" ? body.picks : {},
      at: Date.now()
    };
    await env.ARENA.put(SLOT, JSON.stringify(keep));
    return ok({ at: keep.at });
  }

  return new Response("no", { status: 405 });
}
