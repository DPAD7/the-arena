"""DraftKings' own live game state, handed to the clock every few seconds.

   ESPN's game page ran two and a half minutes behind DraftKings' tracker on
   Oct 17, 2026 (NW at MSU: DraftKings 1:03 left, ESPN 3:29), and an alert
   read off ESPN said "OSU in the red zone" after the drive was over (Jose:
   "we're a full 30 seconds behind... DraftKings has a timer right?").
   DraftKings answers only a Chrome-shaped handshake, which neither the site
   nor the clock can make, so this runs on GitHub (.github/workflows/dklive.yml),
   started by the clock when football is on, and reads DraftKings' league
   lists -- one request a league -- every few seconds. Each game whose score,
   clock, down or ball moved is posted to /push {dklive}, signed, and the
   clock uses it for the alerts and sends it to any open page.

   It stops on its own when nothing is on or due inside half an hour, or
   before GitHub's six-hour limit; the clock starts it again if needed.

       python3 build/dk_live.py            run
       python3 build/dk_live.py --once     one read, printed
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
from read_dk import ask
from slip_track import Board
import dk_kicks

SITE = "https://the-arenasports.pages.dev/push"
LEAGUES = {"nfl": 88808, "ncaaf": 87637}
EVERY = 3            # seconds between reads
QUIET = 30 * 60      # nothing on or due this long: stop
LIMIT = 5.6 * 3600   # GitHub stops a job at six hours
ONCE = "--once" in sys.argv
ORD = {"1": "1st", "2": "2nd", "3": "3rd", "4": "4th"}


def period(p):
    p = str(p or "")
    for k, v in (("1st", "1st"), ("2nd", "2nd"), ("3rd", "3rd"), ("4th", "4th"), ("overtime", "OT"), ("half", "Half")):
        if k in p.lower():
            return v
    return p


def state_of(board, e):
    """One DraftKings event as the clock reads a game, keyed by ESPN's id."""
    if (e.get("status") or "") not in ("STARTED", "SUSPENDED"):
        return None, None
    by_role = {(p.get("venueRole") or "").lower(): p for p in e.get("participants") or []}
    away, home = by_role.get("away"), by_role.get("home")
    if not away or not home:
        return None, None
    ca, ch = board.clubs(away.get("name")), board.clubs(home.get("name"))
    best = None
    for g, lg in board.rows:
        if g[3] in ca and g[4] in ch:
            k = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            gap = abs((dt.datetime.now(dt.timezone.utc) - k).total_seconds())
            if gap < 8 * 3600 and (best is None or gap < best[0]):
                best = (gap, g)
    if not best:
        return None, None
    g = best[1]
    sc = (e.get("eventScorecard") or {}).get("mainScorecard") or {}
    first = sorted(e.get("participants") or [], key=lambda p: p.get("sortOrder") or 0)[0]
    a, b = int(sc.get("firstTeamScore") or 0), int(sc.get("secondTeamScore") or 0)
    score = [a, b] if first is away else [b, a]
    live = e.get("liveGameState") or {}
    secs = live.get("gameTime")
    per = period(live.get("period"))
    clock = ("%d:%02d - %s" % (secs // 60, secs % 60, per)) if isinstance(secs, int) and per not in ("Half",) else per
    ld = sc.get("liveScoreData") or {}
    short = ld.get("shortName") or ""
    poss = ""
    for p, ab in ((away, g[3]), (home, g[4])):
        if short and ((p.get("metadata") or {}).get("shortName") or "") == short:
            poss = ab
    down, togo, yl = ld.get("americanFootballCurrentDown"), ld.get("americanFootballYardsToGo"), ld.get("americanFootballYardLine")
    try:
        to_goal = int(yl)
    except (TypeError, ValueError):
        to_goal = None
    out = {"sc": score, "clock": clock, "poss": poss,
           "down": ("%s & %s" % (ORD.get(str(down), str(down)), togo)) if down and togo else "",
           "toGoal": to_goal, "rz": bool(poss and to_goal is not None and 0 < to_goal <= 20),
           "running": bool(live.get("isClockRunning"))}
    return str(g[1]), out


def due_soon(board):
    now = dt.datetime.now(dt.timezone.utc)
    for g, lg in board.rows:
        k = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        if -5 * 3600 < (now - k).total_seconds() < QUIET:
            return True
    return False


def main():
    board = Board()
    secret = os.environ.get("ASK_SECRET", "")
    sent, t0, quiet_since, gone = {}, time.time(), None, {}
    kicks, kicked_at, said_at, crawled_at = {}, 0, {}, 0
    while time.time() - t0 < LIMIT:
        moved, on, seen = {}, False, set()
        for lg, lid in LEAGUES.items():
            d = ask(None, None, "/sportscontent/dkusmd/v1/leagues/%d" % lid) or {}
            for e in d.get("events") or []:
                gid, st = state_of(board, e)
                if not gid:
                    continue
                on = True
                seen.add(gid)
                # a game that sits still (a timeout, a review) is said again
                # every half minute, so nobody takes its quiet for a lost line
                if sent.get(gid) != st or time.time() - said_at.get(gid, 0) > 30:
                    moved[gid] = st
                    said_at[gid] = time.time()
        # a finished game leaves DraftKings' list instead of saying final: gone
        # for two reads out of the 4th or overtime, it is over, with the score
        # it left on (Jose, Oct 17, 2026: "why do I still see time on the clock")
        for gid, st in list(sent.items()):
            if gid in seen or st.get("final"):
                gone.pop(gid, None)
                continue
            gone[gid] = gone.get(gid, 0) + 1
            if gone[gid] >= 2 and re.search(r"4th|OT", st.get("clock") or ""):
                moved[gid] = dict(st, final=True, clock="Final", rz=False, down="", running=False)
        # every minute, DraftKings' start for every game and bout: a game that
        # kicks off late keeps its prices until it is really on (dk_kicks.py)
        new_kicks = {}
        if time.time() - kicked_at > 60:
            kicked_at = time.time()
            try:
                now_k = dk_kicks.football(board)
                now_k.update(dk_kicks.bouts(board))
                new_kicks = {k: v for k, v in now_k.items() if kicks.get(k) != v}
                kicks.update(new_kicks)
            except Exception as ex:
                print("kicks failed:", ex)
        # every ten minutes while games are on: the board read as his phone
        # reads it, against every rule (crawl.py) -- a fault reaches his phone
        if time.time() - crawled_at > 600 and on:
            crawled_at = time.time()
            try:
                subprocess.run([sys.executable, os.path.join(D, "build", "crawl.py"), "--alert"], timeout=240)
            except Exception as ex:
                print("crawl failed:", ex)
        if ONCE:
            print(json.dumps(moved, indent=1))
            return
        if moved or new_kicks:
            try:
                rq.post(SITE, json={"dklive": {"at": int(time.time() * 1000), "games": moved, "kicks": new_kicks}},
                        headers={"x-ask-secret": secret}, impersonate="chrome", timeout=10)
                sent.update(moved)
            except Exception as ex:
                print("post failed:", ex)
        if on or due_soon(board):
            quiet_since = None
        else:
            quiet_since = quiet_since or time.time()
            if time.time() - quiet_since > QUIET:
                print("nothing on: done")
                return
        time.sleep(EVERY)


if __name__ == "__main__":
    main()
