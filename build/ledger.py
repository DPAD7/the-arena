"""The passers' form, week by week, from what the board has already settled.

   For every NFL game with a settled file (site/final/{eid}.json) the two
   named passers get: passing touchdowns, rushing touchdowns, whether he won
   the passing-yards head to head, and whether his club won. Written to
   site/ledger.json as {week: [rows]}, each row [name, club, espn id, ptd,
   atd, h2h, ml, yards, game id, side] with h2h and ml as "W", "L" or "" (no yards to compare, or a
   tie). The page ranks them; nothing here is a price.

   Usage:  python3 ledger.py
"""
import datetime as dt
import json
import os
import sys
import re

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
POSFILE = D + "/cache/positions.json"
POS = json.load(open(POSFILE)) if os.path.exists(POSFILE) else {}


def position(pid):
    """ESPN's position for a man, cached. A fake punt puts a punter in the
       passing block: Cameron Johnston, 0 for 1 for Pittsburgh in week 1, came
       out ranked among the quarterbacks. (Jose, Sep 17, 2026)"""
    pid = str(pid)
    if pid in POS:
        return POS[pid]
    url = ("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/"
           "athletes/%s?lang=en" % pid)
    try:
        d = rq.get(url, impersonate="chrome", timeout=20).json()
        POS[pid] = ((d.get("position") or {}).get("abbreviation") or "").upper()
    except Exception as e:
        print("  position unknown for %s: %s" % (pid, e))
        return ""
    json.dump(POS, open(POSFILE, "w"))
    return POS[pid]


def passers(j, abbr):
    """Every man who threw for this club, in the order ESPN lists them."""
    for t in (j.get("boxscore") or {}).get("players") or []:
        if ((t.get("team") or {}).get("abbreviation")) != abbr:
            continue
        for st in t.get("statistics") or []:
            if st.get("name") == "passing":
                out = []
                for a in st.get("athletes") or []:
                    pid = str((a.get("athlete") or {}).get("id"))
                    nm = (a.get("athlete") or {}).get("displayName")
                    line = dict(zip(st.get("labels", []), a.get("stats", [])))
                    # this is the passers' form, so only men ESPN calls quarterbacks
                    pos = position(pid)
                    if pos and pos != "QB":
                        print("  not a passer: %s (%s) -- %s" % (nm, pos, line.get("C/ATT")))
                        continue
                    out.append((pid, nm, line))
                return out
    return []


def stat(j, pid, kind):
    for t in (j.get("boxscore") or {}).get("players") or []:
        for st in t.get("statistics", []):
            if st.get("name") != kind:
                continue
            for a in st.get("athletes", []):
                if str((a.get("athlete") or {}).get("id")) == str(pid):
                    return dict(zip(st.get("labels", []), a.get("stats", [])))
    return None


def num(x):
    try:
        return int(str(x).replace(",", ""))
    except ValueError:
        return 0


_LIVE_PROPS = None


def live_props(eid):
    """What the board is charging right now, out of site/prices.json.

       The saved copy is taken when the sweep runs, and DraftKings posts a
       head-to-head on the morning of the game -- so a game whose copy was
       frozen the night before has no head-to-head in it for ever, and Hurts
       and Young read two legs on a week they won three (Jose, Sep 20, 2026).
       The saved copy is still the closing price; this only fills a hole."""
    global _LIVE_PROPS
    if _LIVE_PROPS is None:
        try:
            _LIVE_PROPS = json.load(open(D + "/site/prices.json")).get("PROPS") or {}
        except Exception:
            _LIVE_PROPS = {}
    return _LIVE_PROPS.get(str(eid)) or {}


def priced(league, week, eid):
    """What DraftKings charged on this game, as keep_prices.py saved it."""
    f = D + "/prices/%s/wk%s/%s.json" % (league, week, eid)
    if not os.path.exists(f):
        return {}
    d = json.load(open(f))
    h2h = d.get("h2h") or [None, None]
    if not any(h2h):
        h2h = (live_props(eid).get("h2h") or [None, None])
    out = {"h2h": h2h, "by": {}, "side": {}}
    for man in d.get("passers") or []:
        row = {"ptd": man.get("ptd") or [None, None], "atd": man.get("atd") or [None, None], "name": man.get("name")}
        out["by"][str(man.get("id"))] = row
        out["side"][str(man.get("side"))] = row       # the man the board priced, whoever played
    return out


