"""Settles a game the minute it ends, not hours later.

   Nothing watched a game while it was being played. The board asked ESPN
   about it three and a half hours after kickoff, and again at five and a
   half if the first ask found it still going -- so a Thursday night game
   read FINAL on the page, where the browser's own refresh had seen it, and
   not in our own record until the small hours. College is worse: those
   games routinely run past three and a half hours (Jose, Sep 22, 2026: "why
   the fuck are we asking again 3 1/2 and 5 1/2 ... we get the final notice
   from espn").

   ESPN has no way to tell us a game is over, so this asks. It sleeps until
   the next kickoff, then asks the scoreboard every thirty seconds while
   anything is being played, settles each game the moment it reads final,
   deploys, and goes back to sleep. One call covers every game at once, so
   ten kickoffs at one o'clock cost the same as one.

   A game that is settled is never asked about again -- settle.py keeps the
   file and skips what it already holds.

       python3 build/watch.py              sleep, wake, settle, sleep
       python3 build/watch.py --once       one pass, then stop
       python3 build/watch.py --dry        say what it would do
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
ONCE = "--once" in sys.argv
DRY = "--dry" in sys.argv
BEAT = 30                      # seconds between asks while a game is being played
# a fight is not a game: it can end on any second, and the next bout begins the
# moment the last one does. While a card is running the beat is ten seconds,
# and one call covers every bout on it (Jose, Sep 22, 2026: "a knockout is
# gonna happen any second")
BEAT_MMA = 10
# DraftKings moves each bout's start as the card runs -- a string of knockouts
# pulls the main event forward by an hour and their clock follows it. Their
# TIMES are re-read this often while a card is live, and nothing else: the
# prices were taken once and the ones that are missing are chased on the
# sweep, the same rule the football's hundred and twenty-eight follow
# (Jose, Sep 22, 2026: "we aren't looking for odds, we are looking for a
# time").
DK_EVERY = 5 * 60
IDLE = 15 * 60                 # longest we ever sleep, so a redrawn week is noticed
LATE = dt.timedelta(hours=7)   # after this a game is somebody else's problem
BOARD = {"SCHED": "nfl", "CFB": "college-football"}
SCORE = ("https://site.api.espn.com/apis/site/v2/sports/football/%s/scoreboard"
         "?dates=%s&limit=400")
# a card is a night: the prelims start the clock and the main event lands five
# or six hours later, so a bout is watched from its own bell rather than the
# card's, and the card is settled as a whole once ESPN calls the event over
MMA = ("https://site.web.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard"
       "?dates=%s")
LATE_MMA = dt.timedelta(hours=10)
DK_LAST = 0.0


def say(line):
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    print("%s %s" % (stamp, line), flush=True)


def drawn():
    """Every football game on the board: (league, espn id, kickoff)."""
    s = pagefile.read()
    out = []
    for var, lg in BOARD.items():
        m = re.search(r"var %s = (\[\[.*?\]\]);" % var, s, re.S)
        if not m:
            continue
        for g in json.loads(m.group(1)):
            try:
                kick = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            except ValueError:
                continue
            out.append((lg, str(g[1]), kick))
    return out


def settled(eid):
    return os.path.exists(os.path.join(D, "site", "final", "%s.json" % eid))


def bouts():
    """Every bout on the board: (event id, bout id, first bell). The settled
       file is the event's, not the bout's -- mma_year.py writes one for the
       whole card."""
    s = pagefile.read()
    m = re.search(r"var FIGHTS = (\[\[.*?\]\]);", s, re.S)
    out = []
    for g in json.loads(m.group(1)) if m else []:
        try:
            bell = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        except ValueError:
            continue
        out.append((str(g[0]), str(g[1]), bell))
    return out


def cards_running(now):
    """The fight cards with a bout under way and no settled file yet."""
    live = {}
    for eid, bid, bell in bouts():
        if bell > now or now - bell > LATE_MMA:
            continue
        if settled("mma-" + eid):
            continue
        live.setdefault(eid, bell)
    return live


def mma_over(days):
    """Which UFC events ESPN calls finished right now."""
    done = set()
    for day in days:
        try:
            r = rq.get(MMA % day, impersonate="chrome", timeout=25)
            if r.status_code != 200:
                continue
            for e in (r.json() or {}).get("events") or []:
                st = (((e.get("status") or {}).get("type")) or {})
                if st.get("state") == "post" or st.get("completed"):
                    done.add(str(e.get("id")))
        except Exception as e:
            say("   mma scoreboard did not answer: %s" % e)
    return done


def playing(now, games):
    """The games that have kicked off, are not settled, and are not so old
       that nothing is coming."""
    return [g for g in games
            if g[2] <= now and now - g[2] < LATE and not settled(g[1])]


def finals(league, days):
    """Which of ESPN's games read final right now. One call per league per
       day, however many games are on."""
    done = set()
    for day in days:
        try:
            r = rq.get(SCORE % (league, day), impersonate="chrome", timeout=25)
            if r.status_code != 200:
                continue
            for e in (r.json() or {}).get("events") or []:
                st = (((e.get("status") or {}).get("type")) or {})
                if st.get("state") == "post" or st.get("completed"):
                    done.add(str(e.get("id")))
        except Exception as e:
            say("   %s scoreboard did not answer: %s" % (league, e))
    return done


def run(job, args=()):
    r = subprocess.run([sys.executable, os.path.join(D, "build", job)] + list(args),
                       capture_output=True, text=True, timeout=600)
    for line in (r.stdout + r.stderr).strip().splitlines():
        say("   %s: %s" % (job[:-3], line))
    return r.returncode == 0


def deploy():
    out = subprocess.run(
        ["npx", "wrangler", "pages", "deploy", ".",
         "--project-name=the-arenasports", "--branch=main"],
        cwd=os.path.join(D, "site"), capture_output=True, text=True, timeout=600)
    say("   deployed" if out.returncode == 0
        else "   DEPLOY FAILED " + (out.stderr or "")[-200:])


def pass_once():
    """Ask once. Returns how long to sleep before asking again."""
    now = dt.datetime.now(dt.timezone.utc)
    games = drawn()
    live = playing(now, games)
    cards = cards_running(now)

    if cards:
        days = sorted({b.strftime("%Y%m%d") for b in cards.values()} |
                      {(b - dt.timedelta(days=1)).strftime("%Y%m%d") for b in cards.values()})
        over = [e for e in cards if e in mma_over(days)]
        say("cards under way: %d | ESPN says over: %d" % (len(cards), len(over)))
        # their clock, every five minutes, so the bell we are waiting on is the
        # one the book is actually working to
        global DK_LAST
        if not DRY and time.time() - DK_LAST > DK_EVERY:
            DK_LAST = time.time()
            run("fill_fights.py", ["--times"])
        if over and not DRY:
            say("settling the card: " + ", ".join(over))
            run("mma_year.py")
            run("records_mma.py")
            deploy()

    if not live and not cards:
        ahead = [g[2] for g in games if g[2] > now]
        ahead += [b for _, _, b in bouts() if b > now]
        if not ahead:
            return IDLE
        wait = (min(ahead) - now).total_seconds()
        return max(BEAT, min(wait, IDLE))
    if not live:
        return BEAT_MMA

    days = sorted({g[2].strftime("%Y%m%d") for g in live} |
                  {(g[2] - dt.timedelta(days=1)).strftime("%Y%m%d") for g in live})
    over = []
    for lg in sorted({g[0] for g in live}):
        done = finals(lg, days)
        over += [g for g in live if g[0] == lg and g[1] in done]

    say("being played: %d | ESPN says over: %d" % (len(live), len(over)))
    if not over:
        return BEAT
    say("settling: " + ", ".join(g[1] for g in over))
    if DRY:
        return BEAT
    # settle.py writes every finished game it does not already hold, so it
    # needs no list: it will pick these up and nothing else
    run("settle.py")
    run("ledger.py")
    deploy()
    return BEAT


def main():
    say("watching. %d games on the board" % len(drawn()))
    while True:
        try:
            nap = pass_once()
        except Exception as e:
            say("pass failed, sleeping a minute: %s" % e)
            nap = 60
        if ONCE:
            return 0
        time.sleep(nap)


if __name__ == "__main__":
    sys.exit(main())
