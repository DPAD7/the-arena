"""Zuffa Boxing on the combat page: every card, its bouts, prices and results.

   ESPN publishes no boxing at all, so a boxing card is read from Wikipedia's
   "2026 in Zuffa Boxing", which keeps every event -- the numbered shows and
   the big nights -- with its card table: the class, the two men, and once
   it is fought the winner, the method, the round and the time. DraftKings'
   boxing league prices the bouts and says when each one starts
   (Jose, Sep 25, 2026: "add to the combat page ... full cards").

   What it writes:
     master.html       BOXCARDS and BOXFIGHTS, in the same shape as the UFC
                       tab's FIGHTCARDS and FIGHTS, which the page adds to
                       those at load -- so a boxing bout is drawn by the same
                       card, the same poster row, the same sheet
     site/prices.json  FIGHTS[bout] = the moneyline, as the UFC bouts are,
                       so a price moving never rewrites the page
     site/final/mma-<card>.json
                       each fought bout, in the shape of ESPN's scoreboard,
                       so the page settles it the way it settles a UFC bout
     site/faces/box/   a picture of each man Wikipedia has one of

   A card's id is zb-<number> for a numbered show, zb-<two surnames> for a
   big night; a bout's is the card's and its place on the card.

       python3 build/boxing.py          read, write, and say what changed
       python3 build/boxing.py --dry    say what it would write
"""
import datetime as dt
import json
import os
import re
import sys
import unicodedata

from curl_cffi import requests as rq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile
import prices as pricefile
import whoname
from read_dk import ask

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
UA = {"User-Agent": "the-arena/1.0 (185117539+DPAD7@users.noreply.github.com)"}
API = "https://en.wikipedia.org/w/api.php"
PAGE = "2026 in Zuffa Boxing"
DK_BOXING = 72061
FACES = os.path.join(D, "site", "faces", "box")


def wiki(title, prop="wikitext"):
    j = rq.get(API, params={"action": "parse", "page": title, "prop": prop,
                            "format": "json", "redirects": 1}, headers=UA, timeout=40).json()
    return ((j.get("parse") or {}).get(prop) or {}).get("*", "")


def plain(cell):
    """A table cell as words: links to their text, templates to their first
       argument ({{Abbr|KO|Knockout}} is KO), refs and markup gone."""
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    t = re.sub(r"\{\{(?:Abbr|abbr)\|([^|}]+)\|[^}]*\}\}", r"\1", t)
    t = re.sub(r"\{\{[Rr]ef\|[^}]*\}\}", "", t)
    t = re.sub(r"\{\{[^}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]", r"\1", t)
    t = re.sub(r"'''?", "", t)
    if "|" in t and ("align" in t or "style" in t):
        t = t.split("|", 1)[1]
    # the champion's mark is not part of his name
    t = re.sub(r"\s*\((?:c|ic|interim)\)\s*$", "", t.strip())
    return t.strip()


def slug(name):
    t = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def surname(n):
    b = [x for x in n.split() if not re.match(r"^(Jr\.?|Sr\.?|II|III|IV)$", x)]
    return b[-1] if b else n


def links(cell):
    m = re.search(r"\[\[([^|\]]+)", cell)
    return m.group(1) if m else ""


def events(w):
    """Every card on the page: name, date, and its bouts in card order."""
    out = []
    parts = re.split(r"\n==\s*([^=\n]+?)\s*==\s*\n", w)
    for i in range(1, len(parts), 2):
        head, body = parts[i], parts[i + 1]
        if not re.search(r"Zuffa Boxing \d+|\bvs\.", head):
            continue
        # a big night has its own article, and the section only points at it
        mm = re.search(r"\{\{[Mm]ain\|([^}|]+)", body)
        if mm and "fight date" not in body:
            body = wiki(mm.group(1).strip())
        # both ways of writing it: "September 26, 2026" and "11 April 2026"
        dm = re.search(r"\|\s*fight date\s*=\s*([A-Z][a-z]+ \d{1,2}, \d{4}|\d{1,2} [A-Z][a-z]+ \d{4})", body)
        if not dm:
            continue
        ds = dm.group(1)
        date = dt.datetime.strptime(ds, "%B %d, %Y" if "," in ds else "%d %B %Y").date()
        num = re.match(r"Zuffa Boxing (\d+)", head)
        rows, part = [], ""
        table = body[body.find("{|"):body.find("\n|}", body.find("{|"))] if "{|" in body else ""
        for chunk in table.split("\n|-"):
            if re.search(r"^\s*!\s*colspan", chunk, re.M):
                part = "main" if "Main" in chunk else "prelim"
                continue
            cells = [c for c in re.split(r"\n\|", "\n" + chunk.strip()) if c is not None][1:]
            if len(cells) < 4:
                continue
            a, how, b = cells[1], plain(cells[2]).lower(), cells[3]
            if how not in ("def.", "vs.", "vs", "drew", "draw", "nc", "no contest"):
                continue
            rows.append({
                "w": plain(cells[0]),
                "a": plain(a), "b": plain(b), "alink": links(a), "blink": links(b),
                "res": how,
                "method": plain(cells[4]) if len(cells) > 4 else "",
                "round": plain(cells[5]) if len(cells) > 5 else "",
                "time": plain(cells[6]) if len(cells) > 6 else "",
                "part": part})
        if not rows:
            continue
        main = rows[0]
        if num:
            eid = "zb-%02d" % int(num.group(1))
            name = "Zuffa Boxing %s: %s vs. %s" % (num.group(1).zfill(2), surname(main["a"]), surname(main["b"]))
        else:
            eid = "zb-" + slug(surname(main["a"]) + "-" + surname(main["b"]))
            name = "Zuffa Boxing: %s vs. %s" % (surname(main["a"]), surname(main["b"]))
        out.append({"id": eid, "name": name, "date": date, "bouts": rows})
    return out


