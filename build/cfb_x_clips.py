"""College touchdowns from the programs' own X posts, for the covered programs.

   theScore's NCAAF event page (thescore.com/ncaaf/event/{id}?page=N) embeds
   the two programs' X feeds, newest first, more per page as N grows. The
   posts are matched to the covered side's scoring plays exactly as the NFL
   puller does it (x_clips.py): the post's time against the play's wallclock,
   footage over graphics, the earliest such post. Only posts whose id-time
   falls inside the window after some touchdown are ever resolved.

   Both rows are served: the passes he threw (PTD) and the scores he made
   himself (ATD), so a run by the quarterback is matched like a pass.

   Usage:  python3 cfb_x_clips.py           (played games not yet pulled)
           python3 cfb_x_clips.py --force
"""
import datetime as dt
import email.utils
import json
import os
import re
import sys
import time
import unicodedata

import x_clips as X
from x_clips import T, get, in_game, resolve, FLOOR, WINDOW, SHORTEST, SHORT, NOT_A_TD, FOOTAGE, SCOREBUG

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "cfb_xindex.json")
CACHE = os.path.join(D, "site", "cfb_xposts.json")
FORCE = "--force" in sys.argv


def board():
    s = open(os.path.join(D, "master.html")).read()
    arr = json.loads(re.search(r'var CFB = (\[\[.*?\]\]);', s, re.S).group(1))
    ids = json.loads(re.search(r'var CFBID = (\{.*?\});', s, re.S).group(1))
    return arr, ids


def score_events():
    ev = get("https://api.thescore.com/ncaaf/events").json()
    ev = ev if isinstance(ev, list) else ev.get("events") or []
    out = {}
    for e in ev:
        # theScore writes its dates RFC-2822 ("Thu, 27 Aug 2026 22:00:00 -0000")
        gd = email.utils.parsedate_to_datetime(e["game_date"])
        day = (gd - dt.timedelta(hours=5)).strftime("%Y-%m-%d")
        out.setdefault(day, []).append(e)
    return out


def plain(x):
    return re.sub(r"[^a-z0-9]", "", str(x or "").lower())


def find_event(events, day, d, away, home):
    """theScore's abbreviations are not ESPN's (OU/OKLA, AFA/AF), so a game is
       settled on the day and the two schools' names as ESPN writes them."""
    comp = (d.get("header") or {}).get("competitions", [{}])[0]
    names = {}
    for c in comp.get("competitors") or []:
        t = c.get("team") or {}
        names[c.get("homeAway")] = {plain(t.get("location")), plain(t.get("displayName")), plain(t.get("name")), plain(t.get("abbreviation"))}
    for e in events.get(day, []):
        a, h = e.get("away_team") or {}, e.get("home_team") or {}
        aset = {plain(a.get("full_name")), plain(a.get("name")), plain(a.get("abbreviation")), plain(a.get("location")), plain(a.get("search_name"))}
        hset = {plain(h.get("full_name")), plain(h.get("name")), plain(h.get("abbreviation")), plain(h.get("location")), plain(h.get("search_name"))}
        if (aset & names.get("away", set()) - {""}) and (hset & names.get("home", set()) - {""}):
            return e["id"]
    return None


def post_ids(score_id, kick):
    """Every post id on the event page, walking pages until they predate kickoff."""
    ids, page = set(), 1
    while page <= 8:
        h = get("https://www.thescore.com/ncaaf/event/%d?page=%d" % (score_id, page)).text
        found = re.findall(r'(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/(\d{15,})', h)
        new = set(found) - ids
        if not new:
            break
        ids |= new
        oldest = min(int(i) for i in found)
        when = dt.datetime.fromtimestamp((oldest >> 22) / 1000 + 1288834974.657, dt.timezone.utc)
        if when < kick - dt.timedelta(hours=1):
            break
        page += 1
    return sorted(ids)


def snowflake_time(i):
    return dt.datetime.fromtimestamp((int(i) >> 22) / 1000 + 1288834974.657, dt.timezone.utc)


def lastname(full):
    t = [w for w in str(full or "").split() if w.rstrip(".").lower() not in ("jr", "sr", "ii", "iii", "iv")]
    return (t[-1] if t else "").lower()


def names(text, surname):
    """Does the post write this surname, as a word of its own? Accents dropped
       on both sides; 'Lee' must not be found inside 'Sleep'."""
    if not surname:
        return False
    t = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()
    n = unicodedata.normalize("NFKD", surname).encode("ascii", "ignore").decode().lower()
    return re.search(r"(?<![a-z])" + re.escape(n) + r"(?![a-z])", t) is not None


