"""The four college reads, every sweep: moneyline, passing-yards head to head,
   1+ and 2+ passing TD, for every FBS vs FBS game in the next eight days.

   The models were fit on 2016-21 and read blind on 2022-26 (research/cfb_reads/,
   the RESULTS files there). Each read is the tested rule and nothing else:

     ML    model 75%+ (week_ml.py READ)                         blind 82-92%
     H2H   model winner chance >= the 2016-21 top-10% cut (83.2%), with a line
                                                                 blind ~91%
     1+    LR p >= 0.90 and the game has an ESPN line           blind ~93%
     2+    LR p >= 0.70 and the game has an ESPN line           blind ~78%

   "call" is "take" only when the rule is met; p is always kept so it can be
   shown. The passer for each club is the board's own card QB (the CFB array
   in the page) when it has one, else the man who started the club's last FBS
   game -- the same order the week scripts use.

   History lives in data/cfb_hist/ (one table per model, built from the 4 GB
   ESPN cache once). Each run reads the season's week scoreboards, fetches
   only the summaries of FBS vs FBS games finished since the last run (the
   seen list), appends them, and scores the games still to kick. The models
   are plain logistic regressions kept in data/models/cfb_*.json and run
   with numpy; no scikit-learn on the runner.

   Writes data/cfb_reads.json; suggest.py turns it into the gold on the board.
   A game already under way keeps its read until two days after kickoff.

   Usage:  python3 cfb_reads.py [--dry]
           pip: pandas numpy pyarrow curl_cffi
"""
import datetime as dt
import json
import os
import re
import statistics
import sys
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(D, "data", "cfb_hist")
MODELS = os.path.join(D, "data", "models")
OUT = os.path.join(D, "data", "cfb_reads.json")
sys.path.insert(0, os.path.join(D, "build"))

SB = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
SUM = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event={}"
ODDS = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/events/{0}/competitions/{0}/odds?limit=50"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/{}/types/2/groups/80/children?limit=50"
WINDOW = dt.timedelta(days=8)
KEEP = dt.timedelta(days=2)

try:
    from curl_cffi import requests as _rq
    _S = _rq.Session(impersonate="chrome")
except Exception:  # plain urllib when curl_cffi is missing (local runs)
    _S = None


def get(url, tries=5):
    """JSON or None (404 / gave up). Same retry shape as the research fetch.py."""
    import urllib.request
    for i in range(tries):
        try:
            if _S is not None:
                r = _S.get(url, timeout=30)
                code, body = r.status_code, r.content
            else:
                try:
                    with urllib.request.urlopen(url, timeout=30) as r:
                        code, body = r.status, r.read()
                except urllib.error.HTTPError as e:
                    code, body = e.code, b""
            if code == 200:
                return json.loads(body)
            if code == 404:
                return None
        except Exception:
            pass
        time.sleep(1.5 * (i + 1))
    return None


# ---------------------------------------------------------------- lines

SKIP_ODDS = {"Opening"}


def line(items, home_abbr, away_abbr):
    """Home spread (negative = home favored) and total, median over providers
       (research build.line, on a list instead of a file)."""
    if items is None:
        return np.nan, np.nan
    sp, ou = [], []
    for o in items:
        if o["p"] in SKIP_ODDS:
            continue
        s, det = o.get("spread"), (o.get("details") or "")
        if s is not None and det:
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


def core_odds(eid):
    d = get(ODDS.format(eid)) or {}
    return [dict(p=i.get("provider", {}).get("name"), pid=i.get("provider", {}).get("id"),
                 spread=i.get("spread"), ou=i.get("overUnder"), details=i.get("details"))
            for i in d.get("items", [])]


# ---------------------------------------------------------------- parsing a finished game

def _i(x):
    try:
        return int(x)
    except Exception:
        return 0


def parse_ptd(d, odds, fbs):
    """research build.team_games for one summary: one row per team with a passer."""
    rows = []
    h = d.get("header", {})
    comp = (h.get("competitions") or [{}])[0]
    if not comp.get("status", {}).get("type", {}).get("completed", True):
        return rows
    yr = h.get("season", {}).get("year")
    cs = comp.get("competitors", [])
    if len(cs) != 2 or yr not in fbs:
        return rows
    if not all(c["team"]["id"] in fbs[yr] for c in cs):
        return rows
    box = {p["team"]["id"]: p for p in d.get("boxscore", {}).get("players", [])}
    eid = h["id"]
    home = next(c for c in cs if c["homeAway"] == "home")
    away = next(c for c in cs if c["homeAway"] == "away")
    sp_home, ou = line(odds, home["team"].get("abbreviation", ""), away["team"].get("abbreviation", ""))
    for c in cs:
        o = away if c is home else home
        tid = c["team"]["id"]
        pas = next((s for s in box.get(tid, {}).get("statistics", []) if s["name"] == "passing"), None)
        if not pas or not pas.get("athletes"):
            continue
        lab = pas["labels"]
        qbs, team_td = [], 0
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
    return rows


