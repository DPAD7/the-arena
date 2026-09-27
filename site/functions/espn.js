/* GET /espn?u=<absolute espn url>  ->  that url's JSON, with CORS

   ESPN's own hosts send no Access-Control-Allow-Origin, so the page cannot
   read them directly. Nothing showed it, because a settled game is served
   from our own site/final/*.json and only a game still being played falls
   through to ESPN -- so the live numbers were silently never arriving, on
   every sport, not just college. (Jose spotted it on Syracuse at Pittsburgh,
   Sep 17, 2026.)

   Only ESPN's read-only hosts are proxied, and only GET, so this cannot be
   pointed at anything else. */

const HOSTS = [
  "site.api.espn.com",
  "site.web.api.espn.com",
  "sports.core.api.espn.com",
  "cdn.espn.com",
  /* theScore's box, when ESPN's is empty (Sep 26, 2026) */
  "api.thescore.com"
];

export async function onRequestGet({ request }) {
  const want = new URL(request.url).searchParams.get("u") || "";
  let target;
  try {
    target = new URL(want);
  } catch (e) {
    return json({ error: "bad url" }, 400);
  }
  if (target.protocol !== "https:" || HOSTS.indexOf(target.hostname) < 0) {
    return json({ error: "host not allowed" }, 403);
  }
  /* ESPN's edge is Akamai and refuses a bare machine call -- "Access Denied"
     -- so the request is made the way a browser makes it (Jose, Sep 17, 2026) */
  const r = await fetch(target.toString(), {
    headers: {
      accept: "application/json, text/plain, */*",
      "accept-language": "en-US,en;q=0.9",
      "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 " +
                    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
      referer: "https://www.espn.com/",
      origin: "https://www.espn.com"
    },
    cf: { cacheTtl: 5, cacheEverything: true }
  });
  const body = await r.text();
  return new Response(body, {
    status: r.status,
    headers: {
      "content-type": r.headers.get("content-type") || "application/json",
      "access-control-allow-origin": "*",
      "cache-control": "public, max-age=5"
    }
  });
}

function json(o, status) {
  return new Response(JSON.stringify(o), {
    status: status,
    headers: { "content-type": "application/json", "access-control-allow-origin": "*" }
  });
}
