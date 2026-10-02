"""A game's win probability, drawn play by play, with the NFL gamebook's own
   words pinned to every play that swung it (Jose, Oct 1, 2026: "map the win
   probability with the way the game went, like the chart, and then the plays
   from the gamebook").

   ESPN's settled file (site/final/<id>.json) carries the home side's chance
   after each play and the plays themselves; the NFL's gamebook PDF carries the
   official play-by-play. A play is matched to the gamebook by quarter and
   clock; where none matches, ESPN's own words stand.

       python3 build/wpchart.py 401872950 [--swing 7] [--out file.html]
"""
import collections
import html
import json
import os
import re
import subprocess
import sys
import tempfile

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(D, "build"))
import pagefile

QTR = {"First": 1, "Second": 2, "Third": 3, "Fourth": 4, "Overtime": 5}


def arg(name, default=None):
    if name in sys.argv and sys.argv.index(name) + 1 < len(sys.argv):
        return sys.argv[sys.argv.index(name) + 1]
    return default


def team(abbr):
    """Name, nickname and colour from ESPN's team page."""
    try:
        t = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/%s" % abbr.lower(),
                   impersonate="chrome", timeout=20).json()["team"]
        col = t.get("color") or "888888"
        r, g, b = (int(col[i:i + 2], 16) for i in (0, 2, 4))
        if 0.2126 * r + 0.7152 * g + 0.0722 * b < 60:      # black on black: the second colour
            col = t.get("alternateColor") or "888888"
        return t.get("displayName") or abbr, (t.get("name") or abbr).lower(), "#" + col
    except Exception:
        return abbr, abbr.lower(), "#888888"


def gamebook(away_nick, home_nick, week):
    """The gamebook's plays: [(quarter, clock, text)]."""
    url = "https://www.nfl.com/games/%s-at-%s-2026-reg-%d" % (away_nick, home_nick, week)
    h = rq.get(url, impersonate="chrome", timeout=30).text
    ids = collections.Counter(re.findall(r"[0-9a-f]{8}-[0-9a-f]{4}-11f1-[0-9a-f]{4}-[0-9a-f]{12}", h))
    for u, _ in ids.most_common(8):
        r = rq.get("https://static.www.nfl.com/gamecenter/%s.pdf" % u, timeout=30)
        if r.status_code == 200 and r.content[:4] == b"%PDF":
            with tempfile.TemporaryDirectory() as tmp:
                p = os.path.join(tmp, "g.pdf")
                open(p, "wb").write(r.content)
                subprocess.run(["pdftotext", "-layout", p, p + ".txt"], check=True)
                text = open(p + ".txt").read()
            break
    else:
        return []
    out, q, cur = [], 0, None
    for line in text.split("\n"):
        m = re.search(r"Play By Play\s+(First|Second|Third|Fourth|Overtime) Quarter", line)
        if m:
            q = QTR[m.group(1)]
            continue
        if "Miscellaneous Statistics Report" in line or "Ten Longest Plays" in line:
            q = 0
        if not q:
            continue
        m = re.search(r"\((\d{0,2}:\d{2})\)\s*(.*)", line)
        if m:
            if cur:
                out.append(cur)
            cur = [q, m.group(1).lstrip("0") if m.group(1)[0] != ":" else "0" + m.group(1), m.group(2).strip()]
        elif (cur and line.strip() and len(line) - len(line.lstrip()) > 20 and not re.match(r"\s*\d-\d+-", line)
              and not re.search(r" vs .* at |\d+/\d+/\d{4}|Page \d", line)):
            cur[2] += " " + line.strip()
        elif cur:
            out.append(cur)
            cur = None
    if cur:
        out.append(cur)
    # the drive marks at the right edge (P1, R2) are not the play
    # the drive marks at the right edge (P1, R2) land mid-play once a wrapped
    # line is joined on
    return [(a, b, re.sub(r"\s[PRX]\d{1,2}(?=\s|$)", "", c).strip()) for a, b, c in out]


def clock_key(s):
    s = s.strip()
    if s.startswith(":"):
        s = "0" + s
    m, sec = s.split(":")
    return "%d:%02d" % (int(m), int(sec))


