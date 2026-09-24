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


def deployable(page):
    """The page wrapped as site/index.html, written ready to deploy.

       It is stamped with the moment it was built, and the same stamp is
       written to site/build.txt. The page asks for that file every minute and
       reloads itself when it has changed, so a new version reaches a phone
       that is already open without anybody pulling to refresh
       (Jose, Sep 19, 2026: "I don't want to have to refresh the page")."""
    stamp = time.strftime("%Y%m%d%H%M%S", time.gmtime())
    page = page.replace("__BUILD__", stamp)
    open(os.path.join(D, "site", "build.txt"), "w").write(stamp + "\n")
    open(os.path.join(D, "site", "index.html"), "w").write(
        DOC + page + "\n</body>\n</html>\n")
