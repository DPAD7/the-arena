import { store } from "./_store.js";
/* The clock's door to GitHub.

   clock/clock.js (a Worker holding one alarm) calls this at each moment that
   matters, and this starts .github/workflows/sweep.yml with the token the site
   already holds. GitHub no longer wakes itself every ten minutes to ask
   whether anything is due (Jose, Sep 29, 2026).

     POST /wake   x-wake: <the clock's secret>   {"mode": "due" | "dayend", "moments": "k1,k2"}

   "moments" are the clock's keys for what this wake serves (sweep@<date> <h>,
   pre@<id>@<min>, report@<date> <min>, live@<id>@<ms>), passed on as the
   sweep's "moments" input so a run that starts late still does the work
   (Oct 12, 2026).

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

/* the clock's keys, comma-joined: an array or a string, only the characters
   a key is made of, whole keys only, under GitHub's input size */
export function momentsOf(m) {
  const list = (Array.isArray(m) ? m : String(m || "").split(","))
    .map(k => String(k).trim()).filter(k => k && /^[\w@.:+\- ]+$/.test(k));
  let out = "";
  for (const k of [...new Set(list)]) {
    if (out.length + k.length + 1 > 60000) break;
    out += (out ? "," : "") + k;
  }
  return out;
}

export async function onRequest({ request, env }) {
  if (request.method === "GET") {
    if (!env.CLOCK) return ok({ error: "no clock bound" }, 500);
    const stub = env.CLOCK.get(env.CLOCK.idFromName("board"));
    // ?arm sets it going (or going again): one tick, then its own alarm
    const q = new URL(request.url).searchParams;
    return stub.fetch(q.has("arm") ? "https://clock/arm" : q.has("debug") ? "https://clock/debug" : "https://clock/status");
  }
  if (request.method !== "POST") return ok({ error: "no" }, 405);
  if (!env.ARENA || !env.GH_TOKEN) return ok({ error: "not set up" }, 500);
  const want = await store(env).get("clock:wake");
  const said = request.headers.get("x-wake") || "";
  if (!want || said !== want) return ok({ error: "no" }, 403);
  let body = {};
  try { body = await request.json(); } catch (e) { body = {}; }
  /* every wake is the sweep; the DraftKings login touch ("keep") is gone --
     the login is read on his double tap (Oct 12, 2026) */
  /* football on: DraftKings' live reader; a slip due its result: DraftKings'
     settler -- each its own workflow (Oct 17, 2026) */
  if (body.mode === "dklive" || body.mode === "dksettle") {
    const r = await fetch("https://api.github.com/repos/DPAD7/the-arena/actions/workflows/" + body.mode + ".yml/dispatches", {
      method: "POST",
      headers: { "authorization": "Bearer " + env.GH_TOKEN, "accept": "application/vnd.github+json",
                 "content-type": "application/json", "user-agent": "the-arena-clock" },
      body: JSON.stringify({ ref: "main" })
    });
    return ok({ started: r.status === 204, mode: body.mode }, r.status === 204 ? 200 : 502);
  }
  const mode = body.mode === "dayend" ? "dayend" : "due";
  const moments = momentsOf(body.moments);
  const inputs = { mode: mode };
  if (moments) inputs.moments = moments;
  const send = (inp) => fetch("https://api.github.com/repos/DPAD7/the-arena/actions/workflows/sweep.yml/dispatches", {
    method: "POST",
    headers: { "authorization": "Bearer " + env.GH_TOKEN, "accept": "application/vnd.github+json",
               "content-type": "application/json", "user-agent": "the-arena-clock" },
    body: JSON.stringify({ ref: "main", inputs: inp })
  });
  let r = await send(inputs);
  /* a sweep.yml on main without the "moments" input answers 422 to it: the
     sweep still starts, on its own reading of what is due (Oct 12, 2026) */
  let plain = false;
  if (r.status === 422 && inputs.moments) { r = await send({ mode: mode }); plain = true; }
  return ok({ started: r.status === 204, mode: mode, moments: plain ? "" : moments }, r.status === 204 ? 200 : 502);
}
