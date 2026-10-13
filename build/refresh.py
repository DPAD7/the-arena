"""The board's sweep: decide what this moment is for, run those jobs, deploy once.

   The site's clock (clock/clock.js) starts sweep.yml at the moments that
   matter and names them in the workflow's "moments" input; they reach this
   script as --moments "<key>,<key>" and are served as given, whatever this
   run's own clock says -- a run queued behind another used to find nothing
   due and drop the work (Oct 12, 2026). The keys are the clock's own:

     sweep@<YYYY-MM-DD> <h>        a daily sweep: every job (FULL)
     pre@<id>@<120|60|30>          before a kickoff or first bell: the reads
                                   that must be fresh (PREGAME)
     report@<YYYY-MM-DD> <mins>    the NFL injury-report window: watch_news.py
     live@<id>@<ms>                a card or a game being played
     final@<id>, dayend@<date>     a game over, the day's last final

   With no moments given, --if-due decides for itself the way it always did:
   the sweep hours, 120/60/30 minutes before each start, the report window,
   and a card or game running. Anything else and it exits having asked
   nobody anything.

       python3 build/refresh.py --if-due [--moments "k1,k2"]
       python3 build/refresh.py --day-end          one full pass
       python3 build/refresh.py --if-due --check   exit 0 when something is
                                                   due, 78 when not; writes
                                                   nothing (sweep.yml asks this
                                                   before installing anything)
       ... --plan    say which jobs would run, run none of them
       ... --dry     run the jobs with --dry, write and deploy nothing

   The jobs only write (ARENA_NO_DEPLOY=1); this deploys once at the end of
   the run, and only when site/ or src/ changed (Oct 12, 2026).
"""
import datetime
import hashlib
import json
import urllib.request
import os
import re
import signal
import subprocess
import sys

# A run that never ends blocks every run after it: launchd will not start a
# second copy while one is alive, so one stuck process silently swallowed the
# 10:00, 11:00 and 11:30 pulls on Sep 12. Nothing here may outlive its own
# interval.
# On GitHub the job's own limit is twenty minutes and a later run queues
# behind this one, so the old nine minutes, set for launchd's ten, only cut
# full passes off mid-way: the 9 AM sweep of Oct 1, 2026 stopped in
# fill_fights at 540 seconds with the commit and deploy still to come.
BUDGET = 900          # fifteen minutes, inside the job's twenty


def _out_of_time(_sig, _frame):
    sys.stderr.write("refresh.py passed its %ds budget; stopping so the next "
                     "wake is not blocked\n" % BUDGET)
    # what the run wrote so far still goes out: the jobs no longer deploy on
    # their own, so stopping here without it would leave the site a pass
    # behind (Oct 12, 2026)
    try:
        signal.alarm(0)
        deploy_if_changed(timeout=150)
    except Exception:
        pass
    os._exit(2)


signal.signal(signal.SIGALRM, _out_of_time)
signal.alarm(BUDGET)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = "--plan" in sys.argv
CHECK = "--check" in sys.argv
DRY = "--dry" in sys.argv or PLAN or CHECK
# ODDS_NOW pretends it is another moment, so the wake windows can be tested
# without waiting for one to come round.
NOW = (datetime.datetime.fromisoformat(os.environ["ODDS_NOW"])
       if os.environ.get("ODDS_NOW")
       else datetime.datetime.now(datetime.timezone.utc))
# every job this runs only writes; the deploy is this script's, once
CHILD = dict(os.environ, ARENA_NO_DEPLOY="1")


def log(line):
    if CHECK:
        return
    stamp = NOW.astimezone().strftime("%m/%d %H:%M")
    print(line)
    if not DRY:
        os.makedirs(D + "/logs", exist_ok=True)
        with open(D + "/logs/refresh.log", "a") as f:
            f.write("%s  %s\n" % (stamp, line))


# ------------------------------------------------------- running a job -----
# each job runs once a pass: starters ran three times, news, wire and depth
# twice, played_qb twice (Oct 12, 2026). again=True is for the one job that
# has to read what a later one wrote (qb_clips after the clip builders).
RAN = []


def run(job, args=(), tail=None, again=False, cwd=None, dry=True, timeout=None):
    if job in RAN and not again:
        return []
    RAN.append(job)
    name = job[:-3] + ("" if not args else " " + " ".join(args))
    if PLAN:
        log("   would run %s" % name)
        return []
    if not os.path.exists(D + "/build/" + job):
        log("   %s: not here, skipped" % job[:-3])
        return []
    try:
        r = subprocess.run([sys.executable, D + "/build/" + job] + list(args) + (["--dry"] if DRY and dry else []),
                           capture_output=True, text=True, cwd=cwd or D, env=CHILD, timeout=timeout)
    except Exception as e:
        log("   %s: did not run (%s)" % (name, type(e).__name__))
        return []
    out = (r.stdout + r.stderr).strip().splitlines()
    for line in (out if tail is None else out[-tail:]):
        log("   %s: %s" % (name, line))
    return out


