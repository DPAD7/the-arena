"""Every read the board calls a TAKE, written down and graded, both leagues.

   One row per read in data/reads_log.csv: the moneyline, the passing-yards head
   to head, 1+ and 2+ passing TDs, college and NFL. A read is written in the last
   two hours before its kickoff, rewritten while it can still change, frozen at
   kickoff, and graded from ESPN's box score once the game is final. Nothing a
   person has to remember to run (Jose, Oct 12, 2026: "all need to be wired so
   it automatically runs").

   Usage:  python3 log_reads.py [--dry]
"""
import csv
import datetime as dt
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile

LOG = os.path.join(D, "data", "reads_log.csv")
FIELDS = ["date", "kick", "sport", "market", "game", "pick", "model", "book", "result", "gid", "kick_utc", "qid"]
NOW = dt.datetime.now(dt.timezone.utc)
DRY = "--dry" in sys.argv
ET = dt.timezone(dt.timedelta(hours=-4))


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def load(name):
    try:
        return json.load(open(os.path.join(D, "data", name)))
    except Exception:
        return {}


def implied(o):
    try:
        n = int(str(o).replace("−", "-").replace("+", ""))
    except (TypeError, ValueError):
        return None
    return -n / (-n + 100.0) if n < 0 else 100.0 / (n + 100)


def fam(n):
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", (n or "").lower())
    return re.sub(r"[^a-z ]", "", n).split()[-1] if n.split() else ""


def reads(page):
    """(sport, market, gid, kick, game, pick, model, book, qid) for every TAKE on the board now."""
    P = json.load(open(os.path.join(D, "site", "prices.json"))).get("PROPS", {})
    sched = json.loads(re.search(r"  var SCHED = (\[\[.*?\]\]);", page, re.S).group(1))
    cfb = json.loads(re.search(r"\bCFB\s*=\s*(\[.*?\]);\n", page, re.S).group(1))
    out = []
    ml = {(r["away"], r["home"]): r for r in load("ml_reads.json").get("reads", [])}
    h2h = load("h2h_reads.json").get("reads", [])
    td = load("td_reads.json").get("reads", {})
    for r in sched:
        gid, kick, away, home = str(r[1]), r[2], r[3], r[4]
        game = "%s at %s" % (away, home)
        m = ml.get((away, home))
        if m and m.get("call") == "take":
            out.append(("NFL", "ML 75%+", gid, kick, game, m["pick"], m.get("model"), m.get("book"), ""))
        for h in h2h:
            if {fam(q) for q in h.get("qbs", [])} == {fam(r[5]), fam(r[7])} and h.get("complete") and h.get("pick") and h.get("lead", 0) >= 4:
                qid = r[6] if fam(h["pick"]) == fam(r[5]) else r[8]
                out.append(("NFL", "H2H lead 4+", gid, kick, game, h["pick"], h["lead"], "", qid))
        for i, (nm, qid) in enumerate(((r[5], r[6]), (r[7], r[8]))):
            q = td.get(str(qid)) or {}
            lad = ((P.get(gid) or {}).get("ptd") or [[], []])[i] or []
            b1 = implied(lad[0][0]) if len(lad) > 0 and lad[0] else None
            if q.get("p1") is not None and b1 is not None and q["p1"] >= 0.80 and b1 >= 0.85:
                out.append(("NFL", "1+ PTD 80/85", gid, kick, game, nm, round(100 * q["p1"], 1), round(100 * b1, 1), qid))
            b2 = implied(lad[1][0]) if len(lad) > 1 and lad[1] else None
            if (q.get("two") or {}).get("take") and b2 is not None:
                out.append(("NFL", "2+ PTD rule", gid, kick, game, nm, "", round(100 * b2, 1), qid))
    C = load("cfb_reads.json").get("reads", {})
    for r in cfb:
        gid, kick, away, home = str(r[1]), r[2], r[3], r[4]
        c = C.get(gid)
        if not c:
            continue
        game = "%s at %s" % (away, home)
        m = c.get("ml") or {}
        if m.get("call") == "take":
            out.append(("CFB", "ML 75%+", gid, kick, game, m["pick"], round(100 * m["p"], 1), "", ""))
        h = c.get("h2h") or {}
        if h.get("call") == "take":
            out.append(("CFB", "H2H 83%+", gid, kick, game, h["pick"], round(100 * h["p"], 1), "", str(h.get("pick_id") or "")))
        for qid, q in (c.get("ptd") or {}).items():
            if q.get("take1"):
                out.append(("CFB", "1+ PTD 90%+", gid, kick, game, q["name"], round(100 * q["p1"], 1), "", qid))
            if q.get("take2"):
                out.append(("CFB", "2+ PTD 70%+", gid, kick, game, q["name"], round(100 * q["p2"], 1), "", qid))
    return out


