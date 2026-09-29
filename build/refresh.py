"""Ask DraftKings what the board's prices are now, and rewrite only what moved.

   DraftKings sends no timestamp, no version and no ETag, and answers
   cache-control: no-store — so there is no way to ask whether a price has
   changed short of fetching it and comparing. That is what this does. It
   fetches, compares against what is on the page, and writes nothing at all
   unless a digit is different.

   Only events that have not kicked off are asked about. A game in progress
   is not priced any more and its buttons are already locked by the clock on
   the page, so pulling it would be spending a request on nothing.

   Run with --dry to see what moved without writing or deploying.

   Run with --if-due to have it decide for itself whether this is one of the
   moments worth looking: two hours, one hour and half an hour before each
   kickoff still to come. Overlapping games share a wake, so a Sunday with
   fourteen one-o'clock games costs the same as one game. Anything else and
   it exits without asking DraftKings a single question.
"""
import datetime
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
BUDGET = 540          # nine minutes, inside launchd's ten


def _out_of_time(_sig, _frame):
    sys.stderr.write("refresh.py passed its %ds budget; stopping so the next "
                     "wake is not blocked\n" % BUDGET)
    os._exit(2)


signal.signal(signal.SIGALRM, _out_of_time)
signal.alarm(BUDGET)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile
from read_dk import ask

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
# ODDS_NOW pretends it is another moment, so the wake windows can be tested
# without waiting for one to come round.
NOW = (datetime.datetime.fromisoformat(os.environ["ODDS_NOW"])
       if os.environ.get("ODDS_NOW")
       else datetime.datetime.now(datetime.timezone.utc))


def log(line):
    stamp = NOW.astimezone().strftime("%m/%d %H:%M")
    print(line)
    if not DRY:
        with open(D + "/logs/refresh.log", "a") as f:
            f.write("%s  %s\n" % (stamp, line))


def whose(page, at):
    """Name the price in the log the way the card names it: the game, then the
       man or the club the button sits against."""
    head = page.rfind('<div class="gcard"', 0, at)
    clubs = re.findall(r'<span class="gteam[^"]*">(?:<span class="gml">.*?</span>)?'
                       r'([A-Za-z&;. ]+?)(?:<span class="gml">.*?</span>)?</span>',
                       page[head:at + 400], re.S)
    game = "/".join(c.strip() for c in clubs[:2] if c.strip()) or "?"
    near = page[max(head, at - 320):at]
    man = re.findall(r'class="(?:wrname|ptdline)">([^<]{1,20})</span>', near)
    lab = re.findall(r'class="gmk">([^<]{1,14})</span>', near)
    tail = (man[-1] if man else (lab[-1] if lab else "ML")).strip()
    return ("%s %s" % (game, tail))[:22]


def implied(american):
    """What the book is charging, as a chance out of a hundred."""
    n = int(american)
    return 100.0 / (n + 100.0) if n > 0 else -n / (-n + 100.0)


def as_html(american):
    n = int(american)
    return ("+%d" % n) if n > 0 else ("&minus;%d" % -n)


def plain(american):
    """DraftKings writes its minus sign U+2212; make it a number."""
    return int(str(american).replace("−", "-").replace("+", "").strip())


# ------------------------------------------------------- what to ask for ----
src = json.load(open(D + "/data/sources.json"))