def main():
    gid = arg("--game") or next((a for a in sys.argv[1:] if a.isdigit()), None)
    swing = float(arg("--swing", "7")) / 100
    s = pagefile.read()
    sched = json.loads(re.search(r"  var SCHED = (\[\[.*?\]\]);", s, re.S).group(1))
    g = next(x for x in sched if str(x[1]) == str(gid))
    week, away, home = g[0], g[3], g[4]
    f = json.load(open(os.path.join(D, "site", "final", "%s.json" % gid)))
    comp = f["header"]["competitions"][0]
    score = {c["homeAway"]: c["score"] for c in comp["competitors"]}
    an, anick, acol = team(away)
    hn, hnick, hcol = team(home)
    plays = {p["id"]: p for d in f["drives"]["previous"] for p in d["plays"]}
    book = gamebook(anick, hnick, week)
    used = set()

    def official(p):
        q, ck = p["period"]["number"], clock_key(p["clock"]["displayValue"])
        for i, (bq, bc, bt) in enumerate(book):
            if i not in used and bq == q and clock_key(bc) == ck:
                used.add(i)
                return bt, True
        secs = lambda c: int(clock_key(c).split(":")[0]) * 60 + int(clock_key(c).split(":")[1])
        who = re.search(r"([A-Z][a-zA-Z]?\.[A-Z][A-Za-z'\-]+)", p.get("text") or "")
        best = None
        for i, (bq, bc, bt) in enumerate(book):
            if i in used or bq != q or abs(secs(bc) - secs(ck)) > 20:
                continue
            if who and who.group(1) not in bt:
                continue
            gap = abs(secs(bc) - secs(ck))
            if best is None or gap < best[0]:
                best = (gap, i, bt)
        if best:
            used.add(best[1])
            return best[2], True
        return p.get("text") or "", False

    pts = []          # (index, home %, play)
    for i, w in enumerate(f["winprobability"]):
        pts.append((i, 100 * w["homeWinPercentage"], plays.get(w["playId"])))
    print("wpchart: %d of %d chances tied to a play" % (sum(1 for x in pts if x[2]), len(pts)))
    swings = []
    for i in range(1, len(pts)):
        d = pts[i][1] - pts[i - 1][1]
        p = pts[i][2]
        if abs(d) >= swing * 100 and p:
            txt, ok = official(p)
            swings.append({"i": i, "d": d, "q": p["period"]["number"], "clock": p["clock"]["displayValue"],
                           "text": txt, "book": ok, "after": pts[i][1]})

    # the chart
    W, H, L, R, T, B = 760, 320, 44, 16, 18, 30
    n = len(pts) - 1 or 1
    X = lambda i: L + (W - L - R) * i / n
    Y = lambda v: T + (H - T - B) * (1 - v / 100)
    path = " ".join("%s%.1f,%.1f" % ("M" if k == 0 else "L", X(i), Y(v)) for k, (i, v, _) in enumerate(pts))
    qmarks = []
    lastq = 1
    for i, v, p in pts:
        if p and p["period"]["number"] != lastq:
            lastq = p["period"]["number"]
            qmarks.append((i, "Q%d" % lastq if lastq < 5 else "OT"))
    svg = ['<svg viewBox="0 0 %d %d" role="img" aria-label="win probability">' % (W, H)]
    svg.append('<rect x="%d" y="%d" width="%d" height="%.1f" fill="%s" opacity=".10"/>' % (L, T, W - L - R, Y(50) - T, hcol))
    svg.append('<rect x="%d" y="%.1f" width="%d" height="%.1f" fill="%s" opacity=".10"/>' % (L, Y(50), W - L - R, H - B - Y(50), acol))
    for v in (0, 25, 50, 75, 100):
        svg.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" class="grid%s"/>' % (L, W - R, Y(v), Y(v), " mid" if v == 50 else ""))
        svg.append('<text x="%d" y="%.1f" class="ax" text-anchor="end">%d</text>' % (L - 6, Y(v) + 4, v))
    svg.append('<text x="%d" y="%d" class="ax lab">%s</text>' % (L + 6, T + 14, html.escape(home)))
    svg.append('<text x="%d" y="%d" class="ax lab">%s</text>' % (L + 6, H - B - 6, html.escape(away)))
    for i, lab in qmarks:
        svg.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" class="q"/>' % (X(i), X(i), T, H - B))
        svg.append('<text x="%.1f" y="%d" class="ax" text-anchor="middle">%s</text>' % (X(i), H - 10, lab))
    svg.append('<text x="%d" y="%d" class="ax" text-anchor="start">Q1</text>' % (L + 2, H - 10))
    svg.append('<path d="%s" class="wp"/>' % path)
    for k, sw in enumerate(swings, 1):
        x, y = X(sw["i"]), Y(sw["after"])
        svg.append('<circle cx="%.1f" cy="%.1f" r="9" class="pin %s"/><text x="%.1f" y="%.1f" class="pinn" text-anchor="middle">%d</text>'
                   % (x, y, "up" if sw["d"] > 0 else "down", x, y + 3.5, k))
    svg.append("</svg>")

    rows = []
    for k, sw in enumerate(swings, 1):
        who = home if sw["d"] > 0 else away
        rows.append('<li><span class="n %s">%d</span><div><b>Q%s %s</b> &middot; %s %+.0f &rarr; %s %.0f%%'
                    '<p>%s</p></div></li>'
                    % ("up" if sw["d"] > 0 else "down", k, sw["q"] if sw["q"] < 5 else "OT", html.escape(sw["clock"]),
                       html.escape(who), abs(sw["d"]), html.escape(home), sw["after"],
                       html.escape(sw["text"]) + ("" if sw["book"] else ' <i>(ESPN)</i>')))
    out = arg("--out") or os.path.join(D, "notes", "wp-%s-%s-%s.html" % (away, home, gid))
    page = TEMPLATE % {
        "title": "%s at %s" % (away, home), "an": html.escape(an), "hn": html.escape(hn),
        "as": score["away"], "hs": score["home"], "wk": week, "svg": "".join(svg),
        "rows": "".join(rows), "n": len(swings), "sw": int(swing * 100),
        "hcol": hcol, "acol": acol, "matched": sum(1 for x in swings if x["book"]),
    }
    os.makedirs(os.path.dirname(out), exist_ok=True)
    open(out, "w").write(page)
    print("wpchart: %s at %s, %d plays, %d swings of %d+ points, %d in the gamebook's words -> %s"
          % (away, home, len(pts), len(swings), int(swing * 100), sum(1 for x in swings if x["book"]), out))


