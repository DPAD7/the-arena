"""CFB moneyline: one row per FBS vs FBS game, home minus away pre-game differences.

  python3 ml/build_ml.py   -> ml/tg.parquet (team-games), ml/games.parquet (game rows + label)

Every feature comes from games strictly before kickoff (FBS vs FBS games only).
Team profile: season-to-date; with fewer than 4 games this season, the prior season's
last (8 - 2*n) games are pooled in (same blend as the NFL build).
QB profile: the game's starter (most attempts), his last 10 FBS games across seasons/teams,
shrunk toward the league rate. No odds, spread or total are model inputs.
"""
import glob, json, os, sys
from collections import defaultdict
import numpy as np
import pandas as pd

M = os.path.dirname(os.path.abspath(__file__)); D = os.path.dirname(M)
sys.path.insert(0, D)
import build  # FBS sets

def _i(x):
    try: return int(x)
    except Exception: return 0

def ranks():
    """eid -> {team id: AP/CFP curated rank or 99} from the scoreboard files."""
    R = {}
    for f in glob.glob(os.path.join(D, "weeks", "*.json")):
        try: d = json.load(open(f))
        except Exception: continue
        for e in d.get("events", []):
            for c in e["competitions"][0]["competitors"]:
                R.setdefault(e["id"], {})[c["team"]["id"]] = (c.get("curatedRank") or {}).get("current", 99) or 99
    return R

