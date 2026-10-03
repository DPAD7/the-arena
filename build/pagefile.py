"""One door in and out of the page.

   The page lives as parts under src/ (Sep 30, 2026): the boot screen, the
   styles, the markup, the script in seven slices and the search. Each part
   is a run of whole lines of the one page, cut at a line that appears in it
   once (src/parts.json says which), so read() joins them back byte for byte
   and write() cuts a written page at the same lines again. Nothing reads or
   writes the parts but this module; a script asks for the page as one
   string, edits it, and hands the string back, the way it always has.

   Every run that changes the page reads the whole page, edits the string it
   is holding, and writes the whole page back. So a run that started before an
   edit was saved will put the page back the way it was, with no error and
   nothing in the log. On Sep 17, 2026 that ate the same edit twice and made a
   deploy ship a call to a function that did not exist.

   The guard is one line of arithmetic: before writing, read the page again.
   If it is not byte for byte what this run started from, somebody else has
   written since, and this run's copy is stale, so it does not write. Nothing
   is lost by skipping -- the next wake reads the new page and does the same
   work on it.

   Usage:

       import pagefile
       s = pagefile.read()
       ...                       # edit the string
       if not pagefile.write(s, was=pagefile.LAST):
           print("page changed under us, not written")
           return

   A write that cannot find a part's first line in the new page (the line was
   edited away) raises rather than writing, so a mistake stops the run
   instead of scrambling the parts; put the line back or move it in
   src/parts.json.

   (Jose, Sep 17, 2026; the parts, Sep 30, 2026)
"""
import json
import os
import re
import time

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(D, "src")
PARTS = os.path.join(SRC, "parts.json")
LAST = None          # what the last read() returned, for the usual one-read run


def parts():
    return json.load(open(PARTS))


def assemble():
    """The page as one string, the parts joined in order."""
    return "".join(open(os.path.join(SRC, p["file"])).read() for p in parts())


def cut(page):
    """The page as its parts, cut at each part's first line. Raises when a
       first line is missing from the page or in it more than once."""
    lines = page.split("\n")
    ps = parts()
    starts = [0]
    for p in ps[1:]:
        hits = [i for i, l in enumerate(lines) if l == p["at"]]
        if len(hits) != 1:
            raise ValueError("pagefile: the line %r that starts %s is %s in the page"
                             % (p["at"], p["file"], "missing" if not hits else "there %d times" % len(hits)))
        starts.append(hits[0])
    if starts != sorted(starts):
        raise ValueError("pagefile: the parts' first lines are out of order in the page")
    out = []
    for k, p in enumerate(ps):
        lo = starts[k]
        hi = starts[k + 1] if k + 1 < len(ps) else len(lines)
        out.append((p["file"], "\n".join(lines[lo:hi]) + ("\n" if k + 1 < len(ps) else "")))
    return out


def read():
    """The page as it is now, remembered so write() can check it is unchanged."""
    global LAST
    LAST = assemble()
    return LAST


def write(new, was=None):
    """Write the page, unless it has changed since it was read.

       Answers True when it wrote and False when it stood down."""
    global LAST
    if was is None:
        was = LAST
    if was is None:
        raise ValueError("pagefile.write needs the text this run started from")
    if assemble() != was:
        return False
    pieces = cut(new)
    for f, text in pieces:
        path = os.path.join(SRC, f)
        if os.path.exists(path) and open(path).read() == text:
            continue
        tmp = path + ".tmp"
        open(tmp, "w").write(text)
        os.replace(tmp, path)
    LAST = new
    return True


DOC = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       # it is opened from the home screen and used as an app, and an app
       # does not pinch-zoom (Jose, Sep 22, 2026: "I can still zoom in when
       # you normally can't zoom in on apps"). viewport-fit=cover is what
       # lets the safe-area insets the two bars are placed with mean anything
       '<meta name="viewport" content="width=device-width, initial-scale=1, '
       'maximum-scale=1, user-scalable=no, viewport-fit=cover">\n'
       '<meta name="robots" content="noindex">\n'
       # video.twimg.com answers 403 to any request that names another site as its referer
       '<meta name="referrer" content="no-referrer">\n</head>\n<body>\n')


# a line of the page that is only data: the schedules, prices and maps the
# sweep rewrites every run ("  var SCHED = [[...]];")
DATALINE = re.compile(r'^  var [A-Z][A-Z0-9_]* = [\[{"].*;\s*$')


def stamps(page):
    """Two fourteen-digit stamps: one for the code, one for the data lines.
       A stamp from the clock changed on every sweep, and the page reloads on
       a new stamp, so the app restarted every time prices moved and closed
       the wallet or the search under him (Jose, Sep 29, 2026: "is there a
       bug in the code that restarts the app when something refreshes?").
       Now only new code reloads a page in front of him; new data waits for
       the page to be put away."""
    import hashlib
    code, data = [], []
    for line in page.split("\n"):
        (data if DATALINE.match(line) else code).append(line)
    h = lambda xs: "%014d" % (int(hashlib.sha1("\n".join(xs).encode()).hexdigest(), 16) % 10 ** 14)
    return h(code), h(data)


