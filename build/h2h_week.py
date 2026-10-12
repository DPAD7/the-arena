"""The head-to-head read for every NFL game, the moment its lines are complete.

   The read is the edge score tested in research/nfl_h2h (thisweek2.py): each
   passer gets a point for each edge on his side -- the softer pass defense
   faced, more yards after the catch allowed, more yards allowed to the top
   receiver, the more efficient offense, his receivers set higher in total on
   their lines, a new coach on the other side -- and two for each combined box.
   No price goes into it. Lead 6+ won 78-84% of blind games (2024, 2025); lead
   4-5 about 73%. The cutoffs were locked on 2021-23 and are written below.

   A game is read only when DraftKings has both men's head to head up and a
   receiving-yards line for every receiver with 10%+ of his team's targets
   over its last three games (who also played its last one). Lines are read
   from BettingPros, which carries DraftKings' (book 12) for every player in
   one call -- the same archive the read was tested on.

   Season-to-date team profiles come from nflverse play-by-play and are kept
   in data/h2h_profiles.json, rebuilt when six hours old. A game already under
   way keeps the read it had at kickoff.

   Writes data/h2h_reads.json, which suggest.py turns into the gold on the
   game page (lead 4+, complete).

   Usage:  python3 h2h_week.py [--dry]
"""
import csv
import gzip
import io
import json
import math
import os
import re
import sys
import time
from datetime import datetime, date, timedelta, timezone

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "h2h_reads.json")
PROF = os.path.join(D, "data", "h2h_profiles.json")
DRY = "--dry" in sys.argv
SEASON = 2026
WEEK1 = date(2026, 9, 8)          # the Tuesday before week one
NFV = "https://github.com/nflverse/nflverse-data/releases/download/"
BP = "https://api.bettingpros.com/v3/"
KEY = {"x-api-key": "CHi8Hy5CEE4khd46XNYL23dCFX96oUdw6qOt1Dnh"}   # BettingPros' own public site key
S = rq.Session(impersonate="chrome")

# locked on 2021-23 (the 2/3 quantile of each gap), never refit
CUT = {"d_p_epa": 0.17, "d_yac": 0.822, "w_dwr1": 23.909, "o_epa": 0.139, "l_rec": 45.5}
NFV_TEAM = {"LAR": "LA", "JAC": "JAX", "WSH": "WAS"}


def tm(t):
    return NFV_TEAM.get(t, t)


def norm(s):
    s = (s or "").lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


def get(url, **kw):
    for i in range(3):
        try:
            r = S.get(url, timeout=60, **kw)
            if r.status_code == 200:
                return r
        except Exception:
            pass
        time.sleep(2 * (i + 1))
    raise RuntimeError("no answer from " + url.split("?")[0])


def fnum(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


# ---------------------------------------------------------------- profiles

def build_profiles():
    ros = list(csv.DictReader(io.StringIO(get(NFV + "weekly_rosters/roster_weekly_%d.csv" % SEASON).text)))
    pos = {r["gsis_id"]: r["position"] for r in ros if r.get("gsis_id")}
    name = {r["gsis_id"]: r["full_name"] for r in ros if r.get("gsis_id")}
    raw = gzip.decompress(get(NFV + "pbp/play_by_play_%d.csv.gz" % SEASON).content).decode()
    off, dfn, tgt = {}, {}, {}   # (team, week) -> lists
    for p in csv.DictReader(io.StringIO(raw)):
        if p["season_type"] != "REG" or p["play_type"] not in ("pass", "run"):
            continue
        wk, o, d = int(p["week"]), p["posteam"], p["defteam"]
        epa = fnum(p["epa"])
        isp = p["play_type"] == "pass"
        qbrun = (not isp) and pos.get(p["rusher_player_id"]) == "QB"
        for side, team in ((off, o), (dfn, d)):
            g = side.setdefault((team, wk), {"opp": d if side is off else o, "epa": [], "p_epa": [], "yac": [], "qb_repa": [], "scr": 0})
            g["epa"].append(epa)
            if isp:
                g["p_epa"].append(epa)
                g["yac"].append(fnum(p["yards_after_catch"]))
            if qbrun:
                g["qb_repa"].append(epa)
            if side is off and fnum(p["qb_scramble"]):
                g["scr"] += 1
        if isp and fnum(p["pass_attempt"]) and p["receiver_player_id"]:
            t = tgt.setdefault((o, wk), {})
            r = t.setdefault(p["receiver_player_id"], [0, 0.0])
            r[0] += 1
            r[1] += fnum(p["passing_yards"]) or 0.0

    def season(side, team, keys):
        games = [g for (t, w), g in side.items() if t == team]
        return {k: mean([(g[k] if k == "scr" else mean(g[k])) for g in games]) for k in keys}

    teams = sorted({t for t, _ in off})
    prof = {}
    for t in teams:
        prof[t] = {"off": season(off, t, ("epa", "p_epa", "scr", "qb_repa")),
                   "def": season(dfn, t, ("p_epa", "yac", "qb_repa"))}
    # yards the defense gives up to the offense's top target (by targets so far)
    wr1 = {}
    for (o, w), t in sorted(tgt.items(), key=lambda kv: kv[0][1]):
        before = {}
        for (o2, w2), t2 in tgt.items():
            if o2 == o and w2 < w:
                for pid, (n, _) in t2.items():
                    before[pid] = before.get(pid, 0) + n
        pool = before or {pid: n for pid, (n, _) in t.items()}
        lead = max(pool, key=pool.get)
        wr1.setdefault(off[(o, w)]["opp"], []).append(t.get(lead, [0, 0.0])[1])
    for t in teams:
        prof[t]["def"]["wr1"] = mean(wr1.get(t, []))
    # who must have a line: 10%+ of targets over the last three games, and in the last one
    need = {}
    for t in teams:
        wks = sorted(w for (o, w) in tgt if o == t)[-3:]
        tot, per = 0, {}
        for w in wks:
            for pid, (n, _) in tgt[(t, w)].items():
                per[pid] = per.get(pid, 0) + n
                tot += n
        last = tgt[(t, wks[-1])] if wks else {}
        need[t] = sorted([name.get(pid, pid), round(100 * n / tot)] for pid, n in per.items()
                         if tot and n / tot >= 0.10 and pid in last and pos.get(pid) != "QB")
    games = list(csv.DictReader(io.StringIO(get("https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv").text)))
    coach = {}
    for g in games:
        for s in ("away", "home"):
            if g["season"] in (str(SEASON - 1), str(SEASON)):
                coach.setdefault(g[s + "_team"], {})[g["season"]] = g[s + "_coach"]
    for t in teams:
        c = coach.get(t, {})
        prof[t]["new_coach"] = int(bool(c.get(str(SEASON))) and c.get(str(SEASON)) != c.get(str(SEASON - 1)))
    team_of = {}
    last_wk = max(int(r["week"]) for r in ros)
    for r in ros:
        if int(r["week"]) == last_wk:
            team_of[norm(r["full_name"])] = r["team"]
    return {"at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"), "teams": prof, "need": need, "team_of": team_of}