def parse_h2h(d, odds, fbs):
    """research h2h/build_h2h.team_games for one summary (both sides or nothing)."""
    h = d.get("header", {})
    comp = (h.get("competitions") or [{}])[0]
    if not comp.get("status", {}).get("type", {}).get("completed", True):
        return []
    yr = h.get("season", {}).get("year")
    cs = comp.get("competitors", [])
    if len(cs) != 2 or yr not in fbs or not all(c["team"]["id"] in fbs[yr] for c in cs):
        return []
    box = {p["team"]["id"]: p for p in d.get("boxscore", {}).get("players", [])}
    tst = {t["team"]["id"]: {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
           for t in d.get("boxscore", {}).get("teams", [])}
    eid = h["id"]
    home = next(c for c in cs if c["homeAway"] == "home")
    away = next(c for c in cs if c["homeAway"] == "away")
    sp_home, ou = line(odds, home["team"].get("abbreviation", ""), away["team"].get("abbreviation", ""))
    rr = []
    for c in cs:
        o = away if c is home else home
        tid = c["team"]["id"]
        pas = next((s for s in box.get(tid, {}).get("statistics", []) if s["name"] == "passing"), None)
        if not pas or not pas.get("athletes") or tid not in tst:
            return []
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
            return []
        att, yds, cmp_, qid, qname = max(qbs, key=lambda x: (x[0], x[1]))
        T = tst[tid]
        try:
            tca = [int(x) for x in (T.get("completionAttempts") or "0/0").replace("-", "/").split("/")]
        except Exception:
            tca = [0, 0]
        try:
            pts, opts = float(c.get("score")), float(o.get("score"))
        except Exception:
            return []
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
    for r in rr:
        r["sackyds"] = max(0, r["t_pyds"] - r["t_net"])
    return rr


def parse_ml(d, rank, fbs):
    """research ml/build_ml.team_games for one summary; rank = {team id: curated rank or 99}."""
    h = d.get("header", {}); comp = (h.get("competitions") or [{}])[0]
    if not comp.get("status", {}).get("type", {}).get("completed", True):
        return []
    yr = h.get("season", {}).get("year"); cs = comp.get("competitors", [])
    if len(cs) != 2 or yr not in fbs or not all(c["team"]["id"] in fbs[yr] for c in cs):
        return []
    box = {p["team"]["id"]: p for p in d.get("boxscore", {}).get("players", [])}
    tst = {t["team"]["id"]: {s["name"]: s.get("displayValue") for s in t.get("statistics", [])} for t in d.get("boxscore", {}).get("teams", [])}
    eid = h["id"]; home = next(c for c in cs if c["homeAway"] == "home")
    rr = []
    for c in cs:
        o = [x for x in cs if x is not c][0]; tid = c["team"]["id"]
        T = tst.get(tid)
        pas = next((s for s in box.get(tid, {}).get("statistics", []) if s["name"] == "passing"), None)
        try:
            pts, opts = float(c.get("score")), float(o.get("score"))
        except Exception:
            return []
        if not T or not pas or not pas.get("athletes"):
            return []
        qbs = []
        for a in pas["athletes"]:
            st = dict(zip(pas["labels"], a["stats"]))
            try:
                cm, att = [int(x) for x in st["C/ATT"].split("/")]
                qbs.append((att, _i(st.get("YDS")), _i(st.get("TD")), _i(st.get("INT")), a["athlete"]["id"], a["athlete"]["displayName"]))
            except Exception:
                continue
        if not qbs:
            return []
        q = max(qbs, key=lambda x: (x[0], x[1]))
        try:
            patt = int((T.get("completionAttempts") or "0/0").replace("-", "/").split("/")[1])
        except Exception:
            patt = q[0]
        ratt = _i(T.get("rushingAttempts"))
        rr.append(dict(eid=eid, date=comp["date"], season=yr, stype=h["season"].get("type", 2), week=h.get("week") or 0,
                       team=tid, team_abbr=c["team"].get("abbreviation"), opp=o["team"]["id"], opp_abbr=o["team"].get("abbreviation"),
                       is_home=c is home, neutral=bool(comp.get("neutralSite")), conf=bool(comp.get("conferenceCompetition")),
                       rank=(rank or {}).get(tid, 99), pts=pts, opp_pts=opts,
                       yds=_i(T.get("totalYards")), plays=patt + ratt, pyds=_i(T.get("netPassingYards")), ryds=_i(T.get("rushingYards")),
                       to=_i(T.get("turnovers")), qb=q[4], qb_name=q[5], q_att=q[0], q_yds=q[1], q_td=q[2], q_int=q[3]))
    return rr


# ---------------------------------------------------------------- features: 1+/2+ passing TD (research build.py)

def _days(g, key):
    """g.groupby(key, sort=True) as lists of row tuples, rows in frame order inside
       each day -- the same walk without pandas' cost per group."""
    by = defaultdict(list)
    for r, k in zip(g.itertuples(), key):
        by[k].append(r)
    for k in sorted(by):
        yield k, by[k]


QN, TN, K_QB = 12, 12, 4.0


def ptd_features(g):
    qb_hist = defaultdict(lambda: deque(maxlen=QN))
    tm_hist = defaultdict(lambda: deque(maxlen=TN))
    df_hist = defaultdict(lambda: deque(maxlen=TN))
    season_n = defaultdict(int)
    lg = deque(maxlen=3000)
    out = []
    for date, day in _days(g, g["date"]):
        # the league numbers do not move inside a day, so they are worked once per day
        lg_td = np.mean([x[0] for x in lg]) if lg else 1.8
        lg_pts = np.mean([x[1] for x in lg]) if lg else 28.0
        lg_hit = np.mean([x[0] >= 1 for x in lg]) if lg else 0.8
        feats = []
        for r in day:
            th, oh, qh = tm_hist[r.team], df_hist[r.opp], qb_hist[r.qb]
            t_td = (sum(x[0] for x in th) + 3 * lg_td) / (len(th) + 3)
            t_pts = (sum(x[1] for x in th) + 3 * lg_pts) / (len(th) + 3)
            o_td = (sum(x[0] for x in oh) + 3 * lg_td) / (len(oh) + 3)
            o_pts = (sum(x[1] for x in oh) + 3 * lg_pts) / (len(oh) + 3)
            q_td = (sum(x[0] for x in qh) + K_QB * t_td) / (len(qh) + K_QB)
            q_hit = (sum(x[0] >= 1 for x in qh) + K_QB * lg_hit) / (len(qh) + K_QB)
            q_att = (sum(x[1] for x in qh) + K_QB * 30.0) / (len(qh) + K_QB)
            feats.append(dict(q_td=q_td, q_hit=q_hit, q_att=q_att, q_n=len(qh), t_td=t_td, t_pts=t_pts,
                              o_td=o_td, o_pts=o_pts, t_n=len(th), o_n=len(oh),
                              gnum=season_n[(r.season, r.team)]))
        for r, f in zip(day, feats):
            out.append({**r._asdict(), **f})
        for r in day:
            qb_hist[r.qb].append((r.ptd, r.att))
            tm_hist[r.team].append((r.team_ptd, r.pts, r.att))
            df_hist[r.opp].append((r.team_ptd, r.pts))
            season_n[(r.season, r.team)] += 1
            lg.append((r.team_ptd, r.pts))
    X = pd.DataFrame(out).drop(columns=["Index"])
    X["home"] = (X.ha == "H").astype(int)
    X["away"] = (X.ha == "A").astype(int)
    X["has_line"] = X.spread.notna().astype(int)
    X["itt"] = X.total / 2 - X.spread / 2
    # research model.prep
    X["lq_n"] = np.log1p(X.q_n)
    X["conf"] = X.conf.astype(int)
    X["early"] = (X.gnum < 3).astype(int)
    X["post"] = (X.stype == 3).astype(int)
    X["total_f"] = X.total.fillna((X.t_pts + X.o_pts))
    X["spread_f"] = X.spread.fillna(0.0)
    X["itt_f"] = X.total_f / 2 - X.spread_f / 2
    return X


# ---------------------------------------------------------------- features: head to head (research h2h/build_h2h.py)

def _pool(L, season):
    cur = [x for x in L if x[0] == season]
    if len(cur) >= 3:
        return cur, len(cur)
    return cur + [x for x in L if x[0] == season - 1], len(cur)


def _m(L, k):
    v = [x[k] for x in L]
    return float(np.mean(v)) if v else np.nan


H2H_FEATS = ["q_ypg", "q_apg", "q_ypa", "q_cmp", "q_ypg3", "t_prate", "t_ppg", "t_plays", "t_rypg", "t_ypc", "t_sacked",
             "d_pypg", "d_ypa", "d_qbypg", "d_sack", "d_rypg", "d_papg", "d_ppg", "proj", "proj2", "itt", "spread"]


def h2h_features(g):
    qbH, tmH, dfH = defaultdict(list), defaultdict(list), defaultdict(list)
    out = []
    for date, day in _days(g, g["date"]):
        fs = []
        for r in day:
            s = r.season
            q, qn = _pool(qbH[r.qb], s)
            t, tn = _pool(tmH[r.team], s)
            o, on = _pool(dfH[r.opp], s)
            q3 = qbH[r.qb][-3:]
            fs.append(dict(
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
                gnum=len([x for x in tmH[r.team] if x[0] == s])))
        for r, f in zip(day, fs):
            out.append({**r._asdict(), **f})
        for r in day:
            if getattr(r, "upcoming", False):
                continue
            qbH[r.qb].append((r.season, r.q_yds, r.q_att, r.q_cmp))
            tmH[r.team].append((r.season, r.t_patt, r.t_ratt, r.t_ryds, r.pts, r.sackyds, r.q_yds))
            dfH[r.opp].append((r.season, r.t_pyds, r.t_patt, r.q_yds, r.sackyds, r.t_ryds, r.pts))
    X = pd.DataFrame(out).drop(columns=["Index"])
    X["q_new"] = (X.q_any == 0).astype(int)
    X["q_ypg"] = X.q_ypg.fillna(X.t_qbypg)
    X["q_ypg3"] = X.q_ypg3.fillna(X.q_ypg)
    for c in ["q_ypg", "q_apg", "q_ypa", "q_cmp", "q_ypg3", "t_prate", "t_ppg", "t_plays", "t_qbypg", "t_rypg", "t_ypc",
              "t_sacked", "d_pypg", "d_ypa", "d_qbypg", "d_sack", "d_rypg", "d_papg", "d_ppg"]:
        X[c] = X.groupby("season")[c].transform(lambda v: v.fillna(v.mean()))
    X["itt"] = X.total / 2 - X.spread / 2
    lg = X.groupby("season").d_qbypg.transform("mean")
    X["proj"] = X.q_ypg * X.d_qbypg / lg
    X["proj2"] = (X.q_ypg + X.d_qbypg) / 2
    return X


def h2h_pair(X):
    h = X[X.is_home].set_index("eid"); a = X[~X.is_home].set_index("eid")
    common = h.index.intersection(a.index)
    h, a = h.loc[common], a.loc[common]
    G = pd.DataFrame(index=common)
    for c in ["date", "season", "stype", "week", "ha", "conf", "total", "upcoming"]:
        G[c] = h[c]
    G["neutral"] = (h.ha == "N").astype(int)
    G["h_team"], G["a_team"] = h.team_abbr, a.team_abbr
    G["h_qb"], G["a_qb"] = h.qb_name, a.qb_name
    G["h_qid"], G["a_qid"] = h.qb.astype(str), a.qb.astype(str)
    G["h_spread"] = h.spread
    G["early"] = ((h.gnum < 3) | (a.gnum < 3)).astype(int)
    for c in H2H_FEATS:
        G["g_" + c] = h[c] - a[c]
    G["g_d_sack"] = -(h.d_sack - a.d_sack)
    G["g_t_sacked"] = -(h.t_sacked - a.t_sacked)
    G["g_spread"] = -(h.spread - a.spread) / 2
    G["home_site"] = 1 - G.neutral
    return G.reset_index().rename(columns={"index": "eid"})


# ---------------------------------------------------------------- features: moneyline (research ml/build_ml.py)

TF = ["pf", "pa", "ypp_o", "ypp_d", "py_o", "py_d", "ry_o", "ry_d", "to_o", "to_d", "win", "mov"]
ML_DIFF = TF + ["l3_win", "l3_mov", "srs", "q_ypa", "q_tdr", "q_intr", "backup", "newqb", "rest", "ranked", "rankpts"]


def ml_srs(g):
    done = g[~g.upcoming]
    hg = done[done.is_home]
    res = []
    gd, hgd = g.date.dt.date, hg.date.dt.date  # worked once; the same filters as research build_ml.srs
    for date in sorted(gd.unique()):
        day = g[gd == date]; s = int(day.season.iloc[0])
        past = hg[(hgd < date) & (hg.season >= s - 1)]
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


def ml_features(g):
    g = g.sort_values(["date", "eid", "team"]).reset_index(drop=True)
    o = g[["eid", "team", "yds", "plays", "pyds", "ryds", "to"]].rename(columns={"team": "opp", "yds": "o_yds", "plays": "o_plays", "pyds": "o_pyds", "ryds": "o_ryds", "to": "o_to"})
    g = g.merge(o, on=["eid", "opp"], how="left")
    tmH, qbH, starts = defaultdict(list), defaultdict(list), defaultdict(list)
    lastdate = {}
    lgq = []
    out = []
    for date, day in _days(g, g.date.dt.date):
        fs = []
        for r in day:
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
        for r, f in zip(day, fs):
            out.append({**r._asdict(), **f})
        for r in day:
            if r.upcoming: continue
            tmH[r.team].append(dict(season=r.season, pf=r.pts, pa=r.opp_pts, yds=r.yds, plays=r.plays, oyds=r.o_yds, oplays=r.o_plays,
                                    py_o=r.pyds, py_d=r.o_pyds, ry_o=r.ryds, ry_d=r.o_ryds, to_o=r.to, to_d=r.o_to,
                                    win=float(r.pts > r.opp_pts), mov=max(-28, min(28, r.pts - r.opp_pts)), ypp_o=0, ypp_d=0))
            qbH[r.qb].append((r.q_att, r.q_yds, r.q_td, r.q_int)); lgq.append((r.q_att, r.q_yds, r.q_td, r.q_int))
            starts[r.team].append((r.season, r.qb)); lastdate[r.team] = r.date
    X = pd.DataFrame(out).drop(columns=["Index"])
    X = X.merge(ml_srs(g), on=["eid", "team"], how="left")
    for c in TF + ["l3_win", "l3_mov", "srs"]:
        X[c] = X.groupby("season")[c].transform(lambda v: v.fillna(v.quantile(0.25) if c not in ("pa", "ypp_d", "py_d", "ry_d", "to_o") else v.quantile(0.75)))
    return X


def ml_pair(X):
    h = X[X.is_home].set_index("eid"); a = X[~X.is_home].set_index("eid")
    c = h.index.intersection(a.index); h, a = h.loc[c], a.loc[c]
    G = pd.DataFrame(index=c)
    for k in ["date", "season", "stype", "week", "conf", "neutral", "upcoming"]: G[k] = h[k]
    G["h_team"], G["a_team"], G["h_id"], G["a_id"] = h.team_abbr, a.team_abbr, h.team, a.team
    G["h_qb"], G["a_qb"] = h.qb_name, a.qb_name
    G["home"] = (~h.neutral.astype(bool)).astype(int); G["conf"] = h.conf.astype(int)
    G["early"] = ((h.g_n < 3) | (a.g_n < 3)).astype(int)
    for k in ML_DIFF:
        G["d_" + k] = h[k] - a[k]
        G["h_" + k], G["a_" + k] = h[k], a[k]
    return G.reset_index().rename(columns={"index": "eid"})


# ---------------------------------------------------------------- models

def load_model(name):
    return json.load(open(os.path.join(MODELS, "cfb_%s.json" % name)))


def predict(m, F):
    """Standard-scaled logistic regression, as sklearn's predict_proba[:, 1]."""
    x = F[m["feats"]].astype(float)
    if m.get("fillna") is not None:
        x = x.fillna(m["fillna"])
    z = (x.values - np.array(m["mean"])) / np.array(m["scale"])
    return 1.0 / (1.0 + np.exp(-(z @ np.array(m["coef"]) + m["intercept"])))


# ---------------------------------------------------------------- history

def load_hist():
    H = {}
    for k in ("ptd", "h2h", "ml"):
        g = pd.read_parquet(os.path.join(HIST, k + ".parquet"))
        g["date"] = pd.to_datetime(g["date"], utc=True)
        H[k] = g
    H["seen"] = json.load(open(os.path.join(HIST, "seen.json")))
    H["fbs"] = {int(k): set(v) for k, v in json.load(open(os.path.join(HIST, "fbs.json"))).items()}
    return H


def fbs_teams(yr):
    """FBS team ids from the conference rosters (research fetch.fbs)."""
    g = get(CORE.format(yr))
    teams = {}
    for c in (g or {}).get("items", []):
        cc = get(c["$ref"])
        t = get(cc["teams"]["$ref"].split("?")[0] + "?limit=60")
        for x in t["items"]:
            teams[re.search(r"teams/(\d+)", x["$ref"]).group(1)] = cc.get("abbreviation") or cc["name"]
    return sorted(teams)


def season_of(now):
    return now.year if now.month >= 7 else now.year - 1


def scoreboards(season):
    """Every week scoreboard of the season (research fetch.weeks): the events, newest copy."""
    jobs = [(2, w) for w in range(1, 17)] + [(3, 1)]
    urls = [f"{SB}?groups=80&seasontype={st}&dates={season}&limit=300" + (f"&week={w}" if st == 2 else "") for st, w in jobs]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(get, urls))
    if any(r is None for r in res):
        raise SystemExit("cfb_reads: an ESPN scoreboard did not answer; nothing written")
    ev = {}
    for d in res:
        for e in d.get("events", []):
            ev[e["id"]] = e
    return ev


