"""Four sports on one board, and a rail to pick between them.

   The week carousel stays the spine: everything is placed in the week its own
   date falls in, so college Saturday and a Saturday fight card sit beside the
   NFL games they share a weekend with. The pills filter what is shown without
   moving anything.

   College is moneyline, anytime touchdown and passing touchdowns. It has no
   head-to-head -- DraftKings' league-wide category 1185 answers with nothing
   for NCAAF -- so that section is simply absent rather than drawn empty.
"""
import json
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")
CFB = open("/tmp/cfbsched.js").read()
MMA = open("/tmp/mmasched.js").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------------ style ---
once("""  /* the weeks, along the top, the way the league counts them */""",
     """  /* the sports, as pills under the weeks */
  .sportbar {
    grid-column: 1 / -1; display: flex; gap: 8px; overflow-x: auto;
    scrollbar-width: none; padding: 8px 14px 4px; margin: 0 -14px;
  }
  .sportbar::-webkit-scrollbar { display: none; }
  .sptab {
    flex: none; display: inline-flex; align-items: center; gap: 6px;
    appearance: none; cursor: pointer;
    background: rgba(255, 255, 255, 0.05); border: 1px solid var(--edge);
    border-radius: 999px; padding: 6px 13px;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 13px; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted); white-space: nowrap;
  }
  .sptab img { width: 15px; height: 15px; display: block; }
  .sptab[aria-selected="true"] {
    color: #10161f; background: var(--amber); border-color: var(--amber);
  }
  .sptab:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }
  .lgmk {
    margin: 16px 0 -4px; display: flex; align-items: center; gap: 7px;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 13px; letter-spacing: 0.12em;
    text-transform: uppercase; color: var(--muted);
  }
  .lgmk img { width: 14px; height: 14px; }
  .mmacard .ghead { justify-content: space-between; }
  .mmaname {
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 15px; letter-spacing: 0.04em;
    color: var(--ink); text-transform: uppercase; line-height: 1.15;
  }
  /* the weeks, along the top, the way the league counts them */""",
     "the week styling")

# ----------------------------------------------------------------- header ---
once('    <div class="weekbar" id="weekbar" role="tablist" aria-label="Week"></div>',
     '    <div class="weekbar" id="weekbar" role="tablist" aria-label="Week"></div>\n'
     '    <div class="sportbar" id="sportbar" role="tablist" aria-label="Sport"></div>',
     "the week bar")

# ------------------------------------------------------------------- data ---
once("  var WEEKS = 18;",
     """  var WEEKS = 18;
  /* College, three weeks out: [week, id, kickoff, away, home, away passer,
     his id, home passer, his id, how many of the two are Power Four]. */
  var CFB = """ + CFB + """;
  /* Every UFC and Contender Series card still to come: [week, id, start, name] */
  var MMA = """ + MMA + """;
  var SPORTS = [
    {key: "all", label: "All", ico: ""},
    {key: "nfl", label: "NFL", ico: "ico/nfl.svg"},
    {key: "college-football", label: "NCAAF", ico: "ico/cfb.svg"},
    {key: "boxing", label: "Box", ico: "ico/boxing.svg"},
    {key: "mma", label: "MMA", ico: "ico/mma.svg"}
  ];
  var sport = "all";""", "the week count")

# ---------------------------------------------------------------- drawing ---
once("""  var drawn = {1: true};""",
     """  /* a college card: moneyline, anytime touchdown, passing touchdowns.
     No head-to-head -- DraftKings does not price one for college. */
  function cfbFrame(g) {
    var id = g[1], kick = g[2], away = g[3], home = g[4];
    var aq = g[5], aqid = g[6], hq = g[7], hqid = g[8];
    var p = etParts(kick);
    var sec = function (kind, lab) {
      return '<div class="ptdx ptdx--v2" data-scale="2" data-kind="' + kind + '">' +
        '<div class="ptdhead"><span style="color:var(--amber)">' + last(aq) +
        '</span><span class="gmk">' + lab + '</span>' +
        '<span style="color:#5aa9ff">' + last(hq) + '</span></div>' +
        '<div class="ptdrow"><span class="trkbox ptdcount">0</span>' + ptdSide("l") +
        '<span class="ptdzero">0</span>' + ptdSide("r") +
        '<span class="trkbox ptdcount">0</span></div></div>';
    };
    return '<div class="gcard" data-espn="' + id + '" data-lg="college-football"' +
      ' data-sport="college-football" data-lhome="0"' +
      ' data-lqb="' + aq + '" data-lqbid="' + aqid + '"' +
      ' data-rqb="' + hq + '" data-rqbid="' + hqid + '"' +
      ' data-p4="' + g[9] + '" data-kick="' + kick + '">' +
      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml"' +
      '>' + GHOST + '</span>' + away + '</span><span class="gtime">' + p.time +
      '</span><span class="gteam">' + home + '<span class="gml">' + GHOST +
      '</span></span></div>' + sec("PTD", "PTD") + sec("ATD", "ATD") +
      '<button class="gmorebtn" type="button" aria-label="More">' +
      '<svg viewBox="0 0 24 24" width="18" height="18">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg></button>' +
      sheetFor(away + ' v ' + home) + '</div>';
  }

  function mmaFrame(e) {
    var p = etParts(e[2]);
    return '<div class="gcard mmacard" data-bout="' + e[1] + '" data-sport="mma"' +
      ' data-kick="' + e[2] + '">' +
      '<div class="ghead"><span class="mmaname">' + e[3] + '</span>' +
      '<span class="gtime">' + p.time + '</span></div>' +
      '<p class="wkempty">Fights are wired when DraftKings prices them.</p></div>';
  }

  function sheetFor(title) {
    return '<dialog class="sheet gsheet"><div class="sheet__head">' +
      '<button class="sheet__x" type="button" data-shut aria-label="Back">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<h2 class="sheet__title">' + title + '</h2>' +
      '<span aria-hidden="true"></span></div>' +
      '<div class="sheet__scroll"><div class="hits" hidden></div>' +
      '<p class="wkempty">No prices yet.</p></div></dialog>';
  }

  function ptdSide(which) {
    var edge = which === "l" ? "right" : "left";
    return '<div class="ptdside ptdside--' + which + '"><div class="ptdbar">' +
      '<div class="ptdfill" style="' + edge + ':0; width:0%"></div>' +
      '<i class="ntick ntick--n1" style="' + edge + ':50.0%"><b>1</b></i>' +
      '<i class="ntick ntick--n2" style="' + edge + ':100.0%"><b>2</b></i></div>' +
      '<div class="ptdmarks"><span class="ptdbtn ptdbtn--n1">' +
      '<span class="ptdline">1+</span>' + GHOST + '</span>' +
      '<span class="ptdbtn ptdbtn--n2"><span class="ptdline">2+</span>' +
      GHOST + '</span></div></div>';
  }

  var drawn = {1: true};""", "the drawn map")

