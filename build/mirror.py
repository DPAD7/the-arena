"""Every picture the board draws, kept here rather than asked for each time.

   The page used to draw its club marks straight off ESPN's CDN and its
   fighters off ESPN and theScore. That is a request a reader's browser makes
   to somebody else, on every card, saying which game is being looked at --
   the same thing the four trackers were cut for. The faces of the passers
   were already ours; this makes the rest ours too.

     site/logos/nfl/<abbr>.png          32 clubs
     site/logos/ncaa/<espn id>.png      every college on the board
     site/faces/mma/<espn id>.png       the fighters, ESPN's picture
     site/faces/mma/s<score id>.png     theScore's, where ESPN has none

   Nothing is invented: a picture that will not come down is left out, and
   the page falls back to the original address for anything missing, so a
   fighter added tomorrow still has a face tonight.

   Usage:  python3 mirror.py            what is missing
           python3 mirror.py --all      everything again
"""
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL = "--all" in sys.argv
H = {"accept": "image/png,image/*;q=0.8"}

ESPN_CLUB = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/%s/500/%s.png&w=96&h=96"
# 336, not 220: the bout card draws a fighter across his whole half of the
# head -- about 300 real pixels on a phone -- and a 220px picture blurs at
# that size. The passers were moved to 336 for the same reason; the fighters
# were missed (Jose, Sep 22, 2026: "make sure that none of the images are
# blurry for all 3 sports"). ESPN's combiner will serve any width asked for.
ESPN_MAN = ("https://a.espncdn.com/combiner/i?img=/i/headshots/mma/players/full/"
            "%s.png&w=336&h=336&scale=crop")
SCORE_MAN = "https://assets-sports-gcp.thescore.com/mma/fighter/%s/w192xh192_headshot.png"


def arrays():
    s = open(D + "/master.html").read()
    out = {}
    for name in ("SCHED", "CFB", "FIGHTS"):
        m = re.search(r"var %s = (\[\[.*?\]\]);" % name, s, re.S)
        out[name] = json.loads(m.group(1)) if m else []
    m = re.search(r"var CFBID = (\{.*?\});", s, re.S)
    out["CFBID"] = json.loads(m.group(1)) if m else {}
    return out


def keep(url, path):
    """One picture, if it is not here already and the wire will give it up."""
    full = D + "/site/" + path
    if os.path.exists(full) and not ALL:
        return None
    os.makedirs(os.path.dirname(full), exist_ok=True)
    try:
        r = rq.get(url, headers=H, impersonate="chrome", timeout=30)
    except Exception:
        return False
    if r.status_code != 200 or len(r.content) < 200:
        return False
    open(full, "wb").write(r.content)
    # and the same picture as webp, which is what the face route reaches for
    # first. Left to faces.py this drifted: the pngs here were refetched at 336
    # and the old 220px webps stayed beside them, so the route went on serving
    # the small one and the card stayed blurry (Jose, Sep 22, 2026). Built in
    # memory and written whole, so a conversion that throws leaves no empty
    # file behind to be served in the png's place.
    if full.endswith(".png") and "/faces/" in full:
        webp = full[:-4] + ".webp"
        try:
            import io
            from PIL import Image
            buf = io.BytesIO()
            Image.open(full).convert("RGBA").save(buf, "WEBP", quality=82, method=6)
            if buf.tell() < 500:
                raise ValueError("wrote %d bytes" % buf.tell())
            open(webp, "wb").write(buf.getvalue())
        except Exception as e:
            if os.path.exists(webp) and os.path.getsize(webp) < 500:
                os.remove(webp)
            print("   %s stayed a png: %s" % (os.path.basename(full), e))
    return True


def main():
    a = arrays()
    want = []
    clubs = {g[3] for g in a["SCHED"]} | {g[4] for g in a["SCHED"]}
    for ab in sorted(x for x in clubs if x):
        want.append((ESPN_CLUB % ("nfl", ab.lower()), "logos/nfl/%s.png" % ab.lower()))
    seen = set()
    for g in a["CFB"]:
        for ab in (g[3], g[4]):
            cid = a["CFBID"].get(ab)
            if not cid or cid in seen:
                continue
            seen.add(cid)
            want.append((ESPN_CLUB % ("ncaa", cid), "logos/ncaa/%s.png" % cid))
    for f in a["FIGHTS"]:
        for eid, sid in ((f[4], f[12] if len(f) > 12 else ""),
                         (f[6], f[13] if len(f) > 13 else "")):
            if eid:
                want.append((ESPN_MAN % eid, "faces/mma/%s.png" % eid))
            # theScore's copy only where ESPN has none. The page reaches for
            # ESPN's first and never gets past it, so mirroring both held 402
            # pictures that could not be drawn -- 18.8MB and 587 files, on
            # every deploy, for nothing. Not one of them was the only picture
            # we had of anybody (Jose, Sep 22, 2026: "so we don't need that?").
            if sid and not (eid and os.path.exists(
                    D + "/site/faces/mma/%s.png" % eid)):
                want.append((SCORE_MAN % sid, "faces/mma/s%s.png" % sid))
    got = miss = had = 0
    gone = []
    for url, path in want:
        r = keep(url, path)
        if r is None:
            had += 1
        elif r:
            got += 1
        else:
            miss += 1
            gone.append(path)
            print("  no picture: %s" % path)
    # A man neither ESPN nor theScore has a picture of was still asked for by
    # every reader's browser, on every card, and answered 404 -- an outside
    # request that could never succeed. The names are written down so the page
    # skips straight to the silhouette and calls nobody (Jose, Sep 22, 2026:
    # "wire it so that it gets the new first and saves them").
    nopic = sorted({os.path.basename(p)[:-4] for p in gone
                    if p.startswith("faces/mma/")})
    json.dump(nopic, open(D + "/site/nopic.json", "w"),
              separators=(",", ":"))
    print("mirrored %d, already held %d, none to be had %d (of %d)" % (got, had, miss, len(want)))
    print("no picture anywhere: %d fighters, written to site/nopic.json" % len(nopic))


if __name__ == "__main__":
    main()
