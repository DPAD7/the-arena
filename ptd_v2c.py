"""Two things off the TB/CIN card.

   The band above the bar: the PTD label sat 8px clear of a row 38px tall,
   and the zero in the middle is set to align to the top of that row rather
   than to the bar it belongs to — so it floated a good 15px above the bar
   and left an empty stripe under the dashed rule. The label comes down, the
   zero comes down to the bar's own level.

   And the chips hold their places. They were laid out as a centered pair, so
   Burrow — who is only priced at 2+ — had his one chip slide into the middle
   as though it were the only market. Each number now owns half the band
   whether or not the other is offered, so 2+ is always outside and 1+ always
   inside and a missing one leaves its gap.
"""
D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


once("""  /* the count box sits level with the bar it counts for, now that the
     price chips have left the row for the band underneath */
  .ptdx--v2 .ptdrow { align-items: center; }""",
     """  /* the count box sits level with the bar it counts for, now that the
     price chips have left the row for the band underneath */
  .ptdx--v2 .ptdrow { align-items: center; }
  /* the zero belongs to the bar, not to the top of a row the count box made
     tall, and the label has no reason to stand off from either */
  .ptdx--v2 .ptdzero { align-self: center; margin-top: 0; }
  .ptdx--v2 { padding-top: 4px; }
  .ptdx--v2 .ptdhead { margin-bottom: 2px; }
  /* Each number owns half the band, offered or not: 2+ outside, 1+ inside.
     Laid out as a centered pair instead, a man priced at only one of them had
     his single chip drift into the middle. */
  .ptdx--v2 .ptdmarks {
    display: grid; grid-template-columns: 1fr 1fr; justify-items: center;
  }
  .ptdx--v2 .ptdside--l .ptdbtn--n2 { grid-column: 1; }
  .ptdx--v2 .ptdside--l .ptdbtn--n1 { grid-column: 2; }
  .ptdx--v2 .ptdside--r .ptdbtn--n1 { grid-column: 1; }
  .ptdx--v2 .ptdside--r .ptdbtn--n2 { grid-column: 2; }""",
     "the v2 row styling")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("tightened, and the chips hold their slots")
