"""Cut master.html into the parts under src/ (once, Sep 30, 2026).

   The page is one 19,000-line file; the parts are consecutive slices of it,
   cut at lines that appear once in the page (the style tags, a handful of
   function heads), so pagefile can join them back byte for byte and cut a
   written page at the same lines again. src/parts.json is the list, in
   order: each part's file and the exact line it starts on (the first part
   starts at the top).

       python3 build/split_page.py          cuts master.html into src/
"""
import json
import os
import re
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(D, "src")
PARTS = [
    ("00-boot.html", None),
    ("10-styles.css", "<style>"),
    ("20-markup.html", "</style>"),
    ("30-app-1.js", "  function fsAny(row) {"),
    ("31-app-2.js", "  function started(card) {"),
    ("32-app-3.js", "  function toDecOdds(o) {"),
    ("33-app-4.js", "  function clubRecOf(r) {"),
    ("34-app-5.js", "  function openingDay(list) {"),
    ("35-app-6.js", "  function inBout(card, sel) {"),
    ("36-app-7.js", "  function nextLook() {"),
    ("40-search.js", None),          # the third script: its first function line, found below
]


def main():
    page = open(os.path.join(D, "master.html")).read()
    lines = page.split("\n")
    # the last part starts at the first function line of the third script
    third = max(i for i, l in enumerate(lines) if l == "<script>")
    fn = next(i for i in range(third, len(lines))
              if re.match(r"^ {2,4}function [A-Za-z0-9_]+\(", lines[i]) and lines.count(lines[i]) == 1)
    parts = [(f, a) for f, a in PARTS]
    parts[-1] = (parts[-1][0], lines[fn])
    starts = [0]
    for f, a in parts[1:]:
        hits = [i for i, l in enumerate(lines) if l == a]
        if len(hits) != 1:
            print("anchor not unique: %r %s" % (a, hits)); return 1
        starts.append(hits[0])
    if starts != sorted(starts):
        print("anchors out of order"); return 1
    os.makedirs(SRC, exist_ok=True)
    out = []
    for k, (f, a) in enumerate(parts):
        lo = starts[k]
        hi = starts[k + 1] if k + 1 < len(parts) else len(lines)
        text = "\n".join(lines[lo:hi]) + ("\n" if k + 1 < len(parts) else "")
        open(os.path.join(SRC, f), "w").write(text)
        out.append({"file": f, "at": a, "lines": hi - lo})
    json.dump(out, open(os.path.join(SRC, "parts.json"), "w"), indent=1)
    joined = "".join(open(os.path.join(SRC, p["file"])).read() for p in out)
    print("identical:", joined == page, "|", ", ".join("%s %d" % (p["file"], p["lines"]) for p in out))
    return 0 if joined == page else 1


if __name__ == "__main__":
    sys.exit(main())