BEFORE = (120, 60, 30)     # minutes before a kickoff that a price is worth reading
# and after the whistle -- for the football, nothing. watch.py is awake while
# a game is being played and settles it the second ESPN says final, so a fixed
# look three and a half hours after kickoff is both late and, for a college
# game that ran long, wrong (Jose, Sep 22, 2026: "no 3 1/2 and 5 1/2 either").
# The fights keep theirs: a card is a night, not a game, and watch.py does not
# read them.
AFTER = ()
# and nothing after a card either. watch.py is awake from the first bell,
# asks ESPN every ten seconds, and writes each bout down the moment it reads
# final -- so looking again seven and nine hours later is looking at what is
# already settled (Jose, Sep 22, 2026: "we don't need to settle hours after,
# if ESPN says it's final then it's final")
AFTER_MMA = ()
SLOT = 11                  # the agent wakes every ten, so a window a shade wider
# DraftKings posts a game's passing props days after its moneyline, with no
# notice. These are the hours (Eastern) the drawn weeks are swept for anything
# newly posted, on top of the kickoff wakes above. Jose asked for this on
# Sep 15, 2026 after telling us by hand, again, that the props were up.
# Three a day now, not five: the noon and six o'clock sweeps asked nobody for
# a price -- fill_week.py sat them out -- and the kickoff wakes already stand
# in front of every game, so they were the rest of the list read again for
# nothing (Jose, Sep 23, 2026: "five sweeps is overkill").
SWEEP_ET = (9, 15, 21)
# the three of those that ask DraftKings for prices. A week is a hundred and
# twenty-eight prices -- a moneyline each club, 1+ and 2+ passing touchdowns
# and an anytime touchdown each passer, across sixteen games -- and fill_week.py
# now skips any game whose eight are already held. So the asking empties itself
# out over the week, and three times a day is enough to catch each market the
# morning, afternoon or evening it goes up (Jose, Sep 22, 2026: "no that
# overkill ... three times a day until its full, then stop"). The kickoff wakes
# still run it regardless: a late starter swap makes a price we hold the wrong
# man's, and that cannot wait for the next sweep.
PRICE_ET = (9, 15, 21)
# the hub's own reading, once a day before the football starts. Its thirteen
# pages are slow and none of them price anything, so they are kept off the
# kickoff wakes and never compete with a board that is about to lock. Left at
# hand-run they went two weeks stale: the sheets, splits, teasers and team
# spreads were still reading Sep 4 on Sep 18 (Jose, Sep 18, 2026)
HUB_ET = (10,)
# the rankings, once a day, on the nine o'clock sweep: the AP poll for the
# college cards, then the UFC's own table and the flattened copy a bout card
# reads its number from. A vote moves once a week, so asking more often only
# asks. Left hand-run, nothing on the schedule had ever refreshed them
# (Jose, Sep 23, 2026: "put the rankings on the schedule, once a day").
RANKS_ET = (9, 15)   # the AP poll is out Sunday afternoon; 9 AM alone left it a day behind (Sep 27, 2026)
RANK_JOBS = ("cfb_rank.py", "ufc_rankings.py", "fighter_ranks.py")
HUB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB_JOBS = ("hub_props", "hub_sheets", "hub_sheet_games", "hub_team_sheets",
            "hub_splits", "hub_team_splits", "hub_streaks", "hub_consistency",
            "hub_matchups", "hub_systems", "hub_tds", "hub_teasers",
            "hub_league_stats")
HORIZON_DAYS = 8           # the same reach fill_week.py and fill_fights.py price


def board_events():
    """Every drawn game and bout on the page still to come inside the horizon,
       shaped like the hand-built events so due_now() can read them."""
    page = open(D + "/master.html").read()
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


def hub_due(seen):
    """The daily hub read, if this is the hour for it."""
    from zoneinfo import ZoneInfo
    et = NOW.astimezone(ZoneInfo("America/New_York"))
    out = []
    for h in HUB_ET:
        wake = et.replace(hour=h, minute=0, second=0, microsecond=0)
        key = "hub@" + wake.strftime("%Y-%m-%d %H")
        late = (et - wake).total_seconds() / 60.0
        if key not in seen and 0 <= late < SLOT:
            out.append((key, "hub read %d:00 ET" % h, 0))
    return out


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


def read_hub():
    """Set the thirteen hub readers going and let go of them. They are minutes
       of fetching apiece and this run has nine for everything, so waiting on
       them would kill the wake that is actually pricing games."""
    log_path = HUB + "/hub_sweep.log"
    # quoted: the folder is "the arena", so unquoted the shell reads
    # /Users/joe/Desktop/the and every one of the thirteen readers dies on the
    # space before it opens anything. They have never once run (Sep 20, 2026)
    import shlex
    script = "; ".join("%s %s" % (shlex.quote(sys.executable),
                                  shlex.quote("%s/build/%s.py" % (HUB, j)))
                       for j in HUB_JOBS)
    with open(log_path, "a") as f:
        f.write("\n===== %s\n" % NOW.isoformat())
        subprocess.Popen(["/bin/sh", "-c", script], cwd=HUB, stdout=f, stderr=f,
                         start_new_session=True)
    log("hub: %d readers set going, logging to %s" % (len(HUB_JOBS), log_path))


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


