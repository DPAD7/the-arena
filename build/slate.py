"""What is worth taking out of one slate window, across games.

   He parlays three markets: the moneyline, the quarterback head-to-head, and
   passing touchdowns. This reads the board, groups the cards by kickoff, and
   for every leg in a window puts our own number next to what DraftKings
   charges. One leg per game, so the legs are independent and the card really
   is the product of its parts -- legs inside one game move together and the
   book prices that, which is a different tool.

   Usage:  python3 slate.py                 every window still to come
           python3 slate.py --window 17:00  one window, UTC hour
           python3 slate.py --all           past windows too, to check it
"""
import collections
import datetime
import os
import re
import sqlite3
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qbspy.db")

# What the favorite's quarterback has done, by how short the favorite was:
# 1,293 games with a closing price and both passers placed (h2h_history.py).
BANDS = ((-10000, -400, 0.730), (-400, -250, 0.617),
         (-250, -160, 0.549), (-160, 10000, 0.537))

# A club that runs it this often takes the ball out of its own passer's hands;
# both misses in week one were won on the ground (CHI 39 carries, DET 33).
# The run-heavy filter is dead. Baltimore runs 54.6%, Buffalo 51.7%, Jacksonville
# 46.3% and all three quarterbacks won their head-to-heads on 9/13; Detroit runs
# 43.2% and Goff lost his. It threw out three winners and kept the loser.

FLOOR = -1000              # nothing shorter is worth the ticket


def american(t):
    m = re.match(r"\s*(&minus;|−|-|\+)?\s*(\d+)", (t or "").strip())
    if not m:
        return None
    v = int(m.group(2))
    return -v if m.group(1) in ("&minus;", "−", "-") else v


def implied(o):
    return None if o is None else (100.0 / (o + 100.0) if o > 0 else -o / (-o + 100.0))


def fair(a, b):
    """Both sides of a two-way market, with the book's cut taken back out."""
    pa, pb = implied(a), implied(b)
    if pa is None or pb is None or pa + pb <= 0:
        return implied(a), implied(b)
    return pa / (pa + pb), pb / (pa + pb)


def price(p):
    if not p or p <= 0 or p >= 1:
        return "--"
    v = -round(100 * p / (1 - p)) if p >= 0.5 else round(100 * (1 - p) / p)
    return ("+%d" % v) if v > 0 else str(v)


# ------------------------------------------------------------------ board ----
CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
BTN = r'<button class="price"[^>]*data-oid="([^"]*)"[^>]*>([^<]*)'


def attr(c, k):
    m = re.search(r'data-%s="([^"]*)"' % k, c)
    return m.group(1) if m else ""


def read_board():
    s = open(os.path.join(D, "master.html")).read()
    out = []
    for mm in CARD.finditer(s):
        c = mm.group(0)
        if attr(c, "lg") != "nfl":
            continue
        head = re.search(r'<div class="ghead">.*?</div>\n', c, re.S)
        if not head:
            continue
        teams = re.findall(r'<span class="gteam[^"]*">(?:<span class="gml">.*?</span>)?'
                           r'([A-Za-z&;.]+)(?:<span class="gml">.*?</span>)?</span>',
                           head.group(0), re.S)
        ml = [american(x) for _, x in re.findall(
            r'<span class="gml">' + BTN, head.group(0))]
        while len(ml) < 2:
            ml.append(None)
        h2h = []
        h = re.search(r'<div class="h2hrow">.*?</div>\n', c, re.S)
        if h:
            h2h = [american(x) for _, x in re.findall(
                r'<span class="h2hodds">' + BTN, h.group(0))]
        while len(h2h) < 2:
            h2h.append(None)
        ptd = {}
        for sec in re.finditer(r'<div class="ptdx[^"]*"[^>]*>.*?\n        </div>', c, re.S):
            kind = attr(sec.group(0), "kind") or "PTD"
            if kind != "PTD":
                continue
            for i, which in enumerate(("l", "r")):
                pane = re.search(r'<div class="ptdside ptdside--%s">.*?</div></div>' % which,
                                 sec.group(0), re.S)
                if not pane:
                    continue
                for line, _oid, p in re.findall(
                        r'<span class="ptdline">(\d)\+</span>' + BTN, pane.group(0)):
                    ptd[(i, int(line))] = american(p)
        out.append({"kick": attr(c, "kick"), "espn": attr(c, "espn"),
                    "teams": (teams + ["", ""])[:2],
                    "qb": [attr(c, "lqb"), attr(c, "rqb")],
                    "ml": ml, "h2h": h2h, "ptd": ptd})
    return out