def team_games(files=None):
    RK = ranks(); rows = []
    for f in (glob.glob(os.path.join(D, "cache", "*.json")) if files is None else files):
        d = json.load(open(f)); h = d.get("header", {}); comp = (h.get("competitions") or [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed", True): continue
        yr = h.get("season", {}).get("year"); cs = comp.get("competitors", [])
        if len(cs) != 2 or yr not in build.FBS or not all(c["team"]["id"] in build.FBS[yr] for c in cs): continue
        box = {p["team"]["id"]: p for p in d.get("boxscore", {}).get("players", [])}
        tst = {t["team"]["id"]: {s["name"]: s.get("displayValue") for s in t.get("statistics", [])} for t in d.get("boxscore", {}).get("teams", [])}
        eid = h["id"]; home = next(c for c in cs if c["homeAway"] == "home")
        rr = []; ok = True
        for c in cs:
            o = [x for x in cs if x is not c][0]; tid = c["team"]["id"]
            T = tst.get(tid)
            pas = next((s for s in box.get(tid, {}).get("statistics", []) if s["name"] == "passing"), None)
            try: pts, opts = float(c.get("score")), float(o.get("score"))
            except Exception: ok = False; break
            if not T or not pas or not pas.get("athletes"): ok = False; break
            qbs = []
            for a in pas["athletes"]:
                st = dict(zip(pas["labels"], a["stats"]))
                try:
                    cm, att = [int(x) for x in st["C/ATT"].split("/")]
                    qbs.append((att, _i(st.get("YDS")), _i(st.get("TD")), _i(st.get("INT")), a["athlete"]["id"], a["athlete"]["displayName"]))
                except Exception: continue
            if not qbs: ok = False; break
            q = max(qbs, key=lambda x: (x[0], x[1]))
            try: patt = int((T.get("completionAttempts") or "0/0").replace("-", "/").split("/")[1])
            except Exception: patt = q[0]
            ratt = _i(T.get("rushingAttempts"))
            rr.append(dict(eid=eid, date=comp["date"], season=yr, stype=h["season"].get("type", 2), week=h.get("week") or 0,
                           team=tid, team_abbr=c["team"].get("abbreviation"), opp=o["team"]["id"], opp_abbr=o["team"].get("abbreviation"),
                           is_home=c is home, neutral=bool(comp.get("neutralSite")), conf=bool(comp.get("conferenceCompetition")),
                           rank=RK.get(eid, {}).get(tid, 99), pts=pts, opp_pts=opts,
                           yds=_i(T.get("totalYards")), plays=patt + ratt, pyds=_i(T.get("netPassingYards")), ryds=_i(T.get("rushingYards")),
                           to=_i(T.get("turnovers")), qb=q[4], qb_name=q[5], q_att=q[0], q_yds=q[1], q_td=q[2], q_int=q[3]))
        if ok: rows += rr
    g = pd.DataFrame(rows); g["date"] = pd.to_datetime(g.date, utc=True); g["upcoming"] = False
    return g

TF = ["pf", "pa", "ypp_o", "ypp_d", "py_o", "py_d", "ry_o", "ry_d", "to_o", "to_d", "win", "mov"]

def features(g):
    """g: team-games (completed + optional upcoming rows with upcoming=True). Returns team-game rows with pre-game features."""
    g = g.sort_values(["date", "eid", "team"]).reset_index(drop=True)
    opp = g.set_index(["eid", "team"])
    # attach each row's opponent box line (for defense)
    o = g[["eid", "team", "yds", "plays", "pyds", "ryds", "to"]].rename(columns={"team": "opp", "yds": "o_yds", "plays": "o_plays", "pyds": "o_pyds", "ryds": "o_ryds", "to": "o_to"})
    g = g.merge(o, on=["eid", "opp"], how="left")
    tmH, qbH, starts = defaultdict(list), defaultdict(list), defaultdict(list)
    lastdate = {}
    lgq = []  # league QB lines (att, yds, td, int)
    out = []
    for date, day in g.groupby(g.date.dt.date, sort=True):
        fs = []
        for r in day.itertuples():
            s = r.season; L = tmH[r.team]
            cur = [x for x in L if x["season"] == s]
            prev = [x for x in L if x["season"] == s - 1]
            base = cur if len(cur) >= 4 or not prev else prev[-(8 - 2 * len(cur)):] + cur
            f = {"g_n": len(cur), "hist": len(base)}
            for k in TF:
                f[k] = float(np.mean([x[k] for x in base])) if base else np.nan
            if base:
                pl = sum(x["plays"] for x in base) or 1; opl = sum(x["oplays"] for x in base) or 1
                f["ypp_o"] = sum(x["yds"] for x in base) / pl; f["ypp_d"] = sum(x["oyds"] for x in base) / opl
            f["l3_win"] = float(np.mean([x["win"] for x in cur[-3:]])) if cur else np.nan
            f["l3_mov"] = float(np.mean([x["mov"] for x in cur[-3:]])) if cur else np.nan
            # QB: last 10 games anywhere, shrunk toward the league per-attempt rates with 60 attempts
            Q = qbH[r.qb][-10:]
            la = sum(x[0] for x in lgq[-3000:]) or 1
            lypa = sum(x[1] for x in lgq[-3000:]) / la if lgq else 7.3
            ltd = sum(x[2] for x in lgq[-3000:]) / la if lgq else 0.05
            lint = sum(x[3] for x in lgq[-3000:]) / la if lgq else 0.027
            qa = sum(x[0] for x in Q); K = 60
            f["q_ypa"] = (sum(x[1] for x in Q) + K * lypa) / (qa + K)
            f["q_tdr"] = (sum(x[2] for x in Q) + K * ltd) / (qa + K)
            f["q_intr"] = (sum(x[3] for x in Q) + K * lint) / (qa + K)
            f["q_n"] = len(Q)
            # backup / new QB: this game's starter is not the team's usual starter (3+ of its recent starts)
            st = [x for x in starts[r.team] if x[0] == s]
            st = st if len(st) >= 2 else [x for x in starts[r.team] if x[0] == s - 1][-8:] + st
            ids = [x[1] for x in st]
            u = max(set(ids), key=ids.count) if ids else None
            f["backup"] = int(u is not None and r.qb != u and ids.count(u) >= 3)
            f["newqb"] = int(len(Q) == 0)
            ld = lastdate.get(r.team)
            f["rest"] = min(21.0, (r.date - ld).days) if ld is not None and (r.date - ld).days < 60 else 21.0
            f["ranked"] = int(r.rank <= 25); f["rankpts"] = (26 - r.rank) if r.rank <= 25 else 0
            fs.append(f)
        for r, f in zip(day.itertuples(), fs):
            out.append({**r._asdict(), **f})
        for r in day.itertuples():
            if r.upcoming: continue
            tmH[r.team].append(dict(season=r.season, pf=r.pts, pa=r.opp_pts, yds=r.yds, plays=r.plays, oyds=r.o_yds, oplays=r.o_plays,
                                    py_o=r.pyds, py_d=r.o_pyds, ry_o=r.ryds, ry_d=r.o_ryds, to_o=r.to, to_d=r.o_to,
                                    win=float(r.pts > r.opp_pts), mov=max(-28, min(28, r.pts - r.opp_pts)), ypp_o=0, ypp_d=0))
            qbH[r.qb].append((r.q_att, r.q_yds, r.q_td, r.q_int)); lgq.append((r.q_att, r.q_yds, r.q_td, r.q_int))
            starts[r.team].append((r.season, r.qb)); lastdate[r.team] = r.date
    X = pd.DataFrame(out).drop(columns=["Index"])
    X = X.merge(srs(g), on=["eid", "team"], how="left")
    # teams with no FBS history (new to FBS): season mean of the bottom quarter
    for c in TF + ["l3_win", "l3_mov", "srs"]:
        X[c] = X.groupby("season")[c].transform(lambda v: v.fillna(v.quantile(0.25) if c not in ("pa", "ypp_d", "py_d", "ry_d", "to_o") else v.quantile(0.75)))
    return X

def srs(g):
    """Margin rating from earlier games only: ridge fit of capped margin = r_team - r_opp + hfa,
    this season's games at weight 1, last season's at max(0.1, 1 - weeks_in/8)."""
    done = g[~g.upcoming]
    hg = done[done.is_home]
    res = []
    for date in sorted(g.date.dt.date.unique()):
        day = g[g.date.dt.date == date]; s = int(day.season.iloc[0])
        past = hg[(hg.date.dt.date < date) & (hg.season >= s - 1)]
        cur = past[past.season == s]
        wk = cur.week.max() if len(cur) else 0
        w = np.where(past.season == s, 1.0, max(0.1, 1 - wk / 8))
        teams = sorted(set(past.team) | set(past.opp))
        if len(past) < 50:
            for r in day.itertuples(): res.append((r.eid, r.team, np.nan))
            continue
        ix = {t: i for i, t in enumerate(teams)}; n = len(teams)
        A = np.zeros((len(past), n + 1)); y = np.clip((past.pts - past.opp_pts).values, -28, 28)
        A[np.arange(len(past)), [ix[t] for t in past.team]] = 1
        A[np.arange(len(past)), [ix[t] for t in past.opp]] = -1
        A[:, n] = (~past.neutral).astype(float).values
        Wt = np.sqrt(w)[:, None]; lam = 2.0
        sol = np.linalg.solve((A * Wt).T @ (A * Wt) + lam * np.eye(n + 1), (A * Wt).T @ (y * Wt[:, 0]))
        for r in day.itertuples(): res.append((r.eid, r.team, sol[ix[r.team]] if r.team in ix else np.nan))
    return pd.DataFrame(res, columns=["eid", "team", "srs"]).drop_duplicates(["eid", "team"])

DIFF = TF + ["l3_win", "l3_mov", "srs", "q_ypa", "q_tdr", "q_intr", "backup", "newqb", "rest", "ranked", "rankpts"]

def pair(X):
    h = X[X.is_home].set_index("eid"); a = X[~X.is_home].set_index("eid")
    c = h.index.intersection(a.index); h, a = h.loc[c], a.loc[c]
    G = pd.DataFrame(index=c)
    for k in ["date", "season", "stype", "week", "conf", "neutral", "upcoming"]: G[k] = h[k]
    G["h_team"], G["a_team"], G["h_id"], G["a_id"] = h.team_abbr, a.team_abbr, h.team, a.team
    G["h_qb"], G["a_qb"] = h.qb_name, a.qb_name
    G["h_pts"], G["a_pts"] = h.pts, a.pts
    G["home"] = (~h.neutral.astype(bool)).astype(int); G["conf"] = h.conf.astype(int)
    G["early"] = ((h.g_n < 3) | (a.g_n < 3)).astype(int)
    for k in DIFF: G["d_" + k] = h[k] - a[k]
    G["y"] = (h.pts > a.pts).astype(int)
    return G.reset_index().rename(columns={"index": "eid"})

if __name__ == "__main__":
    g = team_games(); g.to_parquet(os.path.join(M, "tg.parquet"))
    X = features(g); X.to_parquet(os.path.join(M, "X.parquet"))
    G = pair(X); G.to_parquet(os.path.join(M, "games.parquet"))
    print(len(g), "team-games", len(G), "games"); print(G.groupby("season").agg(n=("y", "size"), home=("y", "mean"), srs=("d_srs", lambda v: v.notna().mean())))
