"""The man in front rides the tick.

   The head-to-head bar already says who leads and by how much, but it says it
   in a colour and a number. A face says it before either is read. ESPN serves
   a headshot keyed on the athlete id the card already carries, so the tick
   gets one -- and only while somebody is actually in front. Level, there is no
   leader and no face.
"""
import os

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:44], s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------------ style ---
once("  .h2htick { position: absolute; top: -5px; bottom: -5px; width: 2px; background: #fff; }",
     """  .h2htick { position: absolute; top: -5px; bottom: -5px; width: 2px; background: #fff; }
  .h2hface {
    position: absolute; top: 50%; left: 50%;
    width: 30px; height: 30px; margin: -15px 0 0 -15px;
    border-radius: 50%; object-fit: cover; object-position: top center;
    background: #0d1a2b; border: 2px solid #fff;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.6);
    opacity: 0; transition: opacity 0.18s, left 0.18s;
    pointer-events: none; z-index: 3;
  }
  .h2hface.on { opacity: 1; }""", "the tick styling")

# ------------------------------------------------------- put one on the bar --
once("""          var fill = h.querySelector(".h2hfill"), tick = h.querySelector(".h2htick");""",
     """          var fill = h.querySelector(".h2hfill"), tick = h.querySelector(".h2htick");
          /* the face rides the tick, so it is made once and then moved */
          var face = h.querySelector(".h2hface");
          if (!face) {
            face = document.createElement("img");
            face.className = "h2hface";
            face.alt = "";
            (tick.parentNode || h).appendChild(face);
          }""", "the fill lookup")

once("""          } else {
            fill.style.left = "50%"; fill.style.width = "0"; tick.style.left = "50%";
          }""",
     """          } else {
            fill.style.left = "50%"; fill.style.width = "0"; tick.style.left = "50%";
          }
          /* whoever is in front, at the edge of his own fill */
          var lead = gap > 0 ? card.dataset.lqbid : (gap < 0 ? card.dataset.rqbid : "");
          if (lead && card.dataset.lg === "nfl") {
            face.src = "https://a.espncdn.com/i/headshots/nfl/players/full/" +
                       lead + ".png";
            face.style.left = tick.style.left;
            face.classList.add("on");
          } else {
            face.classList.remove("on");
            face.removeAttribute("src");
          }""", "the level case")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("the leader's face rides the tick")
