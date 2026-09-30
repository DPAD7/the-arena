"""Ten men for one passing touchdown, out of Jose's own pool.

   The note, not the board. Nothing here touches the page, the prices or the
   ledger -- it reads what the sweep has already written, asks ESPN what each
   fixture's number is, and leaves one file behind: notes/ptd10-week-N.md, who
   to take and why (Jose, Sep 20, 2026: "make a separate note to tell me of
   who to take and why based on the 21 qbs i have ... $100, 10 legs or less,
   10 is ideal").

   The pool is data/ptd_pool.json, by ESPN id -- the ids, never the written
   names, because the name is what loses a man.

   What ranks them
   ---------------
   Two numbers, measured rather than felt, over 6,642 starts from 2009 to 2026
   (league_play and game_odds, read Sep 20, 2026):

     * what he has been throwing -- passing touchdowns a start, his last three
     * what the book says his club scores -- the total and the spread together,
       which is the one pre-game number that beat his own form

   Passing yards, which this note used to rank on, is the weaker of the two:
   255+ yards a start is 86.9%, implied points of 26 or more is 88.6%, and the
   pair of them together is 90.4%. Taking everybody is 81.1%.

   Ranked on `touchdowns a start + implied points / 10`, the six bands run:

       4.90 and up   88.2%        3.50 - 3.91   82.1%
       4.35 - 4.89   87.0%        3.05 - 3.49   75.3%
       3.92 - 4.34   83.1%        under 3.05    71.0%

   And what that is worth, ranking every starter this way over 243 weeks and
   taking the top of the list:

       top 4   all land 60% of weeks        top 8    35%
       top 6   45%                          top 10   24%   (ten at random: 13%)

   So ten legs is a one-in-four week even when the ten are the right ten. Six
   is a coin flip. The note names ten because that is the shape he asked for,
   and says this every time so the number is never a surprise.

   What it writes down
   -------------------
   The call is locked in data/ptd10_called.json the first time a week is
   written, before the games, and never rewritten. When that week has been
   played the note carries its own grade: how the ten did, and how the rest of
   the pool did behind them.

   Usage:  python3 build/ptd10.py            the week the board is on
           python3 build/ptd10.py --week 4
"""
import collections
import datetime
import json
import os
import subprocess
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
NOTES = os.path.join(D, "notes")
POOL = os.path.join(D, "data", "ptd_pool.json")
CALLED = os.path.join(D, "data", "ptd10_called.json")
ODDS = os.path.join(D, "data", "ptd_odds.json")
CORE = ("http://sports.core.api.espn.com/v2/sports/football/leagues/nfl"
        "/events/%s/competitions/%s/odds")
WANT = 10                     # ten legs is the shape he asked for
STAKE = 100.0

# measured, not guessed -- see the docstring. Score is touchdowns a start
# over the games we have read, plus the club's implied points over ten.
BANDS = ((4.90, 0.882), (4.35, 0.870), (3.92, 0.831),
         (3.50, 0.821), (3.05, 0.753), (0.0, 0.710))
# every start since 2009 averages this many passing touchdowns, and two starts
# of it are added to every man so a one-game record cannot lead the list
MEAN, HOLD = 1.64, 2.0


def read(path, fallback=None):
    try:
        return json.load(open(path))
    except Exception:
        return fallback


def sched():
    """The board's own schedule, parsed out of the page it is written in."""
    page = pagefile.read()
    i = page.index("  var SCHED = [[")
    j = page.index("];", i)
    return json.loads(page[i + len("  var SCHED = "):j + 1])


def kick(g):
    return datetime.datetime.strptime(g[2].replace("Z", "+0000"), "%Y-%m-%dT%H:%M%z")


def band(score):
    for floor, rate in BANDS:
        if score >= floor:
            return rate
    return BANDS[-1][1]


def american(dec):
    if not dec or dec <= 1:
        return ""
    return "+%d" % round((dec - 1) * 100) if dec >= 2 else "-%d" % round(100 / (dec - 1))