TEMPLATE = """<title>%(title)s Win Probability</title>
<meta charset="utf-8">
<style>
:root{color-scheme:dark;--ground:#000;--ink:#f2f2f2;--mute:#8b8b90;--line:#232326;--green:#17c257;--red:#ff5b5b}
body{background:var(--ground);color:var(--ink);font:15px/1.45 -apple-system,system-ui,sans-serif;margin:0;padding:20px 16px 40px}
.wrap{max-width:820px;margin:0 auto}
h1{font-size:20px;margin:0 0 2px;letter-spacing:.01em}
.sub{color:var(--mute);margin:0 0 16px;font-size:13px;letter-spacing:.06em;text-transform:uppercase}
.score{display:flex;gap:18px;font-variant-numeric:tabular-nums;font-weight:700;font-size:15px;margin-bottom:14px}
.chart{border:1px solid var(--line);border-radius:12px;padding:8px 4px}
svg{display:block;width:100%%;height:auto}
.grid{stroke:var(--line);stroke-width:1}.grid.mid{stroke:#55555a;stroke-dasharray:4 4}
.q{stroke:#3a3a3f;stroke-width:1}
.ax{fill:var(--mute);font-size:11px;font-variant-numeric:tabular-nums}.lab{font-weight:700;fill:#c8c8cc}
.wp{fill:none;stroke:var(--ink);stroke-width:2.2;stroke-linejoin:round}
.pin{stroke:#000;stroke-width:1.5}.pin.up{fill:%(hcol)s}.pin.down{fill:%(acol)s}
.pinn{fill:#fff;font-size:10px;font-weight:800;paint-order:stroke;stroke:#000;stroke-width:2px}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:22px 0 8px}
ol{list-style:none;padding:0;margin:0;display:grid;gap:8px}
li{display:flex;gap:12px;border:1px solid var(--line);border-radius:10px;padding:10px 12px}
li b{font-variant-numeric:tabular-nums}
li p{margin:4px 0 0;color:#d4d4d8;font-size:14px}
li i{color:var(--mute);font-style:normal;font-size:12px}
.n{flex:none;width:24px;height:24px;border-radius:7px;display:grid;place-items:center;font-weight:800;font-size:12px;color:#fff}
.n.up{background:%(hcol)s}.n.down{background:%(acol)s}
.note{color:var(--mute);font-size:12px;margin-top:14px}
</style>
<div class="wrap">
<h1>%(an)s at %(hn)s</h1>
<p class="sub">Week %(wk)s &middot; ESPN win probability, play by play</p>
<div class="score"><span>%(an)s %(as)s</span><span>%(hn)s %(hs)s</span></div>
<div class="chart">%(svg)s</div>
<h2>The %(n)s plays that moved it %(sw)s+ points</h2>
<ol>%(rows)s</ol>
<p class="note">The line is the home side's chance to win after each play; above the dashed line the home side is favored. Plays are in the NFL gamebook's words (%(matched)s of %(n)s matched by quarter and clock); the rest are ESPN's.</p>
</div>
"""

if __name__ == "__main__":
    main()
