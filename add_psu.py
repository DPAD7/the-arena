"""Penn State at Temple joins the Saturday board, and Mateer's 1+ fills the
   slot that was standing empty beside his 2+.

   Both prices read off DraftKings this morning:
     Rocco Becht (PSU) 2+ passing touchdowns   -256
     John Mateer (OKLA) 1+ passing touchdowns  -407
   The Penn State game was not on the board at all, so the card is built from
   the same shape every other college card has — moneylines outward, the
   passing section on the second cut, the arrow to the win probability.

   Only the two markets asked for are filled. Becht's 1+ is priced at -1660
   and Temple has nobody quoted; those slots stay placeholders.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")

BECHT2 = "0QA368313179#2278330412_13L87637Q1-2015862131Q20"
MATEER1 = "0QA367934595#2276939120_13L87637Q1-192366120Q20"
GHOST = '<span class="ghost" aria-hidden="true"></span>'


def price(oid, shown, pct):
    return ('<button class="price" type="button" data-oid="%s">%s '
            '<span class="pct">%d%%</span></button>' % (oid, shown, pct))


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ---------------------------------------------- Mateer's first touchdown ----
once('<span class="ptdbtn ptdbtn--n1"><span class="ptdline">1+</span>%s</span>'
     '<span class="ptdbtn ptdbtn--n2"><span class="ptdline">2+</span>'
     '<button class="price" type="button" data-oid="0QA367934595#2276939124'
     % GHOST,
     '<span class="ptdbtn ptdbtn--n1"><span class="ptdline">1+</span>%s</span>'
     '<span class="ptdbtn ptdbtn--n2"><span class="ptdline">2+</span>'
     '<button class="price" type="button" data-oid="0QA367934595#2276939124'
     % price(MATEER1, "&minus;407", 80), "Mateer's 1+ slot")


# ------------------------------------------------- the Penn State card ----
def pane(which, chips):
    edge = "right" if which == "l" else "left"
    ticks = "".join('<i class="ntick ntick--n%d" style="%s:%.1f%%"><b>%d</b></i>'
                    % (k, edge, k / 2.0 * 100.0, k) for k in (1, 2))
    marks = "".join('<span class="ptdbtn ptdbtn--n%d"><span class="ptdline">%d+</span>%s</span>'
                    % (k, k, chips.get(k, GHOST)) for k in (1, 2))
    return ('<div class="ptdside ptdside--%s">'
            '<div class="ptdbar"><div class="ptdfill" style="%s:0; width:0%%"></div>%s</div>'
            '<div class="ptdmarks">%s</div></div>' % (which, edge, ticks, marks))


# ESPN has Penn State at 94.2 before kickoff; the chart is drawn to that and
# redrawn from the live feed once the game is on.
Y = 55 - (94.2 - 50) / 50.0 * 55

CHART = ('<div class="wpx"><svg viewBox="0 0 300 110" preserveAspectRatio="none">'
         '<defs><clipPath id="psutem-o"><rect x="0" y="0" width="300" height="55"/></clipPath>'
         '<clipPath id="psutem-u"><rect x="0" y="55" width="300" height="55"/></clipPath></defs>'
         '<line class="wpe" x1="0" y1="55" x2="300" y2="55"/>'
         '<polygon points="0.0,{y} 300.0,{y} 300,55 0,55" fill="var(--amber)" opacity="0.18" clip-path="url(#psutem-o)"/>'
         '<polygon points="0.0,{y} 300.0,{y} 300,55 0,55" fill="#5aa9ff" opacity="0.18" clip-path="url(#psutem-u)"/>'
         '<polyline points="0.0,{y} 300.0,{y}" fill="none" stroke="var(--amber)" stroke-width="2" '
         'stroke-dasharray="4 4" vector-effect="non-scaling-stroke" clip-path="url(#psutem-o)"/>'
         '<polyline points="0.0,{y} 300.0,{y}" fill="none" stroke="#5aa9ff" stroke-width="2" '
         'stroke-dasharray="4 4" vector-effect="non-scaling-stroke" clip-path="url(#psutem-u)"/>'
         '</svg><div class="wpscale"><span>100</span><span>50</span><span>100</span></div></div>'
         ).format(y="%.1f" % Y)

CARD = '''      <div class="gcard" data-espn="401858442" data-lg="college-football" data-lhome="0" data-lqb="Rocco Becht" data-kick="2026-09-12T16:00Z">
        <div class="ghead"><span class="gteam gteam--flip"><span class="gml">@MLL@</span>PSU</span><span class="gtime">12:00 PM</span><span class="gteam">TEM<span class="gml">@MLR@</span></span></div>
        <div class="ptdx ptdx--v2" data-scale="2" data-need="2" data-kind="PTD">
          <div class="ptdhead"><span style="color:var(--amber)">Becht</span><span class="gmk">PTD</span><span style="color:#5aa9ff">&mdash;</span></div>
          <div class="ptdrow"><span class="trkbox ptdcount">0</span>@PANEL@<span class="ptdzero">0</span>@PANER@<span class="trkbox ptdcount">0</span></div>
        </div>
        <button class="gmorebtn" type="button" aria-label="More"><svg viewBox="0 0 24 24" width="18" height="18"><polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg></button>
        <dialog class="sheet gsheet">
          <div class="sheet__head">
            <button class="sheet__x" type="button" data-shut aria-label="Back"><svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true"><path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>
            <h2 class="sheet__title">PSU v TEM</h2>
            <span aria-hidden="true"></span>
          </div>
          <div class="sheet__scroll">
          <div class="wprow"><span class="wpteam" style="color:var(--amber)">PSU</span><span class="wpbig">94.2%</span></div>
          @CHART@
          <div class="wprow"><span class="wpteam" style="color:#5aa9ff">TEM</span><span class="wpbig">5.8%</span></div>
          </div>
        </dialog>
      </div>
'''
for tok, val in (("@MLL@", price("0ML86111684_3", "&minus;3200", 97)),
                 ("@MLR@", price("0ML86111684_1", "+1400", 7)),
                 ("@PANEL@", pane("l", {2: price(BECHT2, "&minus;256", 72)})),
                 ("@PANER@", pane("r", {})),
                 ("@CHART@", CHART)):
    assert tok in CARD, tok
    CARD = CARD.replace(tok, val)

# it kicks at noon with the others, so it goes after them on the Saturday board
anchor = s.find('data-espn="401856679"')
end = s.find("\n      </div>\n", anchor) + len("\n      </div>\n")
s = s[:end] + CARD + s[end:]

assert s.count("data-oid") == before + 4, "expected four new prices: two moneylines, Becht 2+, Mateer 1+"
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("prices on the board:", s.count("data-oid"), "(was %d)" % before)
