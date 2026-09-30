"""Put the recovered prices back on the cards that never had any.

   Two week-one cards were built by hand and never went through the pricer,
   so PROPS holds nothing for them and their chips are empty. backfill_prices
   recovered what DraftKings charged; this writes it into PROPS so those cards
   read like every other. A game PROPS already prices is left alone.

   Usage:  python3 seed_props.py            (writes)
           python3 seed_props.py --dry
"""
import json
import os
import re
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
DRY = "--dry" in sys.argv


def main():
    s = pagefile.read()
    props = json.loads(re.search(r"  var PROPS = (\{.*?\});\n", s, re.S).group(1))
    sched = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    added = []
    for g in sched:
        eid = g[1]
        has = props.get(eid) or {}
        have = has.get("ptd") or [[None, None], [None, None]]
        haveA = has.get("atd") or [[None, None], [None, None]]
        # complete means both markets, not just the passing one
        if all(x for side in have for x in side) and all(x for side in haveA for x in side):
            continue
        f = D + "/prices/nfl/wk%s/%s.json" % (g[0], eid)
        if not os.path.exists(f):
            continue
        d = json.load(open(f))
        ptd = [list(have[0]), list(have[1])]
        atd = [list(haveA[0]), list(haveA[1])]
        filled = 0
        for man in d.get("passers") or []:
            i = man.get("side")
            if i not in (0, 1):
                continue
            # only the empty slots: a price the page already holds stands
            for k in (0, 1):
                if not ptd[i][k] and (man.get("ptd") or [None, None])[k]:
                    ptd[i][k] = man["ptd"][k]; filled += 1
                if not atd[i][k] and (man.get("atd") or [None, None])[k]:
                    atd[i][k] = man["atd"][k]; filled += 1
        if not filled:
            continue
        entry = dict(has)
        entry["ptd"] = ptd
        entry["atd"] = atd
        entry.setdefault("h2h", d.get("h2h") or [None, None])
        props[eid] = entry
        added.append("%s/%s" % (g[3], g[4]))
    print("cards seeded from the archive: %d%s%s" % (len(added), " -- " + ", ".join(added) if added else "", " (dry)" if DRY else ""))
    if DRY or not added:
        return
    old = re.search(r"  var PROPS = (\{.*?\});\n", s, re.S)
    s = s[:old.start()] + "  var PROPS = " + json.dumps(props, separators=(",", ":")) + ";\n" + s[old.end():]
    if not pagefile.write(s):
        print("page changed under us, not written")
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
           '<meta name="theme-color" content="#000000">\n'
           '<meta name="robots" content="noindex">\n<meta name="referrer" content="no-referrer">\n</head>\n<body>\n')
    open(D + "/site/index.html", "w").write(doc + s + "\n</body>\n</html>\n")
    print("written")


if __name__ == "__main__":
    main()
