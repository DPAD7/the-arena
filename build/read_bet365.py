"""bet365's boosted cards, read out of a tab you already have open.

   Of the five sources this is the only one with no plain-fetch route, and it
   took four dead ends to be sure of it. `popularboostcompetitions` carries all
   of it — sixty-three kilobytes of their pipe format — and answers any request
   with two hundred and an empty body unless it carries `x-net-sync-term`. That
   term is not the session id, not any of the six cookies they set, and appears
   nowhere in the bundle they ship. It is minted by their own socket handshake
   and dies with the tab.

   Reading the rendered page instead does not help, which was the fifth dead
   end: their markets arrive over that same socket, so a browser we drive
   ourselves shows the navigation and an empty pane. The markup is filled *by*
   the protocol; it is not a way around it.

   What is left is the way in DraftKings needed before curl_cffi beat Akamai —
   ask from inside. A tab you already have open has the socket connected and
   the term live, and a read issued in that tab is the site talking to itself.
   Nothing is navigated, nothing is clicked, nothing is scrolled. The tab stays
   exactly where you left it.

   The cards sit in the markup by class, and these are theirs, not guessed —
   `rrc` is the BetBoostReactLibDefault bundle that draws this page:

       rrc-806  the name somebody wrote      "Maye Day"
       rrc-88   one leg, in the words a reader sees
       rrc-20f  the price before the boost
       rrc-a2   the price after it

   What we take is the **shape**, not the price. Their cards are built so the
   legs drag each other along — a quarterback's yards beside his own
   touchdowns, a club winning beside its receiver producing — and that is a
   claim about correlation our own record can settle. Prices are stored because
   a source's own number should never be quietly dropped, and they stay in the
   database where the house rule leaves them.

   Open a bet365 tab on the boosts, then:

       python3 build/read_bet365.py
       python3 build/read_bet365.py --show     print them, write nothing

   Chrome needs *View → Developer → Allow JavaScript from Apple Events* ticked
   once, or every read comes back empty with no explanation.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import re
import subprocess
import time

from store import open_db, patiently, put_many

# The boost page. The hash route is theirs: B12 is football, C… the
# competition, and K^5 the boosts tab.
PAGE = ("https://www.va.bet365.com/#/AC/B12/C20426855/D48/E1441/F36/K%5E5/")

SCHEMA = """
-- A boosted card, as a reader sees it. `name` is the two words somebody wrote
-- over it; `shape` is which of their three templates it is, worked out from
-- the legs rather than stated anywhere.
CREATE TABLE IF NOT EXISTS boost_card (
    read_on     TEXT NOT NULL,
    card_id     TEXT NOT NULL,      -- name and legs, hashed, so a card is one row
    name        TEXT NOT NULL,
    legs        INTEGER NOT NULL,
    shape       TEXT,
    was         TEXT,               -- the price before the boost
    now         TEXT,               -- and after
    -- The game, and when it kicks off. Written above the block of boosts
    -- rather than on any of them, so they are climbed to rather than read
    -- off the card. Without them a boost reached no page: it is the fixture
    -- that decides which week a card belongs to, and a card with no week is
    -- a card nothing can ever show.
    fixture     TEXT,
    kickoff     TEXT,
    PRIMARY KEY (read_on, card_id)
);

