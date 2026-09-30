"""Every fought bout's closing line and props, from bestfightodds.com's
   archive (Jose, Sep 30, 2026: the old fights had no moneyline and the paid
   sheet had no prices to pay).

   The archive keeps, for every event, each book's moneyline and its whole
   prop sheet: method, round, round-and-method, distance, double chances.
   DraftKings' own column is often empty on an old card, so a line is taken
   from the books in a fixed order (DraftKings first), and a prop takes the
   best price across the books, with the book it came from written beside it.

   How an event is found: a numbered UFC card and a Contender Series week by
   name and date; a Fight Night has no name of its own there ("UFC Vegas 121"),
   so it is reached through its main event -- the archive's page for that man
   lists his bouts with the event each was on, and the one on our date is it.
   Nothing is guessed: a bout is tied to the archive's only when both names
   match (whoname's rule, in either order), an event only when the date does.

   Jose's rule for the double chances (Sep 30, 2026): "KO or submission" is
   built from the two method rows combined, so it reads a few cents off
   "inside the distance", which keeps its own row.

   Writes data/bfo_odds.json     {bout id: {event, mu, names, ml: {book: [l, r]},
                                            props: {label: {book: price}}}}
   and fills, for a bout that is over:
       site/prices.json FPROPS   every sheet key the book left empty
       the page's FIGHTS row     the moneyline, where it had none
   Nothing DraftKings priced is touched.

       python3 build/bfo_odds.py [--dry] [--fresh]
"""
import datetime as dt
import json
import os
import re
import sys
import time
import html as H
from urllib.parse import quote_plus

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile
import prices as pricefile
import whoname
from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "bfo_odds.json")
EVENTS = os.path.join(D, "data", "bfo_events.json")
CACHE = os.path.join(D, "cache", "bfo")
NOTE = os.path.join(D, "notes", "bfo-review.md")
BASE = "https://www.bestfightodds.com"
DRY = "--dry" in sys.argv
FRESH = "--fresh" in sys.argv
NOW = dt.datetime.now(dt.timezone.utc)
# a line is taken from the first of these that priced the bout
BOOK_ORDER = ["DraftKings", "FanDuel", "BetMGM", "Caesars", "BetRivers", "BetWay", "Unibet", "Bet365", "Kalshi", "Polymarket"]
KNOWN = BOOK_ORDER + ["BetOnline", "Bovada", "Pinnacle", "Circa", "PointsBet", "SportsBet", "5Dimes", "Betway", "Intertops"]


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


# the letters that do not fold to a plain one by decomposition; the archive
# writes Sygula and Wiklacz where the board writes Syguła and Wikłacz
PLAIN = str.maketrans({"ł": "l", "Ł": "L", "ø": "o", "Ø": "O", "đ": "d", "Đ": "D", "ß": "ss", "æ": "ae", "Æ": "Ae", "œ": "oe", "Œ": "Oe"})
NAMES_F = os.path.join(D, "data", "bfo_names.json")
LEARNED = json.load(open(NAMES_F)) if os.path.exists(NAMES_F) else {}


def nkey(n):
    """whoname's key, the archive's plain letters folded the same way, and a
       spelling the archive is known to use taken back to the board's."""
    n = LEARNED.get(str(n or ""), n)
    return whoname.key(str(n or "").translate(PLAIN))


def squash(n):
    return re.sub(r"[^a-z]", "", nkey(n))


def turned(n):
    return " ".join(sorted(nkey(n).split()))


def get(path, days=None):
    """A page of the archive, kept in cache/bfo/. An event that is over never
       changes, so its page is fetched once; a fighter's page and a search
       are kept a day."""
    os.makedirs(CACHE, exist_ok=True)
    f = os.path.join(CACHE, re.sub(r"[^A-Za-z0-9._-]+", "_", path.strip("/"))[:150] + ".html")
    if os.path.exists(f) and not FRESH:
        if days is None or time.time() - os.path.getmtime(f) < days * 86400:
            return open(f).read()
    r = rq.get(BASE + path, impersonate="chrome", timeout=40)
    time.sleep(0.6)
    if r.status_code != 200:
        return ""
    open(f, "w").write(r.text)
    return r.text


