"""A rewind for a bout the recorder never saw, rebuilt from the record.

   The recorder (log_fights.py) reads ESPN every six seconds while a card is
   fought, and anim.py cuts that into the rewind. A card it missed -- 9/22,
   9/26, and UFC 331's early bouts, before it ran on GitHub -- has no such
   log, and ESPN keeps no timing for a strike once the bout is over. What is
   kept (Jose, Sep 28, 2026: "sure"):

     ufcstats.com   the official count for every round of a UFC bout: each
                    man's landed and thrown, significant by head, body and leg
                    and by distance, clinch and ground, knockdowns and control
     ESPN           the timed moments -- takedowns, knockdowns, submission
                    attempts, round starts -- the result, the round and the
                    time it ended, and the winner. For a Contender Series bout,
                    which ufcstats does not carry, ESPN's whole-fight count

   From these it writes the same samples the recorder would have: one at the
   start, one at the end of every round, one at the finish. anim.py's own
   cut() then spreads each round's strikes evenly through that round, so a
   rebuilt rewind is right round by round, and the called moments land at
   their real second -- only the order of strikes inside a round is not the
   night's. Each one carries "rebuilt": "rounds" (or "fight" for a Contender
   Series bout) to say so.

   ufcstats sits behind a browser check, so it is read with playwright.

       python3 build/anim_rebuild.py              every finished bout with no rewind
       python3 build/anim_rebuild.py 401911630    one bout
"""
import datetime as dt
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anim
import log_fights

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "anim")
WON = os.path.join(D, "data", "fight_winners.json")
NOW = dt.datetime.now(dt.timezone.utc)


def fold(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z ]", "", s).split()


def last(s):
    bits = [b for b in fold(s) if b not in ("jr", "sr", "ii", "iii")]
    return bits[-1] if bits else ""


def fights():
    s = open(os.path.join(D, "master.html"), encoding="utf-8").read()
    m = re.search(r"  var FIGHTS = (\[\[.*?\]\]);", s, re.S)
    return json.loads(m.group(1)) if m else []


def espn(eid, bout):
    base = "%s/events/%s/competitions/%s" % (log_fights.CORE, eid, bout)
    c = log_fights.ask(base)
    if not c:
        return None
    st = log_fights.ask(base + "/status")
    plays = []
    p = log_fights.ask(base + "/plays?limit=400") or {}
    for it in p.get("items") or []:
        plays.append({"what": (it.get("type") or {}).get("text") or "",
                      "round": (it.get("period") or {}).get("number") or 0,
                      "clock": (it.get("clock") or {}).get("displayValue")})
    men = []
    for m in c.get("competitors") or []:
        men.append({"id": str(m.get("id")), "winner": m.get("winner"),
                    "stats": (m.get("statistics") or {}).get("$ref")})
    return {"status": st or {}, "plays": plays, "men": men, "format": c.get("format") or {}}


# -- ufcstats ----------------------------------------------------------------

def of(x):
    m = re.match(r"(\d+) of (\d+)", x.strip())
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def secs(x):
    m = re.match(r"(\d+):(\d\d)", x.strip())
    return int(m.group(1)) * 60 + int(m.group(2)) if m else 0


