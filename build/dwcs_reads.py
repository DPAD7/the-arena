"""The Contender Series read: every men's bout on a DWCS card scored from the two
   men's pro records, ESPN first. Called by ufc_reads.py on each sweep; it never
   touches the regular UFC card's read.

   UFC Stats does not carry the Contender Series and most of its men have no UFC
   minutes, so the UFC model cannot read them. This one reads only what a
   prospect brings: age, height, reach, pro wins and losses, how he wins (KO, sub,
   decision, in round 1), how he loses, streak, last three, layoff, years as a pro,
   fights in a named promotion (any ESPN league but "other"), an earlier DWCS
   shot, and the level of the men he has fought (their ESPN career record).
   No odds.

   Data (data/dwcs/, from ESPN; Oct 12, 2026):
     bouts.json        every DWCS bout 2017-2026 (scoreboard, ESPN ids, winner)
     fighters.json     each man's ESPN fight log (core API eventlog, competitions, status)
     opp_records.json  the ESPN career record of every man they had fought
     odds.json         ESPN's posted moneyline, for comparison only, never in the model

   Blind test (scratchpad dwcs/honest.py): features and the ridge strength chosen on
   2017-22 only, then refit each year on the years before and 2023-26 graded:
       all bouts 56.5% (177) · 70%+ 64.0% (50, 1.28 a card) · 75%+ 65.5% (29, 0.74 a card)
       by year 46.5 / 73.3 / 50.0 / 56.1%. The posted favorite won 60.9% of the
       same bouts. No tier clears 70% blind, so no DWCS pick carries a "won" rate.

   ESPN's career record for a past opponent is today's, not the one he had then:
   a small look-ahead in the opposition-level feature only.

   Usage:  python3 build/dwcs_reads.py --fit [--before YYYY-MM-DD]
           python3 build/dwcs_reads.py --card <espn event id>     score and print
"""
import datetime as dt
import json
import math
import os
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import numpy as np

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DW = os.path.join(D, "data", "dwcs")
MODEL = os.path.join(D, "data", "models", "dwcs_ml.json")
CORE = "https://sports.core.api.espn.com/v2/sports/mma"
C_RIDGE = 0.3                         # chosen on 2019-22 walk-forward (all features)
TIERS = ()                            # no confidence band tested 75%+ blind (best: 75%+ won 65.5%)
BLIND = dict(all=(56.5, 177), t70=(64.0, 50), t75=(65.5, 29), fav=(60.9, 128), years="2023-26")

try:
    from curl_cffi import requests as _rq
except Exception:
    _rq = None

_local = threading.local()
_mem = {}


def _sess():
    s = getattr(_local, "s", None)
    if s is None:
        s = _local.s = _rq.Session(impersonate="chrome")
    return s


def gj(u, keep=True):
    u = u.replace("http://", "https://")
    if keep and u in _mem:
        return _mem[u]
    for i in range(5):
        try:
            x = _sess().get(u, timeout=30)
            if x.status_code == 200:
                j = x.json()
                _mem[u] = j
                return j
            if x.status_code == 404:
                return None
        except Exception:
            pass
        time.sleep(1 + i)
    return None


