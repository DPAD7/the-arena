"""The college programs whose touchdowns get clips: cfb_cover.json.

   The list is a floor, not a snapshot. Jose picked the programs by hand
   (conference by conference, Sep 15, 2026); on top of that, any team in the
   current AP Top 25 that is not yet on it is added, and nothing is ever
   removed here -- a team that breaks through stays. A team dropped by hand
   is listed in cfb_drop.json and is never added back by the poll.

   Usage:  python3 cfb_cover.py        (adds this week's ranked newcomers)
"""
import json
import os
import shutil

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "cfb_cover.json")


def main():
    cover = json.load(open(OUT)) if os.path.exists(OUT) else {}
    have = {v["id"] for v in cover.values()}
    # dropped by hand (cfb_drop.json): stays out however high it is ranked
    dropped = {v["id"] for v in (json.load(open(os.path.join(D, "data", "cfb_drop.json")))
                                 if os.path.exists(os.path.join(D, "data", "cfb_drop.json")) else {}).values()}
    r = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings",
               impersonate="chrome124", timeout=45).json()
    ap = [p for p in r.get("rankings", []) if "AP" in p.get("name", "")]
    if not ap:
        print("no AP poll on ESPN today; list unchanged (%d)" % len(cover))
        return
    added = []
    for x in ap[0]["ranks"]:
        t = x["team"]
        if str(t["id"]) in have or str(t["id"]) in dropped:
            continue
        # the ranking entry carries no full name; the team record does
        full = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/%s" % t["id"],
                      impersonate="chrome124", timeout=45).json().get("team", {})
        name = full.get("displayName") or t.get("location", "")
        cover[t["abbreviation"]] = {"name": name, "id": str(t["id"]), "conf": "AP Top 25 entrant"}
        added.append("#%d %s" % (x["current"], name))
    json.dump(cover, open(OUT, "w"), indent=1, sort_keys=True)
    shutil.copy(OUT, os.path.join(D, "site", "cfb_cover.json"))
    print("added from the AP Top 25: %s" % (", ".join(added) or "none"))
    print("covered programs: %d" % len(cover))


if __name__ == "__main__":
    main()
