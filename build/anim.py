"""The fight, cut for playback: site/anim/<bout>.json and site/anim/index.json.

   Every six seconds through a card, log_fights.py writes what ESPN says each
   man has landed -- by target and by range -- and where the clock stands;
   fight_plays.jsonl carries the moments ESPN calls out, takedowns, knockdowns,
   submission attempts, pauses. This turns that into what the card plays back:

     ev       every strike, one entry each, spread evenly across the six
              seconds it arrived in: {t, w, k, p, sig} for a significant one
              (w = a|b who threw it, k = head|body|leg, p = d|c|g for range),
              {t, w, grey} for a landed one ESPN did not call significant,
              {t, w, miss} for one thrown and missed, kd:1 on the one that put
              a man down; and {t, state, cl, gr, ac, bc} once a sample, saying
              how many clinch and ground strikes came in and how much control
              each man added, which is what moves the seam and turns the card
     moments  the called moments, on the same clock
     stop     the second the bout ended; how, fr, fc the method, round, time
     won      0 if the man on the left of the card won, 1 for the right
     fb       where the finishing strike landed

   The left man on the card is a and red; the right is b and blue -- the same
   order the card draws them in, read from FIGHTS in master.html, so the
   playback can never put a man on the wrong side of his own card.

   The feed breaks significant strikes down by distance head/body/leg and
   clinch head only; whatever is significant and neither is taken as ground.
   Total strikes have no breakdown at all, so a landed non-significant strike
   is grey and a missed one is hollow, and both land anywhere.

   Usage:  python3 build/anim.py            every logged bout
           python3 build/anim.py 401905375  one bout
"""
import glob
import json
import os
import re
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
LOG = os.path.join(D, "data", "fight_log.jsonl")
PLAYS = os.path.join(D, "data", "fight_plays.jsonl")
WON = os.path.join(D, "data", "fight_winners.json")
OUT = os.path.join(D, "site", "anim")

HOW = {"ko/tko": "TKO", "ko": "KO", "tko": "TKO", "submission": "SUB", "sub": "SUB",
       "decision - unanimous": "UD", "decision - split": "SD", "decision - majority": "MD",
       "u dec": "UD", "s dec": "SD", "m dec": "MD", "decision": "DEC", "dq": "DQ", "nc": "NC"}
KEEP = ("Takedown Attempt", "Takedown", "Knockdown", "Submission Attempt", "Reversal",
        "Round Pause", "Round Unpause", "Round Start")
SIG = [("sigDistanceHeadStrikesLanded", "head", "d"), ("sigDistanceBodyStrikesLanded", "body", "d"),
       ("sigDistanceLegStrikesLanded", "leg", "d"), ("sigClinchHeadStrikesLanded", "head", "c")]


def rows(path):
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            yield json.loads(line)
        except ValueError:
            continue


def clock_secs(s):
    m = re.match(r"^(\d+):(\d\d)$", str(s or ""))
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def cards():
    """the card's own left and right, by ESPN id, per bout"""
    s = pagefile.read()
    i = s.index("  var FIGHTS = [[")
    j = s.index("];", i)
    out = {}
    for f in json.loads(s[i + len("  var FIGHTS = "):j + 1]):
        out[str(f[1])] = {"L": (f[3], str(f[4])), "R": (f[5], str(f[6]))}
    # the market says how many rounds the bout was for. site/prices.json, not
    # the copy baked into the page: the baked one is the thin eleven-market
    # read and carries no "rounds", which is how Tsarukyan's five-round bout
    # was drawn with three (Sep 20, 2026)
    try:
        fp = json.load(open(os.path.join(D, "site", "prices.json"))).get("FPROPS") or {}
    except (ValueError, OSError):
        fp = {}
    for b in out:
        out[b]["rounds"] = (fp.get(b) or {}).get("rounds")
    return out


def last_name(n):
    # a suffix is not a surname: Raul Rosas Jr. is ROSAS (Sep 28, 2026)
    bits = [b for b in str(n or "").strip().split(" ")
            if b.lower().strip(".,") not in ("jr", "sr", "ii", "iii", "iv")]
    return (bits[-1] if bits else "").upper()


