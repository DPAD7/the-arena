"""The blind test behind build/ufc_reads.py, from the repo's own tables: for each
year 2019-2026, fit on every year before (men, decided, the audit's sample), score
that year, and count how often the model's side won by confidence tier. Women's
bouts are scored by the same men-fit model and counted apart. Needs scikit-learn.

    python3 research/ufc_reads/walk_forward.py   (-> walk_forward.txt)
"""
import os, sys, warnings
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build"))
import ufc_reads as U
X = U.load_hist()["bouts"].reset_index(drop=True)
FE = U.feat(X); FC = list(FE.columns); y = X.a_won.values
dec = X.winner.isin(["red", "blue"]).values; wom = U.women(X); samp = X.train.astype(bool).values
P = np.full(len(X), np.nan)
for yr in range(2019, 2027):
    tr = (X.yr < yr).values & ~wom & dec & samp; te = (X.yr == yr).values
    F = FE.copy()
    for c in FC: F[c + "_na"] = F[c].isna().astype(int); F[c] = F[c].fillna(0)
    F = F.loc[:, F[tr].std() > 0]; Z = ((F - F[tr].mean()) / F[tr].std()).values
    m = HistGradientBoostingClassifier(**U.GBM).fit(np.vstack([Z[tr], -Z[tr]]), np.concatenate([y[tr], 1 - y[tr]]))
    P[te] = ((m.predict_proba(Z)[:, 1] + 1 - m.predict_proba(-Z)[:, 1]) / 2)[te]
conf = np.maximum(P, 1 - P); w = np.where(P > 0.5, y, 1 - y); card = X.date.dt.strftime("%Y-%m-%d")
for lab, grp in (("men (the audit's sample)", ~wom & samp & dec), ("women, men-fit model", wom & dec)):
    print(lab)
    for per, (a, b) in (("2019-23", (2019, 2023)), ("2024-26", (2024, 2026))):
        m = grp & X.yr.between(a, b).values; cards = card[m].nunique()
        for lo, hi, t in ((0.75, 1.01, "75%+  "), (0.70, 0.75, "70-74%"), (0.70, 1.01, "70%+  ")):
            k = m & (conf >= lo) & (conf < hi)
            print("  %s %s  %.1f%%  (%d, %.2f a card)" % (per, t, 100 * w[k].mean(), k.sum(), k.sum() / cards))
