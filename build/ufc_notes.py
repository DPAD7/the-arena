"""Missed weight and short notice, per UFC bout, off each event's Wikipedia page.

Nothing else the board reads carries them: ESPN's bout has no weigh-in and no
booking date. Each UFC event's Wikipedia article writes both into its bout
notes -- "At the weigh-ins, Esteban Ribovics weighed in at 156.5 pounds, half
a pound over the lightweight non-title fight limit" (UFC 332), and "... was
replaced by X on short notice". The record hold puts them on the fight's own
row and on the NEXT row (Jose, Oct 8, 2026: "why are they missing?").

Events are listed off "List of UFC events"; an event's page is read once and
kept in data/ufc_records/notes.json, except the ones within two weeks either
side of today, which are read again every run -- that is when the weigh-ins
and the late changes are written.

    python3 build/ufc_notes.py      -> data/ufc_records/notes.json
"""
import json, os, re, sys, time, unicodedata
from datetime import date, datetime, timedelta
from curl_cffi import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "ufc_records", "notes.json")
API = "https://en.wikipedia.org/w/api.php"
UA = {"User-Agent": "the-arena/1.0 (https://the-arenasports.pages.dev)"}
MON = {m: i for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split(), 1)}
WORDS = {"half a": 0.5, "a half": 0.5, "one": 1, "a": 1, "two": 2, "three": 3, "four": 4, "five": 5,
         "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}


def ln(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower().replace(".", "").replace("-", " ")
    p = [w for w in x.split() if w not in ("jr", "sr", "ii", "iii")]
    return p[-1] if p else ""


def get(params):
    for i in range(4):
        try:
            r = requests.get(API, params=dict(params, format="json", formatversion=2), headers=UA, timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(2 + 3 * i)
    return None


def events():
    """(date, page title) for every UFC event since 2010, held and scheduled"""
    d = get({"action": "parse", "page": "List of UFC events", "prop": "wikitext"})
    t = (d or {}).get("parse", {}).get("wikitext", "")
    out = []
    for m in re.finditer(r"\|\s*\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*\n\|\s*\{\{dts\|(\d{4})\|(\w{3})\w*\|(\d{1,2})\}\}", t):
        title, y, mo, dd = m.groups()
        if not title.startswith("UFC") or mo[:3] not in MON:
            continue
        out.append(("%s-%02d-%02d" % (y, MON[mo[:3]], int(dd)), title.strip()))
    return [e for e in out if e[0] >= "2010-01-01"]


def links(s):
    return [(m.start(), (m.group(2) or m.group(1)).strip()) for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", s)]


def plain(s):
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    return re.sub(r"\{\{[^{}]*\}\}", "", s)


def pounds(s):
    m = re.search(r"((?:\d+(?:\.\d+)?)|half a|a half|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|a)"
                  r"(?: and (?:a )?half| and a quarter)? pounds? over", s, re.I)
    if not m:
        return None
    w = m.group(1).lower()
    v = float(w) if re.match(r"\d", w) else WORDS.get(w, 1)
    if re.search(r" and (?:a )?half pounds? over", m.group(0), re.I):
        v += 0.5
    return ("%g" % v)


NAME = r"([A-Z][\w'\u2019.-]+(?: (?:[A-Z][\w'\u2019.-]+|de|da|dos|do|van|von|el|al))*)"


def shown(s):
    """the text as read: a link is its shown words"""
    return re.sub(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]", r"\1", s)


def notes_of(text):
    """{last name: {"mw": "0.5"} / {"rp": 1}} for one event's article: who
       missed weight and by how much, and who came in as a replacement"""
    out = {}
    for para in plain(text).split("\n"):
        for s in re.split(r"(?<=[a-z\]][.])\s+(?=[A-Z\[])", para):
            t = shown(s)
            low = t.lower()
            i = low.find("weighed in at")
            if i > 0 and " over" in low:
                m = re.search(NAME + r"\s*(?:\([^)]*\))?\s*$", t[:i].strip())
                lb = pounds(t)
                if m and lb:
                    out.setdefault(ln(m.group(1)), {})["mw"] = lb
            for m in re.finditer(r"replaced by (?:[^A-Z,.]*?)" + NAME, t):
                out.setdefault(ln(m.group(1)), {})["rp"] = 1
            if "short notice" in low or "late notice" in low:
                m = re.search(NAME + r"[^.]*?(?:stepped in|agreed|accepted|took the (?:bout|fight))", t)
                if m:
                    out.setdefault(ln(m.group(1)), {})["rp"] = 1
    return out


def booked(title, surname, on):
    """the day the event's page first named him: the edits are walked by
       halves, so a page of five hundred edits is read nine times"""
    r = get({"action": "query", "prop": "revisions", "titles": title, "rvprop": "ids|timestamp",
             "rvlimit": 500, "rvstart": on + "T23:59:59Z", "redirects": 1})
    try:
        revs = list(reversed(r["query"]["pages"][0]["revisions"]))     # oldest first
    except Exception:
        return None
    def has(k):
        x = get({"action": "query", "prop": "revisions", "revids": revs[k]["revid"], "rvprop": "content", "rvslots": "main"})
        try:
            t = x["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
        except Exception:
            return False
        return surname in ln_all(t)
    if not revs or not has(len(revs) - 1):
        return None
    lo, hi = 0, len(revs) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if has(mid):
            hi = mid
        else:
            lo = mid + 1
    return revs[lo]["timestamp"][:10]


def ln_all(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return set(re.findall(r"[a-z]+", t))


def main():
    try:
        old = json.load(open(OUT))
    except Exception:
        old = {}
    evs = events()
    if not evs:
        print("ufc_notes: the event list did not read, the old notes kept")
        return
    today = date.today()
    near = lambda d: abs((datetime.fromisoformat(d).date() - today).days) <= 14
    want = [(d, t) for d, t in evs if t not in old or near(d)]
    for k in range(0, len(want), 40):
        chunk = want[k:k + 40]
        r = get({"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                 "redirects": 1, "titles": "|".join(t for _, t in chunk)})
        if not r:
            continue
        q = r.get("query", {})
        back = {x["to"]: x["from"] for x in q.get("redirects", []) + q.get("normalized", [])}
        for p in q.get("pages", []):
            revs = p.get("revisions") or []
            if not revs:
                continue
            title = back.get(p["title"], p["title"])
            d = next((d for d, t in chunk if t == title), None)
            if d is None:
                continue
            old[title] = {"date": d, "notes": notes_of(revs[0]["slots"]["main"]["content"])}
        time.sleep(1)
    # how many days' notice each board fighter who came in as a replacement had
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import pagefile
    F = json.loads(re.search(r"var FIGHTS = (\[\[.*?\]\]);", pagefile.read(), re.S).group(1))
    # the men on the cards still to come: their own fights are the ones the
    # record hold shows, so theirs are the replacements worth dating
    board = {ln(n) for f in F if f[2][:10] >= today.isoformat() for n in (f[3], f[5])}
    if "--dry" not in sys.argv:
        json.dump(old, open(OUT, "w"), indent=0, sort_keys=True)
    todo = [(t, w) for t, e in old.items() for w, v in e["notes"].items()
            if v.get("rp") and w in board and "days" not in v and e["date"] <= (today + timedelta(days=60)).isoformat()]
    print("ufc_notes: dating %d replacements" % len(todo), flush=True)
    for title, who in todo:
        e = old[title]; v = e["notes"][who]
        b = booked(title, who, e["date"])
        v["days"] = (datetime.fromisoformat(e["date"]) - datetime.fromisoformat(b)).days if b else None
    if "--dry" not in sys.argv:
        json.dump(old, open(OUT, "w"), indent=0, sort_keys=True)
    mw = sum(1 for e in old.values() for v in e["notes"].values() if "mw" in v)
    rp = sum(1 for e in old.values() for v in e["notes"].values() if "rp" in v)
    sn = sum(1 for e in old.values() for v in e["notes"].values() if v.get("days") is not None and v["days"] <= 21)
    print("ufc_notes: %d events, %d missed weight, %d replacements, %d short notice on the board (%d read now)" % (len(old), mw, rp, sn, len(want)))


if __name__ == "__main__":
    main()
