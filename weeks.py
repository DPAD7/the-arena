"""The board stops being four days and becomes a season.

   Eighteen weeks across the top, the way the league counts them, and inside
   a week the days it holds with their own headings. Week one keeps the cards
   that were built by hand, prices and all. Every other week is drawn from the
   schedule at load: the same head, the same head-to-head, the same passing
   touchdowns, with an empty slot where each price will go. Nothing has to be
   rebuilt when DraftKings starts pricing week three -- the frame is already
   standing and refresh.py fills it.
"""
import json
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")
SCHED = open("/tmp/sched.js").read()

# ------------------------------------------------------------------ style ---
once = lambda old, new, what: (
    _once(old, new, what))


def _once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


_once("""  .daynav {""",
      """  /* the weeks, along the top, the way the league counts them */
  .weekbar {
    grid-column: 1 / -1; display: flex; gap: 6px; overflow-x: auto;
    scrollbar-width: none; -webkit-overflow-scrolling: touch;
    padding: 0 14px 2px; margin: 0 -14px;
  }
  .weekbar::-webkit-scrollbar { display: none; }
  .wktab {
    flex: none; appearance: none; background: none; border: 0;
    padding: 7px 2px 9px; cursor: pointer;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 15px; letter-spacing: 0.1em;
    text-transform: uppercase; color: var(--muted);
    border-bottom: 3px solid transparent; white-space: nowrap;
  }
  .wktab + .wktab { margin-left: 12px; }
  .wktab[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--amber); }
  .wktab:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }
  .dayhead {
    margin: 18px 0 2px; font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 19px; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--ink);
  }
  .dayhead .amber { color: var(--amber); }
  .wkboard[hidden] { display: none !important; }
  .wkempty {
    padding: 34px 6px; text-align: center; color: var(--muted); font-size: 13px;
  }
  .daynav {""", "the day-nav styling")

# ----------------------------------------------------------------- header ---
_once("""    <button class="daynav" id="prevday" type="button" aria-label="Previous day">
      <svg viewBox="0 0 24 24" width="26" height="26"><polygon points="16,3 6,12 16,21" fill="var(--ink)"/></svg>
    </button>
    <h1 id="daytitle">SAT <span class="amber">9/12</span></h1>
    <button class="daynav" id="nextday" type="button" aria-label="Next day">
      <svg viewBox="0 0 24 24" width="26" height="26"><polygon points="8,3 18,12 8,21" fill="var(--amber)"/></svg>
    </button>
    <div class="clock" id="clock"></div>""",
      """    <div class="weekbar" id="weekbar" role="tablist" aria-label="Week"></div>
    <div class="clock" id="clock"></div>""", "the day header")

# ------------------------------------------------------------ the boards ----
# week one keeps every card already built; the rest are drawn at load
_once('    <div class="board board--nfl" id="board-sat">',
      '  <div class="wkboard" id="wk-1">\n'
      '    <div class="dayhead">Fri <span class="amber">9/11</span></div>\n'
      '    <div class="board board--nfl" id="board-fri"></div>\n'
      '    <div class="dayhead">Sat <span class="amber">9/12</span></div>\n'
      '    <div class="board board--nfl" id="board-sat">', "the Saturday board")

# the three that were hidden come out of hiding, each under its own heading
for day, label in (("fri", "Fri <span class=\"amber\">9/11</span>"),
                   ("sun", "Sun <span class=\"amber\">9/13</span>"),
                   ("mon", "Mon <span class=\"amber\">9/14</span>")):
    old = '  <div class="board board--nfl" id="board-%s" hidden>' % day
    if day == "fri":
        # already announced above; move its contents up beside the heading
        new = '  <div class="board board--nfl" id="board-fri-cards">'
    else:
        new = ('    <div class="dayhead">%s</div>\n'
               '    <div class="board board--nfl" id="board-%s">' % (label, day))
    _once(old, new, "the %s board" % day)

# close week one and stand the other seventeen up empty
_once("""      </div>
    </div>
  </div>
</div>
<dialog class="sheet" id="slipsheet\"""",
       """      </div>
    </div>
  </div>
  </div>
""" + "".join('  <div class="wkboard" id="wk-%d" hidden></div>\n' % w
              for w in range(2, 19)) + """</div>
<dialog class="sheet" id="slipsheet\"""", "the end of the boards")