def price_drawn():
    """The drawn weeks: results first, then every game and bout still to come.
       fill_week.py and fill_fights.py deploy what they change themselves."""
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
    # ptd10.py rides at the back and touches nothing the board reads: it takes
    # the ledger and the prices the jobs above have just written and leaves one
    # note behind, notes/ptd10-week-N.md -- who to take for one passing
    # touchdown and why (Jose, Sep 20, 2026: "do not change how we do the site,
    # just make a separate note")
    # ask_fold.py rides behind the two pricers: whatever a double tap read
    # between sweeps is kept on the site, and this lays it into the price
    # files -- only where a slot is empty, never over a price the sweep just
    # read (Jose, Sep 23, 2026: double tap fetches the missing prices).
    from zoneinfo import ZoneInfo
    hour = NOW.astimezone(ZoneInfo("America/New_York")).hour
    for job in ("settle.py", "played_qb.py", "kicks.py", "news.py", "wire.py", "depth.py", "starters.py", "dk_sitemap.py", "dk_people.py", "ledger.py", "alt_ptd.py", "mma_year.py", "fill_week.py", "cfb_ml.py", "keep_prices.py", "fill_fights.py", "boxing.py", "posters.py", "alerts.py", "lineups.py", "guard.py", "qb_search.py", "ask_fold.py", "score_watch.py", "networks.py", "birthdays.py", "faces.py", "mirror.py", "records_mma.py", "ptd10.py", "covered.py"):
        if job == "fill_week.py" and hour in SWEEP_ET and hour not in PRICE_ET:
            log("   fill_week: not a pricing hour (%d:00 ET), nothing asked" % hour)
            continue
        r = subprocess.run([sys.executable, D + "/build/" + job] + (["--dry"] if DRY else []),
                           capture_output=True, text=True)
        for line in (r.stdout + r.stderr).strip().splitlines():
            log("   %s: %s" % (job[:-3], line))


def card_running():
    """A fight card under way: from half an hour before its first bell until
       three hours after the last one is due. While it runs, the book moves
       every bout that is left -- a knockout in the first pulls the rest of the
       night forward -- so the prices and the clock are read on every pass
       rather than on the wakes alone (Jose, Sep 18, 2026)."""
    page = open(D + "/master.html").read()
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
    page = open(D + "/master.html").read()
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
    page = open(D + "/master.html").read()
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


def after_due(events, seen):
    """The wakes that stand behind a game rather than in front of it."""
    hit = []
    for e in events:
        if not e["start"]:
            continue
        kick = datetime.datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
        fight = e["id"].startswith("FIGHTS:")
        for mins in (AFTER_MMA if fight else AFTER):
            key = "%s@+%d" % (e["id"], mins)
            if key in seen:
                continue
            late = (NOW - (kick + datetime.timedelta(minutes=mins))).total_seconds() / 60.0
            if 0 <= late < SLOT:
                hit.append((key, e["name"], mins, fight))
    return hit


def settle_late(fight):
    """After the whistle: the result and the ladder, then the touchdown clips
       from the club sites, nfl.com and the clubs' posts. The clip builders are
       the slow ones, so they run here and nowhere else.

       A card answers to mma_year.py instead, which writes the fought event to
       site/final/mma-{id}.json and takes ESPN's stored closing price for every
       bout the board still shows unpriced."""
    jobs = ("mma_year.py",) if fight else (
        "settle.py", "played_qb.py", "starters.py", "ledger.py", "alt_ptd.py",
        "nfl_clips.py", "build_nflindex.py", "club_clips.py", "x_clips.py")
    for job in jobs:
        if not os.path.exists(D + "/build/" + job):
            log("   %s: not here, skipped" % job[:-3])
            continue
        r = subprocess.run([sys.executable, D + "/build/" + job] + (["--dry"] if DRY else []),
                           capture_output=True, text=True, cwd=D)
        for line in (r.stdout + r.stderr).strip().splitlines()[-6:]:
            log("   %s: %s" % (job[:-3], line))
    if DRY:
        return
    # played_qb and starters write the page, so the deploy carries it built
    pagefile.deployable(pagefile.read())
    out = subprocess.run(
        ["npx", "wrangler", "pages", "deploy", ".",
         "--project-name=the-arenasports", "--branch=main"],
        cwd=D + "/site", capture_output=True, text=True, timeout=300)
    log("after the whistle: deployed" if out.returncode == 0
        else "after the whistle: DEPLOY FAILED " + (out.stderr or "")[-200:])


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


