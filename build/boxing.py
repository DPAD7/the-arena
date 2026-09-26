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
import html
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

    def find_any(test):
        for m, lab, od, oid in rows:
            if m.startswith("Round Group Betting") and test(lab) and od:
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
    e["draw"] = [find("Fight Outcome", lambda l: l == "Draw")]
    # the round groups, however the book cuts them: 1-2 and 3-4 on a short
    # bout, 1-3 or 1-4 on a twelve-rounder
    spans = sorted({tuple(map(int, re.search(r"Rounds (\d+)-(\d+)", lab).groups()))
                    for m, lab, od, oid in rows
                    if m.startswith("Round Group Betting") and re.search(r"Rounds (\d+)-(\d+)", lab)})
    for lo, hi in spans:
        e["rg%d-%d" % (lo, hi)] = [find_any(lambda l, m=m, lo=lo, hi=hi: his(l, m) and l.endswith("Rounds %d-%d" % (lo, hi)))
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


def ufc_results(num):
    """Zuffa's own results page on UFC.com, written live at ringside: each
       "A defeats B via TKO - Round 3, 2:12" line as it lands. The official
       word, and faster than Wikipedia (Jose, Sep 26, 2026: "we don't have
       another credible source?")."""
    try:
        t = rq.get("https://www.ufc.com/news/zuffa-boxing-%s-results" % num,
                   impersonate="chrome124", timeout=30).text
    except Exception:
        return []
    tx = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t))
    out = []
    for m in re.finditer(r"([A-Z][\w'.\- ]+?) (?:defeats|def\.) ([A-Z][\w'.\- ]+?) via ([A-Za-z ]+?)(?: \((?:[^)]*)\))?(?: [\u2013\-] Round (\d+)(?:, (\d+:\d\d))?)?(?= |$)", tx):
        a, b, how = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        # the weight class sits before the names: "Cruiserweight: Rogelio Romero"
        a = a.split(": ")[-1]
        short = {"TKO": "TKO", "KO": "KO", "Unanimous Decision": "UD", "Split Decision": "SD",
                 "Majority Decision": "MD", "Disqualification": "DQ", "Corner Retirement": "RTD"}
        first = how.lower().split()[0] if how else ""
        how = {"unanimous": "UD", "split": "SD", "majority": "MD", "decision": "DEC", "points": "PTS",
               "technical": "TD", "disqualification": "DQ", "corner": "RTD"}.get(first) or \
              next((v for k, v in short.items() if how.lower().startswith(k.lower())), how.upper()[:4])
        out.append({"w": a, "l": b, "how": how, "rd": m.group(4) or "", "time": m.group(5) or ""})
    for m in re.finditer(r"([A-Z][\w'.\- ]+?) vs\.? ([A-Z][\w'.\- ]+?) (?:ends in a|declared a) (draw|no contest)", tx, re.I):
        out.append({"w": "", "a": m.group(1).split(": ")[-1].strip(), "b": m.group(2).strip(), "how": m.group(3).upper()})
    return out


TAP = "https://www.tapology.com"


def tap_get(path):
    """Tapology turns a Chrome fingerprint away and answers Safari's."""
    try:
        return rq.get(TAP + path, impersonate="safari17_2_ios", timeout=30).text
    except Exception:
        return ""


def tap_events():
    """Each Zuffa card's Tapology page, keyed the way the board keys them:
       {"zb-02": "/fightcenter/events/138880-...", "zb-garcia-benn": ...}."""
    t = tap_get("/fightcenter/promotions/6299-zuffa-boxing-zb")
    out = {}
    for href, alt in re.findall(r'href="(/fightcenter/events/\d+-[^"]+)".{0,6000}?<img alt=\'([^\']+)\' class=\'w-\[65px\]', t, re.S):
        m = re.match(r"Zuffa Boxing (\d+)$", alt.strip())
        if m:
            out.setdefault("zb-%02d" % int(m.group(1)), href)
        else:
            m = re.match(r"(?:Zuffa Boxing:\s*)?(\S+) vs\.? (\S+)$", alt.strip())
            if m:
                out.setdefault(("zb-%s-%s" % m.groups()).lower(), href)
    return out


def _named(words):
    """The man after a W or an L: Tapology writes his name twice ("Jalil
       Hackett Jalil Hackett", or "Radivoje Kalajdzic R. Kalajdzic"), so the
       name is the words up to where his surname comes round again."""
    for k in range(2, min(6, len(words))):
        if words[k:2 * k] == words[:k]:
            return " ".join(words[:k])
    for k in range(2, min(6, len(words))):
        if words[k - 1] in words[k:k + 4]:
            return " ".join(words[:k])
    return " ".join(words[:2])


def tap_results(path):
    """Every finished bout on a Tapology card: winner, loser, how, round,
       clock (Jose, Sep 26, 2026: "we have the results on there too")."""
    t = tap_get(path)
    tx = html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", t)))
    out = []
    pat = (r"(?P<how>(?:Decision|KO/TKO|TKO|KO|DQ|Disqualification|Technical Decision|Corner Stoppage)[^0-9]*?) "
           r"(?:(?P<clk>\d+:\d\d) Round (?P<rd>\d+) of \d+|\d+ Rounds), [\d:]+ Total (?:\d+ )?W (?P<rest>.{0,300})")
    for m in re.finditer(pat, tx):
        rest = m.group("rest")
        if " L " not in rest:
            continue
        w = _named(rest.split(" L ", 1)[0].split())
        l = _named(rest.split(" L ", 1)[1].split())
        how = m.group("how").strip().rstrip(",")
        low = how.lower()
        code = ("UD" if "unanimous" in low else "SD" if "split" in low else "MD" if "majority" in low else
                "DEC" if low.startswith("decision") else "DQ" if "dq" in low or "disq" in low else
                "RTD" if "corner" in low else "TD" if low.startswith("technical") else
                "KO" if low.startswith("ko/tko") and "punch" not in low and False else
                "TKO" if "tko" in low else "KO")
        r = {"w": w, "l": l, "how": code, "rd": m.group("rd") or "", "time": m.group("clk") or ""}
        if r not in out:
            out.append(r)
    # a draw is "D" on both men, a no contest "N" ("Overturned to No Contest")
    for m in re.finditer(r"(Ends in a Draw|No Contest)[^D N]*?.{0,80}? (?P<k>[DN]) (?P<rest>.{0,300})", tx):
        k, rest = m.group("k"), m.group("rest")
        if (" %s " % k) not in rest:
            continue
        a_, b_ = rest.split(" %s " % k, 1)
        r = {"w": "", "a": _named(a_.split()), "b": _named(b_.split()), "how": "DRAW" if k == "D" else "NC"}
        if r not in out:
            out.append(r)
    return out


