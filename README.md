# The Arena

the-arenasports.pages.dev. A static page and a few JSON files on Cloudflare
Pages: no server, no database in the way of a reader, and the live work done
in whatever browser is looking at it.

This folder is `~/Desktop/the arena`. Everything the site is built from is
in it and nothing it runs reaches outside it. It can be moved; only the
LaunchAgent below names the path.

    master.html   the page
    site/         what deploys
    build/        every script, ours and the ones copied from QB Spy
    data/         every JSON and CSV the scripts read, and qbspy.db
    prices/       what each board charged, by league and week
    cache/        fetched pages, re-readable
    logs/         agent.log and refresh.log
    shots/        working screenshots
    attic/        scripts that ran once while the page was being built

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

`build/refresh.py --if-due` every ten minutes, from
`~/Library/LaunchAgents/com.sportsodds.refresh.plist`. It wakes 120, 60 and
30 minutes before each kickoff and first bell; 3.5 and 5.5 hours after a
game, 7 and 9 after a fight card; five times a day for the sweep; once at
10am for the hub; and on every pass while a fight card is actually running,
because a knockout moves every bout left on the bill. `refresh.py` names
every script it calls -- that list is the truth about what is alive here.

## Deploying

    cd ~/Desktop/the\ arena/site && npx wrangler pages deploy . --project-name=the-arenasports --branch=main

`fill_week.py`, `fill_fights.py` and the rest deploy themselves at the end of
a run.

## What came from QB Spy

Copied in on Sep 18, 2026 so this folder stands on its own:

    build/read_dk.py     the DraftKings reader, with store.py and
                         fetch_preview.py that it needs
    build/hub_*.py       the thirteen hub readers, run once a day at 10 ET
    data/qbspy.db        the play record, for the head-to-head model and the
                         props backfill. Six gigabytes; git ignores it.
    data/data.js         the passers, for birthdays

They are copies. QB Spy keeps its own and the two drift from here on.
Nothing the page itself loads comes from QB Spy: every logo, face and font
it shows is under `site/`.