-- One leg of one card, in the words it was written in. Nothing is parsed into
-- a player and a figure here: that is settle_names.py's job, against
-- person_name, and doing it at read time is how a man gets lost.
CREATE TABLE IF NOT EXISTS boost_leg (
    read_on     TEXT NOT NULL,
    card_id     TEXT NOT NULL,
    at          INTEGER NOT NULL,   -- 0, 1, 2 — the order they are drawn in
    said        TEXT NOT NULL,
    PRIMARY KEY (read_on, card_id, at)
);
"""

def tab_on_bet365():
    """A tab already on bet365, whose socket we borrow."""
    find = '''tell application "Google Chrome"
set out to ""
repeat with w from 1 to count of windows
repeat with t from 1 to count of tabs of window w
set out to out & w & "|" & t & "|" & (URL of tab t of window w) & ","
end repeat
end repeat
return out
end tell'''
    out = subprocess.run(["osascript", "-e", find],
                         capture_output=True, text=True).stdout
    for line in out.split(","):
        bits = line.strip().split("|", 2)
        if len(bits) == 3 and "bet365.com" in bits[2]:
            return bits[0], bits[1]
    return None, None


def in_tab(window, tab, code):
    """Run one line of JavaScript inside that tab and hand back what it said."""
    code = code.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    script = ('tell application "Google Chrome" to tell tab %s of window %s '
              'to execute javascript "%s"' % (tab, window, code))
    done = subprocess.run(["osascript", "-e", script],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(
            'Chrome would not run it: ' + done.stderr.strip() +
            '\nTick View > Developer > Allow JavaScript from Apple Events.')
    return done.stdout.strip()


# The same read as before, but issued inside the tab rather than in a browser
# of our own. One expression, because that is all AppleScript will carry.
PICK = """
(function () {
  var out = [], seen = {};
  var names = document.querySelectorAll('.rrc-806');
  for (var i = 0; i < names.length; i++) {
    var tag = names[i], card = tag.closest('.rrc-72') || tag.parentElement;
    for (var n = 0; n < 4 && card && !card.querySelector('.rrc-88'); n++) {
      card = card.parentElement;
    }
    if (!card) { continue; }
    var legs = [].slice.call(card.querySelectorAll('.rrc-88')).map(function (e) {
      return e.textContent.replace(/\\u00a0/g, ' ').trim();
    }).filter(Boolean);
    if (!legs.length) { continue; }
    var k = tag.textContent.trim() + '|' + legs.join('|');
    if (seen[k]) { continue; }
    seen[k] = 1;
    var say = function (s) { var e = card.querySelector(s); return e ? e.textContent.trim() : null; };

    /* The game the boost is on, and when it kicks off. Both are written
       above the block rather than on any card in it, so this climbs out
       until it finds them — matched on what they say, because a line
       comment cannot live here: in_tab folds the whole block onto one line
       and everything after a slash-slash is swallowed. */
    var fixture = null, when = null, up = card;
    for (var u = 0; u < 8 && up && (!fixture || !when); u++) {
      up = up.parentElement;
      if (!up) { break; }
      var bits = up.querySelectorAll('*');
      for (var b = 0; b < bits.length && (!fixture || !when); b++) {
        var t = bits[b].textContent.replace(/\\u00a0/g, ' ').trim();
        if (!t || t.length > 60 || bits[b].children.length) { continue; }
        if (!fixture && / @ /.test(t) && !/[0-9]{2}:/.test(t)) { fixture = t; }
        if (!when && /^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\\b.*\\d/.test(t)) { when = t; }
      }
    }

    out.push({ name: tag.textContent.trim(), legs: legs,
               was: say('.rrc-20f'), now: say('.rrc-a2'),
               fixture: fixture, when: when });
  }
  return JSON.stringify({ cards: out, where: location.hash.slice(0, 50) });
})()
"""


def read_tab():
    """The cards, out of whichever bet365 tab is open."""
    window, tab = tab_on_bet365()
    if not window:
        raise SystemExit('no bet365 tab is open — open the boosts and run again.')
    said = in_tab(window, tab, PICK)
    if not said:
        raise SystemExit(
            'the tab said nothing. Tick View > Developer > '
            'Allow JavaScript from Apple Events, then run again.')
    try:
        return json.loads(said)
    except ValueError:
        raise SystemExit('the tab said something unreadable:\n' + said[:300])


def shape_of(legs):
    """Which of their three templates a card is — worked out from the legs,
    since they never say. Named for what the card does, not for a code."""
    who = [re.split(r':| to ', leg)[0].strip() for leg in legs]
    kinds = [leg.split(':')[-1].strip() if ':' in leg else 'to score'
             for leg in legs]

    if any(leg.lower().startswith('money line') for leg in legs):
        return 'club and a player'
    if len(set(who)) < len(who):
        return 'one man twice, and a team-mate'
    if len(set(kinds)) == 1:
        return 'the same thing, three men'
    return 'other'


def key(name, legs):
    import hashlib
    return hashlib.md5(('|'.join([name] + legs)).encode()).hexdigest()[:12]


def main():
    show = '--show' in sys.argv
    got = read_tab()
    cards = got.get('cards', [])

    if not cards:
        # Loud, not quiet. A sweep that finds nothing must say so.
        print('bet365: no cards on that tab — it is at', got.get('where', '?'),
              '\n  open the boosts tab (K^5) and run again.')
        return 1

    read_on = time.strftime('%Y-%m-%d')
    card_rows, leg_rows = [], []
    for c in cards:
        cid = key(c['name'], c['legs'])
        card_rows.append({
            'read_on': read_on, 'card_id': cid, 'name': c['name'],
            'legs': len(c['legs']), 'shape': shape_of(c['legs']),
            'was': c.get('was'), 'now': c.get('now'),
            'fixture': c.get('fixture'), 'kickoff': c.get('when'),
        })
        for n, said in enumerate(c['legs']):
            leg_rows.append({'read_on': read_on, 'card_id': cid,
                             'at': n, 'said': said})

    for c in card_rows:
        print(f"  {c['name']:<22} {(c.get('fixture') or '?'):<28} "
              f"{c['legs']} legs  {c.get('kickoff') or ''}")
        for l in [x for x in leg_rows if x['card_id'] == c['card_id']]:
            print(f"      · {l['said']}")

    if show:
        return 0

    # A sweep can be holding the file for minutes; wait our turn rather than
    # fail, the way every other fetcher does.
    def write():
        db = open_db()
        db.executescript(SCHEMA)
        put_many(db, 'boost_card', card_rows)
        put_many(db, 'boost_leg', leg_rows)
        db.commit()

    patiently(write)
    print(f'\n{len(card_rows)} cards, {len(leg_rows)} legs written for {read_on}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
