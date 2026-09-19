"""A sample on the Tampa card: two footballs instead of a bar.

   The bar said how far along a passer was, which is a strange thing to draw
   for a count that only ever goes nought, one, two. Two balls say it plainly:
   empty until he throws one, filled and ringed green when he does, filled red
   once the game is over and he did not.

   The count box keeps its number, the prices keep their place, and each
   percentage moves under the ball it belongs to. Only the Tampa card is
   changed -- everything else keeps the bar until this is judged.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")

BALL = ('<svg viewBox="0 0 34 22" aria-hidden="true">'
        '<path class="skin" d="M17 1.6c6.6 0 14.4 3.2 14.4 9.4S23.6 20.4 17 20.4'
        ' 2.6 17.2 2.6 11 10.4 1.6 17 1.6z"/>'
        '<path class="lace" d="M12.4 11h9.2M15 8.6v4.8M17 8.2v5.6M19 8.6v4.8"/>'
        '</svg>')


def cell(n, oid, odds, pct):
    return ('<span class="ptdbtn ptdbtn--n%d">'
            '<i class="ntick ntick--n%d ball">%s</i>'
            '<span class="ptdline">%d+</span>'
            '<span class="ballpct">%s</span>'
            '<button class="price" type="button" data-oid="%s">%s</button>'
            '</span>' % (n, n, BALL, n, pct, oid, odds))


def side(which, one, two):
    return ('<div class="ptdside ptdside--%s">%s%s</div>'
            % (which, cell(1, *one), cell(2, *two)))


ROW = ('<div class="ptdrow"><span class="trkbox ptdcount">0</span>'
       + side("l",
              ("0QA361398521#2250880816_13L88808Q1-192366120Q20", "&minus;660", "87%"),
              ("0QA361398521#2250880833_13L88808Q1-2015862131Q20", "&minus;106", "51%"))
       + '<span class="ptdzero">0</span>'
       + side("r",
              ("0QA361397984#2250877973_13L88808Q1-192366120Q20", "&minus;2100", "95%"),
              ("0QA361397984#2250878013_13L88808Q1-2015862131Q20", "&minus;248", "71%"))
       + '<span class="trkbox ptdcount">0</span></div>')

card = re.search(r'<div class="gcard"[^>]*data-espn="401872925".*?\n      </div>', s, re.S)
c = card.group(0)
old_row = re.search(r'<div class="ptdrow">.*?<span class="trkbox ptdcount">0</span></div>', c, re.S)
new_c = c[:old_row.start()] + ROW + c[old_row.end():]
new_c = new_c.replace('<div class="ptdx ptdx--v2" data-scale="2">',
                      '<div class="ptdx ptdx--v2 ptdx--balls" data-scale="2">', 1)
s = s[:card.start()] + new_c + s[card.end():]

# ------------------------------------------------------------------ style ---
STYLE = """  /* ---- the sample: two footballs in place of the bar ----
     Empty is a ball nobody has thrown yet. Green means he threw it. Red means
     the game finished and he did not. */
  .ptdx--balls .ptdrow { align-items: flex-start; gap: 10px; }
  .ptdx--balls .ptdside {
    display: flex; justify-content: space-evenly; align-items: flex-start;
    gap: 10px; flex: 1; min-width: 0;
  }
  .ptdx--balls .ptdbtn {
    display: flex; flex-direction: column; align-items: center; gap: 5px;
  }
  .ptdx--balls .ptdline { display: none; }
  .ball {
    display: block; width: 44px; height: 30px; position: static;
  }
  .ball svg { width: 100%; height: 100%; display: block; overflow: visible; }
  .ball .skin {
    fill: none; stroke: var(--muted); stroke-width: 1.6; opacity: 0.55;
  }
  .ball .lace {
    fill: none; stroke: var(--muted); stroke-width: 1.4;
    stroke-linecap: round; opacity: 0.55;
  }
  .ball.hit .skin { fill: var(--green); stroke: var(--green); opacity: 1; }
  .ball.hit .lace { stroke: #0c1a12; opacity: 1; }
  .ball.miss .skin { fill: #e2564d; stroke: #e2564d; opacity: 1; }
  .ball.miss .lace { stroke: #2a0f0d; opacity: 1; }
  .ballpct {
    font-family: Barlow, sans-serif; font-weight: 600; font-size: 11.5px;
    color: var(--green); font-variant-numeric: tabular-nums; line-height: 1;
  }
  .ptdx--balls .ptdcount { align-self: center; }
"""
anchor = "  .ptdcount { flex: none; align-self: flex-start; }\n"
assert s.count(anchor) == 1
s = s.replace(anchor, anchor + STYLE, 1)

# the percentage lifter must leave this variant alone -- its numbers are placed
once_old = "  document.querySelectorAll(\".ptdx--v2 .ptdside\").forEach(function (pane) {"
assert s.count(once_old) == 1
s = s.replace(once_old,
              "  document.querySelectorAll(\".ptdx--v2:not(.ptdx--balls) .ptdside\")"
              ".forEach(function (pane) {", 1)

assert s.count("data-oid") == before, "a price moved"
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("footballs on the Tampa card | prices %d" % before)
