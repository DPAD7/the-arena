"""Every named passer's picture, on our own site.

   ESPN's picture service is slow from a phone and every card asked it again.
   This keeps a 168px copy of each passer on the schedule (NFL and college)
   in site/faces/{league}/{espn id}.png, fetched once; the page reads ours
   first and falls back to ESPN's, then to the silhouette.

   Usage:  python3 faces.py
"""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://a.espncdn.com/combiner/i?img=/i/headshots/%s/players/full/%s.png&w=336&h=336&scale=crop"


def main():
    s = open(D + "/master.html").read()
    want = []
    for var, lg in (("SCHED", "nfl"), ("CFB", "college-football")):
        rows = json.loads(re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S).group(1))
        for g in rows:
            for pid in (g[6], g[8]):
                if str(pid).isdigit():
                    want.append((lg, str(pid)))
    led = D + "/site/ledger.json"
    if os.path.exists(led):
        for rows in json.load(open(led)).values():
            for r in rows:
                if str(r[2]).isdigit():
                    want.append(("nfl", str(r[2])))     # anybody who threw, not just the named two
    want = sorted(set(want))
    os.makedirs(D + "/site/faces/nfl", exist_ok=True)
    os.makedirs(D + "/site/faces/college-football", exist_ok=True)
    # A face already on disk may be an old 168px copy -- the college ones all
    # were, and they read as blurry on a phone at the size the card draws them
    # (Jose, Sep 22, 2026). Anything under 336 wide is fetched again.
    def small(png):
        try:
            from PIL import Image
            with Image.open(png) as im:
                return im.width < 336
        except Exception:
            return False

    todo = []
    for lg, pid in want:
        png = D + "/site/faces/%s/%s.png" % (lg, pid)
        if not os.path.exists(png) or small(png):
            todo.append((lg, pid))

    def fetch(item):
        lg, pid = item
        try:
            r = rq.get(URL % (lg, pid), impersonate="chrome124", timeout=30)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("image") and len(r.content) > 500:
                png = D + "/site/faces/%s/%s.png" % (lg, pid)
                open(png, "wb").write(r.content)
                # and the same picture as webp, which is what the board is
                # served: a fifth of the bytes for the same face
                try:
                    from PIL import Image
                    Image.open(png).convert("RGBA").save(png[:-4] + ".webp", "WEBP",
                                                        quality=82, method=6)
                except Exception as e:
                    print("   %s stayed a png: %s" % (pid, e))
                return True
        except Exception:
            pass
        return False

    with ThreadPoolExecutor(8) as ex:
        got = sum(1 for ok in ex.map(fetch, todo) if ok)
    print("faces: %d passers on the schedule, %d fetched now, %d missing at ESPN"
          % (len(want), got, len(todo) - got))


if __name__ == "__main__":
    main()
