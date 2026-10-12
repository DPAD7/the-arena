import os, pickle, sys, pandas as pd
import build, week
from model import prep
D = os.path.dirname(os.path.abspath(__file__))
g = build.team_games()
U = week.upcoming(2026, 6); U["date"] = pd.to_datetime(U.date, utc=True)
last = g.sort_values("date").groupby("team").tail(1).set_index("team")
U["qb"] = U.team.map(last.qb); U["qb_name"] = U.team.map(last.qb_name); U = U[U.qb.notna()]
for c in ("att", "ptd", "team_ptd", "pts", "opp_pts"): U[c] = 0
U["upcoming"] = True; g["upcoming"] = False
X = build.features(pd.concat([g, U], ignore_index=True).sort_values(["date", "eid", "team"]))
X = prep(X[X.upcoming])
M = pickle.load(open(os.path.join(D, "model.pkl"), "rb"))
X["p2"] = (M["lr"].predict_proba(X[M["feats"]])[:, 1] * 100).round(1)
X["et"] = X.date.dt.tz_convert("US/Eastern")
t = X[(X.p2 >= 90) & (X.has_line == 1)].sort_values("p2", ascending=False)
print(t[["qb_name","team_abbr","opp_abbr","ha","spread","total","et","p2"]].to_string(index=False))

