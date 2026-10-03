"""Whether a college team is one Jose cares about, for the phone alerts.

   A college alert -- a new starter, a passer with no odds -- goes to his phone
   only for a team he has starred in the college search, or a game he has
   something on: a pick on the slip, a tracked bet, a gold price on the board
   (Jose, Oct 3, 2026: "why am I getting notifications about this? Is this a
   game that I'm tracking, have starred, or even care about?"). NFL teams are
   always cared about.

   The marks are read once from the site's store, with the board's own key.
"""
import datetime as dt
import json
import os
import re
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile

HOST = "https://the-arenasports.pages.dev"
KEY = "arena-001bff8ddf784985"
_MARKS = None


def _get(path):
    try:
        from curl_cffi import requests as rq
        r = rq.get(HOST + path, timeout=20)
        return r.json() if r.status_code == 200 else {}
    except Exception:
        try:
            import urllib.request
            return json.loads(urllib.request.urlopen(HOST + path, timeout=20).read().decode())
        except Exception:
            return {}


def marks():
    global _MARKS
    if _MARKS is None:
        st = _get("/state?k=" + KEY) or {}
        bets = _get("/bets?k=" + KEY) or {}
        _MARKS = {"stars": st.get("stars") or {}, "picks": st.get("picks") or {},
                  "placed": st.get("placed") or {}, "sent": bets.get("sent") or [],
                  "bets": bets.get("bets") or [], "ok": bool(st)}
    return _MARKS


def _rows(var):
    m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, pagefile.read(), re.S)
    return json.loads(m.group(1)) if m else []


def _oids(gid):
    """Every DraftKings selection id the board holds for one game."""
    try:
        book = json.load(open(os.path.join(D, "site", "prices.json")))
    except (OSError, ValueError):
        return set()
    found = set()
    def walk(x):
        if isinstance(x, list):
            for v in x:
                if isinstance(v, str) and len(v) > 8:
                    found.add(v)
                else:
                    walk(v)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
    for shelf in book.values():
        if isinstance(shelf, dict) and gid in shelf:
            walk(shelf[gid])
    return found


def cares(team):
    """True for an NFL club, a starred college team, or a college team whose
       game this week holds one of his picks, bets or gold marks. If the store
       cannot be read, it says True: an alert too many beats a missed one."""
    now = dt.datetime.now(dt.timezone.utc)
    if any(team in (g[3], g[4]) for g in _rows("SCHED")):
        if not any(team in (g[3], g[4]) for g in _rows("CFB")):
            return True
    m = marks()
    if not m["ok"]:
        return True
    if m["stars"].get("cfb:" + team):
        return True
    soon = [str(g[1]) for g in _rows("CFB") if team in (g[3], g[4])
            and -6 < (dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")) - now).total_seconds() / 86400 < 8]
    for gid in soon:
        if any(str((v or {}).get("g", "")) == gid for v in m["picks"].values() if isinstance(v, dict)):
            return True
        for b in m["sent"] + m["bets"]:
            if any(str(l.get("g", "")) == gid for l in b.get("legs", [])):
                return True
        ids = _oids(gid)
        if any(k in ids for k, v in m["placed"].items() if v):
            return True
    return False
