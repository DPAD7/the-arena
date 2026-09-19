"""The clips ESPN's page shows but its API withholds.

   For the Bengals game the API lists five clips and the page lists six; the
   one it drops is the only touchdown pass in the game. Nothing distinguishes
   the six -- same type, same origination, all syndicatable -- the feed simply
   is not indexed to the game for that one. The page is server-rendered with
   every clip embedded, and it answers 202 with an empty body to anything that
   is not a real browser. So it is read out of a tab Jose already has open,
   the way bet365 is.

   Each id is then filled in from ESPN's watch graph (public key, plain GET),
   which hands back the playable source, and written to site/clips.json in the
   exact shape the board's clip list already uses, so the page concatenates
   them with no adapter.

   Usage:  python3 page_clips.py            (played games not yet pulled)
           python3 page_clips.py --force    (everything again)
           python3 page_clips.py nfl        (one league)
   Uses Chrome window 1 from tab 3 on; --tabs=N loads N pages at once (default 4).
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

sys.path.insert(0, "/Users/joe/qbspy/build")
from read_bet365 import in_tab
try:
    from curl_cffi import requests as rq
except ImportError:
    import requests as rq

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, "site", "clips.json")
WIN, TAB = 1, 3
KEY = "d15c5790-7cb0-4fe1-8782-25f4698d0739"
FORCE = "--force" in sys.argv
ONLY = [a for a in sys.argv[1:] if a in ("nfl", "college-football")]

GRAB = """
(function () {
  var s = "";
  [].slice.call(document.scripts).forEach(function (x) {
    var t = x.textContent || "";
    if (t.indexOf('"vids":[') >= 0 && t.length > s.length) s = t;
  });
  s = s.replace(/\\\\"/g, '"');
  var out = {}, re = /"id":"(\\d{7,9})","description":"([^"]{0,120})"/g, m;
  while ((m = re.exec(s))) if (!out[m[1]]) out[m[1]] = m[2];
  return JSON.stringify(out);
})()
"""


def played():
    s = open(os.path.join(D, "master.html")).read()
    now = dt.datetime.now(dt.timezone.utc)
    out = []
    for lg, var in (("nfl", "SCHED"), ("college-football", "CFB")):
        if ONLY and lg not in ONLY:
            continue
        arr = json.loads(re.search(r'var %s = (\[\[.*?\]\]);' % var, s, re.S).group(1))
        for g in arr:
            if dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")) < now:
                out.append((lg, g[1], g[3] + "/" + g[4]))
    return out


TABS = int(next((a.split("=")[1] for a in sys.argv if a.startswith("--tabs=")), "4"))


def ensure_tabs(n):
    """Enough tabs after the board's to load n pages side by side."""
    have = int(subprocess.run(["osascript", "-e",
                               'tell application "Google Chrome" to count tabs of window %d' % WIN],
                              capture_output=True, text=True).stdout.strip() or "0")
    while have < TAB + n - 1:
        subprocess.run(["osascript", "-e",
                        'tell application "Google Chrome" to make new tab at end of tabs of window %d '
                        'with properties {URL:"about:blank"}' % WIN],
                       capture_output=True, text=True)
        have += 1


def load(tab, lg, eid):
    subprocess.run(["osascript", "-e",
                    'tell application "Google Chrome" to set URL of tab %d of window %d to '
                    '"https://www.espn.com/%s/video/_/gameId/%s"' % (tab, WIN, lg, eid)],
                   capture_output=True, text=True)


def read(tab):
    for _ in range(5):
        got = in_tab(WIN, tab, GRAB)
        try:
            ids = json.loads(got or "{}")
        except ValueError:
            ids = {}
        if ids:
            return ids
        time.sleep(3)
    return {}


def page_ids_batch(games):
    """Load up to TABS pages at once, wait once, read them all."""
    ensure_tabs(len(games))
    for i, (lg, eid, _) in enumerate(games):
        load(TAB + i, lg, eid)
    time.sleep(9)
    return [read(TAB + i) for i in range(len(games))]


def vod(vid):
    q = ('{ VOD(id:"%s",countryCode:"US",languageCode:"en",deviceType:SETTOP,tz:"Z") '
         '{ id name coverageType originalPublishDate duration source { url } } }' % vid)
    r = rq.get("https://watch.graph.api.espn.com/api?apiKey=%s&query=%s"
               % (KEY, urllib.parse.quote(q)), impersonate="chrome124", timeout=40)
    v = ((r.json().get("data") or {}).get("VOD")) or {}
    src = ((v.get("source") or {}).get("url")) or ""
    # the mp4 sits at a predictable path beside the HLS playlist
    m = re.search(r"/wsc/(\d{4}/\d{4})/([0-9a-f-]{36})/", src)
    mp4 = ""
    if m:
        cand = ("https://espnmedia-cdn.akamaized.net/espn/media/16x9/wsc/%s/%s/%s.mp4"
                % (m.group(1), m.group(2), m.group(2)))
        try:
            if rq.head(cand, impersonate="chrome124", timeout=30).status_code == 200:
                mp4 = cand
        except Exception:
            pass
    if not v.get("id"):
        return None
    return {"id": int(v["id"]), "headline": v.get("name") or "",
            "originalPublishDate": v.get("originalPublishDate"),
            "duration": v.get("duration"),
            "tracking": {"coverageType": v.get("coverageType")},
            "links": {"source": {"href": mp4 or src}}}


def main():
    have = json.load(open(OUT)) if os.path.exists(OUT) else {}
    todo = [g for g in played() if FORCE or g[1] not in have]
    print("played games: %d   to pull: %d" % (len(played()), len(todo)))
    for k in range(0, len(todo), TABS):
        batch = todo[k:k + TABS]
        got = page_ids_batch(batch)
        for (lg, eid, name), ids in zip(batch, got):
            clips = []
            for vid in ids:
                rec = vod(vid)
                if rec:
                    clips.append(rec)
            have[eid] = clips
            print("  %-16s %-10s page %2d  filled %2d" % (name, eid, len(ids), len(clips)))
        json.dump(have, open(OUT, "w"), indent=0)
    print("games in clips.json: %d" % len(have))


if __name__ == "__main__":
    main()
