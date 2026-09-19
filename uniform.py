"""Every slot is the same size, whether or not there is a price in it.

   A dash took up a few pixels where a price takes fifty, so a card with a
   market missing sat crooked against one that had it — the receiver boxes
   vanished, the opponent's count box stood alone, one side of the passing bar
   had nothing under it. Each of those dashes becomes a box of exactly the
   size the price would have been, dashed and dimmed so it reads as absent
   rather than as nought.

   And the half with nobody behind it is drawn again. Hiding it was the
   opposite instruction, given an hour earlier; uniform wins.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")
n = {}


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


def swap(pat, repl, what, flags=0):
    global s
    s, c = re.subn(pat, repl, s, flags=flags)
    n[what] = c
    return c


GHOST = '<span class="ghost" aria-hidden="true"></span>'

# ------------------------------------------- the half with nobody is back ----
once("""  /* A side the card knows no quarterback for has nothing to follow, so it
     is not drawn: an empty bar carrying a 1 and a 2 says a milestone is being
     watched when none is. */
  .ptdx--v2 .ptdside--dead .ptdbar, .ptdx--v2 .ptdside--dead .ptdmarks { visibility: hidden; }
  .trkbox--dead { visibility: hidden; }
""", "", "the hidden half")

once("""  /* A half with no man behind it is left blank rather than drawn empty. */
  document.querySelectorAll(".ptdx--v2").forEach(function (sec) {
    var card = sec.closest(".gcard");
    [["l", "lqb", 0], ["r", "rqb", 1]].forEach(function (sd) {
      if (card && card.dataset[sd[1]]) return;
      var pane = sec.querySelector(".ptdside--" + sd[0]);
      if (pane) pane.classList.add("ptdside--dead");
      var box = sec.querySelectorAll(".ptdcount")[sd[2]];
      if (box) box.classList.add("trkbox--dead");
    });
  });

""", "", "the blanking pass")

# ------------------------------------------------------- every empty slot ----
# a moneyline nobody is pricing
swap(r'<span class="gml"><span class="gdash">&mdash;</span></span>',
     '<span class="gml">%s</span>' % GHOST, "moneylines")

# a head-to-head end with no price under the number
swap(r'<span class="h2hodds"><span class="gdash">&mdash;</span></span>',
     '<span class="h2hodds">%s</span>' % GHOST, "head to head")

# a receiver pair that was a single dash becomes two boxes, like the other side
swap(r'<span class="gcell( recpair)?"><span class="gdash">&mdash;</span></span>',
     lambda m: ('<span class="gcell recpair">'
                '<span class="recman">%s<span class="wrname">&nbsp;</span></span>'
                '<span class="recman">%s<span class="wrname">&nbsp;</span></span></span>'
                % (GHOST, GHOST)), "receiver cells")

# and a passing or scoring line nobody is pricing
made = [0]


def pane_slots(m):
    pane, edge = m.group(0), ("right" if "ptdside--l" in m.group(0) else "left")
    have = set(re.findall(r'ptdbtn--n(\d)', pane))
    add = ""
    for k in ("1", "2"):
        if k not in have:
            add += ('<span class="ptdbtn ptdbtn--n%s"><span class="ptdline">%s+</span>%s</span>'
                    % (k, k, GHOST))
            made[0] += 1
    if not add:
        return pane
    return pane.replace('<div class="ptdmarks">', '<div class="ptdmarks">' + add, 1)


s = re.sub(r'<div class="ptdside ptdside--[lr]">.*?(?=<span class="ptdzero"|</div></div>)',
           pane_slots, s, flags=re.S)
n["passing slots"] = made[0]

# ------------------------------------------------------------- the style ----
once("  .price {", """  /* An absent price, the exact size of a present one, so a card with a market
     missing lines up with a card that has it. Dashed and dim: not nought, not
     for sale. */
  .ghost {
    display: inline-block; vertical-align: middle;
    min-width: 56px; padding: 6px 9px; margin: 3px 0;
    border: 1px dashed rgba(255, 255, 255, 0.16); border-radius: 10px;
    font-family: Barlow, "Helvetica Neue", Arial, sans-serif;
    font-weight: 600; font-size: 13.5px; line-height: 1.2;
    color: rgba(255, 255, 255, 0.26); text-align: center;
  }
  .ghost::after { content: "\\2014"; }
  .ptdx--v2 .ptdbtn .ghost { min-width: 48px; padding: 6px 7px; }
  .gcard:not([data-lg]) .ghead .ghost { min-width: 46px; padding: 6px 7px; }

  .price {""", "the price rule")

# ------------------------------------------- heads stop wrapping when full ----
once("""  .gteam {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 21px; letter-spacing: 0.03em; text-align: center;
    display: flex; align-items: center; justify-content: center;
    flex-wrap: wrap; gap: 0 4px;
  }""",
     """  .gteam {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 21px; letter-spacing: 0.03em; text-align: center;
    display: flex; align-items: center; justify-content: center;
    flex-wrap: nowrap; white-space: nowrap; min-width: 0; gap: 0 4px;
  }""", "the club name")

once("  @media (max-width: 700px) {\n    body { padding-block: 20px 76px;",
     """  /* every slot being a full box makes a head wider than it was, so the club
     gives up a little size on a narrow phone rather than dropping a line */
  @media (max-width: 400px) {
    .gteam { font-size: 18px; }
  }
  @media (max-width: 700px) {
    body { padding-block: 20px 76px;""", "the phone block")

assert s.count("data-oid") == before, "prices lost"
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("placeholders:", n, "| dashes left:", s.count('class="gdash"'),
      "| prices:", s.count("data-oid"))