def settle(bt, r):
    """One result laid onto one of our bouts, winner first."""
    ka = whoname.key(bt["a"])
    wa = whoname.key(r.get("w") or r.get("a") or "")
    if not r.get("w"):
        bt["res"] = "drew" if "DRAW" in r["how"] else "nc"
    elif wa == ka or surname(r["w"]).lower() == surname(bt["a"]).lower():
        bt["res"] = "def."
    else:
        bt["a"], bt["b"], bt["alink"], bt["blink"] = bt["b"], bt["a"], bt["blink"], bt["alink"]
        bt["res"] = "def."
    # the scheduled length stays: "3/8" for a stoppage in the third of eight
    sch = re.search(r"\((\d+)\)|/(\d+)|^(\d+)$", bt.get("round") or "")
    sch = next((x for x in sch.groups() if x), "") if sch else ""
    rd = r.get("rd") or ""
    bt["round"] = (rd + "/" + sch) if rd and sch else (sch or rd or bt.get("round") or "")
    bt["method"], bt["time"] = r["how"], r.get("time") or ""


def same_bout(bt, r):
    ka, kb = whoname.key(bt["a"]), whoname.key(bt["b"])
    wa, wl = whoname.key(r.get("w") or r.get("a") or ""), whoname.key(r.get("l") or r.get("b") or "")
    if {ka, kb} == {wa, wl}:
        return True
    # Tapology shortens a long name ("R. Kalajdzic"): both surnames will do
    sa, sb = surname(bt["a"]).lower(), surname(bt["b"]).lower()
    sw, sl = surname(r.get("w") or r.get("a") or "").lower(), surname(r.get("l") or r.get("b") or "").lower()
    return {sa, sb} == {sw, sl}


def main():
    evs = events(wiki(PAGE))
    # the promoter's own results laid over Wikipedia's for any card it has
    # written: a bout it has settled takes its word
    for e in evs:
        num = re.match(r"zb-(\d+)$", e["id"])
        if not num:
            continue
        for r in ufc_results(num.group(1)):
            for bt in e["bouts"]:
                if same_bout(bt, r):
                    settle(bt, r)
    # a bout that is over and still has no result from either takes
    # Tapology's: Wikipedia leaves undercard bouts blank for months
    open_ = [e for e in evs if e["date"] <= dt.date.today() and
             any(bt["res"] in ("vs.", "vs") for bt in e["bouts"])]
    if open_:
        where = tap_events()
        for e in open_:
            if not where.get(e["id"]):
                continue
            for r in tap_results(where[e["id"]]):
                for bt in e["bouts"]:
                    if bt["res"] in ("vs.", "vs") and same_bout(bt, r):
                        settle(bt, r)
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
                # a late change of opponent: the book still lists the bout
                # under the old name, and its clock is still the bout's.
                # One man is enough for the time, never for the price.
                for (x, y), v in dk.items():
                    if (x == whoname.key(bt["a"]) or x == whoname.key(bt["b"])) and \
                            abs((dt.date.fromisoformat(v[1][:10]) - e["date"]).days) <= 1:
                        when = v[1]
                        break
            if not when:
                # no clock from the book: the evening of the date, one clock
                # for the card -- never a made-up time a bout
                when = dt.datetime.combine(e["date"], dt.time(23, 0), dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
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
        # each bout keeps the book's own start, the way the UFC bouts do
        # (Jose, Sep 26, 2026: "why are all the Zuffa Boxing at 11 AM")
        cards.append([0, e["id"], start, e["name"]])
        # prelims first and the main event last, the order a UFC card reads
        fights.extend(reversed(rows))

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
    # every bout carries its prices in its own row and its props inline, the
    # way a UFC bout does: a finished bout is never written to from the file
    # again, so one that closed after the page was built showed dashes
    # (Jose, Sep 26, 2026: "the odds are missing, but we had them before")
    held = bk.get("FIGHTS") or {}
    for r in fights:
        v = held.get(r[1])
        if v and len(v) >= 4:
            r[8], r[9], r[10], r[11] = v[0], v[1], v[2], v[3]
    boxfp = {k: v for k, v in (bk.get("FPROPS") or {}).items() if str(k).startswith("zb-")}

    block = ("  var BOXCARDS = %s;\n  var BOXFIGHTS = %s;\n  var BOXFPROPS = %s;\n"
             % (json.dumps(cards, separators=(",", ":"), ensure_ascii=False),
                json.dumps(fights, separators=(",", ":"), ensure_ascii=False),
                json.dumps(boxfp, separators=(",", ":"), ensure_ascii=False)))
    m = re.search(r"  var BOXCARDS = .*?;\n  var BOXFIGHTS = .*?;\n(?:  var BOXFPROPS = .*?;\n)?", s, re.S)
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
