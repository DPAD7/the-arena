"""One-off: build data/cfb_hist/ from the local ESPN cache (the 4 GB research cache,
   never in the repo), with build/cfb_reads.py's own parsers.

  python3 research/cfb_reads/make_hist.py <study folder: research/cfb_reads/study after its fetch/build have filled cache/, odds/, weeks/, fbs/>

Writes ptd.parquet, h2h.parquet, ml.parquet (team-games, 2016 on), fbs.json, seen.json.
"""
import glob, json, os, sys
import pandas as pd
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "build"))
import cfb_reads as C

S = sys.argv[1]
fbs = {int(os.path.basename(f)[:4]): set(json.load(open(f))) for f in glob.glob(os.path.join(S, "fbs", "*.json"))}
RK, done26 = {}, {}
for f in glob.glob(os.path.join(S, "weeks", "*.json")):
    try: d = json.load(open(f))
    except Exception: continue
    for e in d.get("events", []):
        for c in e["competitions"][0]["competitors"]:
            RK.setdefault(e["id"], {})[c["team"]["id"]] = (c.get("curatedRank") or {}).get("current", 99) or 99
        if os.path.basename(f).startswith("2026_") and e["competitions"][0]["status"]["type"].get("completed"):
            done26[e["id"]] = e
rows = {"ptd": [], "h2h": [], "ml": []}
cached = set()
for i, f in enumerate(glob.glob(os.path.join(S, "cache", "*.json"))):
    eid = os.path.basename(f)[:-5]; cached.add(eid)
    d = json.load(open(f))
    fn = os.path.join(S, "odds", eid + ".json")
    od = json.load(open(fn)) if os.path.exists(fn) else None
    rows["ptd"] += C.parse_ptd(d, od, fbs)
    rows["h2h"] += C.parse_h2h(d, od, fbs)
    rows["ml"] += C.parse_ml(d, RK.get(eid, {}), fbs)
    if i % 1000 == 0: print(i, flush=True)
H = {}
for k, r in rows.items():
    g = pd.DataFrame(r); g["date"] = pd.to_datetime(g["date"], utc=True)
    H[k] = g.sort_values(["date", "eid", "team"]).reset_index(drop=True)
seen = set()
for eid, e in done26.items():
    cs = e["competitions"][0]["competitors"]
    if eid in cached or not (len(cs) == 2 and all(c["team"]["id"] in fbs[2026] for c in cs)):
        seen.add(eid)
H["seen"] = {"2026": sorted(seen)}
H["fbs"] = fbs
C.save_hist(H)
print({k: len(v) for k, v in rows.items()}, "seen", len(seen))
