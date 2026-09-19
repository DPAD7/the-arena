"""What the book charged on every UFC bout, from gidstats.com.

   They publish a closing moneyline for each bout, but not on the bout page
   and not on the event page -- it sits in a fighter's own history, one line
   per fight, as an American price and a word for it ("-125 Slight Favorite").
   So each side's price is read off that man's page, and a bout is the two of
   them put together.

   Nothing is matched by name across sources: a row on a fighter's page is
   tied to a bout by the event's own date and the opponent written on the same
   row, both of which the event page also carries. A bout whose two sides
   cannot both be read is written down as unsettled and counted, never guessed.

   Writes ufc_odds.json beside this file:

       {bout id: {"event", "date", "left", "lodds", "right", "rodds",
                  "lword", "rword"}}

   Usage:  python3 gid_ufc.py                every year they hold, Dec 2020 on
           GID_YEAR=2026 python3 gid_ufc.py    one year
           python3 gid_ufc.py --fresh        ignore the cache

   (Jose, Sep 18, 2026)
"""
import datetime as dt
import difflib
import html
import json
import os
import re
import sys
import time

from curl_cffi import requests as rq

D = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(D, "cache", "gid")
OUT = os.path.join(D, "ufc_odds.json")
# the backfill Jose asked for: the start of the year up to today. A card still
# to be fought has no closing price to read, so asking for one only counts
# misses that were never there (Jose, Sep 18, 2026)
FROM = os.environ.get("GID_FROM", "2026-01-01")
TO = os.environ.get("GID_TO", dt.date.today().isoformat())
FRESH = "--fresh" in sys.argv
PAUSE = 0.35          # their robots asks Yandex for 3s; this is one page a third of a second


def get(url):
    """The page, from the cache when it is there."""
    os.makedirs(CACHE, exist_ok=True)
    key = re.sub(r"[^a-z0-9]+", "_", url.lower())[-120:] + ".html"
    f = os.path.join(CACHE, key)
    if os.path.exists(f) and not FRESH:
        return open(f).read()
    time.sleep(PAUSE)
    r = rq.get(url, impersonate="chrome", timeout=40)
    if r.status_code != 200:
        return ""
    open(f, "w").write(r.text)
    return r.text


def words(seg):
    """A run of markup as the words a reader sees."""
    seg = re.sub(r"(?s)<(script|style).*?</\1>", " ", seg)
    return [x.strip() for x in html.unescape(re.sub(r"(?s)<[^>]+>", "|", seg)).split("|") if x.strip()]


def ufc_events():
    """Every UFC event page they list, from their own sitemap."""
    out = []
    for n in (1, 2):
        s = get("https://gidstats.com/files/sitemap/sitemap%d.xml" % n)
        out += re.findall(r"<loc>(https://gidstats\.com/events/ufc[_-][^<]*/)</loc>", s)
    return sorted(set(out))


def event_day(page):
    """The date the event page prints, as dd.mm.yy -> yyyy-mm-dd."""
    m = re.search(r"\b(\d{2})\.(\d{2})\.(\d{2})\b", page)
    if not m:
        return ""
    return "20%s-%s-%s" % (m.group(3), m.group(2), m.group(1))


def bouts_on(page, url):
    """Each bout page under this event, and the two slugs its name carries."""
    stem = url[len("https://gidstats.com"):]
    out = []
    for href in sorted(set(re.findall(r'href="(%s[^"]+\.html)"' % re.escape(stem), page))):
        name = href.rsplit("/", 1)[-1][:-5]
        if "_vs_" not in name:
            continue
        left, right = name.split("_vs_", 1)
        out.append((name, left, right))
    return out


ODDS = re.compile(r"ODDS\s*([-+]\d{2,5})[ \t]*([A-Za-z][A-Za-z ]{0,22})?")


HIST = {}


