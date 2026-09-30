"""Every passer's season in clips, for the Clips page (Jose, Sep 29, 2026).

   For each NFL game on the board that is over, the scoring plays in its saved
   result (site/final/<id>.json) are read for the two passers the card names:
   a touchdown pass is "... pass from <passer> (...)", a rushing touchdown is
   "<passer> N Yd Rush|Run". Only those two men can be the passer or runner, so
   a surname ties a line to him (the board's rule for names within one game).
   Each line is then found, by the very same text, in the clip indexes the
   cards already play from:

       xindex.json      the clubs' posts on X: the mp4 itself
       clubindex.json   the clubs' own sites: an mcp id /clip answers
       nflindex.json    nfl.com: an external id /clip answers with the game

   Writes site/qbclips.json:
       {espn id: {"name", "club", "clips": [{"gid", "wk", "kind": "ptd"|"rtd",
                  "text", "headline", "src" | "mcp" | "ext"}]}}
   oldest game first.

       python3 build/qb_clips.py
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(D, "site")


def load(name):
    try:
        return json.load(open(os.path.join(SITE, name)))
    except (OSError, ValueError):
        return {}


def last(name):
    words = [w for w in str(name or "").split() if not re.match(r"^(Jr\.?|Sr\.?|II|III|IV|V)$", w)]
    return (words[-1] if words else "").lower()


def main():
    s = pagefile.read()
    m = re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S)
    sched = json.loads(m.group(1)) if m else []
    xi, ci, ni = load("xindex.json"), load("clubindex.json"), load("nflindex.json")
    out = {}
    for g in sorted(sched, key=lambda g: g[2]):
        gid, wk = str(g[1]), g[0]
        f = os.path.join(SITE, "final", gid + ".json")
        if not os.path.exists(f):
            continue
        try:
            plays = (json.load(open(f)).get("scoringPlays") or [])
        except ValueError:
            continue
        men = [(g[5], str(g[6] or ""), g[3]), (g[7], str(g[8] or ""), g[4])]
        for p in plays:
            text = p.get("text") or ""
            kind, who = None, None
            mm = re.search(r" pass from (.+?) \(", text) or re.search(r" pass from (.+?)$", text)
            if mm:
                kind, who = "ptd", mm.group(1)
            else:
                mm = re.match(r"^(.+?) \d+ Yd (Rush|Run)\b", text)
                if mm:
                    kind, who = "rtd", mm.group(1)
            if not kind:
                continue
            hit = [x for x in men if x[1] and last(x[0]) == last(who)]
            if len(hit) != 1:
                continue
            name, pid, club = hit[0]
            clip = {"gid": gid, "wk": wk, "kind": kind, "text": text, "headline": ""}
            for rows, key in ((xi, "src"), (ci, "mcp"), (ni, "ext")):
                row = next((r for r in rows.get(gid) or [] if r.get("text") == text and r.get(key)), None)
                if row:
                    clip[key] = row[key]
                    clip["headline"] = row.get("headline") or ""
                    break
            if not any(k in clip for k in ("src", "mcp", "ext")):
                continue
            q = out.setdefault(pid, {"name": name, "club": club, "clips": []})
            q["club"] = club
            q["clips"].append(clip)
    json.dump(out, open(os.path.join(SITE, "qbclips.json"), "w"), separators=(",", ":"))
    print("qb_clips: %d passers, %d clips (%d TD passes, %d rushing TDs)" % (
        len(out), sum(len(q["clips"]) for q in out.values()),
        sum(1 for q in out.values() for c in q["clips"] if c["kind"] == "ptd"),
        sum(1 for q in out.values() for c in q["clips"] if c["kind"] == "rtd")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