def text(x):
    return H.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", x))).strip()


MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def when(s):
    """'Sep 26th 2026' as a date."""
    m = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* (\d{1,2})(?:st|nd|rd|th)? (\d{4})", s or "")
    if not m:
        return None
    return dt.date(int(m.group(3)), MONTHS[m.group(1).lower()], int(m.group(2)))


def near(a, b):
    """The same night: the archive writes the US date, the board writes UTC."""
    return a and b and abs((a - b).days) <= 1


# ---- finding the event ---------------------------------------------------

def search_events(q):
    """[(slug path, date, name)] the archive answers a query with."""
    s = get("/search?query=" + quote_plus(q), days=1)
    out = []
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        row = m.group(1)
        ev = re.search(r'href="(/events/[^"]+)"', row)
        if not ev:
            continue
        out.append((ev.group(1), when(text(row)), text(re.search(r'<a href="/events/[^"]+"[^>]*>(.*?)</a>', row, re.S).group(1))))
    return out


def search_fighters(q):
    """[(fighter path, name)] the archive answers a query with."""
    s = get("/search?query=" + quote_plus(q), days=1)
    out = []
    for m in re.finditer(r'<a href="(/fighters/[^"]+)"[^>]*>(.*?)</a>', s, re.S):
        out.append((m.group(1), text(m.group(2))))
    return out


def fighter_events(path):
    """[(event path, date)] down a fighter's page."""
    s = get(path, days=1)
    out = []
    for m in re.finditer(r"<tr[^>]*>(.*?)</tr>", s, re.S):
        row = m.group(1)
        ev = re.search(r'href="(/events/[^"]+)"', row)
        d = when(text(row))
        if ev and d:
            out.append((ev.group(1), d))
    return out


def event_query(name):
    """What to ask the archive for a card that has a name of its own there."""
    m = re.match(r"^(UFC \d{3})\b", name)
    if m:
        return m.group(1)
    m = re.match(r"^Dana White's Contender Series: Season \d+, Week (\d+)", name)
    if m:
        return "DWCS Week %s" % m.group(1)
    return None


def find_event(eid, name, date, main):
    """The archive's path for our card, or None with the reason."""
    # through the main event first: the man's own page names the card he was
    # on, and that page is the whole card (UFC 324 by name was a stub of three
    # moved bouts; the card was under another number)
    for who in (main[3], main[5]):
        for path, d in events_of(who, date):
            return path, "via " + who
    q = event_query(name)
    if q:
        for path, d, nm in search_events(q):
            if near(d, date):
                return path, "by name"
    return None, "not in the archive by name or by %s / %s" % (main[3], main[5])


def events_of(who, date):
    """The archive's event pages a man fought on, on our date."""
    out = []
    for fpath, fname in search_fighters(who):
        if nkey(fname) != nkey(who):
            continue
        for path, d in fighter_events(fpath):
            if near(d, date) and path not in [x[0] for x in out]:
                out.append((path, d))
    return out


# ---- reading the event ---------------------------------------------------

def book_of(th):
    t = text(th)
    for k in KNOWN:
        if k.lower() in t.lower():
            return k
    return t.split(" ")[0] if t else ""


