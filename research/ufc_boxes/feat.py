"""Pre-fight features for every UFC bout 2019-2026, from UFC Stats only (no odds yet).
Everything is computed from fights BEFORE the bout date. One row per bout, from the
red corner's side: A = red, B = blue; target a_won."""
import numpy as np, pandas as pd
B = "/private/tmp/claude-501/-Users-joe-Desktop-the-arena/3f4a5d15-c5a9-4028-a759-343c1831a343/scratchpad/ufc2/"
F = pd.read_csv(B + "fights.csv")
FT = pd.read_csv(B + "fighters.csv").set_index("fighter_url")
H = pd.read_csv(B + "history.csv")
F = F[F.winner.isin(["red", "blue"])].copy()
F["date"] = pd.to_datetime(F.event_date)
H["date"] = pd.to_datetime(H.date)
H = H.sort_values("date")
def mins(row, side):
    t = str(row["time"]).split(":"); r = int(row["round"]) if row["round"] == row["round"] else 1
    try: return (r - 1) * 5 + int(t[0]) + int(t[1]) / 60
    except Exception: return np.nan
def ctrl(s):
    try: a, b = str(s).split(":"); return int(a) * 60 + int(b)
    except Exception: return np.nan
# per-fighter per-fight stat lines from fights.csv (2019+)
lines = []
for _, r in F.iterrows():
    m = mins(r, None)
    for me, ot in (("red", "blue"), ("blue", "red")):
        lines.append(dict(url=r[me + "_url"], date=r["date"], mins=m,
                          sig=r[me + "_sig_landed"], sig_att=r[me + "_sig_att"], sig_abs=r[ot + "_sig_landed"],
                          td=r[me + "_td_landed"], td_att=r[me + "_td_att"], td_against=r[ot + "_td_landed"], td_against_att=r[ot + "_td_att"],
                          kd=r[me + "_kd"], kd_abs=r[ot + "_kd"], ctrl=ctrl(r[me + "_ctrl"]), ctrl_abs=ctrl(r[ot + "_ctrl"]), sub=r[me + "_sub_att"]))
L = pd.DataFrame(lines).sort_values("date")
for c in ("sig", "sig_att", "sig_abs", "td", "td_att", "td_against", "td_against_att", "kd", "kd_abs", "ctrl", "ctrl_abs", "sub"):
    L[c] = pd.to_numeric(L[c], errors="coerce")
Lg = {u: g for u, g in L.groupby("url")}
Hg = {u: g for u, g in H.groupby("fighter_url")}
def form(url, d):
    h = Hg.get(url)
    out = dict(n=0, wins=0, losses=0, streak=0, ko_wins=0, sub_wins=0, dec_wins=0, been_kod=0, last_kod=0, last_loss=0, layoff=np.nan)
    if h is None: return out
    p = h[h.date < d]
    p = p[p.result.isin(["W", "L", "D"])]
    if p.empty: return out
    out["n"] = len(p); out["wins"] = int((p.result == "W").sum()); out["losses"] = int((p.result == "L").sum())
    s = 0
    for res in p.result.values[::-1]:
        if res == "W" and s >= 0: s += 1
        elif res == "L" and s <= 0: s -= 1
        else: break
    out["streak"] = s
    w = p[p.result == "W"]; l = p[p.result == "L"]
    out["ko_wins"] = int(w.method.astype(str).str.contains("KO").sum()); out["sub_wins"] = int(w.method.astype(str).str.contains("SUB").sum())
    out["dec_wins"] = int(w.method.astype(str).str.contains("DEC").sum())
    out["been_kod"] = int(l.method.astype(str).str.contains("KO").sum())
    last = p.iloc[-1]; out["last_loss"] = int(last.result == "L"); out["last_kod"] = int(last.result == "L" and "KO" in str(last.method))
    out["layoff"] = (d - last.date).days
    return out
def rates(url, d):
    g = Lg.get(url)
    keys = ["slpm", "sapm", "acc", "tdpm", "tdacc", "tddef", "kdpm", "kdabs", "ctrl_share", "subpm"]
    if g is None: return {k: np.nan for k in keys} | {"ufc_mins": 0}
    p = g[g.date < d]
    if p.empty or p.mins.sum() < 1: return {k: np.nan for k in keys} | {"ufc_mins": 0}
    m = p.mins.sum()
    return dict(slpm=p.sig.sum() / m, sapm=p.sig_abs.sum() / m, acc=p.sig.sum() / max(p.sig_att.sum(), 1),
                tdpm=p.td.sum() / m * 15, tdacc=p.td.sum() / max(p.td_att.sum(), 1),
                tddef=1 - p.td_against.sum() / max(p.td_against_att.sum(), 1), kdpm=p.kd.sum() / m * 15, kdabs=p.kd_abs.sum() / m * 15,
                ctrl_share=p.ctrl.sum() / max(p.ctrl.sum() + p.ctrl_abs.sum(), 1), subpm=p["sub"].sum() / m * 15, ufc_mins=m)
rows = []
for _, r in F.iterrows():
    d = r["date"]; row = dict(date=d, yr=d.year, wc=r.weight_class, title=r.title_bout, rounds=r.scheduled_rounds, method=r.method,
                              a=r.red_name, b=r.blue_name, a_url=r.red_url, b_url=r.blue_url, a_won=int(r.winner == "red"))
    for side, u in (("a", r.red_url), ("b", r.blue_url)):
        ft = FT.loc[u] if u in FT.index else None
        dob = pd.to_datetime(ft.dob) if ft is not None and isinstance(ft.dob, str) else pd.NaT
        row[side + "_age"] = (d - dob).days / 365.25 if pd.notna(dob) else np.nan
        row[side + "_height"] = pd.to_numeric(ft.height_in, errors="coerce") if ft is not None else np.nan
        row[side + "_reach"] = pd.to_numeric(ft.reach_in, errors="coerce") if ft is not None else np.nan
        row[side + "_stance"] = ft.stance if ft is not None else ""
        for k, v in form(u, d).items(): row[side + "_" + k] = v
        for k, v in rates(u, d).items(): row[side + "_" + k] = v
    rows.append(row)
X = pd.DataFrame(rows)
X.to_pickle(B + "U.pkl")
print(len(X), "bouts", X.yr.min(), X.yr.max())