# ------------------------------------------------------------ the deploy ---
def fingerprint():
    """What site/ and src/ hold now, as git sees it: every changed or new
       file, by its content. index.html and build.txt are left out -- they are
       built from the rest at deploy time."""
    try:
        st = subprocess.run(["git", "status", "--porcelain", "-uall", "--", "site", "src"],
                            capture_output=True, text=True, cwd=D, timeout=60).stdout
    except Exception:
        return None
    h = hashlib.sha1()
    for line in sorted(st.splitlines()):
        path = line[3:].split(" -> ")[-1].strip('"')
        if path in ("site/index.html", "site/build.txt"):
            continue
        h.update(line.encode())
        try:
            with open(os.path.join(D, path), "rb") as f:
                h.update(hashlib.sha1(f.read()).digest())
        except OSError:
            pass
    return h.hexdigest()


START = None


OWED = D + "/data/deploy_owed.json"


def deploy_if_changed(timeout=300):
    """One deploy for the whole run, and none when nothing changed. A deploy
       that fails is written down (data/deploy_owed.json, committed with the
       run) and the next run deploys whether or not it changed anything, so
       what this run wrote still reaches the site."""
    if DRY:
        return True
    owed = os.path.exists(OWED)
    if START is not None and fingerprint() == START and not owed:
        log("deploy: nothing on the site changed, not deployed")
        return True
    pagefile.deployable(pagefile.read())
    for attempt in (1, 2):
        out = subprocess.run(["npx", "wrangler", "pages", "deploy", ".",
                              "--project-name=the-arenasports", "--branch=main"],
                             cwd=D + "/site", capture_output=True, text=True, timeout=timeout)
        if out.returncode == 0:
            log("deployed")
            if owed:
                os.remove(OWED)
            return True
        log("DEPLOY FAILED (try %d): %s" % (attempt, (out.stderr or "")[-200:]))
    json.dump({"at": NOW.isoformat()}, open(OWED, "w"))
    return False


BEFORE = (120, 60, 30)     # minutes before a kickoff that a price is worth reading
SLOT = 11                  # the clock's wake lands inside a window a shade over ten
# DraftKings posts a game's passing props days after its moneyline, with no
# notice. These are the hours (Eastern) the drawn weeks are swept for anything
# newly posted, on top of the kickoff wakes above. Jose asked for this on
# Sep 15, 2026 after telling us by hand, again, that the props were up.
# Three a day now, not five: the noon and six o'clock sweeps asked nobody for
# a price -- fill_week.py sat them out -- and the kickoff wakes already stand
# in front of every game, so they were the rest of the list read again for
# nothing (Jose, Sep 23, 2026: "five sweeps is overkill").
SWEEP_ET = (9, 15, 21)
# the rankings, once a day, on the nine o'clock sweep: the AP poll for the
# college cards, then the UFC's own table and the flattened copy a bout card
# reads its number from. A vote moves once a week, so asking more often only
# asks. Left hand-run, nothing on the schedule had ever refreshed them
# (Jose, Sep 23, 2026: "put the rankings on the schedule, once a day").
RANKS_ET = (9, 15)   # the AP poll is out Sunday afternoon; 9 AM alone left it a day behind (Sep 27, 2026)
RANK_JOBS = ("cfb_rank.py", "ufc_rankings.py", "fighter_ranks.py")
HORIZON_DAYS = 8           # the same reach fill_week.py and fill_fights.py price
# (the hub readers at 10 ET are gone: they wrote only to data/qbspy.db, which
# the run throws away, and nothing read them -- Oct 12, 2026. So is the daily
# DraftKings login touch: the DK read was retired.)


def board_events():
    """Every drawn game and bout on the page still to come inside the horizon,
       shaped like the hand-built events so due_now() can read them."""
    page = pagefile.read()
    out = []
    for var in ("SCHED", "CFB", "FIGHTS"):
        m = re.search(r"var %s = (\[\[.*?\]\]);" % var, page, re.S)
        if not m:
            continue
        for g in json.loads(m.group(1)):
            kick = datetime.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            # the games in front of us, and the ones just played: an after-the-
            # whistle wake is looking backwards, and a list of kickoffs still to
            # come has nothing in it for a game that finished an hour ago
            # (Jose, Sep 18, 2026)
            if not (NOW - datetime.timedelta(hours=12) < kick
                    <= NOW + datetime.timedelta(days=HORIZON_DAYS)):
                continue
            name = (g[3] + " v " + g[5]) if var == "FIGHTS" else (g[3] + " @ " + g[4])
            out.append({"id": var + ":" + str(g[1]), "start": g[2], "name": name})
    return out


def tell(key, title, body):
    """A notification on his phone, through the clock (the watcher's route)."""
    try:
        import triage
        triage.alert(key, title, body)
    except Exception as e:
        log("   alert not sent (%s)" % type(e).__name__)


BLOWOUT = -1000            # a favorite this heavy: DraftKings often skips the game's props


def hidden_games():
    """The games he has hidden on the board, by ESPN id, from the site's store."""
    try:
        from curl_cffi import requests as rq
        k = re.search(r"ARENAOWN\s*=\s*[\"']([^\"']+)", pagefile.read())
        r = rq.get(SITE_STATE + (("?k=" + k.group(1)) if k else ""), impersonate="chrome", timeout=30)
        return set(str(x) for x in ((r.json() or {}).get("hidden") or {}))
    except Exception:
        return set()


SITE_STATE = "https://the-arenasports.pages.dev/state"


