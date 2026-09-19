"""The slip and the card detail become sheets.

   Ported from QB Spy: up from the bottom on the iOS curve, pulled back down
   to dismiss, a fixed bar on top while the middle scrolls, the page behind
   held still. The motion only; the data stays ours.

   The card's detail dialog is left a child of its own card, so the live
   updater's card.querySelector(".wpx svg") still finds the chart.
"""
import re
import sys

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ---------------------------------------------------------------- the CSS ----
SHEET_CSS = '''
  /* ---- Sheets ----
     A sheet comes up from the bottom and goes back down the same way. The
     pull only drags when what is under the finger is already at its top;
     anywhere else the same movement is a scroll, which is what it looks
     like it should be. */
  dialog.sheet {
    display: flex; flex-direction: column;
    width: min(560px, calc(100% - 32px)); max-width: none;
    height: auto; max-height: 88vh;
    margin: auto; padding: 0;
    background: rgba(12, 35, 64, 0.93);
    -webkit-backdrop-filter: blur(22px) saturate(1.5);
    backdrop-filter: blur(22px) saturate(1.5);
    color: var(--ink); font: inherit;
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 16px;
    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.62);
    overflow: hidden;
  }
  /* display:flex beats the rule that hides a shut dialog, so say it again. */
  dialog.sheet:not([open]) { display: none; }
  dialog.sheet::backdrop { background: rgba(0, 0, 0, 0.58); }
  .sheet__head {
    flex: none; display: grid; grid-template-columns: 40px 1fr 40px;
    align-items: center; gap: 8px; padding: 9px 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.13);
  }
  .sheet__head > :first-child { justify-self: start; }
  .sheet__head > :last-child { justify-self: end; }
  .sheet__title {
    margin: 0; justify-self: center; text-align: center;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 19px; letter-spacing: 0.07em;
    text-transform: uppercase; color: var(--ink); white-space: nowrap;
    overflow: hidden; text-overflow: ellipsis; max-width: 100%;
  }
  .sheet__x {
    background: none; border: 0; padding: 6px; line-height: 0;
    color: var(--amber); cursor: pointer; border-radius: 8px;
  }
  .sheet__scroll {
    flex: 1 1 auto; min-height: 0; overflow-y: auto;
    -webkit-overflow-scrolling: touch; padding: 10px 14px 14px;
  }
  .sheet__foot {
    flex: none; padding: 10px 14px calc(12px + env(safe-area-inset-bottom));
    border-top: 1px solid rgba(255, 255, 255, 0.13);
  }
  .sheet__foot #sliplink { margin-top: 0; }
  .slipnone { color: var(--muted); text-align: center; padding: 26px 0; }
  @media (max-width: 700px) {
    dialog.sheet {
      width: 100%; max-width: 100%; max-height: 88vh;
      margin: auto 0 0; padding-top: 18px;
      border: 0; border-radius: 20px 20px 0 0;
      box-shadow: 0 -10px 50px rgba(0, 0, 0, 0.62);
      animation: sheet-up 0.3s cubic-bezier(0.32, 0.72, 0, 1);
    }
    /* the handle that says it can be pulled */
    dialog.sheet::before {
      content: ''; position: absolute; top: 7px; left: 50%;
      width: 38px; height: 5px; margin-left: -19px;
      background: rgba(255, 255, 255, 0.3); border-radius: 999px;
    }
    /* while a finger is on it there is no animation to fight */
    dialog.sheet--dragging { animation: none; transition: none; }
    /* and when it is let go it falls back into place or leaves */
    dialog.sheet--settling {
      animation: none; transition: transform 0.26s cubic-bezier(0.32, 0.72, 0, 1);
    }
  }
  @keyframes sheet-up {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }
  /* the page behind a sheet is held where it was */
  body.sheeted { position: fixed; left: 0; right: 0; width: 100%; overflow: hidden; }
  @media (prefers-reduced-motion: reduce) {
    dialog.sheet { animation: none; }
    dialog.sheet--settling { transition: none; }
  }
</style>'''
once("</style>", SHEET_CSS, "close of the stylesheet")

# the slip panel is no longer a panel
once(""".slippanel {
    position: fixed; left: 0; right: 0; bottom: 54px; z-index: 9;
    max-height: 55vh; overflow-y: auto;
    background: rgba(9, 26, 49, 0.6);
    -webkit-backdrop-filter: blur(18px) saturate(1.4);
    backdrop-filter: blur(18px) saturate(1.4);
    border-top: 1px solid rgba(255, 255, 255, 0.14);
    padding: 8px 16px 12px;
  }
  .slippanel[hidden] { display: none !important; }
  """, "", "the old slip panel's CSS")