if "--if-due" in sys.argv:
    # DraftKings is read only when he double taps the bag (dkbets.yml), never
    # on a sweep (Jose, Sep 26, 2026: "only when I double tap")
    hit, seen = due_now(src["events"])
    ahead = [e for e in board_events()
             if datetime.datetime.fromisoformat(e["start"].replace("Z", "+00:00")) > NOW]
    drawn, _ = due_now(ahead)
    if drawn:
        drawn = drawn[:1]    # one run serves every game in the slot
    else:
        drawn = sweeps_due(seen)
    hub = hub_due(seen)
    ranks = ranks_due(seen)
    late = after_due(board_events(), seen)
    running = card_running()
    playing = game_running()
    if late:
        # one run settles every game in the slot and one every card, but a
        # football wake and a fight wake are different work, so a slot holding
        # both does both rather than marking both served and doing one
        # (Jose, Sep 18, 2026)
        games = [x for x in late if not x[3]][:1]
        cards = [x for x in late if x[3]][:1]
        late = games + cards
    # anything over that we have not written down settles now, whatever the
    # clock says -- and a wake the clock was still holding is spent here
    owed = unsettled()
    if owed and not [x for x in late if not x[3]]:
        for lg, gid, nm in owed[:6]:
            log("unsettled: %s %s is final and has no result" % (lg, nm))
        late = late + [("unsettled@%s" % owed[0][1], owed[0][2], 0,
                        owed[0][0] == "mma")]
    if not hit and not drawn and not late and not hub and not ranks and not running and not playing and not boxing_running():
        os._exit(0)          # no interpreter shutdown to get stuck in
    log("due: " + "; ".join("%s, %d min out" % (n or "?", m) for _, n, m in hit + drawn) +
        "".join("%s, %d min after" % (n or "?", m) for _, n, m, _f in late) +
        "".join(n for _, n, _ in hub + ranks))
    # a rehearsal must not spend a real wake
    if not DRY:
        for key, _, _ in hit + drawn + hub + ranks:
            seen[key] = NOW.isoformat()
        for key, _, _, _f in late:
            seen[key] = NOW.isoformat()
        json.dump(seen, open(D + "/data/served.json", "w"), indent=1)
    # a fight card starting: set the recorder going on GitHub for the whole
    # card. It ran on his Mac and never moved when the sweep did, so the 9/26
    # card has no rewinds (Jose, Sep 27, 2026: "where are the rewinds")
    if running and not DRY and ("fightlog@" + str(running)) not in seen:
        tok = os.environ.get("GITHUB_TOKEN") or ""
        repo = os.environ.get("GITHUB_REPOSITORY") or "DPAD7/the-arena"
        if tok:
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
                json.dump(seen, open(D + "/data/served.json", "w"), indent=1)
        else:
            log("fight recorder: no GITHUB_TOKEN here, not started")
    if playing and not DRY:
        r = subprocess.run([sys.executable, D + "/build/played_qb.py"], capture_output=True, text=True, cwd=D)
        out = (r.stdout + r.stderr).strip().splitlines()
        for line in out[-4:]:
            log("   played_qb (live): " + line)
        if any("rows corrected: 0" in x for x in out) is False and r.returncode == 0:
            pagefile.deployable(pagefile.read())
            dep = subprocess.run(["npx", "wrangler", "pages", "deploy", ".",
                                  "--project-name=the-arenasports", "--branch=main"],
                                 cwd=D + "/site", capture_output=True, text=True, timeout=300)
            log("   live passer fixed: deployed" if dep.returncode == 0 else "   live passer fixed: DEPLOY FAILED")
    # a Zuffa card on tonight: its results from the promoter's own page every
    # pass while it runs (Jose, Sep 26, 2026)
    if not DRY and boxing_running():
        r = subprocess.run([sys.executable, D + "/build/boxing.py"], capture_output=True, text=True, cwd=D)
        for line in (r.stdout + r.stderr).strip().splitlines()[-2:]:
            log("   boxing (live): " + line)
        pagefile.deployable(pagefile.read())
        dep = subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=the-arenasports", "--branch=main"],
                             cwd=D + "/site", capture_output=True, text=True, timeout=300)
        log("   boxing results: deployed" if dep.returncode == 0 else "   boxing results: DEPLOY FAILED")
    if running and not drawn:
        # the card is on: read the book again for the prices and for when the
        # bouts that are left now start (Jose, Sep 18, 2026)
        log("card under way (%s): reading the bouts again" % running)
        if not DRY:
            r = subprocess.run([sys.executable, D + "/build/fill_fights.py"], capture_output=True, text=True)
            for line in (r.stdout + r.stderr).strip().splitlines()[-6:]:
                log("   fill_fights: " + line)
    if drawn:
        # The league posts its inactives ninety minutes before kickoff, so the
        # sixty-minute wake is the first one that can read that list instead of
        # guessing at it, and the thirty is the confirm. Both ask ESPN again
        # and settle this one game's passer before the prices are read for him
        # (Jose, Sep 22, 2026: "60-minute wake for injury per game ... the
        # biggest thing is that I don't want to have to do it").
        for _key, _name, _mins in drawn:
            if _mins not in (60, 30) or not _key.startswith("SCHED:"):
                continue
            gid = _key.split(":", 1)[1].split("@")[0]
            log("inactives wake (%d min out): %s" % (_mins, _name))
            for job in ("news.py", "wire.py", "depth.py"):
                r = subprocess.run([sys.executable, D + "/build/" + job],
                                   capture_output=True, text=True, cwd=D)
                for line in (r.stdout + r.stderr).strip().splitlines()[-3:]:
                    log("   %s: %s" % (job[:-3], line))
            r = subprocess.run([sys.executable, D + "/build/starters.py",
                                "--game", gid], capture_output=True, text=True, cwd=D)
            for line in (r.stdout + r.stderr).strip().splitlines()[-6:]:
                log("   starters: " + line)
        price_drawn()
    for _k, _n, _m, _fight in late:
        settle_late(_fight)
    if hub and not DRY:
        read_hub()
        # once a day, DraftKings is asked for a token and the login it hands
        # back is kept, so his login never lapses between double taps; his
        # bets are not read (Jose, Sep 26, 2026: "only when I double tap")
        try:
            r = subprocess.run([sys.executable, D + "/build/dk_bets.py", "--keep"],
                               capture_output=True, text=True, cwd=D, timeout=90)
            for line in (r.stdout + r.stderr).strip().splitlines()[-2:]:
                log("   dk login: " + line)
        except Exception as e:
            log("   dk login: did not run (%s)" % type(e).__name__)
    if ranks and not DRY:
        read_ranks()
    if not hit:
        sys.exit(0)
