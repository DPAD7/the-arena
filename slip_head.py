"""Clear All moves up into the slip's top bar, beside a count.

   It was a full-width button at the foot, under the one control that matters
   there — so the thing you press most often sat beneath the thing you press
   once. The bar carries it instead, the way the book's own slip does: how
   many are on it, what it is, and the way to empty it, all on one line.
"""
D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ----------------------------------------------------------- the markup ----
once('''    <h2 class="sheet__title" id="sliptitle">Betslip</h2>
    <span aria-hidden="true"></span>
  </div>''',
     '''    <h2 class="sheet__title" id="sliptitle">'''
     '''<span class="slipn" id="slipn">0</span>Betslip</h2>
    <span class="slipask" id="slipask" hidden>Clear all your picks?</span>
    <button id="slipclear" type="button">Clear all</button>
  </div>
  <div class="slipconfirm" id="slipconfirm" hidden>
    <button class="slipno" id="slipcancel" type="button">Cancel</button>
    <button class="slipyes" id="slipyes" type="button">Clear All</button>
  </div>''', "the slip title")

once('''  <div class="sheet__head">
    <button class="sheet__x" type="button" data-shuts="slipsheet"''',
     '''  <div class="sheet__head sheet__head--slip">
    <button class="sheet__x" type="button" data-shuts="slipsheet"''', "the slip head")

once('''    <a id="sliplink" href="#" target="_blank" rel="noopener">Add to betslip</a>
    <button id="slipclear" type="button">Clear all</button>
  </div>''',
     '''    <a id="sliplink" href="#" target="_blank" rel="noopener">Add to betslip</a>
  </div>''', "the slip foot")

# -------------------------------------------------------------- the CSS ----
once('''  #slipclear {
    display: block; width: 100%; text-align: center; margin-top: 10px;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--muted); background: none;
    border: 1px solid var(--edge); border-radius: 8px; padding: 8px; cursor: pointer;
  }
  #slipclear:hover { color: var(--ink); border-color: var(--muted); }''',
     '''  /* the bar reads: how many, what it is, and the way to empty it */
  .sheet__head--slip { display: flex; align-items: center; gap: 10px; }
  .sheet__head--slip .sheet__title {
    justify-self: auto; margin-right: auto; text-align: left;
    display: inline-flex; align-items: center; gap: 8px;
  }
  .slipn {
    display: inline-flex; align-items: center; justify-content: center;
    min-width: 22px; height: 22px; padding: 0 5px; border-radius: 999px;
    background: var(--goldgrad); color: var(--chip-ink);
    font-family: Barlow, "Helvetica Neue", Arial, sans-serif;
    font-weight: 700; font-size: 12.5px; letter-spacing: 0;
    font-variant-numeric: tabular-nums;
  }
  #slipclear {
    flex: none;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--muted); background: none;
    border: 1px solid var(--edge); border-radius: 8px;
    padding: 6px 11px; cursor: pointer;
  }
  #slipclear:hover { color: var(--ink); border-color: var(--muted); }
  .slipask {
    margin-left: auto; color: var(--ink); font-size: 13.5px; font-weight: 600;
  }
  .sheet__head--slip .slipask ~ .sheet__title { margin-right: 0; }
  .slipconfirm {
    display: flex; gap: 10px; padding: 10px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.13);
  }
  .slipconfirm[hidden] { display: none !important; }
  .slipconfirm button {
    flex: 1; padding: 11px 8px; border-radius: 10px; cursor: pointer;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 15px; letter-spacing: 0.07em; text-transform: uppercase;
  }
  .slipno { background: none; border: 1px solid var(--edge); color: var(--muted); }
  .slipno:hover { color: var(--ink); border-color: var(--muted); }
  .slipyes { background: var(--goldgrad); border: 0; color: var(--chip-ink); }''',
     "the clear-all styling")

# ---------------------------------------------------------------- the JS ----
once('''    document.getElementById("slipopen").textContent = "Slip (" + on.length + ")";''',
     '''    document.getElementById("slipopen").textContent = "Slip (" + on.length + ")";
    document.getElementById("slipn").textContent = on.length;''', "the slip counter")

once('''  document.getElementById("slipclear").addEventListener("click", function () {
    document.querySelectorAll("button.price.on").forEach(function (b) { b.click(); });
  });''',
     '''  /* Clearing the slip is the one thing on the page that cannot be undone,
     so the bar asks before it does it. */
  (function () {
    var ask = document.getElementById("slipask");
    var press = document.getElementById("slipclear");
    var row = document.getElementById("slipconfirm");
    function arm(on) { ask.hidden = !on; press.hidden = on; row.hidden = !on; }
    press.addEventListener("click", function () { arm(true); });
    document.getElementById("slipcancel").addEventListener("click", function () { arm(false); });
    document.getElementById("slipyes").addEventListener("click", function () {
      document.querySelectorAll("button.price.on").forEach(function (b) { b.click(); });
      arm(false);
    });
    /* never reopens still asking */
    document.getElementById("slipsheet").addEventListener("close", function () { arm(false); });
  }());''', "the clear-all handler")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("clear all is in the bar | prices:", s.count("data-oid"))
