"""The question gets the bar to itself, and the shut slip reads like a slip.

   Asking "clear all your picks?" beside a title and a badge left it four
   words on four lines. While it is asking, the bar is the question and
   nothing else; the arrow and the title come back when it is answered.

   And the bar at the foot — the slip when it is shut — was a lone button
   saying Slip (4). It says what it is the way the book's does: how many on
   the left, and on the right what the four of them pay together, which is
   the one number worth seeing without opening anything.
"""
D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------ the question owns the bar ----
once("""  .slipask {
    margin-left: auto; color: var(--ink); font-size: 13.5px; font-weight: 600;
  }
  .sheet__head--slip .slipask ~ .sheet__title { margin-right: 0; }""",
     """  /* while it is asking, the bar is the question — squeezed beside the title
     it came out four words on four lines */
  .slipask {
    flex: 1; text-align: center; color: var(--ink);
    font-size: 15px; font-weight: 600;
  }
  .sheet__head--slip.asking > .sheet__x,
  .sheet__head--slip.asking > .sheet__title { display: none; }""",
     "the question styling")

once("""    function arm(on) { ask.hidden = !on; press.hidden = on; row.hidden = !on; }""",
     """    var bar = press.closest(".sheet__head");
    function arm(on) {
      ask.hidden = !on; press.hidden = on; row.hidden = !on;
      bar.classList.toggle("asking", on);
    }""", "the arming")

# --------------------------------------------------------- the shut slip ----
once('''<div class="slipbar" id="slipbar" hidden>
  <button id="slipopen" type="button">Slip (0)</button>
</div>''',
     '''<div class="slipbar" id="slipbar" hidden>
  <button class="sliptab" id="slipopen" type="button">
    <span class="slipn" id="slipn2">0</span>
    <span class="sliptab__name">Betslip</span>
    <span class="sliptab__pay"><b id="slippay">&mdash;</b><i>parlay</i></span>
  </button>
</div>''', "the shut slip")

once('''  #slipopen {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 16px; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--chip-ink); background: var(--goldgrad);
    border: 0; border-radius: 8px; padding: 8px 22px; cursor: pointer;
  }''',
     '''  .sliptab {
    display: flex; align-items: center; gap: 10px;
    width: 100%; max-width: 520px; padding: 10px 14px;
    background: rgba(16, 42, 74, 0.82);
    -webkit-backdrop-filter: blur(16px) saturate(1.5);
    backdrop-filter: blur(16px) saturate(1.5);
    border: 1px solid rgba(201, 162, 39, 0.55); border-radius: 14px;
    cursor: pointer; text-align: left;
  }
  .sliptab__name {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 18px; letter-spacing: 0.07em;
    text-transform: uppercase; color: var(--ink);
  }
  .sliptab__pay {
    margin-left: auto; display: flex; flex-direction: column;
    align-items: flex-end; line-height: 1.1;
  }
  .sliptab__pay b {
    font-family: Barlow, "Helvetica Neue", Arial, sans-serif;
    font-weight: 700; font-size: 16px; color: var(--amber);
    font-variant-numeric: tabular-nums;
  }
  .sliptab__pay i {
    font-style: normal; font-size: 10.5px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted);
  }''', "the shut-slip styling")

# ---------------------------------------------------------------- the JS ----
once('''    document.getElementById("slipopen").textContent = "Slip (" + on.length + ")";
    document.getElementById("slipn").textContent = on.length;''',
     '''    document.getElementById("slipn").textContent = on.length;
    document.getElementById("slipn2").textContent = on.length;
    document.getElementById("slippay").textContent = parlay(on);''',
     "the slip counter")

once("  function slip() {",
     '''  /* What the picks pay together: every price as a decimal, multiplied, and
     turned back into the way a book writes it. */
  function parlay(picks) {
    var p = 1;
    for (var i = 0; i < picks.length; i++) {
      var n = parseInt(picks[i].childNodes[0].textContent
        .replace(/\\u2212|\\u2013|\\u2014/g, "-").replace(/[^\\-0-9]/g, ""), 10);
      if (isNaN(n) || n === 0) return "\\u2014";
      p *= n > 0 ? 1 + n / 100 : 1 + 100 / -n;
    }
    if (p <= 1) return "\\u2014";
    var a = p >= 2 ? Math.round((p - 1) * 100) : -Math.round(100 / (p - 1));
    return (a > 0 ? "+" : "\\u2212") + Math.abs(a);
  }

  function slip() {''', "the slip function")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("the shut slip reads like a slip | prices:", s.count("data-oid"))
