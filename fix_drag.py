"""The pull on a sheet moves the sheet, not the page behind it.

   On iOS, preventDefault inside a pointermove does not stop Safari scrolling
   — only touch-action, or preventDefault on a non-passive touchmove, will.
   QB Spy never met this because its whole shell is overflow:hidden and the
   document cannot scroll at any time; this page scrolls normally, so the
   gesture was being taken by the page before the sheet ever saw it.

   Three things, so it does not depend on any one of them:
     touch-action: none on the sheet, with the scrolling middle handed back
     pan-y; overscroll-behavior so a scroll that reaches the end of the middle
     does not carry on into the page; and a touchmove of our own that refuses
     the default while a pull is actually happening.
"""
D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------------------ CSS ----
once("""    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.62);
    overflow: hidden;
  }""",
     """    box-shadow: 0 18px 60px rgba(0, 0, 0, 0.62);
    overflow: hidden;
    /* the gesture belongs to the sheet, not to the page under it */
    touch-action: none;
    overscroll-behavior: contain;
  }""", "the sheet box")

once("""  .sheet__scroll {
    flex: 1 1 auto; min-height: 0; overflow-y: auto;
    -webkit-overflow-scrolling: touch; padding: 10px 14px 14px;
  }""",
     """  .sheet__scroll {
    flex: 1 1 auto; min-height: 0; overflow-y: auto;
    -webkit-overflow-scrolling: touch; padding: 10px 14px 14px;
    /* the middle still scrolls, and stops rather than dragging the page */
    touch-action: pan-y;
    overscroll-behavior: contain;
  }""", "the scrolling middle")

once("  body.sheeted { position: fixed; left: 0; right: 0; width: 100%; overflow: hidden; }",
     "  body.sheeted { position: fixed; left: 0; right: 0; width: 100%; overflow: hidden;\n"
     "    overscroll-behavior: none; }", "the held page")

# ------------------------------------------------------------------- JS ----
# a touchmove is the one refusal iOS honours, so the pull says no there too
once("""    document.addEventListener("pointercancel", function () {
      if (sheet && pulling) settle("back"); else sheet = null;
    }, { passive: true });""",
     """    document.addEventListener("pointercancel", function () {
      if (sheet && pulling) settle("back"); else sheet = null;
    }, { passive: true });

    /* Safari does not treat a pointermove's preventDefault as a refusal to
       scroll; a non-passive touchmove is the one it honours. */
    document.addEventListener("touchmove", function (e) {
      if (pulling && e.cancelable) e.preventDefault();
    }, { passive: false });""", "the pull handlers")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("the pull is the sheet's now | prices:", s.count("data-oid"))