# ------------------------------------------------------------------- JS -----
_once("""  var DAYS = ["fri", "sat", "sun", "mon"];
  var TITLES = {fri: "FRI", sat: "SAT", sun: "SUN", mon: "MON"};
  var DATES = {fri: "9/11", sat: "9/12", sun: "9/13", mon: "9/14"};
  // open on the day it actually is: Fri Sep 11 through Mon Sep 14, 2026
  var day = (function () {
    var now = new Date();
    var d = Math.floor((now - new Date(2026, 8, 11)) / 86400000);
    return Math.max(0, Math.min(DAYS.length - 1, d));
  })();
  function showday() {
    DAYS.forEach(function (d, i) {
      document.getElementById("board-" + d).hidden = i !== day;
    });
    document.getElementById("daytitle").innerHTML =
      TITLES[DAYS[day]] + ' <span class="amber">' + DATES[DAYS[day]] + '</span>';
    document.getElementById("prevday").disabled = day === 0;
    document.getElementById("nextday").disabled = day === DAYS.length - 1;
  }
  document.getElementById("prevday").addEventListener("click", function () {
    if (day > 0) { day--; showday(); }
  });
  document.getElementById("nextday").addEventListener("click", function () {
    if (day < DAYS.length - 1) { day++; showday(); }
  });""",
       """  /* ---- the season ----
     Every game the league plays, as [week, id, kickoff, away, home, away QB,
     his id, home QB, his id]. Week one is already on the page as markup with
     prices in it; every other week is drawn from here, once, the first time
     it is looked at. */
  var SCHED = """ + SCHED + """;
  var WEEKS = 18;
  var ET = {timeZone: "America/New_York"};

  function etParts(iso) {
    var d = new Date(iso);
    var f = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York", weekday: "short",
      month: "numeric", day: "numeric"
    }).formatToParts(d);
    var g = {};
    f.forEach(function (p) { g[p.type] = p.value; });
    var t = new Intl.DateTimeFormat("en-US", {
      timeZone: "America/New_York", hour: "numeric", minute: "2-digit"
    }).format(d);
    return {day: g.weekday, date: g.month + "/" + g.day, time: t};
  }

  var GHOST = '<span class="ghost" aria-hidden="true"></span>';
  function last(name) {
    var bits = String(name || "").split(" ");
    return bits.length > 1 ? bits.slice(1).join(" ") : bits[0];
  }

  function frame(g) {
    var wk = g[0], id = g[1], kick = g[2], away = g[3], home = g[4];
    var aq = g[5], aqid = g[6], hq = g[7], hqid = g[8];
    var p = etParts(kick);
    var side = function (which) {
      return '<div class="ptdside ptdside--' + which + '"><div class="ptdbar">' +
        '<div class="ptdfill" style="' + (which === "l" ? "right" : "left") +
        ':0; width:0%"></div><i class="ntick ntick--n1" style="' +
        (which === "l" ? "right" : "left") + ':50.0%"><b>1</b></i>' +
        '<i class="ntick ntick--n2" style="' + (which === "l" ? "right" : "left") +
        ':100.0%"><b>2</b></i></div><div class="ptdmarks">' +
        '<span class="ptdbtn ptdbtn--n1"><span class="ptdline">1+</span>' + GHOST + '</span>' +
        '<span class="ptdbtn ptdbtn--n2"><span class="ptdline">2+</span>' + GHOST + '</span>' +
        '</div></div>';
    };
    return '<div class="gcard" data-espn="' + id + '" data-lg="nfl" data-lhome="0"' +
      ' data-lqb="' + aq + '" data-lqbid="' + aqid + '"' +
      ' data-rqb="' + hq + '" data-rqbid="' + hqid + '"' +
      ' data-kick="' + kick + '">' +
      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' + GHOST +
      '</span>' + away + '</span><span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + home + '<span class="gml">' + GHOST + '</span></span></div>' +
      '<div class="h2hx"><div class="ptdhead"><span style="color:var(--amber)">' +
      last(aq) + '</span><span class="gmk">H2H YDS</span>' +
      '<span style="color:#5aa9ff">' + last(hq) + '</span></div>' +
      '<div class="h2hrow"><span class="h2hend"><span class="trkbox">0</span>' +
      '<span class="h2hodds">' + GHOST + '</span></span><div class="h2hbar">' +
      '<i class="h2hzero"></i><div class="h2hfill" style="left:50%; width:0"></div>' +
      '<i class="h2htick" style="left:50%"><b>0</b></i></div>' +
      '<span class="h2hend"><span class="trkbox">0</span>' +
      '<span class="h2hodds">' + GHOST + '</span></span></div></div>' +
      '<div class="ptdx ptdx--v2" data-scale="2">' +
      '<div class="ptdhead ptdhead--bare"><span class="gmk">PTD</span></div>' +
      '<div class="ptdrow"><span class="trkbox ptdcount">0</span>' + side("l") +
      '<span class="ptdzero">0</span>' + side("r") +
      '<span class="trkbox ptdcount">0</span></div></div>' +
      '<button class="gmorebtn" type="button" aria-label="More">' +
      '<svg viewBox="0 0 24 24" width="18" height="18">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg></button>' +
      '<dialog class="sheet gsheet"><div class="sheet__head">' +
      '<button class="sheet__x" type="button" data-shut aria-label="Back">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<h2 class="sheet__title">' + away + ' v ' + home + '</h2>' +
      '<span aria-hidden="true"></span></div>' +
      '<div class="sheet__scroll"><div class="hits" hidden></div>' +
      '<p class="wkempty">No prices yet.</p></div></dialog></div>';
  }

  var drawn = {1: true};
  function draw(w) {
    if (drawn[w]) return;
    drawn[w] = true;
    var box = document.getElementById("wk-" + w);
    var games = SCHED.filter(function (g) { return g[0] === w; });
    games.sort(function (a, b) { return Date.parse(a[2]) - Date.parse(b[2]); });
    var html = "", lastDay = "", lastTime = "", open = false;
    games.forEach(function (g) {
      var p = etParts(g[2]);
      var dayKey = p.day + " " + p.date;
      if (dayKey !== lastDay) {
        if (open) { html += '</div></div>'; open = false; }
        html += '<div class="dayhead">' + p.day + ' <span class="amber">' +
                p.date + '</span></div>';
        lastDay = dayKey; lastTime = "";
      }
      if (p.time !== lastTime) {
        if (open) { html += '</div></div>'; }
        html += '<div class="board board--nfl"><div class="slot-h">' + p.time +
                '</div><div class="caro">';
        lastTime = p.time; open = true;
      }
      html += frame(g);
    });
    if (open) { html += '</div></div>'; }
    box.innerHTML = html;
    wire(box);
  }

  /* Anything drawn late needs the same handlers the markup got at load. */
  function wire(box) {
    box.querySelectorAll(".gmorebtn").forEach(function (b) {
      b.addEventListener("click", function () {
        var sheet = b.nextElementSibling;
        if (sheet && sheet.tagName === "DIALOG") openSheet(sheet);
      });
    });
    var now = Date.now();
    box.querySelectorAll(".gcard[data-kick]").forEach(function (card) {
      if (now >= Date.parse(card.dataset.kick)) card.classList.add("locked");
    });
  }

  /* ---- the week carousel ---- */
  var week = (function () {
    var now = Date.now(), pick = 1;
    for (var w = 1; w <= WEEKS; w++) {
      var of = SCHED.filter(function (g) { return g[0] === w; });
      if (!of.length) continue;
      var last = Math.max.apply(null, of.map(function (g) { return Date.parse(g[2]); }));
      if (now <= last + 4 * 3600000) { pick = w; break; }
      pick = Math.min(WEEKS, w + 1);
    }
    return pick;
  })();

  var bar = document.getElementById("weekbar");
  for (var w = 1; w <= WEEKS; w++) {
    var t = document.createElement("button");
    t.className = "wktab";
    t.type = "button";
    t.setAttribute("role", "tab");
    t.dataset.wk = w;
    t.textContent = "WEEK " + w;
    bar.appendChild(t);
  }
  function showweek(w, scroll) {
    week = w;
    for (var i = 1; i <= WEEKS; i++) {
      document.getElementById("wk-" + i).hidden = i !== w;
    }
    bar.querySelectorAll(".wktab").forEach(function (t) {
      var on = Number(t.dataset.wk) === w;
      t.setAttribute("aria-selected", on ? "true" : "false");
      if (on && scroll !== false) {
        t.scrollIntoView({block: "nearest", inline: "center"});
      }
    });
    draw(w);
  }
  bar.addEventListener("click", function (e) {
    var t = e.target.closest(".wktab");
    if (t) showweek(Number(t.dataset.wk));
  });
  function showday() { showweek(week); }""", "the day navigation")

assert s.count("data-oid") == before, "prices moved"
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("18 weeks wired | 272 games in the schedule | prices still %d" % before)
print("page is now %.0f KB" % (len(s) / 1024.0))
