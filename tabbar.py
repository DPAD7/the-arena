"""The sports move to the bottom, where a thumb is.

   Three rails stacked in the header cost about a third of a phone screen
   before a single card appeared. The sport is the thing you switch most and
   the thing you switch with one hand, so it becomes a tab bar: fixed to the
   bottom, icon over label, the way an app does it. The day and the week stay
   up top, where you read them.

   The slip already lives down there, so it is lifted to sit above the tabs
   rather than across them.
"""
import os
import re

D = os.path.dirname(os.path.abspath(__file__))
s = open(D + "/master.html").read()


def once(old, new, what=""):
    global s
    assert s.count(old) == 1, "%s: found %d" % (what or old[:40], s.count(old))
    s = s.replace(old, new, 1)


# ------------------------------------------------------- out of the head ---
once('    <div class="sportbar" id="sportbar" role="tablist" aria-label="Sport"></div>\n', "")
once('<dialog class="sheet" id="slipsheet"',
     '<nav class="tabbar" id="sportbar" role="tablist" aria-label="Sport"></nav>\n'
     '<dialog class="sheet" id="slipsheet"')

# ------------------------------------------------------------------ style ---
once("""  /* the sports, as pills under the weeks */
  .sportbar {
    grid-column: 1 / -1; display: flex; gap: 8px; overflow-x: auto;
    scrollbar-width: none; padding: 8px 14px 4px; margin: 0 -14px;
  }
  .sportbar::-webkit-scrollbar { display: none; }
  .sptab {
    flex: none; display: inline-flex; align-items: center; gap: 6px;
    appearance: none; cursor: pointer;
    background: rgba(255, 255, 255, 0.05); border: 1px solid var(--edge);
    border-radius: 999px; padding: 6px 13px;
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 13px; letter-spacing: 0.08em;
    text-transform: uppercase; color: var(--muted); white-space: nowrap;
  }
  .sptab img { width: 15px; height: 15px; display: block; }
  .sptab[aria-selected="true"] {
    color: #10161f; background: var(--amber); border-color: var(--amber);
  }
  .sptab:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; }""",
     """  /* the sports, along the bottom, where a thumb is */
  .tabbar {
    position: fixed; left: 0; right: 0; bottom: 0; z-index: 40;
    display: flex; align-items: stretch;
    padding: 6px 4px calc(4px + env(safe-area-inset-bottom));
    background: rgba(9, 26, 49, 0.72);
    -webkit-backdrop-filter: blur(18px) saturate(1.4);
    backdrop-filter: blur(18px) saturate(1.4);
    border-top: 1px solid rgba(255, 255, 255, 0.14);
  }
  .sptab {
    flex: 1 1 0; display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 3px;
    appearance: none; background: none; border: 0; cursor: pointer;
    padding: 6px 2px 4px; color: var(--muted);
    font-family: "Barlow Condensed", "Arial Narrow", sans-serif;
    font-weight: 700; font-size: 11.5px; letter-spacing: 0.12em;
    text-transform: uppercase; white-space: nowrap;
  }
  .sptab img { width: 21px; height: 21px; display: block; opacity: 0.62; }
  .sptab .allmk {
    width: 21px; height: 21px; display: grid; place-items: center;
    font-size: 15px; line-height: 1; opacity: 0.62;
  }
  .sptab[aria-selected="true"] { color: var(--amber); }
  .sptab[aria-selected="true"] img,
  .sptab[aria-selected="true"] .allmk { opacity: 1; }
  .sptab:focus-visible { outline: 2px solid var(--amber); outline-offset: -3px; }""",
     "the sport pills")

# the slip sits above the tabs, and the page ends above both
once("""  .slipbar {
    position: fixed; left: 0; right: 0; bottom: 0;""",
     """  .slipbar {
    position: fixed; left: 0; right: 0; bottom: calc(62px + env(safe-area-inset-bottom));""",
     "the slip bar")
once("  body { padding-block: 20px 76px; padding-inline: 12px; }",
     "  body { padding-block: 20px calc(150px + env(safe-area-inset-bottom));\n"
     "         padding-inline: 12px; }", "the body padding")

# ------------------------------------------------------------------- JS -----
once("""    t.innerHTML = (sp.ico ? '<img src="' + sp.ico + '" alt="">' : "") + sp.label;""",
     """    t.innerHTML = (sp.ico ? '<img src="' + sp.ico + '" alt="">'
                          : '<span class="allmk">\\u25C9</span>') +
                  "<span>" + sp.label + "</span>";""", "the pill contents")

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("sports moved to the bottom")
