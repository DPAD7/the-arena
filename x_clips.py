"""The touchdowns neither ESPN nor NFL.com cut a clip of -- the clubs did.

   theScore's recap page for a game embeds every post from the two clubs'
   accounts and @NFL, newest first, one page at a time; it answers a plain
   fetch. Each post is then resolved through X's own embed endpoint (no key)
   for its created time, its account and its video file, which sits on
   video.twimg.com with CORS open and does not expire.

   A club posts its touchdown within about two minutes of the play, so the
   join is the play's wallclock from ESPN against the post's time: nearest
   post with video by the scoring club or @NFL inside a short window, each
   post used once. No name matching anywhere.

   Games are joined to theScore's ids on kickoff date and the two clubs'
   abbreviations, through club_name where the spellings differ.

   Usage:  python3 x_clips.py           (played games not yet pulled)
           python3 x_clips.py --force
"""
import datetime as dt
import json
import os
import re
import sqlite3
import sys
import time

try:
    from curl_cffi import requests as rq
except ImportError:
    import requests as rq

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, "site", "xindex.json")
FORCE = "--force" in sys.argv
HANDLES = {k: v["x"].lower() for k, v in json.load(open(os.path.join(D, "clubs.json"))).items()}   # from nfl.com's team pages
WINDOW = 7 * 60           # the good matches all land inside seven minutes
FLOOR = 20                # nobody cuts and posts a clip faster than this
SHORTEST = 5              # only the four-second cards are known graphics; length alone proves nothing else
PINS = os.path.join(D, "x_pins.json")   # {espn event id: {scoring line: post id}} settled by hand
# a post about something else that happens to land after the touchdown
NOT_A_TD = re.compile(r"sack|strip|recover|intercept|\bint\b|takeaway|our ball|\bpick|stop|fumble|punt|field goal|\bfg\b|\+3|convert|first down|return|red zone|two.point|2.pt|\bpat\b|extra point"
                      r"|budlight|bud light|celly|celebrat", re.I)   # the sponsored post is the celebration, not the play
# a score line with a clock is the score-bug graphic, not the play:
# "Touchdown Irish! Notre Dame 14, Rice 0 | 10:36 1st"
SCOREBUG = re.compile(r"[A-Za-z.'&]+ \d{1,2}, [A-Za-z.'& ]+ \d{1,2}\s*\|?\s*\d{0,2}:?\d{0,2}")
SHORT = 12               # a play runs longer than a graphic; below this it loses to a longer post
# the play itself is posted with the broadcaster's credit
FOOTAGE = re.compile(r"\U0001F4FA|\b(on|via) (fox|cbs|nbc|espn|abc|prime|netflix|nfl\+|nfl network)\b|#\w+vs\w+|\bfox\b|\bcbs\b|\bnbc\b", re.I)
CACHE = os.path.join(D, "site", "xposts.json")   # every post resolved, so a rerun costs nothing


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def in_game(at, kick):
    """ESPN's wallclock is sometimes a whole day off for part of a game
       (SF/LAR's first half is stamped the day after its kickoff). The time
       of day is right, so slide it by days until it sits inside the game."""
    day = dt.timedelta(days=1)
    while at - kick > dt.timedelta(hours=6):
        at -= day
    while at < kick - dt.timedelta(hours=1):
        at += day
    return at


def get(u, **kw):
    last = None
    for attempt in range(3):
        try:
            return rq.get(u, impersonate="chrome124", timeout=45, **kw)
        except Exception as e:   # a timeout mid-run used to lose the whole pull
            last = e
            time.sleep(2 + 3 * attempt)
    raise last


def played():
    s = open(os.path.join(D, "master.html")).read()
    now = dt.datetime.now(dt.timezone.utc)
    arr = json.loads(re.search(r'var SCHED = (\[\[.*?\]\]);', s, re.S).group(1))
    return [g for g in arr if T(g[2]) < now]


def score_abbr():
    """theScore's spelling of each club, from the register; ESPN's is the key."""
    db = sqlite3.connect("/Users/joe/qbspy/data/qbspy.db")
    out = {}
    for written, abbr, src in db.execute("select written, abbr, source from club_name"):
        if "score" in (src or "") and len(written) <= 4 and written.isupper():
            out.setdefault(abbr, written)
    return out


def score_events(day):
    ev = get("https://api.thescore.com/nfl/events?game_date=" + day).json()
    return ev if isinstance(ev, list) else (ev.get("events") or [])


def tweet_ids(score_id, kickoff):
    """Walk the recap back in time until the posts predate kickoff."""
    ids, page = [], 1
    while page <= 12:
        h = get("https://www.thescore.com/nfl/event/%d/recap?page=%d" % (score_id, page)).text
        found = re.findall(r'(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/(\d{15,})', h)
        if not found:
            break
        ids += found
        # snowflake ids carry their time: id >> 22 is ms since the X epoch
        oldest = min(int(i) for i in found)
        when = dt.datetime.fromtimestamp((oldest >> 22) / 1000 + 1288834974.657, dt.timezone.utc)
        if when < kickoff - dt.timedelta(hours=1):
            break
        page += 1
    return sorted(set(ids))


def tok(i):
    n = int(i)
    return format(n / 1e15 * 3.14159265, ".16f").replace("0.", "").replace(".", "").rstrip("0")[:12]


def resolve(i, cache):
    if i in cache:
        return cache[i]
    cache[i] = resolve_(i)
    return cache[i]


