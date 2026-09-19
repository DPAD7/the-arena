"""A card you do not want to look at goes to the bottom, and comes back.

   Ninety-nine college games on a Saturday is a lot of scrolling past things
   you have already decided against. So every card carries a small button in
   its top corner: press it and the card drops below a dashed line at the foot
   of the board, folded away behind an arrow with a count. Press the same
   button down there and it goes back to its place.

   What is hidden is remembered, so it stays hidden when the day changes and
   when the page is opened again. It is never deleted -- the card is moved.
"""
import os

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:44], s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------------ style ---
once("""  .gmorebtn {""",
     """  .gcard { position: relative; }
  .ghide {
    position: absolute; top: 6px; right: 8px; z-index: 5;
    appearance: none; background: none; border: 0; cursor: pointer;
    padding: 4px 6px; line-height: 0; color: var(--muted); opacity: 0.5;
    transition: opacity 0.15s, color 0.15s;
  }
  .ghide:hover, .ghide:focus-visible { opacity: 1; color: var(--amber); }
  .ghide svg { display: block; }
  /* the foot of the board, where hidden cards wait */
  .hidewrap { margin-top: 26px; }
  .hiderule {
    border: 0; border-top: 1px dashed var(--edge); margin: 0 0 10px;
  }
  .hidebar {
    display: flex; align-items: center; gap: 8px; width: 100%;
    appearance: none; background: none; border: 0; cursor: pointer;
    padding: 4px 2px 10px; color: var(--muted);
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 13px; letter-spacing: 0.12em;
    text-transform: uppercase;
  }
  .hidebar svg { transition: transform 0.15s; }
  .hidebar.open svg { transform: rotate(180deg); }
  .hidebox { display: flex; flex-direction: column; gap: 12px; }
  .hidebox[hidden] { display: none !important; }
  .gmorebtn {""", "the arrow styling")

# ------------------------------------------------------------------- JS -----
once("""  function clearBoard() {""",
     """  /* ---- what is put away ----
     Cards are remembered by the id they already carry, so a card hidden on
     Sunday is still hidden when Sunday is looked at again. */
  var HIDEKEY = "odds.hidden.v1";
  var hid = {};
  try { hid = JSON.parse(localStorage.getItem(HIDEKEY) || "{}") || {}; } catch (e) { hid = {}; }
  function idOf(card) {
    return card.dataset.espn || card.dataset.bout || card.dataset.fight || "";
  }
  function saveHidden() {
    try { localStorage.setItem(HIDEKEY, JSON.stringify(hid)); } catch (e) {}
  }
  var EYE = '<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true">' +
    '<path d="M2 12s3.6-6 10-6 10 6 10 6-3.6 6-10 6-10-6-10-6z" fill="none" ' +
    'stroke="currentColor" stroke-width="1.8"/>' +
    '<circle cx="12" cy="12" r="2.6" fill="none" stroke="currentColor" stroke-width="1.8"/>' +
    '<path class="slash" d="M4 20L20 4" stroke="currentColor" stroke-width="1.8" ' +
    'stroke-linecap="round"/></svg>';
  function hideBtn(on) {
    var b = document.createElement("button");
    b.className = "ghide";
    b.type = "button";
    b.setAttribute("aria-label", on ? "Show this game" : "Hide this game");
    b.innerHTML = EYE;
    b.querySelector(".slash").style.display = on ? "" : "none";
    return b;
  }
  function armHide(card) {
    var old = card.querySelector(":scope > .ghide");
    if (old) old.remove();
    var id = idOf(card);
    if (!id) return;
    var b = hideBtn(!!hid[id]);
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      if (hid[id]) { delete hid[id]; } else { hid[id] = 1; }
      saveHidden();
      render();
    });
    card.appendChild(b);
  }

  function clearBoard() {""", "the board clearer")

# every card gets the button, drawn or pooled
once("""      var card = nodeFor(it[1], it[3]);
      card.hidden = false;
      lockOne(card);
      row.appendChild(card);""",
     """      var card = nodeFor(it[1], it[3]);
      card.hidden = false;
      lockOne(card);
      armHide(card);
      row.appendChild(card);""", "the card placer")

# the board is built in two parts now: what is shown, and what is put away
once("""  function build(items, showLeague) {
    clearBoard();""",
     """  function build(all, showLeague) {
    clearBoard();
    var items = [], away = [];
    all.forEach(function (it) { (hid[it[1]] ? away : items).push(it); });""",
     "the builder")

once("""    if (!items.length) {
      BOARD.appendChild(head("wkempty", "Nothing on the board."));
    }
    if (window.markSaved) markSaved(BOARD);
    refreshVisible();""",
     """    if (!items.length && !away.length) {
      BOARD.appendChild(head("wkempty", "Nothing on the board."));
    } else if (!items.length) {
      BOARD.appendChild(head("wkempty", "Everything here is hidden."));
    }
    if (away.length) putAway(away);
    if (window.markSaved) markSaved(BOARD);
    refreshVisible();""", "the empty case")

once("""  function nflItems(list) {""",
     """  /* the dashed line, the count, and the cards folded behind it */
  var hideOpen = false;
  function putAway(away) {
    away.sort(function (a, b) { return Date.parse(a[2]) - Date.parse(b[2]); });
    var wrap = document.createElement("div");
    wrap.className = "hidewrap";
    var rule = document.createElement("hr");
    rule.className = "hiderule";
    wrap.appendChild(rule);
    var bar = document.createElement("button");
    bar.type = "button";
    bar.className = "hidebar" + (hideOpen ? " open" : "");
    bar.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg>' +
      "<span>Hidden \\u00B7 " + away.length + "</span>";
    wrap.appendChild(bar);
    var box = document.createElement("div");
    box.className = "hidebox";
    box.hidden = !hideOpen;
    away.forEach(function (it) {
      var card = nodeFor(it[1], it[3]);
      card.hidden = false;
      lockOne(card);
      armHide(card);
      box.appendChild(card);
    });
    wrap.appendChild(box);
    bar.addEventListener("click", function () {
      hideOpen = !hideOpen;
      box.hidden = !hideOpen;
      bar.classList.toggle("open", hideOpen);
    });
    BOARD.appendChild(wrap);
  }

  function nflItems(list) {""", "the item makers")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("hide button, dashed line, folded section")
