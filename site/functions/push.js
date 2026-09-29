/* The phone's side of the alerts, handed to the clock (clock/clock.js), which
   keeps the subscription and his settings in its own storage -- not in the
   board's store, whose daily cap the marks already lean on.

     GET  /push                    -> {prefs, subs, opened, key}
     POST /push {sub}              the phone's push subscription
     POST /push {drop: endpoint}   forget one
     POST /push {prefs: {...}}     which kinds of alert are on
     POST /push {test: true}       send one now
     POST /push {opened: type}     he opened one of this kind
*/
const KEY = "BMW0ZmiZS6joDa-NPhSXxdQzPVvFrLnx9ILj1wI95dbycBv0Z7Y577PoP1-8djkMjHwwGcR4U6Yy3fZ29z8SNZg";

export async function onRequest({ request, env }) {
  if (!env.CLOCK) return Response.json({ error: "no clock bound" }, { status: 500 });
  const stub = env.CLOCK.get(env.CLOCK.idFromName("board"));
  const json = (x, s) => new Response(JSON.stringify(x), { status: s || 200, headers: { "content-type": "application/json", "cache-control": "no-store" } });
  if (request.method === "GET") {
    const r = await (await stub.fetch("https://clock/prefs")).json();
    return json(Object.assign(r, { key: KEY }));
  }
  if (request.method !== "POST") return json({ error: "no" }, 405);
  let b = {};
  try { b = await request.json(); } catch (e) { return json({ error: "bad" }, 400); }
  const post = (path, body) => stub.fetch("https://clock/" + path, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  if (b.sub || b.drop) return json(await (await post("sub", { sub: b.sub, drop: b.drop })).json());
  if (b.prefs) return json(await (await post("prefs", b.prefs)).json());
  if (b.test) return json(await (await post("test", {})).json());
  if (b.opened) return json(await (await post("opened", { type: b.opened })).json());
  return json({ error: "nothing asked" }, 400);
}
