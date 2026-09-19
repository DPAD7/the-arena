"""Fill every empty slot on tomorrow's NFL cards that DraftKings now prices.

   Head to head passing yards, first-quarter receptions, passing touchdowns and
   the one missing moneyline were all placeholders because the market was not
   on offer when the board was built. Most of them are up now. Each card is
   matched to its DraftKings event through any price it already carries, and a
   ghost is replaced only where a real price exists for it.
"""
import json
import re
import sys

sys.path.insert(0, "/Users/joe/qbspy/build")
from read_dk import ask

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")
GHOST = '<span class="ghost" aria-hidden="true"></span>'
filled = {"ml": 0, "h2h": 0, "ptd": 0, "rec": 0}


def implied(a):
    n = int(str(a).replace("−", "-").replace("+", ""))
    return 100.0 / (n + 100.0) if n > 0 else -n / (-n + 100.0)


def html(a):
    n = int(str(a).replace("−", "-").replace("+", ""))
    return ("+%d" % n) if n > 0 else ("&minus;%d" % -n)


def button(oid, a):
    return ('<button class="price" type="button" data-oid="%s">%s '
            '<span class="pct">%d%%</span></button>'
            % (oid, html(a), round(implied(a) * 100)))


def pull(path):
    d = ask(None, None, path) or {}
    mk = {m["id"]: m for m in d.get("markets") or []}
    rows = []
    for sel in d.get("selections") or []:
        m = mk.get(sel.get("marketId")) or {}
        who = (sel.get("participants") or [{}])[0]
        rows.append({"event": str(m.get("eventId")), "market": m.get("name") or "",
                     "label": sel.get("label"), "odds": (sel.get("displayOdds") or {}).get("american"),
                     "oid": sel.get("id"), "who": who.get("name") or "",
                     "home": (who.get("venueRole") or "").startswith("Home")})
    return rows


print("asking DraftKings...")
H2H = pull("/sportscontent/dkusmd/v1/leagues/88808/categories/1185/subcategories/11977")
REC = pull("/sportscontent/dkusmd/v1/leagues/88808/categories/1342/subcategories/18527")

src = json.load(open(D + "/sources.json"))
oid_event = {}
for e in src["events"]:
    for o in e["oids"]:
        oid_event[o] = e["id"]

CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
cache = {}


def event_rows(eid, cat):
    key = (eid, cat)
    if key not in cache:
        cache[key] = pull("/sportscontent/dkusmd/v1/events/%s/categories/%d" % (eid, cat))
    return cache[key]


def surname(n):
    bits = (n or "").split()
    return bits[-1].lower() if bits else ""


def fix(mm):
    global filled
    card = mm.group(0)
    if 'data-lg="nfl"' not in card:
        return card
    eid = None
    for o in re.findall(r'data-oid="([^"]*)"', card):
        if o in oid_event:
            eid = oid_event[o]
            break
    if not eid:
        return card
    lq = (re.search(r'data-lqb="([^"]*)"', card) or [None, ""])[1] if "data-lqb" in card else ""
    rq = (re.search(r'data-rqb="([^"]*)"', card) or [None, ""])[1] if "data-rqb" in card else ""
    lhome = 'data-lhome="1"' in card

    # ---- head to head passing yards ----
    if '<span class="h2hodds">' + GHOST in card:
        mine = [r for r in H2H if r["event"] == eid]
        by = {surname(r["who"]): r for r in mine}
        for who, first in ((lq, True), (rq, False)):
            r = by.get(surname(who))
            if not r:
                continue
            old = '<span class="h2hodds">%s</span>' % GHOST
            if old not in card:
                break
            parts = card.split(old)
            i = 0 if first else (1 if len(parts) > 2 else 0)
            # replace the first remaining ghost for the left man, the next for the right
            card = card.replace(old, '<span class="h2hodds">%s</span>' % button(r["oid"], r["odds"]), 1)
            filled["h2h"] += 1

    # ---- passing touchdowns ----
    if re.search(r'<span class="ptdline">\d\+</span>' + re.escape(GHOST), card):
        rows = event_rows(eid, 1000)
        for who, side in ((lq, "l"), (rq, "r")):
            if not who:
                continue
            for line in ("1", "2"):
                pat = ('(<div class="ptdside ptdside--%s">(?:(?!</div></div>).)*?'
                       '<span class="ptdbtn ptdbtn--n%s"><span class="ptdline">%s\\+</span>)%s'
                       % (side, line, line, re.escape(GHOST)))
                if not re.search(pat, card, re.S):
                    continue
                hit = [r for r in rows
                       if "Passing Touchdowns" in r["market"]
                       and surname(r["who"] or r["market"].split(" Passing")[0]) == surname(who)
                       and r["label"] == line + "+"]
                if not hit:
                    continue
                card = re.sub(pat, lambda m, b=button(hit[0]["oid"], hit[0]["odds"]): m.group(1) + b,
                              card, count=1, flags=re.S)
                filled["ptd"] += 1

    # ---- first quarter receptions ----
    if '<span class="recman">' + GHOST in card:
        mine = [r for r in REC if r["event"] == eid and r["label"] == "1+"]
        for side_home in ((lhome,), ):
            pass
        for cell_is_left in (True, False):
            want_home = lhome if cell_is_left else (not lhome)
            men = [r for r in mine if r["home"] == want_home]
            men.sort(key=lambda r: implied(r["odds"]), reverse=True)
            cell = re.search(r'<span class="gcell recpair">((?:(?!</span></span>).)*</span></span>)', card, re.S)
            for r in men[:2]:
                old = '<span class="recman">%s<span class="wrname">&nbsp;</span></span>' % GHOST
                if old not in card:
                    break
                card = card.replace(
                    old, '<span class="recman">%s<span class="wrname">%s</span></span>'
                         % (button(r["oid"], r["odds"]), r["who"].split(" ")[-1]), 1)
                filled["rec"] += 1

    # ---- a missing moneyline ----
    if '<span class="gml">' + GHOST in card:
        rows = event_rows(eid, 492)
        mls = [r for r in rows if r["market"] == "Moneyline"]
        teams = re.findall(r'<span class="gteam[^"]*">(?:<span class="gml">.*?</span>)?'
                           r'([A-Za-z]+)(?:<span class="gml">.*?</span>)?</span>', card, re.S)
        for t in teams:
            for r in mls:
                if t.lower() in (r["who"] or "").lower().replace(" ", ""):
                    old = '<span class="gml">%s</span>' % GHOST
                    if old in card:
                        card = card.replace(old, '<span class="gml">%s</span>'
                                            % button(r["oid"], r["odds"]), 1)
                        filled["ml"] += 1
    return card


s = CARD.sub(fix, s)
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("filled:", filled, "| prices %d -> %d" % (before, s.count("data-oid")))
