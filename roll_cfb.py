"""College gets the same two rows: footballs for the throw, bolts for the score.

   The bolt is a flat orange PNG with no paths to recolour, so it is used as a
   mask instead -- its alpha gives the shape and CSS gives the colour. That way
   it answers to the same green and red the footballs do rather than sitting
   there orange whatever happened.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")
GHOST = '<span class="ghost" aria-hidden="true"></span>'
FB = '<svg viewBox="0 0 50 50" aria-hidden="true"><use href="#fb"/></svg>'
BOLT = '<span class="boltmk" aria-hidden="true"></span>'


def chip(n, kind, inner, pct):
    mark = BOLT if kind == "ATD" else FB
    return ('<span class="ptdbtn ptdbtn--n%d">'
            '<i class="ntick ntick--n%d ball">%s</i>'
            '<span class="ptdline">%d+</span>'
            '%s%s</span>' % (n, n, mark, n,
                             ('<span class="ballpct">%s</span>' % pct) if pct else "",
                             inner))


def read_side(pane):
    out = {}
    for mm in re.finditer(r'<span class="ptdbtn ptdbtn--n(\d)">.*?</span>\s*'
                          r'(?=<span class="ptdbtn|</div>|$)', pane, re.S):
        body, n = mm.group(0), int(mm.group(1))
        b = re.search(r'<button class="price"[^>]*data-oid="[^"]*"[^>]*>.*?</button>', body, re.S)
        if not b:
            out[n] = (GHOST, "")
            continue
        raw = b.group(0)
        pct = (re.search(r'<span class="pct">([^<]*)</span>', raw) or [None, ""])[1]
        out[n] = (re.sub(r'\s*<span class="pct">[^<]*</span>', "", raw), pct)
    for n in (1, 2):
        out.setdefault(n, (GHOST, ""))
    return out


CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
edits, done = [], []
for m in CARD.finditer(s):
    c = m.group(0)
    if 'data-lg="college-football"' not in c:
        continue
    title = (re.search(r'<h2 class="sheet__title">([^<]*)', c) or [None, "?"])[1]
    new_c, moved = c, []
    for sec in list(re.finditer(r'<div class="ptdx ptdx--v2"([^>]*)>(.*?)\n        </div>', c, re.S))[::-1]:
        attrs, body = sec.group(1), sec.group(2)
        kind = (re.search(r'data-kind="([^"]*)"', attrs) or [None, "PTD"])[1]
        panes = re.findall(r'<div class="ptdside ptdside--([lr])">(.*?)</div></div>', body, re.S)
        if len(panes) != 2:
            continue
        sides = {w: read_side(p) for w, p in panes}
        head = re.search(r'<div class="ptdhead[^"]*">.*?</div>', body, re.S)
        row = ('<div class="ptdrow">'
               + '<div class="ptdside ptdside--l">%s%s</div>'
                 % (chip(1, kind, *sides["l"][1]), chip(2, kind, *sides["l"][2]))
               + '<span class="trkbox ptdcount">0</span><span class="trkbox ptdcount">0</span>'
               + '<div class="ptdside ptdside--r">%s%s</div>'
                 % (chip(1, kind, *sides["r"][1]), chip(2, kind, *sides["r"][2]))
               + '</div>')
        new_sec = ('<div class="ptdx ptdx--v2 ptdx--balls"%s>\n          %s\n          %s\n        </div>'
                   % (attrs, head.group(0) if head else "", row))
        new_c = new_c[:sec.start()] + new_sec + new_c[sec.end():]
        moved.append(kind)
    if moved:
        edits.append((m.start(), m.end(), new_c))
        done.append("%s (%s)" % (title, "+".join(reversed(moved))))

for lo, hi, new in reversed(edits):
    s = s[:lo] + new + s[hi:]
print("college cards converted: %d" % len(done))
for t in done:
    print("   " + t)

# --------------------------------------------------------- the drawn ones ---
old = """    var sec = function (kind, lab) {
      return '<div class="ptdx ptdx--v2" data-scale="2" data-kind="' + kind + '">' +
        '<div class="ptdhead"><span style="color:var(--amber)">' + last(aq) +
        '</span><span class="gmk">' + lab + '</span>' +
        '<span style="color:#5aa9ff">' + last(hq) + '</span></div>' +
        '<div class="ptdrow"><span class="trkbox ptdcount">0</span>' + ptdSide("l") +
        '<span class="ptdzero">0</span>' + ptdSide("r") +
        '<span class="trkbox ptdcount">0</span></div></div>';
    };"""
new = """    var sec = function (kind, lab) {
      var mark = kind === "ATD"
        ? '<span class="boltmk" aria-hidden="true"></span>' : BALLSVG;
      var chip = function (n) {
        return '<span class="ptdbtn ptdbtn--n' + n + '">' +
          '<i class="ntick ntick--n' + n + ' ball">' + mark + '</i>' +
          '<span class="ptdline">' + n + '+</span>' + GHOST + '</span>';
      };
      var pane = function (w) {
        return '<div class="ptdside ptdside--' + w + '">' + chip(1) + chip(2) + '</div>';
      };
      return '<div class="ptdx ptdx--v2 ptdx--balls" data-scale="2" data-kind="' +
        kind + '">' +
        '<div class="ptdhead"><span style="color:var(--amber)">' + last(aq) +
        '</span><span class="gmk">' + lab + '</span>' +
        '<span style="color:#5aa9ff">' + last(hq) + '</span></div>' +
        '<div class="ptdrow">' + pane("l") +
        '<span class="trkbox ptdcount">0</span><span class="trkbox ptdcount">0</span>' +
        pane("r") + '</div></div>';
    };"""
assert s.count(old) == 1, "the college section builder is not where expected"
s = s.replace(old, new, 1)

# ------------------------------------------------------------------ style ---
anchor = "  .ball.miss {\n    --fb-skin: #e2564d; --fb-edge: #2a0f0d; --fb-seam: #2a0f0d; opacity: 1;\n  }\n"
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + """  /* The boost mark is a flat orange picture with nothing to recolour, so its
     alpha is used as a mask and the colour comes from here -- the same green
     and red the footballs answer to. */
  .boltmk {
    display: block; width: 100%; height: 100%;
    background: var(--fb-skin);
    -webkit-mask: url("ico/boost.png") center / contain no-repeat;
    mask: url("ico/boost.png") center / contain no-repeat;
  }
""", 1)

assert s.count("data-oid") == before, "a price went missing"
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("prices still %d | page %.0f KB" % (before, len(s) / 1024.0))
