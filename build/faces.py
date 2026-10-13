"""Every named passer's picture, on our own site.

   ESPN's picture service is slow from a phone and every card asked it again.
   This keeps a 168px copy of each passer on the schedule (NFL and college)
   in site/faces/{league}/{espn id}.png, fetched once; the page reads ours
   first and falls back to ESPN's, then to the silhouette.

   Usage:  python3 faces.py
"""
import json
import os
import sys
import re
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
URL = "https://a.espncdn.com/combiner/i?img=/i/headshots/%s/players/full/%s.png&w=336&h=336&scale=crop"
# each face ESPN would not give, and when: it is not asked for again for a
# day -- the same college passers with no headshot were asked for on every
# pass (Oct 12, 2026)
MISSES = D + "/data/face_misses.json"


def main():
    s = pagefile.read()
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
    # The first three of every club's quarterback room, whether or not a card
    # draws them. A swap is settled sixty minutes before kickoff and there is
    # no time to go fetching a picture then: Michael Penix Jr. took Atlanta's
    # card and the board had no face for him, because nothing had ever drawn
    # him (Jose, Sep 22, 2026: "lets get the pictures for top 3 qb for each
    # team we dont have to place it but just incase of injury").
    dep = D + "/site/depth.json"
    if os.path.exists(dep):
        for room in json.load(open(dep)).values():
            for q in (room.get("qbs") or [])[:3]:
                if str(q.get("id")).isdigit():
                    want.append(("nfl", str(q["id"])))
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

    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    try:
        misses = json.load(open(MISSES))
    except (OSError, ValueError):
        misses = {}
    todo, rested = [], 0
    for lg, pid in want:
        png = D + "/site/faces/%s/%s.png" % (lg, pid)
        if not os.path.exists(png) or small(png):
            last = misses.get("%s/%s" % (lg, pid))
            try:
                if last and now - dt.datetime.fromisoformat(last) < dt.timedelta(days=1):
                    rested += 1
                    continue
            except ValueError:
                pass
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
                # built in memory and written whole, never saved straight to
                # its own name: a conversion that threw half way left a
                # zero-byte .webp behind, and the face route serves the webp
                # before the png, so the man drew nothing at all. Michael
                # Penix Jr. took Atlanta's card with an empty one
                # (Jose, Sep 22, 2026: "why dont we have an img for penix jr")
                webp = png[:-4] + ".webp"
                try:
                    import io
                    from PIL import Image
                    buf = io.BytesIO()
                    Image.open(png).convert("RGBA").save(buf, "WEBP",
                                                        quality=82, method=6)
                    if buf.tell() < 500:
                        raise ValueError("wrote %d bytes" % buf.tell())
                    open(webp, "wb").write(buf.getvalue())
                except Exception as e:
                    # and an old empty one is taken away rather than left to
                    # be served in the png's place
                    if os.path.exists(webp) and os.path.getsize(webp) < 500:
                        os.remove(webp)
                    print("   %s stayed a png: %s" % (pid, e))
                return True
        except Exception:
            pass
        return False

    with ThreadPoolExecutor(8) as ex:
        oks = list(ex.map(fetch, todo))
    got = sum(1 for ok in oks if ok)
    for (lg, pid), ok in zip(todo, oks):
        if ok:
            misses.pop("%s/%s" % (lg, pid), None)
        else:
            misses["%s/%s" % (lg, pid)] = now.isoformat(timespec="minutes")
    json.dump(misses, open(MISSES, "w"), indent=0, sort_keys=True)
    print("faces: %d passers on the schedule, %d fetched now, %d missing at ESPN%s"
          % (len(want), got, len(todo) - got,
             (", %d misses resting a day" % rested) if rested else ""))


if __name__ == "__main__":
    main()
