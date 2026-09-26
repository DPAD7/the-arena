/* The board's own marks, kept on the site instead of in each browser.

   Hidden games, placed prices and the slip lived in localStorage, so the
   phone, the iPad and the desktop each had their own and none of them
   agreed. There is one reader here, so there is one blob: whatever the last
   device wrote.

   GET  /state?k=<key>   -> { hidden: {...}, placed: {...}, picks: {...}, at: <ms> }
   POST /state?k=<key>   <- the same shape, stored whole

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
  try { const held = JSON.parse((await env.ARENA.get(SLOT)) || "null"); return (held && held.bank) || null; }
  catch (e) { return null; }
}
export async function onRequest({ request, env }) {
  if (!env.ARENA) return ok({ error: "no store" }, { "x-arena": "unbound" });
  if (!allowed(request, env)) return new Response("no", { status: 403 });

  if (request.method === "GET") {
    const held = await env.ARENA.get(SLOT);
    return ok(held ? JSON.parse(held) : { hidden: {}, placed: {}, picks: {}, ring: {}, at: 0 });
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
      /* the men ringed gold on the ledger, by ESPN id. A field left out here
         is a field thrown away on the next write, so anything the board keeps
         has to be named (Jose, Sep 20, 2026) */
      ring: body && body.ring && typeof body.ring === "object" ? body.ring : {},
      /* the balance behind the dollar button: what it stands at, the legs it
         has seen, and which runs of legs it has already settled */
      bank: body && body.bank && typeof body.bank === "object" ? body.bank : await heldBank(env),
      at: Date.now()
    };
    /* the same marks again are not written again: the free tier allows a
       thousand writes a day, and every open device saves as it settles */
    try {
      const held = JSON.parse((await env.ARENA.get(SLOT)) || "null");
      if (held) {
        const a = Object.assign({}, held, { at: 0 }), b = Object.assign({}, keep, { at: 0 });
        if (JSON.stringify(a) === JSON.stringify(b)) return ok({ at: held.at, same: true });
      }
    } catch (e) {}
    await env.ARENA.put(SLOT, JSON.stringify(keep));
    return ok({ at: keep.at });
  }

  return new Response("no", { status: 405 });
}
