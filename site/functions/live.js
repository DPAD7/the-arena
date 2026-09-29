/* The open page's live line to the clock (clock/clock.js): a WebSocket
   handed straight through to its Durable Object. */
export async function onRequest({ request, env }) {
  if (request.headers.get("Upgrade") !== "websocket") return new Response("websocket only", { status: 426 });
  if (!env.CLOCK) return new Response("no clock", { status: 500 });
  return env.CLOCK.get(env.CLOCK.idFromName("board")).fetch(request);
}
