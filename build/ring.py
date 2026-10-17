"""A boxer off The Ring: his cut-out picture, record and division.

   The Ring (ringmagazine.com) keeps a profile for every boxer it covers --
   a cut-out picture like the UFC's, his pro record, his division, and his
   fights with each opponent's own profile -- behind a plain request, so it
   runs on GitHub with no Mac (Jose, Oct 17, 2026: "if I do boxing then look
   at the ring magazine for this image ... DraftKings matches the time").

   Only the men on a bet he pasted are looked up, and only when the board
   doesn't hold them yet -- never a card or a division at a time.

   A man is found by his name: the opponent's profile through the fight they
   share when one man is already known, else The Ring's fighter list in its
   own order (most recently updated first), each profile's name read and kept
   in data/ring_index.json so a name is never looked for twice.

     site/faces/box/<slug>.jpg   his cut-out, square, centred on the head
     data/ring.json              {slug: {id, name, record, kos, division}}

       python3 build/ring.py "Fabio Wardley" "Daniel Dubois"
"""
import io
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACES = os.path.join(D, "site", "faces", "box")
KEEP = os.path.join(D, "data", "ring.json")
INDEX = os.path.join(D, "data", "ring_index.json")
SITE = "https://www.ringmagazine.com"


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def fold(name):
    import unicodedata
    n = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", "", n)).strip()


def get(path):
    r = rq.get(SITE + path, impersonate="chrome", timeout=30)
    return r if r.status_code == 200 else None


def profile(fid):
    r = get("/api/fighter/profile/" + fid)
    try:
        return r.json() if r else None
    except ValueError:
        return None


def find(name, near=None):
    """The Ring's profile for a man, or None."""
    want = fold(name)
    index = json.load(open(INDEX)) if os.path.exists(INDEX) else {}
    for fid, n in index.items():
        if fold(n) == want:
            return profile(fid)
    # the opponent of a man already found: through the fight they share
    if near:
        for f in near.get("fights") or []:
            for side in ("fighterA", "fighterB"):
                p = f.get(side) or {}
                if fold(p.get("name")) == want and p.get("id"):
                    got = profile(p["id"])
                    if got:
                        index[got["id"]] = got.get("name", "")
                        json.dump(index, open(INDEX, "w"), indent=0, sort_keys=True)
                        return got
    sm = get("/api/sitemap/sitemap-fighters")
    ids = re.findall(r"/fighters/([A-Za-z0-9]+)</loc>", sm.text) if sm else []
    found = None
    for fid in ids:
        if fid in index:
            continue
        p = profile(fid)
        if not p:
            continue
        index[fid] = p.get("name", "")
        if fold(p.get("name")) == want:
            found = p
            break
    json.dump(index, open(INDEX, "w"), indent=0, sort_keys=True)
    return found


def face(p, name):
    """His cut-out, square, centred on his head, on the board's dark tile."""
    from PIL import Image
    img = (p.get("cutOutImage") or p.get("heroImage") or {}).get("file") or {}
    if not img.get("url"):
        return ""
    raw = rq.get("https:" + img["url"] + "?w=1600", impersonate="chrome", timeout=30).content
    im = Image.open(io.BytesIO(raw)).convert("RGBA")
    w, h = im.size
    a = im.getchannel("A").point(lambda v: 255 if v > 40 else 0)
    if not a.getbbox():
        return ""
    top = a.getbbox()[1]
    head = a.crop((0, top, w, top + int(h * 0.18))).getbbox()
    cx = (head[0] + head[2]) // 2
    side = int(h * 0.62)
    y0 = max(0, top - int(side * 0.06))
    tile = Image.new("RGBA", (side, side), (21, 23, 27, 255))
    tile.alpha_composite(im.crop((cx - side // 2, y0, cx + side // 2, y0 + side)))
    os.makedirs(FACES, exist_ok=True)
    tile.convert("RGB").resize((400, 400)).save(os.path.join(FACES, slug(name) + ".jpg"), quality=90)
    return "box:" + slug(name)


def boxer(name, near=None):
    """Find him, keep his face if the board has none, and say what The Ring has."""
    p = find(name, near)
    if not p:
        print("  %s: not on The Ring" % name)
        return None, None
    rec = ((p.get("records") or {}).get("pro")) or {}
    div = ((p.get("primaryDivision") or {}).get("name") or "").replace("Ring", "").replace("Men", "").replace("Women", "").strip(" –-")
    out = {"id": p["id"], "name": p.get("name", name),
           "record": "%s-%s-%s" % (rec.get("wins", 0), rec.get("losses", 0), rec.get("draws", 0)) if rec else "",
           "kos": rec.get("knockouts"), "division": div}
    path = os.path.join(FACES, slug(name) + ".jpg")
    out["face"] = ("box:" + slug(name)) if os.path.exists(path) else face(p, name)
    keep = json.load(open(KEEP)) if os.path.exists(KEEP) else {}
    keep[slug(name)] = out
    json.dump(keep, open(KEEP, "w"), indent=1, sort_keys=True)
    return out, p


def pair(a, b):
    """Both men of one bout: the second through the first where it can."""
    oa, pa = boxer(a)
    ob, _ = boxer(b, near=pa)
    return oa, ob


if __name__ == "__main__":
    names = sys.argv[1:]
    for i in range(0, len(names) - 1, 2):
        print(pair(names[i], names[i + 1]))
