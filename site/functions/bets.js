import { store } from "./_store.js";
/* The slips the board handed to DraftKings, and the balance he confirmed by
   hand, kept by the site so the wallet tracks them on every device.

   The DraftKings read is retired (Oct 12, 2026): the extension's sync of My
   Bets, the double tap that started a read on GitHub, and the login jar the
   reader kept are gone, and so are their branches here. What stays:

   GET  /bets?k=<key>                -> { sent: [...], wallet: {bal, at} | null }
   POST /bets?k=<key>  {sent: bet}   a slip "Add to betslip" handed over
   POST /bets?k=<key>  {unsent: id}  one taken back off
   POST /bets?k=<key>  {wallet: n}   his balance, confirmed once by hand
*/

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
    const out = {};
    try { out.sent = JSON.parse((await store(env).get("dkbets:sent")) || "[]"); } catch (e) { out.sent = []; }
    try { out.wallet = JSON.parse((await store(env).get("dkbets:wallet")) || "null"); } catch (e) { out.wallet = null; }
    return ok(out);
  }

  if (request.method === "POST") {
    let body = null;
    try { body = await request.json(); } catch (e) { return ok({ error: "bad" }, 400); }
    /* his balance, confirmed once by hand; the wallet counts from it */
    if (body && typeof body.wallet === "number" && isFinite(body.wallet)) {
      await store(env).put("dkbets:wallet", JSON.stringify({ bal: Math.round(body.wallet * 100) / 100, at: Date.now() }));
      return ok({ wallet: true });
    }
    /* a slip the board handed to DraftKings ("Add to betslip"), kept so the
       wallet tracks it with no DraftKings login (Oct 3, 2026); the last sixty,
       and one can be taken back off */
    if (body && (body.sent || body.unsent)) {
      let list = [];
      try { list = JSON.parse((await store(env).get("dkbets:sent")) || "[]"); } catch (e) { list = []; }
      if (body.unsent) list = list.filter(b => b.id !== body.unsent);
      if (body.sent && typeof body.sent === "object" && Array.isArray(body.sent.legs)) {
        list.push(body.sent);
        list = list.slice(-60);
      }
      const txt = JSON.stringify(list);
      if (txt.length > 200000) return ok({ error: "big" }, 400);
      await store(env).put("dkbets:sent", txt);
      return ok({ sent: list.length });
    }
    /* the book's own bets, its login and the read on a double tap: retired */
    return ok({ error: "retired" }, 410);
  }

  return ok({ error: "no" }, 405);
}
