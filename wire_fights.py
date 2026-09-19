"""The fights settle themselves, the way the football does.

   They were on the board and tracking nothing, because the football updater
   only knows football and the cards carried no ESPN id. The thing that
   stopped me before was the finish method — ESPN's MMA board turned out to
   carry it after all, in competitions[].details as "Unofficial Winner
   Decision" / "Kotko" / "Submission", with the round in status.period.

   So each fight card gets its bout id and both fighters' names, and a second
   updater reads the MMA board and marks the moneyline and every method row.

   Boxing is not wired: ESPN's boxing scoreboard returns no events at all, so
   Garcia v Benn has nothing to read. It stays as it is.
"""
import os
import re
import unicodedata

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
before = s.count("data-oid")

# our five bouts, as ESPN writes the names
BOUTS = {
    "ELLIOTT":  ("401897732", "Tim Elliott", "Edgar Chairez"),
    "WALDO":    ("401897733", "Waldo Cortes Acosta", "Curtis Blaydes"),
    "MCMILLEN": ("401908491", "Tommy McMillen", "Marwan Rahiki"),
    "MORENO":   ("401897731", "Brandon Moreno", "Joseph Morales"),
    "SILVA":    ("401914462", "Jean Silva", "Jose Miguel Delgado"),
}


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------- Navy comes off the board ----
CARD = re.compile(r'      <div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>\n', re.S)
dropped = []


def drop(m):
    c = m.group(0)
    if re.search(r'>NAVY<', c):
        dropped.append(c.count("data-oid"))
        return ""
    return c


s = CARD.sub(drop, s)
assert len(dropped) == 1, "matched %d Navy cards" % len(dropped)

# --------------------------------------------- each fight card learns its bout ----
wired = []


def mark(m):
    c = m.group(0)
    if "data-lg=" in c or "data-bout=" in c:
        return c
    for key, (bid, lf, rf) in BOUTS.items():
        if re.search(r'>%s<' % key, c):
            wired.append(key)
            return c.replace('<div class="gcard"',
                             '<div class="gcard" data-bout="%s" data-lf="%s" data-rf="%s"'
                             % (bid, lf, rf), 1)
    return c


s = CARD.sub(mark, s)
assert len(wired) == 5, "wired %d of 5 fights: %s" % (len(wired), wired)

# ---------------------------------------------------------------- the reader ----
JS = '''  /* ---- The fights, off ESPN's MMA board ----
     One request covers every bout on the card. A finished bout gives the
     winner in competitors[].winner and how he won in details[], written
     "Unofficial Winner Decision" / "Kotko" / "Submission". */
  var MMA = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard";

  function wonBy(how, market) {
    var k = (how || "").toLowerCase();
    var ko = k.indexOf("ko") === 0 || k.indexOf("tko") >= 0;
    var sub = k.indexOf("sub") >= 0;
    var dec = k.indexOf("dec") >= 0;
    if (market === "KO") return ko;
    if (market === "SUB") return sub;
    if (market === "DEC") return dec;
    if (market === "FIN") return ko || sub;
    if (market === "DEC/SUB") return dec || sub;
    if (market === "KO/SUB") return ko || sub;
    return null;
  }

  function surname(n) {
    return (n || "").normalize("NFD").replace(/[\\u0300-\\u036f]/g, "")
      .trim().split(" ").pop().toLowerCase();
  }

  function settleFight(card, winner, how) {
    var lf = surname(card.dataset.lf), rf = surname(card.dataset.rf);
    var w = surname(winner);
    var leftWon = w && w === lf, rightWon = w && w === rf;

    var clubs = card.querySelectorAll(".ghead .gteam");
    if (clubs.length === 2) {
      stamp(clubs[0], leftWon, false);
      stamp(clubs[1], rightWon, true);
    }
    card.querySelectorAll(".grow").forEach(function (row) {
      var lab = row.querySelector(".gmk");
      if (!lab) return;
      var by = wonBy(how, lab.textContent.trim());
      if (by === null) return;
      var cells = row.querySelectorAll(".gcell");
      if (cells[0]) mark(cells[0], !!(leftWon && by));
      if (cells[1]) mark(cells[1], !!(rightWon && by));
    });
  }

  function refreshFights() {
    var cards = document.querySelectorAll(".board:not([hidden]) .gcard[data-bout]");
    if (!cards.length) return;
    fetch(MMA).then(function (r) { return r.json(); }).then(function (d) {
      var bouts = {};
      (d.events || []).forEach(function (e) {
        (e.competitions || []).forEach(function (c) { bouts[String(c.id)] = c; });
      });
      cards.forEach(function (card) {
        var c = bouts[card.dataset.bout];
        if (!c) return;
        var st = ((c.status || {}).type) || {};
        if (st.state === "in" || st.state === "post") {
          card.classList.add("locked");
          card.querySelectorAll("button.price").forEach(function (b) { b.disabled = true; });
        }
        if (st.state !== "post") return;
        var winner = "";
        (c.competitors || []).forEach(function (x) {
          if (x.winner) winner = ((x.athlete || {}).displayName || "");
        });
        var how = "";
        (c.details || []).forEach(function (dd) {
          var t = ((dd.type || {}).text || "");
          if (t.indexOf("Unofficial Winner") === 0) {
            how = t.replace("Unofficial Winner", "").trim();
          }
        });
        settleFight(card, winner, how);
      });
    }).catch(function () {});
  }

  function refreshVisible() {'''
once("  function refreshVisible() {", JS, "the visible refresher")

once("  refreshVisible();\n  setInterval(refreshVisible, 30000);",
     "  refreshVisible();\n  refreshFights();\n"
     "  setInterval(refreshVisible, 30000);\n  setInterval(refreshFights, 30000);",
     "the refresh timers")

assert s.count("data-oid") == before - dropped[0]
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("Navy removed | fights wired:", len(wired), wired, "| prices:", s.count("data-oid"))