MISS_LIMIT = 5             # price passes a side can come up empty before he hears
MISS_HOURS = 48            # only games this close are counted


def count_misses():
    """College only. Every price pass, a college game inside MISS_HOURS where
       DraftKings prices one passer and not the other is counted for the empty
       side; a side priced again is forgotten. Left out: the NFL (its chart
       names the starter, and a missing price there is only the book being
       late), a game with neither side priced (the book has not posted it or
       skips it), a favorite of BLOWOUT or heavier, and any game he has
       hidden. On the fifth empty pass the sides that reached it go to his
       phone in one alert: the passer DraftKings lists instead, or no passing
       props listed (Jose, Sep 30, 2026: "not ... 1000 notifications about all
       the quarterbacks that are on Saturday").
    """
    f = D + "/data/price_misses.json"
    try:
        miss = json.load(open(f))
    except (OSError, ValueError):
        miss = {}
    try:
        dkq = json.load(open(D + "/data/dk_qbs.json"))
    except (OSError, ValueError):
        dkq = {}
    hid = hidden_games()
    page = pagefile.read()
    now_open, lines = {}, []
    m = re.search(r"  var CFB = (\[\[.*?\]\]);", page, re.S)
    for g in json.loads(m.group(1)) if m else []:
        try:
            kick = datetime.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        except (ValueError, AttributeError, IndexError):
            continue
        if not (NOW < kick <= NOW + datetime.timedelta(hours=MISS_HOURS)) or str(g[1]) in hid:
            continue
        try:
            held = json.load(open(D + "/site/prices/%s.json" % g[1]))
        except (OSError, ValueError):
            continue
        ptd = (held.get("props") or {}).get("ptd") or []
        priced = [len(ptd) > i and any(x for x in ptd[i]) for i in (0, 1)]
        if priced[0] == priced[1]:
            continue
        ml = held.get("ml") or []
        try:
            if min(int(str(ml[i]).replace("\u2212", "-")) for i in (0, 2) if len(ml) > i and ml[i]) <= BLOWOUT:
                continue
        except ValueError:
            pass
        side = priced.index(False)
        key = "%s:%d" % (g[1], side)
        was = miss.get(key) or {}
        n = int(was.get("n", 0)) + 1
        now_open[key] = {"n": n, "told": was.get("told", False)}
        if n >= MISS_LIMIT and not was.get("told"):
            club, man = g[3 + side], g[5 + side * 2] or "no passer"
            from cares import cares
            if not cares(club):
                now_open[key]["told"] = True
                continue
            book = [x[1] for x in ((dkq.get(str(g[1])) or [[], []])[side]) if len(x) > 1]
            lines.append("%s %s: DraftKings lists %s" % (club, man, ", ".join(book)) if book
                         else "%s %s: no passing props listed" % (club, man))
            now_open[key]["told"] = True
    if lines:
        tell("props@" + NOW.strftime("%Y-%m-%d %H"),
             "No passing odds: %d college passer%s" % (len(lines), "" if len(lines) == 1 else "s"),
             "; ".join(lines))
        for l in lines:
            log("   price misses told: " + l)
    if not DRY:
        json.dump(now_open, open(f, "w"), indent=1, sort_keys=True)
    log("   price misses: %d college sides counted" % len(now_open))


def ranks_due(seen):
    """The daily rankings read, if this is the hour for it."""
    from zoneinfo import ZoneInfo
    et = NOW.astimezone(ZoneInfo("America/New_York"))
    out = []
    for h in RANKS_ET:
        wake = et.replace(hour=h, minute=0, second=0, microsecond=0)
        key = "ranks@" + wake.strftime("%Y-%m-%d %H")
        late = (et - wake).total_seconds() / 60.0
        if key not in seen and 0 <= late < SLOT:
            out.append((key, "rankings %d:00 ET" % h, 0))
    return out


def read_ranks():
    """The three ranking jobs, in order. Each is a second of fetching, so they
       run in line rather than being let go of. One failing never stops the
       rest -- except that fighter_ranks.py only flattens what ufc_rankings.py
       just wrote, so it is held back when that read failed or came back with
       no divisions: flattening an empty table would wipe every number off
       the bout cards."""
    if PLAN:
        log("   would run %s" % ", ".join(j[:-3] for j in RANK_JOBS))
        return
    ufc_ok = False
    for job in RANK_JOBS:
        if job == "fighter_ranks.py" and not ufc_ok:
            log("   fighter_ranks: ufc_rankings did not read, the old numbers kept")
            continue
        try:
            r = subprocess.run([sys.executable, D + "/build/" + job],
                               capture_output=True, text=True, cwd=D, timeout=90)
        except Exception as e:
            log("   %s: did not run (%s)" % (job[:-3], type(e).__name__))
            continue
        for line in (r.stdout + r.stderr).strip().splitlines()[-3:]:
            log("   %s: %s" % (job[:-3], line))
        if job == "ufc_rankings.py" and r.returncode == 0:
            try:
                ufc_ok = bool(json.load(open(D + "/data/ufc_rankings.json")))
            except Exception:
                ufc_ok = False