def append_new(H, events, season, dry=False):
    """Fetch and add the FBS vs FBS games finished since the seen list was written."""
    fbs = H["fbs"]
    if season not in fbs:
        ids = fbs_teams(season)
        if not ids:
            raise SystemExit("cfb_reads: no FBS list for %d" % season)
        fbs[season] = set(ids)
    seen = set(H["seen"].get(str(season), []))
    todo, skip = [], []
    for eid, e in events.items():
        c = e["competitions"][0]
        if not c["status"]["type"].get("completed") or eid in seen:
            continue
        if all(x["team"]["id"] in fbs[season] for x in c["competitors"]) and len(c["competitors"]) == 2:
            todo.append(eid)
        else:
            skip.append(eid)  # an FCS side: the models never read it
    rank = {eid: {x["team"]["id"]: (x.get("curatedRank") or {}).get("current", 99) or 99
                  for x in e["competitions"][0]["competitors"]} for eid, e in events.items()}

    def one(eid):
        d = get(SUM.format(eid))
        if not d:
            return eid, None, None
        return eid, d, core_odds(eid)

    with ThreadPoolExecutor(8) as ex:
        got = list(ex.map(one, todo))
    new = {"ptd": [], "h2h": [], "ml": []}
    done = list(skip)
    for eid, d, od in got:
        if d is None:
            continue
        new["ptd"] += parse_ptd(d, od, fbs)
        new["h2h"] += parse_h2h(d, od, fbs)
        new["ml"] += parse_ml(d, rank.get(eid), fbs)
        done.append(eid)
    for k, rows in new.items():
        if rows:
            n = pd.DataFrame(rows)
            n["date"] = pd.to_datetime(n["date"], utc=True)
            g = pd.concat([H[k], n], ignore_index=True).drop_duplicates(["eid", "team"], keep="last")
            H[k] = g.sort_values(["date", "eid", "team"]).reset_index(drop=True)
    H["seen"][str(season)] = sorted(seen | set(done))
    print("history: %d new FBS vs FBS games (%d team rows), %d skipped, %d failed"
          % (len(done) - len(skip), len(new["ptd"]), len(skip), len(todo) - (len(done) - len(skip))), file=sys.stderr)
    if not dry and done:
        save_hist(H)
    return H