# college and the fights join the week as it is drawn
once("""    if (open) { html += '</div></div>'; }
    box.innerHTML = html;
    wire(box);""",
     """    if (open) { html += '</div></div>'; }

    var col = CFB.filter(function (g) { return g[0] === w; });
    if (col.length) {
      col.sort(function (a, b) { return Date.parse(a[2]) - Date.parse(b[2]); });
      html += '<div class="lgmk"><img src="ico/cfb.svg" alt=""> College Football</div>';
      var cd = "";
      col.forEach(function (g) {
        var q = etParts(g[2]), key = q.day + " " + q.date;
        if (key !== cd) {
          if (cd) { html += '</div></div>'; }
          html += '<div class="dayhead">' + q.day + ' <span class="amber">' +
                  q.date + '</span></div><div class="board board--nfl">' +
                  '<div class="slot-h">' + q.day + ' <span class="swipe">swipe &rsaquo;</span>' +
                  '</div><div class="caro">';
          cd = key;
        }
        html += cfbFrame(g);
      });
      if (cd) { html += '</div></div>'; }
    }

    var fights = MMA.filter(function (e) { return e[0] === w; });
    if (fights.length) {
      fights.sort(function (a, b) { return Date.parse(a[2]) - Date.parse(b[2]); });
      html += '<div class="lgmk"><img src="ico/mma.svg" alt=""> MMA</div>';
      fights.forEach(function (e) {
        var q = etParts(e[2]);
        html += '<div class="dayhead">' + q.day + ' <span class="amber">' +
                q.date + '</span></div><div class="board board--nfl">' +
                '<div class="caro">' + mmaFrame(e) + '</div></div>';
      });
    }

    box.innerHTML = html;
    wire(box);
    filterSport();""", "the week drawing")

# ------------------------------------------------------------ the filter ----
once("""  bar.addEventListener("click", function (e) {
    var t = e.target.closest(".wktab");
    if (t) showweek(Number(t.dataset.wk));
  });""",
     """  bar.addEventListener("click", function (e) {
    var t = e.target.closest(".wktab");
    if (t) showweek(Number(t.dataset.wk));
  });

  /* ---- the sports ----
     A card says what it is: NFL and college carry data-lg, a fight carries
     data-bout or data-fight. Filtering hides cards and then any heading or
     row left standing over nothing. */
  function kindOf(card) {
    if (card.dataset.sport) return card.dataset.sport;
    if (card.dataset.fight) return "boxing";
    if (card.dataset.bout) return "mma";
    return card.dataset.lg || "";
  }
  function filterSport() {
    document.querySelectorAll(".gcard").forEach(function (card) {
      card.hidden = sport !== "all" && kindOf(card) !== sport;
    });
    document.querySelectorAll(".board .caro").forEach(function (row) {
      var any = row.querySelector(".gcard:not([hidden])");
      var board = row.parentElement;
      if (board && board.classList.contains("board")) board.hidden = !any;
    });
    document.querySelectorAll(".wkboard:not([hidden]) .dayhead, " +
                              ".wkboard:not([hidden]) .lgmk").forEach(function (h) {
      var n = h.nextElementSibling, live = false;
      while (n && !n.classList.contains("dayhead") && !n.classList.contains("lgmk")) {
        if (!n.hidden && n.querySelector && n.querySelector(".gcard:not([hidden])")) {
          live = true; break;
        }
        n = n.nextElementSibling;
      }
      h.hidden = !live;
    });
  }
  var sbar = document.getElementById("sportbar");
  SPORTS.forEach(function (sp) {
    var t = document.createElement("button");
    t.className = "sptab";
    t.type = "button";
    t.setAttribute("role", "tab");
    t.dataset.sp = sp.key;
    t.innerHTML = (sp.ico ? '<img src="' + sp.ico + '" alt="">' : "") + sp.label;
    t.setAttribute("aria-selected", sp.key === sport ? "true" : "false");
    sbar.appendChild(t);
  });
  sbar.addEventListener("click", function (e) {
    var t = e.target.closest(".sptab");
    if (!t) return;
    sport = t.dataset.sp;
    sbar.querySelectorAll(".sptab").forEach(function (x) {
      x.setAttribute("aria-selected", x.dataset.sp === sport ? "true" : "false");
    });
    filterSport();
  });""", "the week click")

once("""    draw(w);
  }""", """    draw(w);
    filterSport();
  }""", "the week shower")

assert s.count("data-oid") == before
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("college: 205 games over 3 weeks | mma: 15 events | page %.0f KB"
      % (len(s) / 1024.0))
