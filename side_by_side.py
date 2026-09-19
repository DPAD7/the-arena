"""1+ and 2+ go back to sitting side by side, without touching the markup,
   the fonts or the sizes.

   The reason they could not fit was never the chips — it was the box they
   were being asked to fit in. Each chip row was confined to its own half of
   the *bar*, which is 93px wide, and two 70px chips need 146. Half of the
   *section* is 156px, because the bar's half does not include the count box
   beside it or the gaps around it.

   So the rows stop being confined to the bar. They are pinned to half the
   section each, in a band reserved underneath, where the count boxes have
   already ended. Nothing moves in the HTML and no type changes size; only
   the box the two chips are measured against.
"""
D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


once("  .ptdx { padding: 8px 0 2px; border-top: 1px dashed var(--edge); }",
     "  /* the band at the bottom is where the chips live, pinned to this box */\n"
     "  .ptdx { position: relative; padding: 8px 0 58px; border-top: 1px dashed var(--edge); }",
     "the section box")

once("""  /* Two chips are 140px wide and half a card is 92, so they cannot sit side
     by side at any readable size — they were overlapping by up to 24px. They
     go one above the other instead, each stack centered under its own bar so
     the card stays even on both sides of the zero. */
  .ptdmarks { display: flex; flex-direction: column; gap: 4px;
    height: auto; min-height: 40px; margin-top: 8px; }
  .ptdbtn { flex: none; }
  .ptdside--l .ptdmarks, .ptdside--r .ptdmarks { align-items: center; }""",
     """  /* Measured against half the bar (93px) two 70px chips overlap by 24px;
     measured against half the section (156px) they fit with room to spare.
     So the row is pinned to the section rather than sitting inside the bar's
     half, in the band reserved at the foot of it — clear of the count boxes,
     which stop 38px down. The higher number sits outside, nearer the edge of
     the card, and the lower one inside, on both sides of the zero. */
  .ptdmarks {
    position: absolute; bottom: 4px; width: calc(50% - 4px);
    display: flex; gap: 6px; justify-content: center; align-items: flex-start;
  }
  .ptdside--l .ptdmarks { left: 0; }
  .ptdside--r .ptdmarks { right: 0; }
  .ptdbtn { flex: none; }
  .ptdside--l .ptdbtn--n2 { order: 0; }
  .ptdside--l .ptdbtn--n1 { order: 1; }
  .ptdside--r .ptdbtn--n1 { order: 0; }
  .ptdside--r .ptdbtn--n2 { order: 1; }""", "the chip row")

# the taller variant reserved height on a row that no longer takes any
once("  .ptdmarks { min-height: 56px; }",
     "  .ptdx:has(.mk) { padding-bottom: 62px; }", "the taller marks row")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("chips side by side again | prices:", s.count("data-oid"))
