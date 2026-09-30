"""Who clears two passing touchdowns before the fourth quarter.

   A 2+ passing touchdown leg that lands in the first three quarters is a
   different bet from one that lands with nine seconds left, and the board
   prices them the same. This counts the first kind: for every game we hold,
   when each passer's touchdowns actually landed, and whether he had two of
   them by the end of the third.

   Written to site/early.json as

       {"weeks": {"2": [{"qb": "J.Allen", "id": "...", "club": "BUF",
                         "early": true, "at": 18.2, "tds": [[1,"3:42"], ...]}]},
        "form":  {"J.Allen": {"games": 2, "early": 1, "rate": 0.5,
                              "q13": 2.0, "last": [false, true]}}}

   `at` is minutes into the game the second one landed, so 18.2 is early in
   the second quarter and 59.9 is nine seconds from the end. `q13` is his
   passing touchdowns in quarters one to three, per game -- the number that
   says how early an offense scores rather than how much.

   Usage:  python3 build/early_two.py           every week we hold
           python3 build/early_two.py --week 2  one week
"""
import collections
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
OUT = os.path.join(D, "site", "early.json")
# the passer's own abbreviation as the play files write it: J.Allen
SAYS = re.compile(r"([A-Z]\.[A-Za-z.'-]+) pass\b")


def summary(gid):
    """The settled file if we have it, otherwise ask -- a game being played
       counts as far as it has got, which is what makes this useful on Sunday
       rather than on Monday."""
    f = os.path.join(D, "site", "final", "%s.json" % gid)
    if os.path.exists(f):
        try:
            return json.load(open(f))
        except ValueError:
            pass
    try:
        return rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
                      "summary?event=%s" % gid, impersonate="chrome", timeout=25).json()
    except Exception:
        return None


def mins(q, clock):
    """How far into the game a play stands, in minutes. Overtime keeps
       counting, so a fifth quarter reads past sixty."""
    m, s = clock.split(":")
    return (q - 1) * 15 + (15 - int(m) - int(s) / 60.0)


def read_game(gid):
    """Every passer in the game: when his touchdowns landed, and whether he
       had two of them before the fourth."""
    d = summary(gid)
    if not d:
        return {}
    tds, seen = collections.defaultdict(list), set()
    for dr in ((d.get("drives") or {}).get("previous") or []):
        for p in (dr.get("plays") or []):
            t = p.get("text") or ""
            m = SAYS.search(t)
            if not m:
                continue
            seen.add(m.group(1))
            if "TOUCHDOWN" not in t.upper():
                continue
            q = (p.get("period") or {}).get("number")
            c = (p.get("clock") or {}).get("displayValue")
            if q and c:
                tds[m.group(1)].append((q, c))
    # the club each man threw for, so the board can name him properly
    club = {}
    for t in ((d.get("boxscore") or {}).get("players") or []):
        ab = ((t.get("team") or {}).get("abbreviation")) or ""
        for c in (t.get("statistics") or []):
            if c.get("name") != "passing":
                continue
            for a in (c.get("athletes") or []):
                nm = ((a.get("athlete") or {}).get("shortName")
                      or (a.get("athlete") or {}).get("displayName") or "")
                pid = str(((a.get("athlete") or {}).get("id")) or "")
                if nm:
                    club[nm.replace(" ", "")] = (ab, pid)
    out = {}
    for nm in seen:
        got = sorted(tds.get(nm, []), key=lambda x: mins(*x))
        q13 = sum(1 for q, _ in got if q <= 3)
        at = mins(*got[1]) if len(got) >= 2 else None
        ab, pid = club.get(nm.replace(" ", ""), ("", ""))
        out[nm] = {"qb": nm, "club": ab, "id": pid,
                   "tds": got, "q13": q13,
                   "early": q13 >= 2,
                   "at": round(at, 1) if at is not None else None}
    return out


def defense(games):
    """Passing touchdowns each club gives up in the first three quarters.
       The same play-by-play read from the other side: a touchdown scored by
       the club with the ball is one allowed by the club without it."""
    allowed, played = collections.Counter(), collections.Counter()
    def one(x):
        gid, aw, hm = x
        return summary(gid), aw, hm
    with ThreadPoolExecutor(10) as ex:
        for d, aw, hm in ex.map(one, games):
            if not d:
                continue
            played[aw] += 1
            played[hm] += 1
            for dr in ((d.get("drives") or {}).get("previous") or []):
                off = ((dr.get("team") or {}).get("abbreviation")) or ""
                for p in (dr.get("plays") or []):
                    t = p.get("text") or ""
                    if "TOUCHDOWN" not in t.upper() or " pass" not in t:
                        continue
                    q = (p.get("period") or {}).get("number")
                    if not q or q > 3:
                        continue
                    d2 = hm if off == aw else aw
                    if d2:
                        allowed[d2] += 1
    return {c: round(allowed[c] / played[c], 2) for c in played if played[c]}


def slate(form, soft, sched, week):
    """This week's board: every passer still to play, his own early rate set
       against how freely the club in front of him gives one up. The number
       is what to expect before the fourth quarter, not over the whole game --
       two of them is the leg (Jose, Sep 20, 2026: "who will do that, no
       sweat")."""
    out = []
    lg = sum(soft.values()) / len(soft) if soft else 1.0
    for g in sched:
        if int(g[0]) != week:
            continue
        for nm, club, opp in ((g[5], g[3], g[4]), (g[7], g[4], g[3])):
            if not nm:
                continue
            short = nm.split()[0][0] + "." + nm.split()[-1]
            f = form.get(short)
            if not f or not f["games"]:
                continue
            d = soft.get(opp)
            # his own pace before the fourth, moved by the defense in front of
            # him; a club nobody has scored on yet is not proof of anything, so
            # it is held halfway to the league
            pull = 1.0 if d is None else (d + lg) / (2 * lg) if lg else 1.0
            out.append({"qb": short, "name": nm, "club": club, "opp": opp,
                        "own": f["q13"], "soft": d,
                        "expect": round(f["q13"] * pull, 2),
                        "record": "%d of %d" % (f["early"], f["games"])})
    out.sort(key=lambda r: -r["expect"])
    return out