def save_hist(H):
    for k in ("ptd", "h2h", "ml"):
        H[k].to_parquet(os.path.join(HIST, k + ".parquet"), compression="zstd", index=False)
    json.dump(H["seen"], open(os.path.join(HIST, "seen.json"), "w"), separators=(",", ":"))
    json.dump({str(k): sorted(v) for k, v in sorted(H["fbs"].items())}, open(os.path.join(HIST, "fbs.json"), "w"), separators=(",", ":"))


# ---------------------------------------------------------------- the board's card QB

def board_qbs():
    """(eid, "away"|"home") -> (ESPN id, name, board abbr) from the page's CFB array
       (research boardqb.py). Matched by side, not by the written abbr: ESPN writes
       Jacksonville State JXST, the board JVST, and a name is not an identifier."""
    try:
        import pagefile
        cfb = json.loads(re.search(r"\bCFB\s*=\s*(\[.*?\]);\n", pagefile.read(), re.S).group(1))
    except Exception as e:
        print("cfb_reads: no board QBs (%s); last starters only" % e, file=sys.stderr)
        return {}
    out = {}
    for g in cfb:
        out[(str(g[1]), "away")] = (str(g[6] or ""), g[5], g[3])
        out[(str(g[1]), "home")] = (str(g[8] or ""), g[7], g[4])
    return out


