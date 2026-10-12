"""Fit on 2016-2021, test blind on 2022..2026, FBS vs FBS starters only.

  python3 model.py   -> model.pkl, preds.parquet, results.txt (all the tables)
"""
import glob, json, os, pickle, sys
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

D = os.path.dirname(os.path.abspath(__file__))
TRAIN = list(range(2016, 2022))
BLIND = [2022, 2023, 2024, 2025, 2026]
FEATS = ["q_td", "q_hit", "q_att", "lq_n", "t_td", "t_pts", "o_td", "o_pts", "home", "away",
         "spread_f", "total_f", "itt_f", "has_line", "conf", "early", "post"]
BANDS = [(0.90, 1.01, "90+"), (0.85, 0.90, "85-89"), (0.80, 0.85, "80-84"), (0.75, 0.80, "75-79"), (0, 0.75, "<75")]
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    OUT.append(s)
    print(s)


def prep(X):
    X = X.copy()
    X["lq_n"] = np.log1p(X.q_n)
    X["conf"] = X.conf.astype(int)
    X["early"] = (X.gnum < 3).astype(int)
    X["post"] = (X.stype == 3).astype(int)
    # no line: stand in a neutral spread and a total from both teams' scoring form
    X["total_f"] = X.total.fillna((X.t_pts + X.o_pts))
    X["spread_f"] = X.spread.fillna(0.0)
    X["itt_f"] = X.total_f / 2 - X.spread_f / 2
    return X


def make_lr():
    return make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000))


def make_gb():
    return HistGradientBoostingClassifier(max_iter=250, learning_rate=0.04, max_leaf_nodes=15,
                                          min_samples_leaf=80, l2_regularization=1.0, random_state=0)


def bands(df, col="p"):
    rows = []
    for lo, hi, nm in BANDS:
        s = df[(df[col] >= lo) & (df[col] < hi)]
        rows.append((nm, len(s), s.y.mean() if len(s) else np.nan))
    return rows


def rule_eval(df, mask):
    s = df[mask]
    wk = s.groupby(["season", "stype", "week"]).size()
    return len(s), (s.y.mean() if len(s) else np.nan), (wk.mean() if len(wk) else 0)


def implied_1plus(line, over_odds, under_odds):
    """Poisson: no-vig P(over line) -> lambda -> P(1+)."""
    from scipy.optimize import brentq
    from scipy.stats import poisson
    dec = lambda a: 1 + (a / 100 if a > 0 else 100 / -a)
    po, pu = 1 / dec(over_odds), 1 / dec(under_odds)
    p_over = po / (po + pu)
    k = int(np.floor(line))  # over 1.5 -> P(X>=2) = 1-cdf(1)
    f = lambda lam: (1 - poisson.cdf(k, lam)) - p_over
    lam = brentq(f, 1e-4, 15)
    return 1 - np.exp(-lam)


def book_2026(P):
    """Join BettingPros 2026 consensus pass-TD lines (market 441) to the 2026 rows by date + last name."""
    rows = []
    for f in sorted(glob.glob(os.path.join(D, "bp", "2026_*.json"))):
        wk = f.split("_")[-1][:-5]
        evf = os.path.join(D, "bp", f"ev_2026_{wk}.json")
        if not os.path.exists(evf):
            continue
        ev = json.load(open(evf))
        for r in json.load(open(f)):
            o, u = r.get("over") or {}, r.get("under") or {}
            ln, oo, uo = o.get("consensus_line") or o.get("line"), o.get("consensus_odds") or o.get("odds"), u.get("consensus_odds") or u.get("odds")
            if ln is None or oo is None or uo is None or str(r["event_id"]) not in ev:
                continue
            try:
                b = implied_1plus(float(ln), float(oo), float(uo))
            except Exception:
                continue
            pl = r["participant"]["player"]
            rows.append(dict(day=pd.Timestamp(ev[str(r["event_id"])]).tz_localize("UTC").tz_convert("US/Eastern").date(),
                             last=pl["last_name"].lower().split(" ")[0], bline=float(ln), book=b))
    B = pd.DataFrame(rows).drop_duplicates(["day", "last"])
    P = P.copy()
    P["day"] = P.date.dt.tz_convert("US/Eastern").dt.date
    P["last"] = P.qb_name.str.split(" ").str[1:].str.join(" ").str.lower().str.replace(r"[^a-z\- ]", "", regex=True).str.split(" ").str[0]
    return P.merge(B, on=["day", "last"], how="left")


