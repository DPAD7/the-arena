"""Every NFL.com highlight, keyed to the play it shows.

   NFL.com's game page carries every highlight with "playIds" -- the play in
   its own play-by-play, which carries quarter, clock and text -- so a clip
   and a touchdown are joined by key, never by matching names. ESPN's feed
   offered five clips for Bucs-Bengals and dropped the one touchdown pass;
   NFL.com carries nineteen for the same game, and even the Netflix game has
   them. The page answers a plain fetch (200), unlike ESPN's.

   Playback is not stored: the signed URL lives fifteen minutes. The board
   asks api.nfl.com for it at tap time with a token minted by the /clip
   function, and needs the clip's mediaObject to do so -- kept here.

   Games are joined to ESPN's event ids through ESPN's own team record
   (slug nickname + date), asserted to resolve for every game.

   Usage:  python3 nfl_clips.py          (played games not yet pulled)
           python3 nfl_clips.py --force
"""
import datetime as dt
import json
import os
import re
import sys

try:
    from curl_cffi import requests as rq
except ImportError:
    import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "nflclips.json")
FORCE = "--force" in sys.argv


def get(u):
    r = rq.get(u, impersonate="chrome124", timeout=60)
    return r.status_code, r.text


def played():
    s = open(os.path.join(D, "master.html")).read()
    now = dt.datetime.now(dt.timezone.utc)
    arr = json.loads(re.search(r'var SCHED = (\[\[.*?\]\]);', s, re.S).group(1))
    return [g for g in arr if dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")) < now]


def nick():
    """ESPN's slug carries the nickname NFL.com keys its game slugs on."""
    m = json.load(open(os.path.join(D, "data", "nfl_slug.json")))
    return {slug.rsplit("-", 1)[1]: ab for slug, ab in m.items()}


def week_slugs(week):
    st, h = get("https://www.nfl.com/schedules/2026/REG%d/" % week)
    return sorted(set(re.findall(r'/games/([a-z0-9-]+-2026-reg-%d)' % week, h)))


def parse(html):
    u = html.replace('\\"', '"').replace("\\u0026", "&").replace("\\u0027", "'")
    plays = {}
    for m in re.finditer(r'"detailsPrimaryText":"([^"]*)","detailsSecondaryText":"([^"]*)"[^}]*?"keyId":"play-(\d+)"', u):
        when = m.group(1).strip()
        q = re.match(r"(\d\d:\d\d)\s+(\w+)", when)
        plays[m.group(3)] = {"clock": q.group(1).lstrip("0") if q else "", "quarter": q.group(2) if q else "",
                             "text": m.group(2).strip(" \u2014 ")}
    seen, out = set(), []
    for m in re.finditer(r'"headline":"([^"]+)","isoDuration":"[^"]*","mcpPlaybackId":"(\d+)","mediaObject":', u):
        start = m.end()
        depth, j = 0, start
        while j < len(u):
            if u[j] == "{": depth += 1
            elif u[j] == "}":
                depth -= 1
                if depth == 0: j += 1; break
            j += 1
        try:
            mo = json.loads(u[start:j])
        except ValueError:
            continue
        ext = mo.get("externalId")
        if not ext or ext in seen:
            continue
        seen.add(ext)
        pids = mo.get("playIds") or []
        play = plays.get(str(pids[0])) if pids else None
        out.append({"headline": m.group(1), "externalId": ext, "mcpPlaybackId": m.group(2),
                    "playId": pids[0] if pids else None,
                    "quarter": play["quarter"] if play else None,
                    "clock": play["clock"] if play else None,
                    "play": play["text"] if play else None,
                    "description": mo.get("description"), "publishDate": mo.get("publishDate"),
                    "duration": mo.get("duration"), "mediaObject": mo})
    return out


def main():
    have = json.load(open(OUT)) if os.path.exists(OUT) else {}
    games = played()
    ab_of = nick()
    by_week = {}
    for g in games:
        by_week.setdefault(g[0], []).append(g)
    unjoined = 0
    for wk, gs in sorted(by_week.items()):
        slugs = week_slugs(wk)
        for g in gs:
            eid, away, home = g[1], g[3], g[4]
            if eid in have and not FORCE:
                continue
            hit = [s for s in slugs if ab_of.get(s.split("-at-")[0]) == away
                   and ab_of.get(s.split("-at-")[1].split("-2026")[0]) == home]
            if len(hit) != 1:
                unjoined += 1
                print("  %-9s no single NFL.com slug for it: %s" % (away + "/" + home, hit))
                continue
            st, html = get("https://www.nfl.com/games/%s?tab=highlights-replays" % hit[0])
            if st != 200:
                print("  %-9s page answered %s" % (away + "/" + home, st))
                continue
            clips = parse(html)
            keyed = sum(1 for c in clips if c["playId"])
            have[eid] = {"slug": hit[0], "clips": clips}
            print("  %-9s %-36s %2d highlights, %2d keyed to a play" % (away + "/" + home, hit[0], len(clips), keyed))
    json.dump(have, open(OUT, "w"), indent=0)
    print("games in nflclips.json: %d   left unjoined: %d" % (len(have), unjoined))


if __name__ == "__main__":
    main()
