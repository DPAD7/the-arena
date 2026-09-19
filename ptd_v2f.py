"""The percentages move above the bar, and every bar carries both numbers.

   The strip between the PTD label and the bar was empty, and the chance a
   price implies is exactly the kind of thing that belongs over the stretch of
   bar it describes — so each percentage goes up there, standing over its own
   price.

   It is read off the chip at load rather than written into the markup twice,
   so when refresh.py rewrites a price the percentage above it follows without
   anything else having to know.

   And both marks are always drawn. Burrow is priced at 2+ only, so his bar
   showed a 2 and nothing else, which made the empty half look like it meant
   nothing. The 1 is where one touchdown is whether or not anyone is selling
   it, and it colors from the count like the other, not from a chip that may
   not exist.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# --------------------------------------------- every bar carries 1 and 2 ----
i = s.find('class="ptdx ptdx--v2"')
start = s.rfind("<div ", 0, i)
end = s.find("\n        </div>", start)
sec = s[start:end]
added = [0]


def fill(m):
    block, edge = m.group(0), ("right" if "ptdside--l" in m.group(0) else "left")
    have = set(re.findall(r'ntick--n(\d)', block))
    add = ""
    for n in ("1", "2"):
        if n not in have:
            add += ('<i class="ntick ntick--n%s" style="%s:%.1f%%"><b>%s</b></i>'
                    % (n, edge, int(n) / 2.0 * 100.0, n))
            added[0] += 1
    return block.replace('></div>', '></div>' + add, 1) if add else block


sec = re.sub(r'<div class="ptdside ptdside--[lr]">.*?(?=<span class="ptdzero"|$)',
             fill, sec, flags=re.S)
s = s[:start] + sec + s[end:]
assert s.count('ntick--n1') >= 2

# -------------------------------------------------------------- the CSS ----
once("  /* a chip here is a price, nothing else — and it is 56px only because",
     """  /* the chance a price implies, standing over the stretch of bar it is
     about, in the strip that was empty between the label and the bar */
  .ptdx--v2 .ptdpct {
    position: absolute; top: -18px;
    font-size: 11px; font-weight: 700; color: var(--green);
    font-variant-numeric: tabular-nums; white-space: nowrap;
  }
  .ptdx--v2 .ptdside--l .ptdpct { transform: translateX(50%); }
  .ptdx--v2 .ptdside--r .ptdpct { transform: translateX(-50%); }
  .ptdx--v2 .ptdside--l .ptdpct--n1 { right: 25%; }
  .ptdx--v2 .ptdside--l .ptdpct--n2 { right: 75%; }
  .ptdx--v2 .ptdside--r .ptdpct--n1 { left: 25%; }
  .ptdx--v2 .ptdside--r .ptdpct--n2 { left: 75%; }
  /* a chip here is a price, nothing else — and it is 56px only because""",
     "the chip comment")

# ---------------------------------------------------------------- the JS ----
once("""  showday();""",
     """  /* Lift each percentage out of its chip and stand it over the bar. Read at
     load, so a price rewritten by refresh.py brings its own number with it. */
  document.querySelectorAll(".ptdx--v2 .ptdside").forEach(function (pane) {
    pane.querySelectorAll(".ptdbtn").forEach(function (chip) {
      var pct = chip.querySelector(".pct");
      var line = chip.querySelector(".ptdline");
      if (!pct || !line) return;
      var n = parseInt(line.textContent, 10);
      var out = document.createElement("span");
      out.className = "ptdpct ptdpct--n" + n;
      out.textContent = pct.textContent.trim();
      pane.appendChild(out);
    });
  });

  showday();""", "the start of the day")

# the marks color from the count, so one with nothing priced against it still
# says whether it was reached
once("""            var second = ptd.classList.contains("ptdx--v2");
            var tk = pane.querySelector(".tick");
            if (tk) tk.classList.toggle("hit", v >= over);""",
     """            var second = ptd.classList.contains("ptdx--v2");
            var tk = pane.querySelector(".tick");
            if (tk) tk.classList.toggle("hit", v >= over);
            if (second) {
              pane.querySelectorAll(".ntick").forEach(function (nt) {
                var n = parseInt(nt.textContent, 10);
                var got = v >= n ? true : (done ? false : null);
                nt.classList.toggle("hit", got === true);
                nt.classList.toggle("miss", got === false);
              });
            }""", "the tick toggle")

once("""              if (second) {
                /* the number on the bar is the tick, and carries the result */
                var nt = pane.querySelector(".ntick--n" + need);
                if (nt) {
                  nt.classList.toggle("hit", hit === true);
                  nt.classList.toggle("miss", hit === false);
                }
                return;
              }""",
     """              /* in the second cut the bar's own numbers carry the result */
              if (second) return;""", "the chip marking")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("marks added where none were priced:", added[0],
      "| ticks on the card:", sec.count('class="ntick'))
