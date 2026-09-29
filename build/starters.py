"""Who takes the snap on each drawn card, settled by three sources in order.

   A card drew its passer once, when the week was drawn, and nothing looked
   again. On Sep 22, 2026 that had Cooper Rush on Atlanta's card against ESPN's
   Michael Penix Jr., Carson Wentz on Minnesota's against Kyler Murray, and two
   quarterbacks ESPN's own chart marked D still starting. Jose: "the biggest
   thing is that I don't want to have to do it."

   The order, as he set it that day:

       1. the depth chart names the room, in order          site/depth.json
       2. the mark beside his name can veto him             the same file
       3. DraftKings settles the doubt                      site/prices/<id>.json

   The letters ESPN writes, and what each one does here:

       P    Probable             he plays, marked
       Q    Questionable         he plays, marked
       D    Doubtful             swap -- ESPN's legend omits D, the chart
                                 writes it, and it is nearer Out than Q
       O    Out                  swap
       IR   Injured reserve      swap
       PUP  Physically unable    swap
       SUS  Suspended            swap

   A swap takes the next man down the chart who is himself a go, and keeps
   going down if that man is marked too.

   DraftKings is the tiebreak and it runs both ways. A book pricing a man's
   passing props is the market saying he takes the field: a Probable or
   Questionable passer DraftKings prices goes back to starter and his mark
   comes off every place it is drawn (Jose, Sep 22, 2026: "if dart is
   questionable and dk has his props we move him back to the starter and then
   list the odds for him and remove the injury icon from all locations"). It
   does not overrule Out, IR, PUP or Suspended -- a stale market is not a
   medical clearance, and those four are the club's own word.

   When this runs, from build/refresh.py:

       when the week is drawn        after last week's last game goes final
       every sweep                   9am, noon, 3, 6 and 9 Eastern
       60 minutes before kickoff     the league posts inactives at 90, so this
                                     is the first wake that can read the list
                                     rather than guess at it
       30 minutes before kickoff     the confirm

   It writes master.html's SCHED through pagefile, so a run that started before
   somebody else's edit stands down rather than putting the page back.

       python3 build/starters.py            every drawn game inside the horizon
       python3 build/starters.py --game ID  one game, for a kickoff wake
"""
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEPTH = os.path.join(D, "site", "depth.json")
PRICES = os.path.join(D, "site", "prices")

# the letters that take a man off the card. Q and P do not -- he plays, marked.
# D is here although ESPN's legend omits it: the chart writes it, and doubtful
# is nearer out than questionable (Jose, Sep 22, 2026)
SWAP = ("O", "D", "IR", "PUP", "SUS", "SUSP", "NFI")
# DraftKings can put a Probable or Questionable man back on the card, and that
# is the whole of its say. None of these is a market's to overturn -- a price
# left standing is not a medical clearance, it is a price left standing.
FINAL = SWAP
# how far ahead a card is worth settling. Beyond it the chart is a guess about
# a week that has not been played into yet, and today's letter says nothing
# about a man ten days out -- the same reach fill_week.py prices
HORIZON_DAYS = 8


def pricefile(espn_id):
    f = os.path.join(PRICES, "%s.json" % espn_id)
    if not os.path.exists(f):
        return None, None
    try:
        return f, json.load(open(f))
    except ValueError:
        return None, None


def priced(espn_id, side):
    """Is DraftKings pricing the passing props on this side of this game?

       The file keys a market by side, not by man -- "ptd" is a pair, away
       then home -- so this asks about the side and the caller knows who is
       standing on it. The moneyline is deliberately not read: a club price
       says nothing about who throws it."""
    f, pr = pricefile(espn_id)
    if not pr:
        return False
    for market in ("ptd", "atd"):
        got = (pr.get("props") or {}).get(market) or []
        if len(got) <= side:
            continue
        mine = got[side]
        # a rung is [price, id]; ptd carries several rungs a side, atd one
        rungs = mine if mine and isinstance(mine[0], list) else [mine]
        if any((r or [None])[0] for r in rungs):
            return True
    return False


def unprice(espn_id, side):
    """Take this side's props off the file.

       A swap changes whose props we draw, and the prices are keyed to the
       side, so leaving them puts the old passer's numbers under the new
       passer's face (Jose, Sep 22, 2026). They are blanked rather than
       guessed at, and fill_week.py reads the book again for the man who is
       actually starting. The moneyline is the club's and stays."""
    f, pr = pricefile(espn_id)
    if not pr:
        return False
    hit = False
    for market, got in (pr.get("props") or {}).items():
        if not isinstance(got, list) or len(got) <= side or got[side] is None:
            continue
        mine = got[side]
        if mine and isinstance(mine[0], list):
            got[side] = [[None, None] for _ in mine]
        else:
            got[side] = [None, None]
        hit = True
    if hit:
        json.dump(pr, open(f, "w"), separators=(",", ":"))
    return hit


