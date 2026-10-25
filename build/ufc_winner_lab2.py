"""UFC winner lab, round 2: fight-week facts, line movement, coin-flip sub-models, per-card refit.

   Research only; nothing on the board reads it. Builds on build/ufc_winner_lab.py (round 1)
   and reads build/ufc_reads.py (never edits it).

   Leak rules: a card on day d is scored with models and stackers fit only on bouts dated
   before d. Wikipedia facts come from the page revision as of 06:00 UTC on the card's day
   (rvstart), so nothing written after the weigh-ins' day can enter. Odds are BFO's opening
   line and the closing mean (both pre-bell) and gidstats' closing line.

   Usage:
     python3 build/ufc_winner_lab2.py fetch-wiki --out DIR     # one request at a time, cached
     python3 build/ufc_winner_lab2.py fetch-bfo  --out DIR     # BFS over UFC fighters' BFO pages, cached
     python3 build/ufc_winner_lab2.py run        --out DIR [--per year|card]
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import warnings

import numpy as np
import pandas as pd
import requests
from sklearn.linear_model import LogisticRegression

warnings.filterwarnings("ignore")
D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import ufc_reads as U  # noqa: E402
import ufc_winner_lab as L1  # noqa: E402

UA = "TheArenaBoard/1.0 (https://the-arenasports.pages.dev; research, one page at a time)"
FROM = "2010-01-01"          # blind model p, stack history and the learning loop all start at the first card here
LOOP = "2010-01-01"          # the learning loop starts here (Jose, Oct 25: 2010 to now, every card)
TEST = "2022-01-01"          # graded from here (round 1 comparable)


# ================================================================== Wikipedia, as of the card's morning
def wiki_get(params, tries=5):
    q = dict(params, format="json", formatversion=2, maxlag=5)
    for i in range(tries):
        try:
            r = requests.get("https://en.wikipedia.org/w/api.php", params=q, headers={"User-Agent": UA}, timeout=30)
            if r.status_code == 200:
                j = r.json()
                if (j.get("error") or {}).get("code") != "maxlag":
                    return j
        except Exception:
            pass
        time.sleep(2 ** i)
    raise RuntimeError("wikipedia failed")


def wiki_events(out):
    fn = os.path.join(out, "wiki", "list.json")
    if not os.path.exists(fn):
        json.dump(wiki_get(dict(action="query", prop="revisions", rvprop="content", rvslots="main", titles="List of UFC events")),
                  open(fn, "w"))
    t = json.load(open(fn))["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
    t = t[t.find("Past events"):]
    ev = []
    mon = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}
    for row in t.split("\n|-"):
        m = re.search(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]\s*\n\|\s*\{\{dts\|(\d{4})\|(\w{3})\w*\|(\d{1,2})\}\}", row)
        if m:
            ev.append((m.group(1).strip(), dt.date(int(m.group(2)), mon[m.group(3)[:3]], int(m.group(4)))))
    return ev


def fetch_wiki(out):
    os.makedirs(os.path.join(out, "wiki"), exist_ok=True)
    ev = [e for e in wiki_events(out) if e[1] >= dt.date.fromisoformat(FROM)]
    print("events", len(ev))
    for title, day in sorted(ev, key=lambda e: e[1]):
        fn = os.path.join(out, "wiki", "%s_%s.json" % (day, re.sub(r"[^A-Za-z0-9]+", "_", title).strip("_")))
        if os.path.exists(fn):
            continue
        j = wiki_get(dict(action="query", prop="revisions", rvprop="content|ids|timestamp", rvslots="main", redirects=1,
                          titles=title, rvlimit=1, rvdir="older", rvstart="%sT06:00:00Z" % day))
        p = (j.get("query") or {}).get("pages", [{}])[0]
        rv = (p.get("revisions") or [{}])[0]
        json.dump(dict(title=title, day=str(day), revid=rv.get("revid"), ts=rv.get("timestamp"),
                       wikitext=(rv.get("slots") or {}).get("main", {}).get("content", "")), open(fn, "w"))
        print(day, title, rv.get("timestamp"), len(json.load(open(fn))["wikitext"]), flush=True)
        time.sleep(1.0)


def wiki_side_facts(out, h, X):
    """per bout row: a_/b_ replacement, notice days, short words, missed weight, lbs, newcomer;
       plus catchweight / rematch from the page and the records"""
    import glob
    pages = {}
    for fn in glob.glob(os.path.join(out, "wiki", "2*.json")):
        j = json.load(open(fn))
        if j.get("wikitext"):
            pages.setdefault(j["day"], []).append(j)
    fighters = h["fighters"].drop_duplicates("fighter_url", keep="last")
    gidx = {}
    for u, n in zip(fighters.fighter_url, fighters.name):
        k = " ".join(U._wtoks(n))
        gidx[k] = None if k in gidx and gidx[k] != u else u
    gidx = {k: v for k, v in gidx.items() if v}
    cols = ["repl", "rebook", "notice", "short", "missed", "lbs", "newc"]
    R = {s + "_" + c: np.full(len(X), np.nan) for s in "ab" for c in cols}
    R["has_wiki"] = np.zeros(len(X))
    R["catch"] = np.zeros(len(X))
    Xs = X[X.date >= pd.Timestamp(FROM)]
    for (d, ev), g in Xs.groupby([X.date.dt.strftime("%Y-%m-%d"), "event"]):
        day = dt.date.fromisoformat(d)
        cand = []
        for k in (0, -1, 1):
            cand += pages.get(str(day + dt.timedelta(days=k)), [])
        if not cand:
            continue
        sur = [L1.ln(n) for n in list(g.a) + list(g.b)]
        best = max(cand, key=lambda p: U._card_fit(p["wikitext"], sur, day))
        if U._card_fit(best["wikitext"], sur, day) < 0.5:
            continue
        bouts = [(r.a_url, [r.a], r.b_url, [r.b], str(r.wc), "title" in str(r.wc).lower()) for r in g.itertuples()]
        try:
            F = U.wiki_facts(best["wikitext"], day, bouts, gidx)
        except Exception as e:
            print("parse fail", d, ev, e)
            continue
        for i, r in zip(g.index, g.itertuples()):
            R["has_wiki"][i] = 1
            R["catch"][i] = float("catch" in str(r.wc).lower())
            for s, u in (("a", r.a_url), ("b", r.b_url)):
                v = F.get(u) or {}
                R[s + "_repl"][i] = float(bool(v.get("replacement") or v.get("rebook")))
                R[s + "_rebook"][i] = float(bool(v.get("rebook")))
                nd = v.get("notice_days")
                R[s + "_notice"][i] = nd if nd is not None and 0 <= nd <= 120 else np.nan
                R[s + "_short"][i] = float(bool(v.get("short_words")))
                R[s + "_missed"][i] = float(bool(v.get("missed_weight")))
                R[s + "_lbs"][i] = v.get("lbs_over") if v.get("lbs_over") is not None else np.nan
                R[s + "_newc"][i] = float(bool(v.get("newcomer")))
    return pd.DataFrame(R, index=X.index)


# ================================================================== Best Fight Odds fighter pages: open, close range, close mean
BFO = "https://www.bestfightodds.com"
_MO = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def bfo_date(s):
    m = re.search(r"(\w{3})\w* (\d{1,2})\w{2} (\d{4})", s)
    return dt.date(int(m.group(3)), _MO[m.group(1)[:3]], int(m.group(2))) if m else None


def am(s):
    try:
        return float(s.replace("+", ""))
    except Exception:
        return np.nan


def bfo_parse(s):
    """[(event, date, me_url, me_name, open, lo, hi, spark[], opp_url, opp_name, o_open, o_lo, o_hi)]"""
    i = s.find('<table class="team-stats-table"')
    if i < 0:
        return []
    t = s[i:s.find("</table>", i)]
    rows = re.findall(r"<tr([^>]*)>(.*?)</tr>", t, re.S)
    out, ev, day, k = [], None, None, 0
    while k < len(rows):
        attr, r = rows[k]
        if "event-header" in attr:
            m = re.search(r'<a href="(/events/[^"]+)"[^>]*>(.*?)</a>\s*(.*?)</td>', r, re.S)
            ev, day = (m.group(2).strip(), bfo_date(m.group(3))) if m else (None, None)
            k += 1
            continue
        if "main-row" in attr and k + 1 < len(rows):
            r2 = rows[k + 1][1]
            f1 = re.search(r'href="(/fighters/[^"]+)"[^>]*>(.*?)</a>', r)
            f2 = re.search(r'href="(/fighters/[^"]+)"[^>]*>(.*?)</a>', r2)
            ml1 = re.findall(r'<span id="oID\d+">([^<]*)</span>', r)
            ml2 = re.findall(r'<span id="oID\d+">([^<]*)</span>', r2)
            sp = re.search(r'data-sparkline="([^"]*)"', r)
            d2 = re.search(r'color: #767676">([^<]*)<', r2)
            dd = bfo_date(d2.group(1)) if d2 else day
            if f1 and f2:
                g = lambda a, j: am(a[j]) if len(a) > j else np.nan
                spark = [float(x) for x in sp.group(1).split(",") if x.strip()] if sp and sp.group(1).strip() else []
                out.append((ev, dd, f1.group(1), f1.group(2), g(ml1, 0), g(ml1, 1), g(ml1, 2), spark,
                            f2.group(1), f2.group(2), g(ml2, 0), g(ml2, 1), g(ml2, 2)))
            k += 2
            continue
        k += 1
    return out


def fetch_bfo(out, limit=4000):
    cdir = os.path.join(out, "bfo")
    os.makedirs(cdir, exist_ok=True)
    seen, queue = set(), []
    import glob
    seeds = glob.glob(os.path.join(D, "cache", "bfo", "fighters_*.html")) + glob.glob(os.path.join(cdir, "*.html"))
    pages = {}
    for fn in seeds:
        pages[fn] = open(fn, encoding="utf-8", errors="ignore").read()

    def enqueue(s):
        for (ev, day, mu, mn, *_r) in bfo_parse(s):
            ou = _r[4]
            if ev and "UFC" in ev and day and day >= dt.date.fromisoformat(os.environ.get("BFO_FROM", "2016-06-01")):
                for u in (mu, ou):
                    if u not in seen:
                        seen.add(u)
                        queue.append(u)
    for s in pages.values():
        enqueue(s)
    n = 0
    sess = requests.Session()
    sess.headers["User-Agent"] = "Mozilla/5.0 (" + UA + ")"
    while queue and n < limit:
        u = queue.pop(0)
        fn = os.path.join(cdir, u.strip("/").replace("/", "_") + ".html")
        if os.path.exists(fn):
            enqueue(open(fn, encoding="utf-8", errors="ignore").read())
            continue
        try:
            r = sess.get(BFO + u, timeout=40)
            if r.status_code == 200:
                open(fn, "w").write(r.text)
                enqueue(r.text)
            else:
                print("http", r.status_code, u, flush=True)
                if r.status_code in (403, 429):
                    time.sleep(60)
        except Exception as e:
            print("err", u, e, flush=True)
        n += 1
        if n % 50 == 0:
            print("fetched", n, "queue", len(queue), flush=True)
        time.sleep(1.0)
    print("done", n, "queue left", len(queue))


def dec2p(x):
    return 1 / x if x and x > 1 else np.nan


def bfo_moves(out, X):
    """per bout: open and close (no-vig) for side a, close range width"""
    import glob
    rec = {}
    for fn in glob.glob(os.path.join(out, "bfo", "*.html")) + glob.glob(os.path.join(D, "cache", "bfo", "fighters_*.html")):
        for (ev, day, mu, mn, op, lo, hi, sp, ou, on, oop, olo, ohi) in bfo_parse(open(fn, encoding="utf-8", errors="ignore").read()):
            if not day or not ev or "UFC" not in ev:
                continue
            k1, k2 = L1.ln(mn), L1.ln(on)
            pa_o, pb_o = L1.am2p(op), L1.am2p(oop)
            # close: mean of the range ends' implied probs for each side
            pa_c = np.nanmean([L1.am2p(lo), L1.am2p(hi)]) if np.isfinite(lo) or np.isfinite(hi) else np.nan
            pb_c = np.nanmean([L1.am2p(olo), L1.am2p(ohi)]) if np.isfinite(olo) or np.isfinite(ohi) else np.nan
            spc = dec2p(sp[-1]) if sp else np.nan
            sp0 = dec2p(sp[0]) if sp else np.nan
            spmax = max((dec2p(x) for x in sp), default=np.nan) if sp else np.nan
            spmin = min((dec2p(x) for x in sp), default=np.nan) if sp else np.nan
            v = dict(pa_o=pa_o, pb_o=pb_o, pa_c=pa_c, pb_c=pb_c, sp_c=spc, sp_0=sp0, sp_n=len(sp), sp_max=spmax, sp_min=spmin,
                     wid=abs(L1.am2p(lo) - L1.am2p(hi)) if np.isfinite(lo) and np.isfinite(hi) else np.nan)
            rec[(day, k1, k2)] = v
            # the mirror (spark is only for the main-row man)
            rec.setdefault((day, k2, k1), dict(pa_o=pb_o, pb_o=pa_o, pa_c=pb_c, pb_c=pa_c, sp_c=np.nan, sp_0=np.nan, sp_n=0,
                                               sp_max=np.nan, sp_min=np.nan, wid=v["wid"], mirror=1))
            if (day, k1, k2) in rec and rec[(day, k1, k2)].get("mirror") and not v.get("mirror"):
                rec[(day, k1, k2)] = v
    cols = ["open", "close_bfo", "spark_move", "spark_open", "wid", "sp_n", "spark_range"]
    R = {c: np.full(len(X), np.nan) for c in cols}
    for i, (d, a, b) in enumerate(zip(X.date, X.a, X.b)):
        if d < pd.Timestamp(FROM):
            continue
        ka, kb = L1.ln(a), L1.ln(b)
        v, flip = None, False
        for k in (0, -1, 1, 2, -2):
            dd = (d + pd.Timedelta(days=k)).date()
            if (dd, ka, kb) in rec:
                v = rec[(dd, ka, kb)]
                break
            if (dd, kb, ka) in rec:
                v, flip = rec[(dd, kb, ka)], True
                break
        if not v:
            continue
        po = v["pa_o"] / (v["pa_o"] + v["pb_o"]) if np.isfinite(v["pa_o"]) and np.isfinite(v["pb_o"]) else np.nan
        pc = v["pa_c"] / (v["pa_c"] + v["pb_c"]) if np.isfinite(v["pa_c"]) and np.isfinite(v["pb_c"]) else np.nan
        sm = v["sp_c"] - v["sp_0"] if np.isfinite(v["sp_c"]) else np.nan   # one side's implied move (with vig)
        if flip:
            po, pc, sm = 1 - po, 1 - pc, -sm
        R["open"][i], R["close_bfo"][i], R["spark_move"][i] = po, pc, sm
        R["wid"][i], R["sp_n"][i] = v["wid"], v["sp_n"]
        R["spark_range"][i] = v["sp_max"] - v["sp_min"] if np.isfinite(v["sp_max"]) else np.nan
    return pd.DataFrame(R, index=X.index)


def walk_min(X, FE, y, base_tr, test, params, per="card", min_n=300):
    """round 1's blind walk, leaving p empty for cards with under min_n earlier bouts (the first 2010 cards:
       the records start in 2010, so there is nothing before them to learn from)"""
    P = np.full(len(X), np.nan)
    if per == "year":
        groups = [(pd.Timestamp("%d-01-01" % yr), (X.yr == yr).values & test) for yr in sorted(X.yr[test].unique())]
        # a year with no history before Jan 1: refit each month instead, so 2010 learns from its own early cards
        g2 = []
        for d, te in groups:
            if (base_tr & (X.date < d).values).sum() < min_n:
                mo = X.date.dt.to_period("M")
                for m in sorted(mo[te].unique()):
                    g2.append((m.to_timestamp(), te & (mo == m).values))
            else:
                g2.append((d, te))
        groups = g2
    else:
        groups = [(pd.Timestamp(d), (X.date == d).values & test) for d in sorted(X.date[test].unique())]
    for d, te in groups:
        tr = base_tr & (X.date < d).values
        if tr.sum() >= min_n:
            P[te] = L1.fit_predict(FE, y, tr, te, params)
    return P


# ================================================================== scoring helpers
def score(name, X, P, mask, note=""):
    s, g = L1.summary(name, X, P, mask, note)
    return s, g


def stack_walk(X, y, cols, train_mask, test, C=1.0, inter=False):
    """logistic stack refit before every test card on earlier bouts only; cols: list of arrays,
       antisymmetric (a-b) so no intercept. NaN -> 0."""
    Z = np.column_stack([np.nan_to_num(c, nan=0.0) for c in cols])
    P = np.full(len(X), np.nan)
    for d in sorted(X.date[test].unique()):
        te = test & (X.date == d).values
        tr = train_mask & (X.date < d).values
        Zt = np.vstack([Z[tr], -Z[tr]])
        yt = np.concatenate([y[tr], 1 - y[tr]])
        lr = LogisticRegression(C=C, fit_intercept=False, max_iter=2000).fit(Zt, yt)
        P[te] = lr.predict_proba(Z[te])[:, 1]
    return P, lr.coef_[0]


# ================================================================== main run
def run(a):
    out = a.out
    t0 = time.time()
    h = U.load_hist()
    X = h["bouts"].reset_index(drop=True).copy()
    X["date"] = pd.to_datetime(X.date)
    y = X.a_won.values.astype(int)
    men = ~U.women(X)
    dec = X.winner.isin(["red", "blue"]).values
    samp = X.train.astype(bool).values
    base_tr = men & dec & samp
    test = men & dec & (X.date >= pd.Timestamp(TEST)).values
    hist = men & dec & (X.date >= pd.Timestamp(FROM)).values
    FE0 = U.feat(X)
    C = pd.read_parquet(os.path.join(a.r1, "features_cache.parquet"))
    pm = C.pop("p_mkt").values
    FX = L1.feat_extra(X, C)
    FE2 = pd.concat([FE0, FX], axis=1)
    SLOW = dict(max_depth=3, learning_rate=0.03, max_iter=400, l2_regularization=2.0, min_samples_leaf=40, random_state=0)

    # blind stats-model p for 2017-26 (yearly refit as round 1, or per card)
    fn = os.path.join(out, "pmod_%s_%s.npy" % (a.per, FROM[:4]))
    if os.path.exists(fn):
        Pmod = np.load(fn)
    else:
        Pmod = walk_min(X, FE2, y, base_tr, hist, SLOW, per=a.per)
        np.save(fn, Pmod)
    print("model walk ready %.0fs" % (time.time() - t0))
    fn0 = os.path.join(out, "pmod0_%s_%s.npy" % (a.per, FROM[:4]))
    if os.path.exists(fn0):
        Pmod0 = np.load(fn0)
    else:
        Pmod0 = walk_min(X, FE0, y, base_tr, hist, dict(U.GBM), per=a.per)
        np.save(fn0, Pmod0)

    W = wiki_side_facts(out, h, X)
    B = bfo_moves(out, X)
    W.to_csv(os.path.join(out, "wiki_facts.csv"))
    B.to_csv(os.path.join(out, "bfo_moves.csv"))
    print("wiki on %d/%d test bouts, bfo open on %d/%d" % ((W.has_wiki[test] > 0).sum(), test.sum(),
                                                            np.isfinite(B.open[test]).sum(), test.sum()))
    has = np.isfinite(pm)
    lm = np.where(has, L1.logit(np.where(has, pm, .5)), 0.0)
    lmod = L1.logit(np.where(np.isfinite(Pmod), Pmod, .5))
    tr = hist & has & np.isfinite(Pmod)

    versions, store, cards = [], {}, {}

    def add(name, P, note=""):
        P = np.where(np.isfinite(P), P, np.where(has, pm, Pmod))
        s, g = score(name, X, P, test, note)
        versions.append(s)
        store[name] = P
        cards[name] = g
        print("%-34s acc %.1f  mean card %.1f  >=75 %.1f%%" % (name, s["acc"], s["mean_card"], s["ge75"]), flush=True)

    add("M favorite (closing line)", np.where(has, pm, Pmod))
    P4, w4 = stack_walk(X, y, [lmod, lm], tr, test)
    add("V4 blend (round 1 rebuilt)", P4, "w=%s" % np.round(w4, 2))

    # ---- fight-week facts as stack terms (a minus b)
    f = lambda c: np.nan_to_num(W["a_" + c].values, nan=0) - np.nan_to_num(W["b_" + c].values, nan=0)
    nd = lambda s: np.where(W[s + "_repl"].values > 0, np.nan_to_num(W[s + "_notice"].values, nan=14), 99)
    shortn = lambda s: ((W[s + "_repl"].values > 0) & ((nd(s) <= 14) | (W[s + "_short"].values > 0))).astype(float)
    sn = shortn("a") - shortn("b")
    miss = f("missed")
    lbs = np.nan_to_num(W.a_lbs.values, nan=0) * (W.a_missed.values > 0) - np.nan_to_num(W.b_lbs.values, nan=0) * (W.b_missed.values > 0)
    lbs = np.where(np.isnan(lbs), 0, lbs)
    repl = f("repl")
    lognd = np.where(W.a_repl.values > 0, -np.log1p(nd("a").clip(0, 99)), 0) - np.where(W.b_repl.values > 0, -np.log1p(nd("b").clip(0, 99)), 0)
    # rematch: same pair met before in the records, side a won the last meeting
    last = {}
    remat = np.zeros(len(X))
    order = X.sort_values("date").index
    for i in order:
        k = tuple(sorted([X.a_url[i], X.b_url[i]]))
        if k in last and X.date[i] > last[k][0]:
            remat[i] = 1 if last[k][1] == X.a_url[i] else -1
        if X.winner[i] in ("red", "blue"):
            # the bout row's winner side: a_won says whether a won
            last[k] = (X.date[i], X.a_url[i] if X.a_won[i] == 1 else X.b_url[i])
    debut = (np.nan_to_num(X.a_n.values if "a_n" in X else np.zeros(len(X))) == 0).astype(float) if "a_n" in X else None
    fw = dict(short=sn, miss=miss, lbs=lbs, repl=repl, lognotice=lognd, rematch=remat)
    for k, v in fw.items():
        m = test & (v != 0)
        print("fact %-10s nonzero on %d test bouts (%d with a price)" % (k, m.sum(), (m & has).sum()))
    P5, w5 = stack_walk(X, y, [lmod, lm, sn, miss, lbs], tr, test)
    add("V5 +fight-week (short notice, missed weight)", P5, "w=%s" % np.round(w5, 3))
    P5b, w5b = stack_walk(X, y, [lmod, lm, sn, miss, lbs, repl, lognd, remat], tr, test)
    add("V5b +all fight-week facts, rematch", P5b, "w=%s" % np.round(w5b, 3))
    # interaction: does the market under-react to facts in pick'ems? facts x (1-|2p-1|)
    pk = 1 - np.abs(2 * np.where(has, pm, .5) - 1)
    P5c, w5c = stack_walk(X, y, [lmod, lm, sn, miss, lbs, sn * pk, miss * pk], tr, test)
    add("V5c fight-week x pick'em", P5c, "w=%s" % np.round(w5c, 3))

    # ---- line movement
    op = B.open.values
    hop = np.isfinite(op)
    lop = np.where(hop, L1.logit(np.where(hop, op, .5)), 0)
    lcl = np.where(np.isfinite(B.close_bfo.values), L1.logit(np.nan_to_num(B.close_bfo.values, nan=.5)), lm)
    mv = np.where(hop, lcl - lop, 0)          # logit move toward a
    spm = np.nan_to_num(B.spark_move.values, nan=0)
    print("bfo open on %d test bouts; move sd %.3f" % ((hop & test).sum(), np.std(mv[hop & test])))
    P6, w6 = stack_walk(X, y, [lmod, lm, mv], tr, test)
    add("V6 +line move (open->close)", P6, "w=%s" % np.round(w6, 3))
    P6b, w6b = stack_walk(X, y, [lmod, lm, lop], tr, test)
    add("V6b +opening line as its own term", P6b, "w=%s" % np.round(w6b, 3))
    P6c, w6c = stack_walk(X, y, [lmod, lm, mv, spm, mv * pk], tr, test)
    add("V6c +move, spark move, move x pick'em", P6c, "w=%s" % np.round(w6c, 3))
    # closing average of BFO books vs gidstats close (two closes)
    P6d, w6d = stack_walk(X, y, [lmod, lm, lcl], tr, test)
    add("V6d +BFO close mean beside gidstats close", P6d, "w=%s" % np.round(w6d, 3))

    # ---- all together
    P7, w7 = stack_walk(X, y, [lmod, lm, sn, miss, lbs, mv], tr, test)
    add("V7 V4 + fight-week + move", P7, "w=%s" % np.round(w7, 3))

    # ---- coin-flip sub-models: residual GBM on style features inside pick'ems, fit on earlier bouts
    from sklearn.ensemble import HistGradientBoostingClassifier
    mconf = np.maximum(pm, 1 - pm)
    coin = has & (mconf < 0.6)
    sty = style_feats(X, FE0)
    Zs = np.column_stack([lm, lmod] + [np.nan_to_num(sty[c].values, nan=0) for c in sty.columns])
    P8 = P7.copy()
    for yr in sorted(X.yr[test].unique()):
        te = test & (X.yr == yr).values & coin
        trc = hist & coin & (X.date < pd.Timestamp("%d-01-01" % yr)).values & np.isfinite(Pmod)
        # pre-2017 coin bouts with a market price are not in hist; use all priced bouts before the year
        if trc.sum() < 300:
            continue
        g = HistGradientBoostingClassifier(max_depth=2, learning_rate=0.03, max_iter=150, min_samples_leaf=60,
                                           l2_regularization=3.0, random_state=0)
        g.fit(np.vstack([Zs[trc], -Zs[trc]]), np.concatenate([y[trc], 1 - y[trc]]))
        p = (g.predict_proba(Zs[te])[:, 1] + 1 - g.predict_proba(-Zs[te])[:, 1]) / 2
        P8[te] = p
    add("V8 V7 + coin-flip style GBM (fav<60%)", P8, "style: td, sub, reach, stance, pace, ctrl, age inside pick'ems")
    # linear style terms inside pick'ems
    Ps, ws = stack_walk(X, y, [lmod, lm, sn, miss, lbs, mv] + [np.nan_to_num(sty[c].values, nan=0) * pk for c in sty.columns],
                        tr, test, C=0.3)
    add("V8b V7 + style x pick'em (linear)", Ps, "")
    # production features model only (V0 GBM) blended, to check which model helps
    lmod0 = L1.logit(np.where(np.isfinite(Pmod0), Pmod0, .5))
    P9, w9 = stack_walk(X, y, [lmod, lmod0, lm, sn, miss, lbs, mv], tr, test)
    add("V9 both stats models + market + facts + move", P9, "w=%s" % np.round(w9, 3))

    # ------------------------------------------------ coin-flip third: hit rate per version
    rows = []
    for k, P in store.items():
        r = np.where(P > .5, y == 1, y == 0)
        rows.append(dict(version=k, coin_n=int((test & coin).sum()), coin_hit=100 * r[test & coin].mean(),
                         rest_hit=100 * r[test & ~coin].mean()))
    CF = pd.DataFrame(rows)

    # ------------------------------------------------ facts: raw hit of the market in bouts with each fact
    FT = []
    for k, v in (("short-notice side", sn), ("missed weight side", miss), ("rematch", remat), ("line moved 5+ pts", None)):
        if v is None:
            mvp = np.where(hop, np.abs(np.where(np.isfinite(B.close_bfo.values), B.close_bfo.values, pm) - op), 0)
            m = test & hop & (mvp >= 0.05)
            # did the side the line moved toward win?
            tow = np.sign(np.where(np.isfinite(B.close_bfo.values), B.close_bfo.values, pm) - op)
            hit = np.where(tow > 0, y == 1, y == 0)[m].mean() * 100
            fav = np.where(pm > .5, y == 1, y == 0)[m].mean() * 100
            FT.append(dict(fact=k, bouts=int(m.sum()), fact_side_won=hit, favorite_won=fav))
            continue
        m = test & (v != 0) & has
        side_won = np.where(v > 0, y == 1, y == 0)[m].mean() * 100   # the side with the fact (short/miss) or the last winner
        fav = np.where(pm > .5, y == 1, y == 0)[m].mean() * 100
        imp = np.where(v > 0, pm, 1 - pm)[m].mean() * 100
        FT.append(dict(fact=k, bouts=int(m.sum()), fact_side_won=side_won, fact_side_priced=imp, favorite_won=fav))
    FT = pd.DataFrame(FT)
    write(out, X, y, test, versions, store, cards, CF, FT, pm, W, B)
    print("done %.0fs" % (time.time() - t0))
    if a.loop:
        terms = dict(sn=sn, miss=miss, lbs=lbs, repl=repl, lognd=lognd, remat=remat, mv=mv, spm=spm, lop=lop)
        loop(out, h, X, y, men & dec, test, has, pm, Pmod, Pmod0, FE2, sty, terms, pk, W, B)


def style_feats(X, FE0):
    """style matchup terms from production side stats (a minus b and products)"""
    g = lambda c: X[c].values.astype(float) if c in X else np.full(len(X), np.nan)
    out = {}
    for c in ("tdpm", "tddef", "subpm", "ctrl_share", "slpm", "sapm", "acc", "kdpm", "reach", "age", "height"):
        if "a_" + c in X:
            out["d_" + c] = g("a_" + c) - g("b_" + c)
    if "a_tdpm" in X and "b_tddef" in X:
        out["wrest_edge"] = g("a_tdpm") * (1 - g("b_tddef")) - g("b_tdpm") * (1 - g("a_tddef"))
    if "a_slpm" in X:
        out["strike_edge"] = (g("a_slpm") - g("b_sapm")) - (g("b_slpm") - g("a_sapm"))
    if "a_stance" in X:
        sa, sb = X.a_stance.astype(str), X.b_stance.astype(str)
        out["south_vs_orth"] = ((sa == "Southpaw") & (sb == "Orthodox")).astype(float) - ((sb == "Southpaw") & (sa == "Orthodox")).astype(float)
    return pd.DataFrame(out, index=X.index)


def write(out, X, y, test, versions, store, cards, CF, FT, pm, W, B):
    V = pd.DataFrame(versions)
    V.to_csv(os.path.join(out, "versions.csv"), index=False)
    CF.to_csv(os.path.join(out, "coinflip.csv"), index=False)
    FT.to_csv(os.path.join(out, "facts.csv"), index=False)
    BO = X.loc[test, ["date", "event", "wc", "a", "b", "winner", "method"]].copy()
    BO["p_mkt"] = pm[test]
    for k, P in store.items():
        BO["p_" + re.sub(r"\W+", "_", k.split()[0])] = P[test]
    BO["a_won"] = y[test]
    BO = pd.concat([BO, W.loc[test], B.loc[test]], axis=1)
    BO.to_csv(os.path.join(out, "bouts.csv"), index=False)
    for k, g in cards.items():
        g.to_csv(os.path.join(out, "per_card_%s.csv" % re.sub(r"\W+", "_", k.split()[0])), index=False)
    print(L1.md_table(V[["version", "bouts", "acc", "mean_card", "med_card", "ge75"]]))
    print(L1.md_table(CF))
    print(L1.md_table(FT))


def matchmaking(h, X):
    """how the UFC booked the bout, all known before the card: d_* are a-minus-b terms, i_* bout indicators"""
    F = h["fights"].copy()
    F["pos"] = F.groupby("event_name", sort=False).cumcount()
    F["ncard"] = F.groupby("event_name", sort=False).fight_url.transform("size")
    pos = dict(zip(F.fight_url, F.pos))
    nc = dict(zip(F.fight_url, F.ncard))
    sr = dict(zip(F.fight_url, pd.to_numeric(F.scheduled_rounds, errors="coerce")))
    p = np.array([pos.get(u, np.nan) for u in X.fight_url], float)
    n = np.array([nc.get(u, np.nan) for u in X.fight_url], float)
    rounds5 = np.array([sr.get(u, 3) for u in X.fight_url], float) == 5
    title = X.wc.astype(str).str.contains("Title").values
    # rankings: the last snapshot before the card, best rank in any men's division; champion = 0, unranked = 16
    R = pd.read_csv(os.path.join(D, "data", "ufc_records", "rankings.csv"))
    R = R[~R.weightclass.str.contains("Pound|Women")].copy()
    R["k"] = [" ".join(U._wtoks(x)) for x in R.fighter.astype(str)]
    R["date"] = pd.to_datetime(R.date)
    snaps = np.array(sorted(R.date.unique()))
    by = {d: g.groupby("k")["rank"].min().to_dict() for d, g in R.groupby("date")}

    def rank(name, d):
        i = np.searchsorted(snaps, np.datetime64(d)) - 1
        if i < 0 or (np.datetime64(d) - snaps[i]) > np.timedelta64(60, "D"):
            return np.nan
        return by[snaps[i]].get(" ".join(U._wtoks(name)), 16)
    ra = np.array([rank(a, d) for a, d in zip(X.a, X.date)], float)
    rb = np.array([rank(b, d) for b, d in zip(X.b, X.date)], float)
    g = lambda c: X[c].values.astype(float)
    deb_a, deb_b = (g("a_n") == 0), (g("b_n") == 0)
    main = p < 5
    out = dict(
        pos=p, ncard=n,
        d_rank_gap=np.where(np.isfinite(ra) & np.isfinite(rb), rb - ra, 0),
        d_ranked=np.where(np.isfinite(ra) & np.isfinite(rb), (ra < 16).astype(float) - (rb < 16), 0),
        d_prospect=((g("a_age") <= 28) & (g("a_streak") >= 3)).astype(float) - ((g("b_age") <= 28) & (g("b_streak") >= 3)),
        d_vet_slide=((g("a_age") >= 33) & (g("a_l3") <= 0.34)).astype(float) - ((g("b_age") >= 33) & (g("b_l3") <= 0.34)),
        d_unbeaten_pro=((g("a_pl") == 0) & (g("a_pn") >= 5)).astype(float) - ((g("b_pl") == 0) & (g("b_pn") >= 5)),
        d_debut_vs_elo=np.where(deb_b & ~deb_a, np.nan_to_num(g("a_elo") - 1500), 0) - np.where(deb_a & ~deb_b, np.nan_to_num(g("b_elo") - 1500), 0),
        d_newcomer_maincard=(deb_a & main).astype(float) - (deb_b & main),
        d_tenure=np.log1p(np.nan_to_num(g("a_n"))) - np.log1p(np.nan_to_num(g("b_n"))),
        d_won_last=((g("a_last_loss") == 0) & ~deb_a).astype(float) - ((g("b_last_loss") == 0) & ~deb_b),
        i_main_event=(p == 0).astype(float), i_co_main=(p == 1).astype(float), i_main_card=main.astype(float),
        i_early_prelim=(p >= n - 3).astype(float) * (n >= 11), i_five_rd_nontitle=(rounds5 & ~title).astype(float),
        i_title=title.astype(float), i_both_ranked=((ra < 16) & (rb < 16)).astype(float),
        i_unranked_pair=((ra == 16) & (rb == 16)).astype(float),
    )
    return pd.DataFrame(out, index=X.index)


def newton(Z, y, w=None, it=8):
    """the stack's logistic fit, no intercept, mirrored sides and L2 as sklearn C=1 (2*sum ll + |w|^2/2)"""
    w = np.zeros(Z.shape[1]) if w is None else w.copy()
    for _ in range(it):
        p = 1 / (1 + np.exp(-Z @ w))
        g = 2 * Z.T @ (p - y) + w
        H = 2 * (Z * (p * (1 - p))[:, None]).T @ Z + np.eye(len(w))
        st = np.linalg.solve(H, g)
        w -= st
        if np.abs(st).max() < 1e-6:
            break
    return w