def dk_bouts():
    """{(man, man): (event id, start)} from DraftKings' boxing league."""
    out = {}
    d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % DK_BOXING) or {}
    for e in d.get("events") or []:
        n = e.get("name") or ""
        if " vs " not in n:
            continue
        a, b = [whoname.key(x.strip()) for x in n.split(" vs ", 1)]
        when = (e.get("startEventDate") or "")[:16]
        when = (when + "Z") if when else ""
        out[(a, b)] = (str(e["id"]), when, False)
        out[(b, a)] = (str(e["id"]), when, True)
    return out, d


def dk_ml(d, eid):
    """The moneyline on one DraftKings bout, from the league read: [(label, odds, oid)]."""
    mk = {m["id"]: m for m in d.get("markets") or [] if str(m.get("eventId")) == eid}
    got = []
    for s in d.get("selections") or []:
        m = mk.get(s.get("marketId"))
        if not m or "Moneyline" not in (m.get("name") or ""):
            continue
        od = ((s.get("displayOdds") or {}).get("american") or "").replace("−", "-")
        got.append((s.get("label") or "", od, s.get("id") or ""))
    return got


def dk_props(eid, a, b, nr):
    """The sheet's keys from DraftKings' boxing markets, both men in our
       order: KO and DEC from Fight Outcome, each round from Round Betting,
       and the distance. Boxing has no submission, so there is none."""
    rows = []
    for cat in (545, 1030):
        d = ask(None, None, "/sportscontent/dkusmd/v1/events/%s/categories/%d" % (eid, cat)) or {}
        mk = {m["id"]: m.get("name") or "" for m in d.get("markets") or []}
        for sel in d.get("selections") or []:
            od = ((sel.get("displayOdds") or {}).get("american") or "").replace("\u2212", "-")
            rows.append((mk.get(sel.get("marketId"), ""), sel.get("label") or "", od, sel.get("id") or ""))

    def find(market, test):
        for m, lab, od, oid in rows:
            if m == market and test(lab) and od:
                return [od, oid]
        return None

    def his(lab, man):
        return whoname.key(lab).startswith(whoname.key(man))

    e = {"rounds": nr}
    e["ko"] = [find("Fight Outcome", lambda l, m=m: his(l, m) and "KO" in l) for m in (a, b)]
    e["dec"] = [find("Fight Outcome", lambda l, m=m: his(l, m) and "Decision" in l) for m in (a, b)]
    e["dist"] = [find("Fight to Go the Distance", lambda l: l == "Yes")]
    e["nodist"] = [find("Fight to Go the Distance", lambda l: l == "No")]
    for n in range(1, nr + 1):
        e["rd%d" % n] = [find("Round Betting", lambda l, m=m, n=n: his(l, m) and l.endswith("Round %d" % n))
                         for m in (a, b)]
    return e


def face(link, name):
    """A man's picture from his Wikipedia article, where it has a free one."""
    if not link:
        return ""
    f = slug(name)
    path = os.path.join(FACES, f + ".jpg")
    if os.path.exists(path):
        return "box:" + f
    if DRY:
        return ""
    try:
        j = rq.get(API, params={"action": "query", "prop": "pageimages", "piprop": "thumbnail",
                                "pithumbsize": 300, "titles": link, "format": "json", "redirects": 1},
                   headers=UA, timeout=30).json()
        src = ""
        for p in ((j.get("query") or {}).get("pages") or {}).values():
            src = ((p.get("thumbnail") or {}).get("source")) or ""
        if not src:
            return ""
        r = rq.get(src, headers=UA, timeout=30)
        if r.status_code != 200:
            return ""
        os.makedirs(FACES, exist_ok=True)
        open(path, "wb").write(r.content)
        return "box:" + f
    except Exception:
        return ""


METHOD = {"UD": "Decision", "SD": "Decision", "MD": "Decision", "PTS": "Decision",
          "KO": "KO/TKO", "TKO": "KO/TKO", "RTD": "KO/TKO", "DQ": "DQ"}


