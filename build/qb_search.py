"""Every quarterback's season, in one file, for the board's search.

   Pull down on any page and type a name: his card comes up at once, and a
   few names make a 1+ PTD parlay (Jose, Sep 28, 2026: "I type in who I'm
   looking to parlay and we get logic back based on 1 PTD ... or if I'm
   looking for Lamar Jackson stats"). The page asks nothing of anyone while
   he types, so everything it shows is written here, a few times a day, from
   what the sweep already holds:

     the rows       SCHED and CFB in master.html -- who played whom, and when
     the results    site/final/<game>.json -- his passing and rushing TDs and
                    yards, off the box score, by his ESPN id
     the prices     site/prices.json PROPS -- his 1+ PTD price (the close for a
                    game that is over, the price now for one that is not)
     the weather    site/alerts.json, the injury wire site/wire.json
     the defence    passing TDs each club has given up a game, off the same
                    box scores

   Written to site/qbsearch.json:
     {"at": ..., "qbs": {id: {"n", "t", "lg", "g": [game, ...], "nx": next}}}
   a game is {"d", "o", "h", "r", "yd", "p", "ru", "px", "sl"}: date, the
   other club, home, W/L with the score, yards, passing TDs, rushing TDs,
   1+ PTD price, and the kickoff slot (1 for 1:00 ET, 4 for 4:05/4:25, 0 else).

       python3 build/qb_search.py
"""
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ET = dt.timezone(dt.timedelta(hours=-4))


def rows(s, var):
    m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
    return json.loads(m.group(1)) if m else []


def load(path, fallback):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return fallback


def box_of(gid):
    """{espn id: (yards, passing TDs, rushing TDs, attempts)} and the score."""
    f = load(os.path.join(D, "site", "final", "%s.json" % gid), None)
    if not f:
        return None, None
    men = {}
    for team in (f.get("boxscore") or {}).get("players") or []:
        for cat in team.get("statistics") or []:
            if cat.get("name") not in ("passing", "rushing"):
                continue
            lab = cat.get("labels") or []
            for a in cat.get("athletes") or []:
                aid = str((a.get("athlete") or {}).get("id") or "")
                st = dict(zip(lab, a.get("stats") or []))
                m = men.setdefault(aid, [0, 0, 0, 0])
                try:
                    if cat["name"] == "passing":
                        m[0] = int(st.get("YDS") or 0)
                        m[1] = int(st.get("TD") or 0)
                        m[3] = int(str(st.get("C/ATT") or "0/0").split("/")[1])
                    else:
                        m[2] = int(st.get("TD") or 0)
                except ValueError:
                    pass
    score = {}
    for c in (((f.get("header") or {}).get("competitions") or [{}])[0].get("competitors") or []):
        score[str((c.get("team") or {}).get("abbreviation") or "")] = c.get("score")
    return men, score


def slot(iso):
    t = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ET)
    if t.weekday() != 6:
        return 0
    return 1 if t.hour < 14 else 4 if t.hour < 18 else 0


