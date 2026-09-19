"""The drawn cards get the same chart the hand-built ones have.

   refresh() already asks ESPN about every visible card and paints the win
   probability into .wprow and .wpx -- the frames simply had nowhere to put it.
   So they get the same skeleton, with ids of their own, and two things are
   added: a pre-game reading from ESPN's predictor for games not yet played,
   and a limit on which cards are asked about at all. A college Saturday is
   ninety-nine cards, and ninety-nine requests every thirty seconds for games
   a month out is rude and pointless.
"""
import os

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
s = open(D + "/master.html").read()
before = s.count("data-oid")


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:44], s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------- the sheet's body ---
once('''  function sheetFor(title) {''',
     '''  /* The same chart the hand-built cards carry, with ids of its own. */
  var wpn = 0;
  function chartFor(lname, rname) {
    var k = "d" + (++wpn);
    return '<div class="wprow"><span class="wpteam" style="color:var(--amber)">' +
      lname + '</span><span class="wpbig">&mdash;</span></div>' +
      '<div class="wpx"><svg viewBox="0 0 300 120" preserveAspectRatio="none">' +
      '<defs><clipPath id="' + k + '-over"><rect x="0" y="0" width="300" height="60"/>' +
      '</clipPath><clipPath id="' + k + '-under"><rect x="0" y="60" width="300" height="60"/>' +
      '</clipPath></defs>' +
      '<line class="wpe" x1="0" y1="60" x2="300" y2="60"/>' +
      '<polygon points="" fill="#f1b82d" opacity="0.18" clip-path="url(#' + k + '-over)"/>' +
      '<polygon points="" fill="#5aa9ff" opacity="0.18" clip-path="url(#' + k + '-under)"/>' +
      '<polyline points="" fill="none" stroke="#f1b82d" stroke-width="2" ' +
      'vector-effect="non-scaling-stroke" clip-path="url(#' + k + '-over)"/>' +
      '<polyline points="" fill="none" stroke="#5aa9ff" stroke-width="2" ' +
      'vector-effect="non-scaling-stroke" clip-path="url(#' + k + '-under)"/>' +
      '</svg></div>' +
      '<div class="wprow"><span class="wpteam" style="color:#5aa9ff">' + rname +
      '</span><span class="wpbig">&mdash;</span></div>';
  }

  function sheetFor(title) {''', "the sheet builder")

# the NFL frame builds its own sheet inline; it uses the shared one now
once("""      '<dialog class="sheet gsheet"><div class="sheet__head">' +
      '<button class="sheet__x" type="button" data-shut aria-label="Back">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<h2 class="sheet__title">' + away + ' v ' + home + '</h2>' +
      '<span aria-hidden="true"></span></div>' +
      '<div class="sheet__scroll"><div class="hits" hidden></div>' +
      '<p class="wkempty">No prices yet.</p></div></dialog></div>';""",
     """      sheetFor(away + ' v ' + home) + '</div>';""", "the NFL sheet")

once('''      '<div class="sheet__scroll"><div class="hits" hidden></div>' +
      '<p class="wkempty">No prices yet.</p></div></dialog>';
  }''',
     '''      '<div class="sheet__scroll"><div class="hits" hidden></div>' +
      chartFor(title.split(" v ")[0], title.split(" v ").pop()) +
      '</div></dialog>';
  }''', "the empty sheet")

# ---------------------------------------------- a reading before kickoff ----
once('''        var pct = paintChart(card, series, lhome);''',
     '''        /* Before a ball is thrown there is no curve, only ESPN's own
           projection. It is still the number the sheet is asking for. */
        if (!series || series.length < 2) {
          var pr = d.predictor || {};
          var hp = parseFloat((pr.homeTeam || {}).gameProjection);
          if (!isNaN(hp)) {
            var left = lhome ? hp : 100 - hp;
            var reads0 = card.querySelectorAll(".wpbig");
            if (reads0.length === 2) {
              reads0[0].textContent = left.toFixed(1) + "%";
              reads0[1].textContent = (100 - left).toFixed(1) + "%";
            }
          }
        }
        var pct = paintChart(card, series, lhome);''', "the chart painting")

# ------------------------------------------------- ask about fewer cards ----
once('''  function refreshVisible() {
    document.querySelectorAll(".board:not([hidden]) .gcard[data-espn]").forEach(refresh);
  }''',
     '''  /* Only games worth asking about: anything already under way or finished,
     and anything inside the next eight days. A card in November has nothing
     to tell us and there are ninety-nine of them on a Saturday. */
  function refreshVisible() {
    var now = Date.now(), soon = now + 8 * 86400000;
    document.querySelectorAll(".board:not([hidden]) .gcard[data-espn]")
      .forEach(function (card) {
        var k = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
        if (k && k > soon) return;
        refresh(card);
      });
  }''', "the refresher")

assert s.count("data-oid") == before
assert "No prices yet." not in s
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("chart wired into every drawn card")