def parse_event(s):
    """[{mu, names: [a, b], ml: {book: [a, b]}, props: {label: {book: price}}}]"""
    tables = re.findall(r'<table class="odds-table"[^>]*>(.*?)</table>', s, re.S)
    if not tables:
        return []
    main = max(tables, key=len)
    head = re.search(r"<thead>(.*?)</thead>", main, re.S)
    books = [book_of(t) for t in re.findall(r"<th[^>]*>(.*?)</th>", head.group(1), re.S)] if head else []
    # the table is several bodies, one a matchup: all of them, in order
    bodies = re.findall(r"<tbody>(.*?)</tbody>", main, re.S)
    body = "".join(bodies) if bodies else main
    out, cur = [], None
    for attrs, row in re.findall(r"<tr([^>]*)>(.*?)</tr>", body, re.S):
        th = re.search(r"<th[^>]*>(.*?)</th>", row, re.S)
        label = text(th.group(1)) if th else ""
        # a man's row names him in his own link; the archive's own edit link
        # sits in front of it with a number
        who = re.search(r'<a href="/fighters/[^"]+"[^>]*>(.*?)</a>', th.group(1), re.S) if th else None
        if who:
            label = text(who.group(1))
        cells = re.findall(r"<td([^>]*)>(.*?)</td>", row, re.S)
        vals = {}
        for i, (a, c) in enumerate(cells):
            v = re.search(r'<span id="oID\d+"[^>]*>([^<]*)</span>', c)
            b = books[i + 1] if i + 1 < len(books) else ""
            if v and b and re.match(r"^[+-]\d+$", v.group(1).strip()):
                vals[b] = v.group(1).strip()
        if 'class="pr"' in attrs:
            if cur and label:
                # the same label can repeat (a book's own split rows): the first wins
                slot = cur["props"].setdefault(label, {})
                for b, v in vals.items():
                    slot.setdefault(b, v)
            continue
        if not who:
            continue
        # the men come in pairs, the props under them; the matchup's number is
        # on the row or in the archive's own edit link, when it is anywhere
        mu = re.search(r'id="mu-(\d+)"', attrs) or re.search(r"/matchups/(\d+)", row)
        if cur is None or cur["names"][1]:
            cur = {"mu": mu.group(1) if mu else "", "names": [label, ""], "ml": {}, "props": {}}
            out.append(cur)
            for b, v in vals.items():
                cur["ml"].setdefault(b, ["", ""])[0] = v
        else:
            cur["names"][1] = label
            for b, v in vals.items():
                cur["ml"].setdefault(b, ["", ""])[1] = v
    return [m for m in out if m["names"][1]]


# ---- prices ---------------------------------------------------------------

def prob(o):
    n = int(o)
    return 100.0 / (n + 100) if n > 0 else -n / (-n + 100.0)


def american(p):
    if p <= 0 or p >= 1:
        return ""
    if p >= 0.5:
        return "-%d" % round(100 * p / (1 - p))
    return "+%d" % round(100 * (1 - p) / p)


def dec(o):
    n = int(o)
    return 1 + n / 100.0 if n > 0 else 1 + 100.0 / -n


def combine(a, b):
    """Two outcomes that cannot both happen, priced together, book by book."""
    out = {}
    for bk in a:
        if bk in b:
            out[bk] = american(prob(a[bk]) + prob(b[bk]))
    return {k: v for k, v in out.items() if v}


def best(slot):
    """The longest price a book gave, and the book: [price, "", book]."""
    if not slot:
        return None
    bk = max(slot, key=lambda k: dec(slot[k]))
    return [slot[bk], "", bk]


def side_of(label, names):
    """Which man a prop row names, by the way the archive writes him: his
       surname, or the whole name. Blank when both could be meant."""
    lk = nkey(label)
    hits = []
    for i, n in enumerate(names):
        k = nkey(n)
        toks = k.split()
        cands = {k}
        if toks:
            cands.add(toks[-1])
            if len(toks) > 1:
                cands.add(" ".join(toks[-2:]))
        if any(lk.startswith(c + " ") for c in cands if c):
            hits.append(i)
    return hits[0] if len(hits) == 1 else None


