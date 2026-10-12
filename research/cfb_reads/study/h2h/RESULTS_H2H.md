# CFB QB head-to-head passing yards: blind study

**Question:** in an FBS vs FBS game, which starting QB throws for more passing yards?
**Scope:** 2016 through Oct 8, 2026. The starter is each team's leading passer by attempts, with 10+ attempts. Ties are dropped. That leaves 7,219 games. Another 335 games (4.4%) were dropped because a starter threw fewer than 10 passes, mostly from injuries and benchings, so the hit rates below don't include those games.
**Split:** cutoffs and the model were locked on 2016-2021 (3,970 games). Each later season was then read blind: 2022 (704), 2023 (729), 2024 (768), 2025 (780) and 2026 weeks 1-6 (268).
All tables are in `results.txt` and `rules.csv`.

## Features
All features are pre-game and season-to-date. When a team or QB has fewer than 3 games in the season, the prior season's games are pooled in. Each feature is the gap between the two sides.
- **QB:** yards/game, attempts/game, yards/attempt, completion %, yards/game over his last 3 games.
- **Team:** pass rate, points/game, plays/game, rush yards/game, yards/carry.
- **Defense faced:** pass yards allowed/game, yards/attempt allowed, leading-passer yards allowed/game, pass attempts faced/game, rush yards allowed/game, points allowed/game.
- **Matchup projection:** QB yards/game scaled by the defense's yards allowed.
- **Price:** ESPN closing spread, total and implied team totals.
- **Other:** home/neutral, conference game, early season.

**Sacks aren't available.** College scoring counts sack yards as rushing, so ESPN's college boxscores show no sacks (gross passing yards equal net in 99.9% of team-games). Sacks were dropped.

## Baselines (blind)
| rule | 2016-21 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|
| spread favorite's QB | 60.5% | 58.2% | 62.1% | 61.2% | 63.4% | 61.9% |
| higher QB yds/game | 62.8% | 61.6% | 61.7% | 64.2% | 63.1% | 63.3% |
| home QB | 53.2% | 52.8% | 52.4% | 52.3% | 51.7% | 58.6% |

## Logistic model on the gaps (fit on 2016-21)
The biggest weights:
- team rush yards/game gap (negative)
- matchup projection
- implied team total and spread
- yards/carry
- points/game
- QB last-3 yards/game

| tier (cut locked on 2016-21) | 2016-21 | 2022 | 2023 | 2024 | 2025 | 2026 | all blind | per week |
|---|---|---|---|---|---|---|---|---|
| all games | 66.2% | 62.8% | 65.2% | 66.1% | 66.3% | 70.1% | 65.6% (3,249) | ~48 |
| top 30% (winner chance 72.9%+) | 83.0% | 73.5% | 80.7% | 84.3% | 81.0% | 77.0% | 80.0% (958) | ~14 |
| top 20% (77.4%+) | 85.1% | 77.5% | 81.5% | 87.8% | 85.4% | 81.2% | 83.2% (602) | ~8.5 |
| **top 10% (83.2%+)** | 86.9% | **90.2%** | **83.6%** | **93.5%** | **92.9%** | **95.8%** | **90.7% (258)** | **~3.8** |

## Edge score (no price; 18 stats, +1 per edge, cutoffs locked on 2016-21)
| margin | 2016-21 | 2022 | 2023 | 2024 | 2025 | 2026 | per week |
|---|---|---|---|---|---|---|---|
| 3+ | 69.5% | 63.7% | 66.0% | 70.6% | 67.1% | 66.0% | ~34 |
| 4+ | 71.4% | 63.6% | 70.1% | 72.2% | 68.7% | 67.7% | ~29 |
| 5+ | 72.6% | 65.6% | 72.2% | 74.3% | 70.2% | 69.6% | ~24 |
| 6+ | 74.6% | 66.4% | 71.5% | 75.6% | 73.1% | 72.3% | ~19 |
| 8+ | 77.9% | 71.9% | 76.6% | 82.6% | 74.2% | 72.7% | ~12 |

The edge score is weaker than the model at every volume. Without price, 70%+ in every season only shows up at margin 7+, which hit 70.0-77.8% at ~15 a week.

## Single and pair rules
I tested 4,850 rules: 100 single rules and 4,750 pairs, with thresholds at the 50th-90th percentile of each gap.
- **3,396** hit 68%+ on 2016-21 (n≥40).
- **1,801** of those also held 68%+ blind in each of 2022, 2023, 2024 and 2025.
- **Shuffle test** (blind labels permuted within each season, 20 runs): 0.6 rules passed by luck on average, with a maximum of 4. The pass count is real signal, but the rules overlap heavily (most are versions of "the QB with more yards/game, more points and a bigger spread"), so 1,801 is not 1,801 independent findings.
- **Best volume rule at 70%+ in every blind season:** QB yds/game gap in the top 50% (61+ yards) AND last-3 yds/game gap in the top 40%. It hit 70.4 / 71.6 / 75.7 / 76.9 / 73.4% at ~14 a week.
- **A plain spread of 19+ points, pick the favorite's QB:** 71.9 / 70.0 / 82.1 / 83.3 / 76.7%, ~10 a week.

## The rule: model winner chance in the top 10% (83.2%+)
| season | hit | games | per week (min-max) |
|---|---|---|---|
| 2022 | 90.2% | 61 | 4.1 (1-9) |
| 2023 | 83.6% | 55 | 3.7 (1-8) |
| 2024 | 93.5% | 62 | 3.9 (1-7) |
| 2025 | 92.9% | 56 | 3.5 (1-8) |
| 2026 | 95.8% | 24 | 4.0 (2-7) |
| all blind | 90.7% | 258 | ~3.8 |

**What the flagged games look like:**
- 96% of flagged picks are the spread favorite's QB, and the median spread is 25.75 points.
- Half come from early-season games (either team fewer than 3 games in), which hit 96.9% (128). The rest hit 84.6% (130).

**Wider tiers:**
- Top 20% (77.4%+) hit 77.5-87.8% at ~8.5 a week.
- Winner chance 80%+ hit 82.1 / 83.2 / 92.9 / 89.4 / 90.9% at ~6 a week.

## BettingPros
- There is **no college H2H market**. The NCAAF market list has passing yards (440), passing TDs (441) and other player props, with no player matchups.
- Market 440 has lines **only for 2026**. There are none for 2022-2025.
- **2026 side check (141 games where both QBs had a line):**
  - The higher pass-yards line won 66.7%, and 78.5% when the lines were 25+ yards apart (93 games).
  - The model's pick won 70.2% in the same games.
  - The top-10% picks went 9-0, and every one sided with the higher line.
- This is a single season, so it is reference only (`bp_side.py`, `bp_side.txt`).

## Caveats
- The test labels use the QB who actually started. `week_h2h.py` uses each team's last FBS starter, so a starter change before kickoff isn't seen.
- A starter who is hurt or benched early isn't counted (the 335 dropped games).
- Games with no ESPN line can't be flagged.

## Files
- `build_h2h.py`: builds `tg.parquet` (team-games) and `games.parquet` (game gaps and label).
- `study.py`: writes `results.txt`, `rules.csv`, `model.pkl`, `edge.pkl` and `scored.parquet`.
- `week_h2h.py <season> <week>`: refreshes the data and writes `week_<season>_<week>.csv`, marking TOP10 (the rule) and TOP20.
- `bp_side.py`: the 2026 BettingPros side check.
