"""ESPN core odds per event, keeping the moneylines (home/away) per provider.

  python3 ml/fetch_ml.py 2022 2023 ...   -> ml/mlodds/<eid>.json
Only FBS-vs-FBS games already in games.parquet. Used ONLY as the book check, never as a model input.
"""
import json, os, sys
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
M = os.path.dirname(os.path.abspath(__file__)); D = os.path.dirname(M)
sys.path.insert(0, D)
import fetch

def one(eid, force=False):
    fn = os.path.join(M, "mlodds", f"{eid}.json")
    if os.path.exists(fn) and not force:
        return
    d = fetch.get(fetch.ODDS.format(eid)) or {}
    keep = []
    for i in d.get("items", []):
        h, a = i.get("homeTeamOdds") or {}, i.get("awayTeamOdds") or {}
        cl = i.get("close") or {}
        keep.append(dict(p=(i.get("provider") or {}).get("name"), details=i.get("details"), spread=i.get("spread"),
                         hml=h.get("moneyLine"), aml=a.get("moneyLine"), hfav=h.get("favorite"), afav=a.get("favorite")))
    json.dump(keep, open(fn, "w"))

if __name__ == "__main__":
    yrs = [int(x) for x in sys.argv[1:]] or list(range(2016, 2027))
    g = pd.read_parquet(os.path.join(D, "games.parquet"))
    ids = sorted(set(g[g.season.isin(yrs)].eid))
    with ThreadPoolExecutor(8) as ex:
        list(ex.map(one, ids))
    print("done", len(ids))
