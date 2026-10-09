"""The news, read for the passers before the injury wire has it.

   ESPN's NFL news feed tags every story with the ESPN ids of the men in it,
   so nothing here is matched by name: a headline counts for a passer only
   when he is the first man it is tagged with, and he is on a club's chart in
   site/depth.json or named on the page.

       site.api.espn.com/apis/site/v2/sports/football/nfl/news

   Two kinds of headline are acted on, the same day they run (Jose, Sep 28,
   2026: "I keep having to tell you this person's out"):

     out        "Mayfield (thumb) out at least three weeks", ruled out, on IR,
                doubtful -- held in data/wire_held.json, which wire.py lays
                over ESPN's own injury entry until that entry is newer
     starts     "Keenum to start", named the starter -- held in
                data/qb_named.json against the club's next game, which
                starters.py puts on the card ahead of the chart

   The insiders are read too: Adam Schefter, Ian Rapoport and Pete Thamel's
   own ESPN pages carry their latest posts, and a post counts for a passer
   when exactly one passer on the charts or the cards is named in it, whole
   name, suffixes and accents aside (Jose, Sep 29, 2026, the three pages).
   Their pages are drawn in a browser -- a plain fetch is turned away.

   A held mark whose return date has passed is let go.

       python3 build/news.py
"""
import datetime as dt
import json
import os
import re
import sys

from curl_cffi import requests as rq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news?limit=100"
HELD = os.path.join(D, "data", "wire_held.json")
NAMED = os.path.join(D, "data", "qb_named.json")
DEPTH = os.path.join(D, "site", "depth.json")
NOW = dt.datetime.now(dt.timezone.utc)

# a headline that says he will not play; the ones that say he will are read
# first and win, so "won't miss" and "cleared" never mark a man out
NOT_OUT = re.compile(r"won'?t miss|not expected to miss|avoids|cleared|return(s|ing)? |set to return|"
                     r"no long-term|could play|expected to play|will play|practic", re.I)
# back in the lineup: read before IR, since "activated from IR" names it
ACTIVE = re.compile(r"\bactivat|\bwill play\b|\bset to play|cleared to play|expected to play|\bto play (thursday|friday|saturday|sunday|monday|tonight)", re.I)
IR = re.compile(r"\b(IR|injured reserve)\b", re.I)
OUT = re.compile(r"\)\s+out\b|\bout (for|at least|indefinitely|with|vs\.?|against|this|until|through|\d)|ruled out|will miss|to miss|expected to miss|sidelined|season-ending|"
                 r"torn|to sit|won'?t play|inactive", re.I)
DOUBT = re.compile(r"\bdoubtful\b", re.I)
START = re.compile(r"\b(to start|will start|set to start|slated to start|gets the start|"
                   r"named (the )?starter|start(s|ing)? at QB)\b", re.I)


def load(path):
    try:
        return json.load(open(path))
    except (OSError, ValueError):
        return {}


INSIDERS = ("adam-schefter", "ian-rapoport", "pete-thamel")
X_HANDLES = (("Adam Schefter", "AdamSchefter"), ("Ian Rapoport", "RapSheet"),
             ("Mike Garafolo", "MikeGarafolo"), ("Pete Thamel", "PeteThamel"))


