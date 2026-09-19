"""The odds stand where the number they buy stands.

   The price for 1+ sits in the stretch of bar between 0 and 1, and the price
   for 2+ between 1 and 2 — so a chip is under the ground it is betting on
   rather than in an arbitrary half of the card. That only works if the chips
   are measured against the bar itself rather than against half the section,
   so they move inside the bar's own box.

   The green percentage comes off these two, which is also what makes the
   room for it: a chip is a price now, and the prices sit 52px apart.
"""
D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


once("""  /* Each number owns half the band, offered or not: 2+ outside, 1+ inside.
     Laid out as a centered pair instead, a man priced at only one of them had
     his single chip drift into the middle. */
  .ptdx--v2 .ptdmarks {
    display: grid; grid-template-columns: 1fr 1fr; justify-items: center;
  }
  .ptdx--v2 .ptdside--l .ptdbtn--n2 { grid-column: 1; }
  .ptdx--v2 .ptdside--l .ptdbtn--n1 { grid-column: 2; }
  .ptdx--v2 .ptdside--r .ptdbtn--n1 { grid-column: 1; }
  .ptdx--v2 .ptdside--r .ptdbtn--n2 { grid-column: 2; }""",
     """  /* Each price hangs under the stretch of bar it buys: 1+ over the ground
     between 0 and 1, 2+ over the ground between 1 and 2. Measured against
     the bar, not against half the section, so it lines up with the numbers
     on it whether or not the other price is offered. */
  .ptdx--v2 .ptdside { position: relative; }
  .ptdx--v2 .ptdmarks {
    position: static; display: block; width: auto; height: 0;
  }
  .ptdx--v2 .ptdbtn { position: absolute; top: 15px; }
  .ptdx--v2 .ptdside--l .ptdbtn { transform: translateX(50%); }
  .ptdx--v2 .ptdside--r .ptdbtn { transform: translateX(-50%); }
  .ptdx--v2 .ptdside--l .ptdbtn--n1 { right: 25%; }
  .ptdx--v2 .ptdside--l .ptdbtn--n2 { right: 75%; }
  .ptdx--v2 .ptdside--r .ptdbtn--n1 { left: 25%; }
  .ptdx--v2 .ptdside--r .ptdbtn--n2 { left: 75%; }
  /* a chip here is a price, nothing else */
  .ptdx--v2 .ptdbtn .pct { display: none; }""", "the chip placement")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("odds aligned to the bar, percentages off")