def profiles():
    try:
        P = json.load(open(PROF))
        age = datetime.now(timezone.utc) - datetime.strptime(P["at"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=timezone.utc)
        if age < timedelta(hours=6):
            return P
    except Exception:
        pass
    P = build_profiles()
    if not DRY:
        json.dump(P, open(PROF, "w"), indent=0, sort_keys=True)
    return P


# ---------------------------------------------------------------- lines

def lines(eid):
    """market -> [(name, team, position, selection, line, cost)] from DraftKings, else FanDuel."""
    out = {}
    for mid in (74, 100, 105):
        o = get(BP + "offers?sport=NFL&market_id=%d&event_id=%s&location=MD&limit=50" % (mid, eid), headers=KEY).json()
        rows = []
        for x in o.get("offers", []):
            ps = {str(p["id"]): p for p in x.get("participants") or []}
            for s in x["selections"]:
                bk = {b["id"]: b["lines"] for b in s["books"]}
                src = 12 if bk.get(12) else (10 if bk.get(10) else None)
                if src is None:
                    continue
                ln = [l for l in bk[src] if l.get("main")] or bk[src]
                p = ps.get(str(s.get("participant"))) or (list(ps.values())[0] if ps else {})
                pl = p.get("player") or {}
                rows.append((p.get("name"), pl.get("team"), pl.get("position"), s.get("selection") or "", ln[0].get("line"), ln[0].get("cost")))
        out[mid] = rows
    return out


# ---------------------------------------------------------------- the score

def score(P, ev, L):
    h = [r for r in L[74] if r[5] is not None][:2]
    if len(h) < 2:
        return None
    teams = [tm(ev["home"]), tm(ev["visitor"])]
    tms = [tm(r[1]) if tm(r[1] or "") in teams else P["team_of"].get(norm(r[0])) for r in h]
    if tms[0] not in teams or tms[1] not in teams or tms[0] == tms[1]:
        return None
    T = P["teams"]
    if tms[0] not in T or tms[1] not in T:
        return None

    def ov(mid, nm):
        for r in L[mid]:
            if r[3] == "over" and norm(r[0]) == norm(nm):
                return r[4]

    def recl(team):
        xs = [r for r in L[105] if r[3] == "over" and r[2] != "QB" and r[4] is not None and tm(r[1] or "") == team]
        return sum(r[4] for r in xs), {norm(r[0]) for r in xs}

    def gap(a, b):
        return None if a is None or b is None else a - b

    rec = {t: recl(t) for t in tms}
    missing = []
    for t in tms:
        for nm, share in P["need"].get(t, []):
            if norm(nm) not in rec[t][1]:
                missing.append("%s %s (%d%%)" % (t, nm.split(" ")[0][:1] + "." + " ".join(nm.split(" ")[1:]), share))
    sides = []
    for i in (0, 1):
        me, ot = tms[i], tms[1 - i]
        cl = [ov(100, h[i][0]), ov(100, h[1 - i][0])]
        sides.append(dict(
            d_p_epa=gap(T[ot]["def"]["p_epa"], T[me]["def"]["p_epa"]),
            d_yac=gap(T[ot]["def"]["yac"], T[me]["def"]["yac"]),
            w_dwr1=gap(T[ot]["def"]["wr1"], T[me]["def"]["wr1"]),
            o_epa=gap(T[me]["off"]["epa"], T[ot]["off"]["epa"]),
            o_p_epa=gap(T[me]["off"]["p_epa"], T[ot]["off"]["p_epa"]),
            o_scr=gap(T[me]["off"]["scr"], T[ot]["off"]["scr"]),
            m_qb_repa=gap(T[me]["off"]["qb_repa"], T[ot]["def"]["qb_repa"]),
            l_rec=rec[me][0] - rec[ot][0],
            l_cl=gap(cl[0], cl[1]),
            coach=T[me]["new_coach"]))
    for i in (0, 1):
        f, o = sides[i], sides[1 - i]
        pts = 0
        for k in CUT:
            v = f[k]
            if v is not None and abs(v) >= CUT[k]:
                pts += 1 if v > 0 else -1
        pts += f["coach"] - o["coach"]
        g = lambda k, d=0: f[k] if f[k] is not None else d
        f["bx"] = [int(g("o_epa") >= 0.1 and f["l_rec"] >= 45.5), int(g("o_p_epa") >= 0.207 and f["l_rec"] >= 33.5),
                   int(g("o_scr") <= -1 and f["l_rec"] >= 33.5), int(g("m_qb_repa") >= 0.378 and g("l_cl") >= 2)]
        f["score"] = pts + 2 * sum(f["bx"])
    a, b = sides
    li = 0 if a["score"] >= b["score"] else 1
    W, nm = sides[li], [h[0][0], h[1][0]]
    why = []
    if (W["d_p_epa"] or 0) >= CUT["d_p_epa"]: why.append("Faces the softer pass defense (EPA per pass allowed)")
    if (W["d_yac"] or 0) >= CUT["d_yac"]: why.append("Faces a defense that gives up more yards after the catch")
    if (W["w_dwr1"] or 0) >= CUT["w_dwr1"]: why.append("Opponent gives up more yards to the top receiver (%+.0f a game)" % W["w_dwr1"])
    if (W["o_epa"] or 0) >= CUT["o_epa"]: why.append("His offense is more efficient (EPA per play)")
    if W["l_rec"] >= CUT["l_rec"]: why.append("His receivers are set %.1f yards higher in total on their lines" % W["l_rec"])
    if sum(W["bx"]): why.append("%d of 4 combined boxes checked" % sum(W["bx"]))
    if W["coach"] and not sides[1 - li]["coach"]: why.append("New coach for his side")
    lead = int(abs(a["score"] - b["score"]))
    return dict(qbs=nm, pick=nm[li] if lead else None, lead=lead, complete=not missing, missing=missing,
                score=[a["score"], b["score"]], why=why if lead else [], checks=W["bx"],
                game="%s@%s" % (ev["visitor"], ev["home"]), eid=ev["id"], kick=ev["scheduled"] + "Z")


def main():
    now = datetime.now(timezone.utc)
    wk = max(1, (now.date() - WEEK1).days // 7 + 1)
    evs = []
    for w in (wk, wk + 1):
        evs += get(BP + "events?sport=NFL&week=%d&season=%d" % (w, SEASON), headers=KEY).json().get("events", [])
    try:
        old = json.load(open(OUT))
    except Exception:
        old = {"reads": []}
    keep = {}
    for r in old.get("reads", []):
        k = r.get("kick")
        if k and now - timedelta(days=2) < datetime.strptime(k, "%Y-%m-%d %H:%M:%SZ").replace(tzinfo=timezone.utc) <= now:
            keep[r["eid"]] = r     # under way or just over: the read it had at kickoff
    P = profiles()
    reads = list(keep.values())
    for ev in evs:
        kick = datetime.strptime(ev["scheduled"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        if kick <= now or kick > now + timedelta(days=8) or ev["id"] in keep:
            continue
        try:
            r = score(P, ev, lines(ev["id"]))
        except Exception as e:
            print("%s@%s: %s" % (ev["visitor"], ev["home"], e))
            continue
        if r:
            reads.append(r)
    reads.sort(key=lambda r: r["kick"])
    out = {"at": now.strftime("%Y-%m-%d %H:%M UTC"), "week": wk,
           "note": "a read only when the H2H and the line of every receiver with 10%+ of his team's targets (last 3 games) are posted on both sides",
           "reads": reads}
    for r in reads:
        print("%-9s %-22s lead %d %s%s" % (r["game"], r["pick"] or "-", r["lead"], "complete" if r["complete"] else "waiting",
                                         "" if r["complete"] else " on " + ", ".join(r["missing"])))
    if not DRY:
        json.dump(out, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
