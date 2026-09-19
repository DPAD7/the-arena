"""Three rails, in the order he wants them: the day, then the sport, then the
   week where a week exists.

   The week is a range and the day is a place inside it, so they stack rather
   than replace each other. Pick NFL and the week rail appears under the pills;
   the day rail narrows to the days that week actually holds. Pick All or UFC
   and the week rail is simply not there, because neither has weeks.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:40], s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------ the rails, in order ------
once('''    <div class="daybar" id="daybar" role="tablist" aria-label="Day"></div>
    <div class="weekbar" id="weekbar" role="tablist" aria-label="Week" hidden></div>
    <div class="sportbar" id="sportbar" role="tablist" aria-label="Sport"></div>''',
     '''    <div class="daybar" id="daybar" role="tablist" aria-label="Day"></div>
    <div class="sportbar" id="sportbar" role="tablist" aria-label="Sport"></div>
    <div class="weekbar" id="weekbar" role="tablist" aria-label="Week" hidden></div>''',
     "the three rails")

once("""  .wktab + .wktab { margin-left: 12px; }""",
     """  .wktab + .wktab { margin-left: 12px; }
  .weekbar { padding-top: 2px; }""")

# ------------------------------------------------------------ the days -----
# the day rail is rebuilt whenever the range it covers changes
once('''  DAYS.forEach(function (d) {
    var t = document.createElement("button");
    t.className = "dtab";
    t.type = "button";
    t.setAttribute("role", "tab");
    t.dataset.day = d[0];
    var bits = d[0].split(" ");
    t.innerHTML = "<b>" + (d[0] === today ? "Today" : bits[0]) + "</b><i>" +
                  bits[1] + "</i>";
    dbar.appendChild(t);
  });

  function markDay(scroll) {
    dbar.querySelectorAll(".dtab").forEach(function (t) {
      var on = t.dataset.day === day;
      t.setAttribute("aria-selected", on ? "true" : "false");
      if (on && scroll !== false) {
        t.scrollIntoView({block: "nearest", inline: "center"});
      }
    });
  }''',
     '''  /* Which days the rail offers depends on what is selected: the whole run
     when there is no week, and only that week's days when there is one. */
  function daysNow() {
    if (sport === "nfl") return daysOf(SCHED, week);
    if (sport === "college-football") return daysOf(CFB, cfbWeek);
    return DAYS;
  }
  function daysOf(list, w) {
    var seen = {}, out = [];
    list.forEach(function (g) {
      if (g[0] !== w) return;
      var k = dayKeyOf(g[2]);
      if (!seen[k]) { seen[k] = 1; out.push([k, g[2]]); }
    });
    out.sort(function (a, b) { return Date.parse(a[1]) - Date.parse(b[1]); });
    return out;
  }
  function buildDays() {
    var list = daysNow();
    dbar.innerHTML = "";
    list.forEach(function (d) {
      var t = document.createElement("button");
      t.className = "dtab";
      t.type = "button";
      t.setAttribute("role", "tab");
      t.dataset.day = d[0];
      var bits = d[0].split(" ");
      t.innerHTML = "<b>" + (d[0] === today ? "Today" : bits[0]) + "</b><i>" +
                    bits[1] + "</i>";
      dbar.appendChild(t);
    });
    if (!list.some(function (d) { return d[0] === day; })) {
      var pick = list.filter(function (d) { return d[0] === today; })[0] || list[0];
      day = pick ? pick[0] : day;
    }
    markDay();
  }

  function markDay(scroll) {
    dbar.querySelectorAll(".dtab").forEach(function (t) {
      var on = t.dataset.day === day;
      t.setAttribute("aria-selected", on ? "true" : "false");
      if (on && scroll !== false) {
        t.scrollIntoView({block: "nearest", inline: "center"});
      }
    });
  }''', "the day rail")

# a day is always a day now; the week only narrows which days exist
once('''  dbar.addEventListener("click", function (e) {
    var t = e.target.closest(".dtab");
    if (!t) return;
    day = t.dataset.day;
    mode = "day";
    markDay();
    render();
  });''',
     '''  dbar.addEventListener("click", function (e) {
    var t = e.target.closest(".dtab");
    if (!t) return;
    day = t.dataset.day;
    markDay();
    render();
  });''', "the day click")

once('''    var w = Number(t.dataset.wk);
    if (sport === "nfl") { week = w; } else { cfbWeek = w; }
    wbar.querySelectorAll(".wktab").forEach(function (x) {
      x.setAttribute("aria-selected", Number(x.dataset.wk) === w ? "true" : "false");
    });
    render();''',
     '''    var w = Number(t.dataset.wk);
    if (sport === "nfl") { week = w; } else { cfbWeek = w; }
    wbar.querySelectorAll(".wktab").forEach(function (x) {
      x.setAttribute("aria-selected", Number(x.dataset.wk) === w ? "true" : "false");
    });
    day = "";            /* the week decides which days exist */
    buildDays();
    render();''', "the week click")

# ----------------------------------------------------- what render means ----
once('''  function render() {
    var items = [];
    if (mode === "week" && sport === "nfl") {
      items = nflItems(SCHED.filter(function (g) { return g[0] === week; }));
    } else if (mode === "week" && sport === "college-football") {
      items = cfbItems(CFB.filter(function (g) { return g[0] === cfbWeek; }));
    } else {
      var on = function (iso) { return dayKeyOf(iso) === day; };
      if (sport === "all" || sport === "nfl") {
        items = items.concat(nflItems(SCHED.filter(function (g) { return on(g[2]); })));
      }
      if (sport === "all" || sport === "college-football") {
        items = items.concat(cfbItems(CFB.filter(function (g) { return on(g[2]); })));
      }
      if (sport === "all" || sport === "mma") {
        items = items.concat(fightItems(FIGHTS.filter(function (f) { return on(f[2]); })));
      }
    }
    build(items, sport === "all");
  }''',
     '''  /* The day is always what is shown. A week, where one exists, only decides
     which days the rail offers. */
  function render() {
    var items = [], on = function (iso) { return dayKeyOf(iso) === day; };
    if (sport === "all" || sport === "nfl") {
      items = items.concat(nflItems(SCHED.filter(function (g) {
        return on(g[2]) && (sport !== "nfl" || g[0] === week);
      })));
    }
    if (sport === "all" || sport === "college-football") {
      items = items.concat(cfbItems(CFB.filter(function (g) {
        return on(g[2]) && (sport !== "college-football" || g[0] === cfbWeek);
      })));
    }
    if (sport === "all" || sport === "mma") {
      items = items.concat(fightItems(FIGHTS.filter(function (f) { return on(f[2]); })));
    }
    build(items, sport === "all");
  }''', "the renderer")

# ------------------------------------------------------- the sport click ----
once('''    var weekly = sport === "nfl" || sport === "college-football";
    mode = weekly ? "week" : "day";
    dbar.hidden = weekly;
    wbar.hidden = !weekly;
    if (weekly) {
      weekTabs(sport === "nfl" ? WEEKS : CFB_WEEKS,
               sport === "nfl" ? week : cfbWeek);
    } else {
      markDay();
    }
    render();''',
     '''    var weekly = sport === "nfl" || sport === "college-football";
    wbar.hidden = !weekly;
    if (weekly) {
      /* open on the week holding the day already chosen, if it holds one */
      var list = sport === "nfl" ? SCHED : CFB;
      var hit = list.filter(function (g) { return dayKeyOf(g[2]) === day; })[0];
      if (hit) { if (sport === "nfl") { week = hit[0]; } else { cfbWeek = hit[0]; } }
      weekTabs(sport === "nfl" ? WEEKS : CFB_WEEKS,
               sport === "nfl" ? week : cfbWeek);
    }
    buildDays();
    render();''', "the sport click")

# the opening call builds the rail rather than assuming it is there
once('''  day = DAYS.some(function (d) { return d[0] === today; })
        ? today : ((DAYS[0] && DAYS[0][0]) || today);
  markDay();
  render();''',
     '''  day = DAYS.some(function (d) { return d[0] === today; })
        ? today : ((DAYS[0] && DAYS[0][0]) || today);
  buildDays();
  render();''', "the opening call")

# mode is gone; the day is always the view
s = s.replace('  var mode = "day", day = "", week = 1, cfbWeek = 1, sport = "all";',
              '  var day = "", week = 1, cfbWeek = 1, sport = "all";', 1)
assert "mode ===" not in s and "mode =" not in s, "a mode reference survived"

assert s.count("data-oid") == before
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("day, sport, week -- in that order")
