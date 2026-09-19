"""The clubs wear their own badge.

   ESPN serves a logo for every NFL club keyed on the abbreviation we already
   carry, so the head can show the badge where it showed three letters. The
   letters stay as the image's alt text, which is what a reader sees if the
   picture never arrives -- the card must not come apart because a CDN was
   slow.

   College needs a team id rather than an abbreviation and we do not store one
   yet, so its cards keep their letters for now.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:40], s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------------ style ---
once("  .gml .price { margin: 0; }",
     """  .gml .price { margin: 0; }
  .glogo {
    width: 30px; height: 30px; display: block; object-fit: contain;
    filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.55));
  }
  .gteam:has(.glogo) { display: inline-flex; align-items: center; gap: 8px; }""",
     "the price margin")

# --------------------------------------------------------- the drawn card ---
once("""      '</span>' + away + '</span><span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + home + '<span class="gml">' + priceSlot(g[11], g[12]) +
      '</span></span></div>' +""",
     """      '</span>' + badge(away) + '</span><span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + badge(home) + '<span class="gml">' +
      priceSlot(g[11], g[12]) + '</span></span></div>' +""", "the NFL head")

once("""  var GHOST = '<span class="ghost" aria-hidden="true"></span>';""",
     """  var GHOST = '<span class="ghost" aria-hidden="true"></span>';
  /* ESPN's badge for a club, with the letters kept as the alt text so a card
     never comes apart because a picture was slow. */
  function badge(ab) {
    if (!ab) return "";
    return '<img class="glogo" alt="' + ab + '" src="https://a.espncdn.com/i/' +
           'teamlogos/nfl/500/' + ab.toLowerCase() + '.png">';
  }""", "the ghost")

# -------------------------------------------------- the cards built by hand --
CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
swapped = 0
out = []
for m in CARD.finditer(s):
    c = m.group(0)
    if 'data-lg="nfl"' not in c:
        continue
    head = re.search(r'<div class="ghead">.*?</div>\n', c, re.S)
    if not head:
        continue
    h = head.group(0)
    before = h

    def logo(ab):
        return ('<img class="glogo" alt="%s" src="https://a.espncdn.com/i/'
                'teamlogos/nfl/500/%s.png">' % (ab, ab.lower()))

    # the away club sits after its price, the home club before its own
    h = re.sub(r'(</span>)([A-Z&;]{2,4})(</span><span class="gtime">)',
               lambda mm: mm.group(1) + logo(mm.group(2)) + mm.group(3), h)
    h = re.sub(r'(<span class="gteam">)([A-Z&;]{2,4})(<span class="gml">)',
               lambda mm: mm.group(1) + logo(mm.group(2)) + mm.group(3), h)
    if h != before:
        out.append((m.start() + head.start(), m.start() + head.end(), h))
        swapped += 1

for lo, hi, new in reversed(out):
    s = s[:lo] + new + s[hi:]
print("hand-built NFL heads given badges: %d" % swapped)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