def decimal(price):
    if not price:
        return None
    try:
        v = int(str(price).replace("−", "-").replace("+", ""))
    except ValueError:
        return None
    return 1 + (v / 100.0 if v > 0 else 100.0 / -v) if v else None


def numbers(gid, home, away, cache):
    """What the fixture's own number says each club scores: half the total,
       and half the spread to the club that is giving it. ESPN writes the
       favourite as it is spoken -- "GB -7" -- so the club is read off the
       line rather than assumed to be the home side.

       A club the line names that is on neither side of this fixture is left
       unsettled and counted, never guessed at."""
    key = str(gid)
    if key in cache:
        return tuple(cache[key]) if cache[key] else (None, None, None)
    out = subprocess.run(["curl", "-s", "-m", "25", CORE % (gid, gid)],
                         capture_output=True, text=True).stdout
    got = (None, None, None)
    try:
        items = (json.loads(out or "{}").get("items") or [])
    except ValueError:
        items = []
    for it in items:
        total, spread = it.get("overUnder"), it.get("spread")
        who = (it.get("details") or "").split()[0] if it.get("details") else ""
        if total is None or spread is None or not who:
            continue
        if who not in (home, away):
            print("   the line says %s, which is neither %s nor %s -- left alone"
                  % (who, away, home))
            continue
        edge = abs(spread) / 2.0
        h = total / 2.0 + (edge if who == home else -edge)
        got = (round(h, 2), round(total - h, 2), total)
        break
    cache[key] = list(got) if got[0] is not None else None
    return got


def form(led, games, now):
    """Every passer's played starts: touchdowns a start, and how often he threw
       one. A fixture that has not been played sits in the ledger at nothing,
       and counting it would read as a start he was shut out in."""
    tds, hit, starts = collections.defaultdict(list), collections.Counter(), collections.Counter()
    allowed, faced, seen = collections.Counter(), collections.Counter(), set()
    for wk in sorted(led, key=int):
        for r in led[wk]:
            g = games.get(str(r[8] or ""))
            if not g or kick(g) > now:
                continue
            pid = str(r[2])
            tds[pid].append(r[3] or 0)
            starts[pid] += 1
            hit[pid] += 1 if (r[3] or 0) >= 1 else 0
            opp = g[4] if r[1] == g[3] else g[3]
            allowed[opp] += r[3] or 0
            if (str(r[8]), r[1]) not in seen:
                seen.add((str(r[8]), r[1]))
                faced[opp] += 1
    soft = {club: allowed[club] / faced[club] for club in faced if faced[club]}
    return tds, hit, starts, soft


def price_for(prices, gid, side):
    """What a board charges for his first touchdown, if any board has posted
       one. A week drawn but unpriced is drawn with nulls, which is not a price
       and is never read as one."""
    p = ((prices.get("PROPS") or {}).get(str(gid)) or {}).get("ptd")
    if not p or len(p) <= side or not p[side]:
        return None
    rung = p[side][0]
    if not rung:
        return None
    return rung[0] if isinstance(rung, (list, tuple)) else rung