def book_of(espn_id, club, depth):
    """Whose passing prices the card is carrying for this club, off the
       prices file itself: DraftKings' own number for each man it priced,
       pinned to ESPN's in data/dk_people.json, and kept only if ESPN has him
       in this club's room. The side is settled by the club, never by
       DraftKings' away/home order. data/dk_qbs.json goes stale on a game the
       sweep holds more than a day out; this does not, because it is the very
       read the prices on the card came from (Jose, Sep 29, 2026: Daniels's
       face over Mariota's prices -- "we should get IDs for all ESPN
       quarterbacks and IDs for all DraftKings quarterbacks")."""
    f, pr = pricefile(espn_id)
    q = ((pr or {}).get("props") or {}).get("_qb") or {}
    try:
        pins = json.load(open(os.path.join(D, "data", "dk_people.json")))
    except (OSError, ValueError):
        pins = {}
    room = set(str(x.get("id")) for x in ((depth.get(club) or {}).get("qbs") or []))
    out = []
    for men in q.values():
        for pid, nm in (men or {}).items():
            e = str((pins.get(str(pid)) or {}).get("espn") or "")
            if e and e in room and [e, nm] not in out:
                out.append([e, nm])
    return out


def settle(club, espn_id, side, depth):
    """The man who starts for this club on this game, and what to say about
       him. Answers None when we have no chart for the club at all -- an
       absence is not a reason to redraw the card."""
    room = (depth.get(club) or {}).get("qbs") or []
    if not room:
        return None
    for q in room:
        mark = (q.get("mark") or "").upper()
        if not mark:
            return {"id": q["id"], "name": q["name"], "mark": None, "cleared": 0}
        if mark not in SWAP:
            # Probable or Questionable: he plays, and he keeps his mark unless
            # the book is pricing him
            return {"id": q["id"], "name": q["name"], "mark": mark,
                    # the book pricing HIM, not just his side: the side was
                    # priced for Mariota while Daniels sat questionable
                    "cleared": 1 if any(x[0] == str(q["id"]) for x in book_of(espn_id, club, depth)) else 0}
        # marked and stopped: keep going down the room, and if that man is
        # marked too, keep going. A conflict with the book is noted by the
        # caller rather than settled here.
    return None


try:
    NAMED = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qb_named.json")))
except (OSError, ValueError):
    NAMED = {}


_TEAMS = None


def chart_qbs(club):
    """The club's QBs in chart order, off ESPN's own depth chart -- for when
       site/depth.json has nothing for the club (Tampa, Sep 28, 2026)."""
    global _TEAMS
    from curl_cffi import requests as rq
    try:
        if _TEAMS is None:
            j = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams", impersonate="chrome", timeout=30).json()
            _TEAMS = {t["team"]["abbreviation"]: t["team"]["id"]
                      for t in j["sports"][0]["leagues"][0]["teams"]}
        tid = _TEAMS.get(club)
        yr = datetime.datetime.now().year if datetime.datetime.now().month >= 3 else datetime.datetime.now().year - 1
        d = rq.get("https://sports.core.api.espn.com/v2/sports/football/leagues/nfl/seasons/%d/teams/%s/depthcharts"
                   % (yr, tid), impersonate="chrome", timeout=30).json()
        for it in d.get("items") or []:
            qb = (it.get("positions") or {}).get("qb")
            if qb:
                out = []
                for a in qb.get("athletes") or []:
                    m = re.search(r"/athletes/(\d+)", (a.get("athlete") or {}).get("$ref", ""))
                    if m:
                        out.append(m.group(1))
                return out
    except Exception:
        return []
    return []


def espn_name(pid):
    from curl_cffi import requests as rq
    try:
        return rq.get("https://site.web.api.espn.com/apis/common/v3/sports/football/nfl/athletes/%s" % pid,
                      impersonate="chrome", timeout=30).json()["athlete"]["displayName"]
    except Exception:
        return ""


