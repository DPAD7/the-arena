/* What his open slips are riding on, read while their games are on, and what
   is worth telling him (Jose, Sep 29, 2026: push alerts, the badge, "2 PTD
   happened, the next is...", red zone, win probability, you won).

   Every leg is tied to its game by DraftKings' own selection id against the
   board's prices (site/prices.json), never by a written name -- the same rule
   the wallet's tracker keeps. */
const SITE = "https://the-arenasports.pages.dev";
const MIN = 60000;

/* sel -> {gid, kind, side, n, team, qb, qbName, lg} for every leg the board prices */
export function legIndex(prices, sched) {
  const rows = {};
  for (const r of sched) if (r[0] === "game") rows[r[1]] = r;
  const out = {};
  const put = (oid, v) => { if (oid && !out[oid]) out[oid] = v; };
  for (const lgk of ["SCHED", "CFB"]) {
    for (const [gid, ml] of Object.entries(prices[lgk] || {})) {
      const r = rows[gid]; if (!r) continue;
      put(ml[1], { gid, kind: "ml", side: 0, team: r[4], lg: r[3] });
      put(ml[3], { gid, kind: "ml", side: 1, team: r[5], lg: r[3] });
    }
  }
  for (const [gid, p] of Object.entries(prices.PROPS || {})) {
    const r = rows[gid]; if (!r) continue;
    for (const side of [0, 1]) {
      const team = side ? r[5] : r[4], qb = side ? r[9] : r[7], qbName = side ? r[8] : r[6];
      ((p.ptd || [])[side] || []).forEach((c, i) => { if (c && c[1]) put(c[1], { gid, kind: "ptd", side, n: i + 1, team, qb, qbName, lg: r[3] }); });
      ((p.atd || [])[side] || []).forEach((c, i) => { if (c && c[1]) put(c[1], { gid, kind: "atd", side, n: i + 1, team, qb, qbName, lg: r[3] }); });
      const h = (p.h2h || [])[side];
      if (h && h[1]) put(h[1], { gid, kind: "h2h", side, team, qb, qbName, lg: r[3] });
    }
  }
  return out;
}

const last = (n) => String(n || "").split(" ").filter(w => !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(w)).pop() || n;

/* one game as ESPN has it now: status, score, win chance, possession, red
   zone, and each passer's TDs and yards */
export async function readGame(gid, lg, board) {
  const g = { state: "pre", sc: [0, 0], wpHome: null, poss: null, rz: false, down: "", clock: "", qb: {} };
  const ev = (board.events || []).find(e => String(e.id) === String(gid));
  if (ev) {
    const c = (ev.competitions || [])[0] || {}, st = (c.status || {});
    g.state = (st.type || {}).state || "pre";
    g.clock = (st.type || {}).shortDetail || "";
    for (const x of c.competitors || []) g.sc[x.homeAway === "home" ? 1 : 0] = +x.score || 0;
    const s = c.situation || {};
    g.poss = s.possession ? String(s.possession) : null;
    g.rz = !!s.isRedZone;
    g.down = s.downDistanceText || "";
    const pr = (s.lastPlay || {}).probability;
    if (pr && pr.homeWinPercentage != null) g.wpHome = pr.homeWinPercentage;
    g.teamId = {};
    for (const x of c.competitors || []) g.teamId[String((x.team || {}).id)] = (x.team || {}).abbreviation;
  }
  if (g.state !== "pre") {
    try {
      const d = await (await fetch("https://site.api.espn.com/apis/site/v2/sports/football/" + lg + "/summary?event=" + gid)).json();
      for (const t of ((d.boxscore || {}).players) || []) {
        for (const st of t.statistics || []) {
          if (st.name !== "passing" && st.name !== "rushing") continue;
          const lb = st.labels || [], iTD = lb.indexOf("TD"), iY = lb.indexOf("YDS");
          for (const a of st.athletes || []) {
            const id = String((a.athlete || {}).id), q = g.qb[id] = g.qb[id] || { ptd: 0, rtd: 0, pyd: 0 };
            const v = a.stats || [];
            if (st.name === "passing") { q.ptd = +v[iTD] || 0; q.pyd = +v[iY] || 0; }
            else q.rtd = +v[iTD] || 0;
          }
        }
      }
      const wp = d.winprobability || [];
      if (wp.length && g.wpHome == null) g.wpHome = wp[wp.length - 1].homeWinPercentage;
    } catch (e) {}
  }
  return g;
}

