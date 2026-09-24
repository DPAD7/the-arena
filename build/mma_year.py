"""The whole UFC year on the board: every event ESPN lists for 2026.

   Cards and bouts come from ESPN's UFC scoreboard (the Contender Series is
   on it too): event, date, both men and their ids, the weight class. A bout
   already on the board keeps its DraftKings moneyline; a bout that has been
   fought takes ESPN's stored closing line (ESPN BET) as a plain, unbuttoned
   price. A finished event is written to site/final/mma-{event id}.json so
   the page reads its results without asking ESPN again.

   Usage:  python3 mma_year.py --dry
           python3 mma_year.py
"""
import datetime as dt
import email.utils
import pagefile
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
NOW = dt.datetime.now(dt.timezone.utc)
YEAR = "2026"


def get(u):
    for _ in range(3):
        try:
            r = rq.get(u, impersonate="chrome124", timeout=60)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
    return None


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def week_of(sched, iso):
    """The NFL week a date falls in: the week whose games end last before it,
       plus one; anything before week one's games is week one."""
    t = T(iso)
    ends = {}
    for g in sched:
        ends[g[0]] = max(ends.get(g[0], T(g[2])), T(g[2]))
    wk = 1
    for w in sorted(ends):
        if t > ends[w] + dt.timedelta(hours=6):
            wk = w + 1
    return min(wk, max(ends))


def closing(event_id, bout_id, left_id, right_id):
    o = get("https://sports.core.api.espn.com/v2/sports/mma/leagues/ufc/events/%s/competitions/%s/odds" % (event_id, bout_id))
    for it in (o or {}).get("items") or []:
        out = {}
        for side in ("awayAthleteOdds", "homeAthleteOdds"):
            a = it.get(side) or {}
            ref = (a.get("athlete") or {}).get("$ref") or ""
            aid = ref.rsplit("/", 1)[-1].split("?")[0]
            ml = a.get("moneyLine")
            if aid and ml is not None:
                out[aid] = ("+%d" % ml) if ml > 0 else str(ml)
        if out.get(left_id) and out.get(right_id):
            return out[left_id], out[right_id]
    return None


def plain(x):
    """letters only, accents dropped (Cháirez -> chairez), so the two sources' spellings meet"""
    x = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", x.lower())


def tokens(x):
    """the same, but as a sorted bag of words: 'Rangbo Sulang' and 'Sulang Rangbo' agree"""
    x = unicodedata.normalize("NFKD", str(x or "")).encode("ascii", "ignore").decode().lower()
    return "".join(sorted(re.findall(r"[a-z]+", x)))


_SCORE = None
_HOW = {}
_IDS = {}


def score_lines(iso):
    """theScore's stored moneylines for every bout it lists, keyed by the two
       men's names written plainly -- fetched once, every event, every fight."""
    global _SCORE
    if _SCORE is None:
        _SCORE = {}
        events = get("https://api.thescore.com/mma/events") or []
        for e in events:
            for f in get("https://api.thescore.com/mma/events/%s/fights" % e["id"]) or []:
                o = f.get("odds") or {}
                a, h = f.get("away_fighter") or {}, f.get("home_fighter") or {}
                if a.get("full_name") and h.get("full_name"):
                    v = f.get("victory") or {}
                    # a third key: the event's day and the two surnames, for "Jose Daniel Medina" v "Daniel Medina"
                    day = (f.get("start_datetime") or e.get("start_datetime") or "")[5:16]
                    sur = lambda n: plain(str(n).split()[-1]) if str(n).split() else ""
                    for key in ((plain(a["full_name"]), plain(h["full_name"])), (tokens(a["full_name"]), tokens(h["full_name"])),
                                (day + "|" + sur(a["full_name"]), sur(h["full_name"]))):
                        _IDS[key] = (str(a.get("id") or ""), str(h.get("id") or ""), plain(a["full_name"]))
                        if o.get("away") and o.get("home"):
                            _SCORE[key] = (o["away"], o["home"])
                        if v.get("type"):
                            _HOW[key] = {"type": v.get("type"), "round": v.get("round"), "time": v.get("time"), "scorecard": f.get("scorecard") or ""}
        print("theScore: %d events, %d bouts with lines" % (len(events), len(_SCORE)))
    return _SCORE


