"""DraftKings' own number for each passer on the board, tied to ours.

   Every price DraftKings posts on a man carries his DraftKings id and which
   half of the fixture he is on:

       "participants": [{"id": "738142", "name": "Trinidad Chambliss (MISS)",
                         "venueRole": "AwayPlayer"}]

   The board reads the name instead, and in college that is how a running
   back's price landed on a quarterback's card -- a third of the anytime
   touchdown prices we held were shorter than -150, against one in
   seventy-two in the NFL (Jose, Sep 22, 2026: "why are we guessing name they
   wont fucking change").

   So the name is read once, here, under a rule that cannot pick the wrong
   man, and written down:

       DK 738142  ->  ESPN 4911529    Trinidad Chambliss

   The rule: the fixture is one we hold, the selection says which side he is
   on, that side of our card names exactly one passer, and the written name is
   his after the club tag is cut. Two candidates, the side already decided --
   there is nothing left to guess. Every run after that reads the number.

   A passer who is not pinned is not priced. That is the point: an unknown id
   draws nothing rather than the wrong man's price.

   Written to data/dk_people.json:

       {"738142": {"espn": "4911529", "name": "Trinidad Chambliss"}}

       python3 build/dk_people.py          both leagues, every drawn fixture
       python3 build/dk_people.py --dry    say what it would pin
"""
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from read_dk import ask

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "dk_people.json")
DRY = "--dry" in sys.argv
LEAGUE = {"nfl": 88808, "ncaaf": 87637}
# the categories a passer's prices live in
CATS = (1000, 1003, 1185)


def board():
    """Every drawn fixture, keyed by the two clubs, with the two passers and
       which side each is on."""
    s = open(os.path.join(D, "master.html")).read()
    out = {}
    for var, league in (("SCHED", "nfl"), ("CFB", "ncaaf")):
        m = re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S)
        if not m:
            continue
        for g in json.loads(m.group(1)):
            out[(league, g[3], g[4])] = {
                "league": league, "away": g[3], "home": g[4],
                "qb": [(g[5], str(g[6])), (g[7], str(g[8]))]}
    return out


def clubmap():
    """Every spelling of a club, to our own letters: the college file and the
       register, so DraftKings' "Ole Miss" and "Florida" find MISS and FLA."""
    out = {}
    f = os.path.join(D, "data", "cfb_names.json")
    if os.path.exists(f):
        out.update(json.load(open(f)))
    import sqlite3
    db = sqlite3.connect(os.path.join(D, "data", "qbspy.db"))
    for w, a in db.execute("select written, abbr from club_name"):
        out.setdefault(w, a)
    return out


def bare(written):
    """the name without DraftKings' club tag: "Arch Manning (TEX)" -> "Arch Manning" """
    return re.sub(r"\s*\([A-Za-z&.'\- ]+\)\s*$", "", written or "").strip()


def same(a, b):
    """the same man written two ways: case, stops, accents and a suffix."""
    def flat(x):
        x = (x or "").lower().replace(".", "").replace("'", "").replace("-", " ")
        x = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b", "", x)
        return " ".join(x.split())
    return flat(a) == flat(b) and bool(flat(a))


def dk_events(league):
    d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % LEAGUE[league]) or {}
    out = []
    for e in d.get("events") or []:
        names = [(p.get("name") or "") for p in (e.get("participants") or [])]
        out.append({"id": str(e.get("id")), "name": e.get("name") or "", "clubs": names})
    return out


def selections(eid):
    rows = []
    for c in CATS:
        d = ask(None, None, "/sportscontent/dkusmd/v1/events/%s/categories/%s" % (eid, c)) or {}
        for x in d.get("selections") or []:
            for p in (x.get("participants") or []):
                if (p.get("type") or "") != "Player":
                    continue
                rows.append({"dk": str(p.get("id") or ""),
                             "written": p.get("seoIdentifier") or bare(p.get("name")),
                             "role": p.get("venueRole") or ""})
    return rows


def main():
    have = {}
    if os.path.exists(OUT):
        try:
            have = json.load(open(OUT))
        except ValueError:
            have = {}
    before = len(have)

    games = board()
    # the fixture DraftKings is looking at, by the two clubs it writes
    by_clubs, jobs = {}, []
    for league in ("nfl", "ncaaf"):
        for e in dk_events(league):
            by_clubs[e["id"]] = e
            jobs.append((e["id"], league))

    clubs = clubmap()

    def work(job):
        eid, league = job
        e = by_clubs[eid]
        if len(e["clubs"]) != 2:
            return []
        # DraftKings names the home club first in participants, so the fixture
        # is found both ways round rather than assumed
        letters = [clubs.get(c) for c in e["clubs"]]
        if not all(letters):
            return []
        g = (games.get((league, letters[0], letters[1])) or
             games.get((league, letters[1], letters[0])))
        if not g:
            return []                      # a fixture we do not hold: nothing to pin
        found = []
        for r in selections(eid):
            if not r["dk"] or r["dk"] in have:
                continue
            side = 0 if r["role"] == "AwayPlayer" else 1 if r["role"] == "HomePlayer" else None
            if side is None:
                continue
            # this fixture, this side: exactly one passer can be meant
            name, pid = g["qb"][side]
            if not name or not pid:
                continue
            if same(bare(r["written"]), name):
                found.append((r["dk"], pid, name))
        return found

    with ThreadPoolExecutor(6) as ex:
        got = [x for sub in ex.map(work, jobs) for x in sub]
    seen = set()
    got = [x for x in got if not (x[0] in seen or seen.add(x[0]))]

    pinned = 0
    for dk, espn, name in got:
        if dk in have:
            continue
        have[dk] = {"espn": espn, "name": name}
        pinned += 1

    print("DraftKings ids pinned: %d new, %d held" % (pinned, len(have)))
    for dk, espn, name in got[:12]:
        print("   DK %-8s -> ESPN %-9s %s" % (dk, espn, name))
    if DRY:
        print("(dry run, nothing written)")
        return 0
    json.dump(have, open(OUT, "w"), indent=1, sort_keys=True)
    print("written to %s (%d -> %d)" % (OUT, before, len(have)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