/* a leg's standing: won, lost or open */
export function legState(v, g, other) {
  if (!v || !g) return "open";
  const over = g.state === "post";
  const q = g.qb[String(v.qb)] || { ptd: 0, rtd: 0, pyd: 0 };
  if (v.kind === "ml") return over ? (g.sc[v.side] > g.sc[1 - v.side] ? "won" : "lost") : "open";
  if (v.kind === "ptd") return q.ptd >= v.n ? "won" : over ? "lost" : "open";
  if (v.kind === "atd") return q.rtd >= v.n ? "won" : over ? "lost" : "open";
  if (v.kind === "h2h") {
    const o = g.qb[String(other)] || { pyd: 0 };
    return over ? (q.pyd > o.pyd ? "won" : "lost") : "open";
  }
  return "open";
}

/* what changed since the last look, as messages, each with the key that
   keeps it from being said twice */
export function news(slips, idx, games, prev, rows) {
  const out = [];
  const lab = (lg, v) => (lg.label || lg.pick || "").split(" · ")[0] || (v && v.qbName ? last(v.qbName) : "");
  for (const bet of slips) {
    const legs = (bet.legs || []).map(lg => {
      const v = idx[lg.sel], g = v && games[v.gid], r = v && rows[v.gid];
      const other = v && r ? (v.side ? r[7] : r[9]) : null;
      const dk = String(lg.status || "").toLowerCase();
      const st = dk === "won" || dk === "lost" ? dk : legState(v, g, other);
      return { lg, v, g, st };
    });
    if (legs.some(x => x.st === "lost")) continue;
    const open = legs.filter(x => x.st === "open");
    const odds = String(bet.odds || "");
    if (!open.length && legs.length) {
      out.push({ key: "won@" + bet.id, type: "slip", title: "You won", body: "Your " + odds + " slip hit: $" + (+bet.topay || 0).toFixed(2) + ".", url: "/#slip=" + bet.id });
      continue;
    }
    if (open.length === 1 && legs.length > 1) {
      const x = open[0], g = x.g;
      out.push({ key: "one@" + bet.id + "@" + x.lg.sel, type: "slip", title: "One leg left",
                 body: "On your " + odds + " slip: " + lab(x.lg, x.v) + (g && g.clock ? " · " + g.clock : "") + ".", url: "/#slip=" + bet.id });
    }
  }
  // per game, per passer and per club on his legs
  const seen = {};
  for (const bet of slips) for (const lg of bet.legs || []) {
    const v = idx[lg.sel]; if (!v) continue;
    const g = games[v.gid], p = prev[v.gid] || {}, r = rows[v.gid];
    if (!g || !r) continue;
    const away = r[4], home = r[5];
    if (v.kind === "ptd" || v.kind === "atd") {
      const q = g.qb[String(v.qb)] || { ptd: 0, rtd: 0 }, q0 = (p.qb || {})[String(v.qb)] || { ptd: 0, rtd: 0 };
      if (v.kind === "ptd" && q.ptd > (q0.ptd || 0)) {
        const k = "td@" + v.gid + "@" + v.qb + "@" + q.ptd;
        if (!seen[k]) {
          seen[k] = 1;
          const mine = (bet.legs || []).map(l => idx[l.sel]).filter(w => w && w.kind === "ptd" && w.qb === v.qb).map(w => w.n);
          const hit = mine.filter(n => n <= q.ptd), next = mine.filter(n => n > q.ptd).sort((a, b) => a - b)[0];
          out.push({ key: k, type: "td", title: last(v.qbName) + " TD pass (" + q.ptd + ")",
                     body: (hit.length ? hit.sort().pop() + "+ PTD hit. " : "") + (next ? "Next: " + next + "+ needs " + (next - q.ptd) + " more." : "") + " " + away + " " + g.sc[0] + "–" + g.sc[1] + " " + home + ".",
                     url: "/#game=" + v.gid });
        }
      }
      if (v.kind === "atd" && q.rtd > (q0.rtd || 0)) {
        const k = "rtd@" + v.gid + "@" + v.qb + "@" + q.rtd;
        if (!seen[k]) { seen[k] = 1; out.push({ key: k, type: "td", title: last(v.qbName) + " rushing TD", body: q.rtd + "+ rushing TD hit. " + away + " " + g.sc[0] + "–" + g.sc[1] + " " + home + ".", url: "/#game=" + v.gid }); }
      }
    }
    // red zone, for his club on the ball
    if (g.state === "in" && g.rz && g.teamId && g.teamId[g.poss] === v.team && v.kind !== "h2h") {
      const k = "rz@" + v.gid + "@" + v.team + "@" + g.sc[0] + "-" + g.sc[1] + "@" + (g.clock || "").split(" ").pop().slice(0, 2);
      if (!seen["rz@" + v.gid + v.team] && !p["rz" + v.team]) {
        seen["rz@" + v.gid + v.team] = 1;
        out.push({ key: k, type: "redzone", title: v.team + " in the red zone", body: (g.down ? g.down + ". " : "") + (v.qbName ? last(v.qbName) + " " + (v.kind === "ptd" ? v.n + "+ PTD" : v.kind === "atd" ? "1+ rushing TD" : "") : v.team + " ML") + " · " + g.clock + ".", url: "/#game=" + v.gid });
      }
    }
    // win chance, once each way, on a moneyline
    if (v.kind === "ml" && g.state === "in" && g.wpHome != null) {
      const mine = v.side ? g.wpHome : 1 - g.wpHome, pct = Math.round(mine * 100);
      for (const [edge, word, test] of [["low", "down to", mine <= 0.25], ["high", "up to", mine >= 0.8]]) {
        const k = "wp" + edge + "@" + v.gid + "@" + v.team;
        if (test && !seen[k]) { seen[k] = 1; out.push({ key: k, type: "wp", title: v.team + " win chance " + word + " " + pct + "%", body: away + " " + g.sc[0] + "–" + g.sc[1] + " " + home + " · " + g.clock + ".", url: "/#game=" + v.gid }); }
      }
    }
    // the final, once a game
    if (g.state === "post") {
      const k = "fin@" + v.gid;
      if (!seen[k]) {
        seen[k] = 1;
        const said = (bet.legs || []).map(l => ({ l, w: idx[l.sel] })).filter(x => x.w && x.w.gid === v.gid)
          .map(x => lab(x.l, x.w) + " " + (legState(x.w, g, x.w.side ? r[7] : r[9]) === "won" ? "hit" : "missed")).join(" · ");
        out.push({ key: k, type: "final", title: "Final: " + away + " " + g.sc[0] + "–" + g.sc[1] + " " + home, body: said + ".", url: "/#game=" + v.gid });
      }
    }
  }
  return out;
}

/* legs still being played, for the icon's badge */
export function liveLegs(slips, idx, games, rows) {
  let n = 0;
  for (const bet of slips) {
    const st = (bet.legs || []).map(lg => {
      const v = idx[lg.sel], r = v && rows[v.gid];
      const dk = String(lg.status || "").toLowerCase();
      return dk === "won" || dk === "lost" ? dk : legState(v, v && games[v.gid], v && r ? (v.side ? r[7] : r[9]) : null);
    });
    if (st.includes("lost")) continue;
    n += st.filter(s => s === "open").length;
  }
  return n;
}

export { SITE, MIN };
