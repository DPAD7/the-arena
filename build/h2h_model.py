"""What the head to head would have paid, read off the alt-yards ladders.

   DraftKings never posted the passing-yards matchup on four week-one games
   and no archive holds it. It does hold both men's whole alt-yards ladder,
   and a ladder is a distribution: each rung's price is the chance he clears
   that many yards. Fit a curve to each man's rungs, ask how often one draw
   beats the other, and write it as a price.

   The method is checked against the twelve games where the real head to head
   is known, and the error is printed. Nothing is written to the board.

   Usage:  python3 h2h_model.py
"""
import json
import math
import os
import sys
import re
import sqlite3
import statistics

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qbspy.db")
VIG = 0.045          # the two sides of a matchup are priced to about 104.5%


def dec(o):
    n = int(str(o).replace("−", "-").replace("+", ""))
    return 1 + n / 100.0 if n > 0 else 1 + 100.0 / -n


def chance(o):
    return 1.0 / dec(o)


def spellings(db, name):
    """Every way the sources write this man, through the register -- the hub
       says "Cameron Ward" where the board says "Cam Ward"."""
    pid = db.execute("select person_id from person_name where written = ? limit 1", (name,)).fetchone()
    if not pid:
        return [name]
    return [w for (w,) in db.execute("select distinct written from person_name where person_id = ?", (pid[0],))] or [name]


def ladder(db, fixture_like, name):
    """His rungs: [(yards, chance of clearing)] with the book's margin taken out."""
    rows = []
    for w in spellings(db, name):
        rows += db.execute("""select player, odds from hub_prop
                              where fixture like ? and market = 'Alt Passing Yards'
                                and player like ?""", (fixture_like, w + " %")).fetchall()
    out = {}
    for player, odds in rows:
        m = re.search(r"(\d+)\+$", player.strip())
        if not m:
            continue
        out[int(m.group(1))] = chance(odds)
    return sorted(out.items())


def fit(rungs):
    """The normal that best matches the ladder: its mean and spread."""
    pts = [(y, p) for y, p in rungs if 0.02 < p < 0.98]
    if len(pts) < 6:          # a short ladder fits badly
        return None
    # p(clear y) = 1 - Phi((y - mu)/sd)  ->  z = Phi^-1(1 - p) is linear in y
    xs, zs = [], []
    for y, p in pts:
        p = min(max(p / (1 + VIG), 0.01), 0.99)
        z = math.sqrt(2) * erfinv(2 * (1 - p) - 1)
        xs.append(y); zs.append(z)
    n = len(xs)
    mx, mz = sum(xs) / n, sum(zs) / n
    var = sum((x - mx) ** 2 for x in xs)
    if not var:
        return None
    b = sum((x - mx) * (z - mz) for x, z in zip(xs, zs)) / var    # b = 1/sd
    if b <= 0:
        return None
    sd = 1 / b
    mu = mx - mz * sd
    return mu, sd


def erfinv(x):
    a = 0.147
    ln = math.log(1 - x * x) if abs(x) < 1 else -30.0
    t = 2 / (math.pi * a) + ln / 2
    return math.copysign(math.sqrt(max(math.sqrt(t * t - ln / a) - t, 0.0)), x)


def american(p):
    if p <= 0 or p >= 1:
        return None
    d = 1 / p
    return "+%d" % round((d - 1) * 100) if d >= 2 else "−%d" % round(100 / (d - 1))


def main():
    s = pagefile.read()
    S = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    P = json.loads(re.search(r"  var PROPS = (\{.*?\});\n", s, re.S).group(1))
    db = sqlite3.connect(DB)
    fixtures = {f for (f,) in db.execute("select distinct fixture from hub_prop")}
    errs = []
    print("%-10s %-30s %-16s %-16s" % ("GAME", "MODELLED", "REAL", "ERROR"))
    for g in [g for g in S if g[0] == 1]:
        pick = [f for f in fixtures if " @ " in f]
        fix = None
        for f in pick:
            if g[3].lower() in f.lower().replace(" ", "")[:0] or True:
                pass
        # the fixture is named by clubs; match on both passers being in it
        def here(f, name):
            for w in spellings(db, name):
                if db.execute("select count(*) from hub_prop where fixture = ? and player like ? limit 1", (f, w + " %")).fetchone()[0]:
                    return True
            return False
        cand = [f for f in fixtures if here(f, g[5]) and here(f, g[7])]
        if not cand:
            continue
        fix = cand[0]
        A, B = fit(ladder(db, fix, g[5])), fit(ladder(db, fix, g[7]))
        if not A or not B:
            continue
        muA, sdA = A; muB, sdB = B
        z = (muA - muB) / math.sqrt(sdA ** 2 + sdB ** 2)
        pa = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        # the push is tiny and the book prices both sides to 104.5%
        pa_v, pb_v = pa * (1 + VIG) , (1 - pa) * (1 + VIG)
        mine = (american(pa_v), american(pb_v))
        real = [(x or [None])[0] for x in ((P.get(g[1]) or {}).get("h2h") or [None, None])]
        tag = "%s/%s" % (g[3], g[4])
        if real[0]:
            e = abs(chance(mine[0]) - chance(real[0])) * 100
            errs.append(e)
            print("%-10s %-30s %-16s %.1f pts" % (tag, "%s %s / %s %s" % (g[5].split()[-1], mine[0], g[7].split()[-1], mine[1]),
                                                  "%s / %s" % (real[0], real[1]), e))
        else:
            print("%-10s %-30s %-16s  <- no real price" % (tag, "%s %s / %s %s" % (g[5].split()[-1], mine[0], g[7].split()[-1], mine[1]), "none"))
    if errs:
        print("\nchecked on %d games: average error %.1f points of implied chance, worst %.1f" % (len(errs), statistics.mean(errs), max(errs)))


if __name__ == "__main__":
    main()
