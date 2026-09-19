"""The rendering engine: one board, three views, four rails' worth of state.

   Everything downstream of this is the same as it was -- the cards are the
   cards, the slip is the slip. What changed is that a card is now fetched
   from the pool or drawn on the spot, and the board is rebuilt whenever the
   day, the week or the sport changes.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")

start = s.index("  var drawn = {1: true};")
end = s.index("  function showday() { showweek(week); }")
NEW = r'''  /* ---- the pool ----
     Every card built by hand lives here until a view asks for it. Moving the
     node keeps its prices, its handlers and whatever the settler has already
     written on it; drawing a fresh one would throw all three away. */
  var POOL = document.getElementById("pool");
  var BOARD = document.getElementById("board");
  var STATIC = {};
  POOL.querySelectorAll(".gcard").forEach(function (c) {
    var k = c.dataset.espn || c.dataset.bout || c.dataset.fight;
    if (k) { STATIC[k] = c; c.dataset.pooled = "1"; }
  });

  function clearBoard() {
    BOARD.querySelectorAll(".gcard").forEach(function (c) {
      if (c.dataset.pooled) POOL.appendChild(c);
    });
    BOARD.innerHTML = "";
  }

  function lockOne(card) {
    if (!card.dataset.kick || Date.now() < Date.parse(card.dataset.kick)) return;
    card.classList.add("locked");
    card.querySelectorAll("button.price").forEach(function (b) {
      b.disabled = true;
      b.classList.remove("on");
    });
  }

  function nodeFor(id, html) {
    if (STATIC[id]) return STATIC[id];
    var box = document.createElement("div");
    box.innerHTML = html;
    var card = box.firstElementChild;
    card.querySelectorAll(".gmorebtn").forEach(function (b) {
      b.addEventListener("click", function () {
        var sheet = b.nextElementSibling;
        if (sheet && sheet.tagName === "DIALOG") openSheet(sheet);
      });
    });
    return card;
  }

  /* ---- building a view ----
     An item is [league, id, kickoff, how to draw it if we have no card].
     They are grouped league, then day, then kickoff. */
  function head(cls, html) {
    var h = document.createElement("div");
    h.className = cls;
    h.innerHTML = html;
    return h;
  }

  var LEAGUE_MARK = {
    "nfl": '<img src="ico/nfl.svg" alt=""> NFL',
    "college-football": '<img src="ico/cfb.svg" alt=""> CFB',
    "mma": '<img src="ico/mma.svg" alt=""> MMA'
  };

  function build(items, showLeague) {
    clearBoard();
    items.sort(function (a, b) {
      if (showLeague && a[0] !== b[0]) {
        var o = ["nfl", "college-football", "mma"];
        return o.indexOf(a[0]) - o.indexOf(b[0]);
      }
      return Date.parse(a[2]) - Date.parse(b[2]);
    });
    var lg = "", dy = "", tm = "", row = null;
    items.forEach(function (it) {
      var p = etParts(it[2]), key = p.day + " " + p.date;
      if (showLeague && it[0] !== lg) {
        lg = it[0]; dy = ""; tm = ""; row = null;
        if (LEAGUE_MARK[lg]) BOARD.appendChild(head("lgmk", LEAGUE_MARK[lg]));
      }
      if (key !== dy) {
        dy = key; tm = ""; row = null;
        BOARD.appendChild(head("dayhead",
          p.day + ' <span class="amber">' + p.date + "</span>"));
      }
      if (p.time !== tm) {
        tm = p.time;
        var n = items.filter(function (x) {
          var q = etParts(x[2]);
          return x[0] === it[0] && q.day + " " + q.date === key && q.time === p.time;
        }).length;
        var board = document.createElement("div");
        board.className = "board board--nfl";
        board.appendChild(head("slot-h",
          p.time + (n > 1 ? ' <span class="swipe">swipe &rsaquo;</span>' : "")));
        row = document.createElement("div");
        row.className = "caro";
        board.appendChild(row);
        BOARD.appendChild(board);
      }
      var card = nodeFor(it[1], it[3]);
      card.hidden = false;
      lockOne(card);
      row.appendChild(card);
    });
    if (!items.length) {
      BOARD.appendChild(head("wkempty", "Nothing on the board."));
    }
    refreshVisible();
  }

  function nflItems(list) {
    return list.map(function (g) { return ["nfl", g[1], g[2], frame(g)]; });
  }
  function cfbItems(list) {
    return list.map(function (g) {
      return ["college-football", g[1], g[2], cfbFrame(g)];
    });
  }
  function fightItems(list) {
    return list.map(function (f) {
      return ["mma", f[1], f[2], fightFrame(f)];
    });
  }

  /* ---- the three views ---- */
  var mode = "day", day = "", week = 1, cfbWeek = 1, sport = "all";

  function render() {
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
  }

  function dayKeyOf(iso) {
    var p = etParts(iso);
    return p.day + " " + p.date;
  }

  /* ---- the day rail ---- */
  var DAYS = (function () {
    var seen = {}, all = [], now = Date.now();
    function add(iso) {
      var k = dayKeyOf(iso);
      if (seen[k]) return;
      var t = Date.parse(iso);
      if (t < now - 4 * 86400000 || t > now + 22 * 86400000) return;
      seen[k] = 1;
      all.push([k, iso]);
    }
    SCHED.forEach(function (g) { add(g[2]); });
    CFB.forEach(function (g) { add(g[2]); });
    FIGHTS.forEach(function (f) { add(f[2]); });
    all.sort(function (a, b) { return Date.parse(a[1]) - Date.parse(b[1]); });
    return all;
  })();

  var dbar = document.getElementById("daybar");
  var wbar = document.getElementById("weekbar");
  var today = dayKeyOf(new Date().toISOString());

  DAYS.forEach(function (d) {
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
  }
  dbar.addEventListener("click", function (e) {
    var t = e.target.closest(".dtab");
    if (!t) return;
    day = t.dataset.day;
    mode = "day";
    markDay();
    render();
  });

  /* ---- the week rail, whichever league is asking ---- */
  function weekTabs(n, current) {
    wbar.innerHTML = "";
    for (var w = 1; w <= n; w++) {
      var t = document.createElement("button");
      t.className = "wktab";
      t.type = "button";
      t.setAttribute("role", "tab");
      t.dataset.wk = w;
      t.textContent = "WEEK " + w;
      t.setAttribute("aria-selected", w === current ? "true" : "false");
      wbar.appendChild(t);
    }
    var on = wbar.querySelector('[aria-selected="true"]');
    if (on) on.scrollIntoView({block: "nearest", inline: "center"});
  }
  wbar.addEventListener("click", function (e) {
    var t = e.target.closest(".wktab");
    if (!t) return;
    var w = Number(t.dataset.wk);
    if (sport === "nfl") { week = w; } else { cfbWeek = w; }
    wbar.querySelectorAll(".wktab").forEach(function (x) {
      x.setAttribute("aria-selected", Number(x.dataset.wk) === w ? "true" : "false");
    });
    render();
  });

  function weekOf(list, n) {
    var now = Date.now(), pick = 1;
    for (var w = 1; w <= n; w++) {
      var of = list.filter(function (g) { return g[0] === w; });
      if (!of.length) continue;
      var hi = Math.max.apply(null, of.map(function (g) { return Date.parse(g[2]); }));
      if (now <= hi + 6 * 3600000) return w;
      pick = Math.min(n, w + 1);
    }
    return pick;
  }
  week = weekOf(SCHED, WEEKS);
  cfbWeek = weekOf(CFB, CFB_WEEKS);

  /* ---- the sport pills ---- */
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
    var weekly = sport === "nfl" || sport === "college-football";
    mode = weekly ? "week" : "day";
    dbar.hidden = weekly;
    wbar.hidden = !weekly;
    if (weekly) {
      weekTabs(sport === "nfl" ? WEEKS : CFB_WEEKS,
               sport === "nfl" ? week : cfbWeek);
    } else {
      markDay();
    }
    render();
  });

'''
s = s[:start] + NEW + s[end:]
s = s.replace("  function showday() { showweek(week); }\n", "")
s = s.replace("""  showweek(week, false);
  showDay(DAYS.some(function (d) { return d[0] === today; }) ? today
          : (DAYS[0] && DAYS[0][0]) || today);""",
"""  day = DAYS.some(function (d) { return d[0] === today; })
        ? today : ((DAYS[0] && DAYS[0][0]) || today);
  markDay();
  render();""", 1)

# the fight frame replaces the event placeholder
s = s.replace("""  function mmaFrame(e) {
    var p = etParts(e[2]);
    return '<div class="gcard mmacard" data-bout="' + e[1] + '" data-sport="mma"' +
      ' data-kick="' + e[2] + '">' +
      '<div class="ghead"><span class="mmaname">' + e[3] + '</span>' +
      '<span class="gtime">' + p.time + '</span></div>' +
      '<p class="wkempty">Fights are wired when DraftKings prices them.</p></div>';
  }""",
"""  /* One fight, as a card: the two men with a slot for each price. */
  function fightFrame(f) {
    var p = etParts(f[2]);
    return '<div class="gcard" data-bout="' + f[1] + '" data-sport="mma"' +
      ' data-lf="' + f[3] + '" data-rf="' + f[5] + '"' +
      ' data-kick="' + f[2] + '">' +
      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      GHOST + '</span>' + lastName(f[3]) + '</span>' +
      '<span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + lastName(f[5]) + '<span class="gml">' + GHOST +
      '</span></span></div>' +
      (f[7] ? '<div class="ptdhead ptdhead--bare"><span class="gmk">' + f[7] +
              '</span></div>' : "") +
      '<button class="gmorebtn" type="button" aria-label="More">' +
      '<svg viewBox="0 0 24 24" width="18" height="18">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg></button>' +
      sheetFor(lastName(f[3]) + ' v ' + lastName(f[5])) + '</div>';
  }
  function lastName(n) {
    var bits = String(n || "").trim().split(" ");
    return (bits.length > 1 ? bits.slice(1).join(" ") : bits[0]).toUpperCase();
  }""", 1)

# the old loader that locked cards walked the whole document; the board does it now
s = s.replace("""  (function lockStarted() {
    var now = Date.now();
    document.querySelectorAll(".gcard[data-kick]").forEach(function (card) {
      if (now < Date.parse(card.dataset.kick)) return;
      card.classList.add("locked");
      card.querySelectorAll("button.price").forEach(function (b) {
        b.disabled = true;
        b.classList.remove("on");
      });
    });
  })();
""", "", 1)

assert s.count("data-oid") == before
assert "function showweek" not in s and "function filterSport" not in s
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("engine in | prices %d | page %.0f KB" % (before, len(s) / 1024.0))
