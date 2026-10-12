"""CFB QB H2H passing yards: baselines, LR, edge score, single/pair rules, shuffle test.

  python3 h2h/study.py   -> h2h/results.txt, h2h/rules.csv, h2h/model.pkl

Train / lock everything on 2016-2021. Read 2022, 2023, 2024, 2025, 2026 blind.
"""
import itertools, os, pickle
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

H = os.path.dirname(os.path.abspath(__file__))
OUT = open(os.path.join(H, "results.txt"), "w")


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s); OUT.write(s + "\n")


G = pd.read_parquet(os.path.join(H, "games.parquet"))
G = G[G.ok & ~G.upcoming.astype(bool)].copy()
G["wk"] = G.stype.astype(str) + "_" + G.week.astype(str)
G["home_site"] = 1 - G.neutral
TR = G.season <= 2021
BL = [2022, 2023, 2024, 2025, 2026]
WEEKS = G.groupby("season").wk.nunique()

STATS = ["q_ypg", "q_apg", "q_ypa", "q_cmp", "q_ypg3", "t_prate", "t_ppg", "t_plays", "t_rypg", "t_ypc",
         "d_pypg", "d_ypa", "d_qbypg", "d_rypg", "d_papg", "d_ppg", "proj", "proj2", "itt", "spread"]
GF = ["g_" + s for s in STATS]
y = G.y.values


def hit(pick, mask=None):
    """pick: +1 home, -1 away, 0 no pick. Returns (n, hit rate)."""
    m = pick != 0 if mask is None else (pick != 0) & mask
    n = int(m.sum())
    if n == 0:
        return 0, np.nan
    return n, float(((pick[m] == 1) == (y[m] == 1)).mean())


def row(name, pick):
    cells = []
    n, h = hit(pick, TR.values)
    cells.append(f"{h*100:5.1f}% ({n})")
    for s in BL:
        n, h = hit(pick, (G.season == s).values)
        cells.append(f"{h*100:5.1f}% ({n}, {n/WEEKS[s]:.1f}/wk)")
    nb, hb = hit(pick, (G.season >= 2022).values)
    cells.append(f"{hb*100:5.1f}% ({nb})")
    return f"| {name} | " + " | ".join(cells) + " |"


HDR = "| rule | 2016-21 | 2022 | 2023 | 2024 | 2025 | 2026 | all blind |\n|---|---|---|---|---|---|---|---|"

say("# CFB QB H2H passing yards: results\n")
say("Games:", len(G), "| train 2016-21:", int(TR.sum()), "| weeks per season:", dict(WEEKS))
say("Home QB more yards:", G.groupby("season").y.mean().round(3).to_dict(), "\n")

# ---------------- baselines
say("## Baselines\n"); say(HDR)
fav = np.sign(G.g_spread.fillna(0).values)
say(row("spread favorite's QB", fav))
say(row("higher QB yds/game", np.sign(G.g_q_ypg.values)))
say(row("higher implied team total", np.sign(G.g_itt.fillna(0).values)))
say(row("higher matchup projection", np.sign(G.g_proj.values)))
say(row("home QB (all games)", np.ones(len(G))))

# ---------------- logistic model
say("\n## Logistic model on the gaps\n")
LRF = GF + ["home_site", "early", "conf"]
Xa = G[LRF].fillna(0).values
# early-season and conference flags interact with nothing here; they only shift the home intercept
sc = StandardScaler().fit(Xa[TR.values])
lr = LogisticRegression(C=0.5, max_iter=2000).fit(sc.transform(Xa[TR.values]), y[TR.values])
p = lr.predict_proba(sc.transform(Xa))[:, 1]
G["p"] = p
conf = np.abs(p - 0.5)
say("Weights (standardized):", ", ".join(f"{f} {w:+.2f}" for f, w in sorted(zip(LRF, lr.coef_[0]), key=lambda t: -abs(t[1]))))
say("\n" + HDR)
lrpick = np.where(p > 0.5, 1, -1)
say(row("LR all games", lrpick))
cuts = {}
for q in (0.30, 0.20, 0.10):
    c = np.quantile(conf[TR.values], 1 - q)
    cuts[q] = c
    say(row(f"LR top {int(q*100)}% (p>={0.5+c:.3f} either side, cut locked on train)", np.where(conf >= c, lrpick, 0)))
for pc in (0.70, 0.75, 0.80):
    say(row(f"LR winner chance >= {pc:.0%}", np.where(conf >= pc - 0.5, lrpick, 0)))
pickle.dump(dict(lr=lr, sc=sc, feats=LRF, cuts=cuts), open(os.path.join(H, "model.pkl"), "wb"))

# ---------------- edge score
say("\n## Edge score (no price; spread/ITT left out)\n")
EST = [s for s in STATS if s not in ("spread", "itt")]
trd = G[TR]
edge = {}
for s in EST:
    g = trd["g_" + s].values
    d = np.sign(np.corrcoef(g, trd.y)[0, 1])
    best = None
    for q in (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6):
        c = np.quantile(np.abs(g), q)
        m = np.abs(g) > c
        h = ((np.sign(g[m]) * d > 0) == (trd.y.values[m] == 1)).mean()
        z = (h - 0.5) * np.sqrt(m.sum())
        if best is None or z > best[0]:
            best = (z, c, h, m.mean())
    edge[s] = (d, best[1])
    say(f"- {s}: direction {'+' if d > 0 else '-'}, cutoff |gap| > {best[1]:.3f}, train hit {best[2]*100:.1f}% on {best[3]*100:.0f}% of games")
