"""The fights get their prices, their own start times, and their own shape.

   ESPN stamps every fight on a card with the time its block begins -- three
   times for thirteen fights -- so grouping by the clock put a heading over
   each block and nothing useful under it. DraftKings times each fight
   separately, which is what a card actually looks like. So where DK has the
   fight we take its time and its two prices; the rest keep the block time.

   And a fight card is not a slate: the rows come off, the event name goes on,
   and the fights sit in the order they are fought.
"""
import json
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()
ML = json.load(open("/tmp/ufc_ml.json"))
DKEV = {e["id"]: e for e in json.load(open("/tmp/dk_ufc.json"))}
DKSEL = json.load(open("/tmp/dkml_ufc.json"))

# which DraftKings event each of our fights is, so we can take its clock too
mk = {m["id"]: m for m in DKSEL["markets"] if (m.get("name") or "") == "Moneyline"}
oid_to_event = {}
for sel in DKSEL["selections"]:
    m = mk.get(sel.get("marketId"))
    if m:
        oid_to_event[sel["id"]] = m.get("eventId")

m = re.search(r'  var FIGHTS = (\[\[.*?\]\]);\n', s, re.S)
fights = json.loads(m.group(1))
priced = timed = 0
for f in fights:
    p = ML.get(f[1])
    while len(f) < 12:
        f.append("")
    if p:
        f[8:12] = p
        priced += 1
        eid = oid_to_event.get(p[1])
        when = (DKEV.get(eid) or {}).get("startEventDate")
        if when:
            f[2] = when[:16] + "Z"
            timed += 1
    else:
        f[8:12] = ["", "", "", ""]
s = s[:m.start()] + "  var FIGHTS = " + json.dumps(fights, separators=(",", ":")) + ";\n" + s[m.end():]
print("fights: %d priced, %d given their own start time" % (priced, timed))

# the name of the card each fight belongs to, for the heading
once = lambda old, new: None
old = "  var FIGHTCARDS = "
assert s.count(old) == 1

# ------------------------------------------------------------ the frame ----
OLD_FRAME = """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      GHOST + '</span>' + lastName(f[3]) + '</span>' +
      '<span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + lastName(f[5]) + '<span class="gml">' + GHOST +
      '</span></span></div>' +"""
assert s.count(OLD_FRAME) == 1
s = s.replace(OLD_FRAME, """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      priceSlot(f[8], f[9]) + '</span>' + lastName(f[3]) + '</span>' +
      '<span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + lastName(f[5]) + '<span class="gml">' +
      priceSlot(f[10], f[11]) + '</span></span></div>' +""", 1)

# ----------------------------------------------- a fight card, not a slate --
OLD_BUILD = """      if (p.time !== tm) {
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
      }"""
assert s.count(OLD_BUILD) == 1
s = s.replace(OLD_BUILD, """      /* A fight card is one bill, in fight order -- it gets the event's name
         and no clock rows, because every fight already carries its own. */
      var slot = it[0] === "mma" ? (it[4] || "Fight card") : p.time;
      if (slot !== tm) {
        tm = slot;
        var n = items.filter(function (x) {
          var q = etParts(x[2]);
          return x[0] === it[0] && q.day + " " + q.date === key &&
                 (x[0] === "mma" ? (x[4] || "Fight card") : q.time) === slot;
        }).length;
        var board = document.createElement("div");
        board.className = "board board--nfl";
        board.appendChild(head("slot-h",
          slot + (n > 1 && it[0] !== "mma" ? ' <span class="swipe">swipe &rsaquo;</span>' : "")));
        row = document.createElement("div");
        row.className = it[0] === "mma" ? "bill" : "caro";
        board.appendChild(row);
        BOARD.appendChild(board);
      }""", 1)

# the fight items carry their card's name
OLD_ITEMS = """  function fightItems(list) {
    return list.map(function (f) {
      return ["mma", f[1], f[2], fightFrame(f)];
    });
  }"""
assert s.count(OLD_ITEMS) == 1
s = s.replace(OLD_ITEMS, """  function fightItems(list) {
    var named = {};
    FIGHTCARDS.forEach(function (e) { named[e[1]] = e[3]; });
    return list.map(function (f) {
      return ["mma", f[1], f[2], fightFrame(f), named[f[0]] || "Fight card"];
    });
  }""", 1)

# a bill stacks; it does not swipe
s = s.replace("  .caro {", """  .bill { display: flex; flex-direction: column; gap: 12px; }
  .bill .gcard { width: auto; }
  .caro {""", 1)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("fights stack under their card's name")
