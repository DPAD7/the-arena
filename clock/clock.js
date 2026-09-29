/* The board's clock.

   GitHub woke every ten minutes, all day, to ask "is anything due?", and on
   most wakes nothing was (Jose, Sep 29, 2026: "why would it go off every 10
   minutes ... there's specific rules to this"). This holds one alarm, set to
   the next moment that matters and nothing between:

     the three sweeps           9, 15, 21 ET           (refresh.py SWEEP_ET)
     the hubs                   10 ET                  (HUB_ET)
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
const SITE = "https://the-arenasports.pages.dev";
const SWEEP_ET = [9, 15, 21];
const HUB_ET = [10];
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

  async tick() {
    const now = Date.now();
    let sched = [];
    try { sched = await (await fetch(SITE + "/schedule.json", { cf: { cacheTtl: 0 } })).json(); } catch (e) { sched = []; }
    const done = (await this.ctx.storage.get("done")) || {};
    for (const k of Object.keys(done)) if (now - done[k] > 3 * 86400000) delete done[k];
    const moments = this.moments(sched, now);
    // every moment that has come and not been served: one run serves them all
    const due = moments.filter(m => m.at <= now + 30000 && m.at > now - 20 * MIN && !done[m.key]);
    if (due.length) {
      const ok = await this.wake("due");
      if (ok) for (const m of due) done[m.key] = now;
    }
    // finals, with no phone needed
    const watch = await this.finals(sched, now, done);
    // the day's close-out, once every game of the day is final
    await this.dayEnd(sched, now, done);
    await this.ctx.storage.put("done", done);
    // the next alarm: the next moment, or the next final check
    let next = now + 6 * 60 * MIN;
    for (const m of moments) if (m.at > now + 30000 && !done[m.key] && m.at < next) next = m.at;
    if (watch.checking) next = Math.min(next, now + 2 * MIN);
    if (watch.nextEnd && watch.nextEnd > now) next = Math.min(next, watch.nextEnd);
    await this.ctx.storage.setAlarm(Math.max(now + 30000, next));
  }

  moments(sched, now) {
    const out = [], today = etParts(now).date;
    for (const date of [today, dayShift(today, 1)]) {
      const [y, m, d] = date.split("-").map(Number);
      for (const h of SWEEP_ET) out.push({ key: "sweep@" + date + " " + h, at: etMs(y, m, d, h, 0) });
      for (const h of HUB_ET) out.push({ key: "hub@" + date + " " + h, at: etMs(y, m, d, h, 0) });
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
      const url = "https://site.api.espn.com/apis/site/v2/sports/football/" + lg + "/scoreboard?dates=" + ymd +
                  (lg === "college-football" ? "&groups=80&limit=400" : "");
      try {
        const j = await (await fetch(url)).json();
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