def live(eid):
    """A game with no settled file: ask for it, so one being played now reads
       the same way a finished one does. Nothing yet under way answers None."""
    try:
        d = rq.get("https://site.web.api.espn.com/apis/site/v2/sports/football/nfl/"
                   "summary?event=%s" % eid, impersonate="chrome", timeout=25).json()
    except Exception:
        return None
    comp = ((d.get("header") or {}).get("competitions") or [{}])[0]
    st = ((comp.get("status") or {}).get("type") or {})
    if st.get("state") in (None, "pre"):
        return None
    return d


def stub(out, g):
    """The matchup before a ball is thrown: the two men the board priced, with
       nothing counted and their prices already on."""
    pz = priced("nfl", g[0], g[1])
    for i in (0, 1):
        nm, pid = (g[5], g[6]) if i == 0 else (g[7], g[8])
        if not nm:
            continue
        mine = ((pz.get("side") or {}).get(str(i))) or {}
        odds = [[(x or [None])[0] for x in (mine.get("ptd") or [None, None])],
                [(x or [None])[0] for x in (mine.get("atd") or [None, None])],
                ((pz.get("h2h") or [None, None])[i] or [None])[0],
                g[9 if i == 0 else 11] or None]
        # the same length as a played row, so nothing that reads by position
        # falls off the end of a fixture nobody has played yet
        out.setdefault(str(g[0]), []).append([nm, g[3] if i == 0 else g[4], str(pid), 0, 0,
                                              "", "", 0, str(g[1]), i, None, odds, 1, None, 0])


