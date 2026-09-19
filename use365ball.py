"""The football on the Tampa card is bet365's own, not one I drew.

   classification-12-americanfootball.png is not served -- every path answers
   404 -- but classification/12.svg is the same mark, and it is already on the
   board wearing the CFB pill. Its three paths are inlined here so the fill can
   be changed: hollow until he throws one, green when he does, red once the
   game is over and he has not.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
ico = open(D + "/site/ico/cfb.svg").read()
paths = re.findall(r'<path[^>]*/>', ico)
assert len(paths) == 3, "expected three paths, found %d" % len(paths)


def clean(p, cls):
    p = re.sub(r'\sfill="[^"]*"', "", p)
    return p.replace("<path", '<path class="%s"' % cls, 1)


BALL = ('<svg viewBox="0 0 50 50" aria-hidden="true">'
        + clean(paths[0], "b365 b365--skin")
        + clean(paths[1], "b365 b365--edge")
        + clean(paths[2], "b365 b365--seam")
        + "</svg>")

s = open(D + "/master.html").read()
old = re.search(r"BALL = \('<svg[^;]*?'\)\n", s)
# the ball lives in the card markup, not in a variable -- swap the drawn one out
drawn = re.search(r'<svg viewBox="0 0 34 22" aria-hidden="true">.*?</svg>', s, re.S)
assert drawn, "the drawn ball is not on the card"
n = len(re.findall(r'<svg viewBox="0 0 34 22" aria-hidden="true">.*?</svg>', s))
s = re.sub(r'<svg viewBox="0 0 34 22" aria-hidden="true">.*?</svg>', BALL, s)
print("footballs replaced: %d" % n)

# ------------------------------------------------------------------ style ---
old_css = re.search(r'  \.ball svg \{.*?\.ball\.miss \.lace \{[^}]*\}\n', s, re.S)
assert old_css, "the drawn ball's styling is not there"
new_css = """  .ball svg { width: 100%; height: 100%; display: block; }
  /* bet365's own mark, recoloured: hollow, then green, then red */
  .b365 { transition: fill 0.2s; }
  .b365--skin { fill: var(--muted); opacity: 0.38; }
  .b365--edge { fill: var(--muted); opacity: 0.55; }
  .b365--seam { fill: var(--muted); opacity: 0.22; }
  .ball.hit .b365--skin { fill: var(--green); opacity: 1; }
  .ball.hit .b365--edge { fill: #0c1a12; opacity: 0.85; }
  .ball.hit .b365--seam { fill: #0c1a12; opacity: 0.35; }
  .ball.miss .b365--skin { fill: #e2564d; opacity: 1; }
  .ball.miss .b365--edge { fill: #2a0f0d; opacity: 0.85; }
  .ball.miss .b365--seam { fill: #2a0f0d; opacity: 0.35; }
"""
s = s[:old_css.start()] + new_css + s[old_css.end():]
s = s.replace("""  .ball {
    display: block; width: 44px; height: 30px; position: static;
  }""",
              """  .ball { display: block; width: 34px; height: 34px; position: static; }""", 1)
s = s.replace("  .ptdx--balls .ptdcount { align-self: center; }",
              "  .ptdx--balls .ptdcount { align-self: center; }\n"
              "  .ptdx--balls { padding-bottom: 6px; }", 1)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("using bet365's football")
