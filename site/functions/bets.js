/* His DraftKings bets and balance, as the book shows them, sent from his own
   logged-in desktop tab by the DK Bets extension (tools/dk-bets).

   The board worked its balance out from the prices it had when a price was
   marked, and the book fills at whatever it shows when the slip goes in:
   Army was -198 on the board and -192 on the slip, and the board came out
   $2.79 short (Jose, Sep 26, 2026: "math is off"). The book's own numbers
   are the truth, so the board reads them from here.

   GET  /bets?k=<key>   -> { balance, bets: [...], at }
   POST /bets?k=<key>   <- { balance, bets: [...] }, stored whole
*/
const SLOT = "dkbets";

function ok(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: {
      "content-type": "application/json",
      "cache-control": "no-store",
      "access-control-allow-origin": "*",
      "access-control-allow-headers": "content-type, x-arena-key",
      "access-control-allow-methods": "GET, POST, OPTIONS"
    }
  });
}

function allowed(request, env) {
  if (!env.STATE_KEY) return true;
  const url = new URL(request.url);
  const said = url.searchParams.get("k") || request.headers.get("x-arena-key") || "";
  return said === env.STATE_KEY;
}

export async function onRequest({ request, env }) {
  if (request.method === "OPTIONS") return ok({});
  if (!env.ARENA) return ok({ error: "no store" }, 500);
  if (!allowed(request, env)) return ok({ error: "no" }, 403);

  if (request.method === "GET") {
    const held = await env.ARENA.get(SLOT);
    return ok(held ? JSON.parse(held) : { balance: null, bets: [], at: 0 });
  }

  if (request.method === "POST") {
    let body = null;
    try { body = await request.json(); } catch (e) { return ok({ error: "bad" }, 400); }
    const bets = Array.isArray(body && body.bets) ? body.bets.slice(0, 500) : [];
    /* only open bets are sent, so an empty list can be the truth: it is taken
       when the sync also read a balance, which says the page had drawn; with
       no balance it is a page that had not, and what was there is kept */
    let keep = null;
    try { keep = JSON.parse((await env.ARENA.get(SLOT)) || "null"); } catch (e) { keep = null; }
    const drew = typeof body.balance === "number";
    const out = {
      balance: drew ? body.balance : (keep && keep.balance) || null,
      bets: bets.length || drew ? bets : ((keep && keep.bets) || []),
      at: Date.now()
    };
    await env.ARENA.put(SLOT, JSON.stringify(out));
    return ok({ at: out.at, bets: out.bets.length });
  }

  return ok({ error: "no" }, 405);
}
