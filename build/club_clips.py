"""The touchdowns the club's own site cut a clip of.

   Every club site runs nfl.com's platform. Its /video/ listing links each
   highlight by a slug that names the play, and the video page carries the
   clip's mcpID, which nfl.com's play call answers directly (clip.js takes
   ?mcp=). So for each touchdown pass with no clip on X or nfl.com, the
   scoring club's listing is read and a slug naming the scorer and a
   touchdown is taken; the page then gives the mcpID and the headline.

   Rushing touchdowns count too. Reading passes only is why Lamar Jackson's
   5-yard run against the Colts showed no clip while the Ravens' own site had
   it as "Lamar Jackson Scores First Touchdown of Ravens' Regular Season".
   (Jose found it, Sep 17, 2026)

   Usage:  python3 club_clips.py            (touchdowns still without a clip)
           python3 club_clips.py --force    (every touchdown)
"""
import datetime as dt
import html
import json
import os
import re
import sys

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile
OUT = os.path.join(D, "site", "clubindex.json")
FORCE = "--force" in sys.argv

# the clubs' own domains, from nfl.com's team pages (clubs.json), keyed by ESPN's abbreviation
SITE = {k: v["site"] for k, v in json.load(open(os.path.join(D, "data", "clubs.json"))).items()}


TD = re.compile(r"(^|-)(td|touchdown|six|scores?)(-|$)")
ORD = {1: r"\b(first|1st)\b", 2: r"(second|2nd)", 3: r"(third|3rd)", 4: r"(fourth|4th)"}
REEL = re.compile(r"(^|-)(every|best-plays|top-plays|performance|game-highlights|full-highlights|recap|mic-d|mic-up|press|presser|interview|reaction|preseason|scrums?|availability)(-|$)")


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def get(u):
    return rq.get(u, impersonate="chrome124", timeout=45)


def played():
    s = pagefile.read()
    now = dt.datetime.now(dt.timezone.utc)
    arr = json.loads(re.search(r'var SCHED = (\[\[.*?\]\]);', s, re.S).group(1))
    return [g for g in arr if T(g[2]) < now]


def load(name):
    p = os.path.join(D, "site", name)
    return json.load(open(p)) if os.path.exists(p) else {}


def key(slug, title):
    """One string to match on: the slug and the title, title written like a slug --
       some clubs name the play in the slug, some only in the title (49ers:
       'deebotd16x9' / 'Mike Evans' 2-Yard Touchdown Catch from Brock Purdy')."""
    t = re.sub(r"[^a-z0-9]+", "-", html.unescape(title).lower()).strip("-")
    return slug + "--" + t


def slugs(dom):
    """Every video on the club's listing as {slug: (title, mcpID)}, newest first,
       fifteen pages deep. The listing embeds its playlists as JSON, each entry
       carrying slug, title and mcpID, so no video page has to be opened."""
    out = {}
    for n in range(1, 16):
        r = get("https://www.%s/video/?page=%d" % (dom, n))
        found = {}
        for blob in re.findall(r'<script type="application/json" id="(?:playlist|video-config)-[^"]+">(.*?)</script>', r.text, re.S):
            try:
                cfg = json.loads(blob)
            except ValueError:
                continue
            for v in cfg.get("playlist") or []:
                if v.get("slug"):
                    found.setdefault(v["slug"], (v.get("title") or "", str(v.get("mcpID") or ""),
                                                 v.get("posterImage") or v.get("imageSrc") or ""))
        for sl in re.findall(r'/video/([a-z0-9-]+)', r.text):
            found.setdefault(sl, ("", "", ""))
        new = {k: v for k, v in found.items() if k not in out}
        if not new:
            break
        out.update(new)
    return out


def siblings(dom, slug):
    """The neighbours a club's video page carries in its own playlist."""
    out = {}
    h = get("https://www.%s/video/%s" % (dom, slug)).text
    for blob in re.findall(r'<script type="application/json" id="(?:playlist|video-config)-[^"]+">(.*?)</script>', h, re.S):
        try:
            cfg = json.loads(blob)
        except ValueError:
            continue
        for v in cfg.get("playlist") or []:
            if v.get("slug"):
                out.setdefault(v["slug"], (v.get("title") or "", str(v.get("mcpID") or ""),
                                           v.get("posterImage") or v.get("imageSrc") or ""))
    return out


def deepen(dom, cache, token):
    """The clubs' listings ignore ?page= -- every page hands back the same
       newest set -- so a clip more than a week or two old is invisible to the
       listing alone. Any video page of this game's own week carries a playlist
       of neighbours that reaches back, so those are opened and merged. Lamar
       Jackson's 5-yard run against the Colts was sitting one hop away.
       (Jose found it, Sep 17, 2026)"""
    seeds = [sl for sl in list(cache[dom]) if token and token in sl][:6]
    grew = 0
    for sl in seeds:
        for k, v in siblings(dom, sl).items():
            if k not in cache[dom]:
                cache[dom][k] = v
                grew += 1
    return grew


def page(dom, slug):
    h = get("https://www.%s/video/%s" % (dom, slug)).text
    m = re.search(r'<script type="application/json" id="video-config-[^"]+">(.*?)</script>', h, re.S)
    if not m:
        return None
    cfg = json.loads(m.group(1))
    for v in cfg.get("playlist") or []:
        if v.get("slug") == slug and v.get("mcpID"):
            return {"mcp": str(v["mcpID"]), "headline": v.get("title") or ""}
    return None


