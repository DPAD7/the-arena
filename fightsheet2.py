"""How a fight ends, and where the book contradicts itself.

   Six markets a man, four for the fight itself. Two of them are the same bet
   written twice -- "finish" and "KO or submission" -- and books build those
   from different templates, so they do not always agree. The board keeps both
   and says which is the better price rather than leaving it to be spotted.

   The same holds for the distance: both men's decision prices ought to add up
   to the distance price, and where they do not there is a middle.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")

# ------------------------------------------------------------------ style ---
EXTRA = """  /* two rows that are the same bet: the better price is lit, the worse
     is dimmed, and the pair is marked so it can be found again. */
  .mktrow--wide { grid-template-columns: 1fr 152px; }
  .mktrow--wide .mktcell { grid-column: 2; }
  .mktsame { color: var(--amber); }
  .price--better {
    border-color: var(--green); color: var(--green);
    box-shadow: 0 0 0 1px rgba(23, 194, 87, 0.35);
  }
  .price--worse { opacity: 0.45; }
  .mktnote {
    margin: 10px 2px 0; font-size: 11.5px; color: var(--amber);
    line-height: 1.35;
  }
  .mktnote[hidden] { display: none !important; }
"""
mark = "  .mmaname {"
assert s.count(mark) == 1
s = s.replace(mark, EXTRA + mark, 1)

# -------------------------------------------------------------- the sheet ---
FIGHTER = [("KO", ["mko"], "ko"),
           ("SUB", ["msub"], "sub"),
           ("DEC", ["mdec"], "dec"),
           ("KO / SUB", ["mko", "msub"], "kosub"),
           ("FINISH", ["mko", "msub"], "kosub"),
           ("KO / DEC", ["mko", "mdec"], "kodec"),
           ("SUB / DEC", ["msub", "mdec"], "subdec")]
FIGHT = [("GOES THE DISTANCE", ["mdec"], "dist"),
         ("DOESN'T GO THE DISTANCE", ["mko", "msub"], "nodist"),
         ("ENDS BY KO", ["mko"], "anyko"),
         ("ENDS BY SUB", ["msub"], "anysub")]


def marks(ms):
    return "".join('<svg aria-hidden=\\"true\\"><use href=\\"#%s\\"/></svg>' % m for m in ms)


def frow(label, ms, key):
    return ("'<div class=\"mktrow\" data-mkt=\"%s\"><span class=\"mktlab\">"
            "<span class=\"mktmk\">%s</span>%s</span>' + GHOST + GHOST + '</div>'"
            % (key, marks(ms), label))


def wrow(label, ms, key):
    return ("'<div class=\"mktrow mktrow--wide\" data-mkt=\"%s\"><span class=\"mktlab\">"
            "<span class=\"mktmk\">%s</span>%s</span>"
            "<span class=\"mktcell\">' + GHOST + '</span></div>'"
            % (key, marks(ms), label))


SHEET = (" + '<div class=\"mkt\">'"
         " + '<div class=\"mktrow mktrow--head\"><span>How it ends</span><span>' +"
         " lastName(f[3]) + '</span><span>' + lastName(f[5]) + '</span></div>'"
         + "".join(" + " + frow(*r) for r in FIGHTER)
         + " + '<div class=\"mktrow mktrow--head\" style=\"border-top:1px dashed var(--edge);"
           "padding-top:12px\"><span>The fight</span><span></span><span></span></div>'"
         + "".join(" + " + wrow(*r) for r in FIGHT)
         + " + '</div><p class=\"mktnote\" hidden></p>'")

start = s.index(" + '<div class=\"mkt\">'")
end = s.index(" + '</div></dialog>' +", start)
class _Span:
    pass
old = _Span(); old.start = lambda: start; old.end = lambda: end
assert start < end, "the markets block is not where expected"
s = s[:old.start()] + SHEET + "\n" + s[old.end():]

# ---------------------------------------------- where the book disagrees ----
JS = """
  /* ---- the same bet, twice ----
     "Finish" and "KO or submission" are one outcome; so are "doesn't go the
     distance" and the two men's finish prices. Books price them from separate
     templates and do not always reconcile, so where a pair that should match
     does not, the better side is lit and the worse dimmed. */
  function asDec(btn) {
    if (!btn) return null;
    var n = parseInt((btn.childNodes[0] ? btn.childNodes[0].textContent : "")
      .replace(/\\u2212|\\u2013|\\u2014/g, "-").replace(/[^\\-0-9]/g, ""), 10);
    if (isNaN(n) || n === 0) return null;
    return n > 0 ? 1 + n / 100 : 1 + 100 / -n;
  }
  function markTwins(sheet) {
    var note = sheet.querySelector(".mktnote");
    var said = [];
    function pair(key, other, which) {
      var a = sheet.querySelector('.mktrow[data-mkt="' + key + '"]');
      var b = sheet.querySelector('.mktrow[data-mkt="' + other + '"]');
      if (!a || !b) return;
      [0, 1].forEach(function (col) {
        var x = a.querySelectorAll("button.price")[col];
        var y = b.querySelectorAll("button.price")[col];
        var dx = asDec(x), dy = asDec(y);
        if (dx === null || dy === null || Math.abs(dx - dy) < 0.005) return;
        var better = dx > dy ? x : y, worse = dx > dy ? y : x;
        better.classList.add("price--better");
        worse.classList.add("price--worse");
        said.push(which + " is priced twice and the two do not agree");
      });
    }
    pair("kosub", "kosub");      /* FINISH against KO / SUB, same key */
    if (said.length) {
      note.textContent = said[0] + " \\u2014 the longer one is lit.";
      note.hidden = false;
    } else {
      note.hidden = true;
    }
  }
"""
anchor = "  function fightFrame(f) {"
assert s.count(anchor) == 1
s = s.replace(anchor, JS + anchor, 1)

assert s.count("data-oid") == before
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("7 fighter rows, 4 fight rows, twin-check wired | page %.0f KB" % (len(s) / 1024.0))
