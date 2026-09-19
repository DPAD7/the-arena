"""Where DraftKings offers no moneyline, it still offers a number.

   Nobody prices a 55-point favorite to win outright, so the buy games come
   back with a spread and nothing else. That is not a gap in the data -- it is
   what the book is willing to say about the game -- so the card shows it,
   marked as a spread. What it must never do is show a spread price in the
   moneyline's place and let the two be read as one thing.
"""
import concurrent.futures as cf
import json
import os
import re
import subprocess

D = os.path.dirname(os.path.abspath(__file__))
CORE = ("http://sports.core.api.espn.com/v2/sports/football/leagues/%s"
        "/events/%s/competitions/%s/odds")


def ask(lg, eid):
    out = subprocess.run(["curl", "-s", "-m", "25", CORE % (lg, eid, eid)],
                         capture_output=True, text=True).stdout
    try:
        d = json.loads(out or "{}")
    except Exception:
        return eid, None
    for it in d.get("items") or []:
        if ((it.get("provider") or {}).get("name") or "") != "DraftKings":
            continue
        h = it.get("homeTeamOdds") or {}
        a = it.get("awayTeamOdds") or {}
        sp = it.get("spread")
        if sp is None:
            continue
        # ESPN writes the spread from the home side
        return eid, [float(sp), bool(h.get("favorite"))]
    return eid, None


s = open(D + "/master.html").read()
m = re.search(r'  var CFB = (\[\[.*?\]\]);\n', s, re.S)
cfb = json.loads(m.group(1))
blank = [g for g in cfb if not g[10]]
print("asking about %d college games with no moneyline" % len(blank))

got = {}
with cf.ThreadPoolExecutor(max_workers=16) as pool:
    for i, (eid, res) in enumerate(pool.map(lambda g: ask("college-football", g[1]), blank), 1):
        if res:
            got[eid] = res
        if i % 200 == 0:
            print("   %d asked, %d have a spread" % (i, len(got)))
print("with a spread: %d of %d" % (len(got), len(blank)))


def num(v):
    t = ("%g" % abs(v))
    return t


filled = 0
for g in cfb:
    if g[10]:
        continue
    p = got.get(g[1])
    if not p:
        continue
    home_line, home_fav = p[0], p[1]
    # home_line is the home side's number; the away side is its mirror
    away_line = -home_line
    g[10], g[11] = "s" + ("+" if away_line > 0 else "−") + num(away_line), ""
    g[12], g[13] = "s" + ("+" if home_line > 0 else "−") + num(home_line), ""
    filled += 1
print("filled %d with a spread | still blank %d"
      % (filled, sum(1 for g in cfb if not g[10])))

s = s[:m.start()] + "  var CFB = " + json.dumps(cfb, separators=(",", ":")) + ";\n" + s[m.end():]

# a leading "s" says this is a spread, not a moneyline
old = """  function priceSlot(odds, oid) {
    if (!odds) return GHOST;
    if (!oid) {
      /* a closing line off our own record: what it paid, not what is on offer */
      return '<button class="price" type="button" disabled>' +
             odds.replace("-", "\\u2212") + "</button>";
    }"""
new = """  function priceSlot(odds, oid) {
    if (!odds) return GHOST;
    if (odds.charAt(0) === "s") {
      /* no moneyline is offered on this game -- nobody prices a fifty-point
         favorite to win outright -- so the spread stands in, saying so. */
      return '<button class="price price--sp" type="button" disabled>' +
             odds.slice(1) + "</button>";
    }
    if (!oid) {
      /* a closing line off our own record: what it paid, not what is on offer */
      return '<button class="price" type="button" disabled>' +
             odds.replace("-", "\\u2212") + "</button>";
    }"""
assert s.count(old) == 1
s = s.replace(old, new, 1)
s = s.replace("  .gml .price { margin: 0; }",
              "  .gml .price { margin: 0; }\n"
              "  .price--sp { color: var(--muted); font-style: italic; }", 1)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("page %.0f KB" % (len(s) / 1024.0))
