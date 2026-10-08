# Research behind the picks

Scripts only; the data they read was built in a session scratch folder and is rebuilt by
running them. Paths inside still point at that scratch folder (`.../scratchpad/`); change
the base path before rerunning.

## nfl_h2h — QB head-to-head (who throws for more yards)
- `study5.py` builds the pre-game table from nflverse play-by-play: defense faced (pass EPA,
  YAC allowed), WR1 yards allowed, offense EPA/success, pressure, coach change.
- `search5.py` the walk-forward box search; `locked_2023_24.json` the cuts locked on 2023–24.
- `thisweek2.py` scores the week's games from BettingPros lines (H2H market 74, pass yards 100,
  receiving yards 105). No price in the score.
- Result: edge-score lead 6+ won 78–84% blind (2024, 2025); 2+ boxes 76–80%, 3+ 87–92%.
  A game gets a read only when its H2H and every receiver line on both teams are posted.

## ufc_boxes — fight moneyline box count (no odds)
- `s1.py s2.py s3.py parse.py` (with `fetch.py cache.py`) crawl UFC Stats 2010→ into
  fights.csv / fighters.csv / history.csv.
- `feat.py` pre-fight features; `odds2.py` joins closing odds (used only to sort fights in tests);
  `elo.py` rating; `rounds.py rprof.py` round-by-round profiles.
- `run.py common.py index.py` pull every fighter's full pro record (gidstats first, Sherdog fallback).
- `boxes.py` the UFC-stat boxes; `pro.py` adds the pro-record boxes and tests by era.
- `card2.py <card.json> <date>` scores a booked card; keep the 19 boxes, lead 7+ = the 75% tier.
- Blind test (boxes and cutoff set on 2010–18 only): 70% / 75% / 76% in 2019–21 / 2022–23 /
  2024–26, 74% overall on 430 fights.
- `finish.py` finish boxes (not yet at 75%); `model2.py` the gradient-boosting check (no better).
- Weekly: rank every men's fight → `site/boxpicks.json` (ticket with the rank on the card),
  log in `data/boxpicks_log.csv`, fill results after the card.
