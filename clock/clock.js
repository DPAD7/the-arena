/* The board's clock.

   GitHub woke every ten minutes, all day, to ask "is anything due?", and on
   most wakes nothing was (Jose, Sep 29, 2026: "why would it go off every 10
   minutes ... there's specific rules to this"). This holds one alarm, set to
   the next moment that matters and nothing between:

     the three sweeps           9, 15, 21 ET           (refresh.py SWEEP_ET)
     the hubs                   10 ET                  (HUB_ET)
     the DraftKings login touch  11 ET                  (KEEP_ET)
     before each start          120, 60, 30 minutes    (BEFORE: prices, inactives)
     the injury report          3:30-7 p.m. ET, each half hour, on each
                                game's three practice-report days (REPORT_DAYS)
     a card or a game running   every ten minutes while it runs (the live passes)
     a game's final             from two and a half hours after kickoff, every
                                two minutes until ESPN says final -- then the
                                site saves it (/settled) with no phone open
     the day's last final       one close-out pass (refresh.py --day-end)

   Each wake starts GitHub through the site's /wake (which holds the token)
   and sets the next alarm. The moments come from site/schedule.json, which
   every build writes. A daily cron re-arms it in case an alarm is ever lost.
*/
import { sendPush } from "./push.js";
import { legIndex, readGame, readBout, news, liveLegs, slipState, risks, espnGet, legState } from "./watch.js";
const SITE = "https://the-arenasports.pages.dev";
// every kind of alert, on until he turns it off (the alert settings)
const PREFS = { td: true, redzone: true, wp: true, final: true, slip: true, leghit: true, pregame: true, change: true, fight: true, recap: true };
const SWEEP_ET = [9, 15, 21];
const HUB_ET = [10];
// the daily touch of the DraftKings login, so it never expires on him
// (Jose, Sep 30, 2026: the wallet went red after two weeks without a read)
const KEEP_ET = [];   // no touches: the reader runs on his double tap, as it always did (Jose, Sep 30, 2026)
const BEFORE = [120, 60, 30];
// the NFL's practice reports, by kickoff weekday (0 = Sunday): the report days
const REPORT_DAYS = { 0: [3, 4, 5], 1: [4, 5, 6], 4: [1, 2, 3], 5: [2, 3, 4], 6: [2, 3, 4], 3: [0, 1, 2] };
const MIN = 60000;
const CARD_MS = 6 * 60 * MIN;        // a fight card runs about six hours
const GAME_MS = 4 * 60 * MIN;        // a football game about three and a half
const END_AFTER = 150 * MIN;         // no game is over before this
const GIVE_UP = 7 * 60 * MIN;        // past this the sweep's catch-all has it

