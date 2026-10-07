"""The QB Wire: what moved around each passer, newest first, for the Clips page.

   Three kinds of card, all from files the sweep already writes -- nothing is
   read by name, everything by ESPN id (Jose, Oct 7, 2026, mocked first):

     status   a passer listed questionable, doubtful, out or on IR
              (site/wire.json: status, injury, return date, the reporter's note)
     swap     a club starting another man because its passer is out
              (site/depth.json's starter against site/wire.json), and any
              starter the depth chart changes between sweeps
     targets  a passer whose top targets are questionable or worse: a
              teammate with 15%+ of the targets (site/alerts.json, the same
              rule the leg alerts use)

   Each card keeps the moment it was first seen (data/qbwire_seen.json), so
   the order holds from one sweep to the next. A receiver's face is copied to
   site/faces/nfl the first time he is on a card, so the page never asks ESPN.

   Usage:  python3 build/qbwire.py         writes site/qbwire.json
"""
import datetime as dt
import json
import os
import subprocess

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(D, "site")
OUT = os.path.join(SITE, "qbwire.json")
SEEN = os.path.join(D, "data", "qbwire_seen.json")
STARTERS = os.path.join(D, "data", "qb_starters.json")
PEOPLE = os.path.join(D, "data", "qbwire_people.json")
NOW = dt.datetime.now(dt.timezone.utc)
STAMP = NOW.strftime("%Y-%m-%dT%H:%MZ")


def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def curl(url):
    r = subprocess.run(["curl", "-sL", "--max-time", "20", url], capture_output=True)
    return r.stdout if r.returncode == 0 else b""


def college_man(pid, people):
    """Name and club of a college passer on the wire, asked of ESPN once."""
    if pid in people:
        return people[pid]
    try:
        a = json.loads(curl("https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/seasons/%d/athletes/%s"
                            % (NOW.year, pid)) or b"{}")
        club = ""
        ref = (a.get("team") or {}).get("$ref")
        if ref:
            club = json.loads(curl(ref) or b"{}").get("abbreviation") or ""
        if a.get("displayName"):
            people[pid] = {"n": a["displayName"], "t": club, "lg": "college-football"}
            return people[pid]
    except Exception:
        pass
    return None


TEAMS = os.path.join(D, "data", "qb_clubs.json")
CLUB_ABBR = {}


def past_clubs(pid, teams):
    """{club: [seasons]} a passer has played for, from ESPN's season log,
       asked once a week a man."""
    held = teams.get(pid)
    if held and held.get("at", "") > (NOW - dt.timedelta(days=7)).strftime("%Y-%m-%d"):
        return held["clubs"]
    if not CLUB_ABBR:
        try:
            d = json.loads(curl("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams") or b"{}")
            for t in d["sports"][0]["leagues"][0]["teams"]:
                CLUB_ABBR[str(t["team"]["id"])] = t["team"]["abbreviation"]
        except Exception:
            return (held or {}).get("clubs", {})
    clubs = {}
    try:
        log = json.loads(curl("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/athletes/%s/statisticslog" % pid) or b"{}")
        for e in log.get("entries", []):
            yr = (e.get("season") or {}).get("$ref", "").split("/seasons/")[-1][:4]
            for st in e.get("statistics", []):
                ref = (st.get("team") or {}).get("$ref", "")
                if ref:
                    ab = CLUB_ABBR.get(ref.split("/teams/")[-1].split("?")[0])
                    if ab:
                        clubs.setdefault(ab, []).append(yr)
    except Exception:
        return (held or {}).get("clubs", {})
    teams[pid] = {"at": NOW.strftime("%Y-%m-%d"), "clubs": clubs}
    return clubs


def keep_face(pid):
    """A receiver's face on our own site, copied once."""
    path = os.path.join(SITE, "faces", "nfl", pid + ".png")
    if os.path.exists(path) and os.path.getsize(path) > 500:
        return True
    raw = curl("https://a.espncdn.com/i/headshots/nfl/players/full/%s.png" % pid)
    if len(raw) < 500 or not raw.startswith(b"\x89PNG"):
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    open(path, "wb").write(raw)
    return True


