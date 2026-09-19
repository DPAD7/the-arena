"""Write down every settled market on the board, one row per leg, forever.

   The head-to-head favorite went 5 of 11 this week, which looks like a hole in
   the market and is really just eleven games. The only way to tell the
   difference is to keep the rows and let them add up. Each week this appends
   to results.csv; nothing is ever rewritten.

   Run it after a slate finishes:  python3 log_week.py
"""
import csv
import json
import os
import re
import subprocess
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "results.csv")
FIELDS = ["date", "league", "event", "game", "market", "side", "player",
          "price", "line", "result", "value", "opp_value",
          "team_fav", "same_side", "final", "margin", "note"]


def get(u):
    return json.loads(subprocess.run(["curl", "-s", "-m", "45", u],
                                     capture_output=True, text=True).stdout or "{}")


def num(t):
    m = re.match(r"\s*(&minus;|−|-|\+)?\s*(\d+)", t or "")
    if not m:
        return None
    v = int(m.group(2))
    return -v if m.group(1) in ("&minus;", "−", "-") else v


def passing(box, surname):
    for t in box:
        for cat in t.get("statistics") or []:
            if cat.get("name") != "passing":
                continue
            labs = cat.get("labels") or []
            for a in cat.get("athletes") or []:
                nm = (a.get("athlete") or {}).get("displayName") or ""
                if surname and surname in nm:
                    st = a.get("stats") or []
                    m = {labs[i]: st[i] for i in range(min(len(labs), len(st)))}
                    return int(m.get("YDS") or 0), int(m.get("TD") or 0)
    return None, None


s = open(os.path.join(D, "master.html")).read()
CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)
rows = []

for mm in CARD.finditer(s):
    c = mm.group(0)
    lg = (re.search(r'data-lg="([^"]*)"', c) or [None, None])[1]
    eid = (re.search(r'data-espn="(\d+)"', c) or [None, None])[1]
    if not lg or not eid:
        continue
    d = get("https://site.api.espn.com/apis/site/v2/sports/football/%s/summary?event=%s" % (lg, eid))
    comp = ((d.get("header") or {}).get("competitions") or [{}])[0]
    if (((comp.get("status") or {}).get("type") or {}).get("state")) != "post":
        continue
    day = (comp.get("date") or "")[:10]
    sc, home = {}, None
    for x in comp.get("competitors", []):
        ab = (x.get("team") or {}).get("abbreviation")
        sc[ab] = int(x.get("score") or 0)
        if x.get("homeAway") == "home":
            home = ab
    teams = re.findall(r'<span class="gteam[^"]*">(?:<span class="gml">.*?</span>)?'
                       r'([A-Za-z&;.]+)(?:<span class="gml">.*?</span>)?</span>', c, re.S)
    game = "/".join(teams[:2])
    lq = (re.search(r'data-lqb="([^"]*)"', c) or [None, ""])[1]
    rq = (re.search(r'data-rqb="([^"]*)"', c) or [None, ""])[1]
    box = (d.get("boxscore") or {}).get("players") or []
    winner = max(sc, key=sc.get) if sc else None
    margin = abs(list(sc.values())[0] - list(sc.values())[1]) if len(sc) == 2 else ""
    final = " ".join("%s %d" % (k, v) for k, v in sc.items())

    head = re.search(r'<div class="ghead">.*?</div>\n', c, re.S)
    ml = [num(x) for x in re.findall(r'<span class="gml"><button[^>]*>([^<]*)', head.group(0))] if head else []
    mlfav = None
    if len(ml) == 2 and None not in ml:
        mlfav = 0 if ml[0] < ml[1] else 1

    def add(market, side, player, price, line, result, value, opp, note=""):
        rows.append({"date": day, "league": lg, "event": eid, "game": game,
                     "market": market, "side": side, "player": player,
                     "price": price, "line": line, "result": result,
                     "value": value, "opp_value": opp,
                     "team_fav": "" if mlfav is None else teams[mlfav],
                     "same_side": "" if mlfav is None else int(mlfav == side),
                     "final": final, "margin": margin, "note": note})

    # moneylines
    for i, t in enumerate(teams[:2]):
        if i < len(ml) and ml[i] is not None:
            add("ML", i, t, ml[i], "", int(t == winner), sc.get(t, ""), "", "")

    # head to head passing yards
    h = re.search(r'<div class="h2hrow">.*?</div>\n', c, re.S)
    if h:
        pr = [num(x) for x in re.findall(r'<span class="h2hodds"><button[^>]*>([^<]*)', h.group(0))]
        ly, _ = passing(box, lq.split()[-1] if lq else "")
        ry, _ = passing(box, rq.split()[-1] if rq else "")
        if len(pr) == 2 and ly is not None and ry is not None:
            for i, (who, p, v, o) in enumerate(((lq, pr[0], ly, ry), (rq, pr[1], ry, ly))):
                if p is None:
                    continue
                add("H2H_YDS", i, who, p, "", int(v > o), v, o)

    # passing and scoring touchdowns
    for sec in re.finditer(r'<div class="ptdx[^"]*"[^>]*>.*?\n        </div>', c, re.S):
        kind = (re.search(r'data-kind="([^"]*)"', sec.group(0)) or [None, "PTD"])[1]
        for i, side in enumerate(("l", "r")):
            pane = re.search(r'<div class="ptdside ptdside--%s">.*?</div></div>' % side,
                             sec.group(0), re.S)
            if not pane:
                continue
            who = lq if i == 0 else rq
            _, td = passing(box, who.split()[-1] if who else "")
            if td is None:
                continue
            for line, price in re.findall(r'<span class="ptdline">(\d)\+</span>'
                                          r'<button[^>]*>([^<]*)', pane.group(0)):
                p = num(price)
                if p is None:
                    continue
                add(kind, i, who, p, int(line), int(td >= int(line)), td, "")

new = not os.path.exists(OUT)
with open(OUT, "a", newline="") as f:
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()
    for r in rows:
        w.writerow(r)
print("wrote %d rows to results.csv" % len(rows))
