"""Re-score Saturday Oct 10, 2026 (ESPN week 6) with build/cfb_reads.py and compare with
   the CFB rows logged in data/reads_log.csv.

  python3 research/cfb_reads/validate_w6.py <study folder>/weeks/2026_2_6.json
  (the week-6 scoreboard: which games, kickoffs, ranks; its own lines are not used for the
  logged games -- ML has no line input, PTD/H2H get the run's lines put back)

Mode A (as run): each model is scored the way its logged run saw the world --
  history cut at the run's time, the week-6 games not yet played at that time as the
  slate, the lines those runs saw put back (H2H: the run's own csv; PTD: the printed
  week1.py table -- the logged rows' games), and the card QBs of the board at that time (ML only; the PTD and
  H2H runs of Oct 8 came before boardqb.py and used last starters).
    1+ / 2+ PTD  run 2026-10-08 20:21-20:25 UTC   (week1.py / week2.py)
    H2H          run 2026-10-08 20:53 UTC          (week_h2h.py, csv mtime)
    ML           run 2026-10-09 19:51 UTC          (week_ml.py; board = commit 9d59dc91)
Mode B (as of kickoff): history to Saturday morning, closing lines from history, last starters.
"""
import csv, json, os, re, subprocess, sys
import numpy as np, pandas as pd
R = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(R, "build"))
import cfb_reads as C

snap = json.load(open(sys.argv[1]))
H0 = C.load_hist()


def board_at(commit):
    parts = json.loads(subprocess.check_output(["git", "-C", R, "show", f"{commit}:src/parts.json"]))
    page = "".join(subprocess.check_output(["git", "-C", R, "show", f"{commit}:src/{p['file']}"]).decode() for p in parts)
    cfb = json.loads(re.search(r"\bCFB\s*=\s*(\[.*?\]);\n", page, re.S).group(1))
    out = {}
    for g in cfb:
        out[(str(g[1]), "away")] = (str(g[6] or ""), g[5], g[3])
        out[(str(g[1]), "home")] = (str(g[8] or ""), g[7], g[4])
    return out


def cut(H, t):
    t = pd.Timestamp(t)
    return {**H, **{k: H[k][H[k].date < t].reset_index(drop=True) for k in ("ptd", "h2h", "ml")}}


def events_after(t):
    t = pd.Timestamp(t); ev = {}
    for e in snap["events"]:
        if pd.Timestamp(e["competitions"][0]["date"]) > t:
            e = json.loads(json.dumps(e)); e["competitions"][0]["status"]["type"]["state"] = "pre"
            ev[e["id"]] = e
    return ev


# The lines the logged runs actually saw (the scoreboard snapshot is a day later for the
# Oct 8 runs): H2H from the run's own csv (home spread, total per game), PTD from the
# printed output of week1.py (Oct 8 20:25 UTC, the six 90%+ QBs: club, home spread, total).
H2H_CSV = os.path.join(os.path.dirname(sys.argv[1]), "..", "h2h", "week_2026_6.csv")
PTD_LINES = {"OSU": (-32.5, 56.5), "ND": (-38.5, 54.5), "ORST": (-15.5, 53.5), "NU": (-35.5, 52.5),
             "TOL": (-21.0, 54.5), "UNT": (-28.5, 57.5)}


def inject(U, which):
    U = U.copy()
    home = U[U.ha != "A"].drop_duplicates("eid").set_index("eid").team_abbr  # neutral: first listed is ESPN's home
    if which == "h2h":
        o = pd.read_csv(H2H_CSV)
        L = {(r.h_team, r.a_team): (r.h_spread, r.total) for r in o.itertuples()}
        aw = U[~U.eid.duplicated()].set_index("eid").opp_abbr
    for i, r in U.iterrows():
        hs = None
        if which == "h2h":
            hs = L.get((home[r.eid], aw[r.eid]))
        elif home[r.eid] in PTD_LINES:
            hs = PTD_LINES[home[r.eid]]
        if hs is None:
            continue
        sp, ou = hs
        U.at[i, "spread"] = (sp if r.team_abbr == home[r.eid] else -sp) if sp == sp else np.nan
        U.at[i, "total"] = ou
    return U