def insiders():
    """The insiders' latest posts, off their ESPN pages: [{headline, published, byline}]."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    got = []
    try:
        with sync_playwright() as p:
            b = None
            for kw in ({"channel": "chrome"}, {}):
                try:
                    b = p.chromium.launch(**kw)
                    break
                except Exception:
                    continue
            if not b:
                return []
            pg = b.new_page()
            for who in INSIDERS:
                try:
                    pg.goto("https://www.espn.com/contributor/" + who, wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_timeout(3000)
                    html = pg.content()
                    i = html.find('"feed":[')
                    if i < 0:
                        continue
                    feed, _ = json.JSONDecoder().raw_decode(html[i + 7:])
                    got += [x for x in feed if isinstance(x, dict) and x.get("headline")]
                except Exception:
                    continue
            # and their own X pages, which carry every post the moment it is
            # made: ESPN's copy stopped at 5:55 PM while Schefter posted the
            # Bears' quarterback "direction" at 7:31 (Jose, Sep 30, 2026: "you
            # missed one from 42 mins ago"). X draws a profile's latest posts
            # for a browser with no login
            # X shows a headless browser nothing: it is asked as a desktop Chrome
            pg = b.new_page(viewport={"width": 600, "height": 1400}, user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"))
            # X shows GitHub's runners nothing, and asking cost the sweep
            # minutes it did not have (Oct 1, 2026): there the ESPN copy stands
            for who, handle in (() if os.environ.get("GITHUB_ACTIONS") else X_HANDLES):
                try:
                    pg.goto("https://x.com/" + handle, wait_until="domcontentloaded", timeout=45000)
                    pg.wait_for_selector("article", timeout=30000)
                    pg.wait_for_timeout(1500)
                    for a in pg.query_selector_all("article"):
                        # logged out, X draws a plain post: no clock on it, so
                        # the time is read off the post's own number
                        ids = [re.search(r"/%s/status/(\d+)" % handle, l.get_attribute("href") or "", re.I)
                               for l in a.query_selector_all('a[href*="/status/"]')]
                        ids = [m.group(1) for m in ids if m]
                        lines = a.inner_text().split("\n")
                        if not ids or len(lines) < 4 or lines[1].lower() != "@" + handle.lower():
                            continue
                        text = []
                        for l in lines[3:]:
                            if re.fullmatch(r"[\d.,]+[KM]?", l.strip()) or l.strip() == lines[0]:
                                break
                            text.append(l)
                        when = dt.datetime.fromtimestamp(((int(ids[0]) >> 22) + 1288834974657) / 1000, dt.timezone.utc)
                        if text:
                            got.append({"headline": " ".join(x.strip() for x in text if x.strip()),
                                        "published": when.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                        "byline": who, "source": "x"})
                except Exception:
                    continue
            b.close()
    except Exception:
        pass
    return got


def fold(n):
    import unicodedata
    n = unicodedata.normalize("NFD", n or "")
    n = "".join(c for c in n if not unicodedata.combining(c))
    n = re.sub(r"\b(jr|sr|ii|iii|iv)\b\.?", " ", n, flags=re.I)
    return re.sub(r"[^a-z ]+", " ", n.lower()).split()


def main():
    try:
        r = rq.get(FEED, impersonate="chrome", timeout=30)
        arts = (r.json() or {}).get("articles") or [] if r.status_code == 200 else []
    except Exception:
        arts = []
    if not arts:
        print("news: the feed did not answer; nothing changed")
        return

    depth = load(DEPTH)
    club_of = {}
    for club, room in depth.items():
        for q in room.get("qbs") or []:
            club_of[str(q["id"])] = (club, q.get("name") or "")
    s = pagefile.read()
    m = re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S)
    sched = json.loads(m.group(1)) if m else []
    for g in sched:
        for i, ci in ((5, 3), (7, 4)):
            if g[i + 1]:
                club_of.setdefault(str(g[i + 1]), (g[ci], g[i]))

    # the college cards' passers too, for Thamel
    m2 = re.search(r"  var CFB = (\[\[.*?\]\]);", s, re.S)
    for g in json.loads(m2.group(1)) if m2 else []:
        for i, ci in ((5, 3), (7, 4)):
            if g[i + 1]:
                club_of.setdefault(str(g[i + 1]), (g[ci], g[i]))

    # the insiders' posts, each tied to the one passer it names in full
    names = {}
    for pid, (club, name) in club_of.items():
        k = " ".join(fold(name))
        if len(k.split()) >= 2:
            names.setdefault(k, set()).add(pid)
    posts = insiders()
    print("news: insiders %d posts, %d off X" % (len(posts), sum(1 for x in posts if x.get("source") == "x")))
    for x in posts:
        words = " " + " ".join(fold(x.get("headline"))) + " "
        who = set()
        for k, pids in names.items():
            if " " + k + " " in words:
                who |= pids
        if len(who) == 1:
            arts.append({"type": "HeadlineNews", "headline": x["headline"], "published": x.get("published") or "",
                         "categories": [{"type": "athlete", "athleteId": next(iter(who))}],
                         "by": x.get("byline") or "insider"})

    held, named = load(HELD), load(NAMED)
    moved = []
    # everyone else on ESPN's injury report -- linemen, targets, backs, the
    # men QB Wire names -- for a headline that puts him back in the lineup
    # before the report catches up (Jose, Oct 8, 2026: Tyler Smith activated
    # off IR at 2:53 PM for TNF, the wire still said Questionable at 6:30)
    report = {}
    try:
        lj = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries", impersonate="chrome", timeout=30).json()
        for t in lj.get("injuries") or []:
            for i in t.get("injuries") or []:
                a0 = i.get("athlete") or {}
                # the report carries no id field: it is in the player's link
                m0 = re.search(r"/id/(\d+)", json.dumps(a0.get("links") or []))
                aid = str(a0.get("id") or (m0.group(1) if m0 else ""))
                if aid:
                    report[aid] = ((a0.get("team") or {}).get("abbreviation") or t.get("displayName") or "", a0.get("displayName") or "")
    except Exception:
        report = {}
    # each club playing in the next two days, off its own feed: the league's
    # feed does not carry a lineman's activation
    soon = set()
    for g in sched:
        try:
            t = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        except ValueError:
            continue
        if NOW - dt.timedelta(hours=4) < t < NOW + dt.timedelta(days=2):
            soon |= {g[3], g[4]}
    seen_h = {a.get("headline") for a in arts}
    for club in sorted(soon):
        try:
            tj = rq.get(FEED.split("?")[0] + "?team=%s&limit=15" % club.lower(), impersonate="chrome", timeout=20).json()
        except Exception:
            continue
        for a in tj.get("articles") or []:
            if a.get("headline") not in seen_h:
                seen_h.add(a.get("headline")); arts.append(a)
    for a in sorted(arts, key=lambda a: a.get("published") or ""):
        ids = [str(c["athleteId"]) for c in a.get("categories") or [] if c.get("type") == "athlete" and c.get("athleteId")]
        if not ids or ids[0] in club_of or ids[0] not in report:
            continue
        head, when = a.get("headline") or "", (a.get("published") or "")[:16] + "Z"
        try:
            if NOW - dt.datetime.fromisoformat(when.replace("Z", "+00:00")) > dt.timedelta(days=3):
                continue
        except ValueError:
            continue
        pid = ids[0]
        if (held.get(pid) or {}).get("since", "") >= when:
            continue
        status = "Active" if ACTIVE.search(head) else None if NOT_OUT.search(head) else \
            "Injured Reserve" if IR.search(head) else "Out" if OUT.search(head) else "Doubtful" if DOUBT.search(head) else None
        if status:
            held[pid] = {"status": status, "abbr": status[0], "type": None, "side": None, "since": when, "returns": None,
                         "note": head, "src": "ESPN news, %s: %s" % (when, head)}
            moved.append("%s %s %s (%s)" % (report[pid][0], report[pid][1], status, head))
    # oldest first, so a later headline about the same man has the last word
    for a in sorted(arts, key=lambda a: a.get("published") or ""):
        if a.get("type") != "HeadlineNews":
            continue
        ids = [str(c["athleteId"]) for c in a.get("categories") or []
               if c.get("type") == "athlete" and c.get("athleteId")]
        if not ids or ids[0] not in club_of:
            continue
        pid, (club, name) = ids[0], club_of[ids[0]]
        head = a.get("headline") or ""
        when = (a.get("published") or "")[:16] + "Z"
        try:
            age = NOW - dt.datetime.fromisoformat(when.replace("Z", "+00:00"))
        except ValueError:
            continue
        if age > dt.timedelta(days=3):
            continue
        src = "%s, %s: %s" % (a.get("by") or "ESPN news", when, head)
        # a post that lists several men is read only where it names him: "QB
        # Kienholz is questionable" sat under "RB Rule is doubtful" and he was
        # marked Doubtful for a week (Oct 9, 2026)
        sur = (name.split() or [""])[-1]
        parts = [x for x in re.split(r"[\n]+|(?<=[.!?])\s+", head) if sur and sur.lower() in x.lower()]
        if parts:
            head = " ".join(parts)
        if NOT_OUT.search(head):
            if pid in held and (held[pid].get("since") or "") < when and held[pid].get("src", "").startswith("ESPN news"):
                del held[pid]
                moved.append("%s %s cleared (%s)" % (club, name, head))
            continue
        status = "Injured Reserve" if IR.search(head) else "Out" if OUT.search(head) else \
            "Doubtful" if DOUBT.search(head) else None
        if status:
            was = held.get(pid) or {}
            if (was.get("since") or "") >= when:
                continue
            ret = None
            wk = re.search(r"(\w+)(?:-to-\w+)? weeks?", head)
            n = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "eight": 8}
            if wk and (wk.group(1).lower() in n or wk.group(1).isdigit()):
                k = int(wk.group(1)) if wk.group(1).isdigit() else n[wk.group(1).lower()]
                ret = (NOW + dt.timedelta(weeks=k)).date().isoformat()
            held[pid] = {"status": status, "abbr": status[0], "type": None, "side": None,
                         "since": when, "returns": ret or was.get("returns"),
                         "note": head, "src": src}
            moved.append("%s %s %s (%s)" % (club, name, status, head))
            continue
        if START.search(head):
            nxt = None
            for g in sorted(sched, key=lambda g: g[2]):
                try:
                    t = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
                except ValueError:
                    continue
                if t > NOW and club in (g[3], g[4]):
                    nxt = g
                    break
            if nxt:
                key = "%s|%s" % (nxt[1], club)
                if (named.get(key) or {}).get("id") != pid:
                    named[key] = {"id": pid, "name": name, "why": src}
                    moved.append("%s %s named to start (%s)" % (club, name, head))

    # a held mark lets go once the date he was due back has passed
    today = NOW.date().isoformat()
    for pid in [p for p, h in held.items() if h.get("returns") and h["returns"] < today]:
        del held[pid]
    # a named start lets go once its game is over
    live = {str(g[1]) for g in sched}
    for key in [k for k in named if k.split("|")[0] not in live]:
        del named[key]

    json.dump(held, open(HELD, "w"), indent=1)
    json.dump(named, open(NAMED, "w"), indent=1)
    for line in moved:
        print("   " + line)
    print("news: %d headlines read, %d passers moved" % (len(arts), len(moved)))


if __name__ == "__main__":
    main()
