"""Who the UFC has ranked, by division, with the champion at the top.

   Their rankings are not computed from anything: a panel of media members
   votes, by weight class and pound for pound, and only fighters on the active
   roster can be voted on. Champions sit above their division by rule and are
   only voted on for the pound-for-pound list -- which their own markup calls
   the meta ranking (Jose, Sep 20, 2026: "how are they getting the meta
   ranking").

   So there is nothing to reproduce and nothing to model. There is a table,
   served as plain HTML by their site with no feed behind it, and this reads
   it: every division, its champion, the fifteen behind him, and how far each
   man moved since the last vote.

   Written to data/ufc_rankings.json:

       [{"division": "Lightweight", "champion": "Islam Makhachev",
         "men": [{"rank": 1, "name": "Arman Tsarukyan", "slug": "arman-tsarukyan",
                  "moved": 0}, ...]}]

   `moved` is positive for a man who climbed, negative for one who fell, and
   zero where the page marks nothing.

       python3 build/ufc_rankings.py
"""
import html
import json
import os
import re

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "ufc_rankings.json")
PAGE = "https://www.ufc.com/rankings"

GROUP = re.compile(r'<div class="view-grouping">(.*?)(?=<div class="view-grouping">|\Z)', re.S)
HEAD = re.compile(r'<div class="view-grouping-header">(.*?)</div>', re.S)
CHAMP = re.compile(r'rankings--athlete--champion.*?<h5><a href="/athlete/([^"]+)"[^>]*>\s*(.*?)\s*</a>', re.S)
ROW = re.compile(
    r'views-field-weight-class-rank">\s*(\d+)\s*</td>\s*'
    r'<td class="views-field views-field-title"><a href="/athlete/([^"]+)"[^>]*>\s*(.*?)\s*</a>.*?'
    r'views-field-weight-class-rank-change">(.*?)</td>', re.S)
# "<span class=...rank-increase>Rank increased by</span> 1" -- the number sits
# outside the span, after the words, so it is read from the cell rather than
# from the tag
MOVE = re.compile(r'rank-(increase|decrease)"[^>]*>.*?</span>\s*(\d+)', re.S)


def clean(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))).strip()


def moved(cell):
    m = MOVE.search(cell)
    if not m:
        return 0
    return int(m.group(2)) * (1 if m.group(1) == "increase" else -1)


def main():
    r = rq.get(PAGE, impersonate="chrome", timeout=30)
    if r.status_code != 200:
        raise SystemExit("the rankings page answered %d" % r.status_code)
    out = []
    for blk in GROUP.findall(r.text):
        head = HEAD.search(blk)
        if not head:
            continue
        division = clean(head.group(1))
        champ = CHAMP.search(blk)
        men = [{"rank": int(a), "slug": b, "name": clean(c), "moved": moved(d)}
               for a, b, c, d in ROW.findall(blk)]
        if not men:
            continue
        out.append({"division": division,
                    "champion": clean(champ.group(2)) if champ else None,
                    "champion_slug": champ.group(1) if champ else None,
                    "men": men})
    json.dump(out, open(OUT, "w"), indent=1)
    for d in out:
        climbed = [m for m in d["men"] if m["moved"]]
        print("%-28s champion %-22s %2d ranked%s" % (
            d["division"], d["champion"] or "-", len(d["men"]),
            "" if not climbed else "   moved: " + ", ".join(
                "%s %+d" % (m["name"], m["moved"]) for m in climbed)))
    print("%d divisions written to %s" % (len(out), OUT))


if __name__ == "__main__":
    main()
