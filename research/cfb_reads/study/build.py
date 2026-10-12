"""Turn the cached ESPN JSON into one row per team-game (that team's starting QB).

Only FBS vs FBS games are kept -- for targets AND for the history features.
Every feature is computed from games strictly before the game's kickoff.

  python3 build.py   -> games.parquet (raw team-games), data.parquet (features + target)
"""
import glob, json, os, statistics
from collections import defaultdict, deque
import numpy as np
import pandas as pd

D = os.path.dirname(os.path.abspath(__file__))
FBS = {int(os.path.basename(f)[:4]): set(json.load(open(f))) for f in glob.glob(os.path.join(D, "fbs", "*.json"))}
SKIP_ODDS = {"Opening"}


def line(eid, home_abbr, away_abbr):
    """Home-team spread (negative = home favored) and total, median over providers."""
    fn = os.path.join(D, "odds", f"{eid}.json")
    if not os.path.exists(fn):
        return np.nan, np.nan
    sp, ou = [], []
    for o in json.load(open(fn)):
        if o["p"] in SKIP_ODDS:
            continue
        s, det = o.get("spread"), (o.get("details") or "")
        if s is not None and det:
            # ESPN's spread field is the home line; confirm with the favorite named in details
            fav = det.split(" ")[0].upper()
            if det.upper() in ("EVEN", "PK", "PICK"):
                s = 0.0
            elif fav == home_abbr.upper():
                s = -abs(s)
            elif fav == away_abbr.upper():
                s = abs(s)
            sp.append(float(s))
        if o.get("ou"):
            ou.append(float(o["ou"]))
    return (statistics.median(sp) if sp else np.nan), (statistics.median(ou) if ou else np.nan)


def team_games():
    rows = []
    for f in glob.glob(os.path.join(D, "cache", "*.json")):
        d = json.load(open(f))
        h = d.get("header", {})
        comp = (h.get("competitions") or [{}])[0]
        if not comp.get("status", {}).get("type", {}).get("completed", True):
            continue
        yr = h.get("season", {}).get("year")
        cs = comp.get("competitors", [])
        if len(cs) != 2 or yr not in FBS:
            continue
        ids = [c["team"]["id"] for c in cs]
        if not all(i in FBS[yr] for i in ids):
            continue  # FBS vs FBS only
        box = {p["team"]["id"]: p for p in d.get("boxscore", {}).get("players", [])}
        eid = h["id"]
        home = next(c for c in cs if c["homeAway"] == "home")
        away = next(c for c in cs if c["homeAway"] == "away")
        sp_home, ou = line(eid, home["team"].get("abbreviation", ""), away["team"].get("abbreviation", ""))
        for c in cs:
            o = away if c is home else home
            tid = c["team"]["id"]
            pas = next((s for s in box.get(tid, {}).get("statistics", []) if s["name"] == "passing"), None)
            if not pas or not pas.get("athletes"):
                continue
            lab = pas["labels"]
            qbs = []
            team_td = 0
            for a in pas["athletes"]:
                st = dict(zip(lab, a["stats"]))
                try:
                    att = int(st["C/ATT"].split("/")[1]); td = int(st["TD"])
                except Exception:
                    continue
                team_td += td
                qbs.append((att, td, a["athlete"]["id"], a["athlete"]["displayName"]))
            if not qbs:
                continue
            att, td, qid, qname = max(qbs)
            try:
                pts, opts = float(c.get("score")), float(o.get("score"))
            except Exception:
                continue
            neutral = bool(comp.get("neutralSite"))
            rows.append(dict(
                eid=eid, date=comp["date"], season=yr, stype=h["season"].get("type", 2), week=h.get("week") or 0,
                team=tid, team_abbr=c["team"].get("abbreviation"), opp=o["team"]["id"], opp_abbr=o["team"].get("abbreviation"),
                ha=("N" if neutral else ("H" if c["homeAway"] == "home" else "A")),
                conf=bool(comp.get("conferenceCompetition")),
                qb=qid, qb_name=qname, att=att, ptd=td, team_ptd=team_td, pts=pts, opp_pts=opts,
                spread=(sp_home if c is home else -sp_home) if sp_home == sp_home else np.nan, total=ou))
    g = pd.DataFrame(rows)
    g["date"] = pd.to_datetime(g["date"], utc=True)
    return g.sort_values(["date", "eid", "team"]).reset_index(drop=True)


QN, TN = 12, 12   # QB and team windows (games)
K_QB = 4.0        # shrinkage weight toward the team / league prior


def features(g):
    """Walk the games in time order; features only from earlier games."""
    qb_hist = defaultdict(lambda: deque(maxlen=QN))      # (td, att)
    tm_hist = defaultdict(lambda: deque(maxlen=TN))      # (team_ptd, pts, att)
    df_hist = defaultdict(lambda: deque(maxlen=TN))      # (ptd allowed, pts allowed)
    season_n = defaultdict(int)
    lg = deque(maxlen=3000)                               # league recent team-games (ptd, pts)
    out = []
    for date, day in g.groupby("date", sort=True):
        feats = []
        for r in day.itertuples():
            lg_td = np.mean([x[0] for x in lg]) if lg else 1.8
            lg_pts = np.mean([x[1] for x in lg]) if lg else 28.0
            lg_hit = np.mean([x[0] >= 1 for x in lg]) if lg else 0.8
            th, oh, qh = tm_hist[r.team], df_hist[r.opp], qb_hist[r.qb]
            t_td = (sum(x[0] for x in th) + 3 * lg_td) / (len(th) + 3)
            t_pts = (sum(x[1] for x in th) + 3 * lg_pts) / (len(th) + 3)
            o_td = (sum(x[0] for x in oh) + 3 * lg_td) / (len(oh) + 3)
            o_pts = (sum(x[1] for x in oh) + 3 * lg_pts) / (len(oh) + 3)
            prior_td = t_td
            q_td = (sum(x[0] for x in qh) + K_QB * prior_td) / (len(qh) + K_QB)
            q_hit = (sum(x[0] >= 1 for x in qh) + K_QB * lg_hit) / (len(qh) + K_QB)
            q_att = (sum(x[1] for x in qh) + K_QB * 30.0) / (len(qh) + K_QB)
            feats.append(dict(q_td=q_td, q_hit=q_hit, q_att=q_att, q_n=len(qh), t_td=t_td, t_pts=t_pts,
                              o_td=o_td, o_pts=o_pts, t_n=len(th), o_n=len(oh),
                              gnum=season_n[(r.season, r.team)]))
        for r, f in zip(day.itertuples(), feats):
            out.append({**r._asdict(), **f})
        for r in day.itertuples():
            qb_hist[r.qb].append((r.ptd, r.att))
            tm_hist[r.team].append((r.team_ptd, r.pts, r.att))
            df_hist[r.opp].append((r.team_ptd, r.pts))
            season_n[(r.season, r.team)] += 1
            lg.append((r.team_ptd, r.pts))
    X = pd.DataFrame(out).drop(columns=["Index"])
    X["y"] = (X.ptd >= 1).astype(int)
    X["home"] = (X.ha == "H").astype(int)
    X["away"] = (X.ha == "A").astype(int)
    X["has_line"] = X.spread.notna().astype(int)
    X["itt"] = X.total / 2 - X.spread / 2
    return X


if __name__ == "__main__":
    g = team_games()
    g.to_parquet(os.path.join(D, "games.parquet"))
    X = features(g)
    X.to_parquet(os.path.join(D, "data.parquet"))
    print(len(g), "team-games;", X.groupby("season").agg(n=("y", "size"), base=("y", "mean"), line=("has_line", "mean")))
