"""UFC winner lab: can a moneyline pick on EVERY men's bout get 75% of a card right?

   A research script, nothing on the board reads it. It rebuilds the blind test
   of build/ufc_reads.py card by card (each card scored by a model fit only on
   bouts dated before that card), studies the misses, and tries features and a
   market blend aimed at them. Strictly time-ordered: every feature for a bout on
   day d is built from bouts dated before d; the market price is the closing line
   gidstats keeps for the bout (data/ufc_records/fights.csv `odds`), topped up
   with data/bfo_odds.json, i.e. information that exists before the first bell.

   Usage:  python3 build/ufc_winner_lab.py [--out DIR] [--from 2022-01-01] [--per card|month|year]
           writes DIR/results.md, DIR/per_card_<version>.csv, DIR/bouts_<version>.csv
   Needs: pandas numpy pyarrow scikit-learn joblib
"""
import argparse
import json
import math
import os
import re
import sys
import time
import unicodedata
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import ufc_reads as U  # noqa: E402  (read-only: load_hist, feat, GBM)

PRO = os.path.join(D, "data", "ufc_records")


# ------------------------------------------------------------------ helpers
def am2p(o):
    try:
        o = float(o)
    except Exception:
        return np.nan
    if not np.isfinite(o) or o == 0:
        return np.nan
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def ln(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().replace(".", "").replace("-", " ")
    p = [w for w in s.split() if w not in ("jr", "sr", "ii", "iii")]
    return p[-1] if p else ""


# ------------------------------------------------------------------ the market
def market(X):
    """p_mkt: the market's no-vig chance that side a wins, from the closing line"""
    P = pd.read_csv(os.path.join(PRO, "people.csv"))
    F = pd.read_csv(os.path.join(PRO, "fights.csv"), usecols=["page_url", "date", "odds"])
    F["date"] = pd.to_datetime(F.date, errors="coerce")
    page = {r.fighter_url: r.page_url for r in P.itertuples() if isinstance(r.fighter_url, str)}
    pm = json.load(open(os.path.join(D, "data", "ufc_hist", "pro_map.json")))
    for u, v in pm.items():
        page.setdefault(u, v["page"])
    F = F[F.odds.notna()]
    od = {(r.page_url, r.date): r.odds for r in F.itertuples()}

    def look(u, d):
        p = page.get(u)
        for k in (0, -1, 1):
            v = od.get((p, d + pd.Timedelta(days=k)))
            if v is not None:
                return am2p(v)
        return np.nan
    pa = np.array([look(u, d) for u, d in zip(X.a_url, X.date)])
    pb = np.array([look(u, d) for u, d in zip(X.b_url, X.date)])
    # BFO for bouts gidstats lacks (2026)
    try:
        B = json.load(open(os.path.join(D, "data", "bfo_odds.json")))
        bidx = {}
        for v in B.values():
            ml = v.get("ml") or {}
            if not ml or len(v.get("names", [])) != 2:
                continue
            l = [am2p(x[0]) for x in ml.values() if len(x) == 2]
            r = [am2p(x[1]) for x in ml.values() if len(x) == 2]
            l, r = np.nanmedian(l) if l else np.nan, np.nanmedian(r) if r else np.nan
            n1, n2 = (ln(x) for x in v["names"])
            if v.get("flip"):
                pass  # names already follow the ml order in the file
            bidx[(v["date"], n1, n2)] = (l, r)
            bidx[(v["date"], n2, n1)] = (r, l)
        for i in np.where(np.isnan(pa) & np.isnan(pb))[0]:
            for k in (0, -1, 1):
                ds = str((X.date.iloc[i] + pd.Timedelta(days=k)).date())
                hit = bidx.get((ds, ln(X.a.iloc[i]), ln(X.b.iloc[i])))
                if hit:
                    pa[i], pb[i] = hit
                    break
    except Exception as e:
        print("bfo skipped:", e)
    both = ~np.isnan(pa) & ~np.isnan(pb)
    p = np.full(len(X), np.nan)
    p[both] = pa[both] / (pa[both] + pb[both])
    oa = ~np.isnan(pa) & np.isnan(pb)
    ob = np.isnan(pa) & ~np.isnan(pb)
    p[oa] = np.clip(pa[oa] - 0.025, 0.02, 0.98)
    p[ob] = np.clip(1 - (pb[ob] - 0.025), 0.02, 0.98)
    return p


# ------------------------------------------------------------------ new features, all from bouts before the day
def glicko(h):
    """Glicko-1 over every UFC bout since 1994: rating and RD for each man the morning of each bout"""
    Hh = h["history"].copy()
    Hh["date"] = pd.to_datetime(Hh.date)
    Hr = Hh[Hh.result.isin(["W", "L", "D"])].copy()
    Hr["pair"] = [tuple(sorted([a, b])) + (str(d.date()),) for a, b, d in zip(Hr.fighter_url, Hr.opponent_url, Hr.date)]
    Hr = Hr.sort_values(["date", "o2"], kind="mergesort").drop_duplicates("pair")
    q = math.log(10) / 400
    R, RD, LAST, PRE = {}, {}, {}, {}
    c2 = 60.0 ** 2 / 365.0          # RD regrows ~60 points a year of inactivity (per day)

    def g(rd):
        return 1 / math.sqrt(1 + 3 * q * q * rd * rd / math.pi ** 2)
    for r in Hr.itertuples():
        a, b, d = r.fighter_url, r.opponent_url, r.date
        cur = {}
        for u in (a, b):
            rr, rd = R.get(u, 1500.0), RD.get(u, 300.0)
            if u in LAST:
                rd = min(math.sqrt(rd * rd + c2 * (d - LAST[u]).days), 350.0)
            cur[u] = (rr, rd)
            PRE[(u, d)] = (rr, rd)
        sa = 1.0 if r.result == "W" else 0.0 if r.result == "L" else 0.5
        fin = any(x in str(r.method) for x in ("KO", "SUB"))
        for u, o, s in ((a, b, sa), (b, a, 1 - sa)):
            ru, rdu = cur[u]
            ro, rdo = cur[o]
            gg = g(rdo)
            E = 1 / (1 + 10 ** (-gg * (ru - ro) / 400))
            d2 = 1 / (q * q * gg * gg * E * (1 - E))
            k = 1.15 if fin else 1.0
            nr = ru + k * q / (1 / (rdu * rdu) + 1 / d2) * gg * (s - E)
            nrd = max(math.sqrt(1 / (1 / (rdu * rdu) + 1 / d2)), 50.0)
            R[u], RD[u], LAST[u] = nr, nrd, d
    return PRE


def pro_elo():
    """an Elo over every pro bout in the gidstats records (regional cards too), so a UFC debut
       carries the strength of what he beat on the way in; rating the morning of each bout by page"""
    F = pd.read_csv(os.path.join(PRO, "fights.csv"), usecols=["page_url", "fighter", "date", "result", "opponent",
                                                               "opponent_url", "method"])
    F["date"] = pd.to_datetime(F.date, errors="coerce")
    F = F[F.result.isin(["win", "loss", "draw"]) & F.date.notna()].copy()
    F["opp"] = F.opponent_url.where(F.opponent_url.notna(), "name:" + F.opponent.astype(str).str.lower())
    F["key"] = [tuple(sorted([a, b])) + (str(d.date()),) for a, b, d in zip(F.page_url, F.opp, F.date)]
    F = F.sort_values("date", kind="mergesort").drop_duplicates("key")
    R, N, HIST = {}, {}, {}
    for r in F.itertuples():
        a, b = r.page_url, r.opp
        ra, rb = R.get(a, 1400.0), R.get(b, 1400.0)
        for u, v in ((a, ra), (b, rb)):
            HIST.setdefault(u, []).append((r.date, v, N.get(u, 0)))
        ea = 1 / (1 + 10 ** ((rb - ra) / 400))
        sa = 1.0 if r.result == "win" else 0.0 if r.result == "loss" else 0.5
        ka = 48 if N.get(a, 0) < 8 else 32
        kb = 48 if N.get(b, 0) < 8 else 32
        R[a] = ra + ka * (sa - ea)
        R[b] = rb + kb * ((1 - sa) - (1 - ea))
        N[a] = N.get(a, 0) + 1
        N[b] = N.get(b, 0) + 1
    for u in HIST:
        HIST[u].sort(key=lambda t: t[0])
    return HIST, R


def asof(hist, d):
    """last (rating, n) recorded strictly before day d; the rating after the last bout is not kept, so
       take the pre-bout value of the first bout on/after d if any, else nan"""
    if not hist:
        return np.nan, 0
    for t, v, n in hist:
        if t >= d - pd.Timedelta(days=2):     # the UFC bout itself may be dated a day off in the records
            return v, n
    return np.nan, len(hist)


def extra_side(h, X):
    """per side: glicko r/rd, pro-wide elo, strength of schedule, best win, recent strike form,
       weight-class move, age over 34, recent finish losses"""
    t0 = time.time()
    G = glicko(h)
    PH, PR = pro_elo()
    P = pd.read_csv(os.path.join(PRO, "people.csv"))
    page = {r.fighter_url: r.page_url for r in P.itertuples() if isinstance(r.fighter_url, str)}
    pm = json.load(open(os.path.join(D, "data", "ufc_hist", "pro_map.json")))
    for u, v in pm.items():
        page.setdefault(u, v["page"])
    # per-man timeline of his UFC Stats bouts (2010+): date, opp elo, result, wc, sig diff per min, method
    F = h["fights"].copy()
    F["date"] = pd.to_datetime(F.event_date)

    def mins(rnd, tm):
        try:
            a, b = str(tm).split(":")
            return (int(rnd) - 1) * 5 + int(a) + int(b) / 60
        except Exception:
            return np.nan
    F["mins"] = [mins(r, t) for r, t in zip(F["round"], F["time"])]
    el = {(u, d): e for u, d, e in zip(X.a_url, X.date, X.a_elo)} | {(u, d): e for u, d, e in zip(X.b_url, X.date, X.b_elo)}
    T = {}
    for r in F.itertuples(index=False):
        for me, ot in (("red", "blue"), ("blue", "red")):
            u, o = getattr(r, me + "_url"), getattr(r, ot + "_url")
            sl = pd.to_numeric(getattr(r, me + "_sig_landed"), errors="coerce")
            sa = pd.to_numeric(getattr(r, ot + "_sig_landed"), errors="coerce")
            res = "W" if r.winner == me else "L" if r.winner == ot else "D"
            T.setdefault(u, []).append(dict(date=r.date, oelo=el.get((o, r.date), np.nan), res=res, wc=str(r.weight_class),
                                            sd=(sl - sa) / r.mins if r.mins and r.mins > 0 else np.nan,
                                            fin_loss=int(res == "L" and any(x in str(r.method) for x in ("KO", "SUB")))))
    for u in T:
        T[u].sort(key=lambda z: z["date"])
    WL = {"Flyweight": 125, "Bantamweight": 135, "Featherweight": 145, "Lightweight": 155, "Welterweight": 170,
          "Middleweight": 185, "Light Heavyweight": 205, "Heavyweight": 265}

    def wlb(wc):
        for k in sorted(WL, key=len, reverse=True):
            if k in wc:
                return WL[k]
        return np.nan
    out = {}
    for s in "ab":
        cols = {k: [] for k in ("gr", "grd", "pelo", "pelo_n", "sos", "bestwin", "sd_l2", "sd_car", "wmove", "age34",
                                "finl_l3", "elo_trend", "ufc_wpct_adj")}
        for u, d, wc, age, elo in zip(X[s + "_url"], X.date, X.wc.astype(str), X[s + "_age"], X[s + "_elo"]):
            gr = G.get((u, d))
            cols["gr"].append(gr[0] if gr else np.nan)
            cols["grd"].append(gr[1] if gr else np.nan)
            pv, pn = asof(PH.get(page.get(u)), d)
            cols["pelo"].append(pv)
            cols["pelo_n"].append(pn)
            past = [z for z in T.get(u, []) if z["date"] < d]
            oe = [z["oelo"] for z in past if np.isfinite(z["oelo"])]
            cols["sos"].append(np.mean(oe[-5:]) if oe else np.nan)
            bw = [z["oelo"] for z in past if z["res"] == "W" and np.isfinite(z["oelo"])]
            cols["bestwin"].append(max(bw) if bw else np.nan)
            sd = [z["sd"] for z in past if np.isfinite(z["sd"])]
            cols["sd_l2"].append(np.mean(sd[-2:]) if sd else np.nan)
            cols["sd_car"].append(np.mean(sd) if sd else np.nan)
            cols["wmove"].append((wlb(wc) - wlb(past[-1]["wc"])) if past else np.nan)
            cols["age34"].append(max(0.0, age - 34) if np.isfinite(age) else np.nan)
            cols["finl_l3"].append(sum(z["fin_loss"] for z in past[-3:]) if past else np.nan)
            pe = [el.get((u, z["date"]), np.nan) for z in past[-3:]]
            cols["elo_trend"].append((elo - pe[0]) if past and np.isfinite(pe[0]) and np.isfinite(elo) else np.nan)
            w = [(1 if z["res"] == "W" else 0, z["oelo"]) for z in past if np.isfinite(z["oelo"])]
            cols["ufc_wpct_adj"].append(np.mean([r * (o - 1500) / 100 + r for r, o in w]) if w else np.nan)
        for k, v in cols.items():
            out[s + "_" + k] = np.array(v, float)
    print("extra features %.0fs" % (time.time() - t0))
    return pd.DataFrame(out, index=X.index)


def feat_extra(X, E):
    f = lambda s, c: E[s + "_" + c]
    d = lambda c: f("a", c) - f("b", c)
    return pd.DataFrame({
        "glicko": d("gr"), "glicko_rd": -d("grd"),
        "glicko_z": d("gr") / np.sqrt(f("a", "grd") ** 2 + f("b", "grd") ** 2),
        "pro_elo": d("pelo"), "pro_elo_n": d("pelo_n"),
        "sos": d("sos"), "bestwin": d("bestwin"), "sd_l2": d("sd_l2"), "sd_car": d("sd_car"),
        "sd_trend": (f("a", "sd_l2") - f("a", "sd_car")) - (f("b", "sd_l2") - f("b", "sd_car")),
        "wmove": d("wmove"), "age34": -d("age34"), "finl_l3": -d("finl_l3"), "elo_trend": d("elo_trend"),
        "wpct_adj": d("ufc_wpct_adj"),
    }, index=X.index)


# ------------------------------------------------------------------ fitting
def prep(FE, tr):
    F = FE.copy()
    for c in list(FE.columns):
        if c == "mkt":
            continue
        F[c + "_na"] = F[c].isna().astype(int)
        F[c] = F[c].fillna(0)
    if "mkt" in F:
        F["mkt"] = F["mkt"].fillna(0)        # logit 0 = no market opinion
    keep = F[tr].std() > 0
    F = F.loc[:, keep]
    mu, sd = F[tr].mean(), F[tr].std()
    if "mkt" in F:
        mu["mkt"] = 0.0                     # keep the market antisymmetric under the side swap
    return ((F - mu) / sd).values


def fit_predict(FE, y, tr, te, params):
    Z = prep(FE, tr)
    m = HistGradientBoostingClassifier(**params).fit(np.vstack([Z[tr], -Z[tr]]), np.concatenate([y[tr], 1 - y[tr]]))
    Zt = Z[te]
    return (m.predict_proba(Zt)[:, 1] + 1 - m.predict_proba(-Zt)[:, 1]) / 2


def walk(X, FE, y, base_tr, test_cards, params, per="card", jobs=4):
    """blind p for every bout on each test card; per='card' refits before each card date, per='year' each year"""
    P = np.full(len(X), np.nan)
    if per == "year":
        groups = [(pd.Timestamp("%d-01-01" % yr), (X.yr == yr).values & test_cards) for yr in sorted(X.yr[test_cards].unique())]
    elif per == "month":     # refit on the 1st of each month: still blind, a few weeks' less data than per card
        mo = X.date.dt.to_period("M")
        groups = [(m.to_timestamp(), (mo == m).values & test_cards) for m in sorted(mo[test_cards].unique())]
    else:
        ds = sorted(X.date[test_cards].unique())
        groups = [(pd.Timestamp(d), (X.date == d).values & test_cards) for d in ds]
    res = [fit_predict(FE, y, base_tr & (X.date < d).values, te, params) for d, te in groups]
    for (d, te), p in zip(groups, res):
        P[te] = p
    return P


# ------------------------------------------------------------------ scoring
def per_card(X, P, mask):
    pick_a = P > 0.5
    right = np.where(pick_a, X.a_won.values == 1, X.a_won.values == 0)
    df = pd.DataFrame(dict(date=X.date.dt.strftime("%Y-%m-%d"), event=X.event, right=right.astype(int)))[mask]
    g = df.groupby(["date", "event"]).right.agg(["size", "sum"]).reset_index()
    g.columns = ["date", "card", "bouts", "right"]
    g["pct"] = 100 * g.right / g.bouts
    return g, right


def summary(name, X, P, mask, note=""):
    g, right = per_card(X, P, mask)
    g5 = g[g.bouts >= 5]
    return dict(version=name, bouts=int(mask.sum()), acc=100 * right[mask].mean(), cards=len(g),
                mean_card=g.pct.mean(), med_card=g.pct.median(), ge75=100 * (g.pct >= 75).mean(),
                ge75_5=100 * (g5.pct >= 75).mean(), note=note), g


def bands(P, X, mask):
    conf = np.maximum(P, 1 - P)
    right = np.where(P > 0.5, X.a_won.values == 1, X.a_won.values == 0)
    rows = []
    for lo, hi, lab in ((0.8, 1.01, "80%+"), (0.75, 0.8, "75-79"), (0.7, 0.75, "70-74"), (0.65, 0.7, "65-69"),
                        (0.6, 0.65, "60-64"), (0, 0.6, "<60")):
        k = mask & (conf >= lo) & (conf < hi)
        rows.append((lab, int(k.sum()), 100 * right[k].mean() if k.sum() else np.nan))
    return rows


def md_table(df, fmt=None):
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.itertuples(index=False):
        out.append("| " + " | ".join(("%.1f" % v) if isinstance(v, float) else str(v) for v in r) + " |")
    return "\n".join(out)


# ------------------------------------------------------------------ error analysis
def analyze(path, col):
    """hit rate by situation for one version's picks in bouts.csv; returns a markdown table"""
    B = pd.read_csv(path)
    p = B[col].values
    pa = p > 0.5
    right = np.where(pa, B.a_won == 1, B.a_won == 0)
    conf = np.maximum(p, 1 - p)
    side = lambda c: np.where(pa, B["a_" + c], B["b_" + c])
    oside = lambda c: np.where(pa, B["b_" + c], B["a_" + c])
    pm = B.p_mkt.values
    mconf = np.maximum(pm, 1 - pm)
    dog = np.isfinite(pm) & ((pm > 0.5) != pa)
    meth = B.method.astype(str)
    S = {
        "all": np.ones(len(B), bool),
        "conf <60%": conf < 0.6, "conf 60-69%": (conf >= 0.6) & (conf < 0.7), "conf 70%+": conf >= 0.7,
        "market pick'em (fav <60%)": np.isfinite(pm) & (mconf < 0.6),
        "market fav 60-69%": np.isfinite(pm) & (mconf >= 0.6) & (mconf < 0.7),
        "market fav 70%+": np.isfinite(pm) & (mconf >= 0.7),
        "model picks the market underdog": dog,
        "either man's UFC debut": (B.a_n == 0) | (B.b_n == 0),
        "pick is debuting": side("n") == 0, "opponent is debuting": oside("n") == 0,
        "thin: either man <=2 UFC bouts": np.minimum(B.a_n, B.b_n) <= 2,
        "layoff: either man 365+ days": (B.a_layoff >= 365) | (B.b_layoff >= 365),
        "pick off 365+ days": side("layoff") >= 365,
        "age gap 5+ yrs": (B.a_age - B.b_age).abs() >= 5,
        "pick is the older by 5+": (side("age") - oside("age")) >= 5,
        "pick 35+": side("age") >= 35,
        "weight move: either man changed class": (B.a_wmove.fillna(0) != 0) | (B.b_wmove.fillna(0) != 0),
        "pick moving up": side("wmove") > 0,
        "ended KO/TKO": meth.str.contains("KO"), "ended SUB": meth.str.contains("SUB"),
        "went to decision": meth.str.contains("DEC"), "split/majority decision": meth.str.contains("S-DEC|M-DEC"),
    }
    for wc in ["Flyweight", "Bantamweight", "Featherweight", "Lightweight", "Welterweight", "Middleweight",
               "Light Heavyweight", "Heavyweight"]:
        S["div " + wc] = (B.wc.astype(str).str.replace("UFC ", "").str.replace(" Title", "").str.strip() == wc).values
    miss = ~right
    rows = []
    for k, m in S.items():
        m = np.asarray(m, bool)
        if m.sum() == 0:
            continue
        rows.append(dict(situation=k, bouts=int(m.sum()), hit=100 * right[m].mean(), misses=int((m & miss).sum()),
                         share_of_misses=100 * (m & miss).sum() / miss.sum()))
    return pd.DataFrame(rows)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(D, "research", "ufc_winner_lab"))
    ap.add_argument("--from", dest="start", default="2022-01-01")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--per", default="card", choices=["card", "month", "year"], help="refit cadence of the test walk")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    t0 = time.time()
    h = U.load_hist()
    X = h["bouts"].reset_index(drop=True).copy()
    X["date"] = pd.to_datetime(X.date)
    y = X.a_won.values.astype(int)
    men = ~U.women(X)
    dec = X.winner.isin(["red", "blue"]).values
    samp = X.train.astype(bool).values
    base_tr = men & dec & samp                         # the production training sample
    test = men & dec & (X.date >= pd.Timestamp(a.start)).values   # every decided men's bout on the test cards
    print("bouts %d, test %d men's decided bouts on %d cards" % (len(X), test.sum(), X[test].groupby(["date", "event"]).ngroups))

    FE0 = U.feat(X)
    cache = os.path.join(a.out, "..", "features_cache.parquet")
    if os.path.exists(cache) and len(pd.read_parquet(cache)) == len(X):
        C = pd.read_parquet(cache)
        pm = C.pop("p_mkt").values
        E = C
        print("features from cache", cache)
    else:
        pm = market(X)
        E = extra_side(h, X)
        E.assign(p_mkt=pm).to_parquet(cache)
    print("market price on %d of %d test bouts" % (np.isfinite(pm[test]).sum(), test.sum()))
    FX = feat_extra(X, E)
    MK = pd.DataFrame({"mkt": logit(pm)}, index=X.index)
    MK.loc[~np.isfinite(pm), "mkt"] = np.nan

    per = a.per
    GBM = dict(U.GBM)
    SLOW = dict(max_depth=3, learning_rate=0.03, max_iter=400, l2_regularization=2.0, min_samples_leaf=40, random_state=0)
    versions, store, cards = [], {}, {}

    def run(name, FE, params, note, per_=per):
        t = time.time()
        P = walk(X, FE, y, base_tr, test, params, per=per_, jobs=a.jobs)
        s, g = summary(name, X, P, test, note)
        versions.append(s)
        store[name] = P
        cards[name] = g
        print("%-28s acc %.1f  mean card %.1f  >=75 %.1f%%  (%.0fs)" % (name, s["acc"], s["mean_card"], s["ge75"], time.time() - t))
        return P

    # V0 the production walk: refit each year (reproduces CALL_WON / walk_forward.txt)
    run("V0 prod, yearly refit", FE0, GBM, "build/ufc_reads.py features and GBM, refit Jan 1 each year", per_="year")
    run("V1 prod, per-card refit", FE0, GBM, "same model refit before every card")
    # market only (favorite), model where no price
    P1 = store["V1 prod, per-card refit"]
    Pm = np.where(np.isfinite(pm), pm, P1)
    s, g = summary("M favorite (closing line)", X, Pm, test, "market favorite; model pick on the %d bouts without a price"
                   % (test & ~np.isfinite(pm)).sum())
    versions.append(s); store[s["version"]] = Pm; cards[s["version"]] = g
    print("market favorite acc %.1f mean card %.1f" % (s["acc"], s["mean_card"]))
    FE2 = pd.concat([FE0, FX], axis=1)
    run("V2 +new features", FE2, GBM, "+Glicko, pro-wide Elo, schedule strength, best win, strike form, weight move, age>34")
    run("V2b +new feats, slower GBM", FE2, SLOW, "same, lr .03 x400, leaf 40, l2 2")
    FE3 = pd.concat([FE2, MK], axis=1)
    run("V3 +market as feature", FE3, SLOW, "V2b features + logit closing line")
    FE3b = pd.concat([FE0, MK], axis=1)
    run("V3b prod feats +market", FE3b, SLOW, "production features + logit closing line")

    # V4 stacked blend: logit p = w1*logit(model) + w2*logit(market), weights fit on earlier cards' blind p only
    # blind model p before the test window, by yearly refit, so the blender has history to learn from
    pre = men & dec & (X.date >= pd.Timestamp("2017-01-01")).values & (X.date < pd.Timestamp(a.start)).values
    Ppre = walk(X, FE2, y, base_tr, pre, SLOW, per="year", jobs=a.jobs)
    Pmod = np.where(np.isfinite(Ppre), Ppre, store["V2b +new feats, slower GBM"])
    has = np.isfinite(pm)
    Pbl = np.full(len(X), np.nan)
    wlog = []
    for d in sorted(X.date[test].unique()):
        te = test & (X.date == d).values
        trb = (pre | test) & has & (X.date < d).values & np.isfinite(Pmod)
        lr = LogisticRegression(C=1.0, fit_intercept=False).fit(np.c_[logit(Pmod[trb]), logit(pm[trb])], y[trb])
        w = lr.coef_[0]
        wlog.append((str(pd.Timestamp(d).date()), w[0], w[1], int(trb.sum())))
        z = np.where(has[te], w[0] * logit(Pmod[te]) + w[1] * logit(np.where(has[te], pm[te], 0.5)), logit(Pmod[te]))
        Pbl[te] = 1 / (1 + np.exp(-z))
    s, g = summary("V4 blend model+market", X, Pbl, test, "logistic stack of V2b and the closing line, weights from earlier cards; last w=(%.2f, %.2f)"
                   % (wlog[-1][1], wlog[-1][2]))
    versions.append(s); store[s["version"]] = Pbl; cards[s["version"]] = g
    print("blend acc %.1f mean card %.1f  weights last %s" % (s["acc"], s["mean_card"], wlog[-1]))

    # ------------------------------------------------------------ write
    V = pd.DataFrame(versions)
    V.to_csv(os.path.join(a.out, "versions.csv"), index=False)
    for k, g in cards.items():
        g.to_csv(os.path.join(a.out, "per_card_%s.csv" % re.sub(r"\W+", "_", k.split()[0])), index=False)
    B = X.loc[test, ["date", "event", "wc", "a", "b", "winner", "method", "a_n", "b_n", "a_age", "b_age", "a_layoff",
                     "b_layoff", "a_pn", "b_pn"]].copy()
    B["p_mkt"] = pm[test]
    for k, P in store.items():
        if P is not None:
            B["p_" + re.sub(r"\W+", "_", k.split()[0])] = P[test]
    B["a_won"] = y[test]
    B = pd.concat([B, FX.loc[test, ["wmove", "glicko_rd"]], E.loc[test, ["a_wmove", "b_wmove", "a_pelo_n", "b_pelo_n"]]], axis=1)
    B.to_csv(os.path.join(a.out, "bouts.csv"), index=False)
    json.dump(dict(bands={k: bands(P, X, test) for k, P in store.items() if P is not None},
                   blend_weights=wlog[-1]), open(os.path.join(a.out, "bands.json"), "w"), indent=1, default=float)
    print("done %.0fs -> %s" % (time.time() - t0, a.out))


if __name__ == "__main__":
    main()
