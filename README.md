# The Arena

sports-odds.pages.dev. A static page and a few JSON files on Cloudflare
Pages: no server, no database in the way of a reader, and the live work done
in whatever browser is looking at it.

This folder is `~/Desktop/the arena`. Everything the site is built from is
in it. `~/odds` and `~/Desktop/odds`, its two earlier homes, are symlinks
here so an older path still resolves.

    master.html          the page: markup, styles, script and the last known
                         prices, in one file. pagefile.py is the only door
                         into it -- it refuses a write against a copy that
                         has moved, which is how a scheduled run stopped
                         eating an edit made by hand.
    site/                what wrangler ships. index.html is built from
                         master.html by pagefile.deployable(), so it is never
                         edited and never committed.
    site/prices.json     every price on the board, and when each bout starts.
                         Prices live here rather than in the page so a price
                         moving and an edit to the page cannot collide.
    site/final/<id>.json a settled game, written by settle.py. A card that
                         finds its own file stops asking anybody anything.
    site/ledger.json     the passers' week, built by ledger.py from those
                         files, with alt_ptd.py's price ladder hung on it.
    attic/               scripts that patched the page once while it was
                         being built. Nothing there runs now.

## What runs, and when

`refresh.py --if-due` every ten minutes, from
`~/Library/LaunchAgents/com.sportsodds.refresh.plist`. It wakes 120, 60 and
30 minutes before each kickoff and first bell; 3.5 and 5.5 hours after a
game, 7 and 9 after a fight card; five times a day for the sweep; once at
10am for the hub; and on every pass while a fight card is actually running,
because a knockout moves every bout left on the bill. `refresh.py` names
every script it calls -- that list is the truth about what is alive here.

## Deploying

    cd ~/Desktop/the\ arena/site && npx wrangler pages deploy . --project-name=sports-odds --branch=main

`fill_week.py`, `fill_fights.py` and the rest deploy themselves at the end of
a run.

## What it borrows from QB Spy

Three things, all from `~/qbspy`, all deliberate. `qbspy/` here is a symlink
to that folder, so the borrowed files can be reached from inside this one.
They are not copies: the database is six gigabytes and is written by QB
Spy's own jobs, so a copy would go stale the same afternoon.

    build/read_dk.py     the DraftKings reader. It sits there because it
                         reads through QB Spy's own store, and one reader is
                         right where two would drift apart.
    data/qbspy.db        the play record, for the head-to-head model and the
                         props backfill.
    data/data.js         the passers, for birthdays.
    build/hub_*.py       the thirteen hub readers, run once a day at 10 ET by
                         refresh.py from inside `~/qbspy`, logging to
                         `~/qbspy/hub_sweep.log`.

Nothing in QB Spy reaches back this way. Nothing the page itself loads comes
from QB Spy either: every logo, face and font it shows is under `site/`.