# ---------------------------------------------------------------- the slate

def slate(events, fbs, lo, hi, fetch_odds=True):
    """research week.upcoming over the given events: two rows per FBS vs FBS game
       still to kick (home first), with ESPN's line (scoreboard odds, else core odds)."""
    rows, games = [], {}
    for e in sorted(events.values(), key=lambda e: (e["competitions"][0]["date"], e["id"])):
        c = e["competitions"][0]
        if c["status"]["type"].get("state") != "pre":
            continue
        kick = pd.Timestamp(c["date"])
        if kick.tzinfo is None:
            kick = kick.tz_localize("UTC")
        if not (lo <= kick <= hi):
            continue
        cs = c["competitors"]
        season = int((e.get("season") or {}).get("year") or kick.year)
        if len(cs) != 2 or not all(x["team"]["id"] in fbs.get(season, set()) for x in cs):
            continue
        home = next(x for x in cs if x["homeAway"] == "home"); away = next(x for x in cs if x["homeAway"] == "away")
        ha_, aa_ = home["team"]["abbreviation"], away["team"]["abbreviation"]
        sp, ou = np.nan, np.nan
        od = (c.get("odds") or [None])[0]
        if od and od.get("details"):
            sp, ou = line([dict(p=od.get("provider", {}).get("name"), spread=od.get("spread"), ou=od.get("overUnder"), details=od.get("details"))], ha_, aa_)
        if sp != sp and fetch_odds:
            sp, ou = line(core_odds(e["id"]), ha_, aa_)
        st = int((e.get("season") or {}).get("type") or 2)
        wk = int((e.get("week") or {}).get("number") or 0)
        games[e["id"]] = dict(away=aa_, home=ha_, kick=c["date"])
        for t in (home, away):
            o = away if t is home else home
            rows.append(dict(eid=e["id"], date=c["date"], season=season, stype=st, week=wk if st == 2 else 0,
                             team=t["team"]["id"], team_abbr=t["team"]["abbreviation"], opp=o["team"]["id"], opp_abbr=o["team"]["abbreviation"],
                             ha="N" if c.get("neutralSite") else ("H" if t is home else "A"), conf=bool(c.get("conferenceCompetition")),
                             spread=(sp if t is home else -sp) if sp == sp else np.nan, total=ou,
                             rank=(t.get("curatedRank") or {}).get("current", 99) or 99,
                             is_home=t is home, neutral=bool(c.get("neutralSite"))))
    U = pd.DataFrame(rows)
    if len(U):
        U["date"] = pd.to_datetime(U.date, utc=True)
    return U, games