live = [e for e in src["events"]
        if e["start"] and datetime.datetime.fromisoformat(
            e["start"].replace("Z", "+00:00")) > NOW]
gone = len(src["events"]) - len(live)

board_oids = set()
for e in src["events"]:
    board_oids |= set(e["oids"])
for l in src["league"]:
    board_oids |= set(l.get("oids") or [])

if not live:
    log("no hand-built prices left to ask about; the drawn cards are priced by fill_week.py")
    if not DRY:
        for job in ("fill_week.py", "fill_fights.py", "settle.py"):
            subprocess.run([sys.executable, D + "/build/" + job])
    sys.exit(0)

# every price whose game has not kicked: the ones under an event's own
# category, and the league-wide ones belonging to a game still to come
live_ids = {e["id"] for e in live}
live_oids = set()
for e in live:
    live_oids |= set(e["oids"])
for l in src["league"]:
    for oid, eid in (l.get("event_of") or {}).items():
        if eid in live_ids:
            live_oids.add(oid)

log("asking about %d events still to kick (%d already started)" % (len(live), gone))

# ------------------------------------------------------------ the asking ----
now_price = {}
asked = failed = 0

for e in live:
    for cat in e["cats"]:
        got = ask(None, None,
                  "/sportscontent/dkusmd/v1/events/%s/categories/%d" % (e["id"], cat))
        asked += 1
        if not got:
            failed += 1
            continue
        for s in got.get("selections") or []:
            od = (s.get("displayOdds") or {}).get("american")
            if s.get("id") in board_oids and od:
                now_price[s["id"]] = plain(od)

