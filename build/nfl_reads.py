"""The three tested NFL reads, for every game in the next eight days, every sweep.

   1. The moneyline read (data/ml_reads.json): a logistic regression on the
      home-minus-away pre-game profile -- team EPA per play (offense, defense,
      pass, rush), success rate, sacks, turnovers, points for and against, win
      %, last-3 form, games played, rest, division game, a backup-QB flag, and
      the starting passer's own EPA per dropback and CPOE over his last 16
      games -- trained on 2016-21 only, no odds (research/nfl_ml). Blind: 76%
      (2022-23, 88 games), 80% (2024-25, 118), 90% (2026 Wk1-4, 10) at 75%+.
      TAKE = model 75+, or model 60+ with the book's no-vig % 65+ on the same
      team; LEAN = model 60-74; under 60 no call. The book is information and
      never vetoes. "Won before" is the blind 2022-26 hit rate of the model
      band x book band the game falls in (frozen in data/models/nfl_ml.json).
   2. The 1+ passing TD model (data/ptd_reads.json): a logistic regression on
      the passer's last 16 games (TD passes, hit rate, EPA, dropbacks, streak),
      his team's last 8 (red-zone trips, TD drives, TD passes) and the
      defense's last 8 allowed, home, dome, division; trained 2016-21. Blind:
      80+ hit 84-86%, 75-79 75%, under 75 63-72%. The page words it with the
      book: TAKE = model 80+ and book 85%+.
   3. The touchdown detail (data/td_reads.json): the 1+ model's number and
      reasons, the team's projected points from the game total and spread, and
      the 2+ passing TD rules that held 75%+ blind: projected 29.5+ (80%), heavy
      1+ price (82%+) with a 46+ total and favored by 7.5+ (87%), projected 27+
      with a pass-attempts line of 33.5+ (75%).

   The passer is the board's card QB: site/depth.json's starter (the card
   follows it), never last game's starter. Season-to-date numbers come from
   nflverse play-by-play: past seasons are frozen in data/nfl_reads_hist.json
   (built once, rebuilt only when a season is missing), this season is kept in
   data/nfl_reads_cache.json and rebuilt when six hours old. Schedule, rest,
   totals and spreads come from nflverse's games.csv each run; prices from
   site/prices.json (DraftKings); the attempts line from BettingPros
   (DraftKings, else FanDuel), only for a team projected 27+.

   A game that has kicked off keeps the read it had, for two days. The
   passer files are keyed by ESPN id, one read a man: the soonest game he has
   not started yet wins; by_game holds every game's reads by id.

   Models live in data/models/nfl_ml.json and nfl_ptd1.json as plain
   coefficients, evaluated with numpy (research/nfl_reads has how they were
   made and checked). Needs pandas, numpy, pyarrow and curl_cffi.

   Usage:  python3 nfl_reads.py [--dry] [--rebuild] [--hist]
             --dry      print the reads, write nothing
             --rebuild  rebuild this season's cache now
             --hist     rebuild the frozen past seasons
"""
import io
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
DATA = os.path.join(D, "data")
OUT_ML = os.path.join(DATA, "ml_reads.json")
OUT_PTD = os.path.join(DATA, "ptd_reads.json")
OUT_TD = os.path.join(DATA, "td_reads.json")
HIST = os.path.join(DATA, "nfl_reads_hist.json")
CACHE = os.path.join(DATA, "nfl_reads_cache.json")
M_ML = os.path.join(DATA, "models", "nfl_ml.json")
M_PTD = os.path.join(DATA, "models", "nfl_ptd1.json")
DRY = "--dry" in sys.argv
NFV = "https://github.com/nflverse/nflverse-data/releases/download/"
GAMES = "https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv"
BP = "https://api.bettingpros.com/v3/"
BPKEY = {"x-api-key": "CHi8Hy5CEE4khd46XNYL23dCFX96oUdw6qOt1Dnh"}   # BettingPros' own public site key
B2G = {"LAR": "LA", "WSH": "WAS"}                 # board club -> nflverse club
G2B = {v: k for k, v in B2G.items()}
BPT = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}    # BettingPros club -> nflverse club
TEAMN = {'ARI': 'Cardinals', 'ATL': 'Falcons', 'BAL': 'Ravens', 'BUF': 'Bills', 'CAR': 'Panthers', 'CHI': 'Bears',
         'CIN': 'Bengals', 'CLE': 'Browns', 'DAL': 'Cowboys', 'DEN': 'Broncos', 'DET': 'Lions', 'GB': 'Packers',
         'HOU': 'Texans', 'IND': 'Colts', 'JAX': 'Jaguars', 'KC': 'Chiefs', 'LV': 'Raiders', 'LAC': 'Chargers',
         'LA': 'Rams', 'LAR': 'Rams', 'MIA': 'Dolphins', 'MIN': 'Vikings', 'NE': 'Patriots', 'NO': 'Saints',
         'NYG': 'Giants', 'NYJ': 'Jets', 'PHI': 'Eagles', 'PIT': 'Steelers', 'SF': '49ers', 'SEA': 'Seahawks',
         'TB': 'Buccaneers', 'TEN': 'Titans', 'WAS': 'Commanders', 'WSH': 'Commanders'}
