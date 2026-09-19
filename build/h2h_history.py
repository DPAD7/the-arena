"""Does the market's head-to-head favorite actually throw for more yards?

   Eleven games said 45% and that is not an answer. The gamebooks go back to
   2009 and league_game carries the closing moneyline on 2,123 of them, so the
   same question can be asked of a real pile of football.

   The plays do not say which club a passer belongs to. The scoring plays do:
   game_score gives the scoring club and the text names the man who threw it.
   That is enough to put each passer on a side in any game where he threw a
   touchdown, which is most of them.
"""
import os
import collections
import re
import sqlite3

db = sqlite3.connect(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qbspy.db"))
c = db.cursor()

# nickname -> abbreviation, as the register holds it
club = {}
for written, abbr in c.execute("select written, abbr from club_name"):
    club[written.strip().lower()] = abbr
    club[written.strip().lower().split()[-1]] = abbr

# who threw for whom, read off the scoring plays
side = collections.defaultdict(dict)
PASS = re.compile(r"pass from ([A-Z][A-Za-z.'\-]+)")
for gid, team, said in c.execute("select game_id, team, said from game_score "
                                 "where said like '%pass from%'"):
    m = PASS.search(said or "")
    if not m or not team:
        continue
    ab = club.get((team or "").strip().lower()) or club.get((team or "").strip().lower().split()[-1])
    if ab:
        side[gid][m.group(1)] = ab

# passing yards per man per game
yards = collections.defaultdict(lambda: collections.defaultdict(int))
att = collections.defaultdict(lambda: collections.defaultdict(int))
for gid, passer, result, y in c.execute(
        "select game_id, passer, result, yards from league_play "
        "where kind='pass' and passer is not null and passer<>''"):
    att[gid][passer] += 1
    if result in ("complete", "touchdown"):
        yards[gid][passer] += (y or 0)


def money(t):
    try:
        return int(str(t).replace("−", "-").replace("+", ""))
    except Exception:
        return None


rows = []
for gid, season, home, away, hs, asc, hm, am in c.execute(
        "select game_id, season, home, away, home_score, away_score, home_money, away_money "
        "from league_game where home_score+away_score>0 and home_money is not null "
        "and home_money<>'' and away_money is not null and away_money<>''"):
    hmv, amv = money(hm), money(am)
    if hmv is None or amv is None or gid not in side:
        continue
    # the busiest passer on each side
    best = {}
    for passer, n in sorted(att[gid].items(), key=lambda kv: -kv[1]):
        ab = side[gid].get(passer)
        if ab and ab not in best:
            best[ab] = passer
    if home not in best or away not in best:
        continue
    hy, ay = yards[gid][best[home]], yards[gid][best[away]]
    if hy == ay:
        continue
    fav = home if hmv < amv else away
    dog = away if fav == home else home
    favy = hy if fav == home else ay
    dogy = ay if fav == home else hy
    won_game = home if hs > asc else (away if asc > hs else None)
    rows.append({"season": season, "fav": fav, "dog": dog,
                 "fav_threw_more": favy > dogy,
                 "fav_won": won_game == fav,
                 "margin": abs(hs - asc),
                 "price": min(hmv, amv)})

print("games with a closing price, both passers placed, no tie: %d" % len(rows))
if not rows:
    raise SystemExit

hit = sum(1 for r in rows if r["fav_threw_more"])
print("\nthe TEAM favorite's quarterback threw for more yards in %d of %d  (%.1f%%)"
      % (hit, len(rows), 100.0 * hit / len(rows)))

print("\nby how short the favorite was:")
for lo, hi, label in ((-100000, -400, "shorter than -400"), (-400, -250, "-400 to -250"),
                      (-250, -160, "-250 to -160"), (-160, 0, "-160 to even")):
    g = [r for r in rows if lo <= r["price"] < hi]
    if len(g) < 20:
        continue
    k = sum(1 for r in g if r["fav_threw_more"])
    print("   %-18s %4d games   favorite out-threw in %5.1f%%" % (label, len(g), 100.0 * k / len(g)))

print("\nby the final margin:")
for lo, hi, label in ((0, 4, "1-3 points"), (4, 9, "4-8"), (9, 15, "9-14"),
                      (15, 22, "15-21"), (22, 200, "22+")):
    g = [r for r in rows if lo <= r["margin"] < hi]
    if len(g) < 20:
        continue
    k = sum(1 for r in g if r["fav_threw_more"])
    print("   %-12s %4d games   favorite out-threw in %5.1f%%" % (label, len(g), 100.0 * k / len(g)))

w = [r for r in rows if r["fav_won"]]
l = [r for r in rows if not r["fav_won"]]
print("\nwhen the favorite WON the game:  %4d  he out-threw in %5.1f%%" % (len(w), 100.0 * sum(1 for r in w if r["fav_threw_more"]) / len(w)))
print("when the favorite LOST the game: %4d  he out-threw in %5.1f%%" % (len(l), 100.0 * sum(1 for r in l if r["fav_threw_more"]) / len(l)))