for l in src["league"]:
    if not (set(l.get("oids") or []) & live_oids):
        log("   skipped: %s — every game it prices has kicked" % l["what"])
        continue
    got = ask(None, None, l["path"])
    asked += 1
    if not got:
        failed += 1
        continue
    # an emptied league-wide list is a 200 with nothing in it, not an error.
    # DraftKings relocates markets into each event's own category and leaves
    # the old path answering politely, so every id read from it goes stale
    # while the board keeps showing the price it last saw.
    if not (got.get("selections") or []):
        log("   EMPTY: %s answered with 0 selections — the market has most "
            "likely moved to the events' own categories; its ids are stale"
            % l["what"])
        failed += 1
        continue
    for s in got.get("selections") or []:
        od = (s.get("displayOdds") or {}).get("american")
        if s.get("id") in board_oids and od:
            now_price[s["id"]] = plain(od)

log("%d requests (%d came back empty), %d prices read back"
    % (asked, failed, len(now_price)))

# --------------------------------------------------------- what moved -------
page = pagefile.read()
BTN = r'(<button class="price"[^>]*data-oid="%s"[^>]*>)(.*?)(</button>)'

moved, held, absent = [], 0, []
for oid in sorted(live_oids):
    fresh = now_price.get(oid)
    m = re.search(BTN % re.escape(oid), page, re.S)
    if not m:
        continue
    if fresh is None:
        absent.append(oid)
        continue
    was = m.group(2)
    shown = re.match(r"\s*(&minus;|−|-|\+)?\s*(\d+)", was)
    if shown and plain((("-" if shown.group(1) in ("&minus;", "−", "-") else "+")
                        + shown.group(2))) == fresh:
        held += 1
        continue
    moved.append((oid, was.split("<")[0].strip(), fresh))

log("moved: %d | held: %d | market no longer offered: %d"
    % (len(moved), held, len(absent)))
for oid, was, now in moved[:40]:
    m = re.search(BTN % re.escape(oid), page, re.S)
    log("   %-22s %8s -> %-8s  %s"
        % (whose(page, m.start()), was.replace("&minus;", "-"),
           as_html(now).replace("&minus;", "-"), oid[:24]))

if not moved:
    log("nothing moved — the board is already right, nothing written")
    sys.exit(0)

# ------------------------------------------------------------ the writing ---
# the prices were read from DraftKings minutes ago and the page may have been
# edited since, so the swaps are made against the file as it is now rather than
# against the copy this run started from (Jose, Sep 17, 2026)
page = pagefile.read()
for oid, _, fresh in moved:
    def swap(m, f=fresh):
        return m.group(1) + '%s <span class="pct">%d%%</span>' % (
            as_html(f), round(implied(f) * 100)) + m.group(3)
    page, n = re.subn(BTN % re.escape(oid), swap, page, count=1, flags=re.S)
    if n != 1:
        log("   %s is no longer on the page, left alone" % oid[:24])

# If the page carries a read-time line, keep it current. It does not any more
# — Jose took it off — so this updates one where it exists and never adds one.
when = NOW.astimezone(datetime.timezone(datetime.timedelta(hours=-4)))
stamp = "DK read " + when.strftime("%a %-m/%-d %-I:%M %p") + " ET"
page = re.sub(r'(<div class="stamp" id="stamp">)[^<]*(</div>)',
              lambda m: m.group(1) + stamp + m.group(2), page, count=1)

if DRY:
    log("dry run — nothing written")
    sys.exit(0)

if not pagefile.write(page):
    log("the page changed while this run was reading — nothing written")
    sys.exit(0)
pagefile.deployable(page)

out = subprocess.run(
    ["npx", "wrangler", "pages", "deploy", ".",
     "--project-name=the-arenasports", "--branch=main"],
    cwd=D + "/site", capture_output=True, text=True, timeout=300)
ok = out.returncode == 0
log("deployed" if ok else "DEPLOY FAILED: " + (out.stderr or "")[-300:])
sys.exit(0 if ok else 1)