def main():
    s = pagefile.read()
    sched = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    out = {}
    games = 0
    now = dt.datetime.now(dt.timezone.utc)
    # the week being played, or the next one up: one week of matchups ahead,
    # not the rest of the season (Jose, Sep 17, 2026)
    todo = [int(g[0]) for g in sched
            if dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")) + dt.timedelta(hours=4) > now]
    ahead = min(todo) if todo else 0
    for g in sched:
        f = D + "/site/final/%s.json" % g[1]
        if not os.path.exists(f):
            j = live(g[1])
            if j is None:
                # only the week in front of us: the whole season of empty
                # matchups is eighteen tabs of nothing (Jose, Sep 17, 2026)
                if int(g[0]) == ahead:
                    stub(out, g)
                continue
        else:
            j = json.load(open(f))
        comp = ((j.get("header") or {}).get("competitions") or [{}])[0]
        st = ((comp.get("status") or {}).get("type") or {})
        state = st.get("state")
        if state == "pre":
            stub(out, g)
            continue
        # a game being played belongs on the board as it goes, not only once it
        # is over (Jose, Sep 17, 2026)
        if state not in ("post", "in", None) and not st.get("completed", True):
            continue
        won = {x["team"]["abbreviation"]: bool(x.get("winner")) for x in comp.get("competitors") or [] if x.get("team")}
        score = {x["team"]["abbreviation"]: num(x.get("score")) for x in comp.get("competitors") or [] if x.get("team")}
        clubs = [g[3], g[4]]
        pz = priced("nfl", g[0], g[1])
        crews = [passers(j, clubs[0]), passers(j, clubs[1])]
        if not any(crews):
            # kicked off but nobody has thrown yet: keep the matchup on the
            # board rather than dropping the game (Jose, Sep 17, 2026)
            stub(out, g)
            continue
        games += 1
        # the man on the card is the one the board priced; anybody else who threw
        # still gets his own row (Jose, Sep 16, 2026: Darnold was Seattle's
        # starter and was hurt, Lock finished -- both belong)
        # the head to head is the market: the two men the board priced, not
        # whoever threw the most (Jose, Sep 16, 2026)
        cards, card_yds = [None, None], [0, 0]
        for i in (0, 1):
            want = ((pz.get("side") or {}).get(str(i)) or {}).get("name")
            for pid, nm, line in crews[i]:
                if want and nm == want:
                    cards[i] = pid
            if not cards[i] and crews[i]:
                cards[i] = crews[i][0][0]
            for pid, nm, line in crews[i]:
                if pid == cards[i]:
                    card_yds[i] = num(line.get("YDS"))
        for i in (0, 1):
            carded = cards[i]
            for pid, nm, line in crews[i]:
                r = stat(j, pid, "rushing") or {}
                yds = num(line.get("YDS"))
                is_card = pid == carded
                oy = card_yds[1 - i]
                # the head to head settles at the whistle, not while the man
                # is still throwing: Goff was two yards down at half time
                # (Jose, Sep 17, 2026)
                h2h = "" if state != "post" or not is_card or not crews[1 - i] or yds == oy \
                      else ("W" if yds > oy else "L")
                ml = "" if state != "post" else ("W" if won.get(clubs[i]) else ("L" if clubs[i] in won else ""))
                mine = (pz.get("by") or {}).get(str(pid)) or ((pz.get("side") or {}).get(str(i)) if is_card else {}) or {}
                odds = [[(x or [None])[0] for x in (mine.get("ptd") or [None, None])],
                        [(x or [None])[0] for x in (mine.get("atd") or [None, None])],
                        ((pz.get("h2h") or [None, None])[i] or [None])[0] if is_card else None,
                        (g[9 if i == 0 else 11] or None) if is_card else None]
                # and whether the whistle has gone. A game belongs on the board
                # as it goes, but nothing it has done is paid until it is over:
                # Watson's second touchdown was counted as a winning leg while
                # Cleveland at Tampa was still delayed (Jose, Sep 20, 2026:
                # "why is Watson 2 TD being checked as paid")
                out.setdefault(str(g[0]), []).append([nm, clubs[i], str(pid), num(line.get("TD")), num(r.get("TD")),
                                                      h2h, ml, yds, str(g[1]), i, score.get(clubs[i], 0), odds,
                                                      1 if is_card else 0, None,
                                                      1 if state == "post" else 0])
    # each club's record entering each week, from the finals we hold, for the
    # NFL and college cards (Jose, Sep 17, 2026)
    def records_for(rows):
        tally = {}
        for g in rows:
            f = D + "/site/final/%s.json" % g[1]
            if not os.path.exists(f):
                continue
            comp = ((json.load(open(f)).get("header") or {}).get("competitions") or [{}])[0]
            st = ((comp.get("status") or {}).get("type") or {})
            if st.get("state") != "post":
                continue
            for x in comp.get("competitors") or []:
                ab = (x.get("team") or {}).get("abbreviation")
                if ab:
                    tally.setdefault(int(g[0]), {}).setdefault(ab, [0, 0])
                    tally[int(g[0])][ab][0 if x.get("winner") else 1] += 1
        weeks = sorted({int(g[0]) for g in rows})
        out = {}
        for wk in weeks:
            rec = {ab: [0, 0] for g in rows for ab in (g[3], g[4])}   # 0-0 until a club has played
            for past in weeks:
                if past >= wk:
                    break
                for ab, wl in tally.get(past, {}).items():
                    r = rec.setdefault(ab, [0, 0]); r[0] += wl[0]; r[1] += wl[1]
            out[str(wk)] = {ab: "%d-%d" % tuple(wl) for ab, wl in rec.items()}
        return out
    cfb = json.loads(re.search(r"var CFB = (\[\[.*?\]\]);", s, re.S).group(1))
    json.dump({"nfl": records_for(sched), "ncaaf": records_for(cfb)}, open(D + "/site/records.json", "w"), separators=(",", ":"))
    for wk in out:
        out[wk].sort(key=lambda r: (-(r[3] + r[4]), -r[3], r[5] != "W", r[6] != "W", r[0]))
    json.dump(out, open(D + "/site/ledger.json", "w"), separators=(",", ":"))
    print("ledger: %d games, weeks %s, rows %d" % (games, sorted(out, key=int), sum(len(v) for v in out.values())))


if __name__ == "__main__":
    main()
