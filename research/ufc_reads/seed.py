"""One-time seed of data/ufc_hist/ from the Oct 12, 2026 audit rebuild (UFC Stats
recrawl 2010 -> Oct 10, 2026, scratchpad ufc_audit/: fights.csv, fighters.csv,
history.csv, rounds.csv, events.json, D.pkl). The bouts table is D.pkl's own
point-in-time rows, so the production model is fit on exactly the audited
sample; build/ufc_reads.py appends to it from then on.

    python3 research/ufc_reads/seed.py <audit dir>
"""
import json, os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build"))
import ufc_reads as U

A = sys.argv[1].rstrip("/") + "/"
os.makedirs(U.HIST, exist_ok=True)
F = U._norm_fights(pd.read_csv(A + "fights.csv"))
H0 = pd.read_csv(A + "history.csv")
H0["dt"] = pd.to_datetime(H0.date)
S1 = H0.sort_values("dt")                                  # build.py: H.sort_values('date')
H0.loc[S1.index, "o1"] = np.arange(len(S1))
S2 = S1[S1.result.isin(["W", "L", "D"])].copy().sort_values("dt")   # then Hh.sort_values('date')
H0["o2"] = np.nan
H0.loc[S2.index, "o2"] = np.arange(len(S2))
Hh = H0.reindex(columns=U.HCOLS)
FT = pd.read_csv(A + "fighters.csv").reindex(columns=U.TCOLS)
R = pd.read_csv(A + "rounds.csv").reindex(columns=U.RCOLS)
X = pd.read_pickle(A + "D.pkl")
# the audit's sample: decided bouts with both closing prices (97-99% a year). Prices were
# pulled on Oct 7, 2026, so a bout after that is in the sample when decided, the same
# rule build/ufc_reads.py uses for every bout it appends.
X["train"] = (((X.oa.notna() & X.ob.notna() & (X.oa != X.ob)) | (X.date > "2026-10-07"))
              & X.winner.isin(["red", "blue"])).values
B = X.reindex(columns=U.BCOLS)
for c in B.columns:
    if B[c].dtype == object and c not in ("event", "wc", "a", "b", "a_url", "b_url", "winner", "method", "fight_url"):
        B[c] = pd.to_numeric(B[c], errors="coerce")
h = dict(fights=F, history=Hh, fighters=FT, rounds=R, bouts=B, pro_map={},
         seen=[e[0] for e in json.load(open(A + "events.json"))])
U.save_hist(h)
for k in ("fights", "history", "fighters", "rounds", "bouts"):
    print(k, len(h[k]), "%.2f MB" % (os.path.getsize(os.path.join(U.HIST, k + ".parquet")) / 1e6))
