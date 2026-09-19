"""One board, fed from a pool, so every sport can carry its own weeks.

   The old shape pre-placed everything into the NFL's eighteen weeks, which
   was fine until college wanted weeks of its own -- college week five is not
   NFL week four and never will be. So the cards built by hand, prices and
   settling and all, move into a pool off screen, and one board is filled from
   it: a static card where we have one, a drawn frame where we do not.

   Three views feed the same board. A day shows everything on that date. NFL
   shows one of its eighteen weeks. College shows one of its fifteen. The rail
   on top changes to match; the pills below choose which.
"""
import os
import re

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(D + "/master.html").read()
before = s.count("data-oid")
CFB = open("/tmp/cfb_all.js").read()
FIGHTS = open("/tmp/fights.js").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------- pool, board, and rails ---
# every hand-built card goes into the pool; wk-1 becomes it
once('  <div class="wkboard" id="wk-1">',
     '  <div id="pool" hidden>')
# the other seventeen go away, replaced by the one board
old = "".join('  <div class="wkboard" id="wk-%d" hidden></div>\n' % w for w in range(2, 19))
once(old, '  <div id="board"></div>\n', "the empty week boards")

# boxing comes off the board entirely
m = re.search(r'\s*<div class="gcard" data-fight="garcia-benn".*?\n      </div>\n', s, re.S)
assert m, "boxing card not found"
s = s.replace(m.group(0), "\n", 1)

# ------------------------------------------------------------------ style ---
once("  .wkboard[hidden] { display: none !important; }",
     "  #pool { display: none !important; }\n"
     "  .lgmk[hidden], .dayhead[hidden] { display: none !important; }")

once('    {key: "boxing", label: "Box", ico: "ico/boxing.svg"},\n', "")

# ------------------------------------------------------------------- data ---
once("  var CFB = ", "  var CFB_WEEKS = 15;\n  var CFB = ")
once("  var FIGHTCARDS = ", "  var FIGHTS = " + FIGHTS + ";\n  var FIGHTCARDS = ")
s = re.sub(r'  var CFB = \[\[3,.*?\];\n', "  var CFB = " + CFB + ";\n", s, count=1, flags=re.S)
assert '"401858225"' in s, "college schedule did not land"

now = s.count("data-oid")
gone = len(re.findall(r'<div class="gcard"', open(D + "/master.html").read())) - \
       len(re.findall(r'<div class="gcard"', s))
assert gone == 1, "expected one card to go, %d went" % gone
open(D + "/master.html", "w").write(s)
print("pool + board in place | prices %d -> %d | page %.0f KB"
      % (before, now, len(s) / 1024.0))