# ------------------------------------------------------------- the markup ----
ARROW = ('<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">'
         '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" '
         'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>')

once('''<div class="slippanel" id="slippanel" hidden>
  <div id="sliplist"></div>
  <button id="slipclear" type="button">Clear all</button>
  <a id="sliplink" href="#" target="_blank" rel="noopener">Add to betslip</a>
</div>''',
     '''<dialog class="sheet" id="slipsheet" aria-labelledby="sliptitle">
  <div class="sheet__head">
    <button class="sheet__x" type="button" data-shuts="slipsheet" aria-label="Back">%s</button>
    <h2 class="sheet__title" id="sliptitle">Betslip</h2>
    <span aria-hidden="true"></span>
  </div>
  <div class="sheet__scroll"><div id="sliplist"></div></div>
  <div class="sheet__foot">
    <a id="sliplink" href="#" target="_blank" rel="noopener">Add to betslip</a>
    <button id="slipclear" type="button">Clear all</button>
  </div>
</dialog>''' % ARROW, "the slip markup")

# every card's detail becomes its own sheet, still a child of its own card
CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
GMORE = re.compile(r'<div class="gmore" hidden>(.*?)\n        </div>', re.S)
TEAMS = re.compile(r'<span class="gteam[^"]*">(?:<span class="gml">.*?</span>)?'
                   r'([A-Za-z&;. ]+?)(?:<span class="gml">.*?</span>)?</span>', re.S)
made = [0]


def to_sheet(mm):
    card = mm.group(0)
    g = GMORE.search(card)
    if not g:
        return card
    names = [t.strip() for t in TEAMS.findall(card[:g.start()]) if t.strip()]
    title = " v ".join(names[:2]) if len(names) >= 2 else (names[0] if names else "Detail")
    made[0] += 1
    sheet = ('<dialog class="sheet gsheet">\n'
             '          <div class="sheet__head">\n'
             '            <button class="sheet__x" type="button" data-shut aria-label="Back">%s</button>\n'
             '            <h2 class="sheet__title">%s</h2>\n'
             '            <span aria-hidden="true"></span>\n'
             '          </div>\n'
             '          <div class="sheet__scroll">%s\n          </div>\n'
             '        </dialog>' % (ARROW, title, g.group(1)))
    return card[:g.start()] + sheet + card[g.end():]


s = CARD.sub(to_sheet, s)
assert made[0] > 0, "no card details were turned into sheets"

# ----------------------------------------------------------------- the JS ----
once('''  document.querySelectorAll(".gmorebtn").forEach(function (b) {
    b.addEventListener("click", function () {
      var more = b.nextElementSibling;
      more.hidden = !more.hidden;
      b.classList.toggle("open", !more.hidden);
    });
  });''',
     '''  document.querySelectorAll(".gmorebtn").forEach(function (b) {
    b.addEventListener("click", function () {
      var sheet = b.nextElementSibling;
      if (sheet && sheet.tagName === "DIALOG") openSheet(sheet);
    });
  });''', "the dropdown toggle")

# the slip opens and shuts as a sheet
once('''  document.getElementById("slipopen").addEventListener("click", function () {
    var panel = document.getElementById("slippanel");
    panel.hidden = !panel.hidden;
  });''',
     '''  document.getElementById("slipopen").addEventListener("click", function () {
    openSheet(document.getElementById("slipsheet"));
  });''', "the slip opener")

once('''    var bar = document.getElementById("slipbar");
    var panel = document.getElementById("slippanel");
    bar.hidden = on.length === 0;
    if (!on.length) { panel.hidden = true; return; }''',
     '''    var bar = document.getElementById("slipbar");
    var sheet = document.getElementById("slipsheet");
    bar.hidden = on.length === 0;
    if (!on.length) { if (sheet.open) sheet.close(); return; }''',
     "the slip's empty case")