def sheet_from(mu, flip):
    """The sheet's keys from the archive's rows, best book each, [left, right]
       as the board's row has the two men (flip: the archive has them the
       other way round)."""
    names = mu["names"]
    P = mu["props"]
    per = {}       # key -> [slotL, slotR] of {book: price}
    one = {}       # whole-fight key -> {book: price}

    def put(key, i, slot):
        per.setdefault(key, [{}, {}])
        per[key][i] = slot

    for label, slot in P.items():
        i = side_of(label, names)
        lk = nkey(label)
        if i is not None:
            rest = lk.split(" ", 1)[1] if " " in lk else ""
            # take the man's whole name off the front, however many words
            for n in (names[i],):
                nk = nkey(n)
                for cand in sorted({nk, nk.split()[-1], " ".join(nk.split()[-2:])}, key=len, reverse=True):
                    if lk.startswith(cand + " "):
                        rest = lk[len(cand) + 1:]
                        break
            m = re.match(r"^wins by tko ko in round (\d)$", rest)
            if m: put("kord" + m.group(1), i, slot); continue
            m = re.match(r"^wins by submission in round (\d)$", rest)
            if m: put("subrd" + m.group(1), i, slot); continue
            m = re.match(r"^wins in round (\d)$", rest)
            if m: put("rd" + m.group(1), i, slot); continue
            if rest == "wins by tko ko": put("ko", i, slot); continue
            if rest == "wins by submission": put("sub", i, slot); continue
            if rest == "wins by decision": put("dec", i, slot); continue
            if rest == "wins by unanimous decision": put("ud", i, slot); continue
            if rest == "wins by split majority decision": put("sdmd", i, slot); continue
            if rest == "wins in round 1 or 2": put("rd12", i, slot); continue
            if rest == "wins in round 3 or 4": put("rd34", i, slot); continue
            if rest == "wins in final round or by decision": put("rdlastdec", i, slot); continue
            if rest == "wins inside distance": put("inside", i, slot); continue
            continue
        m = re.match(r"^fight ends in tko ko dq in round (\d)$", lk)
        if m: one["anykord" + m.group(1)] = slot; continue
        m = re.match(r"^fight ends in submission in round (\d)$", lk)
        if m: one["anysubrd" + m.group(1)] = slot; continue
        if lk == "fight goes to decision": one["dist"] = slot; one["anydec"] = slot; continue
        if lk == "fight doesn t go to decision" or lk == "fight doesn t go to decision": one["nodist"] = slot; continue
        if lk == "either fighter wins by tko ko": one["anyko"] = slot; continue
        if lk == "either fighter wins by submission": one["anysub"] = slot; continue
        if lk == "fight ends within 0 01 1 00 of round 1": one["first60"] = slot; continue
        if lk == "fight is a draw": one["draw"] = slot; continue
    # the double chances, from the method rows combined (Jose's rule)
    for key, a, b in (("kosub", "ko", "sub"), ("kodec", "ko", "dec"), ("subdec", "sub", "dec")):
        if a in per and b in per:
            per[key] = [combine(per[a][0], per[b][0]), combine(per[a][1], per[b][1])]
    per.pop("inside", None)
    e = {}
    for key, pair in per.items():
        if flip:
            pair = pair[::-1]
        e[key] = [best(pair[0]), best(pair[1])]
    for key, slot in one.items():
        e[key] = [best(slot)]
    rounds = 5 if any(k.endswith("5") for k in list(per) + list(one)) else 3
    e["rounds"] = rounds
    return e


def line_of(mu, flip):
    """The closing moneyline, from the first book in BOOK_ORDER that has both
       sides: [left, right, book]."""
    for bk in BOOK_ORDER + sorted(mu["ml"]):
        pair = mu["ml"].get(bk)
        if pair and pair[0] and pair[1]:
            l, r = (pair[1], pair[0]) if flip else (pair[0], pair[1])
            return [l, r, bk]
    return None


# ---- the run -----------------------------------------------------------------

