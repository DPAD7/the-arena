"""Run the ORIGINAL research week scripts' scoring paths (verbatim bodies) for one week,
   at full precision, so build/cfb_reads.py can be compared against them.

  python3 research/cfb_reads/compare_orig_week.py <folder with the study scripts + their cache> 2026 7 <out prefix>
  (needs scikit-learn and the 4 GB ESPN cache the study scripts build; writes <out>_ptd/_h2h/_ml.parquet)"""
import os, pickle, sys, json
import numpy as np, pandas as pd
S = sys.argv.pop(1)
sys.path[:0] = [S, S + "/h2h", S + "/ml"]
os.chdir(S)
import build, fetch, week, boardqb
from model import prep
season, wk = int(sys.argv[1]), sys.argv[2]
OUT = sys.argv[3]
# ---- 1+/2+ (week.main body)
ids = fetch.weeks(season, refresh=True)
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(6) as ex:
    list(ex.map(fetch.summary, ids)); list(ex.map(fetch.odds, ids))
g = build.team_games()
U0 = week.upcoming(season, wk)
U = U0.copy()
U["date"] = pd.to_datetime(U.date, utc=True)
last = g.sort_values("date").groupby("team").tail(1).set_index("team")
U["qb"] = U.team.map(last.qb); U["qb_name"] = U.team.map(last.qb_name)
_B = boardqb.board()
for _i, _r in U.iterrows():
    _h = _B.get((str(_r.eid), _r.team_abbr))
    if _h and _h[0] and str(_h[0]) != str(_r.qb):
        U.at[_i, "qb"], U.at[_i, "qb_name"] = type(_r.qb)(_h[0]) if _r.qb == _r.qb else _h[0], _h[1]
U = U[U.qb.notna()]
for c in ("att", "ptd", "team_ptd", "pts", "opp_pts"):
    U[c] = 0
U["upcoming"] = True
g["upcoming"] = False
X = build.features(pd.concat([g, U], ignore_index=True).sort_values(["date", "eid", "team"]))
X = prep(X[X.upcoming])
M = pickle.load(open("model.pkl", "rb")); M2 = pickle.load(open("model2.pkl", "rb"))
X["p1"] = M["lr"].predict_proba(X[M["feats"]])[:, 1]
X["p2"] = M2["lr"].predict_proba(X[M2["feats"]])[:, 1]
X[["eid", "qb", "qb_name", "team_abbr", "spread", "total", "has_line", "p1", "p2"]].to_parquet(OUT + "_ptd.parquet")
print("ptd", len(X), flush=True)
# ---- H2H (week_h2h.main body)
import week_h2h, build_h2h as B
tg = week_h2h.refresh_tg(season)
U = week.upcoming(season, wk)
U["date"] = pd.to_datetime(U.date, utc=True)
last = tg.sort_values("date").groupby("team").tail(1).set_index("team")
U["qb"] = U.team.map(last.qb); U["qb_name"] = U.team.map(last.qb_name)
for _i, _r in U.iterrows():
    _h = _B.get((str(_r.eid), _r.team_abbr))
    if _h and _h[0] and str(_h[0]) != str(_r.qb):
        U.at[_i, "qb"], U.at[_i, "qb_name"] = type(_r.qb)(_h[0]) if _r.qb == _r.qb else _h[0], _h[1]
U["is_home"] = U.ha.eq("H") | (U.ha.eq("N") & ~U.duplicated("eid"))
U = U[U.qb.notna()]
U = U[U.groupby("eid").eid.transform("size") == 2]
for c in ["q_att", "q_yds", "q_cmp", "t_patt", "t_pyds", "t_net", "t_ratt", "t_ryds", "pts", "opp_pts", "sackyds"]:
    U[c] = 0
U["upcoming"] = True
tg = tg.copy(); tg["upcoming"] = False
X = B.features(pd.concat([tg, U], ignore_index=True).sort_values(["date", "eid", "team"]).reset_index(drop=True))
G = B.pair(X[X.upcoming.astype(bool)])
G["home_site"] = 1 - G.neutral
MH = pickle.load(open("h2h/model.pkl", "rb"))
p = MH["lr"].predict_proba(MH["sc"].transform(G[MH["feats"]].fillna(0).values))[:, 1]
G["p_home"] = p; G["chance"] = np.maximum(p, 1 - p)
G["tier"] = np.where(G.chance - 0.5 >= MH["cuts"][0.10], "TOP10", "")
G.loc[G.h_spread.isna(), "tier"] = "no line"
G[["eid", "h_qb", "a_qb", "p_home", "chance", "tier", "h_spread"]].to_parquet(OUT + "_h2h.parquet")
print("h2h", len(G), flush=True)
# ---- ML (week_ml.main body, scoring part)
import build_ml
d = fetch.get(f"{fetch.SB}?groups=80&seasontype=2&dates={season}&week={wk}&limit=300") or {}
fbs = set(json.load(open(os.path.join(S, "fbs", f"{season}.json"))))
g = build_ml.team_games(); g = g[g.season >= season - 3]
last = g.sort_values("date").groupby("team").tail(1).set_index("team")
rows = []
for e in d.get("events", []):
    c = e["competitions"][0]; cs = c["competitors"]
    if len(cs) != 2 or not all(x["team"]["id"] in fbs for x in cs): continue
    if c["status"]["type"].get("completed"): continue
    home = next(x for x in cs if x["homeAway"] == "home")
    for t in cs:
        o = [x for x in cs if x is not t][0]; tid = t["team"]["id"]
        if tid not in last.index: continue
        q = last.loc[tid]
        bq = _B.get((str(e["id"]), t["team"]["abbreviation"]))
        if bq and str(bq[0]) != str(q.qb):
            q = q.copy(); q["qb"], q["qb_name"] = str(bq[0]), bq[1]
        rows.append(dict(eid=e["id"], date=c["date"], season=season, stype=2, week=int(wk), team=tid, team_abbr=t["team"]["abbreviation"],
                         opp=o["team"]["id"], opp_abbr=o["team"]["abbreviation"], is_home=t is home, neutral=bool(c.get("neutralSite")),
                         conf=bool(c.get("conferenceCompetition")), rank=(t.get("curatedRank") or {}).get("current", 99) or 99,
                         qb=q.qb, qb_name=q.qb_name, upcoming=True))
U = pd.DataFrame(rows); U["date"] = pd.to_datetime(U.date, utc=True)
hist = g[~g.eid.isin(U.eid)]
X = build_ml.features(pd.concat([hist, U], ignore_index=True))
G = build_ml.pair(X[X.upcoming.astype(bool)])
mdl = pickle.load(open("ml/model.pkl", "rb"))
G["p"] = mdl["model"].predict_proba(G[mdl["feats"]].fillna(0))[:, 1]
G[["eid", "h_team", "a_team", "h_qb", "a_qb", "p"]].to_parquet(OUT + "_ml.parquet")
print("ml", len(G), flush=True)
