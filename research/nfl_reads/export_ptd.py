"""NFL 1+ passing TD model (Oct 7, 2026) -> data/models/nfl_ptd1.json.

The model is the session's ptd/model.pkl, (LogisticRegression(C=0.3), F, med):
trained 2016-21 on every starting QB game (ptd/build.py, kept here as
build_ptd.py), missing values filled with the 2016-21 medians.

This copies its coefficients into plain JSON and checks that evaluating the
JSON with numpy gives the pickle's probabilities to 1e-9 on random inputs and
on the rebuilt table. With a rebuilt table (build_ptd.py) it also refits the
model from scratch and reports how close the refit is, and the blind hit
rates by band (logged Oct 7: 80+ hit 84-86%, 75-79 hit 75%, under 75 63-72%).

Usage: python3 export_ptd.py <ptd/model.pkl> [<rebuilt X.pkl>]
"""
import json
import os
import pickle
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "..", "data", "models", "nfl_ptd1.json")

lr, F, med = pickle.load(open(sys.argv[1], "rb"))
coef, b0 = lr.coef_[0], lr.intercept_[0]
fill = [float(med[f]) for f in F]


def js(Z):
    return 1 / (1 + np.exp(-(Z @ coef + b0)))


rng = np.random.default_rng(0)
R = pd.DataFrame(rng.normal(size=(500, len(F))) * np.array(fill).clip(0.5) + np.array(fill), columns=F)
d = np.abs(js(R.values) - lr.predict_proba(R)[:, 1]).max()
print("random inputs: max |json - pickle| = %.2e" % d)
assert d < 1e-9

if len(sys.argv) > 2:
    from sklearn.linear_model import LogisticRegression
    X = pd.read_pickle(sys.argv[2])
    X["dome"] = X.roof.isin(["dome", "closed"]).astype(int)
    X["windy"] = (X.wind.fillna(0) >= 15).astype(int)
    Z = X[F].astype(float)
    Z = Z.fillna(med)
    p = lr.predict_proba(Z)[:, 1]
    d = np.abs(js(Z.values) - p).max()
    print("rebuilt table: max |json - pickle| = %.2e" % d)
    assert d < 1e-9
    y = X.hit.values
    for lab, s in (("2016-21", X.season <= 2021), ("2022-26 blind", X.season >= 2022)):
        s = s.values
        print(lab, " | ".join("%d-%d: %.0f%% (%d)" % (100 * lo, 100 * hi, 100 * y[s & (p >= lo) & (p < hi)].mean(), (s & (p >= lo) & (p < hi)).sum())
                              for lo, hi in ((0, .7), (.7, .75), (.75, .8), (.8, .85), (.85, 1))))
    tr = (X.season <= 2021).values
    med2 = X[F].astype(float)[tr].median()
    m2 = LogisticRegression(C=0.3, max_iter=5000).fit(X[F].astype(float).fillna(med2)[tr], y[tr])
    print("refit on the rebuilt table vs the pickle: max coef diff %.4f, max p diff %.4f, train rows %d" % (
        np.abs(m2.coef_[0] - coef).max(), np.abs(m2.predict_proba(X[F].astype(float).fillna(med2))[:, 1] - p).max(), tr.sum()))

json.dump({
    "what": "NFL 1+ passing TD model: logistic regression on pre-game QB/team/defense features, trained 2016-21, no odds",
    "trained": "2016-2021 regular season starting QB games, sklearn LogisticRegression(C=0.3, max_iter=5000); copied from the session's ptd/model.pkl",
    "blind": "model 80+ hit 84-86%, 75-79 hit 75%, under 75 hit 63-72% (2022-26)",
    "cols": list(F), "coef": [float(v) for v in coef], "intercept": float(b0), "fill": fill,
}, open(OUT, "w"), indent=1)
print("wrote", os.path.normpath(OUT))
