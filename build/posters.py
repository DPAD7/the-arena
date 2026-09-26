"""The poster for every fight card, from Wikipedia, for the UFC page's carousel.

   ESPN and theScore carry no event art -- headshots and flags only -- and
   Wikipedia keeps the official poster in each event's infobox (Jose, Sep 25,
   2026: "lets make it a carousel on the ufc page so each one would get one").
   The poster is a fair-use file on the English wiki, so the page-image API
   never returns it; it is read out of the infobox itself.

   A numbered event is its number ("UFC 332"); every other card is its full
   name. A card with no poster yet -- the Contender Series weeks, cards not
   announced in art -- is asked about again on the next run, and the page
   draws its own tile in the meantime.

   Each poster is kept in site/img/posters/<espn id>.jpg and listed in
   site/posters.json, so the page never reaches Wikipedia itself.

       python3 build/posters.py          fetch what is missing
       python3 build/posters.py --dry    say what it would fetch
"""
import json
import os
import re
import sys

from curl_cffi import requests as rq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
OUT = os.path.join(D, "site", "img", "posters")
LIST = os.path.join(D, "site", "posters.json")
UA = {"User-Agent": "the-arena/1.0 (185117539+DPAD7@users.noreply.github.com)"}
API = "https://en.wikipedia.org/w/api.php"


def title_of(name):
    m = re.match(r"(UFC \d+)\b", name)
    return m.group(1) if m else name


def poster_url(title):
    """The first English-wiki image in the article's lead: the infobox poster."""
    try:
        j = rq.get(API, params={"action": "parse", "page": title, "prop": "text", "section": 0,
                                "format": "json", "redirects": 1}, headers=UA, timeout=30).json()
    except Exception:
        return None
    t = ((j.get("parse") or {}).get("text") or {}).get("*", "")
    m = re.search(r'upload\.wikimedia\.org/wikipedia/en/[^"\s?]+\.(?:jpg|jpeg|png)', t)
    return "https://" + m.group(0) if m else None


def main():
    s = pagefile.read()
    cards = json.loads(re.search(r"  var FIGHTCARDS = (\[\[.*?\]\]);", s, re.S).group(1))
    try:
        have = json.load(open(LIST))
    except (OSError, ValueError):
        have = {}
    os.makedirs(OUT, exist_ok=True)
    got, missing = [], []
    for c in cards:
        eid, name = str(c[1]), c[3]
        if eid in have and os.path.exists(os.path.join(D, "site", have[eid])):
            continue
        url = poster_url(title_of(name))
        if not url:
            missing.append(name)
            continue
        if DRY:
            got.append(name)
            continue
        try:
            r = rq.get(url, headers=UA, timeout=45)
            if r.status_code != 200 or len(r.content) < 2000:
                missing.append(name)
                continue
        except Exception:
            missing.append(name)
            continue
        ext = ".png" if url.lower().endswith(".png") else ".jpg"
        rel = "img/posters/%s%s" % (eid, ext)
        open(os.path.join(D, "site", rel), "wb").write(r.content)
        have[eid] = rel
        got.append(name)
    if not DRY:
        json.dump(have, open(LIST, "w"), separators=(",", ":"), sort_keys=True)
    print("posters: %d held, %d new, %d without one yet" % (len(have), len(got), len(missing)))
    for n in missing[:12]:
        print("   no poster yet:", n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
