"""The game page's cases (Jose, Sep 30, 2026): for every football game still
   to come this week, what will happen and why, said from the board's own
   finals -- never a price, never a guess.

   Both sides of the two choices get their case, since he picks the side and
   reads why that side ("if I click on Cleveland it gives me why Cleveland
   wins, how the Steelers win; on the head-to-head, Watson out-throws Rodgers
   and vice versa"). The ladders get a line per passer per rung.

     ML    each club: its record, its wins' and its loss' margins, its side of
           the ball this year (points a game, points allowed), home or away.
     H2H   each passer: yards a game on how many throws, his last three,
           against the other man's numbers.
     PTD   each passer, each rung 1+..6+: how many games he cleared it in, his
           club's red-zone trips a game and how many his passes finished.
     RTD   each passer, each rung: rushing scores in his games this year.

   Writes site/suggest.json  {game id: {"away", "home", "ml": {"away", "home"},
                              "h2h": {"away", "home"}, "ptd": {"away": {"1": ...}},
                              "atd": {...}}}
       python3 build/suggest.py
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
    """[(week, opp, my score, their score, final json)] for the club's finished games."""
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


def passing(j, qid):
    """(yards, attempts, passing TDs) from the box score, or None."""
    for t in (j.get("boxscore") or {}).get("players") or []:
        for st in t.get("statistics") or []:
            if st.get("name") != "passing":
                continue
            keys = st.get("keys") or st.get("labels") or []
            for a in st.get("athletes") or []:
                if str((a.get("athlete") or {}).get("id")) == str(qid):
                    line = dict(zip(keys, a.get("stats") or []))
                    ca = str(line.get("C/ATT") or line.get("completions/passingAttempts") or "0/0")
                    att = int(ca.split("/")[-1]) if "/" in ca else 0
                    return int(line.get("YDS") or line.get("passingYards") or 0), att, int(line.get("TD") or line.get("passingTouchdowns") or 0)
    return None


def drives(j, club, opp, qb):
    """(drives, red-zone trips, drives his passes finished with a touchdown)."""
    sq = short(qb)
    mine = [d for d in ((j.get("drives") or {}).get("previous") or []) if any(sq in (p.get("text") or "") for p in d.get("plays") or [])]

    def yl(p):
        m = re.search(r"at %s (\d+)" % re.escape(opp), ((p.get("start") or {}).get("downDistanceText") or ""))
        return int(m.group(1)) if m else 99
    rz = sum(1 for d in mine if any(yl(p) <= 20 for p in d.get("plays") or []))
    ptd = sum(1 for d in mine if any(sq in (p.get("text") or "") and "pass" in (p.get("text") or "") and "TOUCHDOWN" in (p.get("text") or "") for p in d.get("plays") or []))
    return len(mine), rz, ptd


def rushed(j, qb):
    return sum(1 for p in j.get("scoringPlays") or [] if re.match(r"^%s \d+ Yd (Rush|Run)" % re.escape(qb), p.get("text") or ""))


def words(n):
    return {0: "none", 1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}.get(n, str(n))


def ml_case(club, games, home):
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
    return s


def h2h_case(qb, lines, other, olines):
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
    hi = max(lines, key=lambda x: x[0])
    s += " His most this year was %d on %d throws." % (hi[0], hi[1])
    return s


def ptd_case(qb, club, n, rows):
    """rows: [(ptd, rz trips, pass-td drives, drives)] per game."""
    if not rows:
        return "none", "No game on record yet this year for %s." % fam(qb)
    g = len(rows)
    k = sum(1 for r in rows if r[0] >= n)
    rz = sum(r[1] for r in rows) / g
    fin = sum(r[2] for r in rows)
    trips = sum(r[1] for r in rows)
    s = "%d+ in %d of %d. %s gets %.0f red-zone trips a game; his passes finished %d of %d trips this year" % (n, k, g, club, rz, fin, trips)
    last = rows[-1]
    s += ", %d of %d last week." % (last[2], last[1])
    call = "take" if k / g >= 0.67 else "lean" if k / g >= 0.34 else "pass"
    return call, s


def rtd_case(qb, n, runs):
    if not runs:
        return "none", "No game on record yet this year for %s." % fam(qb)
    g = len(runs)
    k = sum(1 for r in runs if r >= n)
    tot = sum(runs)
    s = "%d+ in %d of %d. " % (n, k, g)
    s += ("No rushing score in %d games." % g) if not tot else ("%s rushing score%s in %d games: %s by game." % (words(tot).capitalize(), "" if tot == 1 else "s", g, ", ".join(str(r) for r in runs)))
    call = "take" if k / g >= 0.67 else "lean" if k / g >= 0.34 else "pass"
    return call, s


