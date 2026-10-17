import { store } from "./_store.js";
/* The double tap on the back of his phone: a placed DraftKings bet, read off
   a screenshot and put in the wallet (Jose, Oct 17, 2026: "just do the double
   tap reader").

   The phone's shortcut takes the screenshot, saves it to Photos as before,
   and reads its text on the phone. Only a screenshot showing a DraftKings
   bet ID is sent here, so nothing else he screenshots ever leaves the phone
   and nothing else costs a cent.

   Here Claude reads the slip -- legs, prices, wager, payout, boost, bet ID --
   and the reading is kept in the store. A bet already in the wallet is
   answered at once and read no further. The reading is then handed to
   .github/workflows/slip.yml, which ties each leg to its game and DraftKings'
   own selection id the way the wallet's legs are always tied (build/slip_track.py),
   and posts the bet to /bets. The site cannot do that part itself:
   DraftKings turns away anything that does not shake hands like Chrome.

     POST /slip?k=<key>   {"image": <base64 JPEG or PNG>}
                       -> {"say": "OSU, NU, TEX · $100 pays $348", "bets": n}
     GET  /slip?key=<bet id>        x-ask-secret: S   (the run reads it back)

   The model's key is ANTHROPIC_API_KEY, a Pages secret he set himself. At
   most DAY_CAP readings a day, so the month's free credit is never passed.
*/
const REPO = "DPAD7/the-arena";
const FLOW = "slip.yml";
const MODEL = "claude-sonnet-5-5";
const DAY_CAP = 50;

function ok(body, status) {
  return new Response(JSON.stringify(body), {
    status: status || 200,
    headers: { "content-type": "application/json", "cache-control": "no-store" }
  });
}

function signed(request, env) {
  const said = request.headers.get("x-ask-secret") || "";
  const want = env.ASK_SECRET || "";
  if (!want || said.length !== want.length) return false;
  let diff = 0;
  for (let i = 0; i < want.length; i++) diff |= said.charCodeAt(i) ^ want.charCodeAt(i);
  return diff === 0;
}

function today() {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/New_York", year: "numeric", month: "2-digit", day: "2-digit"
  }).format(new Date());
}

const ASK = `This is a screenshot of a DraftKings sportsbook bet (My Bets / My Activity, or the bet-placed receipt).
Read every bet that shows a Bet ID. Return JSON only, no prose, in exactly this shape:
{"bets":[{"bet_id":"DK639278387459988247","type":"Single|Parlay|SGP|SGPx","legs_said":3,
  "odds":"+248","was":"+165","boost":"50% Parlay Boost","wager":100.00,"topay":348.00,
  "placed":"2026-10-17T10:24:40","legs":[
   {"who":"Ohio State","team":"","market":"Moneyline","line":"","odds":"-162","game":"OSU vs IND","when":"Today 12:00 PM","status":"open"},
   {"who":"Julian Sayin","team":"OSU","market":"Passing Touchdowns","line":"2+","odds":"-155","game":"OSU vs IND","when":"","status":"open"}]}]}
Rules: "who" is the team or person exactly as written; "team" is the club tag in brackets after a person, else "".
"market" is the market as written (Moneyline, Spread, Total, Passing Touchdowns, Anytime Touchdown Scorer, Method of Victory...).
"line" is the pick's own line as written ("2+", "Over 47.5", "-3.5", "By KO/TKO"), "" for a moneyline.
"was" is the price before a boost, "" if none. "boost" as written, "" if none. "legs_said" is the leg count the slip states ("3 PICK PARLAY"), else the legs you read.
"status": "won" for a green check, "lost" for a red mark, else "open". "placed" in ISO local time if shown, else "".
Use "" or null for anything not visible. Never guess a value that is not on the screen. If no Bet ID is visible, return {"bets":[]}.`;

async function read(env, b64) {
  const media = b64.startsWith("/9j/") ? "image/jpeg" : "image/png";
  const r = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: {
      "x-api-key": env.ANTHROPIC_API_KEY,
      "anthropic-version": "2023-06-01",
      "content-type": "application/json"
    },
    body: JSON.stringify({
      model: MODEL,
      max_tokens: 2000,
      messages: [{ role: "user", content: [
        { type: "image", source: { type: "base64", media_type: media, data: b64 } },
        { type: "text", text: ASK }
      ] }]
    })
  });
  if (!r.ok) throw new Error("Claude said " + r.status + ": " + (await r.text()).slice(0, 200));
  const d = await r.json();
  const text = ((d.content || []).find(c => c.type === "text") || {}).text || "";
  const m = text.match(/\{[\s\S]*\}/);
  if (!m) throw new Error("no JSON in the reading");
  return JSON.parse(m[0]);
}

async function sentIds(env) {
  let list = [];
  try { list = JSON.parse((await store(env).get("dkbets:sent")) || "[]"); } catch (e) {}
  return new Set(list.map(b => String(b.id || "")));
}

function money(n) { return "$" + (Math.round(Number(n || 0) * 100) / 100).toFixed(2).replace(/\.00$/, ""); }

function short(bet) {
  const names = (bet.legs || []).map(l => {
    const w = String(l.who || "").trim();
    const last = w.split(" ").pop();
    return l.team ? last + " " + (l.line || "") : w;
  }).map(s => s.trim()).slice(0, 4).join(", ");
  return names + " · " + money(bet.wager) + " pays " + money(bet.topay);
}

