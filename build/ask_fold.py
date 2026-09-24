"""What the double taps read, folded into the price files.

   A double tap on the board reads the games in front of him from DraftKings
   there and then (build/ask_dk.py, run by .github/workflows/ask.yml) and the
   site keeps what came back in its store, where the page reads it. This puts
   those prices where every other price lives -- site/prices.json, and so
   site/prices/<id>.json -- so they are in the files and in the repo, not only
   in the store (Jose, Sep 23, 2026).

   Only a slot that is empty is filled. A price the file already holds is
   never overwritten, by a newer reading or any other: the sweep's own
   reading stands, and what a tap adds is only what the sweep never had.

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


def fill(have, new, added):
    """new laid under have: only where have is empty. added counts the
       prices that went in."""
    if have in (None, "", []):
        if new not in (None, "", []):
            added[0] += count(new)
        return new
    if slot(have):
        return have if have[0] else (new if slot(new) and new[0] else have)
    if isinstance(have, list) and isinstance(new, list) and len(have) == len(new):
        return [fill(h, n, added) for h, n in zip(have, new)]
    if isinstance(have, dict) and isinstance(new, dict):
        out = dict(have)
        for k, v in new.items():
            out[k] = fill(have.get(k), v, added)
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


def ml_fill(have, new):
    """[price, oid, price, oid]: a side is taken whole where it is empty."""
    row = list(have) if have and len(have) == 4 else ["", "", "", ""]
    n = 0
    for i in (0, 1):
        if not row[i * 2] and new and len(new) == 4 and new[i * 2]:
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
    for gid, one in sorted(got.items()):
        var = shelf.get(gid)
        price = (one or {}).get("price") or {}
        if not var:
            unknown.append(gid)
            continue
        n = 0
        if price.get("ml"):
            row, k = ml_fill(book[var].get(gid), price["ml"])
            if k:
                book[var][gid] = row
                n += k
        if price.get("props"):
            props = "FPROPS" if var == "FIGHTS" else "PROPS"
            box = [0]
            book[props][gid] = fill(book[props].get(gid), price["props"], box)
            n += box[0]
        if n:
            games.append("%s +%d" % (gid, n))
            added += n
    if unknown:
        print("read on a tap but not on the board, left alone (%d): %s"
              % (len(unknown), ", ".join(unknown[:10])))
    print("taps: %d games held on the site, %d prices the files did not have%s"
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
