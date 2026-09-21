"""The UFC's own numbers for a card, round by round.

   ESPN publishes forty-three numbers a fighter and we keep all of them
   (log_fights.py). The UFC publishes more, and publishes them as official:
   every strike by target and by position for each round, how long the fight
   spent at distance, in the clinch and on the ground, control time split by
   where the control was -- back, mount, side, half guard, guard -- and the
   judges' cards with each judge named. ESPN has none of the last three.

   The door is ufc.com's own event page: each bout carries a data-fmid, which
   is the id in the fragment of a link to it (Jose, Sep 20, 2026, pointing at
   ufc.com/event/cryptocom-ufc-331#13017). The stats hang off that id:

       https://d29dxerjsp82wz.cloudfront.net/api/v3/fight/live/<fmid>.json

   What it does not carry is which hand or foot threw a strike. Nothing public
   does; that is tracking data, and it does not exist for the cage.

   Written to data/ufc_official.jsonl, one line a bout, rewritten for a bout
   read again -- unlike the live log, these are settled numbers rather than a
   reading taken at a moment.

       python3 build/ufc_official.py cryptocom-ufc-331
       python3 build/ufc_official.py https://www.ufc.com/event/cryptocom-ufc-331
       python3 build/ufc_official.py --fight 13017
"""
import collections
import json
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "ufc_official.jsonl")
STATS = "https://d29dxerjsp82wz.cloudfront.net/api/v3/fight/live/%s.json"
EVENT = "https://www.ufc.com/event/%s"


def fmids(slug):
    """Every bout on the card, in the order the page writes them."""
    r = rq.get(EVENT % slug, impersonate="chrome", timeout=30)
    if r.status_code != 200:
        print("the event page answered %d for %s" % (r.status_code, slug))
        return []
    return list(dict.fromkeys(re.findall(r'data-fmid="(\d+)"', r.text)))


def bout(fmid):
    try:
        r = rq.get(STATS % fmid, impersonate="chrome", timeout=25)
        if r.status_code != 200:
            return None
        d = (r.json() or {}).get("LiveFightDetail")
    except Exception:
        return None
    if not d:
        return None
    men = {str(f.get("FighterId")): f.get("Name") or {} for f in (d.get("Fighters") or [])}
    return {
        "fmid": str(fmid),
        "event": ((d.get("Event") or {}).get("Name")),
        "event_id": ((d.get("Event") or {}).get("EventId")),
        "status": d.get("Status"),
        "official": d.get("OfficialStats"),
        "segment": d.get("CardSegment"),
        "weight": d.get("WeightClass"),
        "referee": d.get("Referee"),
        "men": [{"id": str(f.get("FighterId")), "mma_id": f.get("MMAId"),
                 "name": f.get("Name"), "corner": f.get("Corner"),
                 "stance": f.get("Stance"), "reach": f.get("Reach"),
                 "height": f.get("Height"), "record": f.get("Record"),
                 "outcome": f.get("Outcome")}
                for f in (d.get("Fighters") or [])],
        "result": d.get("Result"),
        "totals": d.get("FightStats"),
        "rounds": d.get("RoundStats"),
        "names": men,
    }


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--fight" in sys.argv:
        ids = [sys.argv[sys.argv.index("--fight") + 1]]
    else:
        slug = (args[0] if args else "").rsplit("/", 1)[-1].split("#")[0]
        if not slug:
            sys.exit("which card? build/ufc_official.py cryptocom-ufc-331")
        ids = fmids(slug)
        print("%s: %d bouts" % (slug, len(ids)))
    with ThreadPoolExecutor(6) as ex:
        got = [b for b in ex.map(bout, ids) if b]
    # The page's footer ticker carries a data-fmid of its own -- the card's id,
    # not a bout's -- and the stats answer it with some other card entirely.
    # Rather than guess which id is which by how it is written, every bout is
    # asked and the ones that name a different card are dropped and said out
    # loud (Sep 20, 2026).
    if len(got) > 1:
        seen = collections.Counter(b["event_id"] for b in got)
        mine = seen.most_common(1)[0][0]
        for b in got:
            if b["event_id"] != mine:
                print("   %s belongs to %s, not this card -- left out"
                      % (b["fmid"], b.get("event")))
        got = [b for b in got if b["event_id"] == mine]
    held = {}
    if os.path.exists(OUT):
        for line in open(OUT):
            try:
                row = json.loads(line)
            except ValueError:
                continue
            held[row.get("fmid")] = row
    for b in got:
        held[b["fmid"]] = b
    with open(OUT, "w") as f:
        for k in sorted(held, key=lambda x: int(x) if str(x).isdigit() else 0):
            f.write(json.dumps(held[k], separators=(",", ":")) + "\n")
    for b in got:
        names = " v ".join(m["name"].get("LastName") or m["name"].get("FirstName") or "?"
                           if isinstance(m["name"], dict) else str(m["name"])
                           for m in b["men"])
        res = (b.get("result") or {})
        rounds = len(((b.get("rounds") or [{}])[0] or {}).get("Rounds") or [])
        print("   %-6s %-28s %-22s %d rounds  %s" % (
            b["fmid"], names, res.get("Method") or "-", rounds,
            "official" if b.get("official") else "unofficial"))
    print("%d bouts on file at %s" % (len(held), OUT))


if __name__ == "__main__":
    main()