def main():
    wire = load(os.path.join(SITE, "wire.json"), {})
    depth = load(os.path.join(SITE, "depth.json"), {})
    alerts = load(os.path.join(SITE, "alerts.json"), {})
    qbs = (load(os.path.join(SITE, "qbsearch.json"), {}) or {}).get("qbs", {})
    seen = load(SEEN, {})
    starters = load(STARTERS, {})
    people = load(PEOPLE, {})

    def man(pid):
        q = qbs.get(pid)
        if q:
            return {"n": q["n"], "t": q["t"], "lg": "nfl"}
        for club, row in depth.items():
            for x in row.get("qbs", []):
                if x.get("id") == pid:
                    return {"n": x["name"], "t": club, "lg": "nfl"}
        return college_man(pid, people)

    def next_game(club):
        best = None
        for q in qbs.values():
            if q.get("t") == club and q.get("nx") and q["nx"].get("d"):
                if not best or q["nx"]["d"] < best["d"]:
                    best = q["nx"]
        return {"o": best.get("o"), "h": best.get("h"), "d": best.get("d")} if best else None

    cards = []
    # -- status: every passer on the wire
    for pid, v in wire.items():
        m = man(pid)
        # NFL only, like the clips above it (Jose, Oct 7, 2026: "it needs to be ONLY")
        if not m or not v.get("status") or m.get("lg") != "nfl":
            continue
        note = v.get("note") or ""
        if note.strip().lower() == str(v["status"]).lower():
            note = ""
        # a whole injury report pasted as one note: only the line about him
        if len(note) > 220:
            import re as _re
            last = m["n"].split()[-1]
            bits = [b.strip() for b in _re.split(r"(?<=[.!?])\s+", note) if last in b]
            note = " ".join(bits)[:220] if bits else note[:220].rsplit(" ", 1)[0] + "\u2026"
        key = "st@%s@%s" % (pid, v["status"])
        cards.append({"k": "status", "key": key, "at": v.get("since") or seen.get(key) or STAMP,
                      "id": pid, "n": m["n"], "t": m["t"], "lg": m["lg"], "st": v["status"],
                      "inj": "" if v.get("type") in (None, "None") else v["type"],
                      "back": v.get("returns") or "", "note": note})

    # -- swap: a club starting another man while its passer is out, and any
    #    starter the depth chart moved since the last sweep
    out_by_id = {pid: v for pid, v in wire.items() if v.get("status") in ("Out", "Injured Reserve", "Doubtful")}
    for club, row in depth.items():
        st = row.get("starter")
        if not st:
            continue
        names = {x["id"]: x for x in row.get("qbs", [])}
        was = starters.get(club)
        # only a man ranked above the starter: a hurt backup is no swap
        st_rank = (names.get(st) or {}).get("rank") or 9
        hurt = [x for x in row.get("qbs", []) if x["id"] in out_by_id and x["id"] != st and (x.get("rank") or 9) < st_rank]
        gone = None
        if hurt:
            gone = min(hurt, key=lambda x: x.get("rank") or 9)
        elif was and was != st and was in names:
            gone = names[was]
        if gone:
            key = "sw@%s@%s@%s" % (club, gone["id"], st)
            when = (out_by_id.get(gone["id"]) or {}).get("since") or seen.get(key) or STAMP
            w = out_by_id.get(gone["id"]) or {}
            why = ", ".join(x for x in [(w.get("type") or "").split(" - ")[0].lower() if w.get("type") not in (None, "None") else "",
                                        {"Injured Reserve": "IR"}.get(w.get("status"), (w.get("status") or "").lower())] if x)
            cards.append({"k": "swap", "key": key, "at": when, "t": club, "lg": "nfl",
                          "id": st, "n": names.get(st, {}).get("name") or (man(st) or {}).get("n", ""),
                          "out": gone["id"], "on": gone["name"], "why": why})
        starters[club] = st

    # -- targets: a starter whose top targets are questionable or worse
    by_club = {}
    for gid, g in alerts.items():
        for x in g.get("out") or []:
            if x.get("pos") == "QB" or x.get("tsh") is None or (x.get("tsh") or 0) < 0.15:
                continue
            by_club.setdefault(x["team"], {})[x["id"]] = x
    for club, xs in by_club.items():
        st = (depth.get(club) or {}).get("starter")
        m = man(st) if st else None
        if not m:
            continue
        rows = sorted(xs.values(), key=lambda x: -(x.get("tsh") or 0))
        for x in rows:
            keep_face(x["id"])
        key = "tg@%s@%s" % (club, ",".join(sorted(x["id"] + ":" + x["status"] for x in rows)))
        cards.append({"k": "targets", "key": key, "at": seen.get(key) or STAMP, "t": club, "lg": "nfl",
                      "id": st, "n": m["n"], "nx": next_game(club),
                      "share": round(sum(x.get("tsh") or 0 for x in rows) * 100),
                      "rows": [{"id": x["id"], "n": x["name"], "pos": x["pos"], "st": x["status"],
                                "inj": x.get("why") or "", "sh": round((x.get("tsh") or 0) * 100)} for x in rows]})

    # -- the rest of what goes into a call that is not a hit rate (Jose,
    #    Oct 7, 2026: "birthday... revenge games... streaks hot cold... 1 PTD
    #    streaks"): only the starter of each club, only his next game
    births = (load(os.path.join(SITE, "birthdays.json"), {}) or {}).get("qb", {})
    teams = load(TEAMS, {})
    for club, row in depth.items():
        st = row.get("starter")
        q = qbs.get(st) if st else None
        if not q or not q.get("nx") or not q["nx"].get("d"):
            continue
        nx = q["nx"]
        kick = dt.datetime.strptime(nx["d"], "%Y-%m-%dT%H:%MZ").replace(tzinfo=dt.timezone.utc)
        if kick < NOW or kick - NOW > dt.timedelta(days=8):
            continue
        base = {"t": club, "lg": "nfl", "id": st, "n": q["n"], "nx": {"o": nx.get("o"), "h": nx.get("h"), "d": nx.get("d")}}
        # 1+ PTD run, and a cold one, over this season's games, newest first
        games = sorted(q.get("g") or [], key=lambda g: g.get("d") or "", reverse=True)
        hot = 0
        for g in games:
            if (g.get("p") or 0) >= 1:
                hot += 1
            else:
                break
        cold = 0
        for g in games:
            if (g.get("p") or 0) == 0:
                cold += 1
            else:
                break
        if hot >= 3:
            key = "hot@%s@%d" % (st, hot)
            cards.append(dict(base, k="streak", key=key, at=seen.get(key) or STAMP, hot=hot, of=len(games),
                              tds=[g.get("p") or 0 for g in games[:hot]]))
        if cold >= 2:
            key = "cold@%s@%d" % (st, cold)
            cards.append(dict(base, k="cold", key=key, at=seen.get(key) or STAMP, cold=cold))
        # his birthday on game day, or in the week of it
        for gid, men in births.items():
            b = men.get(st)
            if not b or not b.get("on"):
                continue
            on = dt.datetime.strptime(b["on"], "%Y-%m-%d").date()
            if abs((on - kick.date()).days) <= 3:
                key = "bday@%s@%s" % (st, b["on"])
                cards.append(dict(base, k="birthday", key=key, at=seen.get(key) or STAMP, on=b["on"],
                                  age=b.get("age"), day=on == kick.astimezone(dt.timezone(dt.timedelta(hours=-4))).date()))
        # facing a club he played for
        past = past_clubs(st, teams)
        if nx.get("o") and nx["o"] in past and nx["o"] != club:
            key = "rev@%s@%s" % (st, nx["o"])
            cards.append(dict(base, k="revenge", key=key, at=seen.get(key) or STAMP, was=nx["o"], yrs=past[nx["o"]]))
        # weather that counts against a passing leg: 15+ mph wind or rain
        wx = nx.get("wx") or {}
        if wx and not wx.get("in") and ((wx.get("g") or 0) >= 15 or (wx.get("p") or 0) >= 50):
            key = "wx@%s@%s" % (st, nx.get("gid"))
            cards.append(dict(base, k="weather", key=key, at=seen.get(key) or STAMP,
                              wind=wx.get("g"), rain=wx.get("p"), temp=wx.get("t")))
    # -- the offensive line, the lead back, a first start (Jose, Oct 7, 2026:
    #    "definitely need [the offensive line], definitely need lead back,
    #    first start")
    lineups = load(os.path.join(SITE, "lineups.json"), {})
    POS = {"lt": "LT", "lg": "LG", "c": "C", "rg": "RG", "rt": "RT"}
    for club, row in depth.items():
        st = row.get("starter")
        q = qbs.get(st) if st else None
        if not q or not (q.get("nx") or {}).get("gid"):
            continue
        nx = q["nx"]
        base = {"t": club, "lg": "nfl", "id": st, "n": q["n"]}
        side = (lineups.get(nx["gid"]) or {}).get(club) or {}
        hurt = [x for x in side.get("off", []) if x.get("k") in POS and x.get("s") in ("q", "out")]
        if hurt:
            key = "ol@%s@%s" % (nx["gid"], ",".join(sorted(x["k"] + x["s"] for x in hurt)))
            cards.append(dict(base, k="ol", key=key, at=seen.get(key) or STAMP,
                              rows=[{"pos": POS[x["k"]], "n": x.get("nm") or "", "st": "Out" if x["s"] == "out" else "Questionable"} for x in hurt]))
        if not (q.get("g") or []) and not past_clubs(st, teams):
            key = "first@%s" % st
            cards.append(dict(base, k="first", key=key, at=seen.get(key) or STAMP))
    for gid, g in alerts.items():
        for x in g.get("out") or []:
            if x.get("pos") != "RB" or (x.get("sh") or 0) < 0.20:
                continue
            st = (depth.get(x["team"]) or {}).get("starter")
            m = man(st) if st else None
            if not m:
                continue
            keep_face(x["id"])
            key = "rb@%s@%s" % (x["id"], x["status"])
            cards.append({"k": "rb", "key": key, "at": seen.get(key) or STAMP, "t": x["team"], "lg": "nfl", "id": st, "n": m["n"],
                          "rb": {"id": x["id"], "n": x["name"], "st": x["status"], "inj": x.get("why") or "", "sh": round(x["sh"] * 100)}})
    json.dump(teams, open(TEAMS, "w"), indent=0, sort_keys=True)

    for c in cards:
        seen.setdefault(c["key"], c["at"])
    cards.sort(key=lambda c: c["at"], reverse=True)
    # one card a passer, everything about him on it, by kickoff (Jose, Oct 7,
    # 2026: "one card per player... so I don't have to search 20 different
    # places for one quarterback"). A hurt man who is not starting rides on
    # his club's starter, as the starter change.
    groups = {}
    for c in cards:
        club = c.get("t")
        st = (depth.get(club) or {}).get("starter")
        if not st:
            continue
        if c["k"] == "status" and c["id"] != st:
            continue        # a hurt backup, or the man the swap row names
        g = groups.get(club)
        if not g:
            q = qbs.get(st) or {}
            m = man(st) or {}
            nx = q.get("nx") or {}
            g = groups[club] = {"id": st, "n": m.get("n") or q.get("n") or "", "t": club, "lg": "nfl",
                                "nx": {"o": nx.get("o"), "h": nx.get("h"), "d": nx.get("d")} if nx.get("d") else None,
                                "at": c["at"], "facts": []}
        if c["k"] == "swap":
            w = wire.get(c["out"]) or {}
            c = dict(c, back=w.get("returns") or "", note=w.get("note") or "")
        g["facts"].append({k: v for k, v in c.items() if k not in ("t", "lg", "id", "n", "nx") or c["k"] in ("swap", "targets")})
        g["at"] = max(g["at"], c["at"])
    ORDER = {"status": 0, "swap": 1, "first": 1, "targets": 2, "rb": 2, "ol": 3, "revenge": 4, "birthday": 5, "streak": 6, "cold": 6, "weather": 7}
    # his 1+ and 2+ PTD prices as they stand now, off the price file
    book = load(os.path.join(SITE, "prices.json"), {})
    props = book.get("PROPS", {})
    sched = {}
    try:
        import re as _re
        import sys as _sys
        _sys.path.insert(0, os.path.join(D, "build"))
        import pagefile as _pf
        for r in json.loads(_re.search(r"var SCHED = (\[\[.*?\]\]);", _pf.read(), _re.S).group(1)):
            sched[str(r[1])] = r
    except Exception:
        pass
    for club, g in groups.items():
        gid = (qbs.get(g["id"]) or {}).get("nx", {}).get("gid")
        r = sched.get(str(gid))
        ptd = (props.get(str(gid)) or {}).get("ptd") or []
        if r and len(ptd) == 2:
            s0 = 0 if r[3] == club else 1 if r[4] == club else -1
            rungs = ptd[s0] if s0 >= 0 else []
            g["px"] = [(x[0] if x else "") for x in rungs[:2]]
    players = []
    for g in groups.values():
        if not g["nx"]:
            continue
        g["facts"].sort(key=lambda f: ORDER.get(f["k"], 9))
        players.append(g)
    players.sort(key=lambda g: (g["nx"]["d"], g["t"]))
    json.dump({"at": STAMP, "players": players, "cards": cards}, open(OUT, "w"), separators=(",", ":"))
    json.dump(seen, open(SEEN, "w"), indent=0, sort_keys=True)
    json.dump(starters, open(STARTERS, "w"), indent=0, sort_keys=True)
    json.dump(people, open(PEOPLE, "w"), indent=0, sort_keys=True)
    kinds = {}
    for c in cards:
        kinds[c["k"]] = kinds.get(c["k"], 0) + 1
    print("qbwire: %d cards %s" % (len(cards), kinds))


if __name__ == "__main__":
    main()