def box(sport, gid):
    lg = "nfl" if sport == "NFL" else "college-football"
    try:
        j = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/%s/summary?event=%s" % (lg, gid), impersonate="chrome", timeout=20).json()
    except Exception:
        return None
    comp = (j.get("header") or {}).get("competitions", [{}])[0]
    if not ((comp.get("status") or {}).get("type") or {}).get("completed"):
        return None
    win = next((c["team"]["abbreviation"] for c in comp.get("competitors", []) if c.get("winner")), None)
    qb = {}
    for t in (j.get("boxscore") or {}).get("players", []):
        for st in t.get("statistics", []):
            if st.get("name") != "passing":
                continue
            lab = st.get("labels") or []
            for a in st.get("athletes", []):
                v = dict(zip(lab, a.get("stats") or []))
                aid, nm = str(a["athlete"]["id"]), a["athlete"]["displayName"]
                qb[aid] = qb[nm] = (int(v.get("YDS", 0) or 0), int(v.get("TD", 0) or 0))
    return win, qb


def grade(row, res):
    win, qb = res
    pick, qid, mk = row["pick"], row.get("qid") or "", row["market"]
    if mk.startswith("ML"):
        return "W" if pick == win else "L"
    me = qb.get(qid) or qb.get(pick)
    if mk.startswith("H2H"):
        others = [v for k, v in qb.items() if k.isdigit() and k != qid]
        if not me or not others:
            return ""
        other = max(others, key=lambda v: v[0])
        return "W" if me[0] > other[0] else "P" if me[0] == other[0] else "L"
    if not me:
        return "DNP"
    need = 2 if mk.startswith("2+") else 1
    return "W" if me[1] >= need else "L"


def main():
    rows = []
    if os.path.exists(LOG):
        rows = list(csv.DictReader(open(LOG)))
    key = lambda r: (r.get("gid") or r["game"], r["market"], r["pick"])
    have = {key(r): r for r in rows}
    page = pagefile.read()
    added = 0
    for sport, mk, gid, kick, game, pick, model, book, qid in reads(page):
        k = T(kick)
        if not (NOW < k <= NOW + dt.timedelta(hours=2)):
            continue                      # written in the last two hours, frozen at kickoff
        et = k.astimezone(ET)
        r = {"date": et.strftime("%Y-%m-%d"), "kick": et.strftime("%-I:%M %p"), "sport": sport, "market": mk, "game": game,
             "pick": pick, "model": model, "book": book, "result": "", "gid": gid, "kick_utc": kick, "qid": qid}
        if key(r) not in have:
            rows.append(r)
            have[key(r)] = r
            added += 1
        else:
            have[key(r)].update({x: r[x] for x in ("model", "book")})
    # a read that was dropped before kickoff (the line moved it out) is not a read
    rows = [r for r in rows if r.get("result") or not r.get("kick_utc") or T(r["kick_utc"]) <= NOW
            or any(key(r) == (g, m, p) for _s, m, g, _k, _g, p, *_ in reads(page))]
    graded, cache = 0, {}
    for r in rows:
        if r.get("result") or not r.get("gid") or T(r["kick_utc"]) > NOW - dt.timedelta(hours=3):
            continue
        g = (r["sport"], r["gid"])
        if g not in cache:
            cache[g] = box(*g)
        if cache[g]:
            r["result"] = grade(r, cache[g])
            graded += 1 if r["result"] else 0
    print("reads log: %d new, %d graded, %d rows" % (added, graded, len(rows)))
    if not DRY:
        w = csv.DictWriter(open(LOG, "w", newline=""), fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main()