def main():
    evs = events(wiki(PAGE))
    dk, dkraw = dk_bouts()
    s = pagefile.read()
    cards, fights, results, book, fprops = [], [], {}, {}, {}
    priced = 0
    for e in evs:
        start = None
        rows = []
        for k, bt in enumerate(e["bouts"]):
            bid = "%s-%02d" % (e["id"], k + 1)
            hit = dk.get((whoname.key(bt["a"]), whoname.key(bt["b"])))
            when = hit[1] if hit and hit[1][:10] >= str(e["date"] - dt.timedelta(days=1)) else ""
            if not when:
                # no clock from the book: the evening of the date, the main
                # event last, fifteen minutes a bout before it
                base = dt.datetime.combine(e["date"], dt.time(23, 0), dt.timezone.utc)
                when = (base - dt.timedelta(minutes=15 * k)).strftime("%Y-%m-%dT%H:%MZ")
            ida, idb = face(bt["alink"], bt["a"]), face(bt["blink"], bt["b"])
            rows.append([e["id"], bid, when, bt["a"], ida, bt["b"], idb, "Boxing " + bt["w"],
                         "", "", "", "", "", ""])
            if hit and bt["res"] in ("vs.", "vs"):
                ml = dk_ml(dkraw, hit[0])
                pa = [x for x in ml if whoname.key(x[0]) == whoname.key(bt["a"])]
                pb = [x for x in ml if whoname.key(x[0]) == whoname.key(bt["b"])]
                if pa and pb:
                    book[bid] = [pa[0][1], pa[0][2], pb[0][1], pb[0][2]]
                    priced += 1
            # how many rounds it is scheduled for: "-(10)" before, "2/12" for a
            # stoppage, "12" for one that went the distance
            rr = bt["round"] or ""
            sched = re.search(r"\((\d+)\)|/(\d+)|^(\d+)$", rr)
            sched = int(next(x for x in sched.groups() if x)) if sched else 12
            fmt = {"regulation": {"periods": sched, "clock": 180}}
            # the sheet and the rail read a bout's length from FPROPS, and
            # its props where DraftKings has them
            fprops[bid] = {"rounds": sched}
            if hit and bt["res"] in ("vs.", "vs"):
                fprops[bid] = dk_props(hit[0], bt["a"], bt["b"], sched)
            if bt["res"] in ("vs.", "vs"):
                # not fought yet: the page still draws its rounds from here
                results.setdefault(e["id"], []).append({
                    "id": bid, "format": fmt,
                    "status": {"type": {"state": "pre"}, "period": 0},
                    "competitors": []})
            else:
                rd = re.match(r"(\d+)", rr)
                results.setdefault(e["id"], []).append({
                    "format": fmt,
                    "id": bid,
                    "status": {"type": {"state": "post", "completed": True},
                               "period": int(rd.group(1)) if rd else 0,
                               "displayClock": bt["time"] or ""},
                    "competitors": [
                        {"winner": bt["res"] == "def.", "athlete": {"displayName": bt["a"]}},
                        {"winner": False, "athlete": {"displayName": bt["b"]}}],
                    "details": [{"type": {"text": "Unofficial Winner " + METHOD.get(bt["method"].upper(), bt["method"])}}]
                               if bt["res"] == "def." else [],
                    "how": {"type": (bt["method"] or ("DRAW" if "dr" in bt["res"] else "NC")).upper(),
                            "round": rd.group(1) if rd else "", "time": bt["time"] or ""}})
            start = min(start, when) if start else when
        # the card's own clock is its first bout's, the way a UFC card's is
        cards.append([0, e["id"], start, e["name"]])
        # main event first on the page, as Wikipedia lists it
        fights.extend(rows)

    print("boxing: %d cards, %d bouts, %d priced, %d results"
          % (len(cards), len(fights), priced,
             sum(1 for v in results.values() for c in v if c["status"]["type"]["state"] == "post")))
    if DRY:
        for c in cards[-3:]:
            print("   ", c)
        return 0

    for eid, comps in results.items():
        json.dump({"events": [{"id": eid, "competitions": comps}]},
                  open(os.path.join(D, "site", "final", "mma-%s.json" % eid), "w"),
                  separators=(",", ":"))
    bk = pricefile.read()
    bk.setdefault("FIGHTS", {}).update(book)
    for k, v in fprops.items():
        bk.setdefault("FPROPS", {}).setdefault(k, {}).update(v)
    pricefile.write(bk)

    block = ("  var BOXCARDS = %s;\n  var BOXFIGHTS = %s;\n"
             % (json.dumps(cards, separators=(",", ":"), ensure_ascii=False),
                json.dumps(fights, separators=(",", ":"), ensure_ascii=False)))
    m = re.search(r"  var BOXCARDS = .*?;\n  var BOXFIGHTS = .*?;\n", s, re.S)
    if m:
        new = s[:m.start()] + block + s[m.end():]
    else:
        at = s.index("  var FIGHTCARDS = ")
        new = s[:at] + block + s[at:]
    if new != s and not pagefile.write(new):
        print("page changed under us, nothing written")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
