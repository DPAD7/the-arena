/* GET /clip?game=<espn event id>&ext=<nfl externalId>  ->  { accessUrl, headline }
   GET /clip?mcp=<mcp id>                                ->  { accessUrl }

   The second form is what the clubs' own sites use: their pages carry only
   an mcpID, and nfl.com's play call answers it with no media object at all.

   NFL.com's playback call wants a bearer token and the clip's full media
   object. The media object comes from nflclips.json, which the page itself
   never has to load. The signed URL handed back lives fifteen minutes, so
   nothing here is cached but the token.

   The client arguments nfl.com ships to every browser are not kept in this
   repo. Set NFL_CLIENT_ID, NFL_CLIENT_KEY, NFL_CLIENT_SECRET and NFL_DEVICE_ID
   on the Pages project (Settings > Environment variables); the function reads
   them from env. Until they exist it answers 502 and the board falls back to
   ESPN's clips, so nothing on the page breaks. */

const TOKEN_URL = "https://api.nfl.com/identity/v3/token";
const ASSET_URL = "https://api.nfl.com/play/v1/asset/";
const NFL_HEADERS = {
  "content-type": "application/json",
  origin: "https://www.nfl.com",
  referer: "https://www.nfl.com/"
};

let token = null, tokenExp = 0;

function args(env) {
  if (!env.NFL_CLIENT_ID || !env.NFL_CLIENT_KEY || !env.NFL_CLIENT_SECRET) return null;
  return {
    clientId: env.NFL_CLIENT_ID,
    clientKey: env.NFL_CLIENT_KEY,
    clientSecret: env.NFL_CLIENT_SECRET,
    deviceId: env.NFL_DEVICE_ID || "00000000-0000-4000-8000-000000000000",
    deviceInfo: { model: "desktop", osName: "macOS", osVersion: "10.15.7", version: "Chrome" },
    networkType: "other"
  };
}

async function bearer(env) {
  const now = Math.floor(Date.now() / 1000);
  if (token && now < tokenExp - 60) return token;
  const a = args(env);
  if (!a) throw new Error("NFL client arguments not configured");
  const r = await fetch(TOKEN_URL, { method: "POST", headers: NFL_HEADERS, body: JSON.stringify(a) });
  if (!r.ok) throw new Error("token " + r.status);
  const j = await r.json();
  token = j.accessToken;
  tokenExp = Number(j.expiresIn) || (now + 3000);
  return token;
}

export async function onRequestGet({ request, env }) {
  const u = new URL(request.url);
  const game = u.searchParams.get("game") || "";
  const ext = u.searchParams.get("ext") || "";
  const say = (o, s) => new Response(JSON.stringify(o), {
    status: s || 200,
    headers: { "content-type": "application/json", "cache-control": "no-store" }
  });
  const mcp = u.searchParams.get("mcp") || "";
  let id, body, headline = "";
  if (/^\d{4,12}$/.test(mcp)) {
    id = mcp; body = {};
  } else {
    if (!/^\d+$/.test(game) || !/^[A-Za-z0-9_-]{8,40}$/.test(ext)) return say({ error: "bad request" }, 400);
    const lib = await env.ASSETS.fetch(new URL("/nflclips.json", request.url));
    if (!lib.ok) return say({ error: "no library" }, 500);
    const all = await lib.json();
    const clip = ((all[game] || {}).clips || []).find(c => c.externalId === ext);
    if (!clip) return say({ error: "no such clip" }, 404);
    id = ext; body = { asset: clip.mediaObject }; headline = clip.headline;
  }

  let t;
  try { t = await bearer(env); } catch (e) { return say({ error: String(e.message || e) }, 502); }
  const r = await fetch(ASSET_URL + id, {
    method: "POST",
    headers: Object.assign({ authorization: "Bearer " + t }, NFL_HEADERS),
    body: JSON.stringify(body)
  });
  if (!r.ok) return say({ error: "asset " + r.status }, 502);
  const j = await r.json();
  /* the sharpest rendition of the stream, read off its master playlist, so
     a story starts clear instead of climbing up from a blur (Jose, Sep 29,
     2026: "it's blurry then loads the next clip"); the master stays the
     fallback */
  let best = "";
  try {
    const m = await (await fetch(j.accessUrl)).text();
    let top = -1;
    const lines = m.split("\n");
    for (let i = 0; i < lines.length; i++) {
      const bw = /^#EXT-X-STREAM-INF:.*?BANDWIDTH=(\d+)/.exec(lines[i]);
      const next = (lines[i + 1] || "").trim();
      // the sharpest that still starts quickly on a phone's connection
      if (bw && next && !next.startsWith("#") && +bw[1] > top && +bw[1] <= 5000000) { top = +bw[1]; best = new URL(next, j.accessUrl).toString(); }
    }
  } catch (e) { best = ""; }
  return say({ accessUrl: j.accessUrl, best: best, headline: headline });
}
