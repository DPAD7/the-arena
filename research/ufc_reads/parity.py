"""Do build/ufc_reads.py's point-in-time features reproduce the audit's D.pkl?
Recomputes the Oct 3 and Oct 10, 2026 cards plus 400 random bouts from the stored
tables and compares every side feature the model reads."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build"))
import ufc_reads as U
h = U.load_hist()
fe = U.Feats(h)
B = h["bouts"]
pick = B[B.date.isin([pd.Timestamp("2026-10-03"), pd.Timestamp("2026-10-10")])].index.tolist()
pick += B.sample(400, random_state=1).index.tolist()
F = h["fights"].set_index("fight_url")
R = U.bout_rows(h, fe, F.loc[B.fight_url[pick]].reset_index())
old = B.loc[pick].reset_index(drop=True)
bad = {}
for c in [c for c in U.BCOLS if c[:2] in ("a_", "b_") and c not in ("a_url", "b_url", "a_won")]:
    x, y = pd.to_numeric(old[c], errors="coerce").values.astype(float), pd.to_numeric(R[c], errors="coerce").values.astype(float)
    same = (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-12)
    if (~same).sum():
        bad[c] = int((~same).sum())
print("rows", len(R), "| mismatched side features:", bad or "none")
Z0, _ = U.zmat(U.load_model(), old) if os.path.exists(U.MODEL) else (None, None)
