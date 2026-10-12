"""Checks build/nfl_reads.py against the research.

  1. Moneyline features: every 2025 and 2026 Wk1-4 game in the original
     training table (the session's ml/XS.pkl) rebuilt with the job's own code
     from today's nflverse files; feature and probability differences.
  2. Week 5 replay: the Oct 8 reads (git) against the job's code run "as of"
     Week 5 with the depth chart of that evening (git), moneyline and 1+ TD.

Usage: python3 check.py <XS.pkl> <folder with pbp_<year>.parquet, games.csv>
"""
import json
import os
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "build"))
sys.argv, args = sys.argv[:1], sys.argv[1:]
import nfl_reads as N  # noqa: E402

XS, NFV = args
G = pd.read_csv(os.path.join(NFV, "games.csv"), low_memory=False)
parts = [N.aggregate(pd.read_parquet(os.path.join(NFV, "pbp_%d.parquet" % y), columns=N.PBP_COLS)) for y in range(2016, 2027)]
H = {k: pd.concat([p[k] for p in parts[:-1]], ignore_index=True) for k in parts[0]}
bk = N.Book(H, parts[-1], G, 2026)
M = json.load(open(os.path.join(ROOT, "data", "models", "nfl_ml.json")))
MP = json.load(open(os.path.join(ROOT, "data", "models", "nfl_ptd1.json")))
cols = M["cols"]

# ---- 1. features against the training table
X = pd.read_pickle(XS)
X = X[X.season >= 2025].reset_index(drop=True)
diffs, pdiff = {c: [] for c in cols if c not in ("rest", "div")}, []
for r in X.itertuples():
    h, a = bk.prof(r.home, r.season, r.week), bk.prof(r.away, r.season, r.week)
    for side, team, q in ((h, r.home, r.h_qb), (a, r.away, r.a_qb)):
        qe, cp, qn = bk.qprof(q, r.season, r.week)
        side.update(qe=qe, cp=cp, qn=qn, backup=bk.backup(team, r.season, r.week, q))
    z0, z1 = [], []
    for c in cols:
        if c in ("rest", "div"):
            v = getattr(r, c)
            z0.append(v)
            z1.append(v)
            continue
        new = h.get(c, np.nan) - a.get(c, np.nan)
        old = float(getattr(r, "h_" + c)) - float(getattr(r, "a_" + c))
        diffs[c].append(abs((0 if new != new else new) - (0 if old != old else old)))
        z0.append(old)
        z1.append(new)
    f = lambda z: 1 / (1 + np.exp(-(np.nan_to_num(np.array(z, float)) @ np.array(M["coef"]) + M["intercept"])))
    pdiff.append(abs(f(z0) - f(z1)))
pdiff = np.array(pdiff)
print("1. moneyline features, %d games 2025-26 rebuilt vs the training table" % len(X))
print("   max |feature diff|:", {c: round(max(v), 6) for c, v in diffs.items() if max(v) > 1e-9} or "none")
print("   |p diff|: max %.2e, games over 0.005: %d, over 0.01: %d" % (pdiff.max(), (pdiff > 0.005).sum(), (pdiff > 0.01).sum()))

# ---- 2. Week 5 replay
git = lambda ref, path: json.loads(subprocess.check_output(["git", "-C", ROOT, "show", "%s:%s" % (ref, path)]))
dep_ml, dep_pt = git("0467cb05", "site/depth.json"), git("cb8715db", "site/depth.json")
ml8, pt8 = git("78ada516", "data/ml_reads.json"), git("78ada516", "data/ptd_reads.json")
PL = pd.read_csv(os.path.join(NFV, "players.csv"), usecols=["gsis_id", "espn_id"], dtype=str).dropna()
e2g = {str(int(float(e))): g for e, g in zip(PL.espn_id, PL.gsis_id)}
g5 = G[(G.season == 2026) & (G.week == 5) & (G.game_type == "REG")]
print("2. Week 5 replay (model on the pick, Oct 8 file vs job; job without qn = the hand-run week.py)")
for keep_qn in (False, True):
    bad = 0
    for g in g5.itertuples():
        away, home = N.G2B.get(g.away_team, g.away_team), N.G2B.get(g.home_team, g.home_team)
        q = {}
        for club, gq in ((away, g.away_qb_id), (home, g.home_qb_id)):
            s = (dep_ml.get(club) or {}).get("starter")
            q[club] = e2g.get(str(s)) or gq
        gs = pd.Series(g._asdict())
        if not keep_qn:   # ml/week.py never set qn, so it went in as 0
            orig = bk.qprof
            bk.qprof = lambda *a_: orig(*a_)[:2] + (np.nan,)
        p, h, a, contrib = N.ml_read(bk, M, gs, q[away], q[home])
        if not keep_qn:
            bk.qprof = orig
        pick, conf = (home, p) if p >= .5 else (away, 1 - p)
        o = next(r for r in ml8["reads"] if r["away"] == away and r["home"] == home)
        why = N.ml_why(p, h, a, contrib, home, away)
        same = o["pick"] == pick and o["model"] == round(100 * conf)
        bad += not same
        print("   %s %-8s Oct 8 %s %d | job %s %d %s%s" % ("qn" if keep_qn else "  ", away + "@" + home, o["pick"], o["model"], pick, round(100 * conf),
                                                    "" if same else "  <- differs", "" if [w.replace("LAR", "LA").replace("WSH", "WAS") for w in why] == o["why"] or not same or keep_qn else "  (why differs)"))
    print("   %s: %d of %d games differ" % ("with qn" if keep_qn else "without qn", bad, len(g5)))
bad = 0
for g in g5.itertuples():
    for team, opp, home in ((g.home_team, g.away_team, 1), (g.away_team, g.home_team, 0)):
        club = N.G2B.get(team, team)
        sid = str((dep_pt.get(club) or {}).get("starter"))
        qb = e2g.get(sid) or (g.home_qb_id if home else g.away_qb_id)
        row = N.ptd_feats(bk, qb, team, opp, home, 2026, 5, g.roof, g.div_game)[0]
        p1 = round(N.ptd_p(MP, row), 3)
        o = (pt8["reads"].get(sid) or {}).get("p")
        if o is None:
            print("   1+ %-4s %s: no Oct 8 read (job %.3f)" % (club, sid, p1))
            continue
        bad += o != p1
        if o != p1:
            print("   1+ %-4s %s: Oct 8 %.3f job %.3f" % (club, sid, o, p1))
print("   1+ TD: %d of %d passers differ" % (bad, len(pt8["reads"])))
