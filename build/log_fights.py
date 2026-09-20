"""Every number ESPN publishes during a bout, kept with the time we read it.

   ESPN shows a win probability that moves through a fight. We cannot see
   their model, but the numbers it is built from are all public and we were
   throwing every one of them away: strikes landed and thrown, knockdowns,
   takedowns, control time, the round and the clock. They exist only while
   the bout is being fought -- after it, the card carries a result and
   nothing of how it got there (Jose, Sep 19, 2026: "log that and the time we
   have it, so we can get a win probability thing like ESPN").

   So this sits on a card and writes a line every few seconds, per bout, per
   fighter. One line is one reading. The file is what a model would be fit
   to, later; nothing here models anything.

       python3 build/log_fights.py                 tonight's card, till it ends
       python3 build/log_fights.py --event 600060963
       python3 build/log_fights.py --every 5       seconds between readings
       python3 build/log_fights.py --once          one pass and stop

   Written to data/fight_log.jsonl, one JSON object per line, appended and
   never rewritten: a reading is a fact about a moment and nothing later
   changes it. Re-running on the same card adds more readings rather than
   replacing them, which is what makes it a record instead of a snapshot.
"""
import json
import os
import re
import sys
import time
import urllib.request

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "data", "fight_log.jsonl")
# plain http on purpose: this core host answers either way, and https through
# urllib fails on a Mac without a certificate bundle, which is where this runs
CORE = "http://sports.core.api.espn.com/v2/sports/mma/leagues/ufc"
UA = {"User-Agent": "Mozilla/5.0"}

KEEP = ("sigStrikesLanded", "sigStrikesAttempted", "totalStrikesLanded",
        "totalStrikesAttempted", "takedownsLanded", "takedownsAttempted",
        "knockDowns", "submissions", "timeInControl", "controlTime",
        "sigDistanceHeadStrikesLanded", "sigDistanceBodyStrikesLanded",
        "sigDistanceLegStrikesLanded", "sigGroundStrikesLanded",
        "sigClinchHeadStrikesLanded", "reversals")


def ask(url, tries=3):
    for _ in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20)
            return json.load(r)
        except Exception:
            time.sleep(1)
    return {}


def arg(flag, fallback=None):
    if flag in sys.argv:
        i = sys.argv.index(flag)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return fallback


def tonights_event():
    """The fight card the board is showing for today, by its own rows."""
    page = open(os.path.join(D, "master.html")).read()
    m = re.search(r"var FIGHTS = (\[\[.*?\]\]);", page, re.S)
    if not m:
        return None
    today = time.strftime("%Y-%m-%d", time.gmtime())
    soon = time.strftime("%Y-%m-%d", time.gmtime(time.time() + 86400))
    best = None
    for f in json.loads(m.group(1)):
        day = str(f[2])[:10]
        if day in (today, soon):
            best = best or f[0]
    return best


def bouts_of(event_id):
    """Every competition on the card, with both men and their stat refs."""
    d = ask("%s/events/%s/competitions?limit=50" % (CORE, event_id))
    out = []
    for it in d.get("items", []):
        ref = it.get("$ref") or ""
        comp = ask(ref.replace("https://", "http://"))
        if not comp:
            continue
        men = []
        for c in comp.get("competitors", []):
            aid = str((c.get("athlete") or {}).get("$ref", "")).split("/athletes/")[-1].split("?")[0]
            men.append({"id": aid, "stats": (c.get("statistics") or {}).get("$ref", ""),
                        "order": c.get("order")})
        out.append({"bout": str(comp.get("id")), "men": men,
                    "status": (comp.get("status") or {}).get("$ref", "")})
    return out


def name_of(athlete_id, cache={}):
    if athlete_id not in cache:
        a = ask("%s/../../athletes/%s" % (CORE, athlete_id)) or {}
        if not a:
            a = ask("http://sports.core.api.espn.com/v2/sports/mma/athletes/%s" % athlete_id)
        cache[athlete_id] = a.get("displayName") or athlete_id
    return cache[athlete_id]


def read_stats(ref):
    if not ref:
        return {}
    s = ask(ref.replace("https://", "http://"))
    out = {}
    for cat in s.get("splits", {}).get("categories", []):
        for st in cat.get("stats", []):
            if st.get("name") in KEEP:
                out[st["name"]] = st.get("value", st.get("displayValue"))
    return out


def one_pass(bouts, fh):
    """A reading of every bout being fought. Returns how many are still on."""
    live = 0
    for b in bouts:
        st = ask(b["status"].replace("https://", "http://")) if b["status"] else {}
        t = (st.get("type") or {})
        state = t.get("state")
        rd = st.get("period") or 0
        # a bout ESPN calls "in" during the walkouts has no round yet and
        # nothing to say; one that is over is written once and then left
        if state == "in" and rd >= 1:
            live += 1
        elif state != "post":
            continue
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "bout": b["bout"], "state": state, "round": rd,
               "clock": st.get("displayClock"), "secs": st.get("clock"),
               "result": ((st.get("result") or {}).get("displayName")),
               "men": []}
        for m in b["men"]:
            row["men"].append({"id": m["id"], "name": name_of(m["id"]),
                               "order": m.get("order"), "stats": read_stats(m["stats"])})
        if not any(mm["stats"] for mm in row["men"]) and state == "post":
            continue
        fh.write(json.dumps(row, separators=(",", ":")) + "\n")
        fh.flush()
    return live


def main():
    event = arg("--event") or tonights_event()
    if not event:
        print("no card on the board for today")
        return
    every = int(arg("--every", "8"))
    print("card %s | a reading every %ds | writing %s" % (event, every, OUT))
    bouts = bouts_of(event)
    print("bouts on the card: %d" % len(bouts))
    if not bouts:
        return
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    fh = open(OUT, "a")
    started = time.time()
    quiet = 0
    while True:
        live = one_pass(bouts, fh)
        if "--once" in sys.argv:
            break
        # the card is over when nothing has been live for a long stretch, or
        # after nine hours, whichever comes first -- a bill does not run longer
        quiet = 0 if live else quiet + 1
        if quiet > int(3600 / every) or time.time() - started > 9 * 3600:
            print("card finished; %d readings on file" % sum(1 for _ in open(OUT)))
            break
        time.sleep(every)
    fh.close()


if __name__ == "__main__":
    main()