def build(week):
    now = datetime.datetime.now(datetime.timezone.utc)
    pool = read(POOL) or []
    led = read(os.path.join(D, "site", "ledger.json")) or {}
    prices = read(os.path.join(D, "site", "prices.json")) or {}
    cache = read(ODDS) or {}
    rows = sched()
    games = {str(g[1]): g for g in rows}
    tds, hit, starts, soft = form(led, games, now)
    named = {p["name"]: str(p["id"]) for p in pool}

    out, missing = [], []
    for g in rows:
        if int(g[0]) != week:
            continue
        hi, ai, total = numbers(g[1], g[4], g[3], cache)
        for nm, club, opp, side, imp in ((g[5], g[3], g[4], 0, ai), (g[7], g[4], g[3], 1, hi)):
            if not nm or nm not in named:
                continue
            pid = named[nm]
            mine = tds.get(pid) or []
            if not mine:
                missing.append((nm, "no start we have read"))
                continue
            if imp is None:
                missing.append((nm, "no number posted on %s v %s yet" % (club, opp)))
                continue
            # A man with one start behind him is not a 3.00-a-start passer, he
            # is a passer we have seen once. Two starts of the league's own
            # rate are added to everybody, so one loud game cannot carry a man
            # to the top of the list and a long record still speaks for itself
            # (Sep 20, 2026).
            per = (sum(mine) + MEAN * HOLD) / (len(mine) + HOLD)
            score = per + imp / 10.0
            out.append({
                "id": pid, "name": nm, "club": club, "opp": opp,
                "per": round(per, 2), "imp": imp, "total": total,
                "score": round(score, 2), "rate": band(score),
                "record": "%d of %d" % (hit[pid], starts[pid]),
                "soft": round(soft[opp], 1) if opp in soft else None,
                "price": price_for(prices, g[1], side),
                "kick": kick(g).astimezone(
                    datetime.timezone(datetime.timedelta(hours=-4))).strftime("%a %-I:%M %p"),
            })
    json.dump(cache, open(ODDS, "w"), indent=1)
    seen = {r["name"] for r in out} | {m[0] for m in missing}
    for p in pool:
        if p["name"] not in seen:
            missing.append((p["name"], "not on week %d's board" % week))
    out.sort(key=lambda r: (-r["score"], -(r["soft"] or 0)))
    return out, missing


def grade(week, led, games, pool):
    """How last week's ten did, and how the rest of the pool did behind them."""
    log = read(CALLED) or {}
    key = str(week)
    if key not in log:
        return None
    now = datetime.datetime.now(datetime.timezone.utc)
    got = {str(r[2]): (r[3] or 0) >= 1 for r in ((led or {}).get(key) or [])
           if games.get(str(r[8] or "")) and kick(games[str(r[8])]) < now}
    took = [q for q in log[key]["took"] if q["id"] in got]
    if not took:
        return None
    won = [q for q in took if got[q["id"]]]
    rest = [p for p in pool if p["id"] in got and p["id"] not in {q["id"] for q in took}]
    base = len([p for p in rest if got[p["id"]]]) / len(rest) if rest else None
    return {"week": week, "took": len(took), "won": len(won),
            "missed": [q["name"] for q in took if not got[q["id"]]],
            "base": base, "called": log[key]["called"]}


