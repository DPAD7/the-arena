"""Score a week's FBS vs FBS starting QBs for 1+ passing TD.

  python3 week.py 2026 7

Refreshes the season's finished games (fetch.py), rebuilds history (build.py),
takes each team's QB from its last FBS-vs-FBS game, reads the line from ESPN,
scores with the 2016-2021 model and marks the QBs that meet the rule.
"""
import json, os, pickle, sys
import numpy as np
import pandas as pd

import build, fetch
from model import prep

D = os.path.dirname(os.path.abspath(__file__))
RULE_MODEL, RULE_P, RULE_ITT = "lr", 0.90, 0   # set from RESULTS.md


def upcoming(season, week):
    st, wk = (3, None) if str(week).lower() in ("post", "bowl", "bowls") else (2, int(week))
    u = f"{fetch.SB}?groups=80&seasontype={st}&dates={season}&limit=300" + (f"&week={wk}" if wk else "")
    d = fetch.get(u) or {}
    fbs = set(json.load(open(os.path.join(D, "fbs", f"{season}.json"))))
    rows = []
    for e in d.get("events", []):
        c = e["competitions"][0]
        if c["status"]["type"].get("completed"):
            continue
        cs = c["competitors"]
        if len(cs) != 2 or not all(x["team"]["id"] in fbs for x in cs):
            continue
        home = next(x for x in cs if x["homeAway"] == "home"); away = next(x for x in cs if x["homeAway"] == "away")
        # current line: scoreboard odds, else ESPN core odds
        sp, ou = np.nan, np.nan
        od = (c.get("odds") or [None])[0]
        if od and od.get("details"):
            tmp = [dict(p=od.get("provider", {}).get("name"), spread=od.get("spread"), ou=od.get("overUnder"), details=od.get("details"))]
            fn = os.path.join(D, "odds", f"up_{e['id']}.json"); json.dump(tmp, open(fn, "w"))
            sp, ou = build.line(f"up_{e['id']}", home["team"]["abbreviation"], away["team"]["abbreviation"])
        if sp != sp:
            o = fetch.get(fetch.ODDS.format(e["id"])) or {}
            tmp = [dict(p=i.get("provider", {}).get("name"), spread=i.get("spread"), ou=i.get("overUnder"), details=i.get("details")) for i in o.get("items", [])]
            json.dump(tmp, open(os.path.join(D, "odds", f"up_{e['id']}.json"), "w"))
            sp, ou = build.line(f"up_{e['id']}", home["team"]["abbreviation"], away["team"]["abbreviation"])
        for t in (home, away):
            o = away if t is home else home
            rows.append(dict(eid=e["id"], date=c["date"], season=season, stype=st, week=wk or 0,
                             team=t["team"]["id"], team_abbr=t["team"]["abbreviation"], opp=o["team"]["id"], opp_abbr=o["team"]["abbreviation"],
                             ha="N" if c.get("neutralSite") else ("H" if t is home else "A"), conf=bool(c.get("conferenceCompetition")),
                             spread=(sp if t is home else -sp) if sp == sp else np.nan, total=ou))
    return pd.DataFrame(rows)


def main(season, week):
    ids = fetch.weeks(season, refresh=True)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(6) as ex:
        list(ex.map(fetch.summary, ids)); list(ex.map(fetch.odds, ids))
    g = build.team_games()
    U = upcoming(season, week)
    if U.empty:
        print("no upcoming FBS vs FBS games"); return
    U["date"] = pd.to_datetime(U.date, utc=True)
    last = g.sort_values("date").groupby("team").tail(1).set_index("team")
    U["qb"] = U.team.map(last.qb); U["qb_name"] = U.team.map(last.qb_name)
    import sys as _s; _s.path.insert(0, D); import boardqb as _bq
    _B = _bq.board()
    for _i, _r in U.iterrows():
        _h = _B.get((str(_r.eid), _r.team_abbr))
        if _h and _h[0] and str(_h[0]) != str(_r.qb):
            U.at[_i, "qb"], U.at[_i, "qb_name"] = type(_r.qb)(_h[0]) if _r.qb == _r.qb else _h[0], _h[1]
    U = U[U.qb.notna()]
    for c in ("att", "ptd", "team_ptd", "pts", "opp_pts"):
        U[c] = 0
    U["upcoming"] = True
    g["upcoming"] = False
    X = build.features(pd.concat([g, U], ignore_index=True).sort_values(["date", "eid", "team"]))
    X = prep(X[X.upcoming])
    M = pickle.load(open(os.path.join(D, "model.pkl"), "rb"))
    X["p"] = M[RULE_MODEL].predict_proba(X[M["feats"]])[:, 1]
    # the model was fit on games that all had a line; without one the score is not comparable
    X["pick"] = (X.p >= RULE_P) & ((X.itt_f >= RULE_ITT) if RULE_ITT else True) & (X.has_line == 1)
    X = X.sort_values("p", ascending=False)
    pd.set_option("display.width", 200)
    print(f"{season} week {week}: {len(X)} FBS-vs-FBS starters scored; rule {RULE_MODEL.upper()} >= {RULE_P:.0%}"
          + (f" & implied team total >= {RULE_ITT}" if RULE_ITT else "") + f" -> {X.pick.sum()} qualify\n")
    show = X[["qb_name", "team_abbr", "opp_abbr", "ha", "spread", "total", "itt", "q_td", "q_n", "p", "pick"]].copy()
    show["p"] = (show.p * 100).round(1); show["q_td"] = show.q_td.round(2); show["itt"] = show.itt.round(1)
    print(show.to_string(index=False))
    if (X.has_line == 0).any():
        print(f"\n{(X.has_line == 0).sum()} starters have no ESPN line yet and cannot qualify; rerun closer to kickoff.")


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