def main():
    X = prep(pd.read_parquet(os.path.join(D, "data.parquet")))
    tr, te = X[X.season.isin(TRAIN)], X[X.season.isin(BLIND)].copy()
    say("rows: train", len(tr), "blind", len(te))
    say("\n## Base rate of 1+ PTD, FBS starter, FBS vs FBS")
    for s, g in X.groupby("season"):
        say(f"  {s}: {g.y.mean():.1%} of {len(g)}  (line on {g.has_line.mean():.0%})")

    # leave-one-season-out on the training years -> out-of-fold predictions to pick a rule
    oof = tr[["season", "week", "y", "itt_f", "has_line", "total_f", "spread_f"]].copy()
    for name, mk in (("lr", make_lr), ("gb", make_gb)):
        oof[name] = np.nan
        for s in sorted(tr.season.unique()):
            m = mk().fit(tr[tr.season != s][FEATS], tr[tr.season != s].y)
            oof.loc[tr.season == s, name] = m.predict_proba(tr[tr.season == s][FEATS])[:, 1]
    lr, gb = make_lr().fit(tr[FEATS], tr.y), make_gb().fit(tr[FEATS], tr.y)
    te["lr"], te["gb"] = lr.predict_proba(te[FEATS])[:, 1], gb.predict_proba(te[FEATS])[:, 1]
    coef = dict(zip(FEATS, lr[-1].coef_[0].round(3)))
    say("\nLR standardized coefficients:", coef)

    say("\n## Blind fit by season (AUC / Brier)")
    for s, g in te.groupby("season"):
        say(f"  {s}: n={len(g)}  LR AUC {roc_auc_score(g.y, g.lr):.3f} Brier {brier_score_loss(g.y, g.lr):.4f}  |  "
            f"GB AUC {roc_auc_score(g.y, g.gb):.3f} Brier {brier_score_loss(g.y, g.gb):.4f}  |  "
            f"base-only Brier {brier_score_loss(g.y, np.full(len(g), tr.y.mean())):.4f}")
    for name in ("lr", "gb"):
        say(f"\n## Hit rate by model band, blind ({name.upper()})")
        say("  band   " + "  ".join(f"{s:>14}" for s in BLIND))
        per = {s: bands(te[te.season == s].assign(p=te[name])) for s in BLIND}
        for i, (lo, hi, nm) in enumerate(BANDS):
            say(f"  {nm:<6} " + "  ".join(f"{per[s][i][2]:>7.1%} n={per[s][i][1]:<5}" if per[s][i][1] else f"{'-':>14}" for s in BLIND))
        say("  (train out-of-fold) " + "  ".join(f"{nm} {r[2]:.1%}/{r[1]}" for (lo, hi, nm), r in zip(BANDS, bands(oof.assign(p=oof[name])))))

    # rule search on the TRAINING out-of-fold predictions only; then read it blind
    say("\n## Rule search (chosen on 2016-2021 out-of-fold, then read blind)")
    cands = []
    for name in ("lr", "gb"):
        for pt in np.arange(0.78, 0.95, 0.01):
            for itt in [0, 24, 26, 28, 30, 32, 34, 36]:
                m = (oof[name] >= pt) & ((oof.itt_f >= itt) if itt else True)
                n, hit, pw = rule_eval(oof, m)
                if n >= 300 and pw >= 3:
                    cands.append((name, round(pt, 2), itt, n, hit, pw))
    C = pd.DataFrame(cands, columns=["model", "p", "itt", "n", "hit", "per_wk"])
    say(C.sort_values("hit", ascending=False).head(15).to_string(index=False))
    rules = [("lr", 0.90, 0), ("lr", 0.85, 0), ("gb", 0.90, 0), ("gb", 0.85, 0), ("lr", 0.80, 0)]
    best = C[C.hit >= 0.90].sort_values("per_wk", ascending=False).head(3)
    rules += [(r.model, r.p, r.itt) for r in best.itertuples()]
    best2 = C[C.hit >= 0.88].sort_values("per_wk", ascending=False).head(2)
    rules += [(r.model, r.p, r.itt) for r in best2.itertuples()]
    say("\n## Rules read blind: hit% (n, QBs/week)")
    say("  rule                       train-oof            " + "  ".join(f"{s:>22}" for s in BLIND) + "   all blind")
    seen = set()
    for name, pt, itt in rules:
        if (name, pt, itt) in seen:
            continue
        seen.add((name, pt, itt))
        m_tr = (oof[name] >= pt) & ((oof.itt_f >= itt) if itt else True)
        n0, h0, w0 = rule_eval(oof, m_tr)
        cells = []
        for s in BLIND:
            g = te[te.season == s]
            n, h, w = rule_eval(g, (g[name] >= pt) & ((g.itt_f >= itt) if itt else True))
            cells.append(f"{h:6.1%} ({n:4d}, {w:4.1f}/wk)" if n else f"{'-':>22}")
        n, h, w = rule_eval(te, (te[name] >= pt) & ((te.itt_f >= itt) if itt else True))
        say(f"  {name} >= {pt:.2f}" + (f" & ITT >= {itt}" if itt else "") + f"{'':<10}"[:max(0, 14 - (len(str(itt)) + 9 if itt else 0))]
            + f"  {h0:6.1%} ({n0:5d},{w0:4.1f}/wk)  " + "  ".join(cells) + f"   {h:.1%} ({n})")

    # the same ladder on the book alone and on implied team total alone (market info only)
    say("\n## Market info alone (implied team total from ESPN spread+total), blind")
    for itt in (30, 33, 36, 40):
        cells = []
        for s in BLIND:
            g = te[(te.season == s) & (te.has_line == 1)]
            n, h, w = rule_eval(g, g.itt_f >= itt)
            cells.append(f"{h:6.1%} ({n:4d}, {w:4.1f}/wk)")
        say(f"  ITT >= {itt}:  " + "  ".join(cells))

    # shuffle test: permute training labels, refit, read the same 90+ band blind
    say("\n## Shuffle test (labels permuted in training, 20 runs), blind")
    rng = np.random.default_rng(7)
    aucs, hits, ns = [], [], []
    for i in range(20):
        yp = rng.permutation(tr.y.values)
        m = make_lr().fit(tr[FEATS], yp)
        p = m.predict_proba(te[FEATS])[:, 1]
        aucs.append(roc_auc_score(te.y, p))
        top = p >= np.quantile(p, 1 - (te.lr >= 0.90).mean())  # same share of picks as the real 90+ band
        hits.append(te.y.values[top].mean()); ns.append(top.sum())
    real_top = te.lr >= 0.90
    say(f"  real LR: blind AUC {roc_auc_score(te.y, te.lr):.3f}; 90+ band hits {te.y[real_top].mean():.1%} of {real_top.sum()}")
    say(f"  shuffled: blind AUC mean {np.mean(aucs):.3f} (max {np.max(aucs):.3f}); same-size top slice hits "
        f"{np.mean(hits):.1%} (max {np.max(hits):.1%}) vs blind base {te.y.mean():.1%}")

    # 2026 book side-check (BettingPros only has NCAAF pass-TD props from 2026)
    say("\n## 2026 book side-check (BettingPros market 441 consensus, Poisson no-vig 1+), weeks with props only")
    B = book_2026(te[te.season == 2026])
    B = B[B.book.notna()]
    say(f"  matched {len(B)} starter rows to a book line; base {B.y.mean():.1%}; book-only Brier {brier_score_loss(B.y, B.book):.4f}  model Brier {brier_score_loss(B.y, B.lr):.4f}")
    for lo in (0.80, 0.85, 0.90):
        s = B[B.book >= lo]; say(f"  book {lo:.0%}+: {s.y.mean():.1%} of {len(s)}")
    for mp, bk in ((0.80, 0.85), (0.85, 0.85), (0.90, 0.85), (0.85, 0.80), (0.90, 0.90)):
        s = B[(B.lr >= mp) & (B.book >= bk)]
        say(f"  model {mp:.0%}+ AND book {bk:.0%}+: {s.y.mean():.1%} of {len(s)} ({s.groupby('week').size().mean():.1f}/wk)" if len(s) else f"  model {mp:.0%}+ AND book {bk:.0%}+: none")

    pickle.dump(dict(lr=lr, gb=gb, feats=FEATS), open(os.path.join(D, "model.pkl"), "wb"))
    te.to_parquet(os.path.join(D, "preds.parquet"))
    open(os.path.join(D, "results.txt"), "w").write("\n".join(OUT) + "\n")


if __name__ == "__main__":
    main()
