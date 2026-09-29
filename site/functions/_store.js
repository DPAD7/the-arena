/* The board's store, in the clock's Durable Object (clock/clock.js /kv):
   always the latest copy, and none of KV's daily cap. It reads and writes the
   way KV did -- get, put with expirationTtl, delete -- so a function swaps
   env.ARENA for store(env) and nothing else changes. A key the Durable Object
   has never held is read once from KV and copied across, so nothing kept
   before the move is lost (Jose, Sep 29, 2026). */
export function store(env) {
  const stub = env.CLOCK.get(env.CLOCK.idFromName("board"));
  const post = (body) => stub.fetch("https://clock/kv", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  return {
    async get(k) {
      const r = await stub.fetch("https://clock/kv?k=" + encodeURIComponent(k));
      if (r.status === 200) return await r.text();
      const old = env.ARENA ? await env.ARENA.get(k) : null;
      if (old !== null && old !== undefined) await post({ k, v: old });
      return old;
    },
    async put(k, v, opts) {
      await post({ k, v: String(v), ttl: opts && opts.expirationTtl ? opts.expirationTtl : 0 });
    },
    async delete(k) { await post({ k, del: true }); }
  };
}