margin = np.zeros(len(G))
for s, (d, c) in edge.items():
    g = G["g_" + s].values
    margin += np.where(g * d > c, 1, 0) - np.where(g * d < -c, 1, 0)
G["margin"] = margin
say(f"\nEdge stats used: {len(edge)}. Margin = home edges - away edges.\n")
say(HDR)
for m in (1, 3, 4, 5, 6, 7, 8, 9, 10):
    say(row(f"margin {m}+", np.where(np.abs(margin) >= m, np.sign(margin), 0)))
pickle.dump(edge, open(os.path.join(H, "edge.pkl"), "wb"))

# ---------------- single and pair rules
say("\n## Single and pair rules\n")
RF = GF  # all gaps, including price
sig = {}
for s in RF:
    d = np.sign(np.corrcoef(trd[s].fillna(0), trd.y)[0, 1])
    g = G[s].fillna(0).values * d
    for q in (0.5, 0.6, 0.7, 0.8, 0.9):
        t = np.quantile(np.abs(trd[s].fillna(0).values), q)
        sig[(s, q)] = np.where((g >= t) & (g > 0), 1, np.where((g <= -t) & (g < 0), -1, 0)).astype(np.int8)
keys = list(sig)
rules = [((k,), sig[k]) for k in keys]
for a, b in itertools.combinations(keys, 2):
    if a[0] == b[0]:
        continue
    pa, pb = sig[a], sig[b]
    rules.append(((a, b), np.where(pa == pb, pa, 0).astype(np.int8)))
say(f"Candidate rules: {len(rules)} ({len(keys)} single, {len(rules)-len(keys)} pairs; thresholds at the 50/60/70/80/90th percentile of |gap| on 2016-21)")

trm = TR.values
sm = {s: (G.season == s).values for s in BL}
yy = (y == 1)


def evaluate(yv, need=0.68):
    """Rules at 68%+ on train (n>=40) that also hold 68%+ blind in each of 2022-2025."""
    ytrue = (yv == 1)
    out = []
    for k, pk in rules:
        m = (pk != 0) & trm
        n = m.sum()
        if n < 40:
            continue
        h = ((pk[m] == 1) == yy[m]).mean()   # train labels are never shuffled
        if h < need:
            continue
        ok, cells = True, []
        for s in BL:
            mm = (pk != 0) & sm[s]
            nn = mm.sum()
            hh = ((pk[mm] == 1) == ytrue[mm]).mean() if nn else np.nan
            cells.append((nn, hh))
            if s <= 2025 and not (nn > 0 and hh >= need):
                ok = False
        out.append((k, n, h, cells, ok))
    return out


res = evaluate(y)
passed_train = len(res)
held = [r for r in res if r[4]]
say(f"Pass 68% on 2016-21 (n>=40): {passed_train}. Also 68%+ blind in each of 2022-2025: {len(held)}.")


def kname(k):
    return " & ".join(f"{s[0][2:]} top {int((1-s[1])*100)}%" for s in k)


rows = []
for k, n, h, cells, ok in res:
    r = dict(rule=kname(k), train_n=n, train_hit=round(h, 4), held=ok)
    for s, (nn, hh) in zip(BL, cells):
        r[f"n{s}"] = nn; r[f"h{s}"] = round(hh, 4) if nn else np.nan; r[f"pw{s}"] = round(nn / WEEKS[s], 2)
    bm = sum(c[0] for c in cells[:4]); bh = sum(c[0] * c[1] for c in cells[:4] if c[0]) / max(1, bm)
    r["blind22_25_n"] = bm; r["blind22_25_hit"] = round(bh, 4); r["min22_25"] = round(min(c[1] if c[0] else 0 for c in cells[:4]), 4)
    rows.append(r)
R = pd.DataFrame(rows).sort_values(["held", "min22_25"], ascending=False)
R.to_csv(os.path.join(H, "rules.csv"), index=False)

# shuffle test: permute blind labels within each season, 20 times
rng = np.random.default_rng(7)
cnt = []
for i in range(20):
    ys = y.copy()
    for s in BL:
        idx = np.where(sm[s])[0]
        ys[idx] = rng.permutation(ys[idx])
    cnt.append(sum(r[4] for r in evaluate(ys)))
say(f"Shuffle test (blind labels permuted within season, 20x): rules passing by luck mean {np.mean(cnt):.1f}, max {max(cnt)}, per run {cnt}")
say(f"Real labels: {len(held)} held.\n")
say("Held rules with the most volume (2022-25 games/week averaged):\n")
H2 = R[R.held].copy()
H2["pw"] = H2[[f"pw{s}" for s in BL[:4]]].mean(axis=1)
say(H2.sort_values("pw", ascending=False).head(25)[["rule", "train_n", "train_hit", "h2022", "h2023", "h2024", "h2025", "h2026", "n2026", "pw", "min22_25"]].to_string(index=False))
say("\nHeld rules at 70%+ in every blind season 2022-2026, sorted by volume:\n")
H3 = H2[(H2.min22_25 >= 0.70) & (H2.h2026 >= 0.70)]
say(H3.sort_values("pw", ascending=False).head(25)[["rule", "train_n", "train_hit", "h2022", "h2023", "h2024", "h2025", "h2026", "n2026", "pw"]].to_string(index=False))

G.to_parquet(os.path.join(H, "scored.parquet"))
OUT.close()
