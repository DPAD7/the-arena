# CFB 1+ passing TD, starting QB: blind study

Scope: **FBS vs FBS games only.** Any game with an FCS team is left out of the targets and out of the history features. Starter = the team's QB with the most pass attempts. Fit on 2016-2021 (8,403 team-games), tested blind on 2022-2026 (6,736). The 2026 data runs through Oct 8 (weeks 1-5 plus the 3 games of week 6 already played). Full tables are in `results.txt`.

## Data
- ESPN: 8,984 game summaries (cache/), the closing spread and total for each game from ESPN's core odds endpoint (median across books, not counting "Opening"; 100% coverage), and FBS team lists per season taken from the conference rosters (fbs/).
- BettingPros: market 102 is NFL only. For NCAAF, pass TDs are **market 441**, and it has props only for **2026 weeks 1-6**. There are none for 2022-2025. The book can't be tested across seasons, so it is a 2026-only side check below.

## Base rate (FBS starter, FBS opponent)
73.7%-76.5% in every season: 2016 74.9, 2017 73.7, 2018 75.6, 2019 74.3, 2020 76.5, 2021 74.8 | blind 2022 75.2, 2023 74.9, 2024 74.7, 2025 73.7, 2026 73.9.

## Model
Logistic regression with 17 pre-game features:
- QB TD/game, attempts/game and 1+ rate over his last 12 FBS games, across seasons and teams, shrunk toward the team's rate when he has few games
- team pass TDs and points per game
- opponent pass TDs and points allowed per game
- home/away/neutral
- spread, total and implied team total (ITT)
- conference game
- early season (fewer than 3 games in)
- postseason

The biggest weights are on ITT, spread, QB TD/game and QB attempts.

Blind AUC for LR, by season: 0.685, 0.699, 0.740, 0.739, 0.688. The gradient-boosted model (GB) scored 0.673-0.728, lower every season, and had a worse Brier score every season.

## Hit rate by LR band, blind
| band | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|
| 90+ | 88.2% (153) | 91.1% (124) | 95.7% (138) | 95.5% (133) | 95.0% (40) |
| 85-89 | 88.4% (215) | 89.5% (200) | 92.3% (183) | 91.7% (180) | 82.7% (81) |
| 80-84 | 85.9% (248) | 85.2% (230) | 84.3% (242) | 85.2% (271) | 84.1% (69) |
| 75-79 | 74.7% (233) | 76.2% (235) | 81.4% (236) | 79.0% (214) | 83.5% (79) |
| <75 | 63.4% (629) | 64.1% (711) | 62.2% (797) | 61.0% (816) | 63.1% (279) |

## The rule that held: LR model 90%+ (and the game has a posted line)
The rule was chosen on 2016-2021 leave-one-season-out predictions, where it hit 93.5% (913). It was then read blind:

| season | right-wrong | hit | QBs/week |
|---|---|---|---|
| 2022 | 135-18 | 88.2% | 10.9 |
| 2023 | 113-11 | 91.1% | 8.9 |
| 2024 | 132-6 | 95.7% | 9.2 |
| 2025 | 127-6 | 95.5% | 9.5 |
| 2026 | 38-2 | 95.0% | 8.0 |
| all blind | 545-43 | 92.7% | ~9 (0-18 in a given week) |

A wider tier, **LR 85%+**, hit 88.3 / 90.1 / 93.8 / 93.3 / 86.8% blind (1,447 rows, ~22 a week). The 85-89 slice alone dropped to 82.7% in 2026.

## Shuffle test
With the training labels shuffled 20 times, blind AUC averaged 0.491 (max 0.609). The same-size top slice hit 72.3% (max 86.1%), against a 74.6% base. The real model's AUC was 0.715, and its 90+ band hit 92.7%.

## 2026 book side check (one season, weeks 1-5 only)
368 starters matched a BettingPros consensus line, converted to a no-vig Poisson 1+ chance. Their base rate was 78.0%, because props are posted mostly for the better QBs.
- Brier score: book 0.1736, model 0.1649.
- Book 85%+ alone: 85.4% (96).
- The NFL combo, model 80+ AND book 85+: 88.5% (87, 14.5/wk).
- Model 90+ AND book 85+: 97.1% (34, 6.8/wk).

This is a single short season, so it is not a validated rule.

## What didn't work or added nothing
- **GB vs LR:** GB was no better. Its 90+ band hit 89.4 / 88.9 / 96.3 / 95.3 / 90.4%, with lower AUC every season.
- **An ITT filter on top of the model:** it changed the hit rate by less than 1 point, because ITT is already in the model.
- **Market alone (ITT from ESPN spread and total):** it was weaker in 2022. ITT 36+ hit 86.3 / 91.4 / 95.3 / 93.8 / 92.1%, and ITT 33+ hit 87.3-92.4%.
- **The QB's past 1+ rate:** it carried no weight once TD/game was in.
- **2022** was the weakest blind season in every rule tried. It is the only season under 89% for the 90+ rule.

## Files
- `fetch.py`: ESPN weeks, summaries, odds, FBS lists, and BettingPros 441.
- `build.py`: builds `games.parquet` and `data.parquet`.
- `model.py`: writes `model.pkl`, `preds.parquet` and `results.txt`.
- `week.py <season> <week>`: refreshes the season's games, takes each team's QB from its last FBS game, reads ESPN's line, and marks LR 90%+. Starters with no posted line can't qualify. This weekend is ESPN **week 6** of 2026.
