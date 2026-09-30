"""The game page's cases (Jose, Sep 30, 2026): for every football game still
   to come this week, what will happen and why, said from the board's own
   finals, the injury wire and the weather -- never a price, never a guess.

   Both sides of the two choices get their case, since he picks the side and
   reads why that side. The ladders get a line per passer per rung, and the
   line is the opportunity in front of him, not only what he has done:

     ML    each club: its record, its wins' and loss' margins, points for and
           against, home or away, last time out, its line on the wire.
     H2H   each passer: yards a game on how many throws, his games, against
           the other man's; the pass yards the other defense allows, and its
           defenders on the wire.
     PTD   each passer, each rung 1+..6+: games he cleared it in; his club's
           red-zone trips a game and how many his passes finish; what the
           other defense gives up a game in passing scores and yards, and its
           defenders on the wire; the wind; and for the higher rungs what it
           took in his best game (how many by the half) and what to watch.
     RTD   each passer, each rung: his rushing scores, carries and yards a
           game; a lean only for a real rushing threat, never a one-off.

   Leans (the gold ring): ML by points margin, H2H by passing yards, PTD the
   highest rung the numbers carry (at least 1), RTD 1 for a rushing threat
   only. Calls (TAKE / LEAN / PASS) on every rung from the same numbers.

   Writes site/suggest.json.      python3 build/suggest.py
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "suggest.json")
NOW = dt.datetime.now(dt.timezone.utc)
DEF = {"CB", "S", "SS", "FS", "LB", "OLB", "ILB", "MLB", "DE", "DT", "NT", "DL", "EDGE", "DB"}
OFFLINE = {"C", "G", "OT", "OL", "T"}
HURT = ("Out", "Doubtful", "Questionable", "Injured Reserve")


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def short(n):
    n = str(n or "").split()
    return (n[0][0] + "." + n[-1]) if len(n) > 1 else (n[0] if n else "")


def fam(n):
    bits = [b for b in str(n or "").split() if not re.match(r"^(Jr\.?|Sr\.?|II|III|IV|V)$", b)]
    return bits[-1] if bits else str(n or "")


def final(gid):
    try:
        return json.load(open(os.path.join(D, "site", "final", "%s.json" % gid)))
    except Exception:
        return None


def played(sched, club, before_wk):
    """[(week, opp, my score, their score, final)] for the club's finished games, in order."""
    out = []
    for r in sched:
        if r[0] >= before_wk or club not in (r[3], r[4]):
            continue
        j = final(r[1])
        if not j:
            continue
        comps = ((j.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []
        sc = {(c.get("team") or {}).get("abbreviation"): c.get("score") for c in comps}
        opp = r[4] if r[3] == club else r[3]
        try:
            out.append((r[0], opp, int(sc.get(club)), int(sc.get(opp)), j))
        except (TypeError, ValueError):
            continue
    return out


def box_line(j, qid, what):
    for t in (j.get("boxscore") or {}).get("players") or []:
        for st in t.get("statistics") or []:
            if st.get("name") != what:
                continue
            keys = st.get("keys") or st.get("labels") or []
            for a in st.get("athletes") or []:
                if str((a.get("athlete") or {}).get("id")) == str(qid):
                    return dict(zip(keys, a.get("stats") or []))
    return None


def n_of(line, *keys):
    for k in keys:
        if line and line.get(k) not in (None, ""):
            try:
                return int(str(line[k]).split("/")[-1])
            except ValueError:
                pass
    return 0


def passing(j, qid):
    l = box_line(j, qid, "passing")
    if not l:
        return None
    return n_of(l, "YDS", "passingYards"), n_of(l, "C/ATT", "completions/passingAttempts"), n_of(l, "TD", "passingTouchdowns")


def rushing(j, qid):
    l = box_line(j, qid, "rushing")
    if not l:
        return (0, 0, 0)
    return n_of(l, "TD", "rushingTouchdowns"), n_of(l, "CAR", "rushingAttempts"), n_of(l, "YDS", "rushingYards")


def drives(j, club, opp, qb):
    """(drives, red-zone trips, drives his passes finished with a touchdown, his passing scores by the half)."""
    sq = short(qb)
    mine = [d for d in ((j.get("drives") or {}).get("previous") or []) if any(sq in (p.get("text") or "") for p in d.get("plays") or [])]

    def yl(p):
        m = re.search(r"at %s (\d+)" % re.escape(opp), ((p.get("start") or {}).get("downDistanceText") or ""))
        return int(m.group(1)) if m else 99
    rz = sum(1 for d in mine if any(yl(p) <= 20 for p in d.get("plays") or []))
    tdp = [p for d in mine for p in d.get("plays") or [] if sq in (p.get("text") or "") and "pass" in (p.get("text") or "") and "TOUCHDOWN" in (p.get("text") or "")]
    half = sum(1 for p in tdp if ((p.get("period") or {}).get("number") or 9) <= 2)
    return len(mine), rz, len(tdp), half


def allowed(sched, club, wk):
    """What the club's defense gives up a game: passing scores, passing yards, points."""
    gs = played(sched, club, wk)
    if not gs:
        return None
    ptd = yds = pts = 0
    for g in gs:
        pts += g[3]
        for p in g[4].get("scoringPlays") or []:
            if ((p.get("team") or {}).get("abbreviation") == g[1]) and " pass from " in (p.get("text") or ""):
                ptd += 1
        for t in (g[4].get("boxscore") or {}).get("players") or []:
            if ((t.get("team") or {}).get("abbreviation") or "") != g[1]:
                continue
            for st in t.get("statistics") or []:
                if st.get("name") == "passing":
                    keys = st.get("keys") or st.get("labels") or []
                    for a in st.get("athletes") or []:
                        yds += n_of(dict(zip(keys, a.get("stats") or [])), "YDS", "passingYards")
    n = len(gs)
    return {"ptd": ptd / n, "yds": yds / n, "pts": pts / n, "g": n}


def wire(alerts, gid, club):
    """(the club's defenders on the wire, its linemen on the wire), as words."""
    inj = ((alerts.get(gid) or {}).get("inj") or [])

    def say(pos):
        xs = [x for x in inj if x.get("t") == club and x.get("p") in pos and x.get("s") in HURT]
        return ", ".join("%s %s %s" % (x["p"], fam(x["n"]), x["s"].lower().replace("injured reserve", "on IR")) for x in xs)
    return say(DEF), say(OFFLINE)


def words(n):
    return {0: "no", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))


def ml_case(club, games, home, offw):
    if not games:
        return "No game on record yet this year."
    w = [g for g in games if g[2] > g[3]]
    l = [g for g in games if g[2] < g[3]]
    pf = sum(g[2] for g in games) / len(games)
    pa = sum(g[3] for g in games) / len(games)
    bits = ["%s is %d-%d" % (club, len(w), len(l))]
    if w:
        bits.append("its win%s by %s" % ("s" if len(w) > 1 else "", " and ".join(str(g[2] - g[3]) for g in w)))
    if l:
        bits.append("its loss%s by %s" % ("es" if len(l) > 1 else "", " and ".join(str(g[3] - g[2]) for g in l)))
    s = ", ".join(bits) + ". "
    s += "It scores %.0f a game and gives up %.0f, %s." % (pf, pa, "at home here" if home else "on the road here")
    last = games[-1]
    s += " Last out it %s %s %d-%d." % ("beat" if last[2] > last[3] else "lost to", last[1], last[2], last[3])
    if offw:
        s += " On its line: %s." % offw
    return s


def h2h_case(qb, lines, other, olines, oalw, oppw):
    if not lines:
        return "No game on record yet this year for %s." % fam(qb)
    y = sum(x[0] for x in lines) / len(lines)
    a = sum(x[1] for x in lines) / len(lines)
    s = "%s throws for %.0f a game on %.0f throws" % (fam(qb), y, a)
    if olines:
        oy = sum(x[0] for x in olines) / len(olines)
        oa = sum(x[1] for x in olines) / len(olines)
        s += ", %s %.0f on %.0f" % (fam(other), oy, oa)
    s += ". His games: %s." % ", ".join(str(x[0]) for x in lines)
    if oalw:
        s += " The defense across from him gives up %.0f passing yards a game." % oalw["yds"]
    if oppw:
        s += " On it: %s." % oppw
    return s


def expect(rows, oalw):
    """Passing scores to expect: his red-zone trips a game times the share
       his passes finish, met halfway with what the defense gives up."""
    if not rows:
        return None
    g = len(rows)
    rz = sum(r[1] for r in rows) / g
    trips = sum(r[1] for r in rows)
    fin = sum(r[2] for r in rows)
    own = rz * (fin / trips if trips else 0)
    return (own + oalw["ptd"]) / 2 if oalw else own


def call_of(exp, n):
    if exp is None:
        return "none"
    return "take" if exp >= n + 0.4 else "lean" if exp >= n - 0.4 else "pass"


def ptd_case(qb, club, opp, n, rows, oalw, oppw, wx):
    """rows: [(ptd, rz trips, pass-td drives, drives, by the half, wk, opp)] per game."""
    if not rows:
        return "none", "No game on record yet this year for %s." % fam(qb)
    g = len(rows)
    k = sum(1 for r in rows if r[0] >= n)
    rz = sum(r[1] for r in rows) / g
    trips = sum(r[1] for r in rows)
    fin = sum(r[2] for r in rows)
    call = call_of(expect(rows, oalw), n)
    # a rung he has cleared in two games of three is at least a lean, and a
    # take when the numbers do not argue against it
    exp = expect(rows, oalw)
    if k / g >= 0.67 and call == "pass":
        call = "lean"
    if k / g >= 0.67 and exp is not None and exp >= n - 0.2:
        call = "take"
    s = "%d+ in %d of %d. %s gets %.0f red-zone trips a game and his passes finish %d of %d this year" % (n, k, g, club, rz, fin, trips)
    last = rows[-1]
    s += ", %d of %d last week." % (last[2], last[1])
    if oalw:
        s += " %s gives up %.1f passing scores and %.0f passing yards a game." % (opp, oalw["ptd"], oalw["yds"])
    if oppw:
        s += " On its defense: %s." % oppw
    try:
        if wx and int(wx.get("g") or 0) >= 15:
            s += " Wind %s mph." % wx["g"]
    except ValueError:
        pass
    if n >= 2:
        best = max(rows, key=lambda r: r[0])
        if best[0] >= n:
            s += " His %d-score game, week %s at %s: %d by the half." % (best[0], best[5], best[6], best[4])
        s += " To get there he needs %d red-zone trips or more; watch for %d by the half and the trips piling up." % (n + 2, max(1, n - 1))
    return call, s


def rtd_case(qb, n, runs):
    """runs: [(rush TDs, carries, yards)] per game."""
    if not runs:
        return "none", "No game on record yet this year for %s." % fam(qb)
    g = len(runs)
    k = sum(1 for r in runs if r[0] >= n)
    tot = sum(r[0] for r in runs)
    car = sum(r[1] for r in runs) / g
    yds = sum(r[2] for r in runs) / g
    s = "%d+ in %d of %d. %s rushing score%s in %d games, on %.0f carries and %.0f yards a game." % (
        n, k, g, words(tot).capitalize(), "" if tot == 1 else "s", g, car, yds)
    # a man who runs them in: scores in a third of his games on real carries, or two already
    threat = tot >= 2 or (tot >= 1 and car >= 5 and (k / g >= 0.3 or yds >= 30))
    if not threat:
        s += " Not a man who runs them in: no lean here."
        return "pass", s
    call = "take" if k / g >= 0.67 else "lean"
    return call, s


def main():
    s = pagefile.read()
    sched = json.loads(re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    try:
        alerts = json.load(open(os.path.join(D, "site", "alerts.json")))
    except Exception:
        alerts = {}
    out = {}
    for r in sched:
        start = T(r[2])
        if start < NOW - dt.timedelta(hours=4) or start > NOW + dt.timedelta(days=8):
            continue
        wk, gid, away, home = r[0], str(r[1]), r[3], r[4]
        wx = (alerts.get(gid) or {}).get("wx") or {}
        men = {"away": (r[5], str(r[6] or ""), away, home), "home": (r[7], str(r[8] or ""), home, away)}
        game = {"away": away, "home": home, "qb": {k: {"name": v[0], "id": v[1]} for k, v in men.items()}, "ml": {}, "h2h": {}, "ptd": {}, "atd": {}}
        gs, lines, rows, runs, alw, wr = {}, {}, {}, {}, {}, {}
        for side, (qb, qid, club, opp) in men.items():
            gs[side] = played(sched, club, wk)
            alw[side] = allowed(sched, club, wk)      # what this club's defense gives up
            wr[side] = wire(alerts, gid, club)        # (defenders, linemen) on the wire
            lines[side] = [x for x in (passing(g[4], qid) for g in gs[side]) if x]
            rows[side], runs[side] = [], []
            for g in gs[side]:
                p = passing(g[4], qid)
                if not p:
                    continue
                d, rz, fin, half = drives(g[4], club, g[1], qb)
                rows[side].append((p[2], rz, fin, d, half, g[0], g[1]))
                runs[side].append(rushing(g[4], qid))
        for side, (qb, qid, club, opp) in men.items():
            other = "home" if side == "away" else "away"
            game["ml"][side] = ml_case(club, gs[side], side == "home", wr[side][1])
            game["h2h"][side] = h2h_case(qb, lines[side], men[other][0], lines[other], alw[other], wr[other][0])
            game["ptd"][side], game["atd"][side] = {}, {}
            for n in range(1, 7):
                c, t = ptd_case(qb, club, opp, n, rows[side], alw[other], wr[other][0], wx)
                game["ptd"][side][str(n)] = {"call": c, "text": t}
                c, t = rtd_case(qb, n, runs[side])
                game["atd"][side][str(n)] = {"call": c, "text": t}
        # the leans: one a market for the two choices, each man on his own for the ladders
        lean = {"ml": None, "h2h": None, "ptd": {}, "atd": {}}
        gap = {}
        net = {w: (sum(g[2] - g[3] for g in gs[w]) / len(gs[w])) if gs[w] else None for w in men}
        if net["away"] is not None and net["home"] is not None and abs(net["away"] - net["home"]) >= 3:
            lean["ml"] = "away" if net["away"] > net["home"] else "home"
            gap["ml"] = abs(net["away"] - net["home"])
        ypg = {w: (sum(x[0] for x in lines[w]) / len(lines[w])) if lines[w] else None for w in men}
        if ypg["away"] is not None and ypg["home"] is not None and abs(ypg["away"] - ypg["home"]) >= 20:
            lean["h2h"] = "away" if ypg["away"] > ypg["home"] else "home"
            gap["h2h"] = abs(ypg["away"] - ypg["home"])
        for w in men:
            other = "home" if w == "away" else "away"
            exp = expect(rows[w], alw[other])
            best = 0
            for n in range(1, 7):
                if call_of(exp, n) == "take":
                    best = n
            lean["ptd"][w] = (best or 1) if rows[w] else None
            lean["atd"][w] = 1 if runs[w] and game["atd"][w]["1"]["call"] in ("take", "lean") else None
        game["lean"] = lean
        game["call"] = {}
        for m in ("ml", "h2h"):
            l = lean[m]
            game["call"][m] = {w: (None if not l else ("pass" if w != l else ("take" if gap.get(m, 0) >= (7 if m == "ml" else 40) else "lean"))) for w in men}
        out[gid] = game
    json.dump(out, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    print("suggest: %d games" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
