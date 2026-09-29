import { store } from "./_store.js";
/* The clock's door to GitHub.

   clock/clock.js (a Worker holding one alarm) calls this at each moment that
   matters, and this starts .github/workflows/sweep.yml with the token the site
   already holds. GitHub no longer wakes itself every ten minutes to ask
   whether anything is due (Jose, Sep 29, 2026).

     POST /wake   x-wake: <the clock's secret>   {"mode": "due" | "dayend"}

   The secret is kept in ARENA as clock:wake and in the clock as WAKE_SECRET;
   anything else is refused.

     GET /wake    -> what the clock says: its next alarm and what it last served
*/
function ok(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { "content-type": "application/json", "cache-control": "no-store" }
  });
}

export async function onRequest({ request, env }) {
  if (request.method === "GET") {
    if (!env.CLOCK) return ok({ error: "no clock bound" }, 500);
    const stub = env.CLOCK.get(env.CLOCK.idFromName("board"));
    // ?arm sets it going (or going again): one tick, then its own alarm
    return stub.fetch(new URL(request.url).searchParams.has("arm") ? "https://clock/arm" : "https://clock/status");
  }
  if (request.method !== "POST") return ok({ error: "no" }, 405);
  if (!env.ARENA || !env.GH_TOKEN) return ok({ error: "not set up" }, 500);
  const want = await store(env).get("clock:wake");
  const said = request.headers.get("x-wake") || "";
  if (!want || said !== want) return ok({ error: "no" }, 403);
  let body = {};
  try { body = await request.json(); } catch (e) { body = {}; }
  const mode = body.mode === "dayend" ? "dayend" : "due";
  const r = await fetch("https://api.github.com/repos/DPAD7/the-arena/actions/workflows/sweep.yml/dispatches", {
    method: "POST",
    headers: { "authorization": "Bearer " + env.GH_TOKEN, "accept": "application/vnd.github+json",
               "content-type": "application/json", "user-agent": "the-arena-clock" },
    body: JSON.stringify({ ref: "main", inputs: { mode: mode } })
  });
  return ok({ started: r.status === 204, mode: mode }, r.status === 204 ? 200 : 502);
}
