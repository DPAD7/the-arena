"""The number is the mark.

   There was a tick on the bar and a number under it, which is the same thing
   said twice — the number can stand where the tick stood. It sits on the bar
   at its own place on the scale, punched out of the track so it reads over
   the fill as well as over the empty part, and it carries the color: white
   until the game says otherwise, green once he is past it, red once the game
   has ended without it.

   That also gives back the strip under the bar the old labels were using.
"""
D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()


def once(old, new, what):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what, s.count(old))
    s = s.replace(old, new, 1)


once("""  .ntick {
    position: absolute; top: -4px; bottom: -4px; width: 2px;
    margin-left: -1px; margin-right: -1px;
    background: rgba(255, 255, 255, 0.85); border-radius: 1px;
    color: rgba(255, 255, 255, 0.85);
  }
  .ntick b {
    position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
    margin-top: 3px; font-size: 12px; font-weight: 700; line-height: 1;
    color: currentColor; font-variant-numeric: tabular-nums;
  }
  .ntick.hit { background: var(--green); color: var(--green); }
  .ntick.miss { background: #e2564d; color: #e2564d; }""",
     """  /* the number stands where the tick stood, punched out of the track so it
     reads over the fill and over the empty part alike */
  .ntick {
    position: absolute; top: 50%; width: 0;
    color: rgba(255, 255, 255, 0.9);
  }
  .ntick b {
    position: absolute; left: 0; top: 0; transform: translate(-50%, -50%);
    padding: 2px 4px; border-radius: 5px;
    background: var(--panel); box-shadow: 0 0 0 2px var(--panel);
    font-size: 12px; font-weight: 700; line-height: 1;
    font-variant-numeric: tabular-nums; color: currentColor;
  }
  .ntick.hit { color: var(--green); }
  .ntick.miss { color: #e2564d; }""", "the tick styling")

# the strip the old labels sat in is no longer needed
once("  .ptdx--v2 { padding-bottom: 54px; }", "  .ptdx--v2 { padding-bottom: 44px; }",
     "the v2 bottom band")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("the number is the mark now")