PBP_COLS = ['season', 'week', 'season_type', 'game_id', 'posteam', 'defteam', 'epa', 'success', 'pass', 'rush', 'sack',
            'interception', 'fumble_lost', 'qb_epa', 'passer_player_id', 'qb_dropback', 'cpoe', 'pass_touchdown',
            'yardline_100', 'fixed_drive', 'fixed_drive_result']
ML_F = ['o_epa', 'o_sr', 'o_pepa', 'o_repa', 'o_to', 'o_sack', 'd_epa', 'd_sr', 'd_pepa', 'd_repa', 'd_to', 'd_sack', 'pf', 'pa', 'win']

try:
    from curl_cffi import requests as _rq
    S = _rq.Session(impersonate="chrome")
except Exception:          # plain requests will do for GitHub
    import requests as _rq
    S = _rq.Session()


def get(url, **kw):
    for i in range(3):
        try:
            r = S.get(url, timeout=90, **kw)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    raise RuntimeError("no answer from " + url.split("?")[0])


def num(x):
    return float(str(x).replace("−", "-").replace("+", ""))


def ip(o):
    return -o / (-o + 100) if o < 0 else 100 / (o + 100)


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def fin(x):
    """a plain float, or None for a missing number"""
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def season_of(now):
    return now.year if now.month >= 3 else now.year - 1


# ------------------------------------------------------------ play-by-play

def pbp(year):
    local = os.path.join(os.environ.get("NFLV_DIR", "/nonexistent"), "pbp_%d.parquet" % year)
    if os.path.exists(local):          # a folder of already-downloaded seasons, for building the history
        return pd.read_parquet(local, columns=PBP_COLS)
    raw = get(NFV + "pbp/play_by_play_%d.parquet" % year).content
    return pd.read_parquet(io.BytesIO(raw), columns=PBP_COLS)


def aggregate(P):
    """The per-game numbers every feature is built from, exactly as the
       research built them (research/nfl_ml/build.py, qb.py; nfl_reads/build_ptd.py)."""
    P = P[P.season_type == "REG"]
    # team per week, offense and defense (moneyline)
    A = P[P.posteam.notna() & P.epa.notna() & ((P["pass"] == 1) | (P.rush == 1))].copy()
    A["to"] = A.interception.fillna(0) + A.fumble_lost.fillna(0)
    A["pepa"] = np.where(A["pass"] == 1, A.epa, np.nan)
    A["repa"] = np.where(A.rush == 1, A.epa, np.nan)
    off = A.groupby(["season", "week", "posteam"]).agg(o_epa=("epa", "mean"), o_sr=("success", "mean"), o_pepa=("pepa", "mean"),
                                                      o_repa=("repa", "mean"), o_to=("to", "sum"), o_sack=("sack", "mean")).reset_index().rename(columns={"posteam": "team"})
    dfn = A.groupby(["season", "week", "defteam"]).agg(d_epa=("epa", "mean"), d_sr=("success", "mean"), d_pepa=("pepa", "mean"),
                                                      d_repa=("repa", "mean"), d_to=("to", "sum"), d_sack=("sack", "mean")).reset_index().rename(columns={"defteam": "team"})
    W = off.merge(dfn, on=["season", "week", "team"])
    # passer per week, dropbacks only (moneyline)
    q = P[(P.qb_dropback == 1) & P.passer_player_id.notna()]
    QM = q.groupby(["passer_player_id", "season", "week"]).agg(qe=("qb_epa", "mean"), cp=("cpoe", "mean"), n=("qb_epa", "size")).reset_index()
    # passer per game (touchdowns)
    QP = P[P.passer_player_id.notna()].groupby(["season", "week", "game_id", "posteam", "passer_player_id"]).agg(
        db=("qb_dropback", "sum"), ptd=("pass_touchdown", "sum"), qe=("qb_epa", "mean")).reset_index()
    # team drives per game (touchdowns)
    d = P.dropna(subset=["fixed_drive"]).groupby(["season", "week", "game_id", "posteam", "fixed_drive"]).agg(
        rz=("yardline_100", lambda x: (x <= 20).any()), res=("fixed_drive_result", "first")).reset_index()
    d["td"] = d.res.eq("Touchdown")
    TO = d.groupby(["season", "week", "game_id", "posteam"]).agg(drv=("td", "size"), rz=("rz", "sum"), tdd=("td", "sum")).reset_index()
    pt = P.groupby(["season", "week", "game_id", "posteam"]).agg(team_ptd=("pass_touchdown", "sum"), opp=("defteam", "first")).reset_index()
    TO = TO.merge(pt, on=["season", "week", "game_id", "posteam"])
    TO["rz"] = TO.rz.astype(float)
    TO["tdd"] = TO.tdd.astype(float)
    return {"W": W, "QM": QM, "QP": QP, "TO": TO}