# The NFL's practice report is due by 4 p.m. ET, or as soon as practice is
# over, on three set days before each game, and the last of them carries the
# game status (Out, Doubtful, Questionable) -- NFL Personnel (Injury) Report
# Policy. By kickoff weekday (Mon=0): the days whose report counts.
REPORT_DAYS = {6: (2, 3, 4), 0: (3, 4, 5), 3: (0, 1, 2), 4: (1, 2, 3), 5: (1, 2, 3), 2: (6, 0, 1)}
REPORT_FROM, REPORT_TO = (15, 30), (19, 0)     # ET: around the 4 p.m. deadline and late practices


def report_window(seen, mark=True):
    """Is this a half hour the NFL's injury report can have moved in? A report
       day for some game on the board, between 3:30 and 7 p.m. ET, once each
       half hour. Marks the half hour served when it is (and mark is True)."""
    from zoneinfo import ZoneInfo
    et = NOW.astimezone(ZoneInfo("America/New_York"))
    if not ((et.hour, et.minute) >= REPORT_FROM and (et.hour, et.minute) < REPORT_TO):
        return False
    try:
        s = pagefile.read()
        rows = json.loads(re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    except Exception:
        return False
    today = et.date()
    hit = False
    for g in rows:
        try:
            k = datetime.datetime.fromisoformat(g[2].replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York"))
        except ValueError:
            continue
        gap = (k.date() - today).days
        if 1 <= gap <= 4 and today.weekday() in REPORT_DAYS.get(k.weekday(), ()):
            hit = True
            break
    if not hit:
        return False
    key = "report@%s %02d:%02d" % (today.isoformat(), et.hour, 30 if et.minute >= 30 else 0)
    if key in seen:
        return False
    if mark:
        seen[key] = NOW.isoformat()
        json.dump(seen, open(D + "/data/served.json", "w"), indent=1)
    return True


def sweeps_due(seen):
    """The sweep hour this run is standing in for, if it is one."""
    from zoneinfo import ZoneInfo
    et = NOW.astimezone(ZoneInfo("America/New_York"))
    hit = []
    for h in SWEEP_ET:
        wake = et.replace(hour=h, minute=0, second=0, microsecond=0)
        key = "sweep@" + wake.strftime("%Y-%m-%d %H")
        late = (et - wake).total_seconds() / 60.0
        if key not in seen and 0 <= late < SLOT:
            hit.append((key, "sweep %d:00 ET" % h, 0))
    return hit


# ------------------------------------------------------------ the passes ---
# The three daily sweeps (and the day's close-out) run every job.
FULL = ("settle.py", "played_qb.py", "kicks.py", "news.py", "wire.py", "depth.py", "starters.py",
        "dk_sitemap.py", "dk_people.py", "ledger.py", "alt_ptd.py", "mma_year.py", "fill_week.py",
        "dk_promos.py", "cfb_ml.py", "keep_prices.py", "fill_fights.py", "boxing.py", "posters.py",
        "alerts.py", "lineups.py", "qbwire.py", "anim_rebuild.py", "guard.py", "qb_search.py",
        "qb_clips.py", "ask_fold.py", "networks.py", "birthdays.py", "faces.py", "mirror.py",
        "records_mma.py", "ufc_records.py", "bfo_odds.py", "h2h_week.py", "nfl_reads.py",
        "cfb_reads.py", "ufc_reads.py", "suggest.py", "log_reads.py", "covered.py")
# (out of the list, Oct 12, 2026: score_watch.py -- SCORE_WATCH is off on the
# page, so what it wrote was never drawn; ptd10.py -- it wrote only a picks
# note into the gitignored notes/, against the standing no-picks order)
# A 120/60/30-minute wake runs only what has to be fresh at the start: who
# is hurt and who starts, the prices, the lineups and the alerts, and the
# reads built on them -- not the other thirty jobs (Oct 12, 2026). Same
# order as FULL.
PREGAME = ("news.py", "wire.py", "depth.py", "starters.py", "dk_people.py", "fill_week.py",
           "fill_fights.py", "alerts.py", "lineups.py", "guard.py", "h2h_week.py", "nfl_reads.py",
           "cfb_reads.py", "ufc_reads.py", "suggest.py", "log_reads.py")
# after the whistle, the clips; the rest of what settle_late used to run is
# in FULL already, and runs once
CLIPS = ("settle.py", "played_qb.py", "starters.py", "ledger.py", "alt_ptd.py",
         "nfl_clips.py", "build_nflindex.py", "club_clips.py", "x_clips.py", "qb_clips.py")
CARD_DONE = ("mma_year.py", "bfo_odds.py", "ufc_records.py")


def price_drawn(jobs):
    """The drawn weeks: results first, then every game and bout still to come.
       The jobs write; the run deploys once at its end."""
    # keep_prices.py runs after fill_week.py: it copies what was just read
    # alt_ptd.py rides straight behind ledger.py: ledger.py writes ledger.json
    # from scratch each run, so the passing-touchdown ladder has to be put back
    # on right after or the money page silently loses it (Jose, Sep 17, 2026)
    # records_mma.py rides with faces.py: both ask ESPN about the men on the
    # board and write a file of our own for the page (Jose, Sep 19, 2026)
    # wire.py rides with them: who is hurt, by ESPN id, written to
    # site/wire.json so the ledger can put a plaster by his name -- the wire
    # outranks the record (Jose, Sep 21, 2026)
    # kicks.py goes early, because everything after it reads the clock: a
    # college week is drawn before its kickoffs are set, and the networks
    # pick them six to twelve days out. Until they do ESPN files the game
    # at 04:00Z, and left unread the board printed midnight as a real slot
    # -- thirty-three of week four's games under one heading. By the time
    # anybody looked the times were long since posted and nothing was
    # asking (Jose, Sep 22, 2026: "who in the fuck is playing at 12 am").
    # It never moves a game that has already started.
    # depth.py rides directly behind wire.py, which is the order the rule
    # needs: the chart names each club's starter and the wire can veto him.
    # Left hand-run it went seventeen days stale and the board drew Cooper
    # Rush for Atlanta while ESPN's chart said Michael Penix Jr. (Jose,
    # Sep 22, 2026: "fix the ledger for injuries and depth charts weekly")
    # and starters.py behind that, which is why these three moved to the front
    # of the list: it decides who each card draws, and both ledger.py and
    # fill_week.py build on that answer. Run after them, as they first were,
    # the ledger's own week is a preview of men who are not playing and the
    # prices under a swapped card are the other man's
    # (Jose, Sep 22, 2026: "a swap changes whose props we draw")
    # dk_sitemap.py runs ahead of it and does the same job the other way
    # round: DraftKings publishes a page for every NFL player it has ever
    # held, with the id written on the address, so a starter is pinned the
    # day his club is drawn instead of the night somebody prices him. Five
    # days out from week three that was the difference between eight of the
    # thirty-two and all thirty-two. College is not in that file, so college
    # still waits for a price.
    # dk_people.py runs before anything is priced, because everything after
    # it places a price by the number it writes down. DraftKings prices only
    # the men who are playing -- of the six quarterbacks on Atlanta's and
    # Green Bay's charts it prices the two starters and nobody else -- so a
    # backup has no id until the week he starts. That is the week this has
    # to run: Michael Penix Jr. was a backup until Tua went out, and a man
    # who is not pinned is not priced at all (Jose, Sep 22, 2026).
    # cfb_ml.py rides behind fill_week.py, which is the only order that
    # works: fill_week prices a college game while it is still to kick, and
    # cfb_ml fills what is left from ESPN's stored closing line -- never
    # over a price the board already holds. Left hand-run, a college
    # Saturday that passed before anybody looked kept its empty slots
    # for good (Jose, Sep 22, 2026: "is it wired so i dont have to tell you
    # again?").
    # covered.py is last and fetches nothing. It reads what the sweep has
    # just written and says, per league, how much of the week in front of
    # us has a kickoff, a starter, a price and a price on the men -- naming
    # what is missing rather than counting it. Every script above reports
    # its own success, which is how college week four came to draw midnight
    # for thirty-three games and the Dolphins' record on every college card
    # while every line of the log read fine (Jose, Sep 22, 2026: "wire it so
    # it runs and updates and we never have to ask again").
    # ask_fold.py rides behind the two pricers: whatever a double tap read
    # between sweeps is kept on the site, and this lays it into the price
    # files -- only where a slot is empty, never over a price the sweep just
    # read (Jose, Sep 23, 2026: double tap fetches the missing prices).
    for job in jobs:
        run(job)


def card_running():
    """A fight card under way: from half an hour before its first bell until
       three hours after the last one is due. While it runs, the book moves
       every bout that is left -- a knockout in the first pulls the rest of the
       night forward -- so the prices and the clock are read on every pass
       rather than on the wakes alone (Jose, Sep 18, 2026)."""
    page = pagefile.read()
    m = re.search(r"var FIGHTS = (\[\[.*?\]\]);", page, re.S)
    if not m:
        return None
    kicks = {}
    pf = D + "/site/prices.json"
    if os.path.exists(pf):
        try:
            kicks = (json.load(open(pf)).get("KICKS") or {})
        except Exception:
            kicks = {}
    cards = {}
    for f in json.loads(m.group(1)):
        when = kicks.get(str(f[1])) or f[2]
        try:
            t = datetime.datetime.fromisoformat(when.replace("Z", "+00:00"))
        except Exception:
            continue
        lo, hi = cards.get(f[0], (t, t))
        cards[f[0]] = (min(lo, t), max(hi, t))
    for eid, (first, last) in cards.items():
        if first - datetime.timedelta(minutes=30) <= NOW <= last + datetime.timedelta(hours=3):
            return eid
    return None


def boxing_running():
    """A Zuffa card under way: first bell 30 minutes ago to 8 hours after it."""
    page = pagefile.read()
    m = re.search(r"var BOXFIGHTS = (\[.*?\]);\n", page, re.S)
    if not m:
        return None
    for f in json.loads(m.group(1)):
        try:
            t = datetime.datetime.fromisoformat(f[2].replace("Z", "+00:00"))
        except Exception:
            continue
        if t - datetime.timedelta(minutes=30) <= NOW <= t + datetime.timedelta(hours=8):
            return f[0]
    return None


def game_running():
    """A football game under way: kicked off and less than five hours old.
       While one is on, every pass reads its box score for who is actually
       throwing, so a card that named the wrong man is right within ten
       minutes of the snap rather than hours after the whistle
       (Jose, Sep 25, 2026: "we need 100% accurate qbs")."""
    page = pagefile.read()
    for var in ("SCHED", "CFB"):
        m = re.search(r"var %s = (\[\[.*?\]\]);" % var, page, re.S)
        if not m:
            continue
        for g in json.loads(m.group(1)):
            try:
                t = datetime.datetime.fromisoformat(str(g[2]).replace("Z", "+00:00"))
            except Exception:
                continue
            if t <= NOW <= t + datetime.timedelta(hours=5) and \
                    not os.path.exists(D + "/site/final/%s.json" % g[1]):
                return g[1]
    return None


def unsettled():
    """Games and bouts ESPN calls final that we have written no result for.

       The wakes behind a game were a clock: three and a half hours after
       kickoff, then five and a half. A clock does not know anything. Six
       games on Sep 20, 2026 were final for the best part of an hour with no
       result, no ladder and no money page, because the clock had not come
       round yet (Jose: "it's not computing the final scores -- and fix it so
       I don't have to tell you"). This asks instead. One scoreboard read a
       sweep, and if anything is over that we have not written down, the
       settling runs whatever the clock says."""
    want = []
    for lg, path in (("nfl", "football/nfl"),
                     ("college-football", "football/college-football"),
                     ("mma", "mma/ufc")):
        # curl_cffi, like every other reader here: this Mac's own Python
        # cannot open an https socket, so urllib answers nothing at all
        try:
            from curl_cffi import requests as rq
            u = "https://site.api.espn.com/apis/site/v2/sports/" + path + "/scoreboard"
            d = rq.get(u, impersonate="chrome124", timeout=30).json()
        except Exception as e:
            log("unsettled: %s did not answer (%s)" % (lg, type(e).__name__))
            continue
        for e in d.get("events") or []:
            for c in (e.get("competitions") or [{}]):
                st = ((c.get("status") or {}).get("type") or {})
                if st.get("state") != "post":
                    continue
                gid = str(c.get("id") or e.get("id"))
                name = "mma-" + str(e.get("id")) if lg == "mma" else gid
                if not os.path.exists(D + "/site/final/%s.json" % name):
                    want.append((lg, gid, e.get("shortName") or e.get("name") or gid))
                if lg == "mma":
                    break
    return want


def due_now(events):
    """The wakes this run is standing in for, or an empty list. A wake already
       served is not served twice, which is what served.json remembers."""
    seen = {}
    f = D + "/data/served.json"
    if os.path.exists(f):
        try:
            seen = json.load(open(f))
        except Exception:
            seen = {}
    hit = []
    for e in events:
        if not e["start"]:
            continue
        kick = datetime.datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
        for mins in BEFORE:
            wake = kick - datetime.timedelta(minutes=mins)
            key = "%s@%d" % (e["id"], mins)
            if key in seen:
                continue
            late = (NOW - wake).total_seconds() / 60.0
            if 0 <= late < SLOT:
                hit.append((key, e["name"], mins))
    return hit, seen


def open_pass(before):
    """Straight after a price pass: starters.py ran ahead of the book in it, so
       a passer DraftKings has just posted is put on his card now and read for
       his prices, not at the next sweep. Each swap is told to his phone
       (Jose, Sep 30, 2026: Tulsa kept last week's man with no prices while
       DraftKings priced Baylor Hayes). starters.py runs a second time only
       when this pass's book read (data/dk_qbs.json) changed -- the one case
       this is for (Oct 12, 2026)."""
    if _dkq() == before:
        log("   open pass: the book named no new passer this pass")
        return
    said = run("starters.py", tail=4, again=True)
    swaps = [l for l in said if "(DraftKings)" in l]
    if swaps:
        run("suggest.py", tail=4, again=True)
        run("fill_week.py", tail=4, again=True)
        for l in swaps:
            m = re.match(r"\s*(\S+)\s+(.+?)\s+->\s+(.+?)\s+\(DraftKings\)", l)
            from cares import cares
            if m and not cares(m.group(1)):
                log("   swap not told (not starred, nothing on it): %s %s" % (m.group(1), m.group(3)))
            elif m:
                tell("swap@%s@%s" % (m.group(1), m.group(3)), "%s: %s starts" % (m.group(1), m.group(3)),
                     "DraftKings prices %s, not %s -- the card has him now." % (m.group(3), m.group(2)))


def settle_late(fight):
    """After the whistle: the result and the ladder, then the touchdown clips
       from the club sites, nfl.com and the clubs' posts. The clip builders are
       the slow ones, so they run here and nowhere else. A job the pass has
       already run is not run again; qb_clips is, so the clips just built are
       on Stacked (Sep 29, 2026).

       A card answers to mma_year.py instead, which writes the fought event to
       site/final/mma-{id}.json and takes ESPN's stored closing price for every
       bout the board still shows unpriced."""
    for job in (CARD_DONE if fight else CLIPS):
        run(job, tail=6, again=(job == "qb_clips.py" and "x_clips.py" in RAN))


def served():
    f = D + "/data/served.json"
    try:
        return json.load(open(f))
    except (OSError, ValueError):
        return {}


def keep_served(seen):
    if not DRY:
        json.dump(seen, open(D + "/data/served.json", "w"), indent=1)


def given_moments():
    """The clock's keys, from --moments "a,b" (or the MOMENTS variable)."""
    raw = ""
    if "--moments" in sys.argv:
        i = sys.argv.index("--moments")
        raw = sys.argv[i + 1] if i + 1 < len(sys.argv) else ""
    raw = raw or os.environ.get("MOMENTS", "")
    return [k.strip() for k in raw.split(",") if k.strip()]


def read_moments(keys):
    """What the clock's keys ask for: {"sweep": [...], "pre": [(id, mins)],
       "report": bool, "live": [id], "final": [id], "dayend": bool, "ranks": [...]}"""
    want = {"sweep": [], "pre": [], "report": False, "live": [], "final": [], "dayend": False,
            "ranks": [], "other": []}
    for k in keys:
        kind, _, rest = k.partition("@")
        if kind == "sweep":
            want["sweep"].append(k)
            try:
                if int(rest.split()[-1]) in RANKS_ET:
                    want["ranks"].append(k)
            except (ValueError, IndexError):
                pass
        elif kind == "pre":
            gid, _, mins = rest.rpartition("@")
            try:
                want["pre"].append((gid, int(mins)))
            except ValueError:
                want["other"].append(k)
        elif kind == "report":
            want["report"] = True
        elif kind == "live":
            want["live"].append(rest.rpartition("@")[0] or rest)
        elif kind == "final":
            want["final"].append(rest)
        elif kind == "dayend":
            want["dayend"] = True
        else:
            want["other"].append(k)        # hub@, keep@: retired, nothing to do
    return want


def dispatch_fightlog(running, seen):
    """A fight card starting: set the recorder going on GitHub for the whole
       card. It ran on his Mac and never moved when the sweep did, so the 9/26
       card has no rewinds (Jose, Sep 27, 2026: "where are the rewinds")."""
    if DRY or ("fightlog@" + str(running)) in seen:
        return
    tok = os.environ.get("GITHUB_TOKEN") or ""
    repo = os.environ.get("GITHUB_REPOSITORY") or "DPAD7/the-arena"
    if not tok:
        log("fight recorder: no GITHUB_TOKEN here, not started")
        return
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/%s/actions/workflows/fightlog.yml/dispatches" % repo,
            data=json.dumps({"ref": "main", "inputs": {"event": str(running)}}).encode(),
            headers={"authorization": "Bearer " + tok, "accept": "application/vnd.github+json",
                     "content-type": "application/json", "user-agent": "the-arena-sweep"}, method="POST")
        code = urllib.request.urlopen(req, timeout=30).status
    except Exception as e:
        code = str(e)[:80]
    log("fight recorder for card %s: %s" % (running, "started" if code == 204 else "NOT started (%s)" % code))
    if code == 204:
        seen["fightlog@" + str(running)] = NOW.isoformat()
        keep_served(seen)


def main():
    global START
    keys = given_moments()
    seen = served()
    want = read_moments(keys)
    if "--day-end" in sys.argv:
        want["dayend"] = True
    # with no moments named, this run's own clock decides, as it always did
    if not keys and "--if-due" in sys.argv:
        ahead = [e for e in board_events()
                 if datetime.datetime.fromisoformat(e["start"].replace("Z", "+00:00")) > NOW]
        drawn, _ = due_now(ahead)
        if drawn:
            key, _name, mins = drawn[0]      # one run serves every game in the slot
            want["pre"].append((key.split(":", 1)[1].rsplit("@", 1)[0], mins))
            want["_served"] = [key]
        else:
            for key, _name, _m in sweeps_due(seen):
                want["sweep"].append(key)
        for key, _name, _m in ranks_due(seen):
            want["ranks"].append(key)
    running = card_running()
    playing = game_running()
    boxing = boxing_running()
    full = bool(want["sweep"] or want["dayend"])
    pregame = bool(want["pre"])
    cards, boxcards = _ids("FIGHTCARDS"), _ids("BOXCARDS")
    live_cards = [x for x in want["live"] if x in cards]
    live_box = [x for x in want["live"] if x in boxcards]
    live_games = [x for x in want["live"] if x not in cards and x not in boxcards]
    busy = bool(full or pregame or want["ranks"] or want["final"] or want["live"] or running or playing or boxing)
    # the report window, from the clock's key, or (no keys) this run's clock
    fallback = not keys and "--if-due" in sys.argv

    if CHECK:
        # sweep.yml asks before it installs anything: 0 is due, 78 is not
        due = busy or want["report"] or (fallback and report_window(seen, mark=False))
        print("due" if due else "nothing due")
        sys.stdout.flush()
        os._exit(0 if due else 78)

    if not busy:
        # between sweeps, only in the NFL's own report windows: a new injury
        # report or insider post does anything (Jose, Sep 29, 2026: "there's
        # specific rules to this"). watch_news.py deploys what it changes.
        if want["report"] or (fallback and report_window(seen, mark=not DRY)):
            watch_news()
        if want["other"]:
            log("moments with nothing to do: " + ", ".join(want["other"]))
        os._exit(0)          # no interpreter shutdown to get stuck in

    # a report window beside a live pass: watch_news.py first, deploying what
    # it changes itself; beside a sweep or a pregame wake it is not run, those
    # read the same and more (Oct 12, 2026)
    if want["report"] and not (full or pregame):
        watch_news()
    START = fingerprint()
    log("due: " + "; ".join(
        (["sweep " + ", ".join(want["sweep"])] if want["sweep"] else []) +
        (["day end"] if want["dayend"] else []) +
        ["%s, %d min out" % (g, m) for g, m in want["pre"]] +
        (["live " + ", ".join(str(x) for x in want["live"])] if want["live"] else []) +
        (["final " + ", ".join(want["final"])] if want["final"] else []) +
        (["card running %s" % running] if running else []) +
        (["game running %s" % playing] if playing else []) +
        (["boxing running %s" % boxing] if boxing else []) +
        (["rankings"] if want["ranks"] else [])) +
        ("  [given: %s]" % ",".join(keys) if keys else ""))
    # a rehearsal must not spend a real wake
    if not DRY:
        for key in want["sweep"] + want["ranks"] + want.get("_served", []) + keys:
            seen[key] = NOW.isoformat()
            # and the same hour as this script's own clock writes it, so a
            # fallback run later in the window does not run it again
            mm = re.match(r"(sweep|ranks)@(\d{4}-\d\d-\d\d) (\d+)$", key)
            if mm:
                seen["%s@%s %02d" % (mm.group(1), mm.group(2), int(mm.group(3)))] = NOW.isoformat()
                if mm.group(1) == "sweep" and int(mm.group(3)) in RANKS_ET:
                    seen["ranks@%s %02d" % (mm.group(2), int(mm.group(3)))] = NOW.isoformat()
        keep_served(seen)
    if running:
        dispatch_fightlog(running, seen)
    # anything over that we have not written down settles now -- on the three
    # sweeps only (settle.yml saves each game the moment it goes final), and
    # after the early exit above, so a pass with nothing due asks ESPN nothing
    # (Oct 12, 2026)
    owed = []
    if want["sweep"] and not PLAN:
        owed = unsettled()
        for lg, gid, nm in owed[:6]:
            log("unsettled: %s %s is final and has no result" % (lg, nm))

    if full or pregame:
        if pregame and not full:
            # The league posts its inactives ninety minutes before kickoff, so
            # the sixty-minute wake is the first one that can read that list
            # instead of guessing at it, and the thirty is the confirm. news,
            # wire, depth and starters run once, at the head of the pregame
            # list, and starters reads every game in the horizon, this one
            # included (Jose, Sep 22, 2026: "60-minute wake for injury per
            # game ... the biggest thing is that I don't want to have to do it")
            for gid, mins in want["pre"]:
                if mins in (60, 30):
                    log("inactives wake (%d min out): %s" % (mins, gid))
        before = _dkq()
        price_drawn(FULL if full else PREGAME)
        if not DRY:
            open_pass(before)
            count_misses()
    if want["report"] and (full or pregame):
        log("report window: this pass reads the same, watch_news not run")
    # a game being played: its box score says who is throwing, so a card that
    # named the wrong man is right within ten minutes of the snap
    # (Jose, Sep 25, 2026: "we need 100% accurate qbs")
    if (playing or live_games) and (not DRY or PLAN):
        run("played_qb.py", tail=4)
    # a Zuffa card on tonight: its results from the promoter's own page every
    # pass while it runs (Jose, Sep 26, 2026); deployed below only if it
    # changed something (Oct 12, 2026)
    if (boxing or live_box) and (not DRY or PLAN):
        run("boxing.py", tail=2)
    if (running or live_cards) and not (full or pregame):
        # the card is on: read the book again for the prices and for when the
        # bouts that are left now start (Jose, Sep 18, 2026)
        log("card under way (%s): reading the bouts again" % (running or ",".join(live_cards)))
        if not DRY or PLAN:
            run("fill_fights.py", tail=6)
            # and the book's clock for the bouts already on tonight: the pass
            # above skips a card whose block time has gone, so tonight's clock
            # was never read again, and this run's stale copy won the merge
            # over a fresh one -- LaGrange v Ariano back at 7:15 when the book
            # had moved it to 9:20 (Jose, Oct 6, 2026: "Fix it!")
            run("fill_fights.py", ("--times",), tail=3, again=True, cwd=D + "/build")
    if owed or want["final"]:
        if [x for x in owed if x[0] != "mma"] or want["final"]:
            settle_late(False)
        if [x for x in owed if x[0] == "mma"]:
            settle_late(True)
    if want["ranks"] and (not DRY or PLAN):
        read_ranks()
    # a failed deploy still exits 0, so the run's commit lands; the next run
    # deploys what it wrote (deploy_owed.json)
    deploy_if_changed()
    sys.exit(0)


def _ids(var):
    """The card ids a live@ key can name: FIGHTCARDS or BOXCARDS."""
    m = re.search(r"  var %s = (\[.*?\]);\n" % var, pagefile.read(), re.S)
    try:
        return {str(c[1]) for c in json.loads(m.group(1))} if m else set()
    except ValueError:
        return set()


def watch_news():
    if PLAN:
        log("report window: would run watch_news")
        return
    if DRY:
        return
    r = subprocess.run([sys.executable, D + "/build/watch_news.py"], capture_output=True, text=True, cwd=D)
    for line in (r.stdout + r.stderr).strip().splitlines()[-8:]:
        log("   " + line)


def _dkq():
    try:
        return open(D + "/data/dk_qbs.json").read()
    except OSError:
        return ""


if __name__ == "__main__":
    main()
