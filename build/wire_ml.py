"""The moneylines DraftKings is posting, onto the cards that are drawn.

   A drawn card has no markup in the file, so its prices cannot live there --
   they ride in the schedule itself, as two more fields per side. The card is
   built with a real button where a price exists and the empty slot where it
   does not, and the button carries DraftKings' own selection id, so the slip
   and the refresher read it exactly as they read a hand-built one.
"""
import json
import os
import sys
import re

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
ML = json.load(open("/tmp/ml.json"))
s = pagefile.read()
before = s.count("data-oid")


def put(arr, n):
    """Hang [away price, its id, home price, its id] off each row."""
    got = 0
    for g in arr:
        p = ML.get(g[1])
        while len(g) < n:
            g.append("")
        if p:
            g[n - 4:n] = p
            got += 1
        else:
            g[n - 4:n] = ["", "", "", ""]
    return got


def swap(name, rows, what):
    global s
    m = re.search(r'  var %s = \[\[.*?\]\];\n' % name, s, re.S)
    assert m, "%s not found" % name
    s = s[:m.start()] + "  var %s = %s;\n" % (name, json.dumps(rows, separators=(",", ":"))) + s[m.end():]
    print("%-6s %d games, %d with a moneyline" % (what, len(rows), sum(1 for g in rows if g[-4])))


sched = json.loads(re.search(r'  var SCHED = (\[\[.*?\]\]);\n', s, re.S).group(1))
cfb = json.loads(re.search(r'  var CFB = (\[\[.*?\]\]);\n', s, re.S).group(1))
put(sched, 13)     # 9 fields + 4
put(cfb, 14)       # 10 fields + 4
swap("SCHED", sched, "NFL")
swap("CFB", cfb, "CFB")

# ------------------------------------------------------------ the button ---
BTN = '''  /* A price where there is one, the empty slot where there is not. The id is
     DraftKings' own, so everything downstream reads it unchanged. */
  function priceSlot(odds, oid) {
    if (!odds || !oid) return GHOST;
    return '<button class="price" type="button" data-oid="' + oid + '">' +
           odds.replace("-", "\\u2212") + "</button>";
  }
'''
anchor = "  var GHOST = '<span class=\"ghost\" aria-hidden=\"true\"></span>';\n"
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + BTN, 1)

# the NFL head
once_old = """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' + GHOST +
      '</span>' + away + '</span><span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + home + '<span class="gml">' + GHOST + '</span></span></div>' +"""
assert s.count(once_old) == 1
s = s.replace(once_old, """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      priceSlot(g[9], g[10]) +
      '</span>' + away + '</span><span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + home + '<span class="gml">' + priceSlot(g[11], g[12]) +
      '</span></span></div>' +""", 1)

# the college head
cfb_old = """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml"' +
      '>' + GHOST + '</span>' + away + '</span><span class="gtime">' + p.time +
      '</span><span class="gteam">' + home + '<span class="gml">' + GHOST +
      '</span></span></div>' + sec("PTD", "PTD") + sec("ATD", "ATD") +"""
assert s.count(cfb_old) == 1
s = s.replace(cfb_old, """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      priceSlot(g[10], g[11]) + '</span>' + away + '</span><span class="gtime">' +
      p.time + '</span><span class="gteam">' + home + '<span class="gml">' +
      priceSlot(g[12], g[13]) + '</span></span></div>' + sec("PTD", "PTD") + sec("ATD", "ATD") +""", 1)

if not pagefile.write(s):

    print("page changed under us, not written")
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("static prices still %d | page %.0f KB" % (before, len(s) / 1024.0))
