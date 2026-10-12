"""CFB QB head-to-head passing yards: one row per FBS vs FBS game.

  python3 h2h/build_h2h.py  -> h2h/tg.parquet (team-games), h2h/games.parquet (game rows, gaps + label)

Starter = the team's leading passer by attempts, 10+ attempts. Label y = 1 when the
home (ESPN-designated) QB threw for more yards; ties dropped.
Every feature is season-to-date from games strictly before kickoff; when a team or
QB has fewer than 3 games in the season, the prior season's games are pooled in.
"""
import glob, json, os, sys
from collections import defaultdict
import numpy as np
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
D = os.path.dirname(H)
sys.path.insert(0, D)
import build  # noqa: E402  (line(), FBS)


def _i(x):
    try:
        return int(x)
    except Exception:
        return 0


def team_games(upcoming=None, files=None):
    rows = []
    for f in (glob.glob(os.path.join(D, "cache", "*.json")) if files is None else files):
        d = json.load(open(f))
        h = d.get("header", {})
        comp = (h.get("competitions") or [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed", True):
            continue
        yr = h.get("season", {}).get("year")
        cs = comp.get("competitors", [])
        if len(cs) != 2 or yr not in build.FBS or not all(c["team"]["id"] in build.FBS[yr] for c in cs):
            continue
        box = {p["team"]["id"]: p for p in d.get("boxscore", {}).get("players", [])}
        tst = {t["team"]["id"]: {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
               for t in d.get("boxscore", {}).get("teams", [])}
        eid = h["id"]
        home = next(c for c in cs if c["homeAway"] == "home")
        away = next(c for c in cs if c["homeAway"] == "away")
        sp_home, ou = build.line(eid, home["team"].get("abbreviation", ""), away["team"].get("abbreviation", ""))
        ok = True
        rr = []
        for c in cs:
            o = away if c is home else home
            tid = c["team"]["id"]
            pas = next((s for s in box.get(tid, {}).get("statistics", []) if s["name"] == "passing"), None)
            if not pas or not pas.get("athletes") or tid not in tst:
                ok = False; break
            lab = pas["labels"]
            qbs, gross = [], 0
            for a in pas["athletes"]:
                st = dict(zip(lab, a["stats"]))
                try:
                    cmp_, att = [int(x) for x in st["C/ATT"].split("/")]
                    yds = int(st["YDS"])
                except Exception:
                    continue
                gross += yds
                qbs.append((att, yds, cmp_, a["athlete"]["id"], a["athlete"]["displayName"]))
            if not qbs:
                ok = False; break
            att, yds, cmp_, qid, qname = max(qbs, key=lambda x: (x[0], x[1]))
            T = tst[tid]
            try:
                tca = [int(x) for x in (T.get("completionAttempts") or "0/0").replace("-", "/").split("/")]
            except Exception:
                tca = [0, 0]
            try:
                pts, opts = float(c.get("score")), float(o.get("score"))
            except Exception:
                ok = False; break
            neutral = bool(comp.get("neutralSite"))
            rr.append(dict(
                eid=eid, date=comp["date"], season=yr, stype=h["season"].get("type", 2), week=h.get("week") or 0,
                team=tid, team_abbr=c["team"].get("abbreviation"), opp=o["team"]["id"], opp_abbr=o["team"].get("abbreviation"),
                ha=("N" if neutral else ("H" if c["homeAway"] == "home" else "A")), is_home=c is home,
                conf=bool(comp.get("conferenceCompetition")),
                qb=qid, qb_name=qname, q_att=att, q_yds=yds, q_cmp=cmp_,
                t_patt=tca[1] or att, t_pyds=gross, t_net=_i(T.get("netPassingYards")),
                t_ratt=_i(T.get("rushingAttempts")), t_ryds=_i(T.get("rushingYards")), pts=pts, opp_pts=opts,
                spread=(sp_home if c is home else -sp_home) if sp_home == sp_home else np.nan, total=ou))
        if ok:
            rows += rr
    g = pd.DataFrame(rows)
    if g.empty:
        return g
    g["sackyds"] = (g.t_pyds - g.t_net).clip(lower=0)          # yards lost to sacks (gross - net)
    g["date"] = pd.to_datetime(g["date"], utc=True)
    if upcoming is not None and len(upcoming):
        g["upcoming"] = False
        g = pd.concat([g, upcoming], ignore_index=True)
    else:
        g["upcoming"] = False
    return g.sort_values(["date", "eid", "team"]).reset_index(drop=True)


def _pool(L, season):
    """Season-to-date entries; pool the prior season when fewer than 3."""
    cur = [x for x in L if x[0] == season]
    if len(cur) >= 3:
        return cur, len(cur)
    return cur + [x for x in L if x[0] == season - 1], len(cur)


def _m(L, k):
    v = [x[k] for x in L]
    return float(np.mean(v)) if v else np.nan


def features(g):
    qbH, tmH, dfH = defaultdict(list), defaultdict(list), defaultdict(list)
    opp_of = {}
    for r in g.itertuples():
        opp_of[(r.eid, r.team)] = r
    out = []
    for date, day in g.groupby("date", sort=True):
        fs = []
        for r in day.itertuples():
            s = r.season
            q, qn = _pool(qbH[r.qb], s)
            t, tn = _pool(tmH[r.team], s)
            o, on = _pool(dfH[r.opp], s)
            q3 = qbH[r.qb][-3:]
            f = dict(
                q_n=qn, q_any=len(q),
                q_ypg=_m(q, 1), q_apg=_m(q, 2),
                q_ypa=(sum(x[1] for x in q) / max(1, sum(x[2] for x in q))) if q else np.nan,
                q_cmp=(sum(x[3] for x in q) / max(1, sum(x[2] for x in q))) if q else np.nan,
                q_ypg3=_m(q3, 1),
                t_n=tn, t_prate=(sum(x[1] for x in t) / max(1, sum(x[1] + x[2] for x in t))) if t else np.nan,
                t_ppg=_m(t, 4), t_plays=(_m(t, 1) + _m(t, 2)) if t else np.nan, t_qbypg=_m(t, 6),
                t_rypg=_m(t, 3), t_ypc=(sum(x[3] for x in t) / max(1, sum(x[2] for x in t))) if t else np.nan,
                t_sacked=_m(t, 5),
                d_n=on, d_pypg=_m(o, 1), d_ypa=(sum(x[1] for x in o) / max(1, sum(x[2] for x in o))) if o else np.nan,
                d_qbypg=_m(o, 3), d_sack=_m(o, 4), d_rypg=_m(o, 5), d_papg=_m(o, 2), d_ppg=_m(o, 6),
                gnum=len([x for x in tmH[r.team] if x[0] == s]))
            fs.append(f)
        for r, f in zip(day.itertuples(), fs):
            out.append({**r._asdict(), **f})
        for r in day.itertuples():
            if getattr(r, "upcoming", False):
                continue
            qbH[r.qb].append((r.season, r.q_yds, r.q_att, r.q_cmp))
            tmH[r.team].append((r.season, r.t_patt, r.t_ratt, r.t_ryds, r.pts, r.sackyds, r.q_yds))
            dfH[r.opp].append((r.season, r.t_pyds, r.t_patt, r.q_yds, r.sackyds, r.t_ryds, r.pts))
    X = pd.DataFrame(out).drop(columns=["Index"])
    # fallbacks: QB with no history -> his team's leading-passer numbers -> league mean
    X["q_new"] = (X.q_any == 0).astype(int)
    X["q_ypg"] = X.q_ypg.fillna(X.t_qbypg)
    X["q_ypg3"] = X.q_ypg3.fillna(X.q_ypg)
    for c in ["q_ypg", "q_apg", "q_ypa", "q_cmp", "q_ypg3", "t_prate", "t_ppg", "t_plays", "t_qbypg", "t_rypg", "t_ypc",
              "t_sacked", "d_pypg", "d_ypa", "d_qbypg", "d_sack", "d_rypg", "d_papg", "d_ppg"]:
        X[c] = X.groupby("season")[c].transform(lambda v: v.fillna(v.mean()))
    X["itt"] = X.total / 2 - X.spread / 2
    # matchup projection: QB yards/game scaled by how the defense compares with the league
    lg = X.groupby("season").d_qbypg.transform("mean")
    X["proj"] = X.q_ypg * X.d_qbypg / lg
    X["proj2"] = (X.q_ypg + X.d_qbypg) / 2
    return X


FEATS = ["q_ypg", "q_apg", "q_ypa", "q_cmp", "q_ypg3", "t_prate", "t_ppg", "t_plays", "t_rypg", "t_ypc", "t_sacked",
         "d_pypg", "d_ypa", "d_qbypg", "d_sack", "d_rypg", "d_papg", "d_ppg", "proj", "proj2", "itt", "spread"]


def pair(X):
    """Home row minus away row -> one row per game. Gaps are home - away."""
    h = X[X.is_home].set_index("eid"); a = X[~X.is_home].set_index("eid")
    common = h.index.intersection(a.index)
    h, a = h.loc[common], a.loc[common]
    G = pd.DataFrame(index=common)
    for c in ["date", "season", "stype", "week", "ha", "conf", "total", "upcoming"]:
        G[c] = h[c]
    G["neutral"] = (h.ha == "N").astype(int)
    G["h_team"], G["a_team"] = h.team_abbr, a.team_abbr
    G["h_qb"], G["a_qb"] = h.qb_name, a.qb_name
    G["h_att"], G["a_att"] = h.q_att, a.q_att
    G["h_yds"], G["a_yds"] = h.q_yds, a.q_yds
    G["h_spread"] = h.spread
    G["early"] = ((h.gnum < 3) | (a.gnum < 3)).astype(int)
    G["new_gap"] = h.q_new - a.q_new
    for c in FEATS:
        G["g_" + c] = h[c] - a[c]
    # d_* on a row describe the defense that row's QB faces, so h - a > 0 means the home QB
    # faces the softer pass defense. Sack yards are flipped so positive favors the home QB.
    G["g_d_sack"] = -(h.d_sack - a.d_sack)      # positive = home QB faces fewer sack yards
    G["g_t_sacked"] = -(h.t_sacked - a.t_sacked)
    G["g_spread"] = -(h.spread - a.spread) / 2  # positive = home favored (equals -home spread)
    G["g_q_new"] = -(h.q_new - a.q_new)
    G["y"] = np.where(h.q_yds > a.q_yds, 1, np.where(h.q_yds < a.q_yds, 0, -1))
    G["ok"] = (h.q_att >= 10) & (a.q_att >= 10) & (G.y >= 0)
    return G.reset_index().rename(columns={"index": "eid"})


if __name__ == "__main__":
    g = team_games()
    g.to_parquet(os.path.join(H, "tg.parquet"))
    X = features(g)
    G = pair(X)
    G.to_parquet(os.path.join(H, "games.parquet"))
    k = G[G.ok]
    print(len(g), "team-games;", len(G), "games;", len(k), "labeled")
    print(k.groupby("season").agg(n=("y", "size"), home=("y", "mean"), line=("h_spread", lambda v: v.notna().mean())))
