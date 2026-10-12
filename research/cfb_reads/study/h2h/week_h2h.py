"""Score a week's FBS vs FBS games for QB head-to-head passing yards.

  python3 h2h/week_h2h.py 2026 6

Refreshes the season's finished games, parses only summaries not yet in h2h/tg.parquet,
takes each team's QB from its last FBS-vs-FBS game (as week.py does), reads ESPN's line,
and scores with the 2016-2021 logistic model (h2h/model.pkl, from study.py).

Flags:
  TOP10  model winner chance >= the 2016-21 top-10% cutoff (the rule in RESULTS_H2H.md)
  TOP20  model winner chance >= the 2016-21 top-20% cutoff (wider tier)
"""
import glob, json, os, pickle, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd

H = os.path.dirname(os.path.abspath(__file__))
D = os.path.dirname(H)
sys.path.insert(0, D); sys.path.insert(0, H)
import fetch, week  # noqa: E402
import build_h2h as B  # noqa: E402


def refresh_tg(season):
    ids = fetch.weeks(season, refresh=True)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(fetch.summary, ids)); list(ex.map(fetch.odds, ids))
    tg = pd.read_parquet(os.path.join(H, "tg.parquet"))
    sf = os.path.join(H, "seen.json")
    seen = set(json.load(open(sf))) if os.path.exists(sf) else set()
    seen |= set(tg.eid.astype(str))
    files = [f for f in glob.glob(os.path.join(D, "cache", "*.json")) if os.path.basename(f)[:-5] not in seen]
    new = B.team_games(files=files)
    if len(new):
        tg = pd.concat([tg, new.drop(columns=["upcoming"])], ignore_index=True)
        tg = tg.drop_duplicates(["eid", "team"]).sort_values(["date", "eid", "team"]).reset_index(drop=True)
        tg.to_parquet(os.path.join(H, "tg.parquet"))
    json.dump(sorted(seen | {os.path.basename(f)[:-5] for f in files}), open(sf, "w"))
    print(f"parsed {len(files)} new summaries, {len(new)} new FBS team-games", file=sys.stderr)
    return tg


def main(season, wk):
    tg = refresh_tg(season)
    U = week.upcoming(season, wk)
    if U.empty:
        print("no upcoming FBS vs FBS games"); return
    U["date"] = pd.to_datetime(U.date, utc=True)
    last = tg.sort_values("date").groupby("team").tail(1).set_index("team")
    U["qb"] = U.team.map(last.qb); U["qb_name"] = U.team.map(last.qb_name)
    import sys as _s; _s.path.insert(0, __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))); import boardqb as _bq
    _B = _bq.board()
    for _i, _r in U.iterrows():
        _h = _B.get((str(_r.eid), _r.team_abbr))
        if _h and _h[0] and str(_h[0]) != str(_r.qb):
            U.at[_i, "qb"], U.at[_i, "qb_name"] = type(_r.qb)(_h[0]) if _r.qb == _r.qb else _h[0], _h[1]
    U["is_home"] = U.ha.eq("H") | (U.ha.eq("N") & ~U.duplicated("eid"))
    # week.upcoming lists home first; for neutral sites the first listed is ESPN's home side
    U = U[U.qb.notna()]
    U = U[U.groupby("eid").eid.transform("size") == 2]
    for c in ["q_att", "q_yds", "q_cmp", "t_patt", "t_pyds", "t_net", "t_ratt", "t_ryds", "pts", "opp_pts", "sackyds"]:
        U[c] = 0
    U["upcoming"] = True
    tg = tg.copy(); tg["upcoming"] = False
    X = B.features(pd.concat([tg, U], ignore_index=True).sort_values(["date", "eid", "team"]).reset_index(drop=True))
    G = B.pair(X[X.upcoming.astype(bool)])
    G["home_site"] = 1 - G.neutral
    M = pickle.load(open(os.path.join(H, "model.pkl"), "rb"))
    p = M["lr"].predict_proba(M["sc"].transform(G[M["feats"]].fillna(0).values))[:, 1]
    G["p_home"] = p
    G["pick"] = np.where(p > 0.5, G.h_qb + " (" + G.h_team + ")", G.a_qb + " (" + G.a_team + ")")
    G["chance"] = np.maximum(p, 1 - p)
    G["tier"] = np.where(G.chance - 0.5 >= M["cuts"][0.10], "TOP10", np.where(G.chance - 0.5 >= M["cuts"][0.20], "TOP20", ""))
    G.loc[G.h_spread.isna(), "tier"] = "no line"  # the model was fit on games with a line
    G = G.sort_values("chance", ascending=False)
    out = G[["date", "h_qb", "h_team", "a_qb", "a_team", "neutral", "h_spread", "total", "g_q_ypg", "p_home", "pick", "chance", "tier"]].copy()
    out["date"] = out.date.dt.tz_convert("US/Eastern").dt.strftime("%m/%d %H:%M")
    out["chance"] = (out.chance * 100).round(1); out["p_home"] = (out.p_home * 100).round(1); out["g_q_ypg"] = out.g_q_ypg.round(0)
    out.to_csv(os.path.join(H, f"week_{season}_{wk}.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(f"{season} week {wk}: {len(out)} FBS-vs-FBS games scored. TOP10 cutoff {50 + M['cuts'][0.10]*100:.1f}%, "
          f"TOP20 cutoff {50 + M['cuts'][0.20]*100:.1f}% (winner chance). h_spread is the home line.\n")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