/* Eastern wall clock: its parts for an instant, and the instant for its parts */
function etParts(ms) {
  const f = new Intl.DateTimeFormat("en-US", { timeZone: "America/New_York", hourCycle: "h23",
    year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", weekday: "short" });
  const p = {};
  for (const x of f.formatToParts(new Date(ms))) p[x.type] = x.value;
  return { y: +p.year, m: +p.month, d: +p.day, h: +p.hour, mi: +p.minute,
           wd: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].indexOf(p.weekday),
           date: p.year + "-" + p.month + "-" + p.day };
}
function etMs(y, m, d, h, mi) {
  let guess = Date.UTC(y, m - 1, d, h, mi);
  for (let k = 0; k < 2; k++) {
    const p = etParts(guess);
    const off = Date.UTC(p.y, p.m - 1, p.d, p.h, p.mi) - guess;
    guess = Date.UTC(y, m - 1, d, h, mi) - off;
  }
  return guess;
}
function dayShift(date, n) {
  const t = new Date(date + "T12:00:00Z"); t.setUTCDate(t.getUTCDate() + n);
  return t.toISOString().slice(0, 10);
}

export class Clock {
  constructor(ctx, env) { this.ctx = ctx; this.env = env; }

  async fetch(request) {
    const url = new URL(request.url);
    /* an open page: a live line down which the clock sends the games that
       just changed, so the page stops asking ESPN every ten seconds (Jose,
       Sep 29, 2026: "live without asking") */
    if (request.headers.get("Upgrade") === "websocket") {
      const pair = new WebSocketPair();
      this.ctx.acceptWebSocket(pair[1]);
      const at = await this.ctx.storage.getAlarm();
      if (!at || at > Date.now() + 15000) await this.ctx.storage.setAlarm(Date.now() + 5000);
      return new Response(null, { status: 101, webSocket: pair[0] });
    }
    /* the board's own store, always current: his marks, the slip, the
       wallet's bets and the double taps' records. KV could hand back a copy a
       minute old and capped its daily writes; this cannot do either (Jose,
       Sep 29, 2026: "how does it work for sportsbooks but not us") */
    if (url.pathname.endsWith("/kv")) {
      if (request.method === "GET") {
        const rec = await this.ctx.storage.get("kv:" + url.searchParams.get("k"));
        if (!rec || (rec.exp && rec.exp < Date.now())) return new Response(null, { status: 404 });
        return new Response(rec.v, { headers: { "content-type": "text/plain" } });
      }
      const b = await request.json();
      if (b.del) await this.ctx.storage.delete("kv:" + b.k);
      else await this.ctx.storage.put("kv:" + b.k, { v: String(b.v), exp: b.ttl ? Date.now() + b.ttl * 1000 : 0 });
      return Response.json({ ok: true });
    }
    // the phone's push subscription, his alert settings, a test
    if (url.pathname.endsWith("/sub") && request.method === "POST") {
      const b = await request.json();
      const subs = (await this.ctx.storage.get("subs")) || {};
      if (b.sub && b.sub.endpoint) subs[b.sub.endpoint] = b.sub;
      if (b.drop) delete subs[b.drop];
      await this.ctx.storage.put("subs", subs);
      return Response.json({ subs: Object.keys(subs).length });
    }
    // which alerts went out, newest first, for checking one was sent
    if (url.pathname.endsWith("/sent")) {
      const sent = (await this.ctx.storage.get("sent")) || {};
      return Response.json(Object.entries(sent).sort((a, b) => b[1] - a[1]).slice(0, 40));
    }
    if (url.pathname.endsWith("/prefs")) {
      let prefs = Object.assign({}, PREFS, (await this.ctx.storage.get("prefs")) || {});
      if (request.method === "POST") {
        const b = await request.json();
        for (const k of Object.keys(PREFS)) if (k in b) prefs[k] = !!b[k];
        await this.ctx.storage.put("prefs", prefs);
      }
      const subs = (await this.ctx.storage.get("subs")) || {};
      return Response.json({ prefs, subs: Object.keys(subs).length, opened: (await this.ctx.storage.get("opened")) || {} });
    }
    if (url.pathname.endsWith("/cliplog")) {
      const log = (await this.ctx.storage.get("cliplog")) || [];
      if (request.method === "POST") {
        const b = await request.json();
        log.unshift(Object.assign({ at: new Date().toISOString() }, b));
        await this.ctx.storage.put("cliplog", log.slice(0, 120));
        return Response.json({ ok: true });
      }
      return Response.json(log);
    }
    if (url.pathname.endsWith("/opened") && request.method === "POST") {
      // which alerts he opens, to cut the ones he never does
      const b = await request.json(), op = (await this.ctx.storage.get("opened")) || {};
      const t = String(b.type || "other"); op[t] = (op[t] || 0) + 1;
      await this.ctx.storage.put("opened", op);
      return Response.json({ ok: true });
    }
    /* a fault on the board, from the watcher on GitHub (build/triage.py):
       one alert per fault a day, on the phone with the rest (Jose, Sep 30,
       2026: "add a notification system so if that happens it sends you") */
    if (url.pathname.endsWith("/fault") && request.method === "POST") {
      const b = await request.json();
      const day = new Date().toISOString().slice(0, 10);
      const n = await this.tell([{ key: "fault@" + (b.key || b.title || "") + "@" + day, type: "fault", tag: "fault",
                                   title: String(b.title || "The board hit a fault").slice(0, 80),
                                   body: String(b.body || "").slice(0, 200), url: b.url || "/" }], 0);
      return Response.json({ sent: n });
    }
    if (url.pathname.endsWith("/test") && request.method === "POST") {
      const n = await this.tell([{ key: "test@" + Date.now(), type: "test", title: "Alerts are on", body: "This is what they look like.", url: "/" }], 0);
      return Response.json({ sent: n });
    }
    if (url.pathname.endsWith("/debug")) {
      let sched = [];
      try { sched = await (await fetch(SITE + "/schedule.json")).json(); } catch (e) { sched = []; }
      let res = null, err = null;
      try { res = await this.livePush(sched, Date.now()); } catch (e) { err = String(e); }
      let probe = null;
      try { const r = await espnGet("https://site.web.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=" + etParts(Date.now()).date.replace(/-/g, "")); probe = r.status + " " + (await r.text()).slice(0, 160); } catch (e) { probe = "ERR " + e; }
      const cards = sched.filter(r => r[0] === "card" && r[3] === "mma" && Date.parse(r[2]) <= Date.now() + 10 * MIN && Date.now() - Date.parse(r[2]) < 7 * 60 * MIN).map(r => r[1]);
      return Response.json({ sockets: this.ctx.getWebSockets().length, sched: sched.length, cards, livePush: res, err, probe });
    }
    if (url.pathname.endsWith("/status")) {
      const done = (await this.ctx.storage.get("done")) || {};
      const at = await this.ctx.storage.getAlarm();
      return Response.json({ next: at ? new Date(at).toISOString() : null,
                             recent: Object.entries(done).sort((a, b) => b[1] - a[1]).slice(0, 25) });
    }
    await this.tick();
    const at = await this.ctx.storage.getAlarm();
    return Response.json({ armed: at ? new Date(at).toISOString() : null });
  }

  async alarm() { await this.tick(); }
  async webSocketMessage(ws, msg) {}
  async webSocketClose(ws) { try { ws.close(); } catch (e) {} }

  /* while a page is open and football is being played: one scoreboard read
     per league and day, and the games whose score, clock or down moved */
  async livePush(sched, now) {
    const socks = this.ctx.getWebSockets();
    if (!socks.length) return false;
    const on = sched.filter(r => r[0] === "game" && Date.parse(r[2]) <= now + 10 * MIN && now - Date.parse(r[2]) < 5 * 60 * MIN);
    // a fight card running: its bouts on the same line, on a faster beat --
    // a knockout lands on any second (Jose, Sep 29, 2026)
    const cards = sched.filter(r => r[0] === "card" && r[3] === "mma" && Date.parse(r[2]) <= now + 10 * MIN && now - Date.parse(r[2]) < 7 * 60 * MIN);
    if (!on.length && !cards.length) return false;
    let fighting = false;
    const fsig = (await this.ctx.storage.get("fightsig")) || {}, bouts = [];
    for (const ymd of new Set(cards.map(r => etParts(Date.parse(r[2])).date.replace(/-/g, "")))) {
      try {
        const j = await (await espnGet("https://site.web.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=" + ymd)).json();
        for (const e of j.events || []) for (const c of e.competitions || []) {
          const st = c.status || {}, state = (st.type || {}).state;
          if (state === "in") fighting = true;
          const w = (c.competitors || []).filter(m => m.winner).map(m => m.id).join("");
          const now1 = [state, st.period, st.displayClock, w].join("|");
          if (fsig[c.id] !== undefined && fsig[c.id] !== now1) bouts.push(String(c.id));
          fsig[c.id] = now1;
        }
      } catch (e) {}
    }
    await this.ctx.storage.put("fightsig", fsig);
    if (bouts.length) for (const ws of socks) { try { ws.send(JSON.stringify({ bouts })); } catch (e) {} }
    const sig = (await this.ctx.storage.get("livesig")) || {}, changed = [];
    const asks = new Set(on.map(r => r[3] + "|" + etParts(Date.parse(r[2])).date.replace(/-/g, "")));
    let playing = false;
    for (const a of asks) {
      const [lg, ymd] = a.split("|");
      try {
        const j = await (await espnGet("https://site.web.api.espn.com/apis/site/v2/sports/football/" + lg + "/scoreboard?dates=" + ymd + (lg === "college-football" ? "&groups=80&limit=400" : ""))).json();
        for (const e of j.events || []) {
          const c = (e.competitions || [])[0] || {}, st = c.status || {};
          if (((st.type || {}).state) === "in") playing = true;
          const now1 = [((st.type || {}).state), st.displayClock, st.period, (c.competitors || []).map(x => x.score).join("-"),
                        ((c.situation || {}).downDistanceText || ""), ((c.situation || {}).possession || "")].join("|");
          if (sig[e.id] !== undefined && sig[e.id] !== now1) changed.push(String(e.id));
          sig[e.id] = now1;
        }
      } catch (e) {}
    }
    await this.ctx.storage.put("livesig", sig);
    if (changed.length) for (const ws of socks) { try { ws.send(JSON.stringify({ changed })); } catch (e) {} }
    return fighting ? "fight" : playing;
  }

  /* one pass at a time: the daily re-arm and the alarm fired together at
     13:00 UTC, the 9 AM sweep, and each started a sweep -- the second one
     then could not put its commit on the first's (Oct 1 and Oct 2, 2026) */
  async tick() {
    if (this.ticking) return this.ticking;
    this.ticking = this.tickOnce().finally(() => { this.ticking = null; });
    return this.ticking;
  }

  async tickOnce() {
    const now = Date.now();
    let sched = [];
    try { sched = await (await fetch(SITE + "/schedule.json", { cf: { cacheTtl: 0 } })).json(); } catch (e) { sched = []; }
    const done = (await this.ctx.storage.get("done")) || {};
    for (const k of Object.keys(done)) if (now - done[k] > 3 * 86400000) delete done[k];
    const moments = this.moments(sched, now);
    // every moment that has come and not been served: one run serves them all
    const came = moments.filter(m => m.at <= now + 30000 && m.at > now - 20 * MIN && !done[m.key]);
    const keep = came.filter(m => m.key.startsWith("keep@")), due = came.filter(m => !m.key.startsWith("keep@"));
    if (due.length) {
      // claimed before the wake, so nothing else can start the same sweep
      for (const m of due) done[m.key] = now;
      await this.ctx.storage.put("done", done);
      const ok = await this.wake("due");
      if (!ok) { for (const m of due) delete done[m.key]; await this.ctx.storage.put("done", done); }
    }
    // the login's daily touch is its own run (dkbets.yml --keep), not a sweep
    if (keep.length) {
      const ok = await this.wake("keep");
      if (ok) for (const m of keep) done[m.key] = now;
    }
    // finals, with no phone needed
    const watch = await this.finals(sched, now, done);
    // the day's close-out, once every game of the day is final
    await this.dayEnd(sched, now, done);
    // his slips: what their games are doing, and what is worth a push
    let live = false;
    try { live = await this.slips(sched, now); } catch (e) { live = false; }
    await this.ctx.storage.put("done", done);
    // the next alarm: the next moment, or the next final check
    let next = now + 6 * 60 * MIN;
    for (const m of moments) if (m.at > now + 30000 && !done[m.key] && m.at < next) next = m.at;
    if (watch.checking) next = Math.min(next, now + 2 * MIN);
    // a game with his money on it is being played: look every minute
    if (live) next = Math.min(next, now + MIN);
    // a page open while football is on: every fifteen seconds
    let pushing = false;
    try { pushing = await this.livePush(sched, now); } catch (e) { pushing = false; }
    if (pushing) next = Math.min(next, now + (pushing === "fight" ? 5000 : 15000));
    // a bout with his money on it is on: alerts every fifteen seconds
    if (live === "fight") next = Math.min(next, now + 15000);
    if (watch.nextEnd && watch.nextEnd > now) next = Math.min(next, watch.nextEnd);
    await this.ctx.storage.setAlarm(Math.max(now + (pushing === "fight" ? 5000 : pushing ? 15000 : live === "fight" ? 15000 : 30000), next));
  }

  moments(sched, now) {
    const out = [], today = etParts(now).date;
    for (const date of [today, dayShift(today, 1)]) {
      const [y, m, d] = date.split("-").map(Number);
      for (const h of SWEEP_ET) out.push({ key: "sweep@" + date + " " + h, at: etMs(y, m, d, h, 0) });
      for (const h of HUB_ET) out.push({ key: "hub@" + date + " " + h, at: etMs(y, m, d, h, 0) });
      for (const h of KEEP_ET) out.push({ key: "keep@" + date + " " + h, at: etMs(y, m, d, h, 0) });
      // the injury report: this date is a report day for some NFL game
      const wd = new Date(date + "T12:00:00Z").getUTCDay();
      const report = sched.some(r => {
        if (r[0] !== "game" || r[3] !== "nfl") return false;
        const kp = etParts(Date.parse(r[2]));
        const gap = Math.round((Date.parse(kp.date + "T12:00:00Z") - Date.parse(date + "T12:00:00Z")) / 86400000);
        return gap >= 1 && gap <= 4 && (REPORT_DAYS[kp.wd] || []).includes(wd);
      });
      if (report) for (let t = 15 * 60 + 30; t < 19 * 60; t += 30)
        out.push({ key: "report@" + date + " " + t, at: etMs(y, m, d, Math.floor(t / 60), t % 60) });
    }
    for (const r of sched) {
      // a bout rides its card's moments; it starts nothing of its own
      if (r[0] === "bout") continue;
      const start = Date.parse(r[2]);
      if (!(start > now - 12 * 60 * MIN && start < now + 36 * 60 * MIN)) continue;
      for (const b of BEFORE) out.push({ key: "pre@" + r[1] + "@" + b, at: start - b * MIN });
      // while it runs, a pass every ten minutes on the ten-minute grid
      const span = r[0] === "card" ? CARD_MS : (r[3] === "nfl" ? GAME_MS : 0);
      if (span && now >= start && now < start + span) {
        const slot = Math.floor(now / (10 * MIN)) * 10 * MIN;
        for (const t of [slot, slot + 10 * MIN])
          if (t >= start && t < start + span) out.push({ key: "live@" + r[1] + "@" + t, at: t });
      }
    }
    return out;
  }

  async finals(sched, now, done) {
    const open = sched.filter(r => r[0] === "game" && Date.parse(r[2]) < now && now - Date.parse(r[2]) < GIVE_UP && !done["final@" + r[1]]);
    const ready = open.filter(r => now - Date.parse(r[2]) >= END_AFTER);
    let nextEnd = null;
    for (const r of open) {
      const e = Date.parse(r[2]) + END_AFTER;
      if (e > now && (!nextEnd || e < nextEnd)) nextEnd = e;
    }
    if (!ready.length) return { checking: false, nextEnd };
    // one scoreboard read per league and date covers every game on it
    const want = new Set(ready.map(r => r[1])), seenFinal = [];
    const asks = new Set(ready.map(r => r[3] + "|" + etParts(Date.parse(r[2])).date.replace(/-/g, "")));
    for (const a of asks) {
      const [lg, ymd] = a.split("|");
      const url = "https://site.web.api.espn.com/apis/site/v2/sports/football/" + lg + "/scoreboard?dates=" + ymd +
                  (lg === "college-football" ? "&groups=80&limit=400" : "");
      try {
        const j = await (await espnGet(url)).json();
        for (const e of j.events || []) {
          const st = ((((e.competitions || [])[0] || {}).status || {}).type) || {};
          if (want.has(String(e.id)) && (st.state === "post" || st.completed)) seenFinal.push(String(e.id));
        }
      } catch (e) {}
    }
    if (seenFinal.length) {
      try {
        const r = await fetch(SITE + "/settled", { method: "POST", headers: { "content-type": "application/json" },
                                                   body: JSON.stringify({ games: seenFinal }) });
        if (r.ok) for (const g of seenFinal) done["final@" + g] = now;
      } catch (e) {}
    }
    return { checking: ready.length > seenFinal.length, nextEnd };
  }

  async dayEnd(sched, now, done) {
    // a date whose every football game has started and gone final
    const byDay = {};
    for (const r of sched) {
      if (r[0] !== "game") continue;
      const date = etParts(Date.parse(r[2])).date;
      (byDay[date] = byDay[date] || []).push(r);
    }
    const today = etParts(now).date;
    for (const date of [dayShift(today, -1), today]) {
      const games = byDay[date] || [];
      if (!games.length || done["dayend@" + date]) continue;
      if (games.every(r => done["final@" + r[1]])) {
        if (await this.wake("dayend")) done["dayend@" + date] = now;
      }
    }
  }

  /* his open slips, read while their games are on */
  async slips(sched, now) {
    if (!this.env.ARENA) return false;
    let held = null;
    try {
      const own = await this.ctx.storage.get("kv:dkbets");
      held = JSON.parse((own && own.v) || (await this.env.ARENA.get("dkbets")) || "null");
    } catch (e) { held = null; }
    // and the slips he added to the wallet himself (Oct 3, 2026)
    let sent = [];
    try {
      const s0 = await this.ctx.storage.get("kv:dkbets:sent");
      sent = JSON.parse((s0 && s0.v) || (await this.env.ARENA.get("dkbets:sent")) || "[]");
    } catch (e) { sent = []; }
    /* only the slips he tracks: the DraftKings read was retired Oct 3, and its
       last copy (an Oct 1 parlay still "open") was counted in the first recap
       (Jose, Oct 6, 2026: "we already moved away from that") */
    const slips = sent.filter(b => (b.legs || []).length);
    if (!slips.length) return false;
    const rows = {};
    for (const r of sched) if (r[0] === "game" || r[0] === "bout") rows[r[1]] = r;
    let prices = {};
    try { prices = await (await fetch(SITE + "/prices.json")).json(); } catch (e) { return false; }
    const idx = legIndex(prices, sched);
    // a fight moneyline whose DraftKings id moved with its price: the bout it
    // was tracked on and the name on it still say which man (Oct 3, 2026: Silva)
    for (const bet of slips) for (const l of bet.legs || []) {
      if (idx[l.sel] || !l.g || !/\u2016\s*ML\b/.test(String(l.label || l.pick || ""))) continue;
      const r = rows[l.g]; if (!r || r[0] !== "bout") continue;
      const who = String(l.label || l.pick).split("\u2016")[0].trim().toLowerCase();
      const a = String(r[4]).toLowerCase().split(" ").pop(), b = String(r[5]).toLowerCase().split(" ").pop();
      const side = who.includes(a) && !who.includes(b) ? 0 : who.includes(b) && !who.includes(a) ? 1 : -1;
      if (side >= 0) idx[l.sel] = { gid: String(l.g), kind: "fml", side, fight: 1, who: side ? r[5] : r[4] };
    }
    const out = [];
    // the half hour before a slip's first game: a reminder, with anything on
    // the injury wire about the passers on it
    let wire = null;
    for (const bet of slips) {
      const starts = (bet.legs || []).map(l => idx[l.sel]).filter(Boolean).map(v => Date.parse(rows[v.gid][2]));
      if (!starts.length) continue;
      const first = Math.min(...starts);
      if (first - now > 20 * MIN && first - now <= 40 * MIN) {
        if (!wire) { try { wire = await (await fetch(SITE + "/wire.json")).json(); } catch (e) { wire = {}; } }
        const qbs = [...new Set((bet.legs || []).map(l => idx[l.sel]).filter(v => v && v.qb).map(v => v.qb))];
        const hurt = qbs.map(q => wire[String(q)] && wire[String(q)].status ? (idx && Object.values(idx).find(v => v.qb === q) || {}).qbName + " is " + wire[String(q)].status.toLowerCase() : "").filter(Boolean);
        const r0 = Object.values(rows).find(r => Date.parse(r[2]) === first);
        out.push({ key: "pre@" + bet.id, type: "pregame", title: "Your " + (bet.odds || "") + " slip starts soon",
                   body: (r0 ? r0[4] + " @ " + r0[5] + " kicks off in 30 minutes." : "First game in 30 minutes.") + (hurt.length ? " " + hurt.join("; ") + "." : ""),
                   url: "/#slip=" + bet.id });
      }
    }
    // the games on his legs being played now
    const want = new Set();
    for (const bet of slips) for (const l of bet.legs || []) {
      const v = idx[l.sel]; if (!v) continue;
      const st = Date.parse(rows[v.gid][2]);
      /* a slip is only settled when its last leg is, so every leg on it is
         read until then: a fight from the 4 PM prelims had dropped out of
         the window by the time the main event ended, and the win was never
         said (Oct 3, 2026: Silva won and no alert came) */
      if (now >= st - 5 * MIN && now < st + 16 * 60 * MIN) want.add(v.gid);
    }
    const prev = (await this.ctx.storage.get("prev")) || {};
    const games = {};
    if (want.size) {
      const boards = {};
      for (const gid of want) {
        const r = rows[gid], ymd = etParts(Date.parse(r[2])).date.replace(/-/g, ""), k = r[3] + ymd;
        if (r[3] === "boxing") continue;       // no live feed: DraftKings' own word settles it
        if (!boards[k]) {
          const u = r[0] === "bout"
            ? "https://site.web.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=" + ymd
            : "https://site.web.api.espn.com/apis/site/v2/sports/football/" + r[3] + "/scoreboard?dates=" + ymd + (r[3] === "college-football" ? "&groups=80&limit=400" : "");
          try { boards[k] = await (await espnGet(u)).json(); } catch (e) { boards[k] = {}; }
        }
        games[gid] = r[0] === "bout" ? readBout(gid, boards[k]) : await readGame(gid, r[3], boards[k]);
      }
    }
    // a fight on his slip is up next: the bout before it on ESPN's card (which
    // lists them in fight order) has walked out or started, and his has not.
    // A card's printed times are its segments' starts, not each fight's, so
    // the order is the clock (Jose, Oct 3, 2026: "tell me before each fight")
    const cards = {};
    for (const bet of slips) {
      if ((bet.legs || []).some(l => String(l.status || "").toLowerCase() === "lost")) continue;
      for (const l of bet.legs || []) {
        const v = idx[l.sel]; if (!v || !v.fight) continue;
        const r = rows[v.gid]; if (!r || r[3] === "boxing") continue;
        const st = Date.parse(r[2]);
        if (now < st - 3 * 60 * MIN || now > st + 7 * 60 * MIN) continue;
        const ymd = etParts(st).date.replace(/-/g, "");
        if (!cards[ymd]) {
          try { cards[ymd] = await (await espnGet("https://site.web.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=" + ymd)).json(); } catch (e) { cards[ymd] = {}; }
        }
        for (const ev of cards[ymd].events || []) {
          const cs = ev.competitions || [], i = cs.findIndex(c => String(c.id) === String(v.gid));
          if (i < 1) continue;
          const me = ((cs[i].status || {}).type || {}).state, before = ((cs[i - 1].status || {}).type || {}).state;
          /* the bout before it has just ended: his walkout is about five
             minutes off (Jose, Oct 3, 2026: "five minutes before walkout") */
          if (me !== "pre" || before !== "post") continue;
          const nm = c => (c.competitors || []).map(m => ((m.athlete || {}).shortName || "").split(" ").pop()).join(" vs ");
          out.push({ tag: "slip:" + bet.id, key: "walk@" + v.gid, type: "pregame", title: nm(cs[i]) + " walks out in about 5 minutes",
                     body: nm(cs[i - 1]) + " just ended. Your " + ((l.label || l.pick || "").split(" \u00b7 ")[0] || "leg") + " is next.",
                     url: "/#bout=" + v.gid });
        }
      }
    }
    // the result written onto the slips he tracked himself, so every device
    // opens on it settled, not after its own reading of every game (Oct 3,
    // 2026: all six won and his phone still showed Smith open)
    try {
      let moved = false;
      for (const bet of sent) {
        for (const l of bet.legs || []) {
          const v = idx[l.sel], g = v && games[v.gid], r = v && rows[v.gid];
          if (!v || !g) continue;
          const st = legState(v, g, v.fight || !r ? null : (v.side ? r[7] : r[9]), r);
          if ((st === "won" || st === "lost") && String(l.status || "").toLowerCase() !== st) { l.status = st; moved = true; }
        }
        const ls = (bet.legs || []).map(l => String(l.status || "").toLowerCase());
        const bs = ls.includes("lost") ? "lost" : ls.length && ls.every(x => x === "won") ? "won" : "open";
        if (bet.status !== bs) { bet.status = bs; moved = true; }
      }
      if (moved) {
        const s1 = await this.ctx.storage.get("kv:dkbets:sent");
        await this.ctx.storage.put("kv:dkbets:sent", { v: JSON.stringify(sent), exp: (s1 && s1.exp) || 0 });
      }
    } catch (e) {}
    // changes on a leg after it was bet: a teammate ruled out, his passer
    // downgraded -- the first read of a leg is only remembered, never said
    const future = [];
    for (const bet of slips) for (const l of bet.legs || []) {
      const v = idx[l.sel];
      if (v && !v.fight && Date.parse(rows[v.gid][2]) > now) future.push({ bet, l, v });
    }
    if (future.length) {
      let alerts = {};
      try { alerts = await (await fetch(SITE + "/alerts.json")).json(); } catch (e) { alerts = {}; }
      if (!wire) { try { wire = await (await fetch(SITE + "/wire.json")).json(); } catch (e) { wire = {}; } }
      const was = (await this.ctx.storage.get("risk")) || {};
      for (const x of future) {
        const now1 = risks(x.v, alerts[x.v.gid] || {}, wire);
        if (was[x.l.sel]) {
          for (const said of now1) if (!was[x.l.sel].includes(said))
            out.push({ key: "chg@" + x.l.sel + "@" + said, type: "change", title: "Change on your " + ((x.l.label || x.l.pick || "").split(" · ")[0] || "leg"),
                       body: said, url: "/#slip=" + x.bet.id });
        }
        was[x.l.sel] = now1;
      }
      await this.ctx.storage.put("risk", was);
    }
    // each slip's end, kept for the week's recap
    const hist = (await this.ctx.storage.get("hist")) || {};
    for (const bet of slips) {
      /* the slip's own settled status first, and a result that changes is
         rewritten rather than kept from its first read -- the Oct 3 parlay
         was read as lost mid-settle (Jose, Oct 6, 2026) */
      const own = String(bet.status || "").toLowerCase();
      const st = own === "won" || own === "lost" ? own : slipState(bet, idx, games, rows);
      if (st !== "won" && st !== "lost") continue;
      if (!hist[bet.id]) hist[bet.id] = { res: st, wager: +bet.wager || 0, pay: +bet.topay || 0, at: now };
      else hist[bet.id].res = st;
    }
    const et = etParts(now);
    /* the week is Tuesday through Monday Night Football; it is told on
       Tuesday from 10 AM, once nothing he bet that week is still being
       played (Jose, Oct 6, 2026) */
    const stillOn = slips.some(bet => slipState(bet, idx, games, rows) === "open" && now - Date.parse(bet.placed || 0) < 8 * 86400000);
    if (et.wd === 2 && et.h >= 10 && !stillOn) {
      const wk = Object.values(hist).filter(h => now - h.at < 7 * 86400000);
      if (wk.length) {
        const won = wk.filter(h => h.res === "won"), lost = wk.filter(h => h.res === "lost");
        const net = won.reduce((t, h) => t + h.pay, 0) - wk.reduce((t, h) => t + h.wager, 0);
        out.push({ key: "recap@" + et.date, type: "recap", title: "Your week",
                   body: won.length + " won, " + lost.length + " lost · " + (net >= 0 ? "+$" : "−$") + Math.abs(net).toFixed(2) + ".", url: "/" });
      }
    }
    for (const k of Object.keys(hist)) if (now - hist[k].at > 60 * 86400000) delete hist[k];
    await this.ctx.storage.put("hist", hist);
    for (const m of news(slips, idx, games, prev, rows)) out.push(m);
    const badge = liveLegs(slips, idx, games, rows);
    await this.tell(out, badge);
    const keep = {};
    for (const [gid, g] of Object.entries(games)) keep[gid] = { qb: g.qb, state: g.state };
    await this.ctx.storage.put("prev", Object.assign(prev, keep));
    if (Object.entries(games).some(([gid, g]) => rows[gid] && rows[gid][0] === "bout" && g.state === "in")) return "fight";
    return Object.values(games).some(g => g.state === "in") || [...want].some(gid => !games[gid] || games[gid].state === "pre");
  }

  /* send what has not been sent, of the kinds he has on */
  async tell(msgs, badge) {
    if (!msgs.length || !this.env.VAPID_JWK) return 0;
    const prefs = Object.assign({}, PREFS, (await this.ctx.storage.get("prefs")) || {});
    const sent = (await this.ctx.storage.get("sent")) || {};
    const subs = (await this.ctx.storage.get("subs")) || {};
    const jwk = JSON.parse(this.env.VAPID_JWK);
    let n = 0;
    for (const m of msgs) {
      if (sent[m.key] || (m.type in prefs && !prefs[m.type])) continue;
      sent[m.key] = Date.now();
      for (const [ep, sub] of Object.entries(subs)) {
        try {
          // one alert per slip that replaces itself as its legs move -- the free
          // stand-in for DraftKings' Live Activity (Jose, Sep 29, 2026)
          const st = await sendPush(sub, { title: m.title, body: m.body, url: m.url, tag: m.tag || m.key, type: m.type, badge }, jwk);
          if (st === 404 || st === 410) delete subs[ep]; else n++;
        } catch (e) {}
      }
    }
    for (const k of Object.keys(sent)) if (Date.now() - sent[k] > 14 * 86400000) delete sent[k];
    await this.ctx.storage.put("sent", sent);
    await this.ctx.storage.put("subs", subs);
    return n;
  }

  async wake(mode) {
    try {
      const r = await fetch(SITE + "/wake", { method: "POST",
        headers: { "content-type": "application/json", "x-wake": this.env.WAKE_SECRET || "" },
        body: JSON.stringify({ mode }) });
      return r.ok;
    } catch (e) { return false; }
  }
}

export default {
  async fetch(request, env) {
    const stub = env.CLOCK.get(env.CLOCK.idFromName("board"));
    return stub.fetch(request);
  },
  // once a day, in case an alarm was ever lost: re-arm
  async scheduled(event, env) {
    const stub = env.CLOCK.get(env.CLOCK.idFromName("board"));
    await stub.fetch("https://clock/arm");
  }
};
