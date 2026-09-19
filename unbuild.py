"""One way to draw a card. The hand-built cards go; their prices stay.

   Weeks one and two were written into the page by hand, card by card, before
   the board learned to draw a card from the schedule. Two paths meant two
   sets of bugs -- a hand-built card had no data-lab, so the college coverage
   check could not read its team. This lifts every price off the hand-built
   cards into the same places the drawn cards read (PROPS for the props, the
   schedule rows for the moneylines), then removes the hand-built cards.

   Usage:  python3 unbuild.py --dry     (counts only)
           python3 unbuild.py
"""
import json
import os
import re
import sys

from bs4 import BeautifulSoup

D = os.path.dirname(os.path.abspath(__file__))
DRY = "--dry" in sys.argv


def price(btn):
    if not btn or not btn.get("data-oid"):
        return None
    odds = btn.get_text(" ", strip=True).split(" ")[0].replace("−", "-").replace("&minus;", "-")
    return [odds, btn["data-oid"]]


def main():
    s = open(D + "/master.html").read()
    a, b = s.index('<div id="pool" hidden>'), s.index("</div>\n", s.index('<div id="pool" hidden>'))
    # the pool closes where the first top-level </div> after its cards sits; find it by nesting
    depth, i, start = 0, a, a
    while True:
        m = re.compile(r"<div\b|</div>").search(s, i)
        if not m:
            raise SystemExit("pool never closes")
        depth += 1 if m.group(0) == "<div" else -1
        i = m.end()
        if depth == 0:
            break
    pool_html = s[start:i]
    soup = BeautifulSoup(pool_html, "html.parser")
    cards = soup.select("div.gcard[data-espn]")
    props, ml, moved = {}, {}, 0
    total = sum(len(c.select("button.price[data-oid]")) for c in cards)   # the fights in the pool stay as they are
    for c in cards:
        eid, lg = c["data-espn"], c.get("data-lg", "nfl")
        teams = c.select(".ghead .gteam")
        for i, t in enumerate(teams[:2]):
            p = price(t.select_one(".gml button.price"))
            if p:
                ml[(lg, eid, i)] = p
                moved += 1
        entry = {}
        h = [price(x.select_one("button.price")) for x in c.select(".h2hx .h2hodds")]
        if any(h):
            entry["h2h"] = h[:2]
            moved += sum(1 for x in h if x)
        for sec in c.select(".ptdx"):
            kind = "atd" if sec.get("data-kind") == "ATD" else "ptd"
            rows = [[None, None], [None, None]]
            for si, side in enumerate(("l", "r")):
                pane = sec.select_one(".ptdside--" + side)
                if not pane:
                    continue
                for n in (1, 2):
                    chip = pane.select_one(".ptdbtn--n%d" % n)
                    p = price(chip.select_one("button.price")) if chip else None
                    if p:
                        rows[si][n - 1] = p
                        moved += 1
            if any(x for side in rows for x in side):
                entry[kind] = rows
        if entry:
            props[eid] = entry
    print("hand-built cards: %d | prices on them: %d | lifted: %d" % (len(cards), total, moved))
    if moved != total:
        # every price must land somewhere; a shortfall is a layout this does not read
        print("SHORTFALL -- not writing"); return
    if DRY:
        return
    # PROPS: merge over what fill_week.py wrote
    m = re.search(r"  var PROPS = (\{.*?\});\n", s, re.S)
    cur = json.loads(m.group(1))
    cur.update(props)
    s = s[:m.start(1)] + json.dumps(cur, separators=(",", ":")) + s[m.end(1):]
    # moneylines into the schedule rows
    for var, lg in (("SCHED", "nfl"), ("CFB", "college-football")):
        mm = re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S)
        arr = json.loads(mm.group(1))
        slots = ((0, (9, 10)), (1, (11, 12))) if var == "SCHED" else ((0, (10, 11)), (1, (12, 13)))
        for g in arr:
            for i, (oi, ii) in slots:
                v = ml.get((lg, g[1], i))
                if v:
                    while len(g) <= ii:
                        g.append("")
                    g[oi], g[ii] = v[0], v[1]
        s = s[:mm.start(1)] + json.dumps(arr, separators=(",", ":")) + s[mm.end(1):]
    # the football cards leave the pool; the engine draws them now. The fight
    # cards and anything else in the pool stay as they are.
    for c in cards:
        c.decompose()
    s = s[:start] + str(soup) + s[i:]
    open(D + "/master.html", "w").write(s)
    doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
           '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
           '<meta name="robots" content="noindex">\n<meta name="referrer" content="no-referrer">\n</head>\n<body>\n')
    open(D + "/site/index.html", "w").write(
        doc + s + "\n</body>\n</html>\n")
    print("written: PROPS now %d games; pool emptied" % len(cur))


if __name__ == "__main__":
    main()