def main():
    only = None
    if "--game" in sys.argv:
        only = sys.argv[sys.argv.index("--game") + 1]

    if not os.path.exists(DEPTH):
        print("no site/depth.json -- run build/depth.py first")
        return 1
    depth = json.load(open(DEPTH))

    s = pagefile.read()
    m = re.search(r"  var SCHED = (\[\[.*?\]\]);\n", s, re.S)
    if not m:
        print("no SCHED on the page")
        return 1
    sched = json.loads(m.group(1))

    swaps, cleared, argued, clear, seen = [], [], [], {}, 0
    now = datetime.datetime.now(datetime.timezone.utc)
    # the book's passers per game and side, as ESPN ids (fill_week.py asks
    # ESPN who each one is and keeps him only if ESPN says he is a QB on that
    # club), and the wire, which the book cannot overrule
    try:
        dkq_nfl = json.load(open(os.path.join(D, "data", "dk_qbs.json")))
    except (OSError, ValueError):
        dkq_nfl = {}
    try:
        wire = json.load(open(os.path.join(D, "site", "wire.json")))
    except (OSError, ValueError):
        wire = {}
    STOP = ("out", "injured reserve", "physically unable to perform", "suspended", "pup", "ir")
    for g in sched:
        espn_id = str(g[1])
        if only and espn_id != only:
            continue
        if not only:
            # a week further out than the horizon is not settled: today's
            # letter says nothing about a man ten days from now, and rewriting
            # week 7 on a Monday only guarantees it is wrong by Sunday
            try:
                kick = datetime.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
            except ValueError:
                continue
            if not (now - datetime.timedelta(hours=6) < kick
                    <= now + datetime.timedelta(days=HORIZON_DAYS)):
                continue
        seen += 1
        # the away side is drawn on the left and is index 0 everywhere
        for side, (i, club) in enumerate(((5, g[3]), (7, g[4]))):
            # a named starter the chart does not know yet: reported by the
            # club or the insiders and held in data/qb_named.json by game --
            # Keenum over Bagent on Sep 28, 2026, which the chart missed
            # (Jose: "how do you not catch this")
            held = NAMED.get("%s|%s" % (espn_id, club))
            if held:
                if str(g[i + 1]) != str(held["id"]):
                    swaps.append("%-4s %-20s -> %-20s (named)" % (club, g[i], held["name"]))
                    g[i], g[i + 1] = held["name"], held["id"]
                    unprice(espn_id, side)
                continue
            # ESPN and DraftKings agree, or DraftKings decides: the one passer
            # the book prices for this side starts, unless the wire has him
            # Out, on IR, PUP or suspended. Keenum was priced all day while the
            # chart still said Bagent (Jose, Sep 28, 2026: "ESPN has to talk to
            # DraftKings to make sure we're pulling the right quarterback")
            book = [x for x in ((dkq_nfl.get(espn_id) or [[], []])[side]) if x and x[0]]
            if not book:
                book = book_of(espn_id, club, depth)
            if len(book) == 1 and (wire.get(book[0][0]) or {}).get("status", "").lower() not in STOP:
                if str(g[i + 1]) != book[0][0]:
                    swaps.append("%-4s %-20s -> %-20s (DraftKings, ESPN id %s)" % (club, g[i], book[0][1], book[0][0]))
                    g[i], g[i + 1] = book[0][1], book[0][0]
                    unprice(espn_id, side)
                continue
            # the wire outranks everything left: a man it has out, on IR or
            # doubtful gives way to the next man on the club's chart who is
            # not (Jose, Sep 28, 2026: "why do we still have Baker in")
            cur = str(g[i + 1])
            if (wire.get(cur) or {}).get("status", "").lower() in STOP + ("doubtful",):
                nxt = next((x for x in chart_qbs(club) if x != cur and
                            (wire.get(x) or {}).get("status", "").lower() not in STOP + ("doubtful",)), None)
                if nxt:
                    nm = espn_name(nxt) or g[i]
                    swaps.append("%-4s %-20s -> %-20s (wire: %s)" % (club, g[i], nm, wire[cur]["status"]))
                    g[i], g[i + 1] = nm, nxt
                    unprice(espn_id, side)
                    continue
            him = settle(club, espn_id, side, depth)
            if not him:
                continue
            was = str(g[i + 1])
            if was != str(him["id"]) and priced(espn_id, side):
                # the chart takes him off and the book has not: said aloud,
                # never averaged away (the house rule on conflicts)
                argued.append("%s %s comes off the card and DraftKings is "
                              "still pricing that side" % (club, g[i]))
            if str(g[i + 1]) != str(him["id"]):
                swaps.append("%-4s %-20s -> %-20s (%s)"
                             % (club, g[i], him["name"], him["mark"] or "chart"))
                g[i], g[i + 1] = him["name"], him["id"]
                # the prices under that side were the other man's
                if unprice(espn_id, side):
                    swaps[-1] += "  [props cleared]"
            elif him["cleared"]:
                cleared.append("%-4s %-20s %s, and DraftKings prices him"
                               % (club, him["name"], him["mark"]))
                clear[str(him["id"])] = 1

    s = s[:m.start()] + "  var SCHED = %s;\n" % json.dumps(sched, separators=(",", ":")) + s[m.end():]

    # college has no depth chart we read, so a college card takes the man who
    # started that club's last played game. The row was drawn once, before
    # the season, and Rutgers kept AJ Surace on Sep 25, 2026 a week after
    # Dylan Lonergan had taken the job (Jose: "he was the starter you had aj
    # surace"). played_qb.py has already put the man who played on each
    # finished row, so the last finished row is the last word.
    try:
        dkq = json.load(open(os.path.join(D, "data", "dk_qbs.json")))
    except (OSError, ValueError):
        dkq = {}
    c = re.search(r"  var CFB = (\[\[.*?\]\]);\n", s, re.S)
    cfb = json.loads(c.group(1)) if c else []
    last = {}
    for g in sorted(cfb, key=lambda g: g[2]):
        if not os.path.exists(os.path.join(D, "site", "final", "%s.json" % g[1])):
            continue
        for i, club in ((5, g[3]), (7, g[4])):
            if g[i + 1]:
                last[club] = (g[i], str(g[i + 1]))
    # a club whose drawn man DraftKings prices on any open card keeps him on
    # all of them: the market outranks one box score
    for g in cfb:
        if os.path.exists(os.path.join(D, "site", "final", "%s.json" % g[1])):
            continue
        for side, (i, club) in enumerate(((5, g[3]), (7, g[4]))):
            if club in last and last[club][1] != str(g[i + 1]) and priced(str(g[1]), side):
                argued.append("%s %s started last, DraftKings prices %s"
                              % (club, last[club][0], g[i]))
                last.pop(club)
    for g in cfb:
        espn_id = str(g[1])
        if only and espn_id != only:
            continue
        if os.path.exists(os.path.join(D, "site", "final", "%s.json" % espn_id)):
            continue
        try:
            kick = datetime.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        except ValueError:
            continue
        if not only and not (now - datetime.timedelta(hours=6) < kick
                             <= now + datetime.timedelta(days=HORIZON_DAYS)):
            continue
        seen += 1
        for side, (i, club) in enumerate(((5, g[3]), (7, g[4]))):
            # DraftKings first: the one passer it prices for this side is the
            # starter, the way the chart names him in the NFL (Jose, Sep 25,
            # 2026: "dk should confirm"). ESPN keeps no college depth chart --
            # its feed comes back empty for every club -- so the book is the
            # only word before kickoff that is not a guess.
            book = [x for x in ((dkq.get(espn_id) or [[], []])[side]) if x[0]]
            if len(book) == 1:
                if book[0][0] != str(g[i + 1]):
                    swaps.append("%-4s %-20s -> %-20s (DraftKings)" % (club, g[i], book[0][1]))
                    g[i], g[i + 1] = book[0][1], book[0][0]
                continue
            if club not in last or last[club][1] == str(g[i + 1]):
                continue
            swaps.append("%-4s %-20s -> %-20s (last start)"
                         % (club, g[i], last[club][0]))
            g[i], g[i + 1] = last[club]
            f, pr = pricefile(espn_id)
            held = [(v[side] if isinstance(v, list) and len(v) > side else None)
                    for v in ((pr or {}).get("props") or {}).values()]
            if "\"" in json.dumps(held) and unprice(espn_id, side):
                swaps[-1] += "  [props cleared]"
    if c:
        s = s[:c.start()] + "  var CFB = %s;\n" % json.dumps(cfb, separators=(",", ":")) + s[c.end():]

    # who the mark comes off, for the page to read: a man the book is pricing
    # wears no plaster anywhere (Jose, Sep 22, 2026). Written whole each run,
    # so a man the book stops pricing gets his plaster back by himself.
    json.dump(clear, open(os.path.join(D, "site", "cleared.json"), "w"),
              separators=(",", ":"), sort_keys=True)

    if swaps and not pagefile.write(s):
        print("page changed under us, nothing written")
        return 1

    print("starters: %d games read, %d swapped, %d cleared by the book"
          % (seen, len(swaps), len(cleared)))
    for x in swaps:
        print("   ", x)
    for x in cleared:
        print("    cleared:", x)
    # a conflict is logged, never averaged away (the house rule)
    for x in argued:
        print("    CONFLICT:", x)
    return 0


if __name__ == "__main__":
    sys.exit(main())
