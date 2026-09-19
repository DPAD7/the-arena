"""Under the arrow, what the card actually paid.

   Every leg on the card that settled a winner, shown as its price with the
   market underneath it, and the whole lot priced together as a parlay. Read
   off the marks the settler has already put on the card, so nothing is
   decided twice.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# a place for it, at the top of every card's own sheet
n = s.count('<div class="sheet__scroll">\n          <div class="wprow">')
s = s.replace('<div class="sheet__scroll">\n          <div class="wprow">',
              '<div class="sheet__scroll">\n'
              '          <div class="hits" hidden></div>\n'
              '          <div class="wprow">')
assert n > 0, "no card sheets found"

# ----------------------------------------------------------------- style ----
once("  .wp { color: var(--green);",
     """  /* what the card paid: each winning price with its market underneath */
  .hits[hidden] { display: none !important; }
  .hits { margin-bottom: 12px; }
  .hitshead {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 12px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--muted); margin-bottom: 8px;
  }
  .hitrow { display: flex; flex-wrap: wrap; gap: 10px; }
  .hitleg { display: flex; flex-direction: column; align-items: center; gap: 3px; }
  .hitleg .odds {
    font-family: Barlow, "Helvetica Neue", Arial, sans-serif;
    font-weight: 600; font-size: 13.5px; color: var(--green);
    background: rgba(23, 194, 87, 0.12);
    border: 1px solid rgba(23, 194, 87, 0.5); border-radius: 10px;
    min-width: 56px; padding: 6px 9px; text-align: center;
    font-variant-numeric: tabular-nums;
  }
  .hitleg .mkt {
    font-size: 10.5px; letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--muted); white-space: nowrap;
  }
  .hitpay {
    display: flex; align-items: baseline; gap: 8px; margin-top: 10px;
    padding-top: 9px; border-top: 1px dashed var(--edge);
  }
  .hitpay span {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 12px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted);
  }
  .hitpay b {
    margin-left: auto; font-family: Barlow, sans-serif; font-weight: 700;
    font-size: 19px; color: var(--green); font-variant-numeric: tabular-nums;
  }
  .wp { color: var(--green);""", "the win-probability styling")

# -------------------------------------------------------------------- JS ----
once("  function refreshVisible() {",
     '''  /* ---- what the card paid ----
     A leg counts as a winner where the settler has already marked it: a tick
     against the club, the count box lit on the head-to-head, the number on
     the bar gone green, a tick by the receiver's name. */
  function priceOf(btn) {
    return btn ? (btn.childNodes[0].textContent || "").trim() : "";
  }
  function toDec(a) {
    var n = parseInt(String(a).replace(/\\u2212|\\u2013|\\u2014/g, "-").replace(/[^\\-0-9]/g, ""), 10);
    if (isNaN(n) || n === 0) return null;
    return n > 0 ? 1 + n / 100 : 1 + 100 / -n;
  }
  function showHits(card) {
    var box = card.querySelector(".hits");
    if (!box) return;
    var legs = [];

    card.querySelectorAll(".ghead .gteam").forEach(function (side) {
      var b = side.querySelector(".gml button.price");
      if (b && side.querySelector(":scope > .mk.ok")) {
        legs.push([priceOf(b), (side.textContent.replace(/[^A-Za-z ]/g, "").trim() || "") + " ML"]);
      }
    });

    card.querySelectorAll(".h2hend").forEach(function (end) {
      var b = end.querySelector(".h2hodds button.price");
      var n = end.querySelector(".trkbox");
      if (b && n && n.classList.contains("hit")) legs.push([priceOf(b), "H2H YDS"]);
    });

    card.querySelectorAll(".ptdx").forEach(function (sec) {
      var kind = sec.dataset.kind || "PTD";
      sec.querySelectorAll(".ptdside").forEach(function (pane) {
        pane.querySelectorAll(".ptdbtn").forEach(function (chip) {
          var b = chip.querySelector("button.price");
          var line = chip.querySelector(".ptdline");
          if (!b || !line) return;
          var need = parseInt(line.textContent, 10);
          var tick = pane.querySelector(".ntick--n" + need);
          if (tick && tick.classList.contains("hit")) {
            legs.push([priceOf(b), need + "+ " + kind]);
          }
        });
      });
    });

    card.querySelectorAll(".recman").forEach(function (man) {
      var b = man.querySelector("button.price");
      var nm = man.querySelector(".wrname");
      if (b && nm && nm.querySelector(".mk.ok")) {
        legs.push([priceOf(b),
                   nm.textContent.replace(/[\\u2713\\u2715]/g, "").trim() + " 1+ REC 1Q"]);
      }
    });

    if (!legs.length) { box.hidden = true; box.innerHTML = ""; return; }

    var html = '<div class="hitshead">What this card paid</div><div class="hitrow">';
    var dec = 1, ok = true;
    legs.forEach(function (l) {
      html += '<div class="hitleg"><span class="odds">' + l[0] +
              '</span><span class="mkt">' + l[1] + '</span></div>';
      var d = toDec(l[0]);
      if (d === null) ok = false; else dec *= d;
    });
    html += "</div>";
    if (ok && legs.length > 1) {
      var a = dec >= 2 ? Math.round((dec - 1) * 100) : -Math.round(100 / (dec - 1));
      html += '<div class="hitpay"><span>' + legs.length + " leg parlay</span><b>" +
              (a > 0 ? "+" : "\\u2212") + Math.abs(a) + "</b></div>";
    }
    box.innerHTML = html;
    box.hidden = false;
  }

  function refreshVisible() {''', "the visible refresher")

# run it once the settling is done, for football and for the fights
once("        var clubs = card.querySelectorAll(\".gteam\");",
     "        showHitsLater(card);\n        var clubs = card.querySelectorAll(\".gteam\");",
     "the club marking")
once("  function showHits(card) {",
     "  function showHitsLater(card) { setTimeout(function () { showHits(card); }, 0); }\n"
     "  function showHits(card) {", "the hits function")
once("        settleFight(card, winner, how);",
     "        settleFight(card, winner, how);\n        showHits(card);", "the fight settler")

assert s.count("data-oid") == before
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("hit containers added to %d card sheets | prices: %d" % (n, s.count("data-oid")))
