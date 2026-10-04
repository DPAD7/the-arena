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
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
# ARENA_LIVE=1: a second recorder started mid-card keeps its own files, so it
# can never clash with the one already running (Oct 3, 2026)
SUB = "live" if os.environ.get("ARENA_LIVE") else ""
os.makedirs(os.path.join(D, "data", SUB), exist_ok=True)
OUT = os.path.join(D, "data", SUB, "fight_log.jsonl")
# the moments, as against the running totals: round start and end, takedowns
# and attempts, knockdowns, a pause and why, the result. Each carries the time
# it happened, which a total never can (Jose, Sep 19, 2026)
PLAYS = os.path.join(D, "data", SUB, "fight_plays.jsonl")
# plain http on purpose: this core host answers either way, and https through
# urllib fails on a Mac without a certificate bundle, which is where this runs
CORE = "http://sports.core.api.espn.com/v2/sports/mma/leagues/ufc"
UA = {"User-Agent": "Mozilla/5.0"}

# Everything, not a chosen dozen. ESPN publishes forty-three numbers a man and
# this kept twelve of them, which threw away the whole grid: where a strike was
# thrown from crossed with what it was aimed at -- distance, clinch and ground
# against head, body and leg, landed and attempted -- and the grappling with it
# (half guard, side, mount, back, slams). A reading is a fact about a moment
# and we cannot go back for the rest of it, so the log keeps all of it and
# whoever reads it later decides what matters (Jose, Sep 20, 2026: "can we tell
# where the strike came from?" -- we can, but only from the night we kept it).
KEEP = None      # None means keep every number the feed carries


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
    page = pagefile.read()
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
        out.append({"bout": str(comp.get("id")), "men": men, "event": str(event_id),
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
            if KEEP is None or st.get("name") in KEEP:
                out[st["name"]] = st.get("value", st.get("displayValue"))
    return out


def seen_plays():
    """Every play already on file, so a re-run adds and never repeats."""
    have = set()
    if os.path.exists(PLAYS):
        for line in open(PLAYS):
            try:
                have.add(json.loads(line)["id"])
            except Exception:
                pass
    return have


def log_plays(bout, fh, have):
    """The moments of one bout, each written once."""
    d = ask("%s/events/%s/competitions/%s/plays?limit=300"
            % (CORE, bout.get("event", ""), bout["bout"])) if bout.get("event") else {}
    if not d.get("items"):
        return 0
    wrote = 0
    for it in d["items"]:
        play = ask(it["$ref"].replace("https://", "http://")) if "$ref" in it else it
        pid = str(play.get("id") or "")
        if not pid or pid in have:
            continue
        have.add(pid)
        fh.write(json.dumps({
            "id": pid, "bout": bout["bout"], "seq": play.get("sequenceNumber"),
            "what": ((play.get("type") or {}).get("text")),
            "round": ((play.get("period") or {}).get("number")),
            "clock": ((play.get("clock") or {}).get("displayValue")),
            "wallclock": play.get("wallclock"),
        }, separators=(",", ":")) + "\n")
        wrote += 1
    fh.flush()
    return wrote


def one_pass(bouts, fh, done):
    """A reading of every bout being fought. Returns how many are still on,
       and how many are still to come. A bout in `done` has had its result
       written and is not asked about again."""
    live, ahead = 0, 0
    for b in bouts:
        if b["bout"] in done:
            continue
        st = ask(b["status"].replace("https://", "http://")) if b["status"] else {}
        t = (st.get("type") or {})
        state = t.get("state")
        rd = st.get("period") or 0
        # a bout ESPN calls "in" during the walkouts has no round yet and
        # nothing to say; one that is over is written once and then left
        if state == "in" and rd >= 1:
            live += 1
        elif state == "post":
            done.add(b["bout"])
        else:
            ahead += 1
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
    return live, ahead


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
    ph = open(PLAYS, "a")
    have = seen_plays()
    print("plays already on file: %d" % len(have))
    started = time.time()
    done = set()
    while True:
        live, ahead = one_pass(bouts, fh, done)
        for b in bouts:
            if b["bout"] not in done or live:
                log_plays(b, ph, have)
        if "--once" in sys.argv:
            break
        # The card is over the moment its last bout is: nothing on, nothing
        # still to come. It used to wait an hour of quiet after that, asking
        # ESPN about every finished bout every six seconds the whole time,
        # and ran until five in the morning on a card that ended at one
        # (Jose, Sep 20, 2026: "it needs to stop polling after the last fight
        # goes final"). Nine hours is the backstop for a card that never says.
        if (not live and not ahead) or time.time() - started > float(arg("--hours", "9")) * 3600:
            print("card finished: %d of %d bouts final; %d readings on file"
                  % (len(done), len(bouts), sum(1 for _ in open(OUT))))
            break
        # nothing on yet: no need to look every few seconds for the walkouts
        time.sleep(every if live else max(every, 60))
    fh.close()
    ph.close()


if __name__ == "__main__":
    main()