def leans(men, played, sched, wk, lines, rows, runs):
    """{"ml", "h2h", "ptd", "atd"}: "away" | "home" | None, each by a plain
       rule on the finals. ML: the better points margin a game, three clear.
       H2H: the more passing yards a game, twenty clear. 1+ PTD: the man who
       cleared it in more games, two thirds at least. 1+ RTD: the man with
       rushing scores in more games, a third at least."""
    out = {"ml": None, "h2h": None, "ptd": None, "atd": None}
    net = {}
    for w, (qb, qid, club, opp) in men.items():
        gs = played(sched, club, wk)
        net[w] = (sum(g[2] - g[3] for g in gs) / len(gs)) if gs else None
    if net["away"] is not None and net["home"] is not None and abs(net["away"] - net["home"]) >= 3:
        out["ml"] = "away" if net["away"] > net["home"] else "home"
        out["ml_gap"] = abs(net["away"] - net["home"])
    ypg = {w: (sum(x[0] for x in lines[w]) / len(lines[w])) if lines[w] else None for w in men}
    if ypg["away"] is not None and ypg["home"] is not None and abs(ypg["away"] - ypg["home"]) >= 20:
        out["h2h"] = "away" if ypg["away"] > ypg["home"] else "home"
        out["h2h_gap"] = abs(ypg["away"] - ypg["home"])
    def rate(xs, ok):
        return (sum(1 for x in xs if ok(x)) / len(xs)) if xs else 0
    # the ladders lean for each man on his own (Jose, Sep 30, 2026): the
    # passing rung is 2 when he clears 2+ in two games of three, else 1,
    # always at least 1; the rushing rung is 1 when he has run one in a
    # third of his games, else nothing
    out["ptd"] = {}
    out["atd"] = {}
    for w in men:
        out["ptd"][w] = (2 if rate(rows[w], lambda r: r[0] >= 2) >= 0.67 else 1) if rows[w] else None
        out["atd"][w] = 1 if rate(runs[w], lambda x: x >= 1) >= 0.34 else None
    return out


def main():
    s = pagefile.read()
    sched = json.loads(re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    out = {}
    for r in sched:
        start = T(r[2])
        if start < NOW - dt.timedelta(hours=4) or start > NOW + dt.timedelta(days=8):
            continue
        wk, gid, away, home = r[0], str(r[1]), r[3], r[4]
        men = {"away": (r[5], str(r[6] or ""), away, home), "home": (r[7], str(r[8] or ""), home, away)}
        game = {"away": away, "home": home, "qb": {k: {"name": v[0], "id": v[1]} for k, v in men.items()}, "ml": {}, "h2h": {}, "ptd": {}, "atd": {}}
        lines, rows, runs = {}, {}, {}
        for side, (qb, qid, club, opp) in men.items():
            gs = played(sched, club, wk)
            game["ml"][side] = ml_case(club, gs, side == "home")
            lines[side] = [x for x in (passing(g[4], qid) for g in gs) if x]
            rows[side] = []
            runs[side] = []
            for g in gs:
                p = passing(g[4], qid)
                if not p:
                    continue
                d, rz, fin = drives(g[4], club, g[1], qb)
                rows[side].append((p[2], rz, fin, d))
                runs[side].append(rushed(g[4], qb))
        for side in men:
            other = "home" if side == "away" else "away"
            game["h2h"][side] = h2h_case(men[side][0], lines[side], men[other][0], lines[other])
            game["ptd"][side] = {}
            game["atd"][side] = {}
            for n in range(1, 7):
                c, t = ptd_case(men[side][0], men[side][2], n, rows[side])
                game["ptd"][side][str(n)] = {"call": c, "text": t}
                c, t = rtd_case(men[side][0], n, runs[side])
                game["atd"][side][str(n)] = {"call": c, "text": t}
        # the board's own lean, one a market, or none: a gold ring on the page
        # (Jose, Sep 30, 2026: "which one I should take... if none then don't")
        game["lean"] = leans(men, played, sched, wk, lines, rows, runs)
        # and a word on each side of the two choices, like the ladders wear:
        # the leaned side takes TAKE when the gap is wide, LEAN when narrow,
        # the other side PASS; no lean, no word
        game["call"] = {}
        for m, gap in (("ml", game["lean"].get("ml_gap")), ("h2h", game["lean"].get("h2h_gap"))):
            l = game["lean"].get(m)
            game["call"][m] = {w: (None if not l else ("pass" if w != l else ("take" if (gap or 0) >= (7 if m == "ml" else 40) else "lean"))) for w in ("away", "home")}
        for k in ("ml_gap", "h2h_gap"):
            game["lean"].pop(k, None)
        out[gid] = game
    json.dump(out, open(OUT, "w"), separators=(",", ":"), ensure_ascii=False)
    print("suggest: %d games" % len(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