def main():
    want = None
    if "--week" in sys.argv:
        want = int(sys.argv[sys.argv.index("--week") + 1])
    page = pagefile.read()
    i = page.index("  var SCHED = [[")
    j = page.index("];", i)
    sched = json.loads(page[i + len("  var SCHED = "):j + 1])
    games = [(int(g[0]), str(g[1])) for g in sched
             if (want is None or int(g[0]) == want)]
    # only weeks that have started: a fixture nobody has played says nothing
    weeks = collections.defaultdict(list)
    with ThreadPoolExecutor(10) as ex:
        for (wk, gid), got in zip(games, ex.map(lambda x: read_game(x[1]), games)):
            for nm, row in (got or {}).items():
                weeks[str(wk)].append(row)
    form = {}
    for wk in sorted(weeks, key=int):
        for r in weeks[wk]:
            f = form.setdefault(r["qb"], {"games": 0, "early": 0, "q13": 0, "last": []})
            f["games"] += 1
            f["early"] += 1 if r["early"] else 0
            f["q13"] += r["q13"]
            f["last"].append(bool(r["early"]))
    for nm, f in form.items():
        f["rate"] = round(f["early"] / f["games"], 3) if f["games"] else 0
        f["q13"] = round(f["q13"] / f["games"], 2) if f["games"] else 0
    weeks_played = {int(w) for w in weeks}
    for wk in sorted(weeks, key=int):
        hit = [r for r in weeks[wk] if r["early"]]
        print("week %s: %d of %d cleared 2 before the fourth" % (wk, len(hit), len(weeks[wk])))
        for r in sorted(hit, key=lambda r: r["at"] or 99):
            print("   %-12s %-4s  2nd at %4.1f min  (%s)"
                  % (r["qb"], r["club"], r["at"] or 0,
                     " ".join("Q%s %s" % t for t in r["tds"])))
    soft = defense([(str(g[1]), g[3], g[4]) for g in sched if int(g[0]) in weeks_played])
    nxt = (max(int(w) for w in weeks) + 1) if weeks else 1
    board = slate(form, soft, sched, nxt)
    json.dump({"weeks": {k: sorted(v, key=lambda r: (r["at"] is None, r["at"] or 99))
                         for k, v in weeks.items()},
               "form": form, "defense": soft, "next": {"week": nxt, "board": board}},
              open(OUT, "w"), separators=(",", ":"))
    # The picks, written down before the games and never rewritten after.
    # A rule you grade after the fact is not a rule, so the top of the board
    # is locked here with the day it was called and checked when the week is
    # played (Jose, Sep 20, 2026: "yesterday leads to today?" -- this is how
    # we find out).
    if board:
        called = os.path.join(D, "data", "early_called.json")
        try:
            log = json.load(open(called))
        except Exception:
            log = {}
        key = str(nxt)
        if key not in log:
            log[key] = {"called": __import__("datetime").datetime.now(
                            __import__("datetime").timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                        "top3": [r["qb"] for r in board[:3]],
                        "top5": [r["qb"] for r in board[:5]],
                        "board": [{"qb": r["qb"], "opp": r["opp"], "expect": r["expect"]} for r in board]}
            json.dump(log, open(called, "w"), indent=1)
            print("week %d picks written down: %s" % (nxt, ", ".join(log[key]["top3"])))
        else:
            print("week %d was already called on %s: %s"
                  % (nxt, log[key]["called"], ", ".join(log[key]["top3"])))
        # and grade every week that has since been played
        for wk in sorted(log, key=int):
            hit = {r["qb"] for r in weeks.get(wk, []) if r["early"]}
            played = {r["qb"] for r in weeks.get(wk, [])}
            if not played:
                continue
            t3 = [q for q in log[wk]["top3"] if q in played]
            if not t3:
                continue
            got = [q for q in t3 if q in hit]
            rest = played - set(log[wk]["top3"])
            base = len([q for q in rest if q in hit]) / len(rest) if rest else 0
            print("   week %s graded: top three %d of %d (%.0f%%)  everyone else %.0f%%"
                  % (wk, len(got), len(t3), 100 * len(got) / len(t3), 100 * base))
    if board:
        print()
        print("WEEK %d -- most likely to have two before the fourth" % nxt)
        print("   %-12s %-4s %-5s %-6s %-6s %s" % ("passer", "v", "own", "their", "expect", "record"))
        for r in board[:14]:
            print("   %-12s %-4s %-5.1f %-6s %-6.2f %s"
                  % (r["qb"], r["opp"], r["own"],
                     "-" if r["soft"] is None else "%.1f" % r["soft"],
                     r["expect"], r["record"]))
    print()
    print("form, most reliable first")
    for nm, f in sorted(form.items(), key=lambda kv: (-kv[1]["rate"], -kv[1]["q13"])):
        if not f["games"]:
            continue
        print("   %-12s %d of %d   %.1f TD in Q1-Q3 a game" % (nm, f["early"], f["games"], f["q13"]))


if __name__ == "__main__":
    main()
