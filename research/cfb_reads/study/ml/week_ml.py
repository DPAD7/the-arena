"""Score a week's FBS vs FBS games for the moneyline read.

  python3 ml/week_ml.py 2026 7          # games of that week not yet finished
  python3 ml/week_ml.py 2026 6 --all    # also list finished games of that week (scored as of kickoff)

Refreshes the season (fetch.py), takes each team's QB from its last FBS-vs-FBS game,
scores with the 2016-2021 model (no odds in the model), then reads ESPN's moneyline
(pre-game books only, never 'Live' feeds) as the book check.
Tiers: READ = model 75%+ ; BOOK AGREES = model 60+ and book 65+ on the same team.
"""
import json, os, pickle, sys
from concurrent.futures import ThreadPoolExecutor
import numpy as np, pandas as pd

M = os.path.dirname(os.path.abspath(__file__)); D = os.path.dirname(M)
sys.path[:0] = [D, M]
import fetch, build_ml, model_ml

def ml_odds(eid, comp):
    """Save the pre-game moneylines for an event (scoreboard first, ESPN core odds next)."""
    fn = os.path.join(M, "mlodds", f"up_{eid}.json"); keep = []
    o = fetch.get(fetch.ODDS.format(eid)) or {}
    for i in o.get("items", []):
        h, a = i.get("homeTeamOdds") or {}, i.get("awayTeamOdds") or {}
        keep.append(dict(p=(i.get("provider") or {}).get("name"), details=i.get("details"), hml=h.get("moneyLine"), aml=a.get("moneyLine")))
    if not any(k["hml"] for k in keep):
        for od in comp.get("odds") or []:
            ml = od.get("moneyline") or {}
            hm = (od.get("homeTeamOdds") or {}).get("moneyLine") or ((ml.get("home") or {}).get("close") or {}).get("odds")
            am = (od.get("awayTeamOdds") or {}).get("moneyLine") or ((ml.get("away") or {}).get("close") or {}).get("odds")
            keep.append(dict(p=(od.get("provider") or {}).get("name"), details=od.get("details"), hml=hm, aml=am))
    json.dump(keep, open(fn, "w"))
    return model_ml.book(f"up_{eid}")

def main(season, week, show_all=False):
    ids = fetch.weeks(season, refresh=True)
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(fetch.summary, ids))
    d = fetch.get(f"{fetch.SB}?groups=80&seasontype=2&dates={season}&week={week}&limit=300") or {}
    fbs = set(json.load(open(os.path.join(D, "fbs", f"{season}.json"))))
    g = build_ml.team_games(); g = g[g.season >= season - 3]
    last = g.sort_values("date").groupby("team").tail(1).set_index("team")
    import sys as _s; _s.path.insert(0, D); import boardqb as _bq
    BOARD = _bq.board()
    rows, info = [], {}
    for e in d.get("events", []):
        c = e["competitions"][0]; cs = c["competitors"]
        if len(cs) != 2 or not all(x["team"]["id"] in fbs for x in cs): continue
        done = c["status"]["type"].get("completed")
        if done and not show_all: continue
        info[e["id"]] = dict(date=c["date"], done=done, comp=c,
                             score={x["team"]["id"]: x.get("score") for x in cs})
        home = next(x for x in cs if x["homeAway"] == "home")
        for t in cs:
            o = [x for x in cs if x is not t][0]; tid = t["team"]["id"]
            if tid not in last.index: continue
            if done:  # score a finished game as of kickoff: QB = his last game before it
                prior = g[(g.team == tid) & (g.date < pd.Timestamp(c["date"]))].sort_values("date")
                if prior.empty: continue
                q = prior.iloc[-1]
            else:
                q = last.loc[tid]
                # the board's own card QB wins over his last game (Iowa: Brown hurt, Hecklinski on the card)
                bq = BOARD.get((str(e["id"]), t["team"]["abbreviation"]))
                if bq and str(bq[0]) != str(q.qb):
                    q = q.copy(); q["qb"], q["qb_name"] = str(bq[0]), bq[1]
            rows.append(dict(eid=e["id"], date=c["date"], season=season, stype=2, week=week, team=tid, team_abbr=t["team"]["abbreviation"],
                             opp=o["team"]["id"], opp_abbr=o["team"]["abbreviation"], is_home=t is home, neutral=bool(c.get("neutralSite")),
                             conf=bool(c.get("conferenceCompetition")), rank=(t.get("curatedRank") or {}).get("current", 99) or 99,
                             qb=q.qb, qb_name=q.qb_name, upcoming=True))
    if not rows:
        print("no FBS vs FBS games to score"); return
    U = pd.DataFrame(rows); U["date"] = pd.to_datetime(U.date, utc=True)
    hist = g[~g.eid.isin(U.eid)]
    X = build_ml.features(pd.concat([hist, U], ignore_index=True))
    G = build_ml.pair(X[X.upcoming.astype(bool)])
    mdl = pickle.load(open(os.path.join(M, "model.pkl"), "rb"))
    G["p"] = mdl["model"].predict_proba(G[mdl["feats"]].fillna(0))[:, 1]
    with ThreadPoolExecutor(6) as ex:
        G["book"] = list(ex.map(lambda e: ml_odds(e, info[e]["comp"]), G.eid))
    G["pick"] = np.where(G.p >= .5, G.h_team, G.a_team); G["model%"] = (100 * np.maximum(G.p, 1 - G.p)).round(1)
    G["book%"] = (100 * np.where(G.p >= .5, G.book, 1 - G.book)).round(1)
    G["READ"] = np.where(G["model%"] >= 75, "READ", "")
    G["AGREE"] = np.where((G["model%"] >= 60) & (G["book%"] >= 65), "BOOK AGREES", "")
    et = G.date.dt.tz_convert("America/New_York")
    G["kick_ET"] = [d.strftime("%a %b %-d ") + ("TBD" if (d.hour, d.minute) == (0, 0) else d.strftime("%-I:%M %p")) for d in et]
    G["game"] = np.where(G.neutral.astype(bool), G.a_team + " vs " + G.h_team + " (N)", G.a_team + " at " + G.h_team)
    G["result"] = [("" if not info[e]["done"] else f"{G.a_team[i]} {info[e]['score'][G.a_id[i]]}-{info[e]['score'][G.h_id[i]]} {G.h_team[i]}") for i, e in zip(G.index, G.eid)]
    G["pick_won"] = ["" if not info[e]["done"] else ("W" if (float(info[e]["score"][G.h_id[i]]) > float(info[e]["score"][G.a_id[i]])) == (G.p[i] >= .5) else "L") for i, e in zip(G.index, G.eid)]
    G["qbs"] = G.a_qb + " / " + G.h_qb
    G = G.sort_values(["date", "model%"], ascending=[True, False])
    cols = ["kick_ET", "game", "pick", "model%", "book%", "READ", "AGREE", "qbs"] + (["result", "pick_won"] if show_all else [])
    G[cols + ["eid"]].to_csv(os.path.join(M, f"week_{season}_{week}.csv"), index=False)
    pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
    print(f"{season} week {week}: {len(G)} FBS vs FBS games; READ (model 75%+): {(G.READ != '').sum()}; BOOK AGREES: {(G.AGREE != '').sum()}; no moneyline: {G.book.isna().sum()}\n")
    print(G[cols].to_string(index=False))

if __name__ == "__main__":
    main(int(sys.argv[1]), int(sys.argv[2]), "--all" in sys.argv)
