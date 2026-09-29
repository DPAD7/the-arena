"""The sweep checks the whole board before it deploys, and mends what it can.

   Every fault Jose had to point at by hand had the same shape: a read came
   back empty or a piece went missing, and nothing said so (Sep 28, 2026: "it
   can't be me just telling you every time"). So after the sweep's jobs, this
   asks the finished files the questions he has had to ask, and runs again
   whichever job answers for the part that is wrong:

     passers    all 32 clubs on the chart; the wire read; no passer named on
                the page that the wire has out, on IR or doubtful   depth, wire, starters
     lineups    every NFL game in the next day has one              lineups
     prices     every NFL game in the next day has both sides'
                moneyline and 1+ passing TD                         fill_week
     faces      every named passer and every fighter this week      faces
                has a picture on the site
     jerseys    a Kalshi jersey for every club
     fights     every bout this week has its weight class
     settled    every game and bout over for six hours has its
                result written                                      settle
     files      every JSON the page reads opens; every file the
                page and the fonts point at is there
     the page   rendered and measured, build/look.py: nothing
                thrown, no sideways scroll, fonts loaded, no broken
                pictures, HOT at 55px, All and search at 32

   After a deploy, --live asks the site itself: the build on it is the one
   just made (if not, deploy again), the functions answer JSON, and a
   passer's face comes back a picture, never the web page.

   What is still wrong after the mend is written to site/guard.json and
   printed on lines that start GUARD:. An empty list means the board passed.

       python3 build/guard.py
       python3 build/guard.py --live
"""
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(D, "site")
OUT = os.path.join(SITE, "guard.json")
HOST = "https://the-arenasports.pages.dev"
NOW = dt.datetime.now(dt.timezone.utc)
STOP = ("out", "injured reserve", "physically unable to perform", "suspended", "suspension", "pup", "ir", "doubtful")


def load(name):
    try:
        return json.load(open(os.path.join(SITE, name)))
    except (OSError, ValueError):
        return {}


def run(job, *args):
    r = subprocess.run([sys.executable, os.path.join(D, "build", job)] + list(args),
                       capture_output=True, text=True, cwd=D)
    for line in (r.stdout + r.stderr).strip().splitlines()[-3:]:
        print("   %s: %s" % (job[:-3], line))


