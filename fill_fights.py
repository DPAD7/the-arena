"""Prices for the fights, from DraftKings: UFC and the Contender Series.

   Every market the book puts on a bout is read and kept -- all five
   categories, 37 markets, some three hundred selections a fight -- and the
   whole lot is written to ufc_markets.json. The sheet on the site draws only
   the ones it is programmed for; the rest sit in the file until it is
   (Jose, Sep 18, 2026).

   What the board reads:
     the card    moneyline, into the FIGHTS row (fields 8-11)
     the sheet   FPROPS, one entry a bout, the keys below

   How many rounds a bout goes is not stated anywhere. It is read off what
   DraftKings offers -- a three-round bout has no Round 4 -- and kept as
   "rounds", so a three-round fight is not drawn with two rows nobody can
   take.

   Usage:  python3 fill_fights.py          (writes and deploys)
           python3 fill_fights.py --dry
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, "/Users/joe/qbspy/build")
import pagefile
import prices as pricefile
from read_dk import ask

D = os.path.dirname(os.path.abspath(__file__))
DRY = "--dry" in sys.argv
NOW = dt.datetime.now(dt.timezone.utc)
HORIZON = NOW + dt.timedelta(days=8)
LEAGUES = {"ufc": 9034, "dwcs": 187059}
# the five that answer for a bout; anything outside them came back empty
CATS = (491, 556, 558, 677, 726)
ARCHIVE = D + "/ufc_markets.json"


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


# how DraftKings writes a man when the board writes him another way
FN_PATH = D + "/fighter_names.json"
FN = json.load(open(FN_PATH)) if os.path.exists(FN_PATH) else {}


def ours(text):
    """DraftKings' spelling of any man in the text, rewritten as the board's."""
    for theirs, mine in FN.items():
        text = text.replace(theirs, mine)
    return text


def pull(eid):
    """Every market on the bout: {market name: {selection label: [odds, id]}}."""
    out = {}
    for cat in CATS:
        d = ask(None, None, "/sportscontent/dkusmd/v1/events/%s/categories/%d" % (eid, cat)) or {}
        mk = {m["id"]: ours((m.get("name") or "").strip()) for m in d.get("markets") or []}
        for sel in d.get("selections") or []:
            name = mk.get(sel.get("marketId"))
            if not name:
                continue
            odds = ((sel.get("displayOdds") or {}).get("american") or "").replace("−", "-")
            out.setdefault(name, {})[ours((sel.get("label") or "").strip())] = [odds, sel.get("id") or ""]
    return out


def dk_bouts():
    """{(man, man): (event id, when it starts)} -- the start is theirs, not
       ours: our rows carry a block time for a whole prelim card, and the book
       moves each bout as the card runs. A string of knockouts pulls the main
       event forward by an hour and their clock follows it (Jose, Sep 18,
       2026)."""
    out = {}
    for lg in LEAGUES.values():
        d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % lg) or {}
        for e in d.get("events") or []:
            name = e.get("name") or ""
            if " vs " not in name:
                continue
            a, b = [ours(x.strip()) for x in name.split(" vs ", 1)]
            when = (e.get("startEventDate") or "")[:16]
            when = (when + "Z") if when else ""
            out[(a, b)] = (str(e["id"]), when)
            out[(b, a)] = (str(e["id"]), when)
    return out


def rounds_of(mkts):
    """How far the bout can go, read off the rounds the book prices."""
    top = 3
    for lab in (mkts.get("Winning Round") or {}):
        m = re.match(r"Round (\d)$", lab)
        if m:
            top = max(top, int(m.group(1)))
    for n in (4, 5):
        if "Fight to Start Round %d" % n in mkts:
            top = max(top, n)
    return top


def one(mkts, market, label):
    """One selection, or None -- the book does not price every one."""
    got = (mkts.get(market) or {}).get(label)
    return list(got) if got and got[0] else None


def sheet(mkts, left, right, nr):
    """The sheet's own keys, both men where a market has two sides."""
    e = {}

    def two(key, market, lab):
        e[key] = [one(mkts, market(m) if callable(market) else market, lab(m)) for m in (left, right)]

    def fight(key, market, label):
        e[key] = [one(mkts, market, label)]

    # how he wins
    two("ko", "KO/TKO/DQ", lambda m: m)
    two("sub", "Submission", lambda m: m)
    two("dec", "Decision", lambda m: m)
    two("koonly", "KO/TKO/DQ Only Moneyline (If Decision or Submission No Action)", lambda m: m)
    two("subonly", "Submission Only Moneyline (If Decision or KO/TKO/DQ No Action)", lambda m: m)
    two("deconly", "Decision Only Moneyline (If Finish No Action)", lambda m: m)
    two("finishonly", "Finish Only Moneyline (If Decision No Action)", lambda m: m)
    two("rd1only", "Round 1 Only Moneyline (Any Other Result No Action)", lambda m: m)
    two("ud", lambda m: m + " to Win by Unanimous Decision", lambda m: "Yes")
    two("sdmd", lambda m: m + " to Win by Split or Majority Decision", lambda m: "Yes")
    two("kosub", lambda m: m + " to Win by Any Knockout, Submission or DQ", lambda m: "Yes")
    e["finish"] = e["kosub"]
    two("kodec", "Method of Victory Double Chance", lambda m: m + " to Win by KO/TKO/DQ or Decision")
    two("subdec", "Method of Victory Double Chance", lambda m: m + " to Win by Submission or Decision")
    for i, m in enumerate((left, right)):
        if not e["kosub"][i]:
            e["kosub"][i] = e["finish"][i] = one(mkts, "Method of Victory Double Chance",
                                                 m + " to Win by KO/TKO/DQ or Submission")
    # when he wins
    two("cards", "Round Betting", lambda m: m + " By Decision")
    for n in range(1, nr + 1):
        two("rd%d" % n, "Round Betting", lambda m, n=n: "%s Round %d" % (m, n))
        two("kord%d" % n, "Round and Method Betting",
            lambda m, n=n: "%s to Win by KO/TKO/DQ in Round %d" % (m, n))
        two("subrd%d" % n, "Round and Method Betting",
            lambda m, n=n: "%s to Win by Submission in Round %d" % (m, n))
        # the book writes the round and the method with two different dashes
        e["anykord%d" % n] = [one(mkts, "Winning Round and Method", "Round %d - KO/TKO/DQ" % n)]
        e["anysubrd%d" % n] = [one(mkts, "Winning Round and Method", "Round %d – Submission" % n) or
                               one(mkts, "Winning Round and Method", "Round %d - Submission" % n)]
    two("rd12", "Alternate Round Betting", lambda m: m + " to Win in Rounds 1-2")
    if nr == 5:
        two("rd34", "Alternate Round Betting", lambda m: m + " to Win in Rounds 3-4")
    two("rdlastdec", "Alternate Round Betting",
        lambda m: "%s to Win in Round %d or on Decision" % (m, nr))
    # the fight's own
    fight("anyko", "Exact Method of Victory", "KO/TKO/DQ")
    fight("anysub", "Exact Method of Victory", "Submission")
    fight("anydec", "Exact Method of Victory", "Decision")
    fight("dist", "Fight to Go the Distance", "Yes")
    fight("nodist", "Fight to Go the Distance", "No")
    fight("anyud", "Fight to Be Won by Unanimous Decision", "Yes")
    fight("anysdmd", "Fight to Be Won by Split or Majority Decision", "Yes")
    fight("first60", "Fight to End in the 1st 60 Seconds of Round 1", "Yes")
    fight("last10", "Fight to End in the Last 10 Seconds of Any Round", "Yes")
    e["rounds"] = nr
    return e


