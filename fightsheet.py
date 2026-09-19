"""The fights get a sheet of their own, behind the same yellow arrow.

   Seven ways a fight ends, each for each man: knockout, submission, decision,
   a finish either way, and the three double chances. DraftKings prices none of
   them for us yet, so every slot is empty -- the frame stands and the prices
   drop into it when they arrive, the way the football cards already work.

   The three marks are drawn once as symbols: bet365's glove with a burst over
   the knuckles, a figure of eight for the rope, three judges for the cards.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")

KO = open("/tmp/ko.svg").read()
SUB = open("/tmp/sub.svg").read()
DEC = open("/tmp/dec.svg").read()


def as_symbol(svg, name):
    box = re.search(r'viewBox="([^"]*)"', svg).group(1)
    inner = re.search(r'<svg[^>]*>(.*)</svg>', svg, re.S).group(1)
    return '<symbol id="%s" viewBox="%s">%s</symbol>' % (name, box, inner)


SYMS = as_symbol(KO, "mko") + as_symbol(SUB, "msub") + as_symbol(DEC, "mdec")
anchor = '<symbol id="fb" viewBox="0 0 50 50">'
assert s.count(anchor) == 1
i = s.index(anchor)
s = s[:i] + SYMS + s[i:]

# ------------------------------------------------------------------ style ---
STYLE = """  /* ---- how a fight ends ----
     Seven markets, each man his own column. No prices yet, so every slot is
     the same empty box the football cards use. */
  .mkt { margin-top: 2px; }
  .mktrow {
    display: grid; grid-template-columns: 1fr 72px 72px;
    align-items: center; gap: 8px; padding: 7px 0;
    border-top: 1px dashed var(--edge);
  }
  .mktrow--head {
    border-top: 0; padding-bottom: 9px;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 12px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted); text-align: center;
  }
  .mktrow--head span:first-child { text-align: left; }
  .mktlab {
    display: flex; align-items: center; gap: 9px; min-width: 0;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 14px; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--ink);
  }
  .mktmk { display: flex; align-items: center; gap: 3px; flex: none; }
  .mktmk svg { width: 21px; height: 21px; display: block; color: var(--muted); }
  .mktrow .ghost, .mktrow .price { width: 100%; margin: 0; }
  .mktrow .price { min-width: 0; }
"""
mark = "  .mmaname {"
assert s.count(mark) == 1
s = s.replace(mark, STYLE + mark, 1)

# -------------------------------------------------------------- the sheet ---
MARKETS = [("KO", ["mko"]), ("SUB", ["msub"]), ("DEC", ["mdec"]),
           ("FINISH", ["mko", "msub"]), ("KO / DEC", ["mko", "mdec"]),
           ("KO / SUB", ["mko", "msub"]), ("SUB / DEC", ["msub", "mdec"])]


def row(label, marks):
    use = "".join('<svg aria-hidden="true"><use href="#%s"/></svg>' % m for m in marks)
    return ("'<div class=\"mktrow\"><span class=\"mktlab\">"
            "<span class=\"mktmk\">%s</span>%s</span>'"
            " + GHOST + GHOST + '</div>'" % (use.replace("'", "\\'"), label))


SHEET = (" + '<div class=\"mkt\">'"
         " + '<div class=\"mktrow mktrow--head\"><span>How it ends</span><span>' +"
         " lastName(f[3]) + '</span><span>' + lastName(f[5]) + '</span></div>'"
         + "".join(" + " + row(l, m) for l, m in MARKETS)
         + " + '</div>'")

old = """      /* the weight sits under the clock, which puts it on the names' own line
         rather than on a line of its own. No arrow either: ESPN publishes no
         win probability for MMA, so a fight has no sheet to open. */
      '</div>';"""
new = ("""      /* the weight sits under the clock, which puts it on the names' own line
         rather than on a line of its own. The arrow opens the ways a fight
         can end -- no win probability, since ESPN publishes none for MMA. */
      '<button class="gmorebtn" type="button" aria-label="More">' +
      '<svg viewBox="0 0 24 24" width="18" height="18">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg></button>' +
      '<dialog class="sheet gsheet"><div class="sheet__head">' +
      '<button class="sheet__x" type="button" data-shut aria-label="Back">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<h2 class="sheet__title">' + lastName(f[3]) + ' v ' + lastName(f[5]) + '</h2>' +
      '<span aria-hidden="true"></span></div>' +
      '<div class="sheet__scroll"><div class="hits" hidden></div>'"""
       + SHEET +
       """ + '</div></dialog>' +
      '</div>';""")
assert s.count(old) == 1
s = s.replace(old, new, 1)

assert s.count("data-oid") == before
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("seven markets behind the arrow | page %.0f KB" % (len(s) / 1024.0))