def main():
    s = pagefile.read()
    fights = json.loads(re.search(r"  var FIGHTS = (\[\[.*?\]\]);", s, re.S).group(1))
    cards = json.loads(re.search(r"  var FIGHTCARDS = (\[\[.*?\]\]);", s, re.S).group(1))
    evmap = json.load(open(EVENTS)) if os.path.exists(EVENTS) else {}
    have = json.load(open(OUT)) if os.path.exists(OUT) and not FRESH else {}
    report = {"events": [], "bouts": 0, "matched": 0, "lines": 0, "props": 0, "untied": [], "noevent": [], "learned": []}
    by_event = {}
    for f in fights:
        by_event.setdefault(str(f[0]), []).append(f)
    for wk, eid, start, name in cards:
        eid = str(eid)
        if eid.startswith("zb-") or T(start) > NOW - dt.timedelta(hours=6):
            continue                                    # boxing is not in the archive; a card still to come is DraftKings'
        bouts = [f for f in by_event.get(eid, []) if f[3] and f[5] and "TBA" not in (f[3] + f[5])]
        if not bouts:
            continue
        # a card every bout of which is already on record is not read again:
        # the sweep runs this three times a day and only a new card is news
        if not FRESH and all(str(f[1]) in have for f in bouts):
            report["events"].append("%s: on record, %d bouts" % (name, len(bouts)))
            report["bouts"] += len(bouts)
            report["matched"] += len(bouts)
            continue
        date = T(start).date()
        # the main event is the bout the card is named after; failing that
        # the last to start
        named = [f for f in bouts if all(nkey(x).split()[-1] in nkey(name).split() for x in (f[3], f[5]) if nkey(x))]
        main_bout = named[0] if named else max(bouts, key=lambda f: f[2])
        path, how = evmap.get(eid, {}).get("path"), evmap.get(eid, {}).get("how")
        if not path:
            path, how = find_event(eid, name, date, main_bout)
            if path:
                evmap[eid] = {"path": path, "how": how, "name": name}
        if not path:
            report["noevent"].append("%s (%s): %s" % (name, date, how))
            continue
        paths = list(dict.fromkeys([path] + evmap[eid].get("paths", [])))
        mus = []
        for pth in paths:
            mus += parse_event(get(pth))

        def tie(f, mus):
            """The archive's matchup for our bout: both names by the rules
               (as written, letters run together, word order aside), or one
               man certain and the other the only other man in that bout,
               his spelling learned. Never a near miss."""
            for rule in (nkey, squash, turned):
                for mu in mus:
                    a, b = rule(mu["names"][0]), rule(mu["names"][1])
                    if (a, b) == (rule(f[3]), rule(f[5])):
                        return mu, False, None
                    if (a, b) == (rule(f[5]), rule(f[3])):
                        return mu, True, None
            def kin(x, y):
                """the same man written two ways shares a name; two men who
                   share none are a replacement, and the archive's bout is
                   another fight (Jose Ochoa was not Eduardo Chapolin)"""
                return bool(set(nkey(x).split()) & set(nkey(y).split()))
            for mu in mus:
                a, b = nkey(mu["names"][0]), nkey(mu["names"][1])
                for flip, (l, r) in ((False, (f[3], f[5])), (True, (f[5], f[3]))):
                    if a == nkey(l) and b != nkey(r) and kin(mu["names"][1], r) and not any(nkey(x[3]) == b or nkey(x[5]) == b for x in bouts):
                        return mu, flip, (mu["names"][1], r)
                    if b == nkey(r) and a != nkey(l) and kin(mu["names"][0], l) and not any(nkey(x[3]) == a or nkey(x[5]) == a for x in bouts):
                        return mu, flip, (mu["names"][0], l)
            return None, False, None

        got, missing = 0, []
        for f in bouts:
            report["bouts"] += 1
            mu, flip, learned = tie(f, mus)
            if not mu:
                missing.append(f)
                continue
            if learned:
                LEARNED[learned[0]] = learned[1]
                report["learned"].append("%s -> %s (%s)" % (learned[0], learned[1], name))
            got += 1
            report["matched"] += 1
            have[str(f[1])] = {"event": paths[0], "mu": mu["mu"], "names": mu["names"], "flip": flip,
                               "date": str(date), "ml": mu["ml"], "props": mu["props"]}
        # a bout not on that page may be on another page of the same night
        # (the archive splits some cards): its own men's pages say where
        for f in missing:
            found = None
            mu, flip, learned = tie(f, mus)
            if mu:
                found = (mu, flip, learned, paths[-1])
            for who in ((f[3], f[5]) if not found else ()):
                for pth, d in events_of(who, date):
                    if pth in paths:
                        continue
                    paths.append(pth)
                    evmap[eid]["paths"] = paths[1:]
                    mus += parse_event(get(pth))
                    mu, flip, learned = tie(f, mus)
                    if mu:
                        found = (mu, flip, learned, pth)
                        break
                if found:
                    break
            if not found:
                report["untied"].append("%s: %s v %s" % (name, f[3], f[5]))
                continue
            mu, flip, learned, pth = found
            if learned:
                LEARNED[learned[0]] = learned[1]
                report["learned"].append("%s -> %s (%s)" % (learned[0], learned[1], name))
            got += 1
            report["matched"] += 1
            have[str(f[1])] = {"event": pth, "mu": mu["mu"], "names": mu["names"], "flip": flip,
                               "date": str(date), "ml": mu["ml"], "props": mu["props"]}
        report["events"].append("%s: %s, %d of %d bouts (%s)" % (name, ", ".join(paths), got, len(bouts), how))
    # ---- what the board is missing ----
    book = pricefile.read()
    changed_rows = 0
    for f in fights:
        rec = have.get(str(f[1]))
        if not rec or T(f[2]) > NOW - dt.timedelta(hours=6):
            continue
        mu = {"names": rec["names"], "ml": rec["ml"], "props": rec["props"]}
        flip = rec["flip"]
        # the moneyline, where the row has none
        if len(f) > 10 and not f[8] and not f[10]:
            ln = line_of(mu, flip)
            if ln:
                f[8], f[10] = ln[0], ln[1]
                book["FIGHTS"][str(f[1])] = [f[8], "", f[10], ""]
                changed_rows += 1
                report["lines"] += 1
        # the sheet, every key the book left empty
        e = sheet_from(mu, flip)
        fp = book["FPROPS"].setdefault(str(f[1]), {})
        fp.setdefault("rounds", e["rounds"])
        for key, slots in e.items():
            if key == "rounds":
                continue
            cur = fp.get(key) or [None] * len(slots)
            cur = list(cur) + [None] * (len(slots) - len(cur))
            for i, slot in enumerate(slots):
                if slot and not (cur[i] and cur[i][0]):
                    cur[i] = slot
                    report["props"] += 1
            if any(cur):
                fp[key] = cur
    lines = ["# bestfightodds review, %s UTC" % NOW.strftime("%Y-%m-%d %H:%M"), "",
             "- cards read: %d; bouts on them: %d; tied to the archive: %d" % (len(report["events"]), report["bouts"], report["matched"]),
             "- moneylines filled where the row had none: %d" % report["lines"],
             "- sheet prices filled where DraftKings had none: %d" % report["props"], ""]
    if report["noevent"]:
        lines += ["## cards not found", ""] + ["- " + x for x in report["noevent"]] + [""]
    if report["learned"]:
        lines += ["## spellings learned (one man certain, the other the only other man in the bout)", ""] + ["- " + x for x in report["learned"]] + [""]
    if report["untied"]:
        lines += ["## bouts not tied (names differ; never guessed)", ""] + ["- " + x for x in report["untied"]] + [""]
    lines += ["## cards", ""] + ["- " + x for x in report["events"]]
    print("\n".join(lines))
    if DRY:
        print("dry run -- nothing written")
        return 0
    os.makedirs(os.path.dirname(NOTE), exist_ok=True)
    open(NOTE, "w").write("\n".join(lines) + "\n")
    json.dump(evmap, open(EVENTS, "w"), indent=1, sort_keys=True)
    json.dump(LEARNED, open(NAMES_F, "w"), indent=1, sort_keys=True, ensure_ascii=False)
    json.dump(have, open(OUT, "w"), separators=(",", ":"), sort_keys=True)
    pricefile.write(book)
    if changed_rows:
        m = re.search(r"  var FIGHTS = (\[\[.*?\]\]);", s, re.S)
        s2 = s[:m.start(1)] + json.dumps(fights, separators=(",", ":"), ensure_ascii=False) + s[m.end(1):]
        print("page: %d rows given a line" % changed_rows if pagefile.write(s2) else "page moved under us, not written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
