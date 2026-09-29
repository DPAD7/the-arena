import { store } from "./_store.js";
/* The board's own marks, kept on the site instead of in each browser.

   Hidden games, placed prices and the slip lived in localStorage, so the
   phone, the iPad and the desktop each had their own and none of them
   agreed. There is one reader here, so there is one blob: whatever the last
   device wrote.

   GET  /state?k=<key>   -> { hidden: {...}, placed: {...}, picks: {...}, at: <ms> }
   POST /state?k=<key>   <- {patch: {field: {set: {...}, del: [...]}}}: the entries a
                            device changed, laid over what is held. A whole field
                            sent instead replaces that field; the rest are kept

   It answers without a key. The board is one man's, every device has to work
   the moment it opens the site, and a handshake per browser was friction he
   would meet forever (Jose, Sep 19, 2026: "I don't want to have to change
   anything"). What it holds is a list of games put away, the prices marked as
   placed, and the slip -- nothing worth taking -- and the address is not
   written anywhere a reader would see. If it is ever found, allowed() is the
   one place to put a key back.
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
  if (!env.STATE_KEY) return true;
  const url = new URL(request.url);
  const said = url.searchParams.get("k") || request.headers.get("x-arena-key") || "";
  return said === env.STATE_KEY;
}

/* a write that carries no balance keeps the one already held: a device that
   has not read the store yet must never wipe it (Sep 25, 2026) */
async function heldBank(env) {
  try { const held = JSON.parse((await store(env).get(SLOT)) || "null"); return (held && held.bank) || null; }
  catch (e) { return null; }
}
export async function onRequest({ request, env }) {
  if (!env.ARENA) return ok({ error: "no store" }, { "x-arena": "unbound" });
  if (!allowed(request, env)) return new Response("no", { status: 403 });

  if (request.method === "GET") {
    const held = await store(env).get(SLOT);
    return ok(held ? JSON.parse(held) : { hidden: {}, placed: {}, picks: {}, ring: {}, at: 0 });
  }

  if (request.method === "POST" || request.method === "PUT") {
    let body = null;
    try {
      body = await request.json();
    } catch (e) {
      return new Response("bad", { status: 400 });
    }
    /* a write carries only the marks that device changed, and they are laid
       over what is held: a device left open with an older copy used to send
       everything it held, and so put back gold he had taken off elsewhere
       (Jose, Sep 28, 2026: "every time you refresh it goes back on") */
    let held0 = null;
    try { held0 = JSON.parse((await store(env).get(SLOT)) || "null"); } catch (e) { held0 = null; }
    held0 = held0 || { hidden: {}, placed: {}, picks: {}, ring: {}, stars: {}, bank: null };
    const obj = (k) => body && body[k] && typeof body[k] === "object" ? body[k] : null;
    const keep = {
      hidden: obj("hidden") || held0.hidden || {},
      placed: obj("placed") || held0.placed || {},
      picks: obj("picks") || held0.picks || {},
      /* the men ringed gold on the ledger, by ESPN id */
      ring: obj("ring") || held0.ring || {},
      /* the starred quarterbacks in the search's row (Sep 28, 2026) */
      stars: obj("stars") || held0.stars || {},
      /* the balance behind the dollar button */
      bank: obj("bank") || held0.bank || null,
      at: Date.now()
    };
    /* a patch: the entries one device changed, laid over the list held */
    const patch = body && body.patch && typeof body.patch === "object" ? body.patch : {};
    for (const k of ["hidden", "placed", "picks", "ring", "stars"]) {
      const p = patch[k];
      if (!p || typeof p !== "object") continue;
      const out = Object.assign({}, keep[k] || {});
      for (const x of (Array.isArray(p.del) ? p.del : [])) delete out[x];
      Object.assign(out, p.set && typeof p.set === "object" ? p.set : {});
      keep[k] = out;
    }
    /* the same marks again are not written again: the free tier allows a
       thousand writes a day, and every open device saves as it settles */
    // compared with what was read above, not read a second time
    if (held0 && held0.at) {
      const a = Object.assign({}, held0, { at: 0 }), b = Object.assign({}, keep, { at: 0 });
      if (JSON.stringify(a) === JSON.stringify(b)) return ok({ at: held0.at, same: true });
    }
    await store(env).put(SLOT, JSON.stringify(keep));
    return ok({ at: keep.at });
  }

  return new Response("no", { status: 405 });
}