async function dispatch(env, key) {
  const r = await fetch("https://api.github.com/repos/" + REPO + "/actions/workflows/" + FLOW + "/dispatches", {
    method: "POST",
    headers: {
      "authorization": "Bearer " + env.GH_TOKEN,
      "accept": "application/vnd.github+json",
      "x-github-api-version": "2022-11-28",
      "user-agent": "the-arena-slip",
      "content-type": "application/json"
    },
    body: JSON.stringify({ ref: "main", inputs: { key: key } })
  });
  if (r.status !== 204 && r.status !== 200) throw new Error("GitHub said " + r.status);
}

/* a DraftKings share link pasted on the wallet: the post carries the whole
   bet as the book holds it, read here with no login, and handed to
   share.yml (build/dk_share.py) to tie each leg to the board (Jose, Oct 17,
   2026: "a place to put the shared link and then it does it on its own") */
async function fromLink(env, link) {
  const m = /draftkings\.com\/social\/post\/([0-9a-f-]{36})/.exec(link || "");
  if (!m) return ok({ say: "That isn't a DraftKings bet link." }, 400);
  const r = await fetch("https://api.draftkings.com/comments/feed/post/details.json", {
    method: "POST", headers: { "content-type": "application/json", origin: "https://sportsbook.draftkings.com",
                               referer: "https://sportsbook.draftkings.com/" },
    body: JSON.stringify({ postKey: m[1] })
  });
  let bet = null;
  try {
    const d = await r.json();
    for (const e of (d.post || {}).postEntries || []) {
      let props = (e.metadataProperties || {}).properties || [];
      if (!Array.isArray(props)) props = [props];
      for (const p of props) if (p.name === "betJSON") bet = JSON.parse(atob(p.value));
    }
  } catch (e) {}
  /* DraftKings may turn the site away; the run on GitHub reads it either way */
  const id = bet && bet.betId ? "board-dk" + bet.betId : "";
  if (id && (await sentIds(env)).has(id)) return ok({ say: "Already in your wallet.", bets: 0 });
  const legs = bet ? (bet.combinationOutcomes || []).reduce((n, o) => n + ((o.nestedSGPSelections || []).length || 1), 0) : 0;
  const r2 = await fetch("https://api.github.com/repos/" + REPO + "/actions/workflows/share.yml/dispatches", {
    method: "POST",
    headers: { "authorization": "Bearer " + env.GH_TOKEN, "accept": "application/vnd.github+json",
               "x-github-api-version": "2022-11-28", "user-agent": "the-arena-slip", "content-type": "application/json" },
    body: JSON.stringify({ ref: "main", inputs: { link: "https://sportsbook.draftkings.com/social/post/" + m[1] } })
  });
  if (r2.status !== 204 && r2.status !== 200) return ok({ say: "Read it, but could not start the tracker." }, 502);
  return ok({ say: bet ? legs + " legs · " + money(bet.stake) + " pays " + money(bet.potentialPayout) + " · in your wallet in a minute"
                       : "Got it · in your wallet in a minute", bets: 1, id });
}

export async function onRequestPost({ request, env }) {
  let body = null;
  try { body = await request.json(); } catch (e) { return ok({ say: "That screenshot did not come through." }, 400); }
  if (body && body.link) return fromLink(env, body.link);
  if (!env.ANTHROPIC_API_KEY) return ok({ say: "The slip reader has no key yet." }, 500);
  const b64 = String((body && body.image) || "").replace(/^data:[^,]*,/, "").replace(/\s+/g, "");
  if (b64.length < 1000) return ok({ say: "That screenshot did not come through." }, 400);

  const dayKey = "slip:day:" + today();
  const used = parseInt((await store(env).get(dayKey)) || "0", 10) || 0;
  if (used >= DAY_CAP) return ok({ say: "Today's " + DAY_CAP + " slip readings are used up." }, 429);
  await store(env).put(dayKey, String(used + 1), { expirationTtl: 3 * 86400 });

  let got;
  try { got = await read(env, b64); } catch (e) { return ok({ say: "Could not read the slip: " + e.message }, 502); }
  const bets = (got && Array.isArray(got.bets) ? got.bets : []).filter(b => /\d{8,}/.test(String(b.bet_id || "")));
  if (!bets.length) return ok({ say: "No placed DraftKings bet on that screen.", bets: 0 });

  const have = await sentIds(env);
  const said = [], fresh = [];
  for (const bet of bets) {
    const id = "board-dk" + String(bet.bet_id).replace(/\D/g, "");
    bet.id = id;
    if (have.has(id)) { said.push("Already in the wallet: " + short(bet)); continue; }
    const n = (bet.legs || []).length;
    if (bet.legs_said && n < bet.legs_said) {
      said.push("Only " + n + " of " + bet.legs_said + " legs showed. Scroll so the whole slip is on screen and tap again.");
      continue;
    }
    fresh.push(bet);
    said.push(short(bet));
  }
  if (fresh.length) {
    const key = fresh.map(b => b.id.replace("board-dk", "")).join("-");
    await store(env).put("slip:read:" + key, JSON.stringify({ at: Date.now(), bets: fresh }), { expirationTtl: 7 * 86400 });
    try { await dispatch(env, key); } catch (e) { return ok({ say: "Read it, but could not start the tracker: " + e.message }, 502); }
  }
  return ok({ say: said.join("\n"), bets: fresh.length });
}

export async function onRequestGet({ request, env }) {
  if (!signed(request, env)) return ok({ error: "no" }, 403);
  const key = new URL(request.url).searchParams.get("key") || "";
  const held = await store(env).get("slip:read:" + key);
  return held ? new Response(held, { headers: { "content-type": "application/json", "cache-control": "no-store" } }) : ok({ error: "none" }, 404);
}
