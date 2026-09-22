"""The AP poll, written to site/ranks.json, so a college card can wear its
   number without the page asking ESPN for it.

   A side nobody ranks carries nothing -- an absence, not a placeholder
   (Jose, Sep 21, 2026). The file is { "MIZ": 19, ... }, keyed the way the
   card writes a school, and it is rewritten whole each run."""
import json
import os

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = ("https://site.api.espn.com/apis/site/v2/sports/football/"
       "college-football/rankings")


def poll():
    d = rq.get(URL, impersonate="chrome", timeout=25).json()
    got = d.get("rankings") or []
    ap = [x for x in got if "AP" in (x.get("shortName") or x.get("name") or "")]
    if not ap:
        raise SystemExit("no AP poll in %d rankings" % len(got))
    out = {}
    for r in ap[0].get("ranks") or []:
        ab = ((r.get("team") or {}).get("abbreviation") or "").strip()
        if ab:
            out[ab] = r.get("current")
    return out


if __name__ == "__main__":
    ranks = poll()
    path = os.path.join(D, "site", "ranks.json")
    with open(path, "w") as fh:
        json.dump(ranks, fh, separators=(",", ":"), sort_keys=True)
    print("ranks.json: %d ranked" % len(ranks))