def main():
    have = json.load(open(OUT)) if os.path.exists(OUT) else {}
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    cover = {v["id"] for v in json.load(open(os.path.join(D, "data", "cfb_cover.json"))).values()}
    arr, ids = board()
    now = dt.datetime.now(dt.timezone.utc)
    games = [r for r in arr if T(r[2]) < now and (ids.get(r[3]) in cover or ids.get(r[4]) in cover)
             and (FORCE or r[1] not in have)]
    print("played covered games to pull: %d" % len(games))
    events = score_events()
    for r in games:
        eid, kick, away, home = r[1], T(r[2]), r[3], r[4]
        day = (kick - dt.timedelta(hours=5)).strftime("%Y-%m-%d")
        d = get("https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary?event=%s" % eid).json()
        sid = find_event(events, day, d, away, home)
        if not sid:
            print("  %-9s theScore event not settled" % (away + "/" + home))
            continue
        pl = get("https://sports.core.api.espn.com/v2/sports/football/leagues/college-football/events/%s/competitions/%s/plays?limit=400" % (eid, eid)).json()
        when = {str(p.get("id")): p.get("wallclock") for p in (pl.get("items") or []) if p.get("wallclock")}
        # the covered side's quarterback, both rows
        qbs = []
        if ids.get(away) in cover and r[5]:
            qbs.append(lastname(r[5]))
        if ids.get(home) in cover and r[7]:
            qbs.append(lastname(r[7]))
        tds = []
        for p in d.get("scoringPlays") or []:
            m = re.match(r"^(.+?) (\d+) Yd (Run|pass from ([^(]+))", p.get("text") or "")
            if not m or not when.get(str(p.get("id"))):
                continue
            scorer, run = m.group(1).strip(), m.group(3) == "Run"
            passer = scorer if run else m.group(4).strip()
            if not any(q and (q in passer.lower() or q in scorer.lower()) for q in qbs):
                continue
            tds.append({"text": p["text"], "at": in_game(T(when[str(p["id"])]), kick),
                        "who": lastname(scorer), "passer": None if run else lastname(passer)})
        pids = post_ids(sid, kick)
        # resolve only what could be a touchdown post
        want = [i for i in pids if any(FLOOR <= (snowflake_time(i) - td["at"]).total_seconds() <= WINDOW for td in tds)]
        posts = []
        for i in want:
            fresh = i not in cache
            p = resolve(i, cache)
            if p:
                posts.append(p)
            if fresh:
                time.sleep(0.15)
        json.dump(cache, open(CACHE, "w"), separators=(",", ":"))
        rows, used = [], set()
        for td in tds:
            cands = []
            for p in posts:
                # college: only a post carrying the broadcaster's credit is taken --
                # it is the play as aired; everything else the programs post is promo
                if p["id"] in used or NOT_A_TD.search(p["text"]) or SCOREBUG.search(p["text"]):
                    continue
                if p.get("dur", 0) < SHORTEST or p.get("w", 0) <= p.get("h", 0):
                    continue
                # the post must name the man who scored -- a clip of the right game at
                # the right minute that names nobody is a celebration, a promo or the
                # play before. Jose audited "Maiava first td is wrong" on Sep 15, 2026.
                if not names(p["text"], td["who"]):
                    continue
                gap = (T(p["at"]) - td["at"]).total_seconds()
                if FLOOR <= gap <= WINDOW:
                    # named the scorer (required above) -- then, in order: names both men,
                    # carries the broadcaster's credit, is not a short cut, came soonest
                    both = 0 if (not td["passer"] or names(p["text"], td["passer"])) else 1
                    cands.append((both, 0 if FOOTAGE.search(p["text"]) else 1, 1 if p.get("dur", 0) < SHORT else 0, gap, p))
            cands.sort(key=lambda x: x[:4])
            if cands:
                p = cands[0][4]
                used.add(p["id"])
                rows.append({"text": td["text"], "src": p["src"], "headline": "@" + p["user"] + ": " + p["text"][:90],
                             "id": p["id"], "gap": int(cands[0][3])})
        have[eid] = rows
        json.dump(have, open(OUT, "w"), separators=(",", ":"))
        print("  %-9s theScore %-7s posts %3d (looked at %3d)  touchdowns %2d  matched %2d"
              % (away + "/" + home, sid, len(pids), len(want), len(tds), len(rows)))
    print("games in cfb_xindex.json: %d" % len(have))


if __name__ == "__main__":
    main()
