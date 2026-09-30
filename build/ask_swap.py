"""A double tap puts the college passer DraftKings prices on his card.

   The tap (.github/workflows/ask.yml) reads the day's games for the prices
   the cards are missing. A college card can hold last week's man while the
   book prices somebody else -- Tulsa kept Dexter Williams II with no prices
   while DraftKings priced Baylor Hayes -- and the tap only ever asked about
   the man on the card. This runs in the tap's save job: for each college game
   tapped, the one passer DraftKings prices for a side, when he is not the
   card's, goes on the card, his prices are read, the page is deployed and
   his phone is told there and then (Jose, Sep 30, 2026: "as soon as it
   checks that the odds say Corey Lester and it's Michael Page it should
   switch and then give me the odds for that when I double tap the icon").

   Usage:  python3 build/ask_swap.py --games 401862786,401862799 [--dry]
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile
import prices as pricefile
import fill_week

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
NOW = dt.datetime.now(dt.timezone.utc)


def arg(name):
    if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(name) + 1]
    return ""


def tell(key, title, body):
    try:
        import triage
        triage.alert(key, title, body)
    except Exception as e:
        print("alert not sent (%s)" % type(e).__name__)


def main():
    asked = [x.strip() for x in arg("--games").split(",") if x.strip()]
    page = pagefile.read()
    m = re.search(r"  var CFB = (\[\[.*?\]\]);\n", page, re.S)
    cfb = json.loads(m.group(1)) if m else []
    rows = [g for g in cfb if str(g[1]) in asked
            and fill_week.T(g[2]) > NOW
            and not os.path.exists(os.path.join(D, "site", "final", "%s.json" % g[1]))]
    if not rows:
        print("ask_swap: no college game to kick among the tapped")
        return
    reg = os.path.join(D, "data", "register.db")
    if os.path.exists(reg) and not os.path.exists(fill_week.DB):
        fill_week.DB = reg
    club, _person = fill_week.register()
    dkp = os.path.join(D, "data", "dk_people.json")
    dkpeople = json.load(open(dkp)) if os.path.exists(dkp) else {}
    names = json.load(open(D + "/data/cfb_names.json"))
    events = fill_week.dk_events("ncaaf")
    keyed = fill_week.tie_events("ncaaf", events, club, names)
    book = pricefile.read()
    qf = os.path.join(D, "data", "dk_qbs.json")
    try:
        dkq_all = json.load(open(qf))
    except (OSError, ValueError):
        dkq_all = {}
    swaps = []
    for g in rows:
        gid = str(g[1])
        e, how = fill_week.event_for(g, "ncaaf", keyed, events, club, names, loose=False)
        if not e:
            continue
        ml, entry = fill_week.price_event(e, [g[6], g[8]], "ncaaf", dkpeople, [g[5], g[7]])
        dkq = [[], []]
        for role, men in (entry.pop("_qb", {}) or {}).items():
            side = 0 if role == "away" else 1
            if how == "flipped":
                side = 1 - side
            for pid, nm in men.items():
                espn = (dkpeople.get(pid) or {}).get("espn") or ""
                dkq[side].append([str(espn), nm])
        dkq_all[gid] = dkq
        moved = []
        for side in (0, 1):
            priced = [x for x in dkq[side] if x[0]]
            if len(priced) == 1 and priced[0][0] != str(g[6 + side * 2]):
                was = g[5 + side * 2]
                g[5 + side * 2], g[6 + side * 2] = priced[0][1], priced[0][0]
                moved.append((g[3 + side], was, priced[0][1]))
        if not moved:
            continue
        # the card's new man, read for his prices
        ml, entry = fill_week.price_event(e, [g[6], g[8]], "ncaaf", dkpeople, [g[5], g[7]])
        entry.pop("_qb", None)
        book["PROPS"][gid] = entry
        if ml:
            row = list(book["CFB"].get(gid) or ["", "", "", ""])
            for i, (price, oid) in ml.items():
                row[i * 2], row[i * 2 + 1] = price, oid
            book["CFB"][gid] = row
        for team, was, now in moved:
            swaps.append((team, was, now))
            print("ask_swap: %s %s -> %s (DraftKings)" % (team, was, now))
    if not swaps:
        print("ask_swap: every tapped college card holds the passer DraftKings prices")
        return
    if DRY:
        print("dry run -- nothing written")
        return
    page = page[:m.start()] + "  var CFB = %s;\n" % json.dumps(cfb, separators=(",", ":")) + page[m.end():]
    pagefile.write(page)
    pricefile.write(book)
    json.dump(dkq_all, open(qf, "w"))
    if fill_week.NEWPINS:
        allp = json.load(open(dkp)) if os.path.exists(dkp) else {}
        allp.update(fill_week.NEWPINS)
        json.dump(allp, open(dkp, "w"), indent=1, sort_keys=True)
    # the game page's cases are the new man's before the deploy
    subprocess.run([sys.executable, os.path.join(D, "build", "suggest.py")], cwd=D)
    pagefile.deployable(pagefile.read())
    subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=the-arenasports", "--branch=main"],
                   cwd=D + "/site", capture_output=True, text=True)
    print("deployed")
    for team, was, now in swaps:
        tell("swap@%s@%s" % (team, now), "%s: %s starts" % (team, now),
             "DraftKings prices %s, not %s -- the card has him and his odds now." % (now, was))


if __name__ == "__main__":
    main()
