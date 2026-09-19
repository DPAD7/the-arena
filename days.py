"""Days across the top, the way theScore has them; weeks when you ask for them.

   The day is what you look at when you want to know what is on. The week is
   what you look at when you are planning, and only football has one. So the
   top rail is dates, and tapping NFL swaps it for the eighteen weeks --
   tapping anything else swaps it back.

   A day can straddle two week boards, so day mode shows every board and hides
   what does not belong to the date. One filter runs over sport and day
   together, and headings fold when nothing is left under them.
"""
import os

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------------ style ---
once("""  /* the sports, as pills under the weeks */""",
     """  /* the days, along the top */
  .daybar {
    grid-column: 1 / -1; display: flex; gap: 0; overflow-x: auto;
    scrollbar-width: none; padding: 0 14px 2px; margin: 0 -14px;
  }
  .daybar::-webkit-scrollbar { display: none; }
  .daybar[hidden], .weekbar[hidden] { display: none !important; }
  .dtab {
    flex: none; appearance: none; background: none; border: 0; cursor: pointer;
    padding: 7px 13px 9px; border-bottom: 3px solid transparent;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--muted); white-space: nowrap; line-height: 1.15; text-align: center;
  }
  .dtab b { display: block; font-size: 14px; font-weight: 700; }
  .dtab i { display: block; font-size: 11px; font-style: normal; opacity: 0.75; }
  .dtab[aria-selected="true"] { color: var(--ink); border-bottom-color: var(--amber); }
  .dtab:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }
  /* the sports, as pills under the weeks */""", "the sport styling")

# ----------------------------------------------------------------- header ---
once('    <div class="weekbar" id="weekbar" role="tablist" aria-label="Week"></div>\n'
     '    <div class="sportbar" id="sportbar" role="tablist" aria-label="Sport"></div>',
     '    <div class="daybar" id="daybar" role="tablist" aria-label="Day"></div>\n'
     '    <div class="weekbar" id="weekbar" role="tablist" aria-label="Week" hidden></div>\n'
     '    <div class="sportbar" id="sportbar" role="tablist" aria-label="Sport"></div>',
     "the week bar")

# ------------------------------------------------------------ the filter ----
once("""  function filterSport() {
    document.querySelectorAll(".gcard").forEach(function (card) {
      card.hidden = sport !== "all" && kindOf(card) !== sport;
    });""",
     """  function dayKeyOf(iso) {
    var p = etParts(iso);
    return p.day + " " + p.date;
  }
  function filterSport() {
    document.querySelectorAll(".gcard").forEach(function (card) {
      var out = sport !== "all" && kindOf(card) !== sport;
      if (!out && mode === "day" && card.dataset.kick) {
        out = dayKeyOf(card.dataset.kick) !== day;
      }
      card.hidden = out;
    });""", "the sport filter")

# every board is on show in day mode, so a date that straddles two weeks works
once("""  function showweek(w, scroll) {
    week = w;
    for (var i = 1; i <= WEEKS; i++) {
      document.getElementById("wk-" + i).hidden = i !== w;
    }""",
     """  function showweek(w, scroll) {
    week = w;
    for (var i = 1; i <= WEEKS; i++) {
      document.getElementById("wk-" + i).hidden = mode === "day" ? false : i !== w;
    }""", "the week shower")

# ------------------------------------------------------------- the days -----
once("""  var sbar = document.getElementById("sportbar");""",
     """  /* ---- the days ----
     Every date anything is on, from three days back to three weeks out. The
     week a date belongs to has to be drawn before its cards can be shown. */
  var mode = "day", day = "";
  function weekOfDate(iso) {
    var t = Date.parse(iso), pick = 1;
    for (var w = 1; w <= WEEKS; w++) {
      var of = SCHED.filter(function (g) { return g[0] === w; });
      if (!of.length) continue;
      var hi = Math.max.apply(null, of.map(function (g) { return Date.parse(g[2]); }));
      if (t <= hi + 6 * 3600000) return w;
      pick = Math.min(WEEKS, w + 1);
    }
    return pick;
  }
  var DAYS = (function () {
    var seen = {}, all = [];
    function add(iso) {
      var k = dayKeyOf(iso);
      if (!seen[k]) { seen[k] = iso; all.push([k, iso]); }
    }
    SCHED.forEach(function (g) { add(g[2]); });
    CFB.forEach(function (g) { add(g[2]); });
    FIGHTCARDS.forEach(function (e) { add(e[2]); });
    document.querySelectorAll(".gcard[data-kick]").forEach(function (c) {
      add(c.dataset.kick);
    });
    var now = Date.now();
    all = all.filter(function (d) {
      var t = Date.parse(d[1]);
      return t > now - 4 * 86400000 && t < now + 22 * 86400000;
    });
    all.sort(function (a, b) { return Date.parse(a[1]) - Date.parse(b[1]); });
    return all;
  })();

  var dbar = document.getElementById("daybar");
  var today = (function () {
    var p = etParts(new Date().toISOString());
    return p.day + " " + p.date;
  })();
  DAYS.forEach(function (d) {
    var t = document.createElement("button");
    t.className = "dtab";
    t.type = "button";
    t.setAttribute("role", "tab");
    t.dataset.day = d[0];
    t.dataset.iso = d[1];
    var bits = d[0].split(" ");
    t.innerHTML = "<b>" + (d[0] === today ? "Today" : bits[0]) + "</b><i>" +
                  bits[1] + "</i>";
    dbar.appendChild(t);
  });
  function showDay(k, scroll) {
    mode = "day";
    day = k;
    document.getElementById("weekbar").hidden = true;
    dbar.hidden = false;
    var iso = "";
    dbar.querySelectorAll(".dtab").forEach(function (t) {
      var on = t.dataset.day === k;
      t.setAttribute("aria-selected", on ? "true" : "false");
      if (on) {
        iso = t.dataset.iso;
        if (scroll !== false) t.scrollIntoView({block: "nearest", inline: "center"});
      }
    });
    if (iso) {
      var w = weekOfDate(iso);
      draw(w);
      if (w > 1) draw(w - 1);
      if (w < WEEKS) draw(w + 1);
      for (var i = 1; i <= WEEKS; i++) document.getElementById("wk-" + i).hidden = false;
    }
    filterSport();
  }
  dbar.addEventListener("click", function (e) {
    var t = e.target.closest(".dtab");
    if (t) showDay(t.dataset.day);
  });

  var sbar = document.getElementById("sportbar");""", "the sport bar")

# tapping NFL swaps the rail for weeks; anything else swaps it back
once("""    sport = t.dataset.sp;
    sbar.querySelectorAll(".sptab").forEach(function (x) {
      x.setAttribute("aria-selected", x.dataset.sp === sport ? "true" : "false");
    });
    filterSport();
  });""",
     """    sport = t.dataset.sp;
    sbar.querySelectorAll(".sptab").forEach(function (x) {
      x.setAttribute("aria-selected", x.dataset.sp === sport ? "true" : "false");
    });
    if (sport === "nfl") {
      mode = "week";
      dbar.hidden = true;
      document.getElementById("weekbar").hidden = false;
      showweek(week);
    } else if (mode === "week") {
      showDay(day || (DAYS[0] && DAYS[0][0]) || today);
    } else {
      filterSport();
    }
  });""", "the sport click")

# open on today rather than on a week
once("""  showday();""", """  showweek(week, false);
  showDay(DAYS.some(function (d) { return d[0] === today; }) ? today
          : (DAYS[0] && DAYS[0][0]) || today);""", "the opening call")

assert s.count("data-oid") == before
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("day rail in; NFL swaps it for weeks")