def rows(var):
    m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, pagefile.read(), re.S)
    out = []
    for g in json.loads(m.group(1)) if m else []:
        try:
            out.append((g, dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")) - NOW))
        except (ValueError, AttributeError, IndexError):
            continue
    return out


def soon(var, before=dt.timedelta(hours=4), after=dt.timedelta(days=8)):
    return [(g, left) for g, left in rows(var) if -before <= left <= after]


# -- each check returns ["what is wrong", ...], each line tagged by the job
#    that mends it

def passers():
    depth, wire, wrong = load("depth.json"), load("wire.json"), []
    if len(depth) < 32:
        wrong.append(("depth", "depth.json holds %d clubs, not 32" % len(depth)))
    if not wire:
        wrong.append(("wire", "wire.json is empty"))
    for g, _ in soon("SCHED"):
        for i, ci in ((5, 3), (7, 4)):
            club, pid = g[ci], str(g[i + 1] or "")
            st = ((wire.get(pid) or {}).get("status") or "").lower()
            if pid and st in STOP:
                wrong.append(("starters", "%s %s is named for game %s and the wire has him %s" % (club, g[i], g[1], st)))
    return wrong


def lineups():
    lu, depth = load("lineups.json"), load("depth.json")
    return [("lineups", "game %s (%s at %s) has no lineup" % (g[1], g[3], g[4]))
            for g, left in soon("SCHED", after=dt.timedelta(days=1)) if g[3] in depth and str(g[1]) not in lu]


def benches():
    """A red edge always carries a backup: a starter marked out with nobody
       named in for him is a hole in the chart."""
    return [("lineups", "%s %s is out with nobody in for him" % (c, m.get("nm") or m.get("k")))
            for g in load("lineups.json").values() for c, x in g.items()
            for side in x.values() for m in side if m.get("s") == "out" and not m.get("was")]


def formats():
    """A finished bout knows how many rounds it was scheduled for, or its
       finish is drawn in the wrong round."""
    wrong = []
    for f in glob.glob(os.path.join(SITE, "final", "mma-*.json")):
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        n = sum(1 for e in d.get("events") or [] for c in e.get("competitions") or [] if not c.get("format"))
        if n:
            wrong.append((None, "%s has %d bouts with no round count" % (os.path.basename(f), n)))
    return wrong


def rewinds():
    """Every bout on a card finished in the last two weeks has a rewind. The
       recorder runs on GitHub from half an hour before the first bell; a card
       with none means it never started, and nothing else would say so --
       9/22 and 9/26 went by with no rewinds at all (Sep 28, 2026)."""
    idx = load(os.path.join("anim", "index.json")) if os.path.exists(os.path.join(SITE, "anim", "index.json")) else {}
    cards = {}
    for g, left in rows("FIGHTS"):
        if -dt.timedelta(days=14) < left < -dt.timedelta(hours=6):
            cards.setdefault(g[0], []).append(str(g[1]))
    wrong = []
    for eid, bouts in cards.items():
        miss = [b for b in bouts if b not in idx]
        if miss:
            wrong.append((None, "card %s: %d of %d bouts have no rewind" % (eid, len(miss), len(bouts))))
    return wrong


def prices():
    p, wrong = load("prices.json"), []
    for g, left in soon("SCHED", before=dt.timedelta(0), after=dt.timedelta(days=1)):
        gid = str(g[1])
        ml = (p.get("SCHED") or {}).get(gid) or g[9:13]
        if not (ml and ml[0] and ml[2]):
            wrong.append(("fill_week", "%s at %s has no moneyline" % (g[3], g[4])))
        ptd = ((p.get("PROPS") or {}).get(gid) or {}).get("ptd") or []
        for side, name in ((0, g[5]), (1, g[7])):
            if len(ptd) <= side or not ptd[side] or not (ptd[side][0] or [None])[0]:
                wrong.append(("fill_week", "%s has no 1+ passing TD price for %s at %s" % (name, g[3], g[4])))
    return wrong


def faces():
    wrong = []
    for g, _ in soon("SCHED", after=dt.timedelta(days=7)):
        for i in (5, 7):
            pid = str(g[i + 1] or "")
            if pid and not os.path.exists(os.path.join(SITE, "faces", "nfl", pid + ".png")):
                wrong.append(("faces", "%s (%s) has no picture" % (g[i], pid)))
    for g, _ in soon("FIGHTS", after=dt.timedelta(days=7)):
        # ESPN's picture, or theScore's where ESPN has none (build/mirror.py)
        for i, si in ((3, 12), (5, 13)):
            pid, sid = str(g[i + 1] or ""), str((g[si] if len(g) > si else "") or "")
            have = [os.path.join(SITE, "faces", "mma", x + ".png") for x in (pid, "s" + sid) if x.strip("s")]
            # nopic.json: looked for at ESPN, theScore and ufc.com, and none
            # of them has one yet -- a debut's silhouette, not a fault
            if pid and pid not in NOPIC and not any(os.path.exists(x) for x in have):
                wrong.append(("mirror", "%s (%s) has no picture" % (g[i], pid)))
    return wrong


NOPIC = set(load("nopic.json") or [])


def jerseys():
    return [(None, "%s has no Kalshi jersey" % c) for c in load("depth.json")
            if not os.path.exists(os.path.join(SITE, "ico", "jersey", c + ".png"))]


def fights():
    return [(None, "%s vs %s has no weight class" % (g[3], g[5]))
            for g, _ in soon("FIGHTS", after=dt.timedelta(days=7)) if not (g[7] or "").strip()]


def settled():
    wrong = []
    for var, name in (("SCHED", lambda g: g[1]), ("CFB", lambda g: g[1]), ("FIGHTS", lambda g: "mma-" + g[0])):
        for g, left in rows(var):
            if -dt.timedelta(days=4) < left < -dt.timedelta(hours=6) and \
                    not os.path.exists(os.path.join(SITE, "final", "%s.json" % name(g))):
                wrong.append(("settle", "%s %s is over and has no result" % (var, name(g))))
    return wrong


def files():
    wrong = []
    for f in glob.glob(os.path.join(SITE, "*.json")) + glob.glob(os.path.join(SITE, "anim", "index.json")):
        try:
            json.load(open(f))
        except (OSError, ValueError):
            wrong.append((None, "%s does not open" % os.path.relpath(f, SITE)))
    page = open(os.path.join(SITE, "index.html")).read() if os.path.exists(os.path.join(SITE, "index.html")) else ""
    refs = set(re.findall(r'(?:src|href)="((?:ico|img|font|logos|lib|faces)/[^"?#' + "'+" + r']+)"', page))
    for css in glob.glob(os.path.join(SITE, "font", "*.css")):
        for u in re.findall(r"url\(['\"]?([^'\")]+)", open(css).read()):
            if not u.startswith(("http", "data:")):
                refs.add(os.path.relpath(os.path.join(os.path.dirname(css), u), SITE))
    for r in sorted(refs):
        if not os.path.exists(os.path.join(SITE, r)):
            wrong.append((None, "the page points at %s and it is not there" % r))
    return wrong


def the_page():
    try:
        import look
        return [(None, w) for w in look.main()]
    except Exception as e:
        return [(None, "the page could not be rendered (%s)" % type(e).__name__)]


CHECKS = (passers, lineups, benches, formats, rewinds, prices, faces, jerseys, fights, settled, files)
# the order a mend is run in, when more than one is due
MENDS = ("depth", "wire", "starters", "fill_week", "faces", "mirror", "settle", "lineups")


def local():
    wrong = [w for c in CHECKS for w in c()]
    due = {j for j, _ in wrong if j}
    if due:
        for _, w in wrong:
            print("   mending: " + w)
        for job in MENDS:
            # a new passer needs his lineup and his prices read again
            if job in due or (job in ("lineups", "fill_week") and due & {"depth", "starters"}):
                run(job + ".py")
        wrong = [w for c in CHECKS for w in c()]
    wrong += the_page()
    return [w for _, w in wrong]


def live():
    from curl_cffi import requests as rq
    wrong = []

    def get(path):
        try:
            return rq.get(HOST + path, impersonate="chrome", timeout=30)
        except Exception:
            return None

    # the page on the site is the page on main: its stamp put back, it must
    # read letter for letter as this copy of master.html would build. The
    # sweep deploys the repo's page, so anything else is a deploy that did
    # not land, or one made without a push (Sep 20, 2026)
    def same():
        r, t = get("/?%d" % dt.datetime.now().timestamp()), get("/build.txt?%d" % dt.datetime.now().timestamp())
        if r is None or t is None or r.status_code != 200 or t.status_code != 200:
            return False
        return r.text.replace(t.text.strip(), "__BUILD__") == pagefile.DOC + pagefile.read() + "\n</body>\n</html>\n"
    if not same():
        print("   mending: the site does not carry main's page -- building and deploying it")
        pagefile.deployable(pagefile.read())
        subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=the-arenasports", "--branch=main"],
                       cwd=SITE, capture_output=True, text=True, timeout=300)
        if not same():
            wrong.append("the site does not carry main's page, and deploying it again did not take")
    # /state answers to the page's own key, read off the page
    key = (re.search(r'var ARENAOWN = "([^"]+)"', pagefile.read()) or [None, ""])[1]
    for path in ("/state?k=" + key, "/wire.json", "/prices.json", "/qbsearch.json", "/lineups.json"):
        r = get(path)
        ok = r is not None and r.status_code == 200
        try:
            ok = ok and r.json() is not None
        except ValueError:
            ok = False
        if not ok:
            wrong.append("%s does not answer JSON (%s)" % (path.split("?")[0], r.status_code if r is not None else "no answer"))
    g = next((g for g, _ in soon("SCHED") if g[6]), None)
    if g:
        r = get("/face/nfl/%s.png" % g[6])
        if r is not None and r.status_code == 200 and "text/html" in r.headers.get("content-type", ""):
            wrong.append("a passer's face comes back as the web page")
    return wrong


def main():
    wrong = live() if "--live" in sys.argv else local()
    was = load("guard.json")
    was[("live" if "--live" in sys.argv else "board")] = {"at": NOW.strftime("%Y-%m-%dT%H:%MZ"), "wrong": wrong}
    was.pop("wrong", None)
    was.pop("at", None)
    json.dump(was, open(OUT, "w"), indent=1)
    for w in wrong:
        print("GUARD: " + w)
    print("guard%s: %s" % (" (live)" if "--live" in sys.argv else "",
                           "the board passed" if not wrong else "%d still wrong" % len(wrong)))


if __name__ == "__main__":
    main()
