"""The PTD section, rebuilt on the TB/CIN card only.

   Three changes, all of them Jose's:
     the count box moves up beside the PTD label, into the empty corner where
     he drew the green circle;
     the white tick comes off the bar, because the 1+ and 2+ at the foot of it
     are the ticks now — each gets a riser up to the bar so it reads as one;
     and those numbers carry the result, green once the man is past them and
     red once the game has ended without it. No check or cross in the section
     any more; the number itself says it.

   Scoped to .ptdx--v2, so the other twenty cards are untouched until he says.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------- the card ----
i = s.find('data-lqb="Baker Mayfield"')
assert i > 0, "the TB/CIN card is not where it was"
start = s.rfind('<div class="gcard"', 0, i)
end = s.find('<button class="gmorebtn"', start)
card = s[start:end]

m = re.search(r'<div class="ptdx"[^>]*>.*?\n        </div>', card, re.S)
assert m, "no PTD section on that card"
sec = m.group(0)

sec2 = sec.replace('<div class="ptdx"', '<div class="ptdx ptdx--v2"', 1)
# the count boxes come up into the head, where the green circles were drawn
sec2 = sec2.replace(
    '<div class="ptdhead ptdhead--bare"><span class="gmk">PTD</span></div>',
    '<div class="ptdhead"><span class="trkbox ptdcount">0</span>'
    '<span class="gmk">PTD</span>'
    '<span class="trkbox ptdcount">0</span></div>', 1)
sec2 = sec2.replace('<div class="ptdrow"><span class="trkbox ptdcount">0</span>',
                    '<div class="ptdrow">', 1)
sec2 = sec2.replace('<span class="trkbox ptdcount">0</span></div>\n        </div>',
                    '</div>\n        </div>', 1)
# the bar keeps no tick of its own; the numbers below are the ticks
sec2 = re.sub(r'<i class="tick"[^>]*></i>', "", sec2)
assert 'class="tick"' not in sec2 and sec2.count("ptdcount") == 2, "the section did not rebuild"

s = s[:start] + card.replace(sec, sec2, 1) + s[end:]

# -------------------------------------------------------------- the CSS ----
once("  .ptdbtn .price { margin: 0; }",
     """  .ptdbtn .price { margin: 0; }

  /* ---- the PTD section, second cut (TB/CIN only for now) ---- */
  /* the running count sits up beside the label, one per quarterback */
  .ptdx--v2 .ptdhead { align-items: center; margin-bottom: 6px; }
  .ptdx--v2 .ptdhead .trkbox { min-width: 40px; padding: 4px 8px; }
  /* the numbers at the foot of the bar are the ticks: a riser up to the bar,
     and the number itself carries the result */
  .ptdx--v2 .ptdline {
    position: relative; padding-top: 9px;
    color: var(--ink); opacity: 0.75;
  }
  .ptdx--v2 .ptdline::before {
    content: ""; position: absolute; top: 0; left: 50%;
    width: 2px; height: 6px; margin-left: -1px;
    background: currentColor; border-radius: 1px;
  }
  .ptdx--v2 .ptdline.hit { color: var(--green); opacity: 1; font-weight: 700; }
  .ptdx--v2 .ptdline.miss { color: #e2564d; opacity: 1; font-weight: 700; }""",
     "the chip price margin")

# ---------------------------------------------------------------- the JS ----
once("""            var tk = pane.querySelector(".tick");
            if (tk) tk.classList.toggle("hit", v >= over);""",
     """            var second = ptd.classList.contains("ptdx--v2");
            var tk = pane.querySelector(".tick");
            if (tk) tk.classList.toggle("hit", v >= over);""", "the tick toggle")

once("""              var old = b.querySelector(".mk");
              if (old) old.parentNode.removeChild(old);
              var hit = v >= need ? true : (done ? false : null);
              if (hit === null) return;
              var m = document.createElement("span");
              m.className = "mk " + (hit ? "ok" : "no");
              m.innerHTML = hit ? CHECK : CROSS;
              b.querySelector(".ptdline").appendChild(m);""",
     """              var old = b.querySelector(".mk");
              if (old) old.parentNode.removeChild(old);
              var hit = v >= need ? true : (done ? false : null);
              var line = b.querySelector(".ptdline");
              if (second) {
                /* the number is the tick, so it carries the result itself */
                line.classList.toggle("hit", hit === true);
                line.classList.toggle("miss", hit === false);
                return;
              }
              if (hit === null) return;
              var m = document.createElement("span");
              m.className = "mk " + (hit ? "ok" : "no");
              m.innerHTML = hit ? CHECK : CROSS;
              line.appendChild(m);""", "the chip marking")

# he asked for the read-time line to come off
s = re.sub(r'\n    <div class="stamp" id="stamp">[^<]*</div>', "", s, count=1)
s = re.sub(r'\n  /\* When the prices were last read off DraftKings\..*?\n  \}\n', "\n", s,
           count=1, flags=re.S)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("TB/CIN on the second cut | stamp gone:", 'id="stamp"' not in s,
      "| prices:", s.count("data-oid"), "| v2 sections:", s.count("ptdx--v2"))