def T(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------------------------------------------------------------- ESPN
def fighter(aid):
    """one man's ESPN record: birth date, size and every fight with its result"""
    base = "%s/athletes/%s" % (CORE, aid)
    a = gj(base) or {}
    el = gj(base + "/eventlog?limit=200") or {}
    fights = []
    for it in ((el.get("events") or {}).get("items")) or []:
        cu = it["competition"]["$ref"]
        c = gj(cu)
        if not c:
            continue
        me = [x for x in c.get("competitors", []) if str(x["id"]) == str(aid)]
        op = [x for x in c.get("competitors", []) if str(x["id"]) != str(aid)]
        st = (gj(c["status"]["$ref"]) if (c.get("status") or {}).get("$ref") else None) or {}
        if not (st.get("type") or {}).get("completed"):
            continue
        fights.append(dict(cid=c["id"], league=re.search(r"/leagues/([^/]+)/", cu).group(1),
                           event=re.search(r"/events/(\d+)", cu).group(1), date=c.get("date"),
                           winner=me[0].get("winner") if me else None, opp=op[0]["id"] if op else None,
                           oppwin=op[0].get("winner") if op else None, completed=True,
                           result=(st.get("result") or {}).get("displayName"), period=st.get("period")))
    return dict(id=str(aid), name=a.get("displayName"), dob=a.get("dateOfBirth"), height=a.get("height"),
                reach=a.get("reach"), weight=a.get("weight"), fights=fights)


def opp_record(aid):
    j = gj("%s/athletes/%s/records" % (CORE, aid)) or {}
    for it in j.get("items", []):
        if it.get("name") == "overall":
            return it.get("summary")
    return None


def event_name(eid):
    j = gj("%s/leagues/ufc/events/%s" % (CORE, eid)) or {}
    return j.get("name") or ""


def is_dwcs(eid):
    return "contender" in event_name(eid).lower()


# ---------------------------------------------------------------- features
def kind(res):
    r = (res or "").lower()
    if "no contest" in r or "overturned" in r:
        return "NC"
    if "draw" in r:
        return "D"
    if any(k in r for k in ("ko", "disq", "dq", "doctor", "retire", "corner")):
        return "KO"
    if "sub" in r:
        return "SUB"
    if "dec" in r:
        return "DEC"
    return "OTH"


SIDE = ["age", "height", "reach", "pn", "pw", "pl", "wpct", "fin", "ko_rate", "sub_rate", "dec_rate", "kod", "subbed", "dec_l",
        "finished", "streak", "layoff", "l3", "big_w", "big_n", "r1_rate", "unbeaten", "dwcs_prev", "yrs", "fpy", "last_loss",
        "last_finished", "opp_pct", "qual_w", "win_opp_pct"]


def side(F, when, dwcs_events, opp):
    """his numbers on the morning of the bout (fights at least 12 hours before it)"""
    cut = when - dt.timedelta(hours=12)
    rows = sorted([f for f in F["fights"] if f.get("date") and f.get("completed") and T(f["date"]) < cut], key=lambda f: f["date"])
    o = {}
    o["age"] = (when - T(F["dob"])).days / 365.25 if F.get("dob") else np.nan
    o["height"] = F.get("height") or np.nan
    o["reach"] = F.get("reach") or np.nan
    W = [f for f in rows if f["winner"]]
    L = [f for f in rows if f["oppwin"]]
    o["pn"], o["pw"], o["pl"] = len(W) + len(L), len(W), len(L)
    o["wpct"] = len(W) / o["pn"] if o["pn"] else np.nan
    kw = [kind(f["result"]) for f in W]
    kl = [kind(f["result"]) for f in L]
    o["fin"] = sum(k in ("KO", "SUB") for k in kw) / len(W) if W else np.nan
    o["ko_rate"] = kw.count("KO") / o["pn"] if o["pn"] else np.nan
    o["sub_rate"] = kw.count("SUB") / o["pn"] if o["pn"] else np.nan
    o["dec_rate"] = kw.count("DEC") / o["pn"] if o["pn"] else np.nan
    o["kod"], o["subbed"], o["dec_l"] = kl.count("KO"), kl.count("SUB"), kl.count("DEC")
    o["finished"] = o["kod"] + o["subbed"]
    dec = [f for f in rows if f["winner"] or f["oppwin"]]
    s = 0
    for f in reversed(dec):
        if f["winner"] and s >= 0:
            s += 1
        elif f["oppwin"] and s <= 0:
            s -= 1
        else:
            break
    o["streak"] = s
    o["layoff"] = min((when - T(rows[-1]["date"])).days, 1500) if rows else np.nan
    o["l3"] = float(np.mean([1.0 if f["winner"] else 0.0 for f in dec[-3:]])) if dec else np.nan
    big = [f for f in dec if f["league"] != "other"]
    o["big_n"], o["big_w"] = len(big), sum(1 for f in big if f["winner"])
    o["r1_rate"] = sum(1 for f in W if f.get("period") == 1 and kind(f["result"]) in ("KO", "SUB")) / len(W) if W else np.nan
    o["unbeaten"] = int(o["pl"] == 0 and o["pw"] > 0)
    o["dwcs_prev"] = sum(1 for f in rows if f["event"] in dwcs_events)
    o["yrs"] = (when - T(rows[0]["date"])).days / 365.25 if rows else 0.0
    o["fpy"] = o["pn"] / max(o["yrs"], 1.0)
    o["last_loss"] = int(bool(dec) and bool(dec[-1]["oppwin"]))
    o["last_finished"] = int(bool(dec) and bool(dec[-1]["oppwin"]) and kind(dec[-1]["result"]) in ("KO", "SUB"))
    pc, wq, qw = [], [], 0
    for f in dec:
        s_ = opp.get(str(f["opp"]))
        if not s_:
            continue
        w, l = map(int, s_.split("-")[:2])
        if w + l == 0:
            continue
        pc.append(w / (w + l))
        if f["winner"]:
            wq.append(w / (w + l))
            if w + l >= 5 and w / (w + l) >= 0.6:
                qw += 1
    o["opp_pct"] = float(np.mean(pc)) if pc else np.nan
    o["qual_w"] = qw
    o["win_opp_pct"] = float(np.mean(wq)) if wq else np.nan
    return o


def diffs(A, B):
    g = lambda o, k: o.get(k, np.nan)
    d = {"d_" + k: g(A, k) - g(B, k) for k in SIDE}
    d["d_age"], d["d_layoff"] = -d["d_age"], -d["d_layoff"]
    nz = lambda x: 0.0 if x != x else x
    d["fin_vs_dur"] = nz(g(A, "fin")) * min(g(B, "finished"), 5) - nz(g(B, "fin")) * min(g(A, "finished"), 5)
    d["ko_vs_chin"] = nz(g(A, "ko_rate")) * min(g(B, "kod"), 4) - nz(g(B, "ko_rate")) * min(g(A, "kod"), 4)
    d["sub_vs_def"] = nz(g(A, "sub_rate")) * min(g(B, "subbed"), 4) - nz(g(B, "sub_rate")) * min(g(A, "subbed"), 4)
    d["log_pn"] = math.log1p(g(A, "pn")) - math.log1p(g(B, "pn"))
    return d


FC = ["d_" + k for k in SIDE] + ["fin_vs_dur", "ko_vs_chin", "sub_vs_def", "log_pn"]


def women(wc):
    return str(wc).startswith("W ") or "women" in str(wc).lower()


# ---------------------------------------------------------------- history and the model
def load_store():
    J = lambda n: json.load(open(os.path.join(DW, n)))
    return J("bouts.json"), J("fighters.json"), J("opp_records.json")


def table(bouts, fighters, opp):
    dw = {b["event"] for b in bouts}
    rows = []
    for b in bouts:
        m = b["men"]
        if len(m) != 2 or m[0]["id"] not in fighters or m[1]["id"] not in fighters or women(b["wc"]):
            continue
        if not b.get("completed") or (bool(m[0]["winner"]) == bool(m[1]["winner"])):
            continue
        when = T(b["date"])
        A, B = side(fighters[m[0]["id"]], when, dw, opp), side(fighters[m[1]["id"]], when, dw, opp)
        rows.append(dict(diffs(A, B), date=b["date"][:10], a_won=int(bool(m[0]["winner"]))))
    return rows


def fit(before=None):
    from sklearn.linear_model import LogisticRegression
    bouts, fighters, opp = load_store()
    before = before or (dt.date.today() + dt.timedelta(days=1)).isoformat()
    R = [r for r in table(bouts, fighters, opp) if r["date"] < before]
    F = np.array([[r[c] for c in FC] for r in R], float)
    F = np.where(np.isnan(F), 0.0, F)
    mu, sd = F.mean(0), F.std(0, ddof=1) + 1e-9
    Z = (F - mu) / sd
    y = np.array([r["a_won"] for r in R])
    m = LogisticRegression(C=C_RIDGE, max_iter=5000).fit(np.vstack([Z, -Z]), np.r_[y, 1 - y])
    M = dict(model="LogisticRegression (symmetric, ridge C=%s)" % C_RIDGE, fc=FC, mean=mu.tolist(), std=sd.tolist(),
             coef=m.coef_[0].tolist(), icpt=float(m.intercept_[0]), before=before, last_bout=max(r["date"] for r in R),
             n_train=len(R), blind=BLIND, tiers=[dict(min=t, won=w) for t, w in TIERS])
    os.makedirs(os.path.dirname(MODEL), exist_ok=True)
    json.dump(M, open(MODEL, "w"), indent=0)
    print("dwcs model fit on %d men's bouts before %s -> %s" % (len(R), before, os.path.relpath(MODEL, D)))
    return M


def p_of(M, d):
    x = np.array([d[c] for c in M["fc"]], float)
    x = np.where(np.isnan(x), 0.0, x)
    z = (x - np.array(M["mean"])) / np.array(M["std"])
    w = np.array(M["coef"])
    f = lambda v: 1 / (1 + math.exp(-(float(v @ w) + M["icpt"])))
    return (f(z) + 1 - f(-z)) / 2, z * w


def update_store(board_rows, now):
    """append finished DWCS cards from the board that the store lacks (ESPN
       scoreboard by date), with both men's fight logs; True when anything was added"""
    bouts, fighters, opp = load_store()
    have = {b["event"] for b in bouts}
    ev = {}
    for f in board_rows:
        if T(f[2]) < now - dt.timedelta(hours=6):
            ev.setdefault(f[0], f[2])
    new = [(e, d) for e, d in ev.items() if e not in have and is_dwcs(e)]
    if not new:
        return False
    added = []
    for e, d in new:
        day = T(d)
        for dd in (day - dt.timedelta(days=1), day):
            j = gj("https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=%s" % dd.strftime("%Y%m%d"), keep=False) or {}
            for x in j.get("events", []):
                if x["id"] != e:
                    continue
                for c in x["competitions"]:
                    cs = c["competitors"]
                    if len(cs) != 2 or not c["status"]["type"].get("completed"):
                        continue
                    added.append(dict(event=e, ename=x["name"], bid=c["id"], date=c["date"],
                                      wc=(c.get("type") or {}).get("abbreviation", ""), completed=True,
                                      period=c["status"].get("period"), clock=c["status"].get("displayClock"),
                                      sched=((c.get("format") or {}).get("regulation") or {}).get("periods"),
                                      men=[dict(id=m["id"], name=m["athlete"]["displayName"], winner=m.get("winner"),
                                                order=m.get("order")) for m in cs]))
    seen = {b["bid"] for b in bouts}
    added = [b for b in {b["bid"]: b for b in added}.values() if b["bid"] not in seen]
    if not added:
        return False
    ids = sorted({m["id"] for b in added for m in b["men"]})
    with ThreadPoolExecutor(8) as ex:
        for F in ex.map(fighter, ids):
            fighters[F["id"]] = F
    need = sorted({str(f["opp"]) for i in ids for f in fighters[i]["fights"] if f["opp"]} - set(opp))
    with ThreadPoolExecutor(8) as ex:
        for i, r in zip(need, ex.map(opp_record, need)):
            if r:
                opp[i] = r
    bouts += added
    for n, v in (("bouts.json", bouts), ("fighters.json", fighters), ("opp_records.json", opp)):
        json.dump(v, open(os.path.join(DW, n), "w"), separators=(",", ":"))
    print("  dwcs store: +%d bouts from %s" % (len(added), ", ".join(e for e, _ in new)))
    return True


# ---------------------------------------------------------------- the card
def _sur(n):
    p = [w for w in str(n).split() if w.lower().strip(".") not in ("jr", "sr", "ii", "iii")]
    return p[-1] if p else str(n)


def why(A, B, pick, vs, push, fc):
    """the model's biggest pushes toward the pick, said with both men's numbers"""
    me, op = _sur(pick), _sur(vs)

    def rec(o):
        return "%d-%d" % (o["pw"], o["pl"])

    def pct(x):
        return "%.0f%%" % (100 * x) if x == x else "n/a"

    def stk(s):
        return ("W%d" % s) if s > 0 else ("L%d" % -s) if s < 0 else "none"
    T_ = {
        "d_age": lambda: ("%.0f years younger (%.0f vs %.0f)" % (B["age"] - A["age"], A["age"], B["age"]) if B["age"] - A["age"] >= 1
                          else "Age %.0f vs %.0f" % (A["age"], B["age"])),
        "d_height": lambda: ('%.0f" taller' % (A["height"] - B["height"]) if A["height"] > B["height"]
                             else 'Height %.0f" vs %.0f"' % (A["height"], B["height"])),
        "d_reach": lambda: ('%.0f" more reach (%.0f vs %.0f)' % (A["reach"] - B["reach"], A["reach"], B["reach"]) if A["reach"] > B["reach"]
                            else 'Reach %.0f" vs %.0f"' % (A["reach"], B["reach"])),
        "d_wpct": lambda: "Pro record %s vs %s" % (rec(A), rec(B)),
        "d_pl": lambda: "%d pro losses vs %d" % (A["pl"], B["pl"]),
        "d_pw": lambda: "%d pro wins vs %d" % (A["pw"], B["pw"]),
        "d_pn": lambda: "%d pro fights vs %d" % (A["pn"], B["pn"]),
        "log_pn": lambda: "%d pro fights vs %d" % (A["pn"], B["pn"]),
        "d_streak": lambda: "Pro streak %s vs %s" % (stk(A["streak"]), stk(B["streak"])),
        "d_l3": lambda: "Won %d of his last 3, %s %d" % (round(3 * A["l3"]), op, round(3 * B["l3"])),
        "d_unbeaten": lambda: "Unbeaten at %s; %s has lost %s" % (rec(A), op, "once" if B["pl"] == 1 else "%d times" % B["pl"]),
        "d_fin": lambda: "Finishes %s of his wins, %s %s" % (pct(A["fin"]), op, pct(B["fin"])),
        "d_ko_rate": lambda: "%d KO wins in %d fights, %s %d in %d" % (round(A["ko_rate"] * A["pn"]), A["pn"], op, round(B["ko_rate"] * B["pn"]), B["pn"]),
        "d_sub_rate": lambda: "%d submission wins, %s %d" % (round(A["sub_rate"] * A["pn"]), op, round(B["sub_rate"] * B["pn"])),
        "d_dec_rate": lambda: "%d wins on the cards, %s %d" % (round(A["dec_rate"] * A["pn"]), op, round(B["dec_rate"] * B["pn"])),
        "d_r1_rate": lambda: "Finishes %s of his wins in round 1, %s %s" % (pct(A["r1_rate"]), op, pct(B["r1_rate"])),
        "d_kod": lambda: "KO'd %s, %s %s" % (_times(A["kod"]), op, _times(B["kod"])),
        "d_subbed": lambda: "Submitted %s, %s %s" % (_times(A["subbed"]), op, _times(B["subbed"])),
        "d_finished": lambda: "Finished %s as a pro, %s %s" % (_times(A["finished"]), op, _times(B["finished"])),
        "d_dec_l": lambda: "Decision losses %d vs %d" % (A["dec_l"], B["dec_l"]),
        "fin_vs_dur": lambda: "Finishes %s of his wins; %s has been finished %s" % (pct(A["fin"]), op, _times(B["finished"])),
        "ko_vs_chin": lambda: "KO power vs %s's chin: KO'd %s" % (op, _times(B["kod"])),
        "sub_vs_def": lambda: "Submission threat vs %s, submitted %s" % (op, _times(B["subbed"])),
        "d_layoff": lambda: "Fought %.0f months ago, %s %.0f" % (A["layoff"] / 30.4, op, B["layoff"] / 30.4),
        "d_yrs": lambda: "%.0f years as a pro, %s %.0f" % (A["yrs"], op, B["yrs"]),
        "d_big_w": lambda: "%d wins in named promotions, %s %d" % (A["big_w"], op, B["big_w"]),
        "d_big_n": lambda: "%d fights in named promotions, %s %d" % (A["big_n"], op, B["big_n"]),
        "d_dwcs_prev": lambda: "Back on the Contender Series (%d before)" % A["dwcs_prev"],
        "d_opp_pct": lambda: "His opponents won %s of their fights, %s's %s" % (pct(A["opp_pct"]), op, pct(B["opp_pct"])),
        "d_qual_w": lambda: "%d wins over men with winning records (5+ fights), %s %d" % (A["qual_w"], op, B["qual_w"]),
        "d_win_opp_pct": lambda: "Men he beat won %s of their fights, %s's %s" % (pct(A["win_opp_pct"]), op, pct(B["win_opp_pct"])),
        "d_fpy": lambda: "%.1f fights a year, %s %.1f" % (A["fpy"], op, B["fpy"]),
        "d_last_loss": lambda: "%s lost his last fight" % op,
        "d_last_finished": lambda: "%s was finished in his last fight" % op,
    }
    out = []
    for j in np.argsort(-push):
        if push[j] <= 0.02:
            break
        c = fc[j]
        if c in T_:
            try:
                s = T_[c]()
            except Exception:
                continue
            if s not in out:
                out.append(s)
        if len(out) == 4:
            break
    return out


def _times(n):
    n = int(n)
    return "never" if n == 0 else "once" if n == 1 else "%d times" % n


def score_card(rows, M, now=None):
    """the board's FIGHTS rows of one DWCS card -> scored bouts, strongest first.
       Both men's records are read fresh from ESPN; past opponents' records are
       taken from the store, the missing ones fetched."""
    bouts, fighters, opp = load_store()
    dw = {b["event"] for b in bouts} | {str(rows[0][0])}
    ids = sorted({str(f[i]) for f in rows for i in (4, 6) if f[i]})
    with ThreadPoolExecutor(8) as ex:
        fresh = dict(zip(ids, ex.map(fighter, ids)))
    for i in ids:
        if not fresh[i]["fights"] and i in fighters:     # ESPN came back empty: the store's copy
            fresh[i] = fighters[i]
    need = sorted({str(f["opp"]) for i in ids for f in fresh[i]["fights"] if f["opp"]} - set(opp))
    if need:
        with ThreadPoolExecutor(8) as ex:
            for i, r in zip(need, ex.map(opp_record, need)):
                if r:
                    opp[i] = r
        json.dump(opp, open(os.path.join(DW, "opp_records.json"), "w"), separators=(",", ":"))
    out = []
    for f in rows:
        when = T(f[2])
        A = side(fresh[str(f[4])], when, dw, opp)
        B = side(fresh[str(f[6])], when, dw, opp)
        d = diffs(A, B)
        p, push = p_of(M, d)
        a_pick = p >= 0.5
        pk, vs = (f[3], f[5]) if a_pick else (f[5], f[3])
        S, O = (A, B) if a_pick else (B, A)
        out.append(dict(bid=str(f[1]), pick=pk, vs=vs, id=str(f[4] if a_pick else f[6]), conf=max(p, 1 - p), first=bool(a_pick),
                        women=women(f[7]), wc=f[7], why=why(S, O, pk, vs, push if a_pick else -push, M["fc"]),
                        rec=(S["pw"], S["pl"], O["pw"], O["pl"])))
    return sorted(out, key=lambda x: -x["conf"])


def picks(scored):
    """site/boxpicks.json's per-bout shape: men's bouts only, ranked; "won" only for a
       tier tested 75%+ blind (none yet), so every DWCS read is a lean"""
    out, allb, rank = {}, {}, 0
    try:
        FP = json.load(open(os.path.join(D, "site", "prices.json"))).get("FIGHTS", {})
    except Exception:
        FP = {}
    for x in scored:
        pct = int(round(100 * x["conf"]))
        allb[x["bid"]] = dict(pick=x["pick"], vs=x["vs"], p=pct, women=x["women"])
        if x["women"]:
            continue
        rank += 1
        won = next((w for t, w in TIERS if x["conf"] >= t), None)
        out[x["bid"]] = dict(rank=rank, pick=x["pick"], vs=x["vs"], box=[pct, 100 - pct], p=pct, won=won,
                             why=x["why"] + ["Contender Series read (pro records, no odds): %d%%+ reads won %.1f%% blind %s" % (
                                 75 if pct >= 75 else 70 if pct >= 70 else 50, BLIND["t75"][0] if pct >= 75 else
                                 BLIND["t70"][0] if pct >= 70 else BLIND["all"][0], BLIND["years"])],
                             id=x["id"], own_facts="", opp_facts="", opp_flag=False, model="dwcs")
        # the same "Our call" line the UFC tickets carry (Jose, Oct 12, 2026); a
        # Contender Series call is the winner, at its own band's blind rate
        band = BLIND["t75"] if pct >= 75 else BLIND["t70"] if pct >= 70 else BLIND["all"]
        pr = (FP.get(x["bid"]) or ["", "", "", ""])[0 if x.get("first") else 2] or None
        out[x["bid"]]["call"] = dict(market="Moneyline", side=x["pick"] + " wins", p=pct, won=round(band[0]), price=pr,
                                     why=x["why"][:3])
    return out, allb


def main():
    a = sys.argv[1:]
    if "--fit" in a:
        fit(a[a.index("--before") + 1] if "--before" in a else None)
        return 0
    if "--card" in a:
        sys.path.insert(0, os.path.join(D, "build"))
        import pagefile
        s = pagefile.read()
        F = json.loads(re.search(r"var FIGHTS = (\[\[.*?\]\]);", s, re.S).group(1))
        rows = [f for f in F if str(f[0]) == a[a.index("--card") + 1]]
        M = json.load(open(MODEL))
        for x in score_card(rows, M):
            print("%3.0f%%  %-24s over %-24s %s" % (100 * x["conf"], x["pick"], x["vs"], "; ".join(x["why"])))
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
