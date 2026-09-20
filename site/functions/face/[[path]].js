/* GET /face/<league>/<id>.png

   The page asks here, not at /faces/, because /faces/ is a real directory
   and Pages answers a missing file under it with index.html and a 200 --
   and _headers marks /faces/* immutable for a month, so a browser that asked
   for a man before the sweep had mirrored him kept the web page under his
   name and drew the silhouette on every load after. /face/ has no directory
   behind it, so every request comes through here: a picture we hold is
   served with the month's caching set on it; one we do not is a 404, which
   no browser keeps (Jose, Sep 20, 2026). */
export async function onRequestGet({ request, env }) {
  const u = new URL(request.url);
  const path = u.pathname.replace(/^\/face\//, "");
  if (!/^(nfl|college-football|mma)\/[A-Za-z0-9_-]+\.png$/.test(path)) {
    return new Response("", { status: 404, headers: { "cache-control": "no-store" } });
  }
  const r = await env.ASSETS.fetch(new URL("/faces/" + path, u.origin));
  const type = r.headers.get("content-type") || "";
  if (!r.ok || !/^image\//i.test(type)) {
    return new Response("", { status: 404, headers: { "cache-control": "no-store" } });
  }
  return new Response(r.body, {
    status: 200,
    headers: {
      "content-type": type,
      "cache-control": "public, max-age=2592000, immutable"
    }
  });
}