def main():
    s = pagefile.read()
    sched = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    m_f = re.search(r"var FIGHTS = (\[\[.*?\]\]);", s, re.S)
    m_c = re.search(r"var FIGHTCARDS = (\[\[.*?\]\]);", s, re.S)
    old = {f[1]: f for f in json.loads(m_f.group(1))}
    sb = get("https://site.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard?dates=%s0101-%s1231&limit=1000" % (YEAR, YEAR))
    events = sb.get("events") or []
    cards, fights, finals, past = [], [], {}, []
    for e in sorted(events, key=lambda e: e["date"]):
        eid = str(e["id"])
        comps = e.get("competitions") or []
        if not comps:
            continue
        cards.append([week_of(sched, e["date"]), eid, e["date"], e.get("name") or e.get("shortName") or ""])
        # any, not all. A card was only written down once every bout on it had
        # finished, so a knockout at seven fifteen reached our own record at
        # midnight with the main event -- and the board showed nothing settled
        # all night (Jose, Sep 22, 2026: "whenever the KO happens it settles
        # there"). The file is rewritten each time another bout ends, so a card
        # fills in through the night. Bouts still to come carry their own
        # status and are drawn as such.
        done = any((((c.get("status") or {}).get("type") or {}).get("state") == "post") for c in comps)
        if done:
            finals[eid] = {"events": [{"id": eid, "name": e.get("name"), "date": e["date"],
                                       "competitions": [{"id": str(c["id"]), "status": c.get("status"), "details": [d for d in (c.get("details") or []) if str(((d.get("type") or {}).get("text") or "")).startswith("Unofficial Winner")],
                                                         "competitors": [{"id": x.get("id"), "winner": x.get("winner"), "athlete": {"displayName": (x.get("athlete") or {}).get("displayName")}} for x in c.get("competitors") or []]}
                                                        for c in comps]}]}
        for c in comps:
            xs = c.get("competitors") or []
            if len(xs) != 2:
                continue
            l, r = xs[0], xs[1]
            lid, rid = str(l.get("id") or ""), str(r.get("id") or "")
            row = [eid, str(c["id"]), c.get("date") or e["date"],
                   (l.get("athlete") or {}).get("displayName") or "", lid,
                   (r.get("athlete") or {}).get("displayName") or "", rid,
                   ((c.get("type") or {}).get("abbreviation") or ""), "", "", "", ""]
            prev = old.get(str(c["id"]))
            if prev and len(prev) >= 12 and prev[9]:
                row[8:12] = prev[8:12]          # DraftKings' moneyline and ids stay
                # the names as the board already writes them, so the pricers' name match holds
                row[3], row[5] = prev[3], prev[5]
            elif T(row[2]) < NOW:
                past.append((row, eid))
            fights.append(row)
    # closing lines for what has been fought, in parallel
    def cl(item):
        row, eid = item
        c = None
        if True:
            # theScore holds every closing line; both names must match plainly, in either order
            lines = score_lines(row[2])
            l, r = plain(row[3]), plain(row[5])
            bl, br = tokens(row[3]), tokens(row[5])
            if (l, r) in lines:
                c = lines[(l, r)]
            elif (r, l) in lines:
                c = lines[(r, l)][::-1]
            elif (bl, br) in lines:
                c = lines[(bl, br)]
            elif (br, bl) in lines:
                c = lines[(br, bl)][::-1]
        if not c:
            # a bout theScore never priced takes ESPN's stored closing line
            c = closing(eid, row[1], row[4], row[6])
        if c:
            row[8], row[10] = c
        return bool(c)
    score_lines("")                              # built once, before the threads share it
    with ThreadPoolExecutor(4) as ex:
        got = sum(1 for ok in ex.map(cl, past) if ok)
    unmatched = [row[3] + " v " + row[5] for row, _ in past if not row[8]]
    if unmatched:
        print("no line found for %d: %s" % (len(unmatched), "; ".join(unmatched[:8])))
    # theScore's ids for the pictures, on every bout, by the names in either order
    score_lines("")
    pictured = 0
    for row in fights:
        l, r = plain(row[3]), plain(row[5]); bl, br = tokens(row[3]), tokens(row[5])
        hit = _IDS.get((l, r)) or _IDS.get((bl, br)) or _IDS.get((r, l)) or _IDS.get((br, bl))
        if hit:
            while len(row) < 14:
                row.append("")
            # theScore's away man is whoever its first name names; keep our left/right
            row[12], row[13] = (hit[0], hit[1]) if hit[2] in (l, bl) else (hit[1], hit[0])
            pictured += 1
    print("theScore pictures tied on %d bouts" % pictured)
    print("events %d (%d finished) | bouts %d | kept DraftKings lines %d | closing lines %d of %d past"
          % (len(cards), len(finals), len(fights), sum(1 for f in fights if f[9]), got, len(past)))
    if DRY:
        return
    s = s[:m_c.start(1)] + json.dumps(cards, separators=(",", ":")) + s[m_c.end(1):]
    m_f = re.search(r"var FIGHTS = (\[\[.*?\]\]);", s, re.S)
    s = s[:m_f.start(1)] + json.dumps(fights, separators=(",", ":")) + s[m_f.end(1):]
    if not pagefile.write(s):
        print("the page changed while this run was reading -- nothing written")
        return
    pagefile.deployable(s)
    os.makedirs(D + "/site/final", exist_ok=True)
    # how each finished bout ended, from theScore, by the two names in either order
    for eid, j in finals.items():
        for c in j["events"][0]["competitions"]:
            names = [plain((x.get("athlete") or {}).get("displayName")) for x in c["competitors"]]
            bags = [tokens((x.get("athlete") or {}).get("displayName")) for x in c["competitors"]]
            if len(names) == 2:
                how = (_HOW.get((names[0], names[1])) or _HOW.get((names[1], names[0])) or
                       _HOW.get((bags[0], bags[1])) or _HOW.get((bags[1], bags[0])))
                if not how:
                    ds = [plain(str((x.get("athlete") or {}).get("displayName") or "").split()[-1]) for x in c["competitors"]]
                    day = email.utils.format_datetime(T(j["events"][0]["date"]))[5:16]
                    how = _HOW.get((day + "|" + ds[0], ds[1])) or _HOW.get((day + "|" + ds[1], ds[0]))
                if how:
                    c["how"] = how
        json.dump(j, open(D + "/site/final/mma-%s.json" % eid, "w"), separators=(",", ":"))
    print("methods from theScore: %d of %d finished bouts" % (
        sum(1 for j in finals.values() for c in j["events"][0]["competitions"] if c.get("how")),
        sum(len(j["events"][0]["competitions"]) for j in finals.values())))
    print("written")


if __name__ == "__main__":
    main()
