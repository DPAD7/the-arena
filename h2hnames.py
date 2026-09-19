"""The two passers stand under their own ends of the bar.

   They were above it, either side of the label, which put them a long way
   from the numbers they belong to -- the reader's eye had to cross the bar to
   pair a name with its yards. Below the bar they sit directly over each man's
   own count, and the label keeps the top line to itself.

   Done once per card as it is placed, so a card drawn from the schedule and
   one built by hand come out the same.
"""
import os

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:44], s.count(old))
    s = s.replace(old, new, 1)


once("""  .h2hx { padding: 10px 0 4px; border-top: 1px dashed var(--edge); }""",
     """  .h2hx { padding: 10px 0 4px; border-top: 1px dashed var(--edge); }
  /* each passer's name under his own end of the bar */
  .h2hnames {
    display: flex; justify-content: space-between; align-items: baseline;
    margin: 7px 2px 0;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 15px; letter-spacing: 0.02em;
  }""", "the h2h padding")

once("""  function armHide(card) {""",
     """  /* the names come out of the top line and go under the bar, once */
  function nameUnder(card) {
    var h = card.querySelector(".h2hx");
    if (!h || h.querySelector(".h2hnames")) return;
    var head = h.querySelector(".ptdhead");
    var row = h.querySelector(".h2hrow");
    if (!head || !row) return;
    var sides = head.querySelectorAll("span:not(.gmk)");
    if (sides.length !== 2) return;
    var names = document.createElement("div");
    names.className = "h2hnames";
    var left = document.createElement("span");
    left.textContent = sides[0].textContent;
    left.style.color = sides[0].style.color || "var(--amber)";
    var right = document.createElement("span");
    right.textContent = sides[1].textContent;
    right.style.color = sides[1].style.color || "#5aa9ff";
    names.appendChild(left);
    names.appendChild(right);
    row.parentNode.insertBefore(names, row.nextSibling);
    sides[0].remove();
    sides[1].remove();
    head.classList.add("ptdhead--bare");
  }

  function armHide(card) {""", "the hide arming")

for anchor in ("""      lockOne(card);
      armHide(card);
      row.appendChild(card);""",
               """      lockOne(card);
      armHide(card);
      box.appendChild(card);"""):
    assert s.count(anchor) == 1
    s = s.replace(anchor, anchor.replace("      armHide(card);",
                                         "      armHide(card);\n      nameUnder(card);"), 1)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("names moved under the bar")