# ================================================================== the learning loop
def loop(out, h, X, y, md, test, has, pm, Pmod, Pmod0, FE2, sty, terms, pk, W, B, K=5, MIN_N=40, GAIN=None, NOMINATE=None):
    GAIN = float(os.environ.get("LOOP_GAIN", 0.15)) if GAIN is None else GAIN
    NOMINATE = os.environ.get("LOOP_NOMINATE", "score") if NOMINATE is None else NOMINATE
    """walk card by card from LOOP: predict with the current term set S (stack refit on earlier bouts),
       review the card, write a lesson per miss, nominate the terms the lessons favor, and adopt one only
       if it lifts the per-card mean on cards already finished (every score below is blind: each card's
       p comes from a stack fit on bouts before it)"""
    t0 = time.time()
    D0, DL = pd.Timestamp(FROM), pd.Timestamp(LOOP)
    lm = np.where(has, L1.logit(np.where(has, pm, .5)), 0.0)
    lmod = L1.logit(np.where(np.isfinite(Pmod), Pmod, .5))
    lmod0 = L1.logit(np.where(np.isfinite(Pmod0), Pmod0, .5))
    stackm = md & has & np.isfinite(Pmod) & (X.date >= D0).values
    evalm = md & (X.date >= D0).values
    pre = md & (X.date >= D0).values & (X.date < DL).values
    pool = {}

    def put(name, v):
        v = np.nan_to_num(np.asarray(v, float), nan=0.0, posinf=0.0, neginf=0.0)
        nz = v[md] != 0                       # scale only: no outcome enters it
        sd = v[md][nz].std() if nz.sum() > 30 else 0
        if sd > 0 and nz.mean() > 0.003:
            pool[name] = v / sd
    put("lmod", lmod)
    put("lm", lm)
    for c in FE2.columns:
        put("f:" + c, FE2[c].values)
        put("f:%s x pickem" % c, FE2[c].values * pk)
    for c in sty.columns:
        put("style:" + c, sty[c].values)
        put("style:%s x pickem" % c, sty[c].values * pk)
    for k, v in terms.items():
        put("fact:" + k, v)
        put("fact:%s x pickem" % k, v * pk)
    wc = X.wc.astype(str)
    ind = {"LHW": wc.str.contains("Light Heavyweight").values,
           "HW": wc.str.contains("Heavyweight").values & ~wc.str.contains("Light").values,
           "FLY": wc.str.contains("Flyweight").values, "title": wc.str.contains("Title").values,
           "debut": ((X.a_n == 0) | (X.b_n == 0)).values, "thin": (np.minimum(X.a_n, X.b_n) <= 2).values,
           "35+": ((X.a_age >= 35) | (X.b_age >= 35)).values, "layoff": ((X.a_layoff >= 365) | (X.b_layoff >= 365)).values,
           "pickem": pk > 0.8, "missed": (W.a_missed.fillna(0) + W.b_missed.fillna(0)).values > 0,
           "short": terms["sn"] != 0}
    for k, m in ind.items():
        put("rule: market x %s" % k, lm * m)
        put("rule: model x %s" % k, lmod * m)
    put("rule: model0", lmod0)
    put("rule: model-market gap", lmod - lm)
    MM = matchmaking(h, X)
    MM.to_csv(os.path.join(out, "matchmaking.csv"))
    for c in [c for c in MM.columns if c.startswith("d_")]:
        put("mm:" + c[2:], MM[c].values)
        put("mm:%s x pickem" % c[2:], MM[c].values * pk)
    for c in [c for c in MM.columns if c.startswith("i_")]:
        put("mm rule: market x %s" % c[2:], lm * MM[c].values)
        put("mm rule: model x %s" % c[2:], lmod * MM[c].values)
    names = list(pool)
    print("loop pool %d terms" % len(names), flush=True)

    # card ids
    key = X.date.dt.strftime("%Y-%m-%d") + " | " + X.event.astype(str)
    cid_all = pd.factorize(key)[0]
    days = np.array(sorted(X.date[evalm].unique()))
    cache = {}

    def walk_set(S):
        S = tuple(sorted(S))
        if S in cache:
            return cache[S]
        Z = np.column_stack([pool[n] for n in S])
        P = np.full(len(X), np.nan)
        dv = X.date.values
        w = np.zeros(Z.shape[1])
        for d in days:
            te = evalm & (dv == d)
            tr = stackm & (dv < d)
            if tr.sum() < 100:                  # the first cards: no blind history yet, the favorite
                P[te] = np.where(has[te], pm[te], 0.5)
                continue
            w = newton(Z[tr], y[tr], w)
            P[te] = 1 / (1 + np.exp(-Z[te] @ w))
        cache[S] = P
        return P

    def card_mean(P, m):
        r = np.where(P > .5, y == 1, y == 0).astype(float)
        c = cid_all[m]
        u, inv = np.unique(c, return_inverse=True)
        acc = np.bincount(inv, r[m]) / np.bincount(inv)
        ll = -np.mean(np.log(np.clip(np.where(y[m] == 1, P[m], 1 - P[m]), 1e-6, 1)))
        return 100 * acc.mean(), ll

    rnd = h["fights"].set_index("fight_url")["round"].to_dict() if "round" in h["fights"] else {}
    S = ["lmod", "lm"]
    adopted, lessons, Ploop = [], [], np.full(len(X), np.nan)
    stat = {n: [0, 0] for n in names}      # [bouts the term stood against the pick strongly, of those the term was right]
    sc1 = {n: 0.0 for n in names}          # score test of each term on the reviewed bouts: sum (y - p) z
    sc2 = {n: 0.0 for n in names}          #   and its variance sum p(1-p) z^2
    lp = md & (X.date >= DL).values
    ldays = sorted(X.date[lp].unique())
    tw = time.time()
    for i, d in enumerate(ldays):
        te = lp & (X.date.values == d)
        P = walk_set(S)
        Ploop[te] = P[te]
        # ---- the review
        pa = P[te] > .5
        idx = np.where(te)[0]
        for j, ia in zip(idx, pa):
            won_a = y[j] == 1
            for n in names:
                sc1[n] += (y[j] - P[j]) * pool[n][j]
                sc2[n] += P[j] * (1 - P[j]) * pool[n][j] ** 2
            right = ia == won_a
            sgn_pick = 1 if ia else -1
            for n in names:
                if n in ("lmod", "lm"):
                    continue
                v = pool[n][j] * sgn_pick
                if v < -0.5:                      # the term stood against the pick
                    stat[n][0] += 1
                    stat[n][1] += int(not right)  # and the pick lost: the term was right
            sw = 1 if won_a else -1                     # toward the winner
            ori = {n: pool[n][j] * sw for n in names if n not in ("lmod", "lm")}

            def tops(vals, k):
                out_, seen_ = [], set()
                for v, n in sorted(vals, reverse=True):
                    b_ = n.replace(" x pickem", "").replace("style:d_", "f:")
                    if b_ not in seen_:
                        seen_.add(b_)
                        out_.append((v, n))
                    if len(out_) == k:
                        break
                return out_
            tw_ = tops([(v, n) for n, v in ori.items() if v > 0.5], 5)
            tl_ = tops([(-v, n) for n, v in ori.items() if v < -0.5], 3)
            fav_a = pm[j] > .5 if has[j] else Pmod[j] > .5
            upset = has[j] and (fav_a != won_a)
            facts = [n.split(":")[1] for n in ("fact:sn", "fact:miss", "fact:remat", "fact:mv", "fact:repl") if n in ori and ori[n] > 0]
            if right:
                cause = "pick right" + (" (an upset the pick saw)" if upset else "")
            elif tw_:
                cause = tw_[0][1]
            else:
                cause = "coin flip" if has[j] and max(pm[j], 1 - pm[j]) < .6 else "upset, nothing pointed to it"
            lessons.append(dict(card_date=str(pd.Timestamp(d).date()), card=X.event[j], bout="%s vs %s" % (X.a[j], X.b[j]),
                                result="hit" if right else "miss", upset=bool(upset),
                                pick=X.a[j] if ia else X.b[j], pick_p=round(float(max(P[j], 1 - P[j])), 3),
                                winner=X.a[j] if won_a else X.b[j], method=X.method[j], round=rnd.get(X.fight_url[j], ""),
                                market_fav=(X.a[j] if pm[j] > .5 else X.b[j]) if has[j] else "",
                                p_mkt_winner=round(float(pm[j] if won_a else 1 - pm[j]), 3) if has[j] else np.nan,
                                model_pick=(X.a[j] if Pmod[j] > .5 else X.b[j]),
                                suspected_cause=cause,
                                pointed_to_winner="; ".join("%s %+.1f" % (n, v) for v, n in tw_),
                                pointed_to_loser="; ".join("%s %+.1f" % (n, v) for v, n in tl_),
                                fight_week_or_move_toward_winner=", ".join(facts), graded=bool(test[j])))
        # ---- nominate and test (results of this card are now known)
        seen = lp & (X.date.values <= d) | (evalm & (X.date.values < DL))
        known = evalm & (X.date.values <= d)
        if NOMINATE == "against":
            cand = sorted(((stat[n][1] / stat[n][0], n) for n in names if n not in S and stat[n][0] >= MIN_N), reverse=True)[:K]
        else:   # the lessons' residual: terms whose value lines up with what the picks got wrong (score z > 2)
            zs = sorted(((sc1[n] / np.sqrt(sc2[n]), n) for n in names if n not in S and sc2[n] > 0), reverse=True)
            cand = [(1.0, n) for zz, n in zs[:K] if zz > 2.0] + [(1.0, n) for zz, n in sorted(zs)[:K] if zz < -2.0]
        base, bll = card_mean(P, known)
        best = None
        for rate, n in cand:
            if rate <= 0.5:
                continue
            Pc = walk_set(S + [n])
            m, ll = card_mean(Pc, known)
            if m - base >= GAIN and ll <= bll + 1e-4 and (best is None or m > best[0]):
                best = (m, ll, n, rate)
        if best:
            S = S + [best[2]]
            zz = sc1[best[2]] / np.sqrt(sc2[best[2]])
            adopted.append(dict(date=str(pd.Timestamp(d).date()), action="adopt", term=best[2], lesson_score_z=round(zz, 2),
                                lesson_n=stat[best[2]][0], prior_mean_before=round(base, 2), prior_mean_after=round(best[0], 2),
                                prior_cards=int(len(np.unique(cid_all[known])))))
            print("  %s adopt %-36s prior mean %.2f -> %.2f (lesson z %.2f)" % (adopted[-1]["date"], best[2], base, best[0], zz), flush=True)
        elif i % 8 == 7 and len(S) > 2:
            for n in S[2:]:
                Pc = walk_set([x for x in S if x != n])
                m, ll = card_mean(Pc, known)
                if m - base >= 0.1:
                    S = [x for x in S if x != n]
                    adopted.append(dict(date=str(pd.Timestamp(d).date()), action="drop", term=n, prior_mean_before=round(base, 2),
                                        prior_mean_after=round(m, 2), prior_cards=int(len(np.unique(cid_all[known])))))
                    print("  %s drop %s" % (adopted[-1]["date"], n), flush=True)
                    break
        if i % 40 == 0:
            print("card %d/%d %s |S|=%d walks %d %.0fs" % (i, len(ldays), str(pd.Timestamp(d).date()), len(S), len(cache), time.time() - tw), flush=True)
    Lz = pd.DataFrame(lessons)
    ups = []
    dm = md & has & (X.date >= D0).values
    dog_a = pm < .5
    ydog = np.where(dog_a, y == 1, y == 0).astype(float)
    pdog = np.where(dog_a, pm, 1 - pm)
    for n in names:
        if n in ("lmod", "lm"):
            continue
        tdog = pool[n] * np.where(dog_a, 1, -1)       # the term, toward the underdog
        for lab, m in (("2010-21", dm & ~test), ("2022-26", dm & test)):
            k = m & (tdog > 0.5)
            if k.sum() >= 30:
                ups.append(dict(term=n, window=lab, bouts=int(k.sum()), dog_won=100 * ydog[k].mean(), dog_priced=100 * pdog[k].mean(),
                                excess=100 * (ydog[k].mean() - pdog[k].mean())))
    UP = pd.DataFrame(ups)
    if len(UP):
        UP = UP.pivot_table(index="term", columns="window", values=["bouts", "dog_won", "dog_priced", "excess"])
        UP.columns = ["%s_%s" % c for c in UP.columns]
        UP = UP.sort_values("excess_2010-21", ascending=False)
        UP.to_csv(os.path.join(out, "upset_signals.csv"))
    Lz.to_csv(os.path.join(out, "lessons.csv"), index=False)
    pd.DataFrame(adopted).to_csv(os.path.join(out, "adoptions.csv"), index=False)
    stt = pd.DataFrame([dict(term=n, against_pick=v[0], term_right=v[1], rate=100 * v[1] / v[0] if v[0] else np.nan,
                             score_z=sc1[n] / np.sqrt(sc2[n]) if sc2[n] > 0 else np.nan)
                        for n, v in stat.items()]).sort_values("score_z", ascending=False)
    stt.to_csv(os.path.join(out, "lesson_stats.csv"), index=False)
    Pl = np.where(np.isfinite(Ploop), Ploop, pm)
    P4 = walk_set(["lmod", "lm"])
    rows = []
    for nm, P in (("loop (learning, 2010 start)", Pl), ("V4 static blend, same stack", P4), ("market favorite", np.where(has, pm, Pmod))):
        for lab, m in (("graded 2022-26", test), ("full 2010-26", lp)):
            s_, g = L1.summary(nm, X, P, m)
            rows.append(dict(version=nm, window=lab, bouts=s_["bouts"], cards=s_["cards"], acc=round(s_["acc"], 1),
                             mean_card=round(s_["mean_card"], 1), ge75=round(s_["ge75"], 1)))
            if lab.startswith("graded") and nm.startswith("loop"):
                g.to_csv(os.path.join(out, "per_card_loop.csv"), index=False)
    R = pd.DataFrame(rows)
    R.to_csv(os.path.join(out, "loop_summary.csv"), index=False)
    # learning curve: trailing 10 / 25 card means for the loop, the static blend and the favorite
    cur = {}
    for nm, P in (("loop", Pl), ("v4", P4), ("fav", np.where(has, pm, Pmod))):
        _, g = L1.summary(nm, X, P, lp)
        cur[nm] = g.set_index(["date", "card"]).pct
    Cv = pd.DataFrame(cur).reset_index()
    for w in (10, 25):
        for nm in ("loop", "v4", "fav"):
            Cv["%s_t%d" % (nm, w)] = Cv[nm].rolling(w).mean()
        Cv["edge_t%d" % w] = Cv["loop_t%d" % w] - Cv["fav_t%d" % w]
    Cv["n_lessons"] = [int((Lz.card_date <= d).sum()) if len(Lz) else 0 for d in Cv.date]
    Cv["n_adopted"] = [sum(1 for x in adopted if x["date"] <= d and x["action"] == "adopt") - sum(1 for x in adopted if x["date"] <= d and x["action"] == "drop") for d in Cv.date]
    Cv.to_csv(os.path.join(out, "learning_curve.csv"), index=False)
    ok = Cv.dropna(subset=["edge_t25"])
    sl = np.polyfit(np.arange(len(ok)), ok.edge_t25.values, 1)[0] * 100 if len(ok) > 10 else np.nan
    sl2 = np.polyfit(np.arange(len(ok)), ok.loop_t25.values, 1)[0] * 100 if len(ok) > 10 else np.nan
    print("learning curve: trailing-25 loop mean slope %+.2f pts per 100 cards; edge over favorite slope %+.2f" % (sl2, sl))
    for yr, g in Cv.groupby(Cv.date.str[:4]):
        print("  %s cards %d loop %.1f v4 %.1f fav %.1f" % (yr, len(g), g.loop.mean(), g.v4.mean(), g.fav.mean()))
    print(L1.md_table(R))
    print("final set:", S)
    print("loop done %.0fs, %d lessons, %d walks" % (time.time() - t0, len(Lz), len(cache)))
    return R, S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["fetch-wiki", "fetch-bfo", "run"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--r1", default=None, help="round 1 folder (features_cache.parquet)")
    ap.add_argument("--per", default="year", choices=["year", "month", "card"])
    ap.add_argument("--limit", type=int, default=4000)
    ap.add_argument("--loop", action="store_true", help="also run the card-by-card learning loop")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    if a.cmd == "fetch-wiki":
        fetch_wiki(a.out)
    elif a.cmd == "fetch-bfo":
        fetch_bfo(a.out, a.limit)
    else:
        run(a)


if __name__ == "__main__":
    main()
