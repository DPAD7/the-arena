"""Old prices, out of our own database.

   keep_prices.py only sees what is on the page now, so a week that was
   played before it existed has no file. This reads qbspy's dk_prop -- every
   DraftKings price we have ever recorded -- and writes the last reading
   before kickoff for each named passer into prices/nfl/wk{n}/{eid}.json,
   the same shape keep_prices.py writes. A game that already has a file
   keeps it; only what is missing is filled.

   Names are matched through person_name, never guessed: DraftKings' own
   spelling is looked up there and must resolve to the passer's ESPN id.

   Usage:  python3 backfill_prices.py            (writes)
           python3 backfill_prices.py --dry
"""
import datetime as dt
import json
import os
import re
import sqlite3
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qbspy.db")
DRY = "--dry" in sys.argv


def T(x):
    d = dt.datetime.fromisoformat(str(x).replace("Z", "+00:00"))
    return d if d.tzinfo else d.replace(tzinfo=dt.timezone.utc)   # dk_prop writes local, naive


def main():
    s = pagefile.read()
    sched = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    db = sqlite3.connect(DB)
    person = {w: str(p) for w, p in db.execute("select written, person_id from person_name")}
    # a man the board priced who did not take the snaps: the price is his, and
    # it is the price that stands for that side. Sam Darnold was hurt and Drew
    # Lock played at Seattle in week one (Jose, Sep 16, 2026).
    stood_in = json.load(open(D + "/data/priced_instead.json")) if os.path.exists(D + "/data/priced_instead.json") else {}

    # two archives: dk_prop (the board as we read it) and hub_prop (iSportGenius'
    # own per-fixture board, which serves a past week on request -- build/hub_props.py
    # 2026 1). Both are DraftKings' prices; the hub is the deeper of the two.
    rows = db.execute("""select starts, player, player_id, market, said, odds, selection_id, read_on
                           from dk_prop
                          where league = 'nfl'
                            and (market = 'Anytime TD Scorer' or market = '2+ TDs'
                                 or market like '%Passing Touchdowns')
                          order by read_on""").fetchall()
    for kickoff, player, market, odds, sel, read_on in db.execute(
            """select kickoff, player, market, odds, outcome_id, read_on
                 from hub_prop
                where market in ('1+ Passing Touchdowns', '2+ Passing Touchdowns',
                                 'Touchdown Scorer', '2+ Touchdowns')
             order by read_on"""):
        said = {"1+ Passing Touchdowns": "1+", "2+ Passing Touchdowns": "2+"}.get(market, "")
        m = {"Touchdown Scorer": "Anytime TD Scorer", "2+ Touchdowns": "2+ TDs"}.get(market, "Passing Touchdowns")
        # the hub is read after the fact by design, so its rows carry no
        # "before kickoff" test: they are that week's board as it closed
        rows.append((str(kickoff).replace(" ", "T"), player, None, m if m != "Passing Touchdowns" else "Passing Touchdowns",
                     said, odds, sel, "hub"))
    by_day = {}
    for starts, player, pid, market, said, odds, sel, read_on in rows:
        if not starts:
            continue
        by_day.setdefault(starts[:10], []).append((player, pid, market, said, odds, sel, read_on, starts))

    wrote, skipped, unmatched = 0, 0, set()
    for g in sched:
        eid, kick, away, home = g[1], T(g[2]), g[3], g[4]
        if kick > dt.datetime.now(dt.timezone.utc):
            continue
        f = D + "/prices/nfl/wk%s/%s.json" % (g[0], eid)
        if os.path.exists(f) and json.load(open(f)).get("passers", [{}])[0].get("atd", [None])[0]:
            skipped += 1
            continue
        # the two archives stamp kickoff in different zones, so the day either
        # side is read as well and the window below settles it
        pool = []
        for off in (-1, 0, 1):
            pool += by_day.get((kick + dt.timedelta(days=off)).strftime("%Y-%m-%d"), [])
        passers = []
        for i, (name, espn) in enumerate(((g[5], str(g[6])), (g[7], str(g[8])))):
            if not name:
                continue
            swap = (stood_in.get(eid) or {}).get(str(i))
            if swap:
                name, espn = swap["name"], str(swap["id"])
            ptd = [None, None]
            atd = [None, None]
            for player, pid, market, said, odds, sel, read_on, starts in pool:
                # the man, through the register -- never by the written name alone
                who = person.get(player)
                if who != espn:
                    if player == name:
                        unmatched.add(player)
                    continue
                if abs((T(starts) - kick).total_seconds()) > 18 * 3600:
                    continue
                if read_on != "hub" and T(read_on) > kick:
                    continue
                if market.endswith("Passing Touchdowns"):
                    if said in ("1+", "2+"):
                        ptd[int(said[0]) - 1] = [odds, sel]
                elif market == "Anytime TD Scorer":
                    atd[0] = [odds, sel]
                elif market == "2+ TDs":
                    atd[1] = [odds, sel]
            passers.append({"name": name, "id": espn, "side": i, "ptd": ptd, "atd": atd})
        if not any(p["ptd"][0] or p["atd"][0] for p in passers):
            continue
        old = json.load(open(f)) if os.path.exists(f) else {}
        out = {"eid": eid, "league": "nfl", "week": g[0], "kick": g[2], "away": away, "home": home,
               "passers": passers,
               "ml": old.get("ml") or [g[9] or None, g[11] or None],
               "h2h": old.get("h2h") or [None, None],
               "read": "backfilled from dk_prop"}
        # a price the page already held beats a database reading
        for i, p in enumerate(out["passers"]):
            was = (old.get("passers") or [])
            if i < len(was):
                for k in (0, 1):
                    if (was[i].get("ptd") or [None, None])[k]:
                        p["ptd"][k] = was[i]["ptd"][k]
                    if (was[i].get("atd") or [None, None])[k]:
                        p["atd"][k] = was[i]["atd"][k]
        if not DRY:
            os.makedirs(os.path.dirname(f), exist_ok=True)
            json.dump(out, open(f, "w"), separators=(",", ":"))
        wrote += 1
    print("backfilled %d games, %d already priced%s" % (wrote, skipped, " (dry)" if DRY else ""))
    if unmatched:
        print("written names the register does not hold (%d): %s" % (len(unmatched), ", ".join(sorted(unmatched)[:8])))


if __name__ == "__main__":
    main()