SHEET_JS = '''  /* ---- Sheets: opening, shutting, and the page held still behind ---- */
  var heldAt = 0;
  function openSheet(d) {
    if (!d || d.open) return;
    heldAt = window.pageYOffset || document.documentElement.scrollTop || 0;
    document.body.style.top = (-heldAt) + "px";
    document.body.classList.add("sheeted");
    d.showModal();
  }
  function letGo() {
    if (document.querySelector("dialog.sheet[open]")) return;
    document.body.classList.remove("sheeted");
    document.body.style.top = "";
    window.scrollTo(0, heldAt);
  }
  /* A dialog's close does not bubble, so it is caught on the way down. Every
     way out comes through here — the arrow, Escape, and the pull. */
  document.addEventListener("close", function (e) {
    if (!(e.target.matches && e.target.matches("dialog.sheet"))) return;
    e.target.classList.remove("sheet--dragging", "sheet--settling");
    e.target.style.transform = "";
    letGo();
  }, true);
  document.addEventListener("click", function (e) {
    var hit = e.target.closest("[data-shuts], [data-shut]");
    if (!hit) return;
    var d = hit.hasAttribute("data-shuts")
      ? document.getElementById(hit.getAttribute("data-shuts"))
      : hit.closest("dialog.sheet");
    if (d && d.open) d.close();
  });

  /* ---- Pulling a sheet away ----
     Whether a finger moving down means "put this away" or "scroll what is in
     it" is answered by whichever box is actually under the finger, and only
     when that box is already at its top. Nothing here runs on a wide
     window, where a sheet is a centered card instead. */
  (function () {
    var PULL = window.matchMedia("(max-width: 700px)");
    var sheet = null, scroller = null, from = 0, at = 0, began = 0, pulling = false;

    function scrollerUnder(node, within) {
      while (node && node !== within) {
        if (node.scrollHeight > node.clientHeight + 1) {
          var how = getComputedStyle(node).overflowY;
          if (how === "auto" || how === "scroll") return node;
        }
        node = node.parentElement;
      }
      return within;
    }

    function settle(said) {
      if (!sheet) return;
      var going = sheet;
      going.classList.remove("sheet--dragging");
      going.classList.add("sheet--settling");
      if (said === "away") {
        going.style.transform = "translateY(100%)";
        window.setTimeout(function () {
          going.classList.remove("sheet--settling");
          going.style.transform = "";
          if (going.open) going.close();
        }, 260);
      } else {
        going.style.transform = "";
        window.setTimeout(function () {
          going.classList.remove("sheet--settling");
        }, 260);
      }
      sheet = null; scroller = null; pulling = false;
    }

    document.addEventListener("pointerdown", function (e) {
      if (!PULL.matches || e.pointerType === "mouse") return;
      var open = e.target.closest && e.target.closest("dialog.sheet[open]");
      if (!open) return;
      /* a button is a button, and the chart reads under its own finger */
      if (e.target.closest("button, a, input, label, select, textarea, svg")) return;
      sheet = open;
      scroller = scrollerUnder(e.target, open);
      from = e.clientY; at = 0; began = Date.now(); pulling = false;
    }, { passive: true });

    document.addEventListener("pointermove", function (e) {
      if (!sheet) return;
      var moved = e.clientY - from;
      if (!pulling) {
        /* downward, past a few pixels, and only from the very top */
        if (moved < 8 || (scroller && scroller.scrollTop > 0)) {
          if (moved < -8 || (scroller && scroller.scrollTop > 0)) sheet = null;
          return;
        }
        pulling = true;
        sheet.classList.add("sheet--dragging");
      }
      at = Math.max(0, moved);           /* up does nothing; it is already up */
      sheet.style.transform = "translateY(" + at + "px)";
      if (e.cancelable) e.preventDefault();
    }, { passive: false });

    document.addEventListener("pointerup", function () {
      if (!sheet) return;
      if (!pulling) { sheet = null; scroller = null; return; }
      /* far enough, or fast enough — a flick should not travel the whole way */
      var far = at > sheet.getBoundingClientRect().height * 0.25;
      var fast = at / Math.max(1, Date.now() - began) > 0.5;
      settle(far || fast ? "away" : "back");
    }, { passive: true });

    document.addEventListener("pointercancel", function () {
      if (sheet && pulling) settle("back"); else sheet = null;
    }, { passive: true });
  }());

  function labelFor(btn) {'''
once("  function labelFor(btn) {", SHEET_JS, "the head of labelFor")

# an empty slip says so rather than showing nothing
once('''    var list = document.getElementById("sliplist");
    list.innerHTML = "";''',
     '''    var list = document.getElementById("sliplist");
    list.innerHTML = "";
    if (!on.length) {
      list.innerHTML = '<p class="slipnone">Nothing selected yet</p>';
    }''', "the slip list")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("card details turned into sheets:", made[0])
print("prices on the board:", s.count("data-oid"))
