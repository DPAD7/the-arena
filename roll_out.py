"""Three things at once, all of them already settled on the Tampa card.

   The fights read outward like the football does. Every card was written
   NAME odds / NAME odds, so the left-hand price sat inside the name instead
   of against the edge of the card. The left one turns round: odds NAME, time,
   NAME odds.

   Every passing and scoring section goes onto the second cut — the bar scaled
   nought to two, the numbers standing on it as the marks, both of them drawn
   whether or not anyone prices them, the percentage above the stretch of bar
   it describes and the price below it.

   And the narrow-phone fallback stops applying to those sections. It stacked
   the chips because two 70px chips could not share a 92px half; a chip in the
   second cut is 48px and stands on the bar, which fits at 320.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------- 1. the fights read out ----
flipped = [0]
FIGHT = re.compile(r'(<div class="gcard"(?![^>]*data-lg=")[^>]*>\s*<div class="ghead">)'
                   r'<span class="gteam">([A-Z&;\'. -]+?)(<span class="gml">.*?</span>)</span>',
                   re.S)


def flip(m):
    flipped[0] += 1
    return '%s<span class="gteam gteam--flip">%s%s</span>' % (m.group(1), m.group(3), m.group(2))


s = FIGHT.sub(flip, s)

# ------------------------------------------- 2. every section, second cut ----
rolled = [0]
marks = [0]


def to_v2(m):
    sec = m.group(0)
    if "ptdx--v2" in sec:
        return sec                      # the Tampa card is already there
    sec = sec.replace('<div class="ptdx"', '<div class="ptdx ptdx--v2"', 1)
    sec = re.sub(r'data-scale="[\d.]+"', 'data-scale="2"', sec, count=1)
    sec = re.sub(r'<i class="tick"[^>]*></i>', "", sec)

    def bars(pm):
        pane, edge = pm.group(0), ("right" if "ptdside--l" in pm.group(0) else "left")
        have = set(re.findall(r"ntick--n(\d)", pane))
        add = ""
        for n in ("1", "2"):
            if n not in have:
                add += ('<i class="ntick ntick--n%s" style="%s:%.1f%%"><b>%s</b></i>'
                        % (n, edge, int(n) / 2.0 * 100.0, n))
                marks[0] += 1
        return pane.replace("></div>", "></div>" + add, 1) if add else pane

    sec = re.sub(r'<div class="ptdside ptdside--[lr]">.*?(?=<span class="ptdzero"|$)',
                 bars, sec, flags=re.S)
    rolled[0] += 1
    return sec


s = re.sub(r'<div class="ptdx"[^>]*>.*?\n        </div>', to_v2, s, flags=re.S)

# --------------------------------------- 3. the narrow fallback steps back ----
once("""  @media (max-width: 380px) {
    .ptdx, .ptdx:has(.mk) { padding-bottom: 2px; }
    .ptdmarks {
      position: static; width: auto; margin-top: 8px;
      flex-direction: column; gap: 4px; align-items: center;
    }
  }""",
     """  /* The fallback was for chips 70px wide sharing a 92px half. A chip in the
     second cut is 48px and hangs off the bar, so it fits at 320 and does not
     want stacking. */
  @media (max-width: 380px) {
    .ptdx:not(.ptdx--v2), .ptdx:not(.ptdx--v2):has(.mk) { padding-bottom: 2px; }
    .ptdx:not(.ptdx--v2) .ptdmarks {
      position: static; width: auto; margin-top: 8px;
      flex-direction: column; gap: 4px; align-items: center;
    }
  }""", "the narrow fallback")

# ------------------------------- 4. a fight's moneyline is just a price ----
once("  /* a chip here is a price, nothing else",
     """  /* a fight is won or lost and that is the whole market, so its moneyline
     wants no chance printed beside it */
  .gcard:not([data-lg]) .ghead .pct { display: none; }
  /* a chip here is a price, nothing else""", "the chip comment")

assert s.count("data-oid") == before, "prices lost: %d -> %d" % (before, s.count("data-oid"))
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("fights turned round:", flipped[0],
      "| sections on the second cut:", rolled[0],
      "| marks drawn where nothing was priced:", marks[0],
      "| prices:", s.count("data-oid"))
