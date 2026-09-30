"""DraftKings' number for a passer, taken before anyone prices him.

   dk_people.py reads the id off a posted price, so a man is only pinned once
   DraftKings has put a market up on him. Five days out from week three that
   left twenty-four of thirty-two starters unknown, Mahomes among them -- his
   fixture had four selections on it and none of them his (Jose, Sep 22, 2026,
   handing over his own page: ".../patrick-mahomes-odds-11644").

   The id is not hidden. DraftKings publishes every player page it has in a
   sitemap, and writes the id on the end of each address:

       /players/football/nfl/patrick-mahomes-odds-11644

   Fourteen thousand of them, league in the path, no session and no login. So
   a man can be pinned the day his club is drawn rather than the night he is
   priced.

   The rule, because this is the one place a name is read: the league must
   match, and the written name must find **exactly one** page. Two K.J. and
   C.J. Strouds sit in that file; a name that finds both is left alone for
   dk_people.py, which can see which side of which fixture he is on.

   College is not in the sitemap -- only NFL, NHL, MLB and NBA -- so college
   passers still come the other way.

       python3 build/dk_sitemap.py          pin every drawn NFL passer
       python3 build/dk_sitemap.py --dry    say who it would pin
"""
import collections
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
OUT = os.path.join(D, "data", "dk_people.json")
DRY = "--dry" in sys.argv
MAP = "https://sportsbook.draftkings.com/sitemaps/SportsbookPlayerUriProvider_0.xml"


def pages():
    """every NFL player page DraftKings publishes, by its slug."""
    r = rq.get(MAP, impersonate="chrome", timeout=90)
    r.raise_for_status()
    by = collections.defaultdict(list)
    for slug, pid in re.findall(
            r"/players/football/nfl/([a-z0-9\.\-']+)-odds-(\d+)", r.text):
        by[slug].append(pid)
    return by


def slug(name):
    """the name as DraftKings writes it in an address: lower case, stops kept
       (c.j.-stroud), spaces to dashes."""
    n = (name or "").lower().replace("'", "")
    n = re.sub(r"[^a-z0-9\.]+", "-", n)
    return n.strip("-")


def drawn():
    """every NFL passer on the board and every one on a club's depth chart,
       name to ESPN id: a backup is pinned before the week he starts, not
       after -- Mariota's prices sat under Daniels's face for want of it
       (Jose, Sep 29, 2026: "we should get IDs for all ESPN quarterbacks and
       IDs for all DraftKings quarterbacks")"""
    s = pagefile.read()
    m = re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S)
    out = {}
    for g in json.loads(m.group(1)) if m else []:
        for name, pid in ((g[5], g[6]), (g[7], g[8])):
            if name and pid:
                out[name] = str(pid)
    try:
        depth = json.load(open(os.path.join(D, "site", "depth.json")))
    except (OSError, ValueError):
        depth = {}
    for room in depth.values():
        for q in room.get("qbs") or []:
            if q.get("name") and q.get("id"):
                out.setdefault(q["name"], str(q["id"]))
    return out


def main():
    have = {}
    if os.path.exists(OUT):
        try:
            have = json.load(open(OUT))
        except ValueError:
            have = {}
    before = len(have)
    known = {v.get("espn") for v in have.values()}

    by = pages()
    print("NFL player pages DraftKings publishes: %d" % len(by))

    pinned, several, absent = [], [], []
    for name, espn in sorted(drawn().items()):
        if espn in known:
            continue
        found = by.get(slug(name)) or by.get(slug(re.sub(r"\s+(jr\.?|sr\.?|ii|iii|iv|v)$", "", name, flags=re.I))) or []
        if len(found) == 1:
            have[found[0]] = {"espn": espn, "name": name}
            known.add(espn)
            pinned.append((found[0], espn, name))
        elif found:
            several.append(name)
        else:
            absent.append(name)

    print("pinned from the sitemap: %d" % len(pinned))
    for dk, espn, name in pinned[:12]:
        print("   DK %-8s -> ESPN %-9s %s" % (dk, espn, name))
    if several:
        print("more than one page, left for dk_people.py: %s" % ", ".join(several))
    if absent:
        print("no page: %s" % ", ".join(absent))
    if DRY:
        print("(dry run, nothing written)")
        return 0
    json.dump(have, open(OUT, "w"), indent=1, sort_keys=True)
    print("written to %s (%d -> %d)" % (OUT, before, len(have)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
