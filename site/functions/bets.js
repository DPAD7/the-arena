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
    /* the reader's login as DraftKings last re-issued it, locked with a key
       only the reader holds (build/dk_bets.py) */
    if (new URL(request.url).searchParams.get("jar")) return ok({ jar: await env.ARENA.get("dkbets:jar") });
    /* the login his own browser sent (tools/dk-bets): handed back only to the
       reader, which holds ASK_SECRET -- never to the page */
    /* what login is held, without a single value: how many cookies and when */
    if (new URL(request.url).searchParams.get("loginmeta")) {
      const l = JSON.parse((await env.ARENA.get("dkbets:login")) || "{}");
      return ok({ cookies: Object.keys(l.cookies || {}).length, at: l.at || 0 });
    }
    if (new URL(request.url).searchParams.get("login")) {
      if (!env.ASK_SECRET || request.headers.get("x-ask-secret") !== env.ASK_SECRET) return ok({ error: "no" }, 403);
      const l = await env.ARENA.get("dkbets:login");
      return ok(l ? JSON.parse(l) : {});
    }
    const held = await env.ARENA.get(SLOT);
    return ok(held ? JSON.parse(held) : { balance: null, bets: [], at: 0 });
  }

  if (request.method === "POST") {
    let body = null;
    try { body = await request.json(); } catch (e) { return ok({ error: "bad" }, 400); }
    /* the bag's double tap: start a read of the book now (.github/workflows/
       dkbets.yml), at most once a minute, and say when it was asked for so
       the page can watch for a sync newer than that */
    if (body && body.pull) {
      if (!env.GH_TOKEN) return ok({ error: "no GH_TOKEN" }, 500);
      const last = parseInt((await env.ARENA.get("dkbets:pull")) || "0", 10);
      const now = Date.now();
      if (now - last < 60000) return ok({ asked: last, again: true });
      await env.ARENA.put("dkbets:pull", String(now));
      const r = await fetch("https://api.github.com/repos/DPAD7/the-arena/actions/workflows/dkbets.yml/dispatches", {
        method: "POST",
        headers: { "authorization": "Bearer " + env.GH_TOKEN, "accept": "application/vnd.github+json",
                   "user-agent": "the-arena-bets", "content-type": "application/json" },
        body: JSON.stringify({ ref: "main", inputs: { key: String(now) } })
      });
      return ok({ asked: now, started: r.status === 204 || r.status === 200 }, r.status === 204 || r.status === 200 ? 200 : 502);
    }
    /* the extension's login: the DraftKings cookies from his logged-in
       browser, sent whenever DraftKings is open, so an expired login mends
       itself without an export (Jose, Sep 29, 2026: "without having to go
       back and forth"). Write-only from here; only the reader reads it back */
    if (body && body.login && typeof body.login === "object" && body.login.cookies) {
      const txt = JSON.stringify({ cookies: body.login.cookies, at: Date.now() });
      if (txt.length > 60000) return ok({ error: "big" }, 400);
      await env.ARENA.put("dkbets:login", txt);
      return ok({ login: true });
    }
    if (body && typeof body.jar === "string") {
      if (body.jar.length > 60000) return ok({ error: "big" }, 400);
      await env.ARENA.put("dkbets:jar", body.jar);
      return ok({ kept: true });
    }
    /* the reader's login no longer works: said, so the bag goes red, and
       what was held is kept */
    if (body && body.expired) {
      let held = null;
      try { held = JSON.parse((await env.ARENA.get(SLOT)) || "null"); } catch (e) { held = null; }
      held = held || { balance: null, bets: [], at: 0 };
      held.expired = Date.now();
      await env.ARENA.put(SLOT, JSON.stringify(held));
      return ok({ expired: held.expired });
    }
    const bets = Array.isArray(body && body.bets) ? body.bets.slice(0, 500) : [];
    /* only open bets are sent, so an empty list can be the truth: it is taken
       when the sync also read a balance, which says the page had drawn; with
       no balance it is a page that had not, and what was there is kept */
    let keep = null;
    try { keep = JSON.parse((await env.ARENA.get(SLOT)) || "null"); } catch (e) { keep = null; }
    const drew = typeof body.balance === "number";
    /* the free tier is a thousand writes a day: a sync that found nothing new
       is not written, unless a double tap is waiting on it (Sep 26, 2026) */
    if (keep && drew && keep.balance === body.balance &&
        JSON.stringify(keep.bets || []) === JSON.stringify(bets) && !keep.expired) {
      const asked = parseInt((await env.ARENA.get("dkbets:pull")) || "0", 10);
      if (!(asked > (keep.at || 0))) return ok({ at: keep.at, bets: bets.length, same: true });
    }
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
