/* The double tap: the prices a card is missing, asked for there and then.

   The sweep reads DraftKings three times a day. A price posted between two
   sweeps sat unread until the next one, so a double tap on the board asks
   for the games in front of him now (Jose, Sep 23, 2026). The site cannot
   read DraftKings itself -- Akamai turns away anything that does not shake
   hands like Chrome -- so this starts .github/workflows/ask.yml, which runs
   build/ask_dk.py over only those games and posts what it read back here.

   From the page:

     POST /ask            {"games": ["401872948", ...]}
                       -> {"key": K, "state": "running", "games": [...], "again": false}
                          again is true when the same games were already
                          being asked about today and that run is handed back
                          instead of a second one

     GET  /ask?key=K   -> {"key": K, "state": "running" | "done" | "failed",
                           "prices": {game id: <the shape of site/prices/<id>.json>},
                           "missing": [game id, ...],
                           "why": {game id: "started" | "unmapped (...)" | ...}}

   From the run (signed with ASK_SECRET, which the page never holds):

     POST /ask            x-ask-secret: S
                          {"key": K, "prices": {...}, "missing": [...], "why": {...}}

   From the sweep, which folds these into the files (build/ask_fold.py):

     GET  /ask?all=1      x-ask-secret: S
                       -> {"prices": {game id: {"price": {...}, "at": ms}}}

   Kept in the board's own store, ARENA, beside his marks:
     ask:run:<key>     one tap: which games, which run, what came back
     ask:price:<id>    the last reading of one game, for three weeks
     ask:hour:<hour>   how many runs were started that hour

   The page asks without a key, like /state. What it can do with that is
   start a run over at most MOST_GAMES game ids, once per set of games in
   flight and at most RUNS_AN_HOUR times an hour; an id that is not on the
   board comes back missing, "unmapped (not on the board)".
*/
const REPO = "DPAD7/the-arena";
const FLOW = "ask.yml";
const RUNS_AN_HOUR = 30;
const MOST_GAMES = 40;
const PRICE_DAYS = 21;
// every game's asked price, in one record (was one "ask:price:<game>" each)
const PRICES = "ask:prices";
// a tap whose run has not been seen on GitHub by now never started
const NO_RUN_MS = 3 * 60 * 1000;
// the same games asked again this soon after an answer get that answer
const FRESH_MS = 2 * 60 * 1000;
// a run that finished without posting is given this long for the post to
// show up here -- the store is eventually consistent across Cloudflare's
// cities -- before the tap is called failed
const SETTLE_MS = 180 * 1000;

function ok(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { "content-type": "application/json", "cache-control": "no-store" }
  });
}

function signed(request, env) {
  const said = request.headers.get("x-ask-secret");
  if (said === null) return null;
  const want = env.ASK_SECRET || "";
  if (!want || said.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= said.charCodeAt(i) ^ want.charCodeAt(i);
  return diff === 0;
}

/* the board's day, in Eastern time: a Sunday night game is still Sunday */
function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit"
  }).format(new Date());
}

async function keyFor(games) {
  const bytes = new TextEncoder().encode(games.join(","));
  const hash = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  const hex = Array.from(hash.slice(0, 6), b => b.toString(16).padStart(2, "0")).join("");
  return today() + "-" + hex;
}

function ids(list) {
  if (!Array.isArray(list)) return [];
  const seen = new Set();
  for (const one of list) {
    const s = String(one == null ? "" : one).trim();
    if (/^\d{5,12}$/.test(s)) seen.add(s);
  }
  return Array.from(seen).sort();
}

async function readJSON(env, key) {
  // no edge cache: a poll must see the answer the moment it is posted
  const held = await env.ARENA.get(key);
  if (!held) return null;
  try { return JSON.parse(held); } catch (e) { return null; }
}

function github(env, path, init) {
  // GH_API is only ever set to stand GitHub in for a local test
  return fetch((env.GH_API || "https://api.github.com") + "/repos/" + REPO + path, Object.assign({}, init, {
    headers: {
      "authorization": "Bearer " + env.GH_TOKEN,
      "accept": "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "the-arena-ask",
      "content-type": "application/json"
    }
  }));
}

