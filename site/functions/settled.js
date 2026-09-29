/* A game is final: save it once, now.

   The phone reads ESPN while a game is on and sees FINAL the moment it lands.
   Nothing used to be written then -- the card was final on that screen only,
   and the saved result (site/final/<id>.json, which the Form tab and the QB
   search are counted from) waited for a sweep hours later. Now the first
   device that sees a game go final says so here (/settled: /final is the
   folder of saved games, and a POST there never reached a function), and this starts
   .github/workflows/settle.yml, which saves every finished game still without
   a file, counts them in, and deploys (Jose, Sep 29, 2026: "as soon as it
   says final from ESPN ... it settles that final and it's final").

     POST /settled {"games": ["401872948", ...]}  -> {"started": [...], "had": [...]}

   Each game starts a run once: ARENA holds final:<id> after the first word
   of it, so twelve games ending at twelve moments on three devices start at
   most twelve runs, and a game told twice starts nothing. RUNS_AN_HOUR caps
   the rest. Like /state and /ask it answers without a key; a game id that is
   not finished costs one run that saves nothing.
*/
const REPO = "DPAD7/the-arena";
const FLOW = "settle.yml";
const RUNS_AN_HOUR = 40;
const KEEP_S = 60 * 60 * 24 * 21;

function ok(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { "content-type": "application/json", "cache-control": "no-store" }
  });
}

export async function onRequest({ request, env }) {
  if (request.method !== "POST") return ok({ error: "POST only" }, 405);
  if (!env.ARENA) return ok({ error: "no store" }, 500);
  if (!env.GH_TOKEN) return ok({ error: "no GH_TOKEN" }, 500);
  let body = null;
  try { body = await request.json(); } catch (e) { return ok({ error: "bad" }, 400); }
  const games = (Array.isArray(body && body.games) ? body.games : [])
    .map(String).filter(function (g) { return /^\d{6,12}$/.test(g); }).slice(0, 20);
  const fresh = [], had = [];
  for (const g of games) {
    if (await env.ARENA.get("final:" + g)) { had.push(g); continue; }
    fresh.push(g);
  }
  if (!fresh.length) return ok({ started: [], had: had });
  const hour = "final:hour:" + new Date().toISOString().slice(0, 13);
  const n = parseInt((await env.ARENA.get(hour)) || "0", 10) || 0;
  if (n >= RUNS_AN_HOUR) return ok({ started: [], had: had, held: fresh, why: "hourly cap" });
  const r = await fetch("https://api.github.com/repos/" + REPO + "/actions/workflows/" + FLOW + "/dispatches", {
    method: "POST",
    headers: {
      "authorization": "Bearer " + env.GH_TOKEN,
      "accept": "application/vnd.github+json",
      "content-type": "application/json",
      "user-agent": "the-arena-final"
    },
    body: JSON.stringify({ ref: "main", inputs: { games: fresh.join(",") } })
  });
  if (r.status !== 204) return ok({ started: [], had: had, error: "dispatch " + r.status }, 502);
  await env.ARENA.put(hour, String(n + 1), { expirationTtl: 7200 });
  for (const g of fresh) await env.ARENA.put("final:" + g, String(Date.now()), { expirationTtl: KEEP_S });
  return ok({ started: fresh, had: had });
}
