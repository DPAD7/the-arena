"""Two heads were malformed, and a side nobody is tracking stops pretending.

   Where a club or a fighter has no price, the dash that stands in for one was
   written inside the same span as the name instead of beside it, and the
   missing close let the rest of the head — the time, the whole other side —
   nest inside it. On the Atlanta card that put Pittsburgh on its own line
   underneath. It reads as a layout fault and is really a broken tag.

   Then: a card that knows no quarterback for one side has nothing to track
   there, so that half of the passing section is not drawn at all — no bar, no
   marks, no count. It was showing an empty bar with a 1 and a 2 on it, which
   says a milestone is being watched when none is.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# --------------------------------------------------------- the two heads ----
once('<span class="gteam gteam--flip"><span class="gml"><span class="gdash">&mdash;</span>'
     'SILVA</span></span>',
     '<span class="gteam gteam--flip"><span class="gml"><span class="gdash">&mdash;</span>'
     '</span>SILVA</span>', "the Silva head")

once('<span class="gteam gteam--off gteam--flip"><span class="gml">'
     '<span class="gdash">&mdash;</span>ATL</span>',
     '<span class="gteam gteam--off gteam--flip"><span class="gml">'
     '<span class="gdash">&mdash;</span></span>ATL</span>', "the Atlanta head")

# nothing else of the shape is left
left = re.findall(r'<span class="gml"><span class="gdash">&mdash;</span>(?!</span>)', s)
assert not left, "still %d malformed heads" % len(left)

# ------------------------------------------- a side with nobody to follow ----
once("""  /* the zero belongs to the bar, not to the top of a row the count box made
     tall, and the label has no reason to stand off from either */""",
     """  /* A side the card knows no quarterback for has nothing to follow, so it
     is not drawn: an empty bar carrying a 1 and a 2 says a milestone is being
     watched when none is. */
  .ptdx--v2 .ptdside--dead .ptdbar, .ptdx--v2 .ptdside--dead .ptdmarks { visibility: hidden; }
  .trkbox--dead { visibility: hidden; }
  /* the zero belongs to the bar, not to the top of a row the count box made
     tall, and the label has no reason to stand off from either */""",
     "the v2 row styling")

once("""  /* Lift each percentage out of its chip and stand it over the bar.""",
     """  /* A half with no man behind it is left blank rather than drawn empty. */
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

  /* Lift each percentage out of its chip and stand it over the bar.""",
     "the percentage lift")

assert s.count("data-oid") == before
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("heads repaired | prices:", s.count("data-oid"))