def to_js(T):
    out = {}
    for k, df in T.items():
        rows = [[None if (isinstance(v, float) and v != v) else (v.item() if hasattr(v, "item") else v) for v in r] for r in df.itertuples(index=False)]
        out[k] = {"cols": list(df.columns), "rows": rows}
    return out


def from_js(J):
    T = {}
    for k, v in J.items():
        df = pd.DataFrame(v["rows"], columns=v["cols"])
        for c in df.columns:
            if c not in ("team", "game_id", "posteam", "passer_player_id", "opp"):
                df[c] = pd.to_numeric(df[c], errors="coerce")
        T[k] = df
    return T


def build_hist(season):
    """Every past season 2016 -> season-1, per game. Team tables only for the
       last season (the moneyline blends it in early; the TD reads look back 8
       games); passer tables for all, since a man's last 16 can go back years."""
    parts = []
    for y in range(2016, season):
        print("hist: pbp %d" % y)
        parts.append(aggregate(pbp(y)))
    H = {k: pd.concat([p[k] for p in parts], ignore_index=True) for k in parts[0]}
    for k in ("W", "TO"):
        H[k] = H[k][H[k].season == season - 1].reset_index(drop=True)
    return {"seasons": [2016, season - 1], "tables": to_js(H)}


def hist(season):
    try:
        J = json.load(open(HIST))
        if J["seasons"][1] == season - 1 and "--hist" not in sys.argv:
            return from_js(J["tables"])
    except Exception:
        pass
    J = build_hist(season)
    if not DRY:
        json.dump(J, open(HIST, "w"), separators=(",", ":"))
    return from_js(J["tables"])


