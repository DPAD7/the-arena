"""2026-only side check: BettingPros NCAAF passing-yards lines (market 440) as an H2H read.
BettingPros has no college H2H market, and market 440 exists only for 2026."""
import json, os, sys, pickle
import numpy as np, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.dirname(H); sys.path.insert(0, D)
import fetch
os.makedirs(os.path.join(H, "bp440"), exist_ok=True)
rows = []
for wk in range(1, 7):
    fn = os.path.join(H, "bp440", f"2026_{wk}.json")
    if not os.path.exists(fn):
        props, page = [], 1
        while True:
            d = fetch.get(f"https://api.bettingpros.com/v3/props?sport=NCAAF&market_id=440&season=2026&week={wk}&limit=50&page={page}", fetch.BPKEY)
            if not d: break
            props += d.get("props", [])
            if page >= (d.get("_pagination", {}).get("total_pages") or 0): break
            page += 1
        json.dump(props, open(fn, "w"))
    for p in json.load(open(fn)):
        ln = (p.get("over") or {}).get("consensus_line") or (p.get("over") or {}).get("line")
        if ln is None: continue
        rows.append(dict(wk=wk, ev=p["event_id"], last=p["participant"]["player"]["last_name"].lower(), line=float(ln)))
P = pd.DataFrame(rows).drop_duplicates(["ev", "last"])
G = pd.read_parquet(os.path.join(H, "scored.parquet")); G = G[G.season == 2026]
last = lambda n: n.replace(" Jr.", "").replace(" III", "").replace(" II", "").split()[-1].lower()
G["hl"], G["al"] = G.h_qb.map(last), G.a_qb.map(last)
M = pickle.load(open(os.path.join(H, "model.pkl"), "rb"))
out = []
for ev, grp in P.groupby("ev"):
    if len(grp) < 2: continue
    L = dict(zip(grp["last"], grp.line))
    m = G[G.hl.isin(L) & G.al.isin(L)]
    if len(m) != 1: continue
    r = m.iloc[0]
    out.append(dict(eid=r.eid, y=r.y, hline=L[r.hl], aline=L[r.al], p=r.p))
O = pd.DataFrame(out)
O = O[O.hline != O.aline]
O["bp_pick"] = np.where(O.hline > O.aline, 1, 0)
O["lr_pick"] = (O.p > 0.5).astype(int)
O["gap"] = (O.hline - O.aline).abs()
O["top10"] = (O.p - 0.5).abs() >= M["cuts"][0.10]
O["top20"] = (O.p - 0.5).abs() >= M["cuts"][0.20]
f = lambda m, c: f"{(O[m][c] == O[m].y).mean()*100:.1f}% ({m.sum()})"
allm = O.y >= 0
print("2026 games with both QBs' BettingPros pass-yds lines:", len(O))
print("higher pass-yds line wins:", f(allm, "bp_pick"))
for g in (25, 50, 75):
    print(f"line gap {g}+ yds:", f(O.gap >= g, "bp_pick"))
print("LR pick, same games:", f(allm, "lr_pick"))
print("LR TOP10 in these games:", f(O.top10, "lr_pick"), "| agrees with higher line:", int((O[O.top10].lr_pick == O[O.top10].bp_pick).sum()))
print("LR TOP20 in these games:", f(O.top20, "lr_pick"))
print("LR and line agree:", f(O.lr_pick == O.bp_pick, "lr_pick"), "| disagree, LR side:", f(O.lr_pick != O.bp_pick, "lr_pick"))