/* Start the run. GitHub answers a dispatch with the run's number when it is
   asked to; where it does not, the run is found afterwards by its name,
   which carries the key (run-name in ask.yml). */
async function dispatch(env, games, key) {
  const r = await github(env, "/actions/workflows/" + FLOW + "/dispatches", {
    method: "POST",
    body: JSON.stringify({
      ref: "main",
      inputs: { games: games.join(","), key: key },
      return_run_details: true
    })
  });
  if (r.status === 204) return { run: null, url: null };
  if (r.status === 200) {
    const d = await r.json().catch(() => ({}));
    return { run: d.workflow_run_id || null, url: d.html_url || null };
  }
  const why = await r.text().catch(() => "");
  throw new Error("GitHub said " + r.status + ": " + why.slice(0, 200));
}

async function findRun(env, rec) {
  const since = new Date(rec.at - 60 * 1000).toISOString();
  const r = await github(env, "/actions/workflows/" + FLOW +
    "/runs?event=workflow_dispatch&per_page=20&created=%3E%3D" + encodeURIComponent(since));
  if (!r.ok) return null;
  const d = await r.json().catch(() => ({}));
  const want = "ask " + rec.key;
  for (const run of d.workflow_runs || []) {
    if ((run.display_title || run.name) === want &&
        Date.parse(run.created_at) >= rec.at - 60 * 1000) return run;
  }
  return null;
}

async function runOf(env, rec) {
  if (rec.run) {
    const r = await github(env, "/actions/runs/" + rec.run);
    if (r.ok) return await r.json().catch(() => null);
    return null;
  }
  return await findRun(env, rec);
}

async function pricesFor(env, games) {
  const out = {}, all = (await readJSON(env, PRICES)) || {};
  games.forEach(gid => { if (all[gid] && all[gid].price) out[gid] = all[gid].price; });
  return out;
}

/* ---------------------------------------------------------------- the page */

async function tap(request, env) {
  let body = null;
  try { body = await request.json(); } catch (e) { return ok({ error: "bad" }, 400); }
  const games = ids(body && body.games);
  if (!games.length) return ok({ error: "no games" }, 400);
  if (games.length > MOST_GAMES) return ok({ error: "too many games" }, 400);
  if (!env.GH_TOKEN) return ok({ error: "no GH_TOKEN" }, 500);

  const key = await keyFor(games);
  const slot = "ask:run:" + key;
  const rec = await readJSON(env, slot);
  const now = Date.now();
  if (rec) {
    // answered a moment ago: the answer stands, nobody runs again
    if (rec.result && now - rec.result.at < FRESH_MS) {
      return ok({ key, state: "done", games, again: true });
    }
    // still out: hand back the run already going
    if (!rec.result) {
      let going = now - rec.at < NO_RUN_MS;
      const run = await runOf(env, rec).catch(() => null);
      if (run) going = run.status !== "completed";
      if (going) return ok({ key, state: "running", games, again: true });
    }
  }

  const hour = "ask:hour:" + new Date().toISOString().slice(0, 13);
  const count = parseInt((await env.ARENA.get(hour)) || "0", 10) || 0;
  if (count >= RUNS_AN_HOUR) return ok({ key, state: "failed", error: "enough runs this hour" }, 429);
  await env.ARENA.put(hour, String(count + 1), { expirationTtl: 2 * 3600 });

  let started;
  try {
    started = await dispatch(env, games, key);
  } catch (e) {
    return ok({ key, state: "failed", games, error: String(e.message || e) }, 502);
  }
  await env.ARENA.put(slot, JSON.stringify({
    key, games, at: now, run: started.run, url: started.url, result: null
  }), { expirationTtl: 2 * 86400 });
  return ok({ key, state: "running", games, again: false });
}

