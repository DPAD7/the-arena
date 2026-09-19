"""The top twenty-five wear their number.

   ESPN stamps a rank on a competitor per week, so a club that was eighth in
   September and unranked in November reads correctly on each card rather than
   carrying today's number backwards. Only a rank inside the top twenty-five is
   kept; everything else has no number to show.
"""
import json
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
RANKS = json.load(open("/tmp/cfb_ranks.json"))
s = open(D + "/master.html").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:44], s.count(old))
    s = s.replace(old, new, 1)


m = re.search(r'  var CFB = (\[\[.*?\]\]);\n', s, re.S)
cfb = json.loads(m.group(1))
hit = 0
for g in cfb:
    while len(g) < 16:
        g.append("")
    r = RANKS.get(g[1]) or {}
    g[14] = r.get(g[3], "")
    g[15] = r.get(g[4], "")
    if g[14] or g[15]:
        hit += 1
print("college cards carrying a rank: %d" % hit)
s = s[:m.start()] + "  var CFB = " + json.dumps(cfb, separators=(",", ":")) + ";\n" + s[m.end():]

# ------------------------------------------------------------------ style ---
once("  .gml .price { margin: 0; }",
     """  .gml .price { margin: 0; }
  .grank {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 11px; letter-spacing: 0.04em;
    color: var(--amber); vertical-align: 0.35em; margin-right: 3px;
  }""", "the price margin")

# ------------------------------------------------------------- the college --
once("""      priceSlot(g[10], g[11]) + '</span>' + away + '</span><span class="gtime">' +
      p.time + '</span><span class="gteam">' + home + '<span class="gml">' +
      priceSlot(g[12], g[13]) + '</span></span></div>' + sec("PTD", "PTD") + sec("ATD", "ATD") +""",
     """      priceSlot(g[10], g[11]) + '</span>' + rank(g[14]) + away +
      '</span><span class="gtime">' + p.time + '</span><span class="gteam">' +
      rank(g[15]) + home + '<span class="gml">' +
      priceSlot(g[12], g[13]) + '</span></span></div>' + sec("PTD", "PTD") + sec("ATD", "ATD") +""",
     "the college head")

once("""  function badge(ab) {""",
     """  /* a number only where there is one: the top twenty-five, that week */
  function rank(n) {
    return n ? '<span class="grank">' + n + "</span>" : "";
  }
  function badge(ab) {""", "the badge helper")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("page %.0f KB" % (len(s) / 1024.0))