def _board_qb(U, last, board):
    """Last FBS starter, then the board's card QB over him (research week.py / boardqb.py)."""
    U = U.copy()
    U["qb"] = U.team.map(last.qb); U["qb_name"] = U.team.map(last.qb_name)
    for i, r in U.iterrows():
        b = board.get((str(r.eid), "home" if r.is_home else "away"))
        if b and b[0] and str(b[0]) != str(r.qb):
            U.at[i, "qb"], U.at[i, "qb_name"] = str(b[0]), b[1]
    return U


def score_ptd(H, U, board, M1, M2):
    g = H["ptd"].copy()
    last = g.sort_values("date").groupby("team").tail(1).set_index("team")
    V = _board_qb(U, last, board)
    V = V[V.qb.notna()]
    if V.empty:
        return pd.DataFrame()
    V = V[["eid", "date", "season", "stype", "week", "team", "team_abbr", "opp", "opp_abbr", "ha", "conf", "spread", "total", "qb", "qb_name"]].copy()
    for c in ("att", "ptd", "team_ptd", "pts", "opp_pts"):
        V[c] = 0
    V["upcoming"] = True
    g["upcoming"] = False
    X = ptd_features(pd.concat([g, V], ignore_index=True).sort_values(["date", "eid", "team"]))
    X = X[X.upcoming.astype(bool)].copy()
    X["p1"], X["p2"] = predict(M1, X), predict(M2, X)
    X["take1"] = (X.p1 >= M1["rule"]["p"]) & (X.has_line == 1)
    X["take2"] = (X.p2 >= M2["rule"]["p"]) & (X.has_line == 1)
    return X