# ----------------------------------------------------------------- record ----
def our_numbers():
    """Each passer's own rate of throwing one and of throwing two, and how
       hard his club leans on the run. Names go through person_name, never
       matched as written."""
    db = sqlite3.connect(DB)
    c = db.cursor()
    pid = {}
    for w, i in c.execute("select written, person_id from person_name"):
        pid[w] = i
    td = collections.defaultdict(lambda: collections.defaultdict(int))
    att = collections.defaultdict(lambda: collections.defaultdict(int))
    for gid, passer, result in c.execute(
            "select game_id, passer, result from league_play "
            "where kind='pass' and passer is not null and passer<>''"):
        att[passer][gid] += 1
        if result == "touchdown":
            td[passer][gid] += 1
    # Fold every spelling onto the one man before counting. A.Rodgers has 238
    # games and Aa.Rodgers has 8; keyed on the last spelling written, he came
    # out an 87% quarterback on eight games.
    byman = collections.defaultdict(dict)
    for passer, games in att.items():
        who = pid.get(passer, passer)
        for g, n in games.items():
            byman[who][g] = max(byman[who].get(g, 0), n)
    hit = collections.defaultdict(lambda: collections.defaultdict(int))
    for passer, games in td.items():
        who = pid.get(passer, passer)
        for g, n in games.items():
            hit[who][g] = max(hit[who][g], n)
    rate = {}
    for who, games in byman.items():
        played = sorted(g for g, n in games.items() if n >= 10)[-48:]
        if len(played) < 16:
            continue
        one = sum(1 for g in played if hit[who][g] >= 1)
        two = sum(1 for g in played if hit[who][g] >= 2)
        rate[who] = (one / float(len(played)), two / float(len(played)), len(played))
    run = {}
    for club, kind, stat, val in c.execute(
            "select club, kind, stat, value from hub_team_split "
            "where side='offense' and cut='all' and stat='ATT'"):
        try:
            v = float(val)
        except Exception:
            continue
        run.setdefault(club, {})[kind] = max(run.get(club, {}).get(kind, 0), v)
    share = {}
    for club, k in run.items():
        tot = k.get("passing", 0) + k.get("rushing", 0)
        if tot:
            share[club] = k.get("rushing", 0) / tot
    return pid, rate, share


def band(fav_price):
    for lo, hi, p in BANDS:
        if lo <= fav_price < hi:
            return p
    return 0.537


# ------------------------------------------------------------------- legs ----
def legs_for(card, pid, rate, share, clubs):
    out = []
    a, b = card["ml"]
    if a is not None and b is not None:
        pa, pb = fair(a, b)
        fi = 0 if a < b else 1
        for i, (p, o) in enumerate(((pa, a), (pb, b))):
            if o <= FLOOR:
                continue
            out.append({"game": "/".join(card["teams"]), "market": "ML",
                        "side": card["teams"][i], "price": o, "ours": p,
                        "edge": 0.0, "why": "no edge -- the book's own number"})
        # head to head, on the favorite's man
        ha, hb = card["h2h"]
        if ha is not None and hb is not None:
            p = band(min(a, b))
            note = "favorite %s, band %.1f%%" % (card["teams"][fi], p * 100)
            o = (ha, hb)[fi]
            if o > FLOOR:
                out.append({"game": "/".join(card["teams"]), "market": "H2H YDS",
                        "side": card["qb"][fi] or card["teams"][fi], "price": o,
                            "ours": p, "edge": p - (implied(o) or 1), "why": note})
    for (i, line), o in sorted(card["ptd"].items()):
        who = card["qb"][i]
        r = rate.get(pid.get(who))
        if not r or o is None:
            continue
        if o <= FLOOR:          # -1000 and worse is not a bet, it is a deposit
            continue
        p = r[0] if line == 1 else r[1]
        out.append({"game": "/".join(card["teams"]), "market": "%d+ PTD" % line,
                    "side": who, "price": o, "ours": p,
                    "edge": p - (implied(o) or 1),
                    "why": "%d of his last %d games" % (round(p * r[2]), r[2])})
    return out


