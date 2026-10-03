/* What his open slips are riding on, read while their games are on, and what
   is worth telling him (Jose, Sep 29, 2026: push alerts, the badge, "2 PTD
   happened, the next is...", red zone, win probability, you won).

   Every leg is tied to its game by DraftKings' own selection id against the
   board's prices (site/prices.json), never by a written name -- the same rule
   the wallet's tracker keeps. */
/* ESPN's edge is Akamai and turns away a bare machine call, so every read
   here is made the way a browser makes it -- the site's /espn relay does the
   same (Jose, Sep 17, 2026). Without this the clock's reads failed quietly. */
export function espnGet(u) {
  /* through the site's own relay (/espn), the path the phone uses: ESPN's
     edge turned the Worker's own calls away even dressed as a browser */
  return fetch("https://the-arenasports.pages.dev/espn?u=" + encodeURIComponent(u), { headers: {
    accept: "application/json, text/plain, */*", "accept-language": "en-US,en;q=0.9",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    referer: "https://www.espn.com/", origin: "https://www.espn.com" } });
}
const SITE = "https://the-arenasports.pages.dev";
const MIN = 60000;

/* sel -> {gid, kind, side, n, team, qb, qbName, lg} for every leg the board prices */
export function legIndex(prices, sched) {
  const rows = {};
  for (const r of sched) if (r[0] === "game" || r[0] === "bout") rows[r[1]] = r;
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
  // fights: the moneyline and every prop the board prices, by DraftKings id
  for (const [bid, f] of Object.entries(prices.FIGHTS || {})) {
    const r = rows[bid] || null;
    put(f[1], { gid: bid, kind: "fml", side: 0, fight: 1, who: r ? r[4] : "" });
    put(f[3], { gid: bid, kind: "fml", side: 1, fight: 1, who: r ? r[5] : "" });
  }
  for (const [bid, fp] of Object.entries(prices.FPROPS || {})) {
    for (const [key, v] of Object.entries(fp || {})) {
      if (!Array.isArray(v)) continue;
      const one = v.length === 1;
      v.forEach((c, s0) => { if (c && c[1]) put(c[1], { gid: bid, kind: "fm", key, side: one ? -1 : s0, fight: 1 }); });
    }
  }
  return out;
}

/* a bout as ESPN's fight scoreboard has it: on or over, the round, the
   winner's side and how */
