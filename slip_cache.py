"""The slip remembers a pick after its card leaves the board.

   The slip used to be read straight off the page: every button wearing the
   "on" class, in document order. That held while the whole season sat in the
   markup at once. It stopped holding the moment cards started being drawn a
   day at a time -- switch from Saturday to Sunday and the Saturday pick was
   simply not in the room any more, so the slip forgot it.

   So a pick now writes down what it is -- its price and what to call it --
   beside the id that was already being kept, and the slip is built from that.
   The page is still asked for the button, but only to light it up and to hang
   the row's × on something.
"""
import os

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:40], s.count(old))
    s = s.replace(old, new, 1)


once("""    btn.classList.toggle("on", on);
    saved[id] = on || undefined;
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
    slip();""",
     """    btn.classList.toggle("on", on);
    saved[id] = on ? {o: btn.childNodes[0].textContent.trim(), l: labelFor(btn)}
                   : undefined;
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
    slip();""", "setPick")

once("""  function parlay(picks) {
    var p = 1;
    for (var i = 0; i < picks.length; i++) {
      var n = parseInt(picks[i].childNodes[0].textContent
        .replace(/\\u2212|\\u2013|\\u2014/g, "-").replace(/[^\\-0-9]/g, ""), 10);""",
     """  function parlay(picks) {
    var p = 1;
    for (var i = 0; i < picks.length; i++) {
      var n = parseInt(String(picks[i].o)
        .replace(/\\u2212|\\u2013|\\u2014/g, "-").replace(/[^\\-0-9]/g, ""), 10);""",
     "parlay")

once("""  function slip() {
    var on = Array.prototype.slice.call(document.querySelectorAll("button.price.on"));""",
     """  function slip() {
    /* Every pick that has been made, whether or not its card is on the board.
       A pick kept from an older visit may have been written before the price
       was, so anything without one is dropped rather than shown blank. */
    var on = [];
    Object.keys(saved).forEach(function (id) {
      var v = saved[id];
      if (!v) return;
      if (v === true) { delete saved[id]; return; }
      on.push({id: id, o: v.o, l: v.l,
               btn: document.querySelector('button.price[data-oid="' +
                    id.replace(/"/g, '\\\\"') + '"]')});
    });""", "slip")

once("""    var outs = on.map(function (b) { return b.dataset.oid.replace(/#/g, "%23"); }).join("+");""",
     """    var outs = on.map(function (b) { return b.id.replace(/#/g, "%23"); }).join("+");""",
     "the slip link")

once("""      var lab = document.createElement("span");
      lab.textContent = labelFor(b);
      var odds = document.createElement("span");
      odds.className = "so";
      odds.textContent = b.childNodes[0].textContent.trim();
      var x = document.createElement("button");
      x.className = "slipx"; x.type = "button"; x.textContent = "×";
      x.addEventListener("click", function () { setPick(b, false); });""",
     """      var lab = document.createElement("span");
      lab.textContent = b.l;
      var odds = document.createElement("span");
      odds.className = "so";
      odds.textContent = b.o;
      var x = document.createElement("button");
      x.className = "slipx"; x.type = "button"; x.textContent = "×";
      x.addEventListener("click", function () { drop(b.id); });""", "the slip row")

# dropping a pick has to work whether or not the button is on the page
once("""  function slip() {""",
     """  /* Taking a pick off: the button if it is here, the record either way. */
  function drop(id) {
    var btn = document.querySelector('button.price[data-oid="' +
              String(id).replace(/"/g, '\\\\"') + '"]');
    if (btn) { setPick(btn, false); return; }
    saved[id] = undefined;
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
    slip();
  }

  function slip() {""", "the dropper")

# Clear All must clear the record, not the page
once("""      document.querySelectorAll("button.price.on").forEach(function (b) { setPick(b, false); });""",
     """      Object.keys(saved).forEach(function (id) { drop(id); });""", "clear all")

assert "labelFor(b)" not in s or s.count("labelFor(b)") == 0
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("the slip is kept, not read off the page")
