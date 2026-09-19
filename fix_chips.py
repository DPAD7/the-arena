"""The 1+ and 2+ chips stop sitting on top of each other.

   They were placed along the bar by their own line — 1+ at 0.75 on a scale
   of four, 2+ at 2.75 — which puts their centers 47px apart on a phone while
   each chip is 70px wide. Every one of the twenty-five panes that carries
   both was overlapping by 18 to 24 pixels.

   The line each chip stands for is already marked on the bar by the tick, so
   the chip does not have to carry the position too. They go to the two ends
   of their own half instead: the higher number outside, nearer the edge of
   the card, the lower one inside, nearer the middle. That reads the same way
   round and cannot collide at any width.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# each chip says which number it is, so the stylesheet can place it
def name(m):
    which = "n1" if m.group(1).startswith("1") else "n2"
    return '<span class="ptdbtn ptdbtn--%s"><span class="ptdline">%s</span>' % (
        which, m.group(1))


s, n = re.subn(r'<span class="ptdbtn"(?:\s+style="[^"]*")?>'
               r'<span class="ptdline">([^<]*)</span>',
               lambda m: name(m), s)
assert n > 0, "no chips were named"
CHIPS = n

once("""  .ptdmarks { position: relative; height: 40px; margin-top: 8px; }
  .ptdbtn { position: absolute; top: 0; transform: translateX(50%); }
  .ptdside--r .ptdbtn { transform: translateX(-50%); }""",
     """  .ptdmarks { display: flex; align-items: flex-start; gap: 6px;
    height: 40px; margin-top: 8px; }
  .ptdbtn { flex: none; }
  /* The outer number sits at the outer end of its own half and the inner one
     at the inner end, so the pair reads outward from the middle of the card
     on both sides and never overlaps. An auto margin on whichever chip is
     second also puts a lone chip on its own correct end. */
  .ptdside--l .ptdbtn--n2 { order: 0; }
  .ptdside--l .ptdbtn--n1 { order: 1; margin-left: auto; }
  .ptdside--r .ptdbtn--n1 { order: 0; }
  .ptdside--r .ptdbtn--n2 { order: 1; margin-left: auto; }""",
     "the chip placement")

once("  .ptdmarks { height: 56px; }", "  .ptdmarks { height: 56px; }", "the taller marks row")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("chips named:", CHIPS, "| prices:", s.count("data-oid"))