def main():
    s = pagefile.read()
    props = (load(os.path.join(D, "site", "prices.json"), {}) or {}).get("PROPS") or {}
    alerts = load(os.path.join(D, "site", "alerts.json"), {})
    wire = load(os.path.join(D, "site", "wire.json"), {})
    now = dt.datetime.now(dt.timezone.utc)
    qbs, allowed = {}, {}
    nfl, nfl_allowed = qbs, allowed
    # the NFL only, for now (Jose, Sep 28, 2026: "just for NFL now"); college
    # goes to its own file below, for the hold on a college face (Oct 8, 2026)
    cfb, cfb_allowed = {}, {}
    for lg, var in (("nfl", "SCHED"), ("cfb", "CFB")):
        qbs, allowed = (cfb, cfb_allowed) if lg == "cfb" else (qbs, allowed)
        for r in rows(s, var):
            gid, iso, away, home = str(r[1]), r[2], r[3], r[4]
            try:
                kick = dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))
            except ValueError:
                continue
            men, score = box_of(gid)
            ptd = (props.get(gid) or {}).get("ptd") or [[], []]
            for side, ni, ii, me, them in ((0, 5, 6, away, home), (1, 7, 8, home, away)):
                pid = str(r[ii] or "")
                if not pid:
                    continue
                q = qbs.setdefault(pid, {"n": r[ni], "t": me, "lg": lg, "g": [], "nx": None})
                q["n"], q["t"] = r[ni], me
                lad = ptd[side] if side < len(ptd) else []
                px = lad[0][0] if lad and lad[0] and lad[0][0] else ""
                if men is not None:
                    line = men.get(pid)
                    # his team's passing TDs against this defence, for "allows"
                    if line:
                        allowed.setdefault(them, []).append(line[1])
                    if not line or (not line[3] and not line[2]):
                        continue          # on the row but never played
                    mine, theirs = score.get(me), score.get(them)
                    res = ""
                    if mine not in (None, "") and theirs not in (None, ""):
                        a_, b_ = int(mine), int(theirs)
                        res = ("W " if a_ > b_ else "L " if a_ < b_ else "T ") + "%d-%d" % (a_, b_)
                    q["g"].append({"d": iso, "o": them, "h": side == 1, "r": res, "yd": line[0],
                                   "p": line[1], "ru": line[2], "px": px, "sl": slot(iso), "att": line[3]})
                elif kick > now - dt.timedelta(hours=4):
                    if q["nx"] and q["nx"]["d"] <= iso:
                        continue
                    wx = (alerts.get(gid) or {}).get("wx") or {}
                    w = wire.get(pid) or {}
                    q["nx"] = {"d": iso, "gid": gid, "o": them, "h": side == 1, "px": px, "sl": slot(iso),
                               "wx": wx, "inj": (w.get("status") or "") if w else ""}
    qbs, allowed = nfl, nfl_allowed
    for q in cfb.values():
        q["g"].sort(key=lambda g: g["d"], reverse=True)
        for g in q["g"]:
            g.pop("att", None)
    json.dump({"at": now.strftime("%Y-%m-%dT%H:%MZ"), "qbs": {k: v for k, v in cfb.items() if v["g"] or v["nx"]}},
              open(os.path.join(D, "site", "qbsearch_cfb.json"), "w"), separators=(",", ":"))
    for q in qbs.values():
        q["g"].sort(key=lambda g: g["d"], reverse=True)
        if q["nx"]:
            a = allowed.get(q["nx"]["o"]) or []
            q["nx"]["al"] = round(sum(a) / len(a), 1) if a else None
    # a name with no game and no next game is nothing to show
    qbs = {k: v for k, v in qbs.items() if v["g"] or v["nx"]}
    # cold (Jose, Sep 28, 2026, "let's do the 6"): one TD or fewer, passing
    # and rushing, per full start, with at least two full starts. A full start
    # is ten or more throws -- a game he came into late or left hurt does not
    # count against him
    cold = {}
    for pid, q in qbs.items():
        full = [g for g in q["g"] if g.get("att", 0) >= 10]
        tds = sum(g["p"] + g["ru"] for g in full)
        if len(full) >= 2 and tds <= len(full):
            cold[pid] = [len(full), tds]
    for q in qbs.values():
        for g in q["g"]:
            g.pop("att", None)
    json.dump({"at": now.strftime("%Y-%m-%dT%H:%MZ"), "cold": cold},
              open(os.path.join(D, "site", "cold.json"), "w"), separators=(",", ":"))
    out = {"at": now.strftime("%Y-%m-%dT%H:%MZ"), "qbs": qbs}
    json.dump(out, open(os.path.join(D, "site", "qbsearch.json"), "w"), separators=(",", ":"))
    print("cold: " + ", ".join(sorted(qbs[k]["n"] for k in cold)))
    print("qbsearch: %d QBs (%d NFL), %d games"
          % (len(qbs), sum(1 for v in qbs.values() if v["lg"] == "nfl"), sum(len(v["g"]) for v in qbs.values())))


if __name__ == "__main__":
    main()