def cut(bout, samples, plays, card, won_name):
    samples = sorted(samples, key=lambda r: r["at"])
    # a = left of the card, b = right
    side = {card["L"][1]: "a", card["R"][1]: "b"}
    names = [last_name(card["L"][0]), last_name(card["R"][0])]

    def t_of(r):
        left = clock_secs(r.get("clock"))
        rd = int(r.get("round") or 1)
        if r.get("state") == "post":
            # the result clock is time into the round
            into = r.get("secs") if isinstance(r.get("secs"), (int, float)) else (left or 0)
            return (max(1, rd) - 1) * 300 + float(into)
        if left is None:
            return None
        return (max(1, rd) - 1) * 300 + (300 - left)

    def stats(r):
        out = {}
        for m in r.get("men") or []:
            w = side.get(str(m.get("id")))
            if w:
                out[w] = m.get("stats") or {}
        return out

    ev, prev, prev_t = [], None, 0.0
    rounds_seen = 1
    for r in samples:
        if r.get("state") not in ("in", "post"):
            continue
        if r.get("state") == "in" and int(r.get("round") or 0) < 1:
            continue
        t = t_of(r)
        if t is None:
            continue
        rounds_seen = max(rounds_seen, int(r.get("round") or 1))
        now = stats(r)
        if prev is not None and t > prev_t:
            span = t - prev_t
            state = {"t": round(t), "state": 1, "cl": 0, "gr": 0, "ac": 0, "bc": 0}
            for w in ("a", "b"):
                p, n = prev.get(w) or {}, now.get(w) or {}
                d = lambda k: max(0, int((n.get(k) or 0) - (p.get(k) or 0)))
                got = []
                sig_sum = 0
                for key, k, pos in SIG:
                    c = d(key)
                    sig_sum += c
                    got += [{"w": w, "k": k, "p": pos, "sig": 1} for _ in range(c)]
                    if pos == "c":
                        state["cl"] += c
                ground = max(0, d("sigStrikesLanded") - sig_sum)
                state["gr"] += ground
                got += [{"w": w, "k": "head", "p": "g", "sig": 1} for _ in range(ground)]
                grey = max(0, d("totalStrikesLanded") - d("sigStrikesLanded"))
                got += [{"w": w, "grey": 1} for _ in range(grey)]
                miss = max(0, d("totalStrikesAttempted") - d("totalStrikesLanded"))
                got += [{"w": w, "miss": 1} for _ in range(miss)]
                kd = d("knockDowns")
                if kd:
                    heads = [g for g in got if g.get("k") == "head" and g.get("sig")]
                    (heads[-1] if heads else (got[-1] if got else None) or {}).update({"kd": 1})
                    if not got:
                        got.append({"w": w, "k": "head", "p": "d", "sig": 1, "kd": 1})
                state["ac" if w == "a" else "bc"] += d("timeInControl")
                # spread them across the sample, in the order they were counted
                n_got = len(got)
                for idx, g in enumerate(got):
                    g["t"] = round(prev_t + span * (idx + 1) / (n_got + 1), 2)
                    ev.append(g)
            ev.append(state)
        prev, prev_t = now, t
    ev.sort(key=lambda e: e["t"])

    last = samples[-1]
    post = [r for r in samples if r.get("state") == "post"]
    fin = post[-1] if post else last
    stop = t_of(fin) or prev_t
    how = HOW.get(str(fin.get("result") or "").lower().strip(), str(fin.get("result") or "").upper()[:4])
    fr = int(fin.get("round") or 0) or None
    fc = fin.get("clock") if fin.get("state") == "post" else None

    moments = []
    for p in sorted(plays, key=lambda p: (int(p.get("round") or 0), -(clock_secs(p.get("clock")) or 0))):
        w = p.get("what") or ""
        if not (w in KEEP or w.startswith("Pause Reason")):
            continue
        rd = int(p.get("round") or 0)
        left = clock_secs(p.get("clock"))
        if rd < 1:
            continue
        t = (rd - 1) * 300 + (300 - left if left is not None else 0)
        moments.append({"t": t, "what": w})

    won = None
    if won_name:
        if last_name(won_name) == names[0]:
            won = 0
        elif last_name(won_name) == names[1]:
            won = 1
    # where the finishing strike landed: the winner's last significant one
    fb = "head"
    if won is not None and how in ("TKO", "KO"):
        wsig = [e for e in ev if e.get("w") == ("a" if won == 0 else "b") and e.get("sig") and e.get("k")]
        if wsig:
            fb = wsig[-1]["k"]

    rounds = card.get("rounds") or max(3, rounds_seen)
    return {"bout": bout, "names": names, "rounds": rounds, "ev": ev, "moments": moments,
            "stop": round(stop, 2), "how": how, "fr": fr, "fc": fc, "won": won,
            "winner": last_name(won_name) if won_name else None, "fb": fb}


def main(only=None):
    card = cards()
    won = json.load(open(WON)) if os.path.exists(WON) else {}
    by, plays = {}, {}
    for r in rows(LOG):
        by.setdefault(str(r.get("bout")), []).append(r)
    for p in rows(PLAYS):
        plays.setdefault(str(p.get("bout")), []).append(p)
    os.makedirs(OUT, exist_ok=True)
    index = {}
    for f in glob.glob(os.path.join(OUT, "*.json")):
        if os.path.basename(f) != "index.json":
            try:
                d = json.load(open(f))
                index[str(d["bout"])] = {"names": d["names"], "rounds": d["rounds"], "how": d["how"]}
            except (ValueError, KeyError):
                pass
    done, skipped = 0, []
    for bout, samples in by.items():
        if only and bout != only:
            continue
        if bout not in card:
            skipped.append((bout, "not on a card"))
            continue
        if not any(r.get("state") == "post" for r in samples):
            skipped.append((bout, "never saw it end"))
            continue
        d = cut(bout, samples, plays.get(bout, []), card[bout], won.get(bout))
        if len([e for e in d["ev"] if not e.get("state")]) < 5:
            skipped.append((bout, "too few strikes logged"))
            continue
        json.dump(d, open(os.path.join(OUT, bout + ".json"), "w"), separators=(",", ":"))
        index[bout] = {"names": d["names"], "rounds": d["rounds"], "how": d["how"]}
        done += 1
        print("%s %-22s %s R%s %s  ev %d  moments %d  won %s" % (
            bout, " v ".join(d["names"]), d["how"], d["fr"], d["fc"], len(d["ev"]), len(d["moments"]), d["winner"]))
    json.dump(index, open(os.path.join(OUT, "index.json"), "w"), separators=(",", ":"))
    print("written: %d bouts, index of %d" % (done, len(index)))
    for b, why in skipped:
        print("skipped %s: %s" % (b, why))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