class Stats:
    """ufcstats, read through one headless browser for the whole run."""

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self.p = sync_playwright().start()
        # the runner's own Chrome on GitHub; playwright's here
        self.b = None
        for kw in ({"channel": "chrome"}, {}):
            try:
                self.b = self.p.chromium.launch(**kw)
                break
            except Exception:
                continue
        if not self.b:
            self.p.stop()
            raise RuntimeError("no Chrome")
        self.pg = self.b.new_page()
        self.events = None

    def close(self):
        self.b.close()
        self.p.stop()

    def html(self, url):
        self.pg.goto(url)
        h = ""
        for _ in range(30):
            self.pg.wait_for_timeout(700)
            try:
                self.pg.wait_for_load_state("load")
                h = self.pg.content()
            except Exception:
                continue          # the check is still moving the page on
            if "Checking your browser" not in h:
                break
        return h

    def event(self, when, names):
        """The ufcstats event on that date holding a bout between these two."""
        if self.events is None:
            h = self.html("http://ufcstats.com/statistics/events/completed?page=all")
            self.events = re.findall(r'href="(http://ufcstats.com/event-details/[0-9a-f]+)"', h)
        return self.events

    def fight(self, names, date):
        """The per-round tables for the bout between these two men."""
        want = {last(n) for n in names}
        for ev in self.event(date, names)[:12]:
            h = self.html(ev)
            day = re.search(r"Date:\s*</i>\s*([A-Za-z]+ \d+, \d{4})", h)
            if day:
                try:
                    d = dt.datetime.strptime(day.group(1), "%B %d, %Y").date()
                    if abs((d - date).days) > 1:
                        continue
                except ValueError:
                    pass
            for row in re.findall(r'data-link="(http://ufcstats.com/fight-details/[0-9a-f]+)"(.*?)</tr>', h, re.S):
                who = {last(x) for x in re.findall(r'fighter-details/[0-9a-f]+">\s*([^<]+?)\s*</a>', row[1])}
                if want <= who:
                    return self.rounds(row[0])
        return None

    def rounds(self, url):
        self.html(url)
        tables = self.pg.evaluate("""(() => [...document.querySelectorAll('table')].map(t =>
            [...t.querySelectorAll('tr')].map(r => [...r.querySelectorAll('th,td')].map(c =>
              [...c.querySelectorAll('p')].map(p => p.innerText.trim()).filter(Boolean).length
                ? [...c.querySelectorAll('p')].map(p => p.innerText.trim()) : [c.innerText.trim()]))))()""")
        # tables: 0 totals, 1 totals by round, 2 significant, 3 significant by round
        if len(tables) < 4:
            return None
        per = []
        # a round's row holds both men in each cell; headers and the "Round n"
        # rows hold one
        two = lambda r: len(r[0]) == 2 and len(r[1]) == 2 and str(r[1][0]).isdigit()
        tot_rows = [r for r in tables[1] if len(r) >= 10 and two(r)]
        sig_rows = [r for r in tables[3] if len(r) >= 9 and len(r[0]) == 2 and "of" in str(r[1][0])]
        for tr, sr in zip(tot_rows, sig_rows):
            names = tr[0]
            one = {}
            for i in (0, 1):
                kd = int(tr[1][i] or 0)
                sig = of(tr[2][i])
                tot = of(tr[4][i])
                ctrl = secs(tr[9][i]) if len(tr) > 9 else 0
                head, body, leg = of(sr[3][i]), of(sr[4][i]), of(sr[5][i])
                dist, clin, grd = of(sr[6][i]), of(sr[7][i]), of(sr[8][i])
                one[names[i]] = {"kd": kd, "sig": sig[0], "tot": tot, "ctrl": ctrl, "head": head[0],
                                 "body": body[0], "leg": leg[0], "dist": dist[0], "clin": clin[0], "grd": grd[0]}
            per.append(one)
        return per


def as_espn(r):
    """One round of ufcstats as the keys ESPN's feed carries. ufcstats counts
       target and range separately, ESPN crossed: the clinch is counted as
       head, as ESPN counts it; the body and leg strikes as at distance; the
       rest of the distance strikes as head; the ground is whatever is left."""
    body = min(r["body"], r["dist"])
    leg = min(r["leg"], r["dist"] - body)
    return {"sigDistanceHeadStrikesLanded": max(0, r["dist"] - body - leg),
            "sigDistanceBodyStrikesLanded": body, "sigDistanceLegStrikesLanded": leg,
            "sigClinchHeadStrikesLanded": r["clin"], "sigStrikesLanded": r["sig"],
            "totalStrikesLanded": r["tot"][0], "totalStrikesAttempted": r["tot"][1],
            "knockDowns": r["kd"], "timeInControl": r["ctrl"]}


def add(a, b):
    return {k: (a.get(k) or 0) + (b.get(k) or 0) for k in set(a) | set(b)}