def run(t, board, closing=False, lo=None, lines=None):
    H = cut(H0, t)
    ev = events_after(lo or t)
    U, games = C.slate(ev, H0["fbs"], pd.Timestamp(lo or t), pd.Timestamp("2026-10-12T12:00Z"))
    if lines:
        U = inject(U, lines)
    if closing:  # the closing line every finished game carries in history
        P = H0["ptd"].set_index(["eid", "team"])
        U["spread"] = [P.spread.get((e, tm), np.nan) for e, tm in zip(U.eid, U.team)]
        U["total"] = [P.total.get((e, tm), np.nan) for e, tm in zip(U.eid, U.team)]
    return C.score(H, U, games, board, 2026)


A = {"ptd": run("2026-10-08T20:21Z", {}, lines="ptd"), "h2h": run("2026-10-08T20:53Z", {}, lines="h2h"),
     "ml": run("2026-10-09T19:51Z", board_at("9d59dc91"))}
B = run("2026-10-10T12:00Z", {}, closing=True)
log = [r for r in csv.DictReader(open(os.path.join(R, "data", "reads_log.csv"))) if r["sport"] == "CFB" and r["date"] == "2026-10-10"]
seen = set()


def find(reads, game):
    a, h = game.split(" at ")
    return next(((e, r) for e, r in reads.items() if r["away"] == a and r["home"] == h), (None, None))


def mine(reads, mkt, game, pick):
    e, r = find(reads, game)
    if r is None:
        return None, None, None
    if mkt.startswith("ML"):
        m = r["ml"]; return m and m["pick"], m and round(100 * m["p"], 1), m and m["call"] == "take"
    if mkt.startswith("H2H"):
        m = r["h2h"]; return m and "%s (%s)" % (m["pick"], m["team"]), m and round(100 * m["p"], 1), m and m["call"] == "take"
    k = "1" if mkt.startswith("1+") else "2"
    q = next((q for q in r["ptd"].values() if q["name"] == pick), None)
    return q and q["name"], q and round(100 * q["p" + k], 1), q and q["take" + k]


print("market        game          logged pick               logged |  A: pick / p / rule      |  B (kickoff, closing line)")
ok = bad = 0
for row in log:
    key = (row["market"], row["game"])
    if key in seen:
        continue
    seen.add(key)
    src = A["ml"] if row["market"].startswith("ML") else A["h2h"] if row["market"].startswith("H2H") else A["ptd"]
    pa, va, ta = mine(src, row["market"], row["game"], row["pick"])
    pb, vb, tb = mine(B, row["market"], row["game"], row["pick"])
    same = pa == row["pick"] and va is not None and abs(va - float(row["model"])) <= 0.05 and ta
    ok += same; bad += not same
    print("%-13s %-13s %-25s %5s | %s %-24s %5s %-5s | %-24s %5s %s" % (row["market"], row["game"], row["pick"], row["model"],
          "MATCH" if same else "DIFF ", pa, va, "take" if ta else "-", pb, vb, "take" if tb else "-"))
print("\nmode A exact (pick same, p within 0.05 pt, rule met): %d of %d" % (ok, ok + bad))
# reads at the rule in the re-score that were not logged (Saturday games only)
sat = lambda r: pd.Timestamp(r["kick"]).tz_convert("America/New_York").strftime("%Y-%m-%d") == "2026-10-10"
extra = []
for e, r in A["ml"].items():
    if sat(r) and r["ml"] and r["ml"]["call"] and ("ML 75%+", "%s at %s" % (r["away"], r["home"])) not in seen:
        extra.append(("ML", r["away"], r["home"], r["ml"]["pick"], r["ml"]["p"]))
for e, r in A["h2h"].items():
    if sat(r) and r["h2h"] and r["h2h"]["call"] and ("H2H 83%+", "%s at %s" % (r["away"], r["home"])) not in seen:
        extra.append(("H2H", r["away"], r["home"], r["h2h"]["pick"], r["h2h"]["p"]))
for e, r in A["ptd"].items():
    for q in r["ptd"].values():
        for k, mk in (("1", "1+ PTD 90%+"), ("2", "2+ PTD 70%+")):
            if sat(r) and q["take" + k] and (mk, "%s at %s" % (r["away"], r["home"])) not in seen:
                extra.append((mk, r["away"], r["home"], q["name"], q["p" + k]))
print("mode A takes on Saturday not in the log:", extra or "none")
