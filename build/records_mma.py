"""Every fighter's record, from ESPN, for the bout cards.

   A card says who is favoured and how a fight ended; it never said what
   either man had done before. ESPN keeps the record on the athlete himself
   -- /v2/sports/mma/athletes/{id}/records -- as wins, losses and draws, so
   it is asked once a man and kept in site/fighters.json for the page.

   The file is added to, never rebuilt: a man who has not fought since the
   last run is left alone, and only the ones on cards still to come are
   asked about again. Nothing here talks to the page; the page reads the
   file (Jose, Sep 19, 2026).
"""
import json
import os
import re
import sys
import time
import urllib.request

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
OUT = os.path.join(D, "site", "fighters.json")
DRY = "--dry" in sys.argv
API = "http://sports.core.api.espn.com/v2/sports/mma/athletes/%s/records"
UA = {"User-Agent": "Mozilla/5.0"}


def ask(url):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20)
    return json.load(r)


def record_of(athlete_id):
    """"10-6-0" as ESPN writes it, or None where it keeps none."""
    try:
        d = ask(API % athlete_id)
    except Exception as e:
        print("   %s: %s" % (athlete_id, e))
        return None
    for item in d.get("items", []):
        try:
            x = ask(item["$ref"]) if "$ref" in item else item
        except Exception:
            continue
        if x.get("type") == "total" or x.get("name") == "overall":
            return x.get("displayValue") or x.get("summary")
    return None


def on_the_board():
    """Both men in every bout the page draws, with when the bout is."""
    page = pagefile.read()
    m = re.search(r"var FIGHTS = (\[\[.*?\]\]);", page, re.S)
    if not m:
        return []
    out = []
    for f in json.loads(m.group(1)):
        for i in (4, 6):
            if len(f) > i and f[i]:
                out.append((str(f[i]), str(f[2])))
    return out


def main():
    have = {}
    if os.path.exists(OUT):
        try:
            have = json.load(open(OUT))
        except Exception:
            have = {}

    now = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime())
    back = time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(time.time() - 10 * 86400))
    wanted = {}
    for athlete_id, when in on_the_board():
        # A man whose bout is still to come is asked again: he may have fought
        # elsewhere since. One who has just fought is asked too -- his record
        # moved tonight, and it used to be that it never did. Shahbazyan beat
        # Ferreira on Sep 19, 2026 and the card still read 16-6, because the
        # only men asked about were the ones who had not fought yet, so a
        # result could never reach the file (Jose: "SHAHBAZYAN 16-6, what is
        # this?"). Ten days back is well past the point ESPN has settled it.
        if when > back:
            wanted[athlete_id] = True
        elif athlete_id not in have:
            wanted[athlete_id] = False

    asked, got, lost = 0, 0, 0
    for athlete_id in sorted(wanted):
        asked += 1
        rec = record_of(athlete_id)
        if rec:
            if have.get(athlete_id) != rec:
                got += 1
            have[athlete_id] = rec
        elif athlete_id not in have:
            lost += 1

    print("fighters on the board: %d | asked: %d | written or moved: %d | "
          "no record at ESPN: %d | file holds: %d"
          % (len(set(i for i, _ in on_the_board())), asked, got, lost, len(have)))
    if DRY:
        print("dry run -- nothing written")
        return
    json.dump(have, open(OUT, "w"), separators=(",", ":"), sort_keys=True)
    print("written: %s" % OUT)


if __name__ == "__main__":
    main()
