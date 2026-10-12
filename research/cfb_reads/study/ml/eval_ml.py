"""Blind tables for the CFB moneyline read.  python3 ml/eval_ml.py -> ml/results.txt, ml/tiers.csv, ml/calibration.csv, ml/shuffle.csv"""
import os, sys
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss
M = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, M)
import model_ml as mm

T = pd.read_parquet(os.path.join(M, "preds.parquet"))
T["conf_m"] = np.maximum(T.p, 1 - T.p); T["pick_h"] = (T.p >= 0.5).astype(int); T["ok"] = (T.pick_h == T.y)
T["bconf"] = np.maximum(T.book, 1 - T.book); T["bfav_h"] = (T.book >= 0.5).astype(int); T["bok"] = (T.bfav_h == T.y)
T["agree"] = T.book.notna() & (T.pick_h == T.bfav_h)
T["bpick"] = np.where(T.pick_h == 1, T.book, 1 - T.book)       # book's chance for the model's pick
WEEKS = T.groupby("season").week.nunique()
out = []

def row(name, mask):
    r = {"tier": name}
    for s, d in T[mask].groupby("season"):
        r[f"{s}_hit"] = round(100 * d.ok.mean(), 1); r[f"{s}_n"] = len(d); r[f"{s}_wk"] = round(len(d) / WEEKS[s], 1)
        b = d[d.book.notna()]; r[f"{s}_bookp"] = round(100 * b.bpick.mean(), 1) if len(b) else np.nan
    d = T[mask]; r["all_hit"] = round(100 * d.ok.mean(), 1); r["all_n"] = len(d)
    r["min_season"] = min(r.get(f"{s}_hit", np.nan) for s in WEEKS.index)
    pw = d.groupby(["season", "week"]).size().reindex(pd.MultiIndex.from_tuples([(s, w) for s in WEEKS.index for w in sorted(T[T.season == s].week.unique())]), fill_value=0)
    r["wk_min"], r["wk_med"], r["wk_max"] = int(pw.min()), float(pw.median()), int(pw.max())
    out.append(r)

def bookrow(name, mask):
    """Pick the ESPN moneyline favorite on these games."""
    r = {"tier": name}
    for s, d in T[mask & T.book.notna()].groupby("season"):
        r[f"{s}_hit"] = round(100 * d.bok.mean(), 1); r[f"{s}_n"] = len(d); r[f"{s}_wk"] = round(len(d) / WEEKS[s], 1)
        r[f"{s}_bookp"] = round(100 * d.bconf.mean(), 1)
    d = T[mask & T.book.notna()]; r["all_hit"] = round(100 * d.bok.mean(), 1); r["all_n"] = len(d)
    r["min_season"] = min(r.get(f"{s}_hit", np.nan) for s in WEEKS.index)
    out.append(r)

allg = T.p.notna()
row("model all games", allg)
for t in (0.70, 0.75, 0.80, 0.85, 0.90):
    row(f"model {int(t*100)}+", T.conf_m >= t)
for lo, hi in ((0.70, 0.75), (0.75, 0.80), (0.80, 0.85)):
    row(f"model {int(lo*100)}-{int(hi*100)-1}", (T.conf_m >= lo) & (T.conf_m < hi))
bookrow("BOOK favorite, all games", allg)
for t in (0.70, 0.75, 0.80):
    bookrow(f"BOOK favorite on model {int(t*100)}+ games", T.conf_m >= t)
    bookrow(f"BOOK favorite {int(t*100)}%+ (book alone)", T.bconf >= t)
row("model 60+ AND book 65+ same team", (T.conf_m >= .60) & (T.bconf >= .65) & T.agree)
row("model 70+ AND book 65+ same team", (T.conf_m >= .70) & (T.bconf >= .65) & T.agree)
row("model 75+ AND book agrees", (T.conf_m >= .75) & T.agree)
row("model 75+ AND book under 80 (price check)", (T.conf_m >= .75) & T.agree & (T.bconf < .80))
row("model 60-74 AND book 65-79 same team", (T.conf_m >= .60) & (T.conf_m < .75) & (T.bconf >= .65) & (T.bconf < .80) & T.agree)
row("model and book DISAGREE, model 60+", (T.conf_m >= .60) & T.book.notna() & ~T.agree)
R = pd.DataFrame(out); R.to_csv(os.path.join(M, "tiers.csv"), index=False)

# calibration
T["bin"] = pd.cut(T.conf_m, [.5, .6, .7, .75, .8, .85, .9, .95, 1.0001], right=False)
C = T.groupby("bin", observed=True).agg(n=("ok", "size"), model=("conf_m", "mean"), hit=("ok", "mean"), book=("bpick", "mean")).round(3)
C.to_csv(os.path.join(M, "calibration.csv"))
LO = pd.read_parquet(os.path.join(M, "loso.parquet")); LO["c"] = np.maximum(LO.p, 1 - LO.p); LO["ok"] = (LO.p >= .5) == LO.y

# shuffle test: refit on 2016-21 with labels shuffled, read the same blind seasons
G = pd.read_parquet(os.path.join(M, "games.parquet")); TR = G[(G.stype == 2) & (G.season <= 2021)]
rng = np.random.default_rng(7); sh = []
for i in range(200):
    m = mm.fit(TR, rng.permutation(TR.y.values)); p = m.predict_proba(T[mm.FEATS].fillna(0))[:, 1]
    c = np.maximum(p, 1 - p); ok = (p >= .5) == T.y.values; top = np.argsort(-c)[: int((T.conf_m >= .75).sum())]
    sh.append(dict(auc=roc_auc_score(T.y, p), n75=int((c >= .75).sum()), hit75=ok[c >= .75].mean() if (c >= .75).any() else np.nan,
                   hit_top_same_n=ok[top].mean(), hit_all=ok.mean()))
SH = pd.DataFrame(sh); SH.to_csv(os.path.join(M, "shuffle.csv"), index=False)

with open(os.path.join(M, "results.txt"), "w") as f:
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 60)
    f.write("blind AUC / Brier / hit (all games) by season\n")
    for s, d in T.groupby("season"):
        b = d[d.book.notna()]
        f.write(f"{s}: n={len(d)} AUC {roc_auc_score(d.y, d.p):.3f} Brier {brier_score_loss(d.y, d.p):.4f} hit {d.ok.mean():.3f} | book AUC {roc_auc_score(b.y, b.book):.3f} Brier {brier_score_loss(b.y, b.book):.4f} fav hit {b.bok.mean():.3f}\n")
    f.write("\nweeks counted per season: " + str(WEEKS.to_dict()) + "\n\nTIERS (hit %, n, per week, book's avg chance for the pick)\n")
    f.write(R.to_string(index=False) + "\n\nCALIBRATION (blind 2022-26)\n" + C.to_string() + "\n")
    f.write("\nLOSO 2016-21: " + str({t: (round(LO[LO.c >= t].ok.mean(), 3), int((LO.c >= t).sum())) for t in (.7, .75, .8)}) + "\n")
    f.write("\nSHUFFLE (200 label shuffles): " + SH.describe().round(3).to_string() + "\n")
    f.write(f"real: AUC {roc_auc_score(T.y, T.p):.3f} hit75 {T[T.conf_m >= .75].ok.mean():.3f} n75 {(T.conf_m >= .75).sum()}; shuffles with hit_top_same_n >= real: {(SH.hit_top_same_n >= T[T.conf_m >= .75].ok.mean()).sum()}/200\n")
print(open(os.path.join(M, "results.txt")).read())