def history(slug):
    """Every bout on a man's page: when, against whom, and what he was priced.
       Read once per run: both sides of a bout ask for the same two pages, and
       a man on thirty cards would otherwise be parsed thirty times."""
    if slug in HIST:
        return HIST[slug]
    HIST[slug] = []
    page = get("https://gidstats.com/fighters/%s.html" % slug)
    if not page:
        return []
    rows = []
    # the row, not the button inside it: "history-list__item-btn" starts the
    # same way and slicing on it cuts every row before its date
    ROW = 'class="history-list__item history-list__item--'
    for m in re.finditer(re.escape(ROW), page):
        end = page.find(ROW, m.end())
        seg = page[m.start(): end if end > 0 else m.start() + 6000]
        w = words(seg)
        # the date shares its text node with the event ("16.05.2026 . UFC 324"),
        # so it is searched for, not matched as a word of its own
        date = ""
        d = re.search(r"\b(\d{2})\.(\d{2})\.(\d{4})\b", " ".join(w))
        if d:
            date = "%s-%s-%s" % (d.group(3), d.group(2), d.group(1))
        foe = ""
        if "VS" in w:
            i = w.index("VS")
            if i + 1 < len(w):
                foe = w[i + 1]
        o = ODDS.search(re.sub(r"(?s)<[^>]+>", " ", seg))
        rows.append({"date": date, "foe": foe,
                     "odds": o.group(1) if o else "",
                     "word": (o.group(2) or "").strip() if o else ""})
    HIST[slug] = rows
    return rows


def slug_words(slug):
    return set(re.split(r"[_-]", slug))


def settle_slug(slug, on_event):
    """The profile this man's bout file names. The event page lists exactly the
       men who fought on it, so that list is the answer key: the bout file's
       spelling is settled against it rather than guessed at. Only a clear
       winner is taken -- two names equally close is left unsettled."""
    if history(slug):
        return slug
    if not on_event:
        return slug
    want = slug_words(slug)
    scored = []
    for s2 in on_event:
        shared = len(slug_words(s2) & want)
        near = difflib.SequenceMatcher(None, slug, s2).ratio()
        scored.append((shared + near, s2))
    scored.sort(reverse=True)
    if scored and scored[0][0] >= 0.82 and (len(scored) == 1 or scored[0][0] - scored[1][0] >= 0.12):
        return scored[0][1]
    return slug


def price_from(slug, day, foe_slug):
    """This man's price for the bout on that day, by the opponent written on
       the row. The row writes a man as the site writes him and the slug as the
       file writes him, which are not always the same spelling, so they are
       compared on shared words first and closeness second -- never on the
       price, and never on a name carried over from another source."""
    want = slug_words(foe_slug)
    best = None
    for r in history(slug):
        if r["date"] != day or not r["odds"]:
            continue
        wrote = set(re.sub(r"[^a-z ]", " ", r["foe"].lower()).split())
        if wrote & want:
            return r["odds"], r["word"]
        near = difflib.SequenceMatcher(None, "_".join(sorted(wrote)),
                                       "_".join(sorted(want))).ratio()
        if near >= 0.6 and (best is None or near > best[0]):
            best = (near, r["odds"], r["word"])
    if best:
        return best[1], best[2]
    return "", ""


def main():
    evs = ufc_events()
    print("UFC events listed: %d" % len(evs))
    book, seen, unsettled = {}, 0, []
    for url in evs:
        page = get(url)
        if not page:
            continue
        day = event_day(page)
        if not (FROM <= day <= TO):
            continue
        title = (words(page) or [""])[0].split(" - ")[0]
        # the profiles this event page links, for the bout files whose spelling
        # is not the profile's
        on_event = list(dict.fromkeys(re.findall(r'href="/fighters/([^"]+)\.html"', page)))
        for name, left, right in bouts_on(page, url):
            seen += 1
            left, right = settle_slug(left, on_event), settle_slug(right, on_event)
            lo, lw = price_from(left, day, right)
            ro, rw = price_from(right, day, left)
            if not lo and not ro:
                unsettled.append("%s  %s" % (day, name))
                continue
            book[name] = {"event": title, "date": day,
                          "left": left, "lodds": lo, "lword": lw,
                          "right": right, "rodds": ro, "rword": rw}
        print("  %s  %-44s %d bouts" % (day, title[:44], len(bouts_on(page, url))))
    json.dump(book, open(OUT, "w"), indent=0, sort_keys=True)
    both = sum(1 for v in book.values() if v["lodds"] and v["rodds"])
    print("%s to %s: %d bouts seen, %d priced, %d with both sides, %d unpriced"
          % (FROM, TO, seen, len(book), both, len(unsettled)))
    for x in unsettled[:20]:
        print("   no price: %s" % x)


if __name__ == "__main__":
    main()