def samples(bout, card, e, per):
    """The recorder's samples, as it would have written them."""
    st = e["status"]
    fr = int(st.get("period") or 1)
    into = float(st.get("clock") or 0)
    result = ((st.get("result") or {}).get("displayName")) or ""
    L, R = card["L"], card["R"]
    zero = {"sigStrikesLanded": 0}
    out = [{"bout": bout, "at": "0", "state": "in", "round": 1, "clock": "5:00",
            "men": [{"id": L[1], "stats": zero}, {"id": R[1], "stats": zero}]}]
    if per:
        # match ufcstats' two men to the card's left and right by surname
        def pick(one, who):
            for k, v in one.items():
                if last(k) == last(who):
                    return v
            return None
        cum = {L[1]: {}, R[1]: {}}
        for n, one in enumerate(per[:fr], 1):
            for man in (L, R):
                got = pick(one, man[0])
                if got is None:
                    return None
                cum[man[1]] = add(cum[man[1]], as_espn(got))
            row = {"bout": bout, "at": str(n), "round": n,
                   "men": [{"id": L[1], "stats": dict(cum[L[1]])}, {"id": R[1], "stats": dict(cum[R[1]])}]}
            if n < fr:
                row.update({"state": "in", "clock": "0:00"})
            else:
                row.update({"state": "post", "clock": st.get("displayClock"), "secs": into, "result": result})
            out.append(row)
        return out
    # the Contender Series: ESPN's count for the whole fight, at the finish
    men = []
    for m in e["men"]:
        men.append({"id": m["id"], "stats": log_fights.read_stats(m["stats"])})
    if not any(m["stats"] for m in men):
        return None
    out.append({"bout": bout, "at": "1", "state": "post", "round": fr, "clock": st.get("displayClock"),
                "secs": into, "result": result, "men": men})
    return out


def main(only=None):
    cards = anim.cards()
    idx_path = os.path.join(OUT, "index.json")
    index = json.load(open(idx_path)) if os.path.exists(idx_path) else {}
    won = json.load(open(WON)) if os.path.exists(WON) else {}
    todo = []
    for f in fights():
        bout = str(f[1])
        try:
            t = dt.datetime.fromisoformat(f[2].replace("Z", "+00:00"))
        except ValueError:
            continue
        if only and bout != only:
            continue
        if not only and (bout in index or not (NOW - dt.timedelta(days=21) < t < NOW - dt.timedelta(hours=6))):
            continue
        todo.append((f, t))
    if not todo:
        print("rebuild: every finished bout has its rewind")
        return
    us = None
    done, skipped = 0, []
    try:
        for f, t in todo:
            bout, eid = str(f[1]), str(f[0])
            card = cards.get(bout)
            e = espn(eid, bout)
            if not card or not e or ((e["status"].get("type") or {}).get("state")) != "post":
                skipped.append((bout, "not over, or not on ESPN"))
                continue
            per = None
            dwcs = False
            if us is None:
                try:
                    us = Stats()
                except Exception as x:
                    us = False
                    print("ufcstats: no browser here (%s)" % type(x).__name__)
            if us:
                per = us.fight((f[3], f[5]), t.astimezone(dt.timezone(dt.timedelta(hours=-5))).date())
            if not per:
                dwcs = True
            s = samples(bout, card, e, per)
            if not s:
                skipped.append((bout, "no count to rebuild from"))
                continue
            wname = next((f[3] if m["id"] == str(f[4]) else f[5] for m in e["men"] if m.get("winner")), None)
            if wname:
                won[bout] = wname
            if not card.get("rounds"):
                card["rounds"] = ((e["format"].get("regulation") or {}).get("periods"))
            d = anim.cut(bout, s, e["plays"], card, wname)
            if len([x for x in d["ev"] if not x.get("state")]) < 5:
                skipped.append((bout, "too few strikes"))
                continue
            d["rebuilt"] = "fight" if dwcs else "rounds"
            json.dump(d, open(os.path.join(OUT, bout + ".json"), "w"), separators=(",", ":"))
            index[bout] = {"names": d["names"], "rounds": d["rounds"], "how": d["how"]}
            done += 1
            print("%s %-24s %s R%s %s  ev %d  moments %d  won %s  (%s)" % (
                bout, " v ".join(d["names"]), d["how"], d["fr"], d["fc"], len(d["ev"]),
                len(d["moments"]), d["winner"], d["rebuilt"]))
    finally:
        if us:
            us.close()
    json.dump(index, open(idx_path, "w"), separators=(",", ":"))
    json.dump(won, open(WON, "w"), indent=1)
    print("rebuilt: %d bouts, index of %d" % (done, len(index)))
    for b, why in skipped:
        print("skipped %s: %s" % (b, why))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
