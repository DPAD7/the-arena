"""The passing-touchdown rungs a man actually reached, priced.

   The board carries 1+ and 2+ from DraftKings, because that is what it sells
   live. A four-touchdown game is worth far more than the 2+ rung says: Trevor
   Lawrence's week 1 was +1500 at 4+, not -108 at 2+. Action Network keeps the
   milestone ladder to 5+ per book after the books drop it, so the rungs are
   read from there and written into site/ledger.json as a 14th field:

     [1+, 2+, 3+, 4+, 5+]   DraftKings, falling back to the consensus

   Whole-game prices only: the feed keys a first-quarter line the same way.

   Nothing is invented: a rung no book priced is written null, and the page
   falls back to the highest rung we do hold. (Jose, Sep 17, 2026)

   Usage:  python3 alt_ptd.py
"""
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
H = {"accept": "application/json"}
AB = {"JAX": "JAC", "WSH": "WAS", "LAR": "LA"}
DK, CONSENSUS = 30, 15


def an_games(season, week):
    u = ("https://api.actionnetwork.com/web/v2/scoreboard/nfl?period=game"
         "&week=%d&seasonType=reg&season=%d" % (week, season))
    d = rq.get(u, headers=H, impersonate="chrome", timeout=45).json()
    out = {}
    for g in d.get("games") or []:
        out[tuple(sorted(x.get("abbr") or "" for x in (g.get("teams") or [])))] = g["id"]
    return out


def rungs(props, surname):
    """[1+ .. 5+] for this man, DraftKings first, else the consensus."""
    pl = props["players"]
    got, mine = [None] * 5, [None] * 5
    for n in range(1, 6):
        dk = con = None
        for k in props["player_props"]:
            if "passing_touchdowns_milestones_%d_or_more" % n not in k:
                continue
            for o in props["player_props"][k]:
                for bid, lines in (o.get("lines") or {}).items():
                    for ln in lines:
                        p = pl.get(str(ln.get("player_id"))) or {}
                        full = (p.get("full_name") or "").strip().split()
                        # the surname, whole -- matching "Lock" inside "Lockett"
                        # is how a man who was never priced looked priced
                        if not full or full[-1].lower() != surname:
                            continue
                        # the same key carries the whole game and the first
                        # quarter. Keeping whichever came last put a first
                        # quarter +20000 on Josh Allen's 3+ rung, where the
                        # game itself was +235 (Jose, Sep 18, 2026)
                        if (ln.get("period") or "event") != "event":
                            continue
                        if int(bid) == DK:
                            dk = ln.get("odds")
                        elif int(bid) == CONSENSUS:
                            con = ln.get("odds")
        v = dk if dk is not None else con
        got[n - 1] = ("%+d" % v) if v is not None else None
        mine[n - 1] = ("%+d" % dk) if dk is not None else None
    return got, mine


def main():
    led = json.load(open(D + "/site/ledger.json"))
    s = pagefile.read()
    sched = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    clubs = {g[1]: (g[3], g[4]) for g in sched}
    week_of = {g[1]: g[0] for g in sched}
    cache, found, blank, added = {}, 0, 0, 0
    PR = json.load(open(D + "/site/prices.json"))
    sides = {}
    for g in sched:
        sides[(str(g[1]), str(g[6]))] = 0
        sides[(str(g[1]), str(g[8]))] = 1
    for wk, rows in led.items():
        games = an_games(2026, int(wk))
        for r in rows:
            eid = r[8]
            key = tuple(sorted(AB.get(x, x) for x in clubs.get(eid, ("", ""))))
            gid = games.get(key)
            if not gid:
                print("  no archive game for", eid, key)
                continue
            if gid not in cache:
                # a game the archive has no board for answers with a page, not
                # JSON, and took the whole run down with it (Jose, Sep 17, 2026)
                try:
                    cache[gid] = rq.get("https://api.actionnetwork.com/web/v2/games/%d/props" % gid,
                                        headers=H, impersonate="chrome", timeout=45).json()
                except Exception as e:
                    print("  no board for game %s: %s" % (gid, str(e)[:60]))
                    cache[gid] = {"players": {}, "player_props": {}}
            got, dk = rungs(cache[gid], r[0].split()[-1].lower())
            # DraftKings' own rungs the board did not keep -- 4+ and 5+ before
            # Sep 28, 2026 -- go on the game's ladder, so the best price that
            # paid can be a 4+ (Jose: "he threw for four"). Only DraftKings',
            # never the consensus
            side = sides.get((str(eid), str(r[2])))
            pr = (PR.get("PROPS") or {}).get(str(eid))
            if side is not None and pr and pr.get("ptd"):
                lad = pr["ptd"][side] = list(pr["ptd"][side] or [])
                for k, v in enumerate(dk):
                    if v is None:
                        continue
                    while len(lad) <= k:
                        lad.append(None)
                    if not lad[k]:
                        lad[k] = [v, ""]
                        added += 1
            while len(r) < 14:
                r.append(None)
            r[13] = got
            if any(got):
                found += 1
            else:
                blank += 1
                print("  no rungs: %-20s %s" % (r[0], r[1]))
    json.dump(led, open(D + "/site/ledger.json", "w"), separators=(",", ":"))
    json.dump(PR, open(D + "/site/prices.json", "w"), separators=(",", ":"))
    print("DraftKings rungs added to the board's ladders: %d" % added)
    print("rungs written for %d passers, %d had none" % (found, blank))


if __name__ == "__main__":
    main()