export function readBout(bid, board) {
  const b = { state: "pre", period: 0, clock: "", winner: null, how: "", ids: [] };
  for (const e of board.events || []) for (const c of e.competitions || []) {
    if (String(c.id) !== String(bid)) continue;
    const st = c.status || {};
    b.state = (st.type || {}).state || "pre";
    b.period = st.period || 0; b.clock = st.displayClock || "";
    (c.competitors || []).forEach((m, i) => { b.ids.push(String(m.id)); if (m.winner) b.winner = String(m.id); });
    for (const d of c.details || []) { const t = (d.type || {}).text || ""; if (t.indexOf("Unofficial Winner") === 0) b.how = t.slice(17).trim(); }
    // ESPN's own words for how, said the way a card says them
    b.how = ({ Kotko: "KO/TKO", Decision: "decision", Submission: "submission" })[b.how] || b.how;
  }
  return b;
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
      const d = await (await espnGet("https://site.web.api.espn.com/apis/site/v2/sports/football/" + lg + "/summary?event=" + gid)).json();
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
export function legState(v, g, other, row) {
  if (!v || !g) return "open";
  if (v.fight) {
    if (g.state !== "post") return "open";
    const sideId = row ? String(v.side === 0 ? row[6] : row[7]) : null;
    const mine = v.side === -1 ? !!g.winner : g.winner === sideId;
    const how = /sub/i.test(g.how) ? "sub" : /dec/i.test(g.how) ? "dec" : /ko|knock/i.test(g.how) ? "ko" : "";
    if (v.kind === "fml") return mine ? "won" : "lost";
    const k = v.key || "";
    if (k === "ko" || k === "koonly") return mine && how === "ko" ? "won" : "lost";
    if (k === "sub" || k === "subonly") return mine && how === "sub" ? "won" : "lost";
    if (k === "dec" || k === "deconly" || k === "cards") return mine && how === "dec" ? "won" : "lost";
    if (k === "anyko") return how === "ko" ? "won" : "lost";
    if (k === "anysub") return how === "sub" ? "won" : "lost";
    if (k === "dist" || k === "anydec") return how === "dec" ? "won" : "lost";
    if (k === "nodist") return how && how !== "dec" ? "won" : "lost";
    /* the round markets, off the round it ended in (Oct 3, 2026: Smith and
       Wint won in round 1 and the alert counted them as open) */
    const rd = +g.period || 0, fin = how === "ko" || how === "sub";
    let m;
    if (k === "kosub" || k === "finish") return mine && fin ? "won" : "lost";
    if (k === "kodec") return mine && (how === "ko" || how === "dec") ? "won" : "lost";
    if (k === "subdec") return mine && (how === "sub" || how === "dec") ? "won" : "lost";
    if ((m = /^rd(\d+)$/.exec(k))) return mine && fin && rd === +m[1] ? "won" : "lost";
    if ((m = /^kord(\d+)$/.exec(k))) return mine && how === "ko" && rd === +m[1] ? "won" : "lost";
    if ((m = /^subrd(\d+)$/.exec(k))) return mine && how === "sub" && rd === +m[1] ? "won" : "lost";
    if ((m = /^anykord(\d+)$/.exec(k))) return how === "ko" && rd === +m[1] ? "won" : "lost";
    if ((m = /^anysubrd(\d+)$/.exec(k))) return how === "sub" && rd === +m[1] ? "won" : "lost";
    if ((m = /^rg?(\d+)-?(\d+)$/.exec(k.replace("rd12", "r1-2").replace("rd34", "r3-4")))) return mine && fin && rd >= +m[1] && rd <= +m[2] ? "won" : "lost";
    if (k === "rd1only") return fin && rd === 1 ? "won" : "lost";
    if (k === "first60") { const t = String(g.clock || "").split(":"); return fin && rd === 1 && t.length === 2 && (+t[0] * 60 + +t[1]) <= 60 ? "won" : "lost"; }
    return "open";      // the rest wait on DraftKings' own word
  }
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
  const lab = (lg, v) => ((lg.label || lg.pick || "").split(" · ")[0] || (v && v.qbName ? last(v.qbName) : "")).replace(/\s*\u2016\s*/g, " \u00b7 ");
  for (const bet of slips) {
    const legs = (bet.legs || []).map(lg => {
      const v = idx[lg.sel], g = v && games[v.gid], r = v && rows[v.gid];
      const other = v && r && !v.fight ? (v.side ? r[7] : r[9]) : null;
      const dk = String(lg.status || "").toLowerCase();
      const st = dk === "won" || dk === "lost" ? dk : legState(v, g, other, r);
      return { lg, v, g, st };
    });
    if (legs.some(x => x.st === "lost")) continue;
    const open = legs.filter(x => x.st === "open");
    const odds = String(bet.odds || "");
    if (!open.length && legs.length) {
      out.push({ tag: "slip:" + bet.id, key: "won@" + bet.id, type: "slip", title: "You won", body: "Your " + odds + " slip hit: $" + (+bet.topay || 0).toFixed(2) + ".", url: "/#slip=" + bet.id });
      continue;
    }
    /* a leg that lands, with the count: "Carr 2+ PTD ✓ · 1 of 6 hit, 5 left"
       (Jose, Oct 3, 2026). The last two are said by "One leg left" and "You won". */
    if (open.length > 1) {
      const hit = legs.filter(x => x.st === "won");
      for (const x of hit) {
        out.push({ tag: "slip:" + bet.id, key: "hit@" + bet.id + "@" + x.lg.sel, type: "leghit",
                   title: lab(x.lg, x.v) + " \u2713",
                   body: hit.length + " of " + legs.length + " hit, " + open.length + " left on your " + odds + " slip.", url: "/#slip=" + bet.id });
      }
    }
    if (open.length === 1 && legs.length > 1) {
      const x = open[0], g = x.g;
      out.push({ tag: "slip:" + bet.id, key: "one@" + bet.id + "@" + x.lg.sel, type: "slip", title: "One leg left",
                 body: "On your " + odds + " slip: " + lab(x.lg, x.v) + (g && g.clock ? " · " + g.clock : "") + ".", url: "/#slip=" + bet.id });
    }
  }
  // per game, per passer and per club on his legs
  const seen = {};
  /* a leg that has already hit or missed says nothing more, and a slip with a
     leg lost says nothing at all (Jose, Oct 3, 2026: "these shouldn't be
     notifying after my legs go thru") */
  const stOf = (l) => {
    const w = idx[l.sel], gg = w && games[w.gid], rr = w && rows[w.gid];
    const d = String(l.status || "").toLowerCase();
    if (d === "won" || d === "lost") return d;
    return w && gg && rr ? legState(w, gg, w.fight ? null : (w.side ? rr[7] : rr[9]), rr) : "open";
  };
  for (const bet of slips) for (const lg of bet.legs || []) {
    const v = idx[lg.sel]; if (!v) continue;
    const g = games[v.gid], p = prev[v.gid] || {}, r = rows[v.gid];
    if (!g || !r) continue;
    if ((bet.legs || []).some(l => stOf(l) === "lost")) continue;
    const done = stOf(lg) !== "open";
    if (v.fight) {
      if (g.state === "in" && !seen["fon@" + v.gid]) {
        seen["fon@" + v.gid] = 1;
        out.push({ tag: "slip:" + bet.id, key: "fon@" + v.gid, type: "fight", title: r[4] + " vs " + r[5], body: "Your fight is on" + (g.period ? " · R" + g.period : "") + ".", url: "/#bout=" + v.gid });
      }
      if (g.state === "post" && !seen["ffin@" + v.gid]) {
        seen["ffin@" + v.gid] = 1;
        const won = g.winner === String(r[6]) ? r[4] : g.winner === String(r[7]) ? r[5] : "";
        const said = (bet.legs || []).map(l => ({ l, w: idx[l.sel] })).filter(x => x.w && x.w.gid === v.gid)
          .map(x => lab(x.l, x.w) + " " + (legState(x.w, g, null, r) === "won" ? "hit" : legState(x.w, g, null, r) === "lost" ? "missed" : "")).join(" · ");
        out.push({ tag: "slip:" + bet.id, key: "ffin@" + v.gid, type: "fight", title: "Final: " + (won ? won + " wins" : r[4] + " vs " + r[5]) + (g.how ? " by " + g.how : ""),
                   body: (g.period ? "R" + g.period + " " + g.clock + ". " : "") + said + ".", url: "/#bout=" + v.gid });
      }
      continue;
    }
    const away = r[4], home = r[5];
    if (v.kind === "ptd" || v.kind === "atd") {
      const q = g.qb[String(v.qb)] || { ptd: 0, rtd: 0 }, q0 = (p.qb || {})[String(v.qb)] || { ptd: 0, rtd: 0 };
      /* the touchdown that lands the rung is still told; any after it is not */
      if (v.kind === "ptd" && q.ptd > (q0.ptd || 0) && (!done || (q0.ptd || 0) < (v.n || 1))) {
        const k = "td@" + v.gid + "@" + v.qb + "@" + q.ptd;
        if (!seen[k]) {
          seen[k] = 1;
          const mine = (bet.legs || []).map(l => idx[l.sel]).filter(w => w && w.kind === "ptd" && w.qb === v.qb).map(w => w.n);
          const hit = mine.filter(n => n <= q.ptd), next = mine.filter(n => n > q.ptd).sort((a, b) => a - b)[0];
          out.push({ tag: "slip:" + bet.id, key: k, type: "td", title: last(v.qbName) + " TD pass (" + q.ptd + ")",
                     body: [hit.length ? hit.sort().pop() + "+ PTD hit." : "", next ? "Next: " + next + "+ needs " + (next - q.ptd) + " more." : "",
                            away + " " + g.sc[0] + "–" + g.sc[1] + " " + home + "."].filter(Boolean).join(" "),
                     url: "/#game=" + v.gid });
        }
      }
      if (v.kind === "atd" && q.rtd > (q0.rtd || 0) && (!done || (q0.rtd || 0) < (v.n || 1))) {
        const k = "rtd@" + v.gid + "@" + v.qb + "@" + q.rtd;
        if (!seen[k]) { seen[k] = 1; out.push({ tag: "slip:" + bet.id, key: k, type: "td", title: last(v.qbName) + " rushing TD", body: q.rtd + "+ rushing TD hit. " + away + " " + g.sc[0] + "–" + g.sc[1] + " " + home + ".", url: "/#game=" + v.gid }); }
      }
    }
    // red zone, for his club on the ball
    if (!done && g.state === "in" && g.rz && g.teamId && g.teamId[g.poss] === v.team && v.kind !== "h2h") {
      const k = "rz@" + v.gid + "@" + v.team + "@" + g.sc[0] + "-" + g.sc[1] + "@" + (g.clock || "").split(" ").pop().slice(0, 2);
      if (!seen["rz@" + v.gid + v.team] && !p["rz" + v.team]) {
        seen["rz@" + v.gid + v.team] = 1;
        out.push({ tag: "slip:" + bet.id, key: k, type: "redzone", title: v.team + " in the red zone", body: (g.down ? g.down + ". " : "") + (v.qbName ? last(v.qbName) + " " + (v.kind === "ptd" ? v.n + "+ PTD" : v.kind === "atd" ? "1+ rushing TD" : "") : v.team + " ML") + " · " + g.clock + ".", url: "/#game=" + v.gid });
      }
    }
    // win chance, once each way, on a moneyline
    if (!done && v.kind === "ml" && g.state === "in" && g.wpHome != null) {
      const mine = v.side ? g.wpHome : 1 - g.wpHome, pct = Math.round(mine * 100);
      for (const [edge, word, test] of [["low", "down to", mine <= 0.25], ["high", "up to", mine >= 0.8]]) {
        const k = "wp" + edge + "@" + v.gid + "@" + v.team;
        if (test && !seen[k]) { seen[k] = 1; out.push({ tag: "slip:" + bet.id, key: k, type: "wp", title: v.team + " win chance " + word + " " + pct + "%", body: away + " " + g.sc[0] + "–" + g.sc[1] + " " + home + " · " + g.clock + ".", url: "/#game=" + v.gid }); }
      }
    }
    // the final, once a game
    if (g.state === "post") {
      const k = "fin@" + v.gid;
      if (!seen[k]) {
        seen[k] = 1;
        const said = (bet.legs || []).map(l => ({ l, w: idx[l.sel] })).filter(x => x.w && x.w.gid === v.gid)
          .map(x => lab(x.l, x.w) + " " + (legState(x.w, g, x.w.side ? r[7] : r[9], r) === "won" ? "hit" : "missed")).join(" · ");
        out.push({ tag: "slip:" + bet.id, key: k, type: "final", title: "Final: " + away + " " + g.sc[0] + "–" + g.sc[1] + " " + home, body: said + ".", url: "/#game=" + v.gid });
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
      return dk === "won" || dk === "lost" ? dk : legState(v, v && games[v.gid], v && r && !v.fight ? (v.side ? r[7] : r[9]) : null, r);
    });
    if (st.includes("lost")) continue;
    n += st.filter(s => s === "open").length;
  }
  return n;
}

export { SITE, MIN };

/* a slip's end as far as can be told now: won, lost or open */
export function slipState(bet, idx, games, rows) {
  const st = (bet.legs || []).map(lg => {
    const v = idx[lg.sel], r = v && rows[v.gid];
    const dk = String(lg.status || "").toLowerCase();
    return dk === "won" || dk === "lost" ? dk : legState(v, v && games[v.gid], v && r && !v.fight ? (v.side ? r[7] : r[9]) : null, r);
  });
  if (st.includes("lost")) return "lost";
  return st.length && st.every(x => x === "won") ? "won" : "open";
}

/* what could sink a leg before its game, in words: his passer's mark, and a
   teammate out who matters to this kind of leg -- the page's own rules */
export function risks(v, a, wire) {
  const out = [];
  if (v.qb && wire[String(v.qb)] && wire[String(v.qb)].status && v.kind !== "ml")
    out.push(last(v.qbName) + " is " + String(wire[String(v.qb)].status).toLowerCase() + ".");
  const passing = v.kind === "ptd" || v.kind === "h2h";
  for (const x of a.out || []) {
    if (x.team !== v.team || x.pos === "QB" || x.sh == null) continue;
    const big = passing ? (x.tsh >= 0.15 || (x.tds >= 2 && x.rtd * 4 >= x.tds)) : v.kind === "ml" ? x.sh >= 0.15 : false;
    if (big) out.push(x.name + " (" + x.pos + ") is " + String(x.status).toLowerCase().replace("injured reserve", "on injured reserve") + ".");
  }
  return out;
}
