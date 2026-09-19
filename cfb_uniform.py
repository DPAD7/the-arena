"""Every college card carries both sections, priced or not.

   Seven cards were built by hand on the Saturday and each got whatever
   DraftKings happened to be pricing -- one had anytime only, one had passing
   only, one had neither. A card that is missing a section is a card that does
   not line up with the one beside it, so the missing halves go in as empty
   slots. The drawn cards already do this; this is the hand-built ones catching
   up.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")

GHOST = '<span class="ghost" aria-hidden="true"></span>'


def side(which):
    edge = "right" if which == "l" else "left"
    return ('<div class="ptdside ptdside--%s"><div class="ptdbar">'
            '<div class="ptdfill" style="%s:0; width:0%%"></div>'
            '<i class="ntick ntick--n1" style="%s:50.0%%"><b>1</b></i>'
            '<i class="ntick ntick--n2" style="%s:100.0%%"><b>2</b></i></div>'
            '<div class="ptdmarks">'
            '<span class="ptdbtn ptdbtn--n1"><span class="ptdline">1+</span>%s</span>'
            '<span class="ptdbtn ptdbtn--n2"><span class="ptdline">2+</span>%s</span>'
            '</div></div>' % (which, edge, edge, edge, GHOST, GHOST))


def last(name):
    bits = (name or "").split()
    return " ".join(bits[1:]) if len(bits) > 1 else (bits[0] if bits else "&mdash;")


def section(kind, lq, rq):
    return ('        <div class="ptdx ptdx--v2" data-scale="2" data-kind="%s">\n'
            '          <div class="ptdhead"><span style="color:var(--amber)">%s</span>'
            '<span class="gmk">%s</span>'
            '<span style="color:#5aa9ff">%s</span></div>\n'
            '          <div class="ptdrow"><span class="trkbox ptdcount">0</span>%s'
            '<span class="ptdzero">0</span>%s'
            '<span class="trkbox ptdcount">0</span></div>\n'
            '        </div>\n'
            % (kind, last(lq), kind, last(rq), side("l"), side("r")))


CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
added = []
out = []
at = 0
for m in CARD.finditer(s):
    c = m.group(0)
    if 'data-lg="college-football"' not in c:
        continue
    have = set(re.findall(r'<div class="ptdx[^"]*"[^>]*data-kind="([^"]*)"', c))
    # a section with no data-kind is a passing one, as the board has always read it
    for mm in re.finditer(r'<div class="ptdx[^"]*"([^>]*)>', c):
        if "data-kind" not in mm.group(1):
            have.add("PTD")
    want = [k for k in ("PTD", "ATD") if k not in have]
    if not want:
        continue
    lq = (re.search(r'data-lqb="([^"]*)"', c) or [None, ""])[1]
    rq = (re.search(r'data-rqb="([^"]*)"', c) or [None, ""])[1]
    title = (re.search(r'<h2 class="sheet__title">([^<]*)', c) or [None, "?"])[1]
    anchor = '        <button class="gmorebtn"'
    assert c.count(anchor) == 1, "%s: no single more-button" % title
    new = c.replace(anchor, "".join(section(k, lq, rq) for k in want) + anchor, 1)
    out.append((m.start(), m.end(), new))
    added.append("%s +%s" % (title, "/".join(want)))

for lo, hi, new in reversed(out):
    s = s[:lo] + new + s[hi:]

assert s.count("data-oid") == before, "a price moved"
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
for a in added:
    print("  " + a)
print("%d college cards squared up" % len(added))
