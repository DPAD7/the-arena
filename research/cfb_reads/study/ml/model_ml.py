"""Fit the CFB moneyline read on 2016-2021, read 2022-2026 blind.

  python3 ml/model_ml.py   -> ml/model.pkl, ml/preds.parquet, ml/results.txt
"""
import json, os, pickle, sys
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.metrics import roc_auc_score, brier_score_loss

M = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, M)
from build_ml import DIFF
FEATS = ["home"] + ["d_" + k for k in DIFF]
NOTBOOK = {"Opening", "teamrankings", "numberfire", "accuscore", "consensus"}

def imp(ml):
    ml = float(ml); return 100 / (ml + 100) if ml > 0 else -ml / (-ml + 100)

def book(eid):
    """Median no-vig home win chance across books; None when no moneyline was posted."""
    fn = os.path.join(M, "mlodds", f"{eid}.json")
    if not os.path.exists(fn): return np.nan
    ps, cons = [], []
    for o in json.load(open(fn)):
        try: h, a = imp(o["hml"]), imp(o["aml"])
        except Exception: continue
        p = h / (h + a)
        if "live" in (o["p"] or "").lower(): continue  # in-game odds, captured after kickoff
        (cons if o["p"] in NOTBOOK else ps).append(p)
    v = ps or [p for p in cons]
    return float(np.median(v)) if v else np.nan

def fit(T, y=None):
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))
    m.fit(T[FEATS].fillna(0), T.y if y is None else y); return m

def hit(df, pcol="p"):
    pk = (df[pcol] >= 0.5).astype(int); return (pk == df.y).mean()

if __name__ == "__main__":
    G = pd.read_parquet(os.path.join(M, "games.parquet"))
    G = G[G.stype == 2].copy()  # regular season incl. conference title games; bowls only feed history
    G["book"] = [book(e) if s >= 2022 else np.nan for e, s in zip(G.eid, G.season)]
    TR, TE = G[G.season <= 2021], G[G.season >= 2022].copy()
    m = fit(TR); TE["p"] = m.predict_proba(TE[FEATS].fillna(0))[:, 1]
    # leave-one-season-out on the training years (for choosing the tier without touching 2022+)
    loso = []
    for s in range(2016, 2022):
        mm = fit(TR[TR.season != s]); t = TR[TR.season == s].copy(); t["p"] = mm.predict_proba(t[FEATS].fillna(0))[:, 1]; loso.append(t)
    LO = pd.concat(loso)
    pickle.dump(dict(model=m, feats=FEATS), open(os.path.join(M, "model.pkl"), "wb"))
    TE.to_parquet(os.path.join(M, "preds.parquet")); LO.to_parquet(os.path.join(M, "loso.parquet"))
    coef = dict(zip(FEATS, m[-1].coef_[0]))
    print("coefs (standardized):", {k: round(v, 3) for k, v in sorted(coef.items(), key=lambda kv: -abs(kv[1]))})
    for nm, D_ in (("LOSO 2016-21", LO), ("blind", TE)):
        print(nm, {s: (round(roc_auc_score(d.y, d.p), 3), round(hit(d), 3)) for s, d in D_.groupby("season")})