def cache(season):
    """This season's tables and the ESPN -> nflverse passer ids, six hours."""
    now = datetime.now(timezone.utc)
    try:
        C = json.load(open(CACHE))
        age = now - datetime.strptime(C["at"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        if age < timedelta(hours=6) and C.get("season") == season and "--rebuild" not in sys.argv:
            return from_js(C["tables"]), C["e2g"]
    except Exception:
        pass
    print("cache: rebuilding from nflverse")
    T = aggregate(pbp(season))
    PL = pd.read_csv(io.BytesIO(get(NFV + "players/players.csv").content), usecols=["gsis_id", "espn_id", "position"], dtype=str)
    PL = PL[PL.espn_id.notna() & PL.gsis_id.notna() & (PL.position == "QB")]
    e2g = {str(int(float(e))): g for e, g in zip(PL.espn_id, PL.gsis_id)}
    C = {"at": now.strftime("%Y-%m-%dT%H:%MZ"), "season": season, "e2g": e2g, "tables": to_js(T)}
    if not DRY:
        json.dump(C, open(CACHE, "w"), separators=(",", ":"))
    return from_js(C["tables"]), e2g


# ------------------------------------------------------------ the features

class Book:
    """Every table one read needs, past seasons and this one together."""

    def __init__(self, H, C, G, season):
        self.S = season
        self.G = G
        Gr = G[(G.season >= 2016) & G.home_score.notna() & (G.game_type == "REG")]
        rows = []
        for r in Gr.itertuples():
            for t, pf, pa in ((r.home_team, r.home_score, r.away_score), (r.away_team, r.away_score, r.home_score)):
                rows.append(dict(season=r.season, week=r.week, team=t, pf=pf, pa=pa, win=float(pf > pa) + 0.5 * (pf == pa)))
        W = pd.concat([H["W"], C["W"]], ignore_index=True).merge(pd.DataFrame(rows), on=["season", "week", "team"], how="left")
        self.W = W.sort_values(["team", "season", "week"])
        QM = pd.concat([H["QM"], C["QM"]], ignore_index=True).sort_values(["season", "week"])
        QM["k"] = QM.season * 100 + QM.week
        self.QMG = {q: g for q, g in QM.groupby("passer_player_id")}
        QP = pd.concat([H["QP"], C["QP"]], ignore_index=True).sort_values(["season", "week"])
        TO = pd.concat([H["TO"], C["TO"]], ignore_index=True)
        DA = TO.rename(columns={"posteam": "x", "opp": "def"}).groupby(["season", "week", "def"]).agg(
            a_ptd=("team_ptd", "sum"), a_rz=("rz", "sum"), a_tdd=("tdd", "sum"), a_drv=("drv", "sum")).reset_index()
        TO = TO.sort_values(["season", "week"])
        DA = DA.sort_values(["season", "week"])
        self.QPG = {q: g for q, g in QP.groupby("passer_player_id")}
        self.TG = {t: g for t, g in TO.groupby("posteam")}
        self.DG = {t: g for t, g in DA.groupby("def")}
        # every listed starter, for the backup flag
        self.starts = {}
        for r in G[G.game_type == "REG"].sort_values(["season", "week"]).itertuples():
            for t, q in ((r.home_team, r.home_qb_id), (r.away_team, r.away_qb_id)):
                self.starts.setdefault((t, r.season), []).append((r.week, q))

    # -- moneyline (research/nfl_ml/build.py prof, qb.py qprof, boxes.py backup)
    def prof(self, team, season, week):
        W = self.W
        cur = W[(W.team == team) & (W.season == season) & (W.week < week)]
        prev = W[(W.team == team) & (W.season == season - 1)]
        if len(cur) >= 4 or prev.empty:
            base = cur
        else:
            base = pd.concat([prev.tail(8 - 2 * len(cur)) if len(cur) < 4 else prev.iloc[0:0], cur])
        if base.empty:
            return {k: np.nan for k in ML_F} | {"g": 0}
        v = {k: base[k].mean() for k in ML_F}
        v["g"] = len(cur)
        v["l3_win"] = cur.tail(3).win.mean() if len(cur) else np.nan
        v["l3_pd"] = (cur.tail(3).pf - cur.tail(3).pa).mean() if len(cur) else np.nan
        return v

    def qprof(self, q, s, w):
        g = self.QMG.get(q)
        if g is None:
            return (np.nan, np.nan, 0)
        p = g[g.k < s * 100 + w].tail(16)
        p = p[p.n >= 10]
        if p.empty:
            return (np.nan, np.nan, 0)
        return ((p.qe * p.n).sum() / p.n.sum(), p.cp.mean(), len(p))

    def backup(self, t, s, w, q):
        p = [x for wk, x in self.starts.get((t, s), []) if wk < w and x == x]
        if len(p) < 2:
            p = [x for wk, x in self.starts.get((t, s - 1), []) if x == x][-8:] + p
        if not p:
            return 0
        # the usual starter: most starts; a tie goes to the one who started last
        usual = max(set(p), key=lambda x: (p.count(x), max(i for i, y in enumerate(p) if y == x)))
        return int(q != usual and p.count(usual) >= 3)

    # -- touchdowns (research/nfl_reads/build_ptd.py)
    @staticmethod
    def last(g, s, w, n):
        if g is None:
            return None
        k = g.season * 100 + g.week
        return g[k < s * 100 + w].tail(n)


def ml_read(bk, M, g, aq, hq):
    """One game's moneyline read: (p home wins, features home, away, why)."""
    S, WK = int(g.season), int(g.week)
    h, a = bk.prof(g.home_team, S, WK), bk.prof(g.away_team, S, WK)
    for side, team, q in ((h, g.home_team, hq), (a, g.away_team, aq)):
        qe, cp, qn = bk.qprof(q, S, WK)
        side.update(qe=qe, cp=cp, qn=qn, backup=bk.backup(team, S, WK, q))
    cols = M["cols"]
    z = {c: h.get(c, np.nan) - a.get(c, np.nan) for c in cols if c not in ("rest", "div")}
    hr, ar = g.home_rest, g.away_rest
    z["rest"] = (hr or 0) - (ar or 0)
    z["div"] = g.div_game
    Z = np.array([float(z[c]) for c in cols])
    Z = np.where(np.isnan(Z), M["fill"], Z)
    contrib = np.array(M["coef"]) * Z
    p = 1 / (1 + math.exp(-(float(contrib.sum()) + M["intercept"])))
    return p, h, a, dict(zip(cols, contrib))


LAB = {'qe': ('QB play (EPA per dropback)', '{:+.2f}'), 'o_sr': ('Offense success rate', '{:.0%}'), 'd_epa': ('Defense, EPA allowed per play', '{:+.2f}'),
       'd_pepa': ('Pass defense, EPA allowed', '{:+.2f}'), 'l3_win': ('Last 3 games, win %', '{:.0%}'), 'backup': ('Backup QB starting', '{:.0f}'),
       'o_sack': ('Sacks taken per dropback', '{:.1%}'), 'win': ('Win % this season', '{:.0%}'), 'o_pepa': ('Passing offense (EPA)', '{:+.2f}'),
       'o_epa': ('Offense EPA per play', '{:+.2f}'), 'd_sr': ('Defense success rate allowed', '{:.0%}'), 'o_repa': ('Rushing offense (EPA)', '{:+.2f}'),
       'pf': ('Points per game', '{:.1f}'), 'pa': ('Points allowed per game', '{:.1f}'), 'o_to': ('Turnovers per game', '{:.1f}'),
       'd_to': ('Takeaways per game', '{:.1f}'), 'd_sack': ('Sacks per dropback', '{:.1%}'), 'l3_pd': ('Last 3 games, point margin', '{:+.1f}')}


def ml_why(p, h, a, contrib, home, away):
    """the four biggest pushes toward the pick, with both clubs' numbers (ml/week.py)"""
    sgn = 1 if p >= 0.5 else -1
    why = []
    for k, v in sorted(contrib.items(), key=lambda kv: -abs(kv[1])):
        if k not in LAB or v == 0:
            continue
        lab, f = LAB[k]
        hh, aa = h.get(k), a.get(k)
        if hh is None or aa is None or hh != hh or aa != aa:
            continue
        pk, ot = (home, away) if p >= 0.5 else (away, home)
        pv, ov = (hh, aa) if p >= 0.5 else (aa, hh)
        if k == "backup":
            if ov == 1 and pv == 0:
                txt = "%s is starting a backup QB" % ot
            else:
                continue
        else:
            txt = "%s: %s %s, %s %s" % (lab, pk, f.format(pv), ot, f.format(ov))
        if v * sgn > 0:
            why.append(txt)
    return why[:4]


def won_before(M, mod, onpick, agree):
    """blind 2022-26 hit rate for this model band x book band (Oct 7, 2026)"""
    if onpick is None:
        return None, 0
    mv, ov = mod / 100, onpick / 100
    if not agree and 0.70 <= mv < 0.75 and ov < 0.60:
        return tuple(M["disagree_70_75"])        # as shown for SF @ SEA, Oct 8
    for t in M["won_before"]:
        if t["model"][0] <= mv < t["model"][1] and t["book"][0] <= ov < t["book"][1]:
            return t["won"], t["n"]
    return None, 0


def ptd_feats(bk, qb, team, opp, home, S, WK, roof, div):
    """the 1+ model's inputs (ptd/week.py); wind is not read for a coming game"""
    q = bk.last(bk.QPG.get(qb), S, WK, 16)
    t = bk.last(bk.TG.get(team), S, WK, 8)
    d = bk.last(bk.DG.get(opp), S, WK, 8)
    row = dict(home=home, dome=int(roof in ("dome", "closed")), windy=0, div=div)
    q2 = None
    if q is not None and len(q):
        q2 = q[q.db >= 10]
        row.update(q_g=len(q2), q_tdpg=q2.ptd.mean(), q_hit=(q2.ptd >= 1).mean(), q_hit8=(q2.tail(8).ptd >= 1).mean(),
                   q_qe=(q2.qe * q2.db).sum() / max(q2.db.sum(), 1), q_db=q2.db.mean(), q_streak=int(((q2.ptd >= 1)[::-1].cumprod()).sum()))
    if t is not None and len(t):
        row.update(t_rz=t.rz.mean(), t_tdd=t.tdd.mean(), t_ptd=t.team_ptd.mean(), t_rzconv=t.tdd.sum() / max(t.rz.sum(), 1))
    if d is not None and len(d):
        row.update(d_ptd=d.a_ptd.mean(), d_rz=d.a_rz.mean(), d_tdd=d.a_tdd.mean())
    return row, q2, t, d


def ptd_p(MP, row):
    z = np.array([float(row.get(c, np.nan)) for c in MP["cols"]])
    z = np.where(np.isnan(z), np.array(MP["fill"]), z)
    return 1 / (1 + math.exp(-(float(z @ np.array(MP["coef"])) + MP["intercept"])))


# ------------------------------------------------------------ BettingPros attempts

def attempts(weeks, g):
    """{norm name: pass-attempts line} for the game, DraftKings else FanDuel"""
    key = (int(g.season), int(g.week))
    if key not in weeks:
        weeks[key] = get(BP + "events?sport=NFL&week=%d&season=%d" % (key[1], key[0]), headers=BPKEY).json().get("events", [])
    ev = next((e for e in weeks[key] if BPT.get(e.get("home"), e.get("home")) == g.home_team and BPT.get(e.get("visitor"), e.get("visitor")) == g.away_team), None)
    if not ev:
        return {}
    o = get(BP + "offers?sport=NFL&market_id=333&event_id=%s&location=MD&limit=50" % ev["id"], headers=BPKEY).json()
    out = {}
    for x in o.get("offers", []):
        ps = {str(p["id"]): p for p in x.get("participants") or []}
        for s in x["selections"]:
            if s.get("selection") != "over":
                continue
            bks = {b["id"]: b["lines"] for b in s["books"]}
            src = 12 if bks.get(12) else (10 if bks.get(10) else None)
            if src is None:
                continue
            ln = [l for l in bks[src] if l.get("main")] or bks[src]
            p = ps.get(str(s.get("participant"))) or (list(ps.values())[0] if ps else {})
            if ln and ln[0].get("line") is not None:
                out[norm(p.get("name"))] = ln[0]["line"]
    return out


# ------------------------------------------------------------ the run

def main():
    now = datetime.now(timezone.utc)
    SEASON = season_of(now)
    import pagefile
    sched = json.loads(re.search(r"  var SCHED = (\[\[.*?\]\]);", pagefile.read(), re.S).group(1))
    depth = json.load(open(os.path.join(D, "site", "depth.json")))
    prices = json.load(open(os.path.join(D, "site", "prices.json")))
    M = json.load(open(M_ML))
    MP = json.load(open(M_PTD))
    G = pd.read_csv(io.BytesIO(get(GAMES).content), low_memory=False)
    H = hist(SEASON)
    C, e2g = cache(SEASON)
    bk = Book(H, C, G, SEASON)

    def old(p, key):
        try:
            return json.load(open(p)).get(key) or {}
        except Exception:
            return {}
    old_ml = {r["gid"]: r for r in old(OUT_ML, "reads") if isinstance(r, dict) and r.get("gid")}
    old_td_g, old_td_q = old(OUT_TD, "by_game"), old(OUT_TD, "reads")
    old_pt_g, old_pt_q = old(OUT_PTD, "by_game"), old(OUT_PTD, "reads")

    T = lambda s: datetime.strptime(s, "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
    games = []
    for r in sched:
        kick = T(r[2])
        if kick <= now - timedelta(days=2) or kick > now + timedelta(days=8):
            continue
        games.append((kick, r))
    games.sort(key=lambda x: x[0])

    ml_reads, pt_g, td_g, kicked = [], {}, {}, set()
    weeks_bp = {}
    pt_by_qb, td_by_qb = {}, {}
    for kick, r in games:
        wk, gid, away, home = r[0], str(r[1]), r[3], r[4]
        started = kick <= now
        ga, gh = B2G.get(away, away), B2G.get(home, home)
        cand = G[(G.season == SEASON) & (G.game_type == "REG") & (G.away_team == ga) & (G.home_team == gh)]
        if len(cand) > 1:
            cand = cand[cand.week == wk] if (cand.week == wk).any() else cand.iloc[[0]]
        if cand.empty:
            print("%s@%s: not in games.csv" % (away, home))
            continue
        g = cand.iloc[0]
        WK = int(g.week)
        if started and (gid in old_ml or gid in old_td_g):
            kicked.add(gid)
            if gid in old_ml:
                ml_reads.append(dict(old_ml[gid], week=old_ml[gid].get("week") or WK, kick=old_ml[gid].get("kick") or r[2]))
            # the passers' reads it had (a file from before by_game: by the card's two ids)
            ids = [str(x) for x in (r[6], r[8]) if x]
            pt_g[gid] = old_pt_g.get(gid) or {q: old_pt_q[q] for q in ids if q in old_pt_q}
            td_g[gid] = old_td_g.get(gid) or {q: old_td_q[q] for q in ids if q in old_td_q}
            continue
        # the passers: the depth chart's starter (the card follows it)
        men = {}
        for w, club, card_q, card_id, gq in (("away", away, r[5], r[6], g.away_qb_id), ("home", home, r[7], r[8], g.home_qb_id)):
            dp = depth.get(club) or {}
            sid = str(dp.get("starter") or card_id or "")
            nm = next((x["name"] for x in dp.get("qbs", []) if str(x["id"]) == sid), None) or (card_q if str(card_id) == sid else "")
            men[w] = [(sid, nm, e2g.get(sid) or gq)]
            if card_id and str(card_id) != sid:       # the card names someone else: read him too
                men[w].append((str(card_id), card_q, e2g.get(str(card_id)) or gq))
        # 1. the moneyline
        p, h, a, contrib = ml_read(bk, M, g, men["away"][0][2], men["home"][0][2])
        pick, conf = (home, p) if p >= 0.5 else (away, 1 - p)
        mod = round(100 * conf)
        sp = prices.get("SCHED", {}).get(gid) or []
        book = bookpick = agree = None
        onpick = None
        try:
            ma, mh = ip(num(sp[0])), ip(num(sp[2]))
            bh = mh / (ma + mh)
            bp = max(bh, 1 - bh)
            bookpick = home if bh >= 0.5 else away
            book = round(100 * bp)
            agree = bookpick == pick
            onpick = round(100 * (bp if agree else 1 - bp))
        except Exception:
            pass
        won, n = won_before(M, mod, onpick, agree)
        call = "take" if (mod >= 75) or (mod >= 60 and agree and (book or 0) >= 65) else ("lean" if mod >= 60 else None)
        ml_reads.append({"gid": gid, "away": away, "home": home, "pick": pick, "model": mod, "book": book, "bookpick": bookpick,
                         "agree": agree, "won": won, "n": n, "call": call, "rank": None,
                         "why": ml_why(p, h, a, contrib, home, away), "week": WK, "kick": r[2]})
        # 2 and 3. the passers
        total, spread = fin(g.total_line), fin(g.spread_line)
        att = None
        pt_g[gid], td_g[gid] = {}, {}
        for i, w in enumerate(("away", "home")):
            team, opp = (g.home_team, g.away_team) if w == "home" else (g.away_team, g.home_team)
            for sid, nm, qb in men[w]:
                if not sid:
                    continue
                row, q2, t, d = ptd_feats(bk, qb, team, opp, int(w == "home"), SEASON, WK, g.roof, g.div_game)
                p1 = round(ptd_p(MP, row), 3)
                pt_g[gid][sid] = {"p": p1, "name": nm}
                proj = fav = None
                if total is not None and spread is not None:
                    proj = (total + spread) / 2 if w == "home" else (total - spread) / 2
                    fav = spread if w == "home" else -spread
                rec = {"p1": p1, "proj": None if proj is None else round(proj, 1), "total": total, "fav": fav, "two_now": None}
                why = []
                if q2 is not None and len(q2):
                    why.append("TD passes per game: %.2f (last %d games)" % (q2.ptd.mean(), len(q2)))
                    why.append("His efficiency: %+.2f EPA per dropback" % ((q2.qe * q2.db).sum() / max(q2.db.sum(), 1)))
                    cur = q2[q2.season == SEASON]
                    rec["two_now"] = "%d of %d" % ((cur.ptd >= 2).sum(), len(cur)) if len(cur) else None
                if t is not None and len(t):
                    why.append("%s reach the red zone %.1f times a game" % (TEAMN.get(team, team), t.rz.mean()))
                if d is not None and len(d):
                    why.append("%s let teams into the red zone %.1f times a game" % (TEAMN.get(opp, opp), d.a_rz.mean()))
                rec["why1"] = why
                # the 2+ rules that held 75%+ blind (ptd/tdreads.py)
                rules = []
                if proj is not None:
                    pl = ((prices.get("PROPS", {}).get(gid) or {}).get("ptd") or [[], []])
                    pl = pl[i] if len(pl) > i else []
                    try:
                        b1 = ip(num(pl[0][0])) if pl and pl[0] and pl[0][0] else 0
                    except Exception:
                        b1 = 0
                    a_line = None
                    if proj >= 27:
                        if att is None:
                            try:
                                att = attempts(weeks_bp, g)
                            except Exception as e:
                                print("%s@%s attempts: %s" % (away, home, e))
                                att = {}
                        a_line = att.get(norm(nm))
                    if proj >= 29.5:
                        rules.append(("Team projected for %.1f points" % proj, "teams projected 30+ threw 2+ 80% of the time"))
                    if b1 >= .82 and total >= 46 and fav >= 7.5:
                        rules.append(("Heavy on 1+ and favored by %.1f with a %.1f total" % (fav, total), "heavy 1+, big favorite, 46+ total threw 2+ 87% of the time"))
                    if proj >= 27 and a_line and a_line >= 33.5:
                        rules.append(("Projected %.1f points with %.1f pass attempts" % (proj, a_line), "projected 27+ with a 33.5+ attempts line threw 2+ 75% of the time"))
                if rules:
                    w2 = [rl[0] for rl in rules]
                    if rec.get("two_now"):
                        w2.append("2+ TD passes in %s games this season" % rec["two_now"])
                    if d is not None and len(d):
                        w2.append("%s let teams into the red zone %.1f times a game" % (TEAMN.get(opp, opp), d.a_rz.mean()))
                    rec["two"] = {"take": True, "why": w2, "won": rules[0][1]}
                rec["why3"] = (["%s projected for %.1f points" % (TEAMN.get(team, team), proj), "Game total %.1f" % total]
                               if proj is not None else [])
                td_g[gid][sid] = rec
    # one read a man: the soonest game he has not started yet, else the one under way
    order = [str(r[1]) for _, r in games]
    for gid in sorted(order, key=lambda x: (x in kicked, order.index(x))):
        for sid, v in pt_g.get(gid, {}).items():
            pt_by_qb.setdefault(sid, v)
        for sid, v in td_g.get(gid, {}).items():
            td_by_qb.setdefault(sid, v)
    # rank within each week: call, then won-before, then the model
    for wk in {r.get("week") for r in ml_reads}:
        rs = [r for r in ml_reads if r.get("week") == wk]
        for k, r in enumerate(sorted(rs, key=lambda r: (-(r["call"] == "take"), -(r["call"] == "lean"), -(r["won"] or 0), -r["model"])), 1):
            r["rank"] = k
    ml_reads.sort(key=lambda r: (r.get("week") or 0, r["rank"] or 99))
    up = [r for r in ml_reads if r["gid"] not in kicked]
    week = min((r["week"] for r in up), default=max((r.get("week") or 0 for r in ml_reads), default=None))

    for r in ml_reads:
        tag = "kept" if r["gid"] in kicked else ""
        print("ML  wk%s %-8s %-4s model %2d  book %s %-4s  won %s (%s)  %-5s rank %s %s" % (
            r.get("week"), r["away"] + "@" + r["home"], r["pick"], r["model"], r["book"], r["bookpick"], r["won"], r["n"],
            (r["call"] or "-").upper(), r["rank"], tag))
    for kick, r in games:
        gid = str(r[1])
        for sid, v in td_g.get(gid, {}).items():
            print("TD  %-8s %-22s 1+ model %s  proj %s  2+ %s%s" % (
                r[3] + "@" + r[4], (pt_g[gid].get(sid) or {}).get("name") or sid, v.get("p1"), v.get("proj"),
                "TAKE (%s)" % v["two"]["won"] if v.get("two") else "-", "  kept" if gid in kicked else ""))

    day = now.strftime("%Y-%m-%d")
    ml_out = {"at": day, "week": week,
              "note": "rank by call then won-before within each week; TAKE = model 75+ or model 60+ with the book 65+ on the same team; LEAN = model 60-74; book = sportsbook implied %, shown as information",
              "reads": ml_reads}
    pt_out = {"at": day, "note": "1+ passing TD model (research/nfl_ptd): trained 2016-21, no odds; blind: 80+ hit 84-86%, 75-79 hit 75%, under 75 hit 63-72%",
              "reads": pt_by_qb, "by_game": pt_g}
    td_out = {"at": day, "week": week, "reads": td_by_qb, "by_game": td_g}
    if DRY:
        print("dry run: nothing written")
        return
    for path, obj in ((OUT_ML, ml_out), (OUT_PTD, pt_out), (OUT_TD, td_out)):
        # write only on a change, so a quiet sweep commits nothing
        try:
            was = json.load(open(path))
            was.pop("at", None)
        except Exception:
            was = None
        now_ = dict(obj)
        now_.pop("at", None)
        if json.loads(json.dumps(now_)) != was:
            json.dump(obj, open(path, "w"), indent=1)
            print("wrote", os.path.relpath(path, D))


if __name__ == "__main__":
    main()
