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
        if not m or not v.get("status"):
            continue
        note = v.get("note") or ""
        if note.strip().lower() == str(v["status"]).lower():
            note = ""
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

    for c in cards:
        seen.setdefault(c["key"], c["at"])
    cards.sort(key=lambda c: c["at"], reverse=True)
    json.dump({"at": STAMP, "cards": cards}, open(OUT, "w"), separators=(",", ":"))
    json.dump(seen, open(SEEN, "w"), indent=0, sort_keys=True)
    json.dump(starters, open(STARTERS, "w"), indent=0, sort_keys=True)
    json.dump(people, open(PEOPLE, "w"), indent=0, sort_keys=True)
    kinds = {}
    for c in cards:
        kinds[c["k"]] = kinds.get(c["k"], 0) + 1
    print("qbwire: %d cards %s" % (len(cards), kinds))


if __name__ == "__main__":
    main()
