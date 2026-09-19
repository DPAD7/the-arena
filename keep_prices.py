"""Keep every passing and anytime touchdown price DraftKings posts.

   PROPS on the page holds only what is on offer now: a game that has kicked
   is overwritten by the next week's. This copies each game's prices out of
   the page into prices/{week}/{event id}.json the moment they are read, so
   the ledger can say later what a man was priced at, whether or not the
   board ever drew it.

   One file a game: {"eid", "week", "kick", "away", "home", "passers":
   [{name, id, side, ptd: [1+, 2+], atd: [1+, 2+]}], "ml": [away, home],
   "h2h": [away, home], "read": when this copy was taken}. A price already
   written is never overwritten -- the first reading before kickoff is the
   one the ledger settles against; a later reading is added under "moves".

   Usage:  python3 keep_prices.py
"""
import datetime as dt
import json
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
NOW = dt.datetime.now(dt.timezone.utc)


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def main():
    s = open(D + "/master.html").read()
    props = json.loads(re.search(r"  var PROPS = (\{.*?\});\n", s, re.S).group(1))
    kept, moved = 0, 0
    for var in ("SCHED", "CFB"):
        rows = json.loads(re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S).group(1))
        ml_at = (9, 11) if var == "SCHED" else (10, 12)
        for g in rows:
            pr = props.get(g[1])
            if not pr:
                continue
            passers = []
            for i, (name, pid) in enumerate(((g[5], g[6]), (g[7], g[8]))):
                if not name:
                    continue
                passers.append({"name": name, "id": str(pid), "side": i,
                                "ptd": [(pr.get("ptd") or [[None, None], [None, None]])[i][k] for k in (0, 1)],
                                "atd": [(pr.get("atd") or [[None, None], [None, None]])[i][k] for k in (0, 1)]})
            now = {"eid": g[1], "league": "nfl" if var == "SCHED" else "ncaaf", "week": g[0],
                   "kick": g[2], "away": g[3], "home": g[4], "passers": passers,
                   "ml": [g[ml_at[0]] or None, g[ml_at[1]] or None],
                   "h2h": [(pr.get("h2h") or [None, None])[i] for i in (0, 1)],
                   "read": NOW.isoformat(timespec="seconds")}
            out = D + "/prices/%s/wk%s" % (now["league"], g[0])
            os.makedirs(out, exist_ok=True)
            f = out + "/%s.json" % g[1]
            if os.path.exists(f):
                old = json.load(open(f))
                # a file written without a head-to-head or moneyline takes the
                # page's, whenever the game was played (Jose, Sep 16, 2026)
                filled = False
                for key in ("h2h", "ml"):
                    have = old.get(key) or [None, None]
                    if not any(have) and any(now[key]):
                        old[key] = now[key]
                        filled = True
                if filled:
                    json.dump(old, open(f, "w"), separators=(",", ":"))
                    kept += 1
                same = json.dumps(old.get("passers")) == json.dumps(passers) and old.get("ml") == now["ml"] and old.get("h2h") == now["h2h"]
                if same:
                    continue
                if T(g[2]) > NOW:                     # still to kick: the move is worth keeping
                    old.setdefault("moves", []).append({"read": now["read"], "passers": passers, "ml": now["ml"], "h2h": now["h2h"]})
                    json.dump(old, open(f, "w"), separators=(",", ":"))
                    moved += 1
                continue
            json.dump(now, open(f, "w"), separators=(",", ":"))
            kept += 1
    total = sum(len(fs) for _, _, fs in os.walk(D + "/prices"))
    print("prices kept: %d new, %d moves | %d games on file" % (kept, moved, total))


if __name__ == "__main__":
    main()