def show(window, cards, pid, rate, share, clubs):
    print("\n" + "=" * 78)
    print("  %s   %d games" % (window, len(cards)))
    print("=" * 78)
    legs = []
    for c in cards:
        legs += legs_for(c, pid, rate, share, clubs)
    legs.sort(key=lambda l: -l["edge"])
    print("  %-14s %-9s %-20s %6s %6s %7s  %s"
          % ("game", "market", "side", "price", "fair", "edge", "why"))
    for l in legs:
        print("  %-14s %-9s %-20s %6s %6s %+6.1f  %s"
              % (l["game"][:14], l["market"], (l["side"] or "")[:20],
                 ("+%d" % l["price"]) if l["price"] > 0 else l["price"],
                 price(l["ours"]), l["edge"] * 100, l["why"][:34]))
    # one leg a game, best edge, nothing under the break-even
    best = {}
    for l in legs:
        if l["edge"] <= 0.005 or l["market"] == "ML":
            continue
        if l["game"] not in best or l["edge"] > best[l["game"]]["edge"]:
            best[l["game"]] = l
    pick = sorted(best.values(), key=lambda l: -l["edge"])
    if not pick:
        print("\n  nothing in this window clears the price.")
        return
    dec = 1.0
    ours = 1.0
    print("\n  WORTH TAKING -- one leg a game, so the card is the product of its legs")
    for l in pick:
        o = l["price"]
        dec *= (1 + o / 100.0) if o > 0 else (1 + 100.0 / -o)
        ours *= l["ours"]
        print("    %-9s %-20s %6s   we say %5.1f%%   %s"
              % (l["market"], (l["side"] or "")[:20],
                 ("+%d" % o) if o > 0 else o, l["ours"] * 100, l["game"]))
    a = round((dec - 1) * 100) if dec >= 2 else -round(100 / (dec - 1))
    print("    %d legs pays %s%d   |  our chance %.1f%%  |  fair %s"
          % (len(pick), "+" if a > 0 else "−", abs(a), ours * 100, price(ours)))
    if ours * dec > 1:
        print("    edge: %+.0f%% on every dollar through it" % ((ours * dec - 1) * 100))
    else:
        print("    the price does not pay for the chance -- take the legs singly")


if __name__ == "__main__":
    pid, rate, share = our_numbers()
    db = sqlite3.connect(DB)
    clubs = {}
    for written, abbr in db.cursor().execute("select written, abbr from club_name"):
        clubs[abbr.upper()] = None
    # club_name gives abbreviations; hub_team_split is keyed on the full name
    full = {}
    for club in share:
        full[club] = club
    for abbr in list(clubs):
        for club in share:
            if club.upper().replace(" ", "").endswith(abbr.upper()) or \
               abbr.upper() in club.upper().replace(" ", ""):
                clubs[abbr] = club
                break
    board = read_board()
    by = collections.defaultdict(list)
    for c in board:
        by[c["kick"]].append(c)
    want = None
    if "--window" in sys.argv:
        want = sys.argv[sys.argv.index("--window") + 1]
    now = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%MZ")
    for k in sorted(by):
        if want and want not in k:
            continue
        if "--all" not in sys.argv and not want and k < now:
            continue
        show(k, by[k], pid, rate, share, clubs)
    if not by:
        print("no NFL cards on the board")
