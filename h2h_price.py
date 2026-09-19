"""What a head-to-head is really worth, from the two men's own games.

   A head-to-head asks one question: does A throw for more than B. Nobody has
   to model that — the gamebooks hold every game either man has played, so the
   two distributions can simply be run against each other. Every one of A's
   games against every one of B's, and count how often A is in front.

   Usage:  python3 h2h_price.py "J.Burrow" "B.Mayfield" -226
           python3 h2h_price.py --week        (this week's board)
"""
import collections
import re
import sqlite3
import sys

DB = "/Users/joe/qbspy/data/qbspy.db"


def load():
    db = sqlite3.connect(DB)
    c = db.cursor()
    att = collections.defaultdict(lambda: collections.defaultdict(int))
    yds = collections.defaultdict(lambda: collections.defaultdict(int))
    for gid, p, r, y in c.execute("select game_id,passer,result,yards from league_play "
                                  "where kind='pass' and passer is not null and passer<>''"):
        att[gid][p] += 1
        if r in ("complete", "touchdown"):
            yds[gid][p] += (y or 0)
    season = {g: s for g, s in c.execute("select game_id, season from league_game")}
    games = collections.defaultdict(list)
    for gid, byp in att.items():
        for p, a in byp.items():
            if a >= 10:
                games[p].append((season.get(gid) or 0, yds[gid][p]))
    return games


def recent(games, who, n=32):
    g = sorted(games.get(who, []), reverse=True)[:n]
    return [y for _, y in g]


def beats(a, b):
    """Every one of his games against every one of the other man's."""
    win = tie = 0
    for x in a:
        for y in b:
            if x > y:
                win += 1
            elif x == y:
                tie += 1
    n = len(a) * len(b)
    return (win + tie / 2.0) / n if n else None


def american(p):
    if p <= 0 or p >= 1:
        return "—"
    v = -round(100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)
    return ("+%d" % v) if v > 0 else str(v)


def implied(o):
    n = int(str(o).replace("−", "-").replace("+", ""))
    return 100.0 / (n + 100.0) if n > 0 else -n / (-n + 100.0)


def report(games, a, b, price=None, label=""):
    ga, gb = recent(games, a), recent(games, b)
    if len(ga) < 8 or len(gb) < 8:
        print("  %-28s not enough games (%d / %d)" % (label or (a + " v " + b), len(ga), len(gb)))
        return
    p = beats(ga, gb)
    line = "  %-26s %-14s fair %-7s" % (label or (a + " v " + b),
                                        "%d%% (%d v %d g)" % (round(p * 100), len(ga), len(gb)),
                                        american(p))
    if price:
        q = implied(price)
        line += "  offered %-7s = %d%%   edge %+.1f pts" % (price, round(q * 100), (p - q) * 100)
    print(line)


if __name__ == "__main__":
    games = load()
    if len(sys.argv) >= 3 and sys.argv[1] != "--week":
        report(games, sys.argv[1], sys.argv[2],
               sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        print("pass two passers as the gamebook writes them, e.g. J.Burrow B.Mayfield -226")
        print("known passers with 16+ games:")
        big = sorted([p for p, g in games.items() if len(g) >= 16])
        for i in range(0, len(big), 8):
            print("   " + "  ".join("%-12s" % x for x in big[i:i + 8]))
