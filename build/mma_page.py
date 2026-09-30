"""The UFC year on the rails: months across the top, that month's fight
   nights underneath; a finished event read from its own file.

   The football rails are weeks; a fight card has no week, so under the UFC
   pill the top rail shows the months of the year that hold an event and the
   day rail the fight nights of the month picked. A card whose event has
   finished reads site/final/mma-{event}.json (mma_year.py writes it) rather
   than ESPN's live board, which only carries the day's own events.
"""
import os
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
s = pagefile.read()
n = 0


def rep(a, b):
    global s, n
    assert s.count(a) == 1, (s.count(a), a[:70])
    s = s.replace(a, b, 1)
    n += 1


# the fight card says which event it belongs to
rep('''    return '<div class="gcard" data-bout="' + f[1] + '" data-sport="mma"' +''',
    '''    return '<div class="gcard" data-bout="' + f[1] + '" data-event="' + f[0] + '" data-sport="mma"' +''')

# the UFC day rail: every fight night of the month picked, past ones included
rep('''    if (sport === "mma") {
      var seen = {}, out = [], now = Date.now();
      FIGHTS.forEach(function (f) {
        var k = dayKeyOf(f[2]), t = Date.parse(f[2]);
        if (seen[k] || t < now - 4 * 86400000) return;
        seen[k] = 1; out.push([k, f[2]]);
      });''', '''    if (sport === "mma") {
      var seen = {}, out = [];
      FIGHTS.forEach(function (f) {
        var k = dayKeyOf(f[2]);
        if (seen[k] || monthKeyOf(f[2]) !== mmaMonth) return;
        seen[k] = 1; out.push([k, f[2]]);
      });''')

# months across the top for UFC
rep('''  /* ---- the week rail, whichever league is asking ---- */
  function weekTabs(n, current) {''', '''  /* ---- months, for the fights: the year's events, a month at a time ---- */
  var MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  function monthKeyOf(iso) {
    var d = new Date(iso);
    var et = new Date(d.toLocaleString("en-US", { timeZone: "America/New_York" }));
    return et.getFullYear() + "-" + ("0" + (et.getMonth() + 1)).slice(-2);
  }
  var mmaMonth = monthKeyOf(new Date().toISOString());
  function monthTabs() {
    wbar.innerHTML = "";
    var seen = {}, keys = [];
    FIGHTS.forEach(function (f) { var k = monthKeyOf(f[2]); if (!seen[k]) { seen[k] = 1; keys.push(k); } });
    keys.sort();
    if (keys.length && keys.indexOf(mmaMonth) < 0) {
      /* no event this month: the nearest month that has one */
      mmaMonth = keys.filter(function (k) { return k >= mmaMonth; })[0] || keys[keys.length - 1];
    }
    keys.forEach(function (k) {
      var t = document.createElement("button");
      t.className = "wktab";
      t.type = "button";
      t.setAttribute("role", "tab");
      t.dataset.mo = k;
      t.textContent = MONTHS[Number(k.slice(5)) - 1];
      t.setAttribute("aria-selected", k === mmaMonth ? "true" : "false");
      wbar.appendChild(t);
    });
    var on = wbar.querySelector('[aria-selected="true"]');
    if (on) on.scrollIntoView({block: "nearest", inline: "center"});
  }

  /* ---- the week rail, whichever league is asking ---- */
  function weekTabs(n, current) {''')

rep('''    var t = e.target.closest(".wktab");
    if (!t) return;
    var w = Number(t.dataset.wk);
    if (sport === "nfl") { week = w; } else { cfbWeek = w; }''', '''    var t = e.target.closest(".wktab");
    if (!t) return;
    if (sport === "mma") {
      mmaMonth = t.dataset.mo;
      wbar.querySelectorAll(".wktab").forEach(function (x) {
        x.setAttribute("aria-selected", x.dataset.mo === mmaMonth ? "true" : "false");
      });
      day = "";
      buildDays();
      render();
      return;
    }
    var w = Number(t.dataset.wk);
    if (sport === "nfl") { week = w; } else { cfbWeek = w; }''')

rep('''    var weekly = sport === "nfl" || sport === "college-football";
    wbar.hidden = !weekly;
    if (weekly) {''', '''    var weekly = sport === "nfl" || sport === "college-football";
    wbar.hidden = !(weekly || sport === "mma");
    if (sport === "mma") {
      var hitDay = FIGHTS.filter(function (f) { return dayKeyOf(f[2]) === day; })[0];
      if (hitDay) mmaMonth = monthKeyOf(hitDay[2]);
      monthTabs();
    }
    if (weekly) {''')

# a finished event is read from its file; the live board only for the day's own
rep('''  function refreshFights() {
    var cards = document.querySelectorAll(".board:not([hidden]) .gcard[data-bout]");
    if (!cards.length) return;
    fetch(MMA).then(function (r) { return r.json(); }).then(function (d) {
      var bouts = {};
      (d.events || []).forEach(function (e) {
        (e.competitions || []).forEach(function (c) { bouts[String(c.id)] = c; });
      });
      cards.forEach(function (card) {
        var c = bouts[card.dataset.bout];
        if (!c) return;''', '''  function settleBoutCard(card, c) {''')
rep('''        settleFight(card, winner, how);
        showHits(card);
      });
    }).catch(function () {});
  }
''', '''        settleFight(card, winner, how);
        showHits(card);
  }
  function applyBoard(cards, d) {
    var bouts = {};
    (d.events || []).forEach(function (e) {
      (e.competitions || []).forEach(function (c) { bouts[String(c.id)] = c; });
    });
    cards.forEach(function (card) {
      var c = bouts[card.dataset.bout];
      if (c) settleBoutCard(card, c);
    });
  }
  function refreshFights() {
    var cards = [].slice.call(document.querySelectorAll(".board:not([hidden]) .gcard[data-bout]"));
    if (!cards.length) return;
    var now = Date.now(), live = [], byEvent = {};
    cards.forEach(function (card) {
      if (card.dataset.settledBout) return;
      var t = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
      if (t && t < now - 8 * 3600000 && card.dataset.event) {
        (byEvent[card.dataset.event] = byEvent[card.dataset.event] || []).push(card);
      } else if (!t || t < now + 20 * 60000) {
        live.push(card);
      }
    });
    Object.keys(byEvent).forEach(function (eid) {
      fetch("final/mma-" + eid + ".json").then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (d) { applyBoard(byEvent[eid], d); byEvent[eid].forEach(function (c) { c.dataset.settledBout = "1"; }); })
        .catch(function () { live.push.apply(live, byEvent[eid]); });
    });
    if (!live.length) return;
    fetch(MMA).then(function (r) { return r.json(); }).then(function (d) { applyBoard(live, d); }).catch(function () {});
  }
''')
if not pagefile.write(s):
    print("page changed under us, not written")
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n<meta name="referrer" content="no-referrer">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(doc + s + "\n</body>\n</html>\n")
print("page patched:", n, "edits")
