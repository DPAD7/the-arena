"""What the double taps read, folded into the price files.

   A double tap on the board reads the games in front of him from DraftKings
   there and then (build/ask_dk.py, run by .github/workflows/ask.yml) and the
   site keeps what came back in its store, where the page reads it. This puts
   those prices where every other price lives -- site/prices.json, and so
   site/prices/<id>.json -- so they are in the files and in the repo, not only
   in the store (Jose, Sep 23, 2026).

   An empty slot is always filled. A price the file already holds is
   replaced only by a tap read after the sweep last priced the board (9, 15
   and 21 ET): that reading is the newer one, so a price that moved between
   sweeps is brought up to date. A tap older than the last pricing leaves
   the sweep's own reading standing (Jose, Sep 25, 2026: "if there are
   changes re seed those changes").

   Usage:  python3 build/ask_fold.py          (writes and deploys what it adds)
           python3 build/ask_fold.py --dry

   Reads $ASK_SITE/ask?all=1 (the board by default), signed with $ASK_SECRET.
   Without the secret it says so and does nothing.
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prices as pricefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
SITE = os.environ.get("ASK_SITE", "https://the-arenasports.pages.dev").rstrip("/")


def held():
    """Every game the taps have read, as the site keeps them."""
    req = urllib.request.Request(SITE + "/ask?all=1", headers={
        "x-ask-secret": os.environ["ASK_SECRET"], "user-agent": "the-arena-ask"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return (json.load(r).get("prices") or {})


def slot(v):
    """A price and its DraftKings id."""
    return isinstance(v, list) and len(v) == 2 and all(isinstance(x, str) for x in v)


def last_priced(now=None):
    """When the sweep last read DraftKings for prices: the latest of 9, 15
       and 21 ET that has passed, as epoch milliseconds."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    now = now or datetime.now(et)
    for back in range(0, 3):
        day = (now - timedelta(days=back)).date()
        for h in (21, 15, 9):
            t = datetime(day.year, day.month, day.day, h, tzinfo=et)
            if t <= now:
                return t.timestamp() * 1000
    return 0


def fill(have, new, added, over=False):
    """new laid under have: only where have is empty -- or, when over is set,
       laid over it wherever new holds a price. added counts the prices that
       went in or changed."""
    if have in (None, "", []):
        if new not in (None, "", []):
            added[0] += count(new)
        return new
    if slot(have):
        if slot(new) and new[0] and (not have[0] or (over and new != have)):
            added[0] += 1
            return new
        return have
    if isinstance(have, list) and isinstance(new, list) and len(have) == len(new):
        return [fill(h, n, added, over) for h, n in zip(have, new)]
    if isinstance(have, dict) and isinstance(new, dict):
        out = dict(have)
        for k, v in new.items():
            out[k] = fill(have.get(k), v, added, over)
        return out
    return have


def count(v):
    if slot(v):
        return 1 if v[0] else 0
    if isinstance(v, list):
        return sum(count(x) for x in v)
    if isinstance(v, dict):
        return sum(count(x) for k, x in v.items() if k != "rounds")
    return 0


def ml_fill(have, new, over=False):
    """[price, oid, price, oid]: a side is taken whole where it is empty, or
       where it moved when over is set."""
    row = list(have) if have and len(have) == 4 else ["", "", "", ""]
    n = 0
    for i in (0, 1):
        if new and len(new) == 4 and new[i * 2] and (
                not row[i * 2] or (over and [row[i * 2], row[i * 2 + 1]] != [new[i * 2], new[i * 2 + 1]])):
            row[i * 2], row[i * 2 + 1] = new[i * 2], new[i * 2 + 1]
            n += 1
    return row, n


def main():
    if not os.environ.get("ASK_SECRET"):
        print("no ASK_SECRET -- the taps' prices were not asked for")
        return
    try:
        got = held()
    except Exception as e:
        print("the site did not answer: %s" % e)
        return
    page = open(os.path.join(D, "master.html")).read()
    shelf = {}
    for var in ("SCHED", "CFB", "FIGHTS"):
        m = re.search(r"var %s = (\[\[.*?\]\]);" % var, page, re.S)
        for r in (json.loads(m.group(1)) if m else []):
            shelf[str(r[1])] = var
    book = pricefile.read()
    added, games, unknown = 0, [], []
    priced_at = last_priced()
    for gid, one in sorted(got.items()):
        var = shelf.get(gid)
        price = (one or {}).get("price") or {}
        newer = ((one or {}).get("at") or 0) > priced_at
        if not var:
            unknown.append(gid)
            continue
        n = 0
        if price.get("ml"):
            row, k = ml_fill(book[var].get(gid), price["ml"], newer)
            if k:
                book[var][gid] = row
                n += k
        if price.get("props"):
            props = "FPROPS" if var == "FIGHTS" else "PROPS"
            box = [0]
            book[props][gid] = fill(book[props].get(gid), price["props"], box, newer)
            n += box[0]
        if n:
            games.append("%s +%d" % (gid, n))
            added += n
    if unknown:
        print("read on a tap but not on the board, left alone (%d): %s"
              % (len(unknown), ", ".join(unknown[:10])))
    print("taps: %d games held on the site, %d prices filled or brought up to date%s"
          % (len(got), added, (": " + ", ".join(games[:12])) if games else ""))
    if not added or DRY:
        if DRY:
            print("dry run -- nothing written")
        return
    pricefile.write(book)
    subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=the-arenasports", "--branch=main"],
                   cwd=D + "/site", capture_output=True, text=True)
    print("deployed")


if __name__ == "__main__":
    main()