def main():
    s = pagefile.read()
    m = re.search(r"var FIGHTS = (\[\[.*?\]\]);", s, re.S)
    fights = json.loads(m.group(1))
    due = [f for f in fights if NOW < T(f[2]) <= HORIZON]
    bouts = dk_bouts()
    print("fights to start: %d | DraftKings bouts: %d" % (len(due), len(bouts) // 2))
    archive = json.load(open(ARCHIVE)) if os.path.exists(ARCHIVE) else {}
    fp, kicks = {}, {}
    for f in due:
        left, right = f[3], f[5]
        eid, when = bouts.get((left, right)) or (None, "")
        if not eid:
            print("  %-22s v %-22s not on DraftKings by these names" % (left, right))
            continue
        mkts = pull(eid)
        if not mkts:
            print("  %-22s v %-22s nothing came back" % (left, right))
            continue
        for lab, got in (mkts.get("Moneyline") or {}).items():
            if lab == left:
                f[8], f[9] = got
            elif lab == right:
                f[10], f[11] = got
        if when and when != f[2]:
            # logged, never quietly swapped: the row keeps ESPN's time and the
            # board reads the book's out of prices.json (Jose, Sep 18, 2026)
            print("      starts %s on our row, %s on their board" % (f[2][11:16], when[11:16]))
            kicks[str(f[1])] = when
        nr = rounds_of(mkts)
        e = sheet(mkts, left, right, nr)
        fp[f[1]] = e
        archive[str(f[1])] = {"dk": eid, "left": left, "right": right, "rounds": nr, "start": when,
                              "read": NOW.strftime("%Y-%m-%dT%H:%MZ"), "markets": mkts}
        held = sum(1 for k, v in e.items() if k != "rounds" for x in v if x)
        want = sum(1 for k, v in e.items() if k != "rounds" for x in v)
        print("  %-22s v %-22s dk %s  %dr  ML %s/%s  sheet %d/%d  markets %d" %
              (left, right, eid, nr, f[8], f[10], held, want, len(mkts)))
    if DRY:
        print("dry run -- nothing written")
        return
    json.dump(archive, open(ARCHIVE, "w"), indent=1)
    print("ufc_markets.json: %d bouts, every market the book offered" % len(archive))
    # the bouts' prices go to site/prices.json, never into the page: a price
    # that moves must not mean rewriting the page (Jose, Sep 18, 2026)
    book = pricefile.read()
    for f in fights:
        if len(f) > 11 and (f[8] or f[10]):
            book["FIGHTS"][str(f[1])] = [f[8], f[9], f[10], f[11]]
    book["FPROPS"].update(fp)
    book.setdefault("KICKS", {}).update(kicks)
    pricefile.write(book)
    print("written: %d bouts in FPROPS, %d starts in KICKS, prices.json only -- the page is untouched"
          % (len(book["FPROPS"]), len(book.get("KICKS") or {})))
    subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=sports-odds", "--branch=main"],
                   cwd=D + "/site", capture_output=True, text=True)
    print("deployed")


if __name__ == "__main__":
    main()