def score_h2h(H, U, board, M):
    tg = H["h2h"].copy()
    last = tg.sort_values("date").groupby("team").tail(1).set_index("team")
    V = _board_qb(U, last, board)
    V["is_home"] = V.ha.eq("H") | (V.ha.eq("N") & ~V.duplicated("eid"))
    V = V[V.qb.notna()]
    V = V[V.groupby("eid").eid.transform("size") == 2]
    if V.empty:
        return pd.DataFrame()
    V = V[["eid", "date", "season", "stype", "week", "team", "team_abbr", "opp", "opp_abbr", "ha", "conf", "spread", "total", "qb", "qb_name", "is_home"]].copy()
    for c in ["q_att", "q_yds", "q_cmp", "t_patt", "t_pyds", "t_net", "t_ratt", "t_ryds", "pts", "opp_pts", "sackyds"]:
        V[c] = 0
    V["upcoming"] = True
    tg["upcoming"] = False
    X = h2h_features(pd.concat([tg, V], ignore_index=True).sort_values(["date", "eid", "team"]).reset_index(drop=True))
    G = h2h_pair(X[X.upcoming.astype(bool)])
    G["p_home"] = predict(M, G)
    G["chance"] = np.maximum(G.p_home, 1 - G.p_home)
    G["take"] = (G.chance - 0.5 >= M["rule"]["edge"]) & G.h_spread.notna()
    return G


ML_TEXT = {"pf": ("Points per game", "%.1f"), "pa": ("Points allowed per game", "%.1f"), "ypp_o": ("Yards per play", "%.1f"),
           "ypp_d": ("Yards per play allowed", "%.1f"), "py_o": ("Passing yards per game", "%.0f"), "py_d": ("Passing yards allowed per game", "%.0f"),
           "ry_o": ("Rushing yards per game", "%.0f"), "ry_d": ("Rushing yards allowed per game", "%.0f"), "to_o": ("Turnovers per game", "%.1f"),
           "to_d": ("Takeaways per game", "%.1f"), "win": ("Win %%", "pct"), "mov": ("Average margin", "%+.1f"),
           "l3_win": ("Last 3 games, win %%", "pct"), "l3_mov": ("Last 3 games, average margin", "%+.1f"), "srs": ("Margin rating", "%+.1f"),
           "q_ypa": ("QB yards per attempt", "%.1f"), "q_tdr": ("QB TD rate", "pct1"), "q_intr": ("QB INT rate", "pct1"),
           "rest": ("Days of rest", "%.0f"), "rankpts": ("AP rank", "rank")}


def _fmt(v, f):
    if f == "pct":
        return "%d%%" % round(100 * v)
    if f == "pct1":
        return "%.1f%%" % (100 * v)
    if f == "rank":
        return ("#%d" % (26 - v)) if v > 0 else "unranked"
    return f % v


def ml_why(r, M, home_pick):
    """The four inputs that push hardest toward the pick, in plain words."""
    c = np.array(M["coef"]) * (r[M["feats"]].astype(float).fillna(0).values - np.array(M["mean"])) / np.array(M["scale"])
    c = c if home_pick else -c
    pk, ot = (r.h_team, r.a_team) if home_pick else (r.a_team, r.h_team)
    out = []
    for i in np.argsort(-c):
        if c[i] <= 0 or len(out) == 4:
            break
        f = M["feats"][i]
        if f == "home":
            out.append("%s at home" % r.h_team if home_pick else None); continue
        k = f[2:]
        if k in ("backup", "newqb"):
            side = "a" if home_pick else "h"
            if r[side + "_" + k]:
                out.append("%s is starting a backup QB" % ot if k == "backup" else "%s's QB has no FBS start yet" % ot)
            continue
        if k == "ranked":
            continue
        if k in ML_TEXT:
            nm, ff = ML_TEXT[k]
            pv, ov = (r["h_" + k], r["a_" + k]) if home_pick else (r["a_" + k], r["h_" + k])
            if pv == pv and ov == ov:
                out.append("%s: %s %s, %s %s" % (nm.replace("%%", "%"), pk, _fmt(pv, ff), ot, _fmt(ov, ff)))
    return [x for x in out if x]


def score_ml(H, U, board, M, season):
    g = H["ml"]; g = g[g.season >= season - 3].copy()
    g["upcoming"] = False
    last = g.sort_values("date").groupby("team").tail(1).set_index("team")
    V = U[U.team.isin(last.index)].copy()
    V = _board_qb(V, last, board)
    V = V[["eid", "date", "season", "week", "team", "team_abbr", "opp", "opp_abbr", "is_home", "neutral", "conf", "rank", "qb", "qb_name"]].copy()
    V["stype"] = 2
    V["upcoming"] = True
    if V.empty:
        return pd.DataFrame()
    hist = g[~g.eid.isin(V.eid)]
    X = ml_features(pd.concat([hist, V], ignore_index=True))
    G = ml_pair(X[X.upcoming.astype(bool)])
    G["p"] = predict(M, G)
    G["conf_pct"] = (100 * np.maximum(G.p, 1 - G.p)).round(1)
    G["take"] = G.conf_pct >= M["rule"]["pct"]
    return G


