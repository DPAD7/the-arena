"""Each fighter's own face, found the only way ESPN offers it.

   The MMA scoreboard names a fighter and stops -- no athlete id, no headshot,
   which is why the ids on our fight rows were empty. ESPN's search does carry
   both, so every name on the board is looked up once and the id written down
   beside it. A headshot that does not answer is left out rather than shown as
   a broken box.

   Writes faces.json: written name -> athlete id.
"""
import concurrent.futures as cf
import json
import os
import re
import subprocess
import urllib.parse

D = os.path.dirname(os.path.abspath(__file__))
SEARCH = "https://site.web.api.espn.com/apis/search/v2?query=%s&limit=8"
SHOT = "https://a.espncdn.com/i/headshots/mma/players/full/%s.png"


def look(name):
    out = subprocess.run(
        ["curl", "-s", "-m", "25", SEARCH % urllib.parse.quote(name)],
        capture_output=True, text=True).stdout
    try:
        d = json.loads(out or "{}")
    except Exception:
        return name, None
    for r in d.get("results") or []:
        for it in r.get("contents") or []:
            if it.get("type") != "player":
                continue
            link = ((it.get("link") or {}).get("web") or "")
            if "/mma/" not in link:
                continue
            if (it.get("displayName") or "").strip().lower() != name.strip().lower():
                continue
            m = re.search(r"/id/(\d+)/", link)
            if m:
                return name, m.group(1)
    return name, None


def shows(aid):
    code = subprocess.run(
        ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "-m", "20", SHOT % aid],
        capture_output=True, text=True).stdout
    return aid, code == "200"


s = open(D + "/master.html").read()
m = re.search(r'  var FIGHTS = (\[\[.*?\]\]);\n', s, re.S)
fights = json.loads(m.group(1))
names = sorted({f[3] for f in fights} | {f[5] for f in fights})
names = [n for n in names if n and "TBA" not in n and "TBD" not in n]
print("fighters to look up: %d" % len(names))

found = {}
with cf.ThreadPoolExecutor(max_workers=10) as pool:
    for nm, aid in pool.map(look, names):
        if aid:
            found[nm] = aid
print("with an ESPN record: %d" % len(found))

ok = {}
with cf.ThreadPoolExecutor(max_workers=12) as pool:
    for aid, good in pool.map(shows, sorted(set(found.values()))):
        ok[aid] = good
faces = {n: a for n, a in found.items() if ok.get(a)}
print("with a headshot that answers: %d" % len(faces))
json.dump(faces, open(D + "/faces.json", "w"), indent=1, sort_keys=True)

for f in fights:
    f[4] = faces.get(f[3], "")
    f[6] = faces.get(f[5], "")
both = sum(1 for f in fights if f[4] and f[6])
print("fights with both faces: %d of %d" % (both, len(fights)))
s = s[:m.start()] + "  var FIGHTS = " + json.dumps(fights, separators=(",", ":")) + ";\n" + s[m.end():]

# ------------------------------------------------------------------ style ---
old = "  .mmaname {"
new = """  .ffab {
    width: 30px; height: 30px; border-radius: 10px; object-fit: cover;
    object-position: top center; background: #0d1a2b;
    border: 2px solid var(--edge); display: block; flex: none;
  }
  .mmaname {"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

# ------------------------------------------------------------- the frame ---
old = """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      priceSlot(f[8], f[9]) + '</span>' + lastName(f[3]) + '</span>' +
      '<span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + lastName(f[5]) + '<span class="gml">' +
      priceSlot(f[10], f[11]) + '</span></span></div>' +"""
new = """      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      priceSlot(f[8], f[9]) + '</span>' + mug(f[4]) + lastName(f[3]) + '</span>' +
      '<span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + mug(f[6]) + lastName(f[5]) + '<span class="gml">' +
      priceSlot(f[10], f[11]) + '</span></span></div>' +"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

old = "  function lastName(n) {"
new = """  /* a face where ESPN has one; nothing where it does not */
  function mug(id) {
    if (!id) return "";
    return '<img class="ffab" alt="" src="https://a.espncdn.com/i/headshots/' +
           'mma/players/full/' + id + '.png">';
  }
  function lastName(n) {"""
assert s.count(old) == 1
s = s.replace(old, new, 1)

# the head needs to sit its picture beside the name
s = s.replace("  .gteam:has(.glogo) { display: inline-flex; align-items: center; gap: 8px; }",
              "  .gteam:has(.glogo), .gteam:has(.ffab) {\n"
              "    display: inline-flex; align-items: center; gap: 8px;\n  }", 1)

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
