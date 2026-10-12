"""NFL moneyline read (v1, Oct 7, 2026) -> data/models/nfl_ml.json.

The model is the one in research/nfl_ml/search.py: LogisticRegression(C=0.3,
max_iter=5000) on home-minus-away differences of the pre-game team profile
(build.py), the backup flag (boxes.py) and the starter's last-16 EPA per
dropback (qb.py), plus rest and division; trained on 2016-21 only.

It is refit here on the ORIGINAL training table, the session's ml/XS.pkl
(= ml/XQ.pkl as of Oct 8, 2026 plus four schedule columns that are not used),
so the coefficients are the shipped ones, and checked against the logged blind
numbers: 76% (88) 2022-23, 80% (118) 2024-25, 90% (10) 2026 Wk1-4, 78.7% of
216 blind, top coefficient qe 0.7733.

The "won before" table is frozen from the same table: blind games 2022 to
2026 Wk4 with a closing moneyline, banded by our model on the pick and the
book's no-vig % on the pick (the bands of Oct 7, 2026).

Usage: python3 train_ml.py <path to XS.pkl> [<path to model_sos.pkl>]
"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "data", "models", "nfl_ml.json")

X = pd.read_pickle(sys.argv[1])
# the shipped column order (model.pkl is gone; model_sos.pkl was built as
# model.pkl's columns + sos/adjpd, so dropping those two gives it back)
COLS = ['o_epa', 'o_sr', 'o_pepa', 'o_repa', 'o_to', 'o_sack', 'd_epa', 'd_sr', 'd_pepa', 'd_repa', 'd_to', 'd_sack',
        'pf', 'pa', 'win', 'g', 'l3_win', 'l3_pd', 'backup', 'qe', 'cp', 'qn', 'rest', 'div']
if len(sys.argv) > 2:
    _, c2 = pickle.load(open(sys.argv[2], "rb"))
    assert [c for c in c2 if c not in ("sos", "adjpd")] == COLS, c2

F = [c for c in COLS if c not in ("rest", "div")]
Z = pd.DataFrame({c: X["h_" + c].astype(float) - X["a_" + c].astype(float) for c in F})
Z["rest"] = X.rest
Z["div"] = X["div"]
Z = Z[COLS].fillna(0)
y = X.home_won.values
tr = (X.season <= 2021).values
m = LogisticRegression(C=0.3, max_iter=5000).fit(Z[tr], y[tr])
p = m.predict_proba(Z)[:, 1]
c = np.maximum(p, 1 - p)
pw = np.where(p >= 0.5, y, 1 - y)

# --- the logged numbers
res = {}
for lab, a, b in (("2022-23", 2022, 2023), ("2024-25", 2024, 2025), ("2026", 2026, 2026)):
    s = (c >= 0.75) & X.season.between(a, b).values
    res[lab] = (round(100 * pw[s].mean()), int(s.sum()))
bl = (~tr) & (c >= 0.75)
print("blind 75%+:", res, "all blind %.1f%% (%d)" % (100 * pw[bl].mean(), bl.sum()))
top = sorted(zip(COLS, m.coef_[0]), key=lambda t: -abs(t[1]))[:8]
print("top coefs:", [(k, round(v, 4)) for k, v in top])
assert res == {"2022-23": (76, 88), "2024-25": (80, 118), "2026": (90, 10)}, res
assert (round(1000 * pw[bl].mean()), int(bl.sum())) == (787, 216)
assert abs(dict(top)["qe"] - 0.7733410813655579) < 1e-9 and abs(dict(top)["o_sr"] - 0.4501062043050928) < 1e-9

# --- won before: model band x book band on the picked side, blind seasons
ip = lambda o: np.where(o < 0, -o / (-o + 100), 100 / (o + 100))
hm, am = ip(X.home_ml.astype(float)), ip(X.away_ml.astype(float))
mk = hm / (hm + am)
blk = (X.season >= 2022).values & X.home_ml.notna().values
mp = np.where(p >= 0.5, mk, 1 - mk)
MB = [(.5, .6), (.6, .65), (.65, .7), (.7, .75), (.75, .8), (.8, 1.01)]
OB = [(0, .5), (.5, .6), (.6, .7), (.7, .75), (.75, 1.01)]
table = []
for a in MB:
    for o in OB:
        s = blk & (c >= a[0]) & (c < a[1]) & (mp >= o[0]) & (mp < o[1])
        table.append({"model": list(a), "book": list(o), "won": round(100 * pw[s].mean()) if s.sum() else None, "n": int(s.sum())})
cell = lambda mv, ov: next((t["won"], t["n"]) for t in table if t["model"][0] <= mv < t["model"][1] and t["book"][0] <= ov < t["book"][1])
# the Oct 8 Week 5 cells, as logged (model, book on the pick) -> (won, n)
for mv, ov, w, n in ((78, 75, 84, 50), (85, 79, 83, 81), (66, 73, 75, 32), (51, 77, 75, 12), (62, 62, 67, 78), (62, 55, 66, 61),
                     (57, 69, 61, 119), (56, 57, 58, 153), (65, 54, 52, 25), (71, 42, 50, 10), (50, 47, 40, 149), (61, 39, 30, 23)):
    assert cell(mv / 100, ov / 100) == (w, n), (mv, ov, cell(mv / 100, ov / 100), w, n)
# SF @ SEA (model 71 on SF, book 58 on SEA) was shown as "56% on 45 games"
# instead of its own cell (50, 10), after Jose objected to a PASS on Oct 7:
# model 70-75 with the book under 60 on the pick, every season 2016-26
dis = X.home_ml.notna().values & (c >= .70) & (c < .75) & (mp < 0.6)
print("model 70-75, book under 60 on the pick, 2016-26: %.0f%% (%d)" % (100 * pw[dis].mean(), dis.sum()))
assert (round(100 * pw[dis].mean()), int(dis.sum())) == (56, 45)

# --- export
X26 = Z.values
z = X26 @ m.coef_[0] + m.intercept_[0]
pj = 1 / (1 + np.exp(-z))
assert np.abs(pj - p).max() < 1e-9
json.dump({
    "what": "NFL moneyline read v1: logistic regression on home-minus-away pre-game differences, trained 2016-21, no odds",
    "trained": "2016-2021 regular season, sklearn LogisticRegression(C=0.3, max_iter=5000), refit on the original table (ml/XS.pkl)",
    "blind": {"2022-23": res["2022-23"], "2024-25": res["2024-25"], "2026 wk1-4": res["2026"], "all": [78.7, 216]},
    "cols": COLS, "coef": [float(v) for v in m.coef_[0]], "intercept": float(m.intercept_[0]),
    "fill": 0.0,
    "won_before": table,
    "disagree_70_75": [round(100 * pw[dis].mean()), int(dis.sum())],
}, open(OUT, "w"), indent=1)
print("wrote", os.path.normpath(OUT))
