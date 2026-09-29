"""One door in and out of master.html.

   Every run that changes the page reads the whole file, edits the string it
   is holding, and writes the whole file back. So a run that started before an
   edit was saved will put the file back the way it was, with no error and
   nothing in the log. On Sep 17, 2026 that ate the same edit twice and made a
   deploy ship a call to a function that did not exist.

   The guard is one line of arithmetic: before writing, read the file again.
   If it is not byte for byte what this run started from, somebody else has
   written since, and this run's copy is stale, so it does not write. Nothing
   is lost by skipping -- the next wake reads the new file and does the same
   work on it.

   Usage:

       import pagefile
       s = pagefile.read()
       ...                       # edit the string
       if not pagefile.write(s, was=pagefile.LAST):
           print("page changed under us, not written")
           return

   (Jose, Sep 17, 2026)
"""
import os
import re
import time

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(D, "master.html")
LAST = None          # what the last read() returned, for the usual one-read run


def read():
    """The page as it is now, remembered so write() can check it is unchanged."""
    global LAST
    LAST = open(PAGE).read()
    return LAST


def write(new, was=None):
    """Write the page, unless it has changed since it was read.

       Answers True when it wrote and False when it stood down."""
    global LAST
    if was is None:
        was = LAST
    if was is None:
        raise ValueError("pagefile.write needs the text this run started from")
    if open(PAGE).read() != was:
        return False
    open(PAGE, "w").write(new)
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


def deployable(page):
    """The page wrapped as site/index.html, written ready to deploy.

       It is stamped with the moment it was built, and the same stamp is
       written to site/build.txt. The page asks for that file every minute and
       reloads itself when it has changed, so a new version reaches a phone
       that is already open without anybody pulling to refresh
       (Jose, Sep 19, 2026: "I don't want to have to refresh the page")."""
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