def schedule(page):
    """site/schedule.json: every kickoff and first bell on the board, for the
       site's own clock (site/functions/wake.js), which reads it to know when
       anything is due -- sweeps, pregame, injury windows, live games, finals
       (Jose, Sep 29, 2026). [[kind, id, start ISO, league]]"""
    import json as _j
    out = []
    for var, kind, lg in (("SCHED", "game", "nfl"), ("CFB", "game", "college-football"),
                          ("FIGHTCARDS", "card", "mma"), ("BOXCARDS", "card", "boxing")):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, page, re.S)
        for g in _j.loads(m.group(1)) if m else []:
            if len(g) > 2 and g[2]:
                row = [kind, str(g[1]), g[2], lg]
                # a game: its clubs and the passer each card names, by ESPN id,
                # so the clock can tie a leg to his game and his box line
                if kind == "game" and len(g) > 8:
                    row += [g[3], g[4], g[5], str(g[6] or ""), g[7], str(g[8] or "")]
                out.append(row)
    # every bout, for the fight legs on his slips:
    # ["bout", bout id, start, "mma"|"boxing", left, right, left id, right id, card id]
    for var, lg in (("FIGHTS", "mma"), ("BOXFIGHTS", "boxing")):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, page, re.S)
        for f in _j.loads(m.group(1)) if m else []:
            if len(f) > 6 and f[2]:
                out.append(["bout", str(f[1]), f[2], lg, f[3], f[5], str(f[4] or ""), str(f[6] or ""), str(f[0])])
    _j.dump(out, open(os.path.join(D, "site", "schedule.json"), "w"), separators=(",", ":"))


def catch_up(page):
    """On GitHub, the page a run deploys takes in any change to src/ shipped
       to main after the run checked out. A sweep that started before a ship
       built the older page and deployed it over the new one (Oct 3, 2026: the
       slip went back to "No boost" at 10:50). The run's own uncommitted
       writes ride over the pull in a stash; anything that will not apply
       cleanly leaves the run as it was, which is no worse than before."""
    if not os.environ.get("GITHUB_ACTIONS"):
        return page
    import subprocess
    def git(*a):
        return subprocess.run(["git"] + list(a), cwd=D, capture_output=True, text=True)
    try:
        if git("fetch", "-q", "origin", "main").returncode:
            return page
        if git("merge-base", "--is-ancestor", "origin/main", "HEAD").returncode == 0:
            return page
        base = git("merge-base", "HEAD", "origin/main").stdout.strip()
        if not base or git("diff", "--quiet", base, "origin/main", "--", "src").returncode == 0:
            return page
        if page != read():
            print("pagefile: newer page on main, but this run holds unsaved edits; deploying its own")
            return page
        before = git("stash", "list").stdout
        git("stash", "-q")
        stashed = git("stash", "list").stdout != before
        if git("rebase", "-q", "origin/main").returncode:
            git("rebase", "--abort")
            if stashed:
                git("stash", "pop", "-q")
            print("pagefile: could not take the newer page from main; deploying this run's")
            return page
        if stashed and git("stash", "pop", "-q").returncode:
            # a clash: main's code in src/, the run's fresh data everywhere else
            for f in git("diff", "--name-only", "--diff-filter=U").stdout.split():
                git("checkout", "--ours" if f.startswith("src/") else "--theirs", "--", f)
            git("reset", "-q")
            git("stash", "drop", "-q")
            print("pagefile: the run's writes clashed with main's; main's code kept, the run's data kept")
        print("pagefile: took the newer page from main before deploying")
        return read()
    except Exception as e:
        print("pagefile: catch-up skipped:", e)
        return page


def deployable(page):
    """The page wrapped as site/index.html, written ready to deploy.

       It is stamped with the moment it was built, and the same stamp is
       written to site/build.txt. The page asks for that file every minute and
       reloads itself when it has changed, so a new version reaches a phone
       that is already open without anybody pulling to refresh
       (Jose, Sep 19, 2026: "I don't want to have to refresh the page")."""
    page = catch_up(page)
    code, data = stamps(page)
    page = page.replace("__BUILD__", code).replace("__DATA__", data)
    # a third stamp for the injury report and the lineups: the page reads
    # them again only when the sweep has written new ones (Sep 29, 2026)
    import hashlib
    h = hashlib.sha1()
    for f in ("alerts.json", "lineups.json"):
        try:
            h.update(open(os.path.join(D, "site", f), "rb").read())
        except OSError:
            pass
    files = "%014d" % (int(h.hexdigest(), 16) % 10 ** 14)
    schedule(page)
    open(os.path.join(D, "site", "build.txt"), "w").write(code + "\n" + data + "\n" + files + "\n")
    open(os.path.join(D, "site", "index.html"), "w").write(
        DOC + page + "\n</body>\n</html>\n")
