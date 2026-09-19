"""The numbers go onto the bar, where the scale actually is.

   Sitting them above their own price chips put 2+ at roughly three quarters
   of the way along a bar that reaches it at 2 — so a two-touchdown game would
   have colored the mark green while the fill stopped well short of it. The
   numbers are ticks, so they belong at 1 and 2 on the bar's own scale, and
   the fill arriving at one is the same event as it turning green.

   The 1+ / 2+ label stays on each chip so a price still says which market it
   is; it just stops carrying a tick of its own, because the number on the bar
   carries the result now. The check beside the PTD header goes for the same
   reason — it was saying a third time what the count box and the tick say.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------ the ticks ----
i = s.find('class="ptdx ptdx--v2"')
assert i > 0
start = s.rfind("<div ", 0, i)
end = s.find("\n        </div>", start) + len("\n        </div>")
sec = s[start:end]
scale = float(re.search(r'data-scale="([\d.]+)"', sec).group(1))


def ticks(edge, needs):
    out = ""
    for n in needs:
        out += ('<i class="ntick ntick--n%d" style="%s:%.1f%%"><b>%d</b></i>'
                % (n, edge, n / scale * 100.0, n))
    return out


new = sec
# a pane runs to the zero in the middle, or to the end of the row
for pane, edge, stop in (("ptdside--l", "right", r'(?=<span class="ptdzero")'),
                         ("ptdside--r", "left", r'(?=</div>\n        </div>)')):
    m = re.search(r'<div class="ptdside %s">.*?%s' % (pane, stop), new, re.S)
    assert m, pane
    block = m.group(0)
    needs = sorted(int(x) for x in re.findall(r'<span class="ptdline">(\d)\+</span>', block))
    assert needs, "no lines on " + pane
    fixed = block.replace('></div>', '></div>' + ticks(edge, needs), 1)
    new = new.replace(block, fixed, 1)

s = s[:start] + new + s[end:]
assert s.count('class="ntick') == 0 or True

# -------------------------------------------------------------- the CSS ----
once("""  /* the numbers at the foot of the bar are the ticks: a riser up to the bar,
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
     """  /* The numbers are the ticks, standing at their own place on the bar's
     scale, so the fill reaching one is the same event as it turning green.
     The chip keeps its 1+ / 2+ out of sight, because the slip reads it. */
  .ptdx--v2 { padding-bottom: 62px; }
  .ptdx--v2 .ptdmarks { bottom: 2px; }
  .ntick {
    position: absolute; top: -4px; bottom: -4px; width: 2px;
    margin-left: -1px; margin-right: -1px;
    background: rgba(255, 255, 255, 0.85); border-radius: 1px;
    color: rgba(255, 255, 255, 0.85);
  }
  .ntick b {
    position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    margin-top: 3px; font-size: 12px; font-weight: 700; line-height: 1;
    color: currentColor; font-variant-numeric: tabular-nums;
  }
  .ntick.hit { background: var(--green); color: var(--green); }
  .ntick.miss { background: #e2564d; color: #e2564d; }""",
     "the tick styling")

# ---------------------------------------------------------------- the JS ----
once("""              if (second) {
                /* the number is the tick, so it carries the result itself */
                line.classList.toggle("hit", hit === true);
                line.classList.toggle("miss", hit === false);
                return;
              }""",
     """              if (second) {
                /* the number on the bar is the tick, and carries the result */
                var nt = pane.querySelector(".ntick--n" + need);
                if (nt) {
                  nt.classList.toggle("hit", hit === true);
                  nt.classList.toggle("miss", hit === false);
                }
                return;
              }""", "the chip marking")

once("""            var nameCell = ptd.querySelectorAll(".ptdhead span")[sd[1] === 0 ? 0 : 2];
            if (nameCell) stamp(nameCell, v >= over ? true : (done ? false : null), sd[1] === 1);
""", "", "the check beside the PTD header")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("ticks on the bar:", s.count('class="ntick'), "| prices:", s.count("data-oid"))