async function poll(url, env) {
  const key = url.searchParams.get("key") || "";
  if (!/^\d{4}-\d{2}-\d{2}-[0-9a-f]{12}$/.test(key)) return ok({ error: "no key" }, 400);
  const slot = "ask:run:" + key;
  const rec = await readJSON(env, slot);
  if (!rec) return ok({ key, state: "failed", prices: {}, missing: [], why: {}, error: "no such tap" }, 404);

  if (rec.result) {
    const priced = rec.result.priced || [];
    return ok({
      key, state: "done",
      prices: await pricesFor(env, priced),
      missing: rec.result.missing || [],
      why: rec.result.why || {}
    });
  }

  const now = Date.now();
  let state = "running";
  const run = await runOf(env, rec).catch(() => null);
  if (run) {
    if (!rec.run && run.id) {
      rec.run = run.id;
      rec.url = run.html_url || null;
      await env.ARENA.put(slot, JSON.stringify(rec), { expirationTtl: 2 * 86400 });
    }
    if (run.status === "completed") {
      const ended = Date.parse(run.updated_at || "") || now;
      // a failed run posts nothing; a good one may simply not be visible
      // here yet
      if (run.conclusion !== "success" || now - ended > SETTLE_MS) state = "failed";
    }
  } else if (now - rec.at > NO_RUN_MS) {
    state = "failed";
  }
  return ok({
    key, state, prices: {},
    missing: state === "failed" ? rec.games : [],
    why: {}
  });
}

/* ------------------------------------------------------------------ the run */

async function answer(request, env) {
  let body = null;
  try { body = await request.json(); } catch (e) { return ok({ error: "bad" }, 400); }
  const key = String((body && body.key) || "");
  const prices = (body && body.prices && typeof body.prices === "object") ? body.prices : {};
  const now = Date.now();
  const priced = [];
  /* every game's price in one record, not one record a game: a tap of forty
     games was forty writes, and the free tier allows a thousand a day
     (Sep 28, 2026). A game older than PRICE_DAYS drops off as it is rewritten */
  const all = (await readJSON(env, PRICES)) || {};
  for (const gid of Object.keys(all)) {
    if (!all[gid] || now - (all[gid].at || 0) > PRICE_DAYS * 86400000) delete all[gid];
  }
  for (const gid of Object.keys(prices)) {
    if (!/^\d{5,12}$/.test(gid)) continue;
    const price = prices[gid];
    if (!price || typeof price !== "object") continue;
    all[gid] = { price, at: now, key };
    priced.push(gid);
  }
  if (priced.length) await env.ARENA.put(PRICES, JSON.stringify(all));
  if (key) {
    const slot = "ask:run:" + key;
    const rec = (await readJSON(env, slot)) || { key, games: [], at: now, run: null, url: null };
    rec.result = {
      at: now, priced,
      missing: ids(body.missing),
      why: (body.why && typeof body.why === "object") ? body.why : {}
    };
    await env.ARENA.put(slot, JSON.stringify(rec), { expirationTtl: 2 * 86400 });
  }
  return ok({ kept: priced.length });
}

async function everything(env) {
  /* one read for the sweep, where it was a list and a read per game on
     every run */
  const out = {}, all = (await readJSON(env, PRICES)) || {};
  for (const gid of Object.keys(all)) {
    if (all[gid] && all[gid].price) out[gid] = { price: all[gid].price, at: all[gid].at };
  }
  return ok({ prices: out });
}

export async function onRequest({ request, env }) {
  if (!env.ARENA) return ok({ error: "no store" }, 500);
  const url = new URL(request.url);
  const sig = signed(request, env);
  if (sig === false) return new Response("no", { status: 403 });

  if (request.method === "GET") {
    if (url.searchParams.get("all")) {
      if (sig !== true) return new Response("no", { status: 403 });
      return everything(env);
    }
    return poll(url, env);
  }
  if (request.method === "POST") {
    return sig === true ? answer(request, env) : tap(request, env);
  }
  return new Response("no", { status: 405 });
}