def resolve_(i):
    r = get("https://cdn.syndication.twimg.com/tweet-result?id=%s&token=%s" % (i, tok(i)))
    if r.status_code != 200:
        return None
    j = r.json()
    best, dur, w, h = None, 0, 0, 0
    for m in (j.get("mediaDetails") or []):
        vi = m.get("video_info") or {}
        vs = [v for v in vi.get("variants", []) if "mp4" in (v.get("content_type") or "")]
        if vs:
            best = max(vs, key=lambda v: v.get("bitrate") or 0).get("url")
            dur = (vi.get("duration_millis") or 0) / 1000.0
            oi = m.get("original_info") or {}
            w, h = oi.get("width") or 0, oi.get("height") or 0
    if not best:
        vs = [v for v in ((j.get("video") or {}).get("variants") or []) if "mp4" in (v.get("type") or "")]
        if vs:
            best = vs[-1].get("src")
    if not best:
        return None
    return {"id": i, "user": ((j.get("user") or {}).get("screen_name") or "").lower(),
            "at": j.get("created_at"), "text": (j.get("text") or "").split("http")[0].strip(), "src": best,
            "dur": dur, "w": w, "h": h}


def main():
    have = json.load(open(OUT)) if os.path.exists(OUT) else {}
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    games = [g for g in played() if FORCE or g[1] not in have]
    print("played games: %d   to pull: %d" % (len(played()), len(games)))
    sa = score_abbr()
    ev_by_day = {}
    for g in games:
        eid, kick, away, home = g[1], T(g[2]), g[3], g[4]
        day = (kick - dt.timedelta(hours=5)).strftime("%Y-%m-%d")       # the game's own calendar day, US time
        if day not in ev_by_day:
            ev_by_day[day] = score_events(day)
        hit = [e for e in ev_by_day[day]
               if ((e.get("away_team") or {}).get("abbreviation") in (away, sa.get(away))
                   and (e.get("home_team") or {}).get("abbreviation") in (home, sa.get(home)))]
        if len(hit) != 1:
            print("  %-9s theScore event not settled (%d)" % (away + "/" + home, len(hit)))
            continue
        sid = hit[0]["id"]
        d = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=%s" % eid).json()
        pl = get("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/events/%s/competitions/%s/plays?limit=400" % (eid, eid)).json()
        when = {str(p.get("id")): p.get("wallclock") for p in (pl.get("items") or []) if p.get("wallclock")}
        tds = []
        for p in (d.get("scoringPlays") or []):
            m = re.match(r"^(.+?) (\d+) Yd pass from ([^(]+)", p.get("text") or "")
            if m and when.get(str(p.get("id"))):
                club = ((p.get("team") or {}).get("abbreviation") or "").lower()
                tds.append({"text": p["text"], "at": in_game(T(when[str(p["id"])]), kick), "club": club,
                            "who": m.group(1).split()[-1].lower()})
        ids = tweet_ids(sid, kick)
        posts = []
        for i in ids:
            fresh = i not in cache
            r = resolve(i, cache)
            if r:
                posts.append(r)
            if fresh:
                time.sleep(0.15)
        json.dump(cache, open(CACHE, "w"), separators=(",", ":"))
        allowed = {HANDLES.get(away.lower(), ""), HANDLES.get(home.lower(), ""), "nfl"}
        rows, used = [], set()
        pinned = (json.load(open(PINS)) if os.path.exists(PINS) else {}).get(eid, {})
        for td in tds:
            if td["text"] in pinned:
                p = next((q for q in posts if q["id"] == pinned[td["text"]]), None) or resolve(pinned[td["text"]], cache)
                if p:
                    used.add(p["id"])
                    rows.append({"text": td["text"], "src": p["src"], "headline": "@" + p["user"] + ": " + p["text"][:90],
                                 "id": p["id"], "gap": int((T(p["at"]) - td["at"]).total_seconds())})
                    continue
            own = HANDLES.get(td["club"], "")
            cands = []
            for p in posts:
                # only the scoring club or the league post a club's touchdown
                if p["id"] in used or p["user"] not in (own, "nfl") or NOT_A_TD.search(p["text"]) or SCOREBUG.search(p["text"]):
                    continue
                # footage is landscape and runs a while; a graphic is square and short
                if p.get("dur", 0) < SHORTEST or p.get("w", 0) <= p.get("h", 0):
                    continue
                gap = (T(p["at"]) - td["at"]).total_seconds()
                if FLOOR <= gap <= WINDOW:
                    # the club posts the play first and the follow-ups after it
                    footage = 0 if FOOTAGE.search(p["text"]) else 1
                    graphic = 1 if SCOREBUG.search(p["text"]) else 0
                    short = 1 if p.get("dur", 0) < SHORT else 0
                    cands.append((graphic, footage, short, gap, p))
            cands.sort(key=lambda x: x[:4])
            if cands:
                p = cands[0][4]
                used.add(p["id"])
                rows.append({"text": td["text"], "src": p["src"], "headline": "@" + p["user"] + ": " + p["text"][:90],
                             "id": p["id"], "gap": int(cands[0][3])})
        have[eid] = rows
        json.dump(have, open(OUT, "w"), separators=(",", ":"))
        print("  %-9s theScore %-7s posts %3d (video %3d)  touchdown passes %d  matched %d"
              % (away + "/" + home, sid, len(ids), len(posts), len(tds), len(rows)))
    print("games in xindex.json: %d" % len(have))


if __name__ == "__main__":
    main()