def main():
    have = load("clubindex.json")
    x, nfl = load("xindex.json"), load("nflindex.json")
    cache = {}
    deepened = set()
    for g in played():
        eid = g[1]
        covered = {r["text"] for r in x.get(eid, []) + nfl.get(eid, []) + have.get(eid, [])}
        d = get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=%s" % eid).json()
        rows = have.get(eid, [])
        claimed = set()
        # every touchdown in order, so a scorer's nth is known
        PASS = r"^(.+?) (\d+) Yd pass from ([^(]+)"
        RUSH = r"^(.+?) (\d+) Yd (?:Rush|Run)\b"
        plays = [p for p in (d.get("scoringPlays") or [])
                 if re.match(PASS, p.get("text") or "") or re.match(RUSH, p.get("text") or "")]
        seen = {}
        for p in plays:
            text = p.get("text") or ""
            m = re.match(PASS, text)
            kind = "pass" if m else "rush"
            if not m:
                m = re.match(RUSH, text)
            if not m or (text in covered and not FORCE):
                continue
            club = ((p.get("team") or {}).get("abbreviation") or "").lower()
            dom = SITE.get(club)
            if not dom:
                print("  no site for", club)
                continue
            who = [w for w in m.group(1).lower().split() if w.rstrip(".") not in ("jr", "sr", "ii", "iii", "iv")][-1]
            yds = m.group(2)
            seen[who] = seen.get(who, 0) + 1
            nth = seen[who]
            total = sum(1 for q in plays if q["text"].split(" ")[0:1] and
                        re.match(r"^(.+?) \d+ Yd", q["text"]).group(1).split()[-1].lower() == who)
            if dom not in cache:
                cache[dom] = slugs(dom)
            # the slug must name the scorer and a touchdown; the yardage settles
            # which one. Without yardage, a slug is taken only when it is a single
            # play (not a reel) and no other touchdown in the game already took it.
            keys = {sl: key(sl, t[0]) for sl, t in cache[dom].items()}
            # a title naming the catcher, the yardage and a touchdown is the play whatever
            # else it says; without the yardage a reel or a presser is not it
            def other_play(k, kind=None):
                # a different yardage is a different play, and so is a title
                # naming the other kind of score
                # a yardage that belongs to the drive is not the play's:
                # "Jonathan Taylor's first TD caps off Colts' 65-yard opening
                # drive" is the 1-yard score (Jose, Sep 17, 2026)
                y = re.findall(r"(\d+)-y(?:ar)?d(?!(?:-\w+){0,2}-drive)", k)
                if y and yds not in y:
                    return True
                if kind == "rush":
                    return bool(re.search(r"pass-to|passes-to|touchdown-(pass|catch|reception)|"
                                          r"\d+-yard-(td-)?(catch|reception|strike)", k))
                return bool(re.search(r"rushes-for|rushing-(td|touchdown)|\d+-yard-(td-|touchdown-)?run(-|$)", k))
            exact = [sl for sl, k in keys.items()
                     if who in k and TD.search(k) and yds + "-yard" in k and not other_play(k, kind)]
            named = exact or [sl for sl, k in keys.items()
                              if who in k and TD.search(k) and not REEL.search(k) and not other_play(k, kind)]
            if not named and (dom, eid) not in deepened:
                deepened.add((dom, eid))
                if deepen(dom, cache, "week-%s" % g[0]):
                    keys = {sl: key(sl, t[0]) for sl, t in cache[dom].items()}
                    exact = [sl for sl, k in keys.items()
                             if who in k and TD.search(k) and yds + "-yard" in k and not other_play(k, kind)]
                    named = exact or [sl for sl, k in keys.items()
                                      if who in k and TD.search(k) and not REEL.search(k) and not other_play(k, kind)]
            passer = m.group(3).strip().split()[-1].lower() if kind == "pass" else ""
            hit = [s for s in named if yds + "-yard" in keys[s]]
            if not hit:
                others = [s for s in named if s not in claimed]
                # a title that names a different one of his touchdowns is that
                # one, not this one: Henry's 4-yard score was losing to the clip
                # titled "third touchdown" (Jose, Sep 17, 2026)
                others = [s for s in others
                          if not any(j != nth and ORD.get(j) and re.search(ORD[j], keys[s])
                                     for j in ORD)]
                # two left and the passer named on one of them settles it
                ordinal = [s for s in others if ORD.get(nth) and re.search(ORD[nth], keys[s])]
                if ordinal:
                    hit = ordinal[:1]
                elif len(others) == 1:
                    hit = others
                elif passer and len(others) > 1 and sum(1 for s in others if passer in keys[s]) == 1:
                    hit = [s for s in others if passer in keys[s]]
                elif len(others) == 1 and total - nth + 1 == 1:
                    hit = others
                elif len(others) == total - nth + 1:
                    hit = others[-1:]          # listing is newest first: the oldest left is this one
            if hit:
                claimed.add(hit[0])
            if not hit:
                print("  %-9s %-46s not on %s" % (club.upper(), text[:46], dom))
                continue
            title, mcp, poster = cache[dom][hit[0]]
            v = {"mcp": mcp, "headline": html.unescape(title), "poster": poster} if mcp else page(dom, hit[0])
            if not v:
                print("  %-9s %-46s page without an mcp id" % (club.upper(), text[:46]))
                continue
            rows = [r for r in rows if r["text"] != text]
            rows.append({"text": text, "mcp": v["mcp"], "headline": v["headline"], "poster": v.get("poster") or ""})
            print("  %-9s %-46s mcp %s  %s" % (club.upper(), text[:46], v["mcp"], v["headline"][:50]))
        if rows:
            have[eid] = rows
    json.dump(have, open(OUT, "w"), separators=(",", ":"))
    print("rows in clubindex.json: %d" % sum(len(v) for v in have.values()))


if __name__ == "__main__":
    main()