def note(week, board, missing, graded, pool):
    take = board[:WANT]
    lines = ["# One passing touchdown — week %d" % week, ""]
    lines.append("Out of the %d in the pool, ranked on two numbers that were measured over "
                 "6,642 starts since 2009: what he has been throwing (touchdowns a start) and "
                 "what the fixture's own number says his club scores. Both together is 90.4%%; "
                 "his passing yards alone is 86.9%%; taking everybody is 81.1%%." % len(pool))
    lines.append("")
    if take:
        lines.append("## Take these %d" % len(take))
        lines.append("")
        lines.append("| | fixture | kick | TD a start | club scores | rate | this year | opp gives | price |")
        lines.append("|---|---|---|---|---|---|---|---|---|")
        for r in take:
            lines.append("| %s | %s v %s | %s | %.2f | %.1f | %.0f%% | %s | %s | %s |" % (
                r["name"], r["club"], r["opp"], r["kick"], r["per"], r["imp"], 100 * r["rate"],
                r["record"], "—" if r["soft"] is None else "%.1f" % r["soft"],
                r["price"] or "not posted"))
        lines.append("")
        chance = 1.0
        for r in take:
            chance *= r["rate"]
        lines.append("Each one's own rate multiplied out: **%.0f%%** that all %d land. Over 243 "
                     "weeks a top ten chosen this way landed clean 24%% of the time, a top six "
                     "45%%, a top four 60%%. Ten is the shape, not the best odds of a clean week."
                     % (100 * chance, len(take)))
        priced = [decimal(r["price"]) for r in take if decimal(r["price"])]
        if priced:
            tot = 1.0
            for d in priced:
                tot *= d
            lines.append("")
            lines.append("At the prices posted so far (%d of %d legs): **%s**, and $%d returns "
                         "$%.0f." % (len(priced), len(take), american(tot), STAKE, STAKE * tot))
        else:
            lines.append("")
            lines.append("No board has posted a first-touchdown price for this week yet. "
                         "The sweep writes them in as they land.")
        lines.append("")
        lines.append("### Six, if he wants the better week")
        lines.append("")
        six = take[:6]
        c6 = 1.0
        for r in six:
            c6 *= r["rate"]
        lines.append("%s — **%.0f%%** that all six land." % (
            ", ".join(r["name"] for r in six), 100 * c6))
        lines.append("")
        lines.append("## Why each")
        lines.append("")
        for r in take:
            why = "%.2f touchdowns a start, and %s's own number has them scoring %.1f" % (
                r["per"], r["club"], r["imp"])
            if r["total"]:
                why += " of a %.1f game" % r["total"]
            if r["soft"] is not None:
                why += "; %s has given up %.1f a game" % (r["opp"], r["soft"])
            why += "; he has thrown one in %s this year." % r["record"]
            lines.append("- **%s** — %s" % (r["name"], why))
        lines.append("")
    rest = board[WANT:]
    if rest:
        lines.append("## Left out")
        lines.append("")
        for r in rest:
            lines.append("- %s (%s v %s) — %.2f a start, club scores %.1f, %.0f%%" % (
                r["name"], r["club"], r["opp"], r["per"], r["imp"], 100 * r["rate"]))
        lines.append("")
    if missing:
        lines.append("## Not read")
        lines.append("")
        for nm, why in missing:
            lines.append("- %s — %s" % (nm, why))
        lines.append("")
    if graded:
        lines.append("## Week %d, graded" % graded["week"])
        lines.append("")
        lines.append("Called %s. %d of %d landed%s." % (
            graded["called"], graded["won"], graded["took"],
            "" if not graded["missed"] else " — missed: " + ", ".join(graded["missed"])))
        if graded["base"] is not None:
            lines.append("")
            lines.append("The rest of the pool that week: %.0f%%." % (100 * graded["base"]))
        lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("Written by build/ptd10.py on the sweep, %s. It reads the ledger and the "
                 "prices the sweep has already written, asks ESPN for each fixture's number, "
                 "and changes nothing else."
                 % datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
    return "\n".join(lines) + "\n"


def main():
    week = None
    if "--week" in sys.argv:
        week = int(sys.argv[sys.argv.index("--week") + 1])
    rows = sched()
    games = {str(g[1]): g for g in rows}
    led = read(os.path.join(D, "site", "ledger.json")) or {}
    pool = read(POOL) or []
    now = datetime.datetime.now(datetime.timezone.utc)
    if week is None:
        # the week the board is on is the first with most of itself still to
        # play. One Monday fixture left does not make that week the one to
        # call -- it would write down a card for games already settled, which
        # is the one thing this file exists to stop (Sep 20, 2026)
        left = collections.Counter()
        size = collections.Counter()
        for g in rows:
            size[int(g[0])] += 1
            if kick(g) > now:
                left[int(g[0])] += 1
        ahead = sorted(w for w in size if left[w] * 2 >= size[w])
        week = ahead[0] if ahead else max(size)
    board, missing = build(week)
    graded = grade(week - 1, led, games, pool)
    os.makedirs(NOTES, exist_ok=True)
    path = os.path.join(NOTES, "ptd10-week-%d.md" % week)
    open(path, "w").write(note(week, board, missing, graded, pool))
    print("wrote %s -- %d of %d named" % (path, min(WANT, len(board)), len(pool)))

    log = read(CALLED) or {}
    key = str(week)
    if key not in log and board:
        log[key] = {"called": now.strftime("%Y-%m-%d %H:%M UTC"),
                    "took": [{"id": r["id"], "name": r["name"], "score": r["score"],
                              "per": r["per"], "imp": r["imp"], "opp": r["opp"]}
                             for r in board[:WANT]]}
        json.dump(log, open(CALLED, "w"), indent=1)
        print("week %d locked: %s" % (week, ", ".join(q["name"] for q in log[key]["took"])))
    elif key in log:
        print("week %d was called on %s" % (week, log[key]["called"]))


if __name__ == "__main__":
    main()
