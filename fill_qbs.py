"""Every card names both passers.

   Four were built on a Saturday when DraftKings priced only one side, so the
   other was left as a dash. There is a hide button now, so nothing needs to be
   left out to keep the board short -- a card either says who is playing or it
   is wrong. The names come from the schedule already in the page, and which
   side is which is read off data-lhome rather than assumed.
"""
import json
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()

sched = {g[1]: (g[5], g[6], g[7], g[8])
         for g in json.loads(re.search(r'  var SCHED = (\[\[.*?\]\]);\n', s, re.S).group(1))}
cfb = {g[1]: (g[5], g[6], g[7], g[8])
       for g in json.loads(re.search(r'  var CFB = (\[\[.*?\]\]);\n', s, re.S).group(1))}

CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)


def last(n):
    bits = (n or "").split()
    return " ".join(bits[1:]) if len(bits) > 1 else (bits[0] if bits else "")


edits = []
for m in CARD.finditer(s):
    c = m.group(0)
    eid = (re.search(r'data-espn="(\d+)"', c) or [None, None])[1]
    if not eid:
        continue
    src = sched.get(eid) or cfb.get(eid)
    if not src:
        continue
    away, awayid, home, homeid = src
    lhome = (re.search(r'data-lhome="1"', c) is not None)
    left, leftid = (home, homeid) if lhome else (away, awayid)
    right, rightid = (away, awayid) if lhome else (home, homeid)
    new = c
    for side, nm, nid in (("l", left, leftid), ("r", right, rightid)):
        has = (re.search(r'data-%sqb="([^"]*)"' % side, new) or [None, ""])[1]
        if has or not nm:
            continue
        new = new.replace('<div class="gcard"',
                          '<div class="gcard" data-%sqb="%s" data-%sqbid="%s"'
                          % (side, nm, side, nid), 1)
        # and the header the name-mover reads
        col = "var(--amber)" if side == "l" else "#5aa9ff"
        dash = '<span style="color:%s"><span class="gdash">&mdash;</span></span>' % col
        if dash in new:
            new = new.replace(dash, '<span style="color:%s">%s</span>' % (col, last(nm)), 1)
    if new != c:
        edits.append((m.start(), m.end(), new,
                      (re.search(r'<h2 class="sheet__title">([^<]*)', c) or [None, "?"])[1]))

for lo, hi, new, t in reversed(edits):
    s = s[:lo] + new + s[hi:]
for _, _, _, t in edits:
    print("  filled:", t)
print("%d cards squared up" % len(edits))

left = re.findall(r'<div class="gcard"(?![^>]*data-lqb)[^>]*data-espn', s)
print("cards still missing a left passer: %d" % len(left))

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
