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
import datetime
import io
import json
import os
import re
import sys

from curl_cffi import requests as rq
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
OUT = os.path.join(D, "site", "img", "posters")
LIST = os.path.join(D, "site", "posters.json")
UA = {"User-Agent": "the-arena/1.0 (185117539+DPAD7@users.noreply.github.com)"}
API = "https://en.wikipedia.org/w/api.php"


def title_of(name):
    m = re.match(r"(UFC (?:Freedom )?\d+)\b", name)
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


def search_title(name):
    """The article when the card's own name is not its title: Wikipedia
       writes "UFC Fight Night: Silva vs. Delgado" where the board has "Noche
       UFC: Silva vs. Delgado", and "vs." where the board has "vs"."""
    try:
        j = rq.get(API, params={"action": "query", "list": "search", "srsearch": name.replace(":", " "),
                                "format": "json", "srlimit": 3}, headers=UA, timeout=30).json()
    except Exception:
        return None
    # the two headliners must both be in the title: a loose hit took another
    # card with the same man on it (Allen vs. Costa for Allen vs. Duncan)
    m = re.search(r":\s*(.+?)\s+vs\.?\s+(.+?)(?:\s+\d+)?$", name)
    need = [x.split()[-1].lower() for x in m.groups()] if m else []
    for hit in (j.get("query") or {}).get("search") or []:
        t = hit["title"]
        if (re.match(r"(UFC|Noche UFC)\b", t) or "Zuffa" in name) and all(n in t.lower() for n in need):
            return t
    return None


def ufc_art(name, when):
    """The event art from UFC.com, cropped to a poster: it is up before
       Wikipedia has the official one, and gives way to it once it is
       (Jose, Sep 25, 2026: "get them fight week"). Wide and without words,
       so the middle of it is kept."""
    m = re.match(r"UFC (\d+)\b", name)
    et = when.astimezone(datetime.timezone(datetime.timedelta(hours=-4)))
    slug = ("ufc-%s" % m.group(1)) if m else ("ufc-fight-night-%s-%02d-%d" % (et.strftime("%B").lower(), et.day, et.year))
    try:
        t = rq.get("https://www.ufc.com/event/" + slug, impersonate="chrome124", timeout=30).text
        # the event art, or before it is out the temporary hero of the two
        # headliners the page carries, which is art enough until it is
        u = (re.findall(r'(https://ufc\.com/images/styles/background_image_md/[^"\s]*EVENT-ART[^"\s]*)', t) or
             re.findall(r'(https://ufc\.com/images/styles/background_image_md/[^"\s]*TEMP-HERO[^"\s]*)', t))
        if not u:
            return None
        img = Image.open(io.BytesIO(rq.get(u[0].replace("&amp;", "&"), impersonate="chrome124", timeout=30).content)).convert("RGB")
    except Exception:
        return None
    w, h = img.size
    cw = int(h * 263 / 380)
    img = img.crop(((w - cw) // 2, 0, (w - cw) // 2 + cw, h)).resize((263, 380), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=86)
    return out.getvalue()


def main():
    s = pagefile.read()
    cards = json.loads(re.search(r"  var FIGHTCARDS = (\[\[.*?\]\]);", s, re.S).group(1))
    # the big Zuffa nights have posters of their own; a numbered show wears
    # the Zuffa art on the page and is not looked for
    bx = re.search(r"  var BOXCARDS = (\[.*?\]);\n", s, re.S)
    cards += [c for c in (json.loads(bx.group(1)) if bx else []) if not re.match(r"Zuffa Boxing \d", c[3])]
    try:
        have = json.load(open(LIST))
    except (OSError, ValueError):
        have = {}
    os.makedirs(OUT, exist_ok=True)
    got, missing = [], []
    for c in cards:
        eid, name = str(c[1]), c[3]
        # a stand-in from UFC.com is held until Wikipedia has the real one
        if eid in have and os.path.exists(os.path.join(D, "site", have[eid])) and "-ufc" not in have[eid]:
            continue
        url = poster_url(title_of(name))
        if not url:
            alt = search_title(name)
            url = poster_url(alt) if alt else None
        if not url:
            if eid in have:
                continue
            when = datetime.datetime.fromisoformat(c[2].replace("Z", "+00:00"))
            art = None if DRY or "Contender" in name or "Zuffa" in name else ufc_art(name, when)
            if art:
                rel = "img/posters/%s-ufc.jpg" % eid
                open(os.path.join(D, "site", rel), "wb").write(art)
                have[eid] = rel
                got.append(name + " (UFC.com art)")
            else:
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
        if "-ufc" in have.get(eid, ""):
            try:
                os.remove(os.path.join(D, "site", have[eid]))
            except OSError:
                pass
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
