"""The footballs go on every NFL card.

   The sample stood on Tampa/Cincinnati long enough to be judged, so the rest
   of the league follows. Each card keeps its own prices and its own selection
   ids; only the shape around them changes -- the bar and its two numbers come
   out, four footballs go in, and the count boxes move to the middle.

   A price that was never offered stays an empty slot, as it was.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")

BALL = re.search(r'<svg viewBox="0 0 50 50" aria-hidden="true">.*?</svg>', s, re.S)
assert BALL, "the football is not on the page"
BALL = BALL.group(0)
GHOST = '<span class="ghost" aria-hidden="true"></span>'


def chip(n, inner, pct):
    """One football, its price and the chance it implies."""
    return ('<span class="ptdbtn ptdbtn--n%d">'
            '<i class="ntick ntick--n%d ball">%s</i>'
            '<span class="ptdline">%d+</span>'
            '%s%s</span>' % (n, n, BALL, n,
                             ('<span class="ballpct">%s</span>' % pct) if pct else "",
                             inner))


def read_side(pane):
    """What each of the two chips in a pane holds, priced or not."""
    out = {}
    for mm in re.finditer(r'<span class="ptdbtn ptdbtn--n(\d)">.*?</span>\s*'
                          r'(?=<span class="ptdbtn|</div>|$)', pane, re.S):
        body = mm.group(0)
        n = int(mm.group(1))
        b = re.search(r'<button class="price"[^>]*data-oid="[^"]*"[^>]*>.*?</button>', body, re.S)
        if not b:
            out[n] = (GHOST, "")
            continue
        raw = b.group(0)
        pct = (re.search(r'<span class="pct">([^<]*)</span>', raw) or [None, ""])[1]
        clean = re.sub(r'\s*<span class="pct">[^<]*</span>', "", raw)
        out[n] = (clean, pct)
    for n in (1, 2):
        out.setdefault(n, (GHOST, ""))
    return out


CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
edits, done = [], []
for m in CARD.finditer(s):
    c = m.group(0)
    if 'data-lg="nfl"' not in c or "ptdx--balls" in c:
        continue
    title = (re.search(r'<h2 class="sheet__title">([^<]*)', c) or [None, "?"])[1]
    sec = re.search(r'<div class="ptdx ptdx--v2"([^>]*)>(.*?)\n        </div>', c, re.S)
    if not sec:
        continue
    panes = re.findall(r'<div class="ptdside ptdside--([lr])">(.*?)</div></div>', sec.group(2), re.S)
    if len(panes) != 2:
        panes = re.findall(r'<div class="ptdside ptdside--([lr])">(.*?)(?=<span class="ptdzero"|<span class="trkbox|$)',
                           sec.group(2), re.S)
    assert len(panes) == 2, "%s: found %d panes" % (title, len(panes))
    sides = {w: read_side(p) for w, p in panes}
    row = ('<div class="ptdrow">'
           + '<div class="ptdside ptdside--l">%s%s</div>'
             % (chip(1, *sides["l"][1]), chip(2, *sides["l"][2]))
           + '<span class="trkbox ptdcount">0</span><span class="trkbox ptdcount">0</span>'
           + '<div class="ptdside ptdside--r">%s%s</div>'
             % (chip(1, *sides["r"][1]), chip(2, *sides["r"][2]))
           + '</div>')
    new_sec = ('<div class="ptdx ptdx--v2 ptdx--balls"%s>\n          %s\n        </div>'
               % (sec.group(1), row))
    new_c = c[:sec.start()] + new_sec + c[sec.end():]
    edits.append((m.start(), m.end(), new_c))
    done.append(title)

for lo, hi, new in reversed(edits):
    s = s[:lo] + new + s[hi:]

assert s.count("data-oid") == before, "a price went missing"
print("cards given footballs: %d" % len(done))
for t in done:
    print("   " + t)

# ------------------------------------------------- the drawn NFL frame -----
# ptdSide() belongs to the college cards and keeps its bar; the NFL frame has
# its own side builder, and that is the one that gets footballs.
old = """    var side = function (which) {
      return '<div class="ptdside ptdside--' + which + '"><div class="ptdbar">' +
        '<div class="ptdfill" style="' + (which === "l" ? "right" : "left") +
        ':0; width:0%"></div><i class="ntick ntick--n1" style="' +
        (which === "l" ? "right" : "left") + ':50.0%"><b>1</b></i>' +
        '<i class="ntick ntick--n2" style="' + (which === "l" ? "right" : "left") +
        ':100.0%"><b>2</b></i></div><div class="ptdmarks">' +
        '<span class="ptdbtn ptdbtn--n1"><span class="ptdline">1+</span>' + GHOST + '</span>' +
        '<span class="ptdbtn ptdbtn--n2"><span class="ptdline">2+</span>' + GHOST + '</span>' +
        '</div></div>';
    };"""
new = """    var side = function (which) {
      return '<div class="ptdside ptdside--' + which + '">' +
        ballChip(1) + ballChip(2) + '</div>';
    };"""
assert s.count(old) == 1, "the NFL side builder is not where expected"
s = s.replace(old, new, 1)

# the football, and a chip built around it, for anything drawn
helper = """  var BALLSVG = '""" + BALL.replace("'", "\\'") + """';
  function ballChip(n) {
    return '<span class="ptdbtn ptdbtn--n' + n + '">' +
      '<i class="ntick ntick--n' + n + ' ball">' + BALLSVG + '</i>' +
      '<span class="ptdline">' + n + '+</span>' + GHOST + '</span>';
  }
  function frame(g) {"""
assert s.count("  function frame(g) {") == 1
s = s.replace("  function frame(g) {", helper, 1)

# the counts move to the middle and the nought goes, as on the sample
old2 = """      '<div class="ptdrow"><span class="trkbox ptdcount">0</span>' + side("l") +
      '<span class="ptdzero">0</span>' + side("r") +
      '<span class="trkbox ptdcount">0</span></div></div>' +"""
new2 = """      '<div class="ptdrow">' + side("l") +
      '<span class="trkbox ptdcount">0</span><span class="trkbox ptdcount">0</span>' +
      side("r") + '</div></div>' +"""
assert s.count(old2) == 1, "the NFL row is not where expected"
s = s.replace(old2, new2, 1)
s = s.replace(''''<div class="ptdx ptdx--v2" data-scale="2">' +
      '<div class="ptdhead ptdhead--bare"><span class="gmk">PTD</span></div>' +''',
              ''''<div class="ptdx ptdx--v2 ptdx--balls" data-scale="2">' +''', 1)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("prices still %d | page %.0f KB" % (before, len(s) / 1024.0))
