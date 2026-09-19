# The odds board

Live at **https://sports-odds.pages.dev**

Everything for this project now lives here, on the Desktop, rather than in a
session scratchpad that gets wiped.

| File | What it is |
|---|---|
| `master.html` | the page, as one file — edit this one |
| `site/index.html` | the same page wrapped in a full HTML document; this is what deploys |
| `refresh.py` | reads DraftKings, rewrites only the prices that moved, deploys |
| `when.py` | prints the wake plan — every moment the refresher will look, and why |
| `build_sources.py` | works out where each price on the board comes from; writes `sources.json` |
| `sources.json` | 27 events, which categories to ask for, plus two league-wide requests |
| `served.json` | which wakes have already been taken, so none fires twice |
| `refresh.log` | what moved, and when |
| `cache/` | the original pulls, kept so `build_sources.py` can be rerun |

Any change to `master.html` has to be copied into `site/index.html` wrapped in
the doctype/head/body — every patch script here does that at the end. The
viewport meta tag only exists on the wrapped copy, and without it the page is
not mobile.

## Keeping the prices right

DraftKings sends **no timestamp, no version and no ETag**, and answers
`cache-control: no-store`. There is no way to ask whether a price has changed
short of fetching it and comparing. So that is what `refresh.py` does: it
fetches, compares against what is on the page, and writes nothing at all
unless a digit is different.

It only asks about events that have not kicked off. A game in progress is not
priced any more and its buttons are already locked by the clock on the page.

**The cadence is two hours, one hour and half an hour before each kickoff.**
Overlapping games share a wake, so a Sunday with fourteen one-o'clock games
costs the same as one game. `com.sportsodds.refresh` wakes every ten minutes
and asks `refresh.py --if-due` whether this is one of those moments; any other
time it exits without asking DraftKings anything.

```
python3 when.py                  # the plan: what fires, when, and for which games
python3 refresh.py --dry         # what has moved right now, without writing
python3 refresh.py               # rewrite what moved and deploy
launchctl list | grep sportsodds # is the agent loaded
tail -f refresh.log
```

`ODDS_NOW=2026-09-12T14:00:30+00:00 python3 refresh.py --if-due --dry` stands
at another moment, to rehearse a wake without waiting for one.

### The Mac has to be awake

The agent cannot fire on a sleeping machine, and scheduling a `pmset` wake
needs a password. A `caffeinate -dimsu -t 43200` was started at 2:02 AM on
Sep 12, so the Mac is up until about 2 PM that day — every wake from 10 AM
onward is covered. **Sunday and Monday need it renewed**, which is one line:

```
caffeinate -dimsu -t 43200 &      # twelve more hours
```

Nothing here runs 24/7 on its own; that was deliberate.

### What can go stale without failing

Two of the 173 prices — the Garcia/Benn KO method — have no source
`build_sources.py` could find, and DraftKings now returns nothing for that
event's method categories. They will never refresh. `refresh.py` counts them
under "market no longer offered" rather than pretending.

Head-to-head passing yards markets get pulled and reposted by DraftKings; six
of ten were already gone at 2 AM. Those are reported the same way and their
displayed price is left alone rather than deleted.

## Selection ids hold still

`data-oid` is DraftKings' own selection id, and those ids survive a
repricing — 206 of 206 checked on the Lions game, with 146 of them carrying a
different price than an hour earlier. That is what makes "look it up again by
the same id" work at all.

Two requests are league-wide rather than per-event, because nothing else
serves them:

- first-quarter receptions — `/leagues/88808/categories/1342/subcategories/18527`
- head-to-head passing yards — `/leagues/88808/categories/1185/subcategories/11977`

## Reading DraftKings at all

`/Users/joe/qbspy/build/read_dk.py` is the only way in. It uses `curl_cffi`
with `impersonate="chrome124"`; anything else gets a 403 off the TLS
handshake. DraftKings also sends no CORS headers, so the browser can never
fetch them directly — which is why prices are baked into the page and only
ESPN is asked live.
