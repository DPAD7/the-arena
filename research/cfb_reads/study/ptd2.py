"""2+ passing TD: same features, same 2016-21 fit, blind 2022-26."""
import os, pickle, numpy as np, pandas as pd
from model import prep, make_lr, FEATS, TRAIN, BLIND
D = os.path.dirname(os.path.abspath(__file__))
X = prep(pd.read_parquet(os.path.join(D, "data.parquet")))
X["y2"] = (X.ptd >= 2).astype(int)
tr, te = X[X.season.isin(TRAIN)], X[X.season.isin(BLIND)].copy()
print("base 2+:", {s: round(g.y2.mean()*100,1) for s, g in X.groupby("season")})
# out-of-fold on training years to pick a cut
oof = tr.copy()
for s in TRAIN:
    m = make_lr().fit(tr[tr.season != s][FEATS], tr[tr.season != s].y2)
    oof.loc[tr.season == s, "p"] = m.predict_proba(tr[tr.season == s][FEATS])[:, 1]
for c in (0.6, 0.65, 0.7, 0.75, 0.8):
    s = oof[(oof.p >= c) & (oof.has_line == 1)]
    print(f"train OOF {c:.2f}+: {len(s)} hit {s.y2.mean():.1%}")
lr = make_lr().fit(tr[FEATS], tr.y2)
te["p"] = lr.predict_proba(te[FEATS])[:, 1]
for c in (0.6, 0.65, 0.7, 0.75, 0.8):
    out = []
    for yr in BLIND:
        s = te[(te.season == yr) & (te.p >= c) & (te.has_line == 1)]
        out.append(f"{yr} {int(s.y2.sum())}-{len(s)-int(s.y2.sum())} {s.y2.mean():.0%}" if len(s) else f"{yr} 0")
    s = te[(te.p >= c) & (te.has_line == 1)]
    wk = s.groupby(["season","stype","week"]).size().mean()
    print(f"blind {c:.2f}+: " + " | ".join(out) + f" | all {s.y2.mean():.1%} of {len(s)}, {wk:.1f}/wk")
pickle.dump(dict(lr=lr, feats=FEATS), open(os.path.join(D, "model2.pkl"), "wb"))
