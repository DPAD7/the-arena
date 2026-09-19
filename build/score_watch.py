"""Where each NFL game lives on theScore Bet, so a card can carry a Watch link.

   theScore Bet streams the NFL inside its phone app (Genius Sports'
   BetVision). The book's event address is stable, and on a phone it opens
   the app on that game. This asks the book's NFL lines tab for every event,
   ties each to a card through the club register (its two names looked up,
   never guessed) and the date, and writes WATCH = {espn id: book event id}
   into master.html.

   Usage:  python3 score_watch.py           (writes)
           python3 score_watch.py --dry
"""
import datetime as dt
import pagefile
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.argv, _argv = ["score_props"], list(sys.argv)
import score_props as sp
sys.argv = _argv

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRY = "--dry" in sys.argv
DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "qbspy.db")


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def book_events():
    sp.TOKEN[0] = sp.token()
    if not sp.TOKEN[0]:
        sys.exit("no token from theScore Bet")
    page = sp.flat(sp.ask("EventPage", {"includeRichEvent": True, "includeStandardizedBoxscore": True,
                                        "isCfpRankingEnabled": True, "isCombatSportsRedesignEnabled": True,
                                        "canonicalUrl": sp.SITE}))
    m = re.search(r'"(Section:[0-9a-f-]{36})","label":"Lines"', page) or re.search(r'"(Section:[0-9a-f-]{36})"', page)
    if not m:
        sys.exit("theScore Bet's NFL page named no Lines section")
    tab = sp.flat(sp.ask("CompetitionPageSectionLinesTabNode", {
        "isSubscription": False, "pageType": "PAGE", "includeRecommendedProps": True, "isBrandingImageEnabled": True,
        "isNewFeaturedBetParticipantLogoEnabled": True, "isFeaturedBetCarouselHeaderRedesignEnabled": True,
        "includeStandardizedBoxscore": True, "isCfpRankingEnabled": True, "isCombatSportsRedesignEnabled": True,
        "isFeaturedMarketCardRedesignEnabled": True, "isDsModelRecommendedPropsEnabled": False,
        "isBlueprintUiFieldEnabled": False, "includeRichEvent": True, "oddsFormat": "AMERICAN",
        "sectionId": m.group(1), "selectedFilterId": ""}))
    out = {}
    for mm in re.finditer(r'Event:([0-9a-f-]{36})', tab):
        t = tab[mm.end():mm.end() + 600]
        nm = re.search(r'"name":"([^"]+ @ [^"]+)"', t)
        st = re.search(r'"startTime":"([^"]+)"', t)
        if nm and st and mm.group(1) not in out:
            out[mm.group(1)] = (nm.group(1), st.group(1))
    return out


def main():
    s = pagefile.read()
    sched = json.loads(re.search(r"var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    db = sqlite3.connect(DB)
    club = {w: a for w, a in db.execute("select written, abbr from club_name")}
    keyed = {}
    unsettled = []
    for eid, (name, start) in book_events().items():
        a, h = [x.strip() for x in name.split(" @ ", 1)]
        if club.get(a) and club.get(h):
            keyed[(club[a], club[h], start[:10])] = eid
        else:
            unsettled.append(name)
    old = re.search(r"  var WATCH = (\{.*?\});\n", s, re.S)
    watch = json.loads(old.group(1)) if old else {}
    tied = 0
    for g in sched:
        kick = T(g[2])
        eid = keyed.get((g[3], g[4], g[2][:10])) or keyed.get((g[3], g[4], (kick - dt.timedelta(days=1)).strftime("%Y-%m-%d")))
        if eid:
            watch[g[1]] = eid
            tied += 1
    print("theScore Bet NFL events: %d | tied to cards: %d | now in WATCH: %d" % (len(keyed) + len(unsettled), tied, len(watch)))
    if unsettled:
        print("not in the club register (%d): %s" % (len(unsettled), "; ".join(unsettled)))
    if DRY:
        return
    line = "  var WATCH = " + json.dumps(watch, separators=(",", ":")) + ";\n"
    if old:
        s = s[:old.start()] + line + s[old.end():]
    else:
        anchor = "  var PROPS = "
        assert anchor in s
        s = s.replace(anchor, line + anchor, 1)
    if not pagefile.write(s):
        print("the page changed while this run was reading -- nothing written")
        return
    pagefile.deployable(s)
    print("written")


if __name__ == "__main__":
    main()