def score(H, U, games, board, season):
    """All four reads for the slate U -> {eid: read}."""
    M1, M2, MH, MM = load_model("ptd1"), load_model("ptd2"), load_model("h2h"), load_model("ml")
    reads = {eid: dict(g, ml=None, h2h=None, ptd={}) for eid, g in games.items()}
    if U.empty:
        return reads
    P = score_ptd(H, U, board, M1, M2)
    for r in P.itertuples():
        reads[r.eid]["ptd"][str(r.qb)] = dict(name=r.qb_name, team=r.team_abbr, p1=round(float(r.p1), 6), take1=bool(r.take1),
                                              p2=round(float(r.p2), 6), take2=bool(r.take2), has_line=bool(r.has_line))
    G = score_h2h(H, U, board, MH)
    for r in G.itertuples():
        hp = r.p_home > 0.5
        reads[r.eid]["h2h"] = dict(pick=r.h_qb if hp else r.a_qb, pick_id=r.h_qid if hp else r.a_qid, team=r.h_team if hp else r.a_team,
                                   p=round(float(r.chance), 6), call="take" if r.take else None,
                                   has_line=bool(r.h_spread == r.h_spread),
                                   qbs=[[r.a_qid, r.a_qb], [r.h_qid, r.h_qb]])
    G = score_ml(H, U, board, MM, season)
    for _, r in G.iterrows():
        hp = r.p >= .5
        reads[r.eid]["ml"] = dict(pick=r.h_team if hp else r.a_team, p=round(float(max(r.p, 1 - r.p)), 6),
                                  call="take" if r["take"] else None, why=ml_why(r, MM, hp),
                                  qbs=[r.a_qb, r.h_qb])
    return board_abbrs(reads, board)


def board_abbrs(reads, board):
    """Write each club as the board writes it (its CFB row's r[3]/r[4]), so
       suggest.py's away/home test holds when ESPN spells a club differently."""
    for eid, r in reads.items():
        sw = {}
        for side in ("away", "home"):
            b = board.get((str(eid), side))
            if b and b[2] and b[2] != r[side]:
                sw[r[side]] = b[2]
        if not sw:
            continue
        f = lambda a: sw.get(a, a)
        r["away"], r["home"] = f(r["away"]), f(r["home"])
        if r.get("ml"):
            r["ml"]["pick"] = f(r["ml"]["pick"])
            r["ml"]["why"] = [re.sub(r"\b(%s)\b" % "|".join(map(re.escape, sw)), lambda m: sw[m.group(1)], w) for w in r["ml"]["why"]]
        if r.get("h2h"):
            r["h2h"]["team"] = f(r["h2h"]["team"])
        for q in r.get("ptd", {}).values():
            q["team"] = f(q["team"])
    return reads


def show(eid, r):
    bits = []
    m = r.get("ml")
    if m:
        bits.append("ML %s %.1f%%%s" % (m["pick"], 100 * m["p"], " TAKE" if m["call"] else ""))
    h = r.get("h2h")
    if h:
        bits.append("H2H %s %.1f%%%s" % (h["pick"], 100 * h["p"], " TAKE" if h["call"] else ("" if h["has_line"] else " (no line)")))
    for q in r.get("ptd", {}).values():
        bits.append("%s 1+ %.1f%%%s 2+ %.1f%%%s%s" % (q["name"], 100 * q["p1"], " TAKE" if q["take1"] else "",
                                                   100 * q["p2"], " TAKE" if q["take2"] else "", "" if q["has_line"] else " (no line)"))
    return "%s %s at %s %s | %s" % (eid, r["away"], r["home"], r["kick"][5:16].replace("T", " "), " | ".join(bits))


def main():
    dry = "--dry" in sys.argv
    t0 = time.time()
    now = pd.Timestamp.now(tz="UTC")
    season = season_of(now)
    H = load_hist()
    events = scoreboards(season)
    H = append_new(H, events, season, dry=dry)
    U, games = slate(events, H["fbs"], now, now + WINDOW)
    reads = score(H, U, games, board_qbs(), season)
    # a game under way keeps the read it had until two days after kickoff
    try:
        old = json.load(open(OUT)).get("reads", {})
    except Exception:
        old = {}
    for eid, r in old.items():
        k = pd.Timestamp(r.get("kick"))
        if eid not in reads and k <= now < k + KEEP:
            reads[eid] = r
    reads = dict(sorted(reads.items(), key=lambda kv: (kv[1]["kick"], kv[0])))
    for eid, r in reads.items():
        print(show(eid, r))
    n = {"ml": sum(1 for r in reads.values() if (r.get("ml") or {}).get("call")),
         "h2h": sum(1 for r in reads.values() if (r.get("h2h") or {}).get("call")),
         "1+": sum(q["take1"] for r in reads.values() for q in r.get("ptd", {}).values()),
         "2+": sum(q["take2"] for r in reads.values() for q in r.get("ptd", {}).values())}
    print("%d games; takes: ML %d, H2H %d, 1+ PTD %d, 2+ PTD %d; %.0fs" % (len(reads), n["ml"], n["h2h"], n["1+"], n["2+"], time.time() - t0),
          file=sys.stderr)
    if dry:
        return
    out = {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
           "rules": {"ml": "model 75%+", "h2h": "model 83.2%+ with a line", "ptd1": "model 90%+ with an ESPN line",
                     "ptd2": "model 70%+ with an ESPN line"},
           "reads": reads}
    tmp = OUT + ".tmp"
    json.dump(out, open(tmp, "w"), indent=1)
    os.replace(tmp, OUT)


if __name__ == "__main__":
    main()
