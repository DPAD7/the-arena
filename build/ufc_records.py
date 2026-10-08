"""Every fighter's whole pro record, for the hold on a UFC card's record.

Holding a fighter's record on a bout card lifts his career over the board
(Jose, Oct 8, 2026): his record and pro fight count, the path through the
promotions (Other / DWCS / UFC tiles, LEFT where he walked out of the UFC),
the streak and his UFC record with CUT RISK, CHAMP, OFF and RETURNING on that
line, his losses by method, and every fight newest first with its closing
odds, his rank against the man across, TITLE and UPSET tags. The NEXT row --
the bout on the board, its price and any weight change -- is drawn by the
page from the card itself, so it is always the live price.

The pro records are gidstats first and Sherdog where gidstats has nobody
(data/ufc_records/fights.csv and people.csv, pulled Oct 7, 2026); the ranks
at the time are the UFC's own panel history (rankings.csv). Bouts the board
has settled since the pull are added from site/final/mma-*.json, so a record
is never a card behind.

    python3 build/ufc_records.py        -> site/ufc_records.json
"""
import csv, glob, html, json, os, re, sys, unicodedata
from datetime import date, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pagefile

D = os.path.join(ROOT, "data", "ufc_records")
OUT = os.path.join(ROOT, "site", "ufc_records.json")
FACES = os.path.join(ROOT, "site", "faces", "mma")


def nz(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", x.replace(".", "").replace("-", " ").replace("'", "")).strip()


def ln(x):
    p = [w for w in nz(x).split() if w not in ("jr", "sr", "ii", "iii")]
    return p[-1] if p else ""


def esc(x):
    return html.escape(str(x), quote=True)


MAJ = ["UFC", "Bellator", "PFL", "ONE", "RIZIN", "Strikeforce", "WEC"]


def promo(e):
    e = e or ""
    if "Contender" in e:
        return "DWCS"
    for m in MAJ:
        if e.startswith(m) or (m == "Bellator" and "Bellator" in e):
            return m
    return "Other"


def num(x):
    try:
        return int(float(str(x).replace("+", "")))
    except (TypeError, ValueError):
        return None


# ---- the board: who is on it, and each man's ESPN id ----
s = pagefile.read()
FIGHTS = json.loads(re.search(r"var FIGHTS = (\[\[.*?\]\]);", s, re.S).group(1))
ID = {}                                  # normalized name -> ESPN id
for f in FIGHTS:
    for n, i in ((f[3], f[4]), (f[5], f[6])):
        if i:
            ID.setdefault(nz(n), str(i))

# ---- settled bouts on the board, newest results the pull may not have ----
FINALS = []
for fp in glob.glob(os.path.join(ROOT, "site", "final", "mma-*.json")):
    try:
        ev = json.load(open(fp))["events"][0]
    except Exception:
        continue
    for c in ev.get("competitions", []):
        cs = c.get("competitors") or []
        if len(cs) != 2 or not (c.get("status", {}).get("type", {}).get("completed")):
            continue
        for a in cs:
            n = (a.get("athlete") or {}).get("displayName")
            if n and a.get("id"):
                ID.setdefault(nz(n), str(a["id"]))
        FINALS.append(dict(event=ev.get("name", ""), date=(c.get("date") or ev.get("date", ""))[:10],
                           how=c.get("how") or {}, cs=cs))

# ---- the pull ----
people = list(csv.DictReader(open(os.path.join(D, "people.csv"))))
BYNAME = {}
for p in people:
    BYNAME.setdefault(nz(p["name"]), []).append(p)
FBY = {}
for r in csv.DictReader(open(os.path.join(D, "fights.csv"))):
    if r["result"] in ("win", "loss", "draw", "NC"):
        FBY.setdefault(r["page_url"], []).append(r)

RK = {}
for r in csv.DictReader(open(os.path.join(D, "rankings.csv"))):
    if "Pound" in r["weightclass"]:
        continue
    RK.setdefault(r["date"], {}).setdefault(ln(r["fighter"]), []).append(int(r["rank"]))
RKD = sorted(RK)


def rank_at(name, d):
    prev = [x for x in RKD if x <= d]
    if not prev:
        return None
    if (datetime.fromisoformat(d) - datetime.fromisoformat(prev[-1])).days > 60:
        return None
    h = RK[prev[-1]].get(ln(name))
    if not h:
        return "NR"
    return "C" if min(h) == 0 else "#%d" % min(h)


CR = json.load(open(os.path.join(ROOT, "site", "fighter_ranks.json")))


def has_face(i):
    return bool(i) and (os.path.exists(os.path.join(FACES, i + ".webp")) or os.path.exists(os.path.join(FACES, i + ".png")))


def face(name, cls="rh-fc"):
    i = ID.get(nz(name))
    if has_face(i):
        return '<img class="%s" src="face/mma/%s.png" alt="" onerror="var s=document.createElement(\'span\');s.className=this.className;this.replaceWith(s)">' % (cls, i)
    return '<span class="%s"></span>' % cls


def page_for(name, opps):
    """the pull's page for a board name: the one name, and where two men share
    it, the one who has fought a man the board has him facing"""
    c = BYNAME.get(nz(name)) or []
    c = [p for p in c if p["page_url"] in FBY]
    if len(c) <= 1:
        return c[0]["page_url"] if c else None
    best = max(c, key=lambda p: (len({ln(r["opponent"]) for r in FBY[p["page_url"]]} & opps), p.get("last_fight", "")))
    return best["page_url"]


def lbs(div):
    m = re.match(r"(\d+)\s*lbs", div or "")
    return int(m.group(1)) if m else None


def build(name, eid, opps):
    pu = page_for(name, opps)
    if not pu:
        return None
    g = sorted(FBY[pu], key=lambda r: r["date"])
    have = {(r["date"], ln(r["opponent"])) for r in g}
    last = g[-1]["date"] if g else ""
    # bouts settled on the board after the pull
    for b in FINALS:
        me = [a for a in b["cs"] if str(a.get("id")) == eid]
        if not me or b["date"] <= last:
            continue
        me = me[0]; op = [a for a in b["cs"] if a is not me][0]
        on = (op.get("athlete") or {}).get("displayName", "")
        if (b["date"], ln(on)) in have:
            continue
        t = (b["how"].get("type") or "")
        res = "win" if me.get("winner") else ("loss" if op.get("winner") else ("NC" if "No Contest" in t else "draw"))
        meth = "Decision" if "Decision" in t else "Submission" if "Submission" in t else "Draw" if "Draw" in t else ("KO/TKO" if t else "")
        g.append(dict(date=b["date"], result=res, opponent=on, event=b["event"], method=meth,
                      round=str(b["how"].get("round") or ""), time=b["how"].get("time") or "", odds="", title="", division=""))
    g.sort(key=lambda r: r["date"])
    for r in g:
        r["pr"] = promo(r["event"])

    segs = []
    for r in g:
        if not segs or segs[-1]["pr"] != r["pr"]:
            segs.append(dict(pr=r["pr"], w=0, l=0, d=0, y0=r["date"][2:4], y1=r["date"][2:4]))
        sg = segs[-1]; sg["y1"] = r["date"][2:4]
        if r["result"] == "win": sg["w"] += 1
        elif r["result"] == "loss": sg["l"] += 1
        elif r["result"] == "draw": sg["d"] += 1
    while len(segs) > 5:          # fold neighbouring non-UFC stretches, never a UFC one
        for i in range(len(segs) - 1):
            a, b = segs[i], segs[i + 1]
            if a["pr"] != "UFC" and b["pr"] != "UFC":
                segs[i:i + 2] = [dict(pr=a["pr"] if a["pr"] == b["pr"] else "Other", w=a["w"] + b["w"], l=a["l"] + b["l"],
                                      d=a["d"] + b["d"], y0=a["y0"], y1=b["y1"])]
                break
        else:
            break
    tiles = ""; seen = False
    for i, sg in enumerate(segs):
        rec = "%d-%d" % (sg["w"], sg["l"]) + ("-%d" % sg["d"] if sg["d"] else "")
        yrs = "'%s" % sg["y0"] if sg["y0"] == sg["y1"] else "'%s–'%s" % (sg["y0"], sg["y1"])
        if sg["pr"] != "UFC" and seen and i > 0 and segs[i - 1]["pr"] == "UFC":
            tiles += '<div class="rh-left">LEFT</div>'
        if sg["pr"] == "UFC" and seen:
            yrs += " back"
        if sg["pr"] == "UFC":
            seen = True
        tiles += '<div class="rh-t%s"><b>%s</b><span>%s</span><small>%s</small></div>' % (" rh-ufc" if sg["pr"] == "UFC" else "", rec, sg["pr"], yrs)

    W = sum(r["result"] == "win" for r in g); L = sum(r["result"] == "loss" for r in g)
    Dr = sum(r["result"] == "draw" for r in g); NC = sum(r["result"] == "NC" for r in g)
    res = [r["result"] for r in reversed(g) if r["result"] in ("win", "loss")]
    st = ""
    if res:
        k = 1
        while k < len(res) and res[k] == res[0]:
            k += 1
        st = ("W" if res[0] == "win" else "L") + str(k)
    u = [r for r in g if r["pr"] == "UFC"]
    uw = sum(r["result"] == "win" for r in u); ul = sum(r["result"] == "loss" for r in u); ud = sum(r["result"] == "draw" for r in u)
    run = 0
    for r in reversed(u):
        if r["result"] == "loss": run += 1
        elif r["result"] == "win": break
    chips = ""
    if run >= 3 or (run >= 2 and uw <= 1):
        chips += '<span class="rh-chip rh-risk">&#9888; CUT RISK</span>'
    cr = CR.get(name.lower()) or CR.get(nz(name))
    if cr and cr.get("r") == "C":
        tw = sum(1 for r in u if r["result"] == "win" and len(r.get("title") or "") > 3)
        chips += '<span class="rh-chip rh-champ">&#9813; CHAMP%s</span>' % (" · %d UFC TITLE WIN%s" % (tw, "" if tw == 1 else "S") if tw else "")
    if g:
        off = (date.today() - date.fromisoformat(g[-1]["date"])).days / 365.25
        if off >= 2:
            chips += '<span class="rh-chip rh-ret">RETURNING · %.1f YRS OFF</span>' % off
        elif off >= 1:
            chips += '<span class="rh-chip rh-lay">OFF %.1f YRS</span>' % off

    rows = ""
    for r in reversed(g):
        mt = r.get("method") or ""
        m = "Dec" if "Dec" in mt else "Sub" if "Sub" in mt else "Draw" if "Draw" in mt else ("NC" if r["result"] == "NC" else ("KO" if mt else ""))
        t = "" if (not r.get("time") or m == "Dec") else " " + r["time"]
        o = num(r.get("odds"))
        od = "–" if o is None else "%+d" % o
        ti = '<span class="rh-tg rh-ti">TITLE</span>' if (r.get("title") or "").strip() else ""
        cls, lt = {"win": ("rh-w", "W"), "loss": ("rh-l", "L"), "draw": ("rh-d", "D"), "NC": ("rh-nc", "NC")}[r["result"]]
        rk = ""
        if r["pr"] == "UFC":
            a, b = rank_at(name, r["date"]), rank_at(r["opponent"], r["date"])
            if (a and a != "NR") or (b and b != "NR"):
                rk = ' · <span class="rh-rk">%s vs %s</span>' % (a or "NR", b or "NR")
        up = ""
        if o is not None:
            if r["result"] == "win" and o >= 100: up = '<span class="rh-tg rh-up">UPSET</span>'
            if r["result"] == "loss" and o <= -200: up = '<span class="rh-tg rh-dn">UPSET LOSS</span>'
        rd = (" R%s" % r["round"]) if (r.get("round") or "").strip() else ""
        when = datetime.fromisoformat(r["date"]).strftime("%b %-d '%y")
        rows += ('<div class="rh-r"><b class="%s">%s</b><div class="rh-o"><div>%s%s<span class="rh-tg">%s</span>%s%s</div>'
                 '<small>%s%s%s</small></div><div class="rh-od">%s</div></div>') % (
            cls, lt, face(r["opponent"]), esc(r["opponent"]), r["pr"], ti, up, (m + rd + t + " · ") if (m + rd + t).strip() else "", when, rk, od)

    rec = "%d-%d" % (W, L) + ("-%d" % Dr if Dr else "") + (" (%d NC)" % NC if NC else "")
    lo = [r for r in g if r["result"] == "loss"]
    lossline = ('<div class="rh-loss">Losses: %d KO · %d Sub · %d Dec</div>' % (
        sum("KO" in (r.get("method") or "") for r in lo), sum("Sub" in (r.get("method") or "") for r in lo),
        sum("Dec" in (r.get("method") or "") for r in lo))) if lo else ""
    if cr:
        rank = '<span class="rh-crk">%s<i>%s</i></span>' % ("CHAMP" if cr["r"] == "C" else "#%s" % cr["r"], esc(cr["d"].upper()))
    else:
        rank = '<span class="rh-crk rh-nr">NR</span>'
    surname = esc(name.split()[-1].upper() if name.split()[-1].lower() not in ("jr", "jr.", "ii", "iii") else " ".join(name.split()[-2:]).upper())
    last_lb = next((lbs(r.get("division")) for r in reversed(g) if lbs(r.get("division"))), None)
    return dict(
        head='<h3>%s<span class="rh-nm">%s %s</span><small>%d pro fights</small>%s</h3>' % (face(name, "rh-hf"), surname, rec, len(g), rank),
        path=tiles,
        st='Streak <b class="%s">%s</b> · UFC overall %d-%d%s' % ("rh-sw" if st[:1] == "W" else "rh-sl", st or "–", uw, ul, "-%d" % ud if ud else ""),
        chips=chips, loss=lossline, rows=rows, uw=uw, ul=ul, lb=last_lb)


def main():
    out = {}
    who = {}
    today = date.today().isoformat()
    for f in FIGHTS:
        if f[2][:10] < today:
            continue
        for n, i, on in ((f[3], f[4], f[5]), (f[5], f[6], f[3])):
            if i and not re.search(r"\bTBA\b|TBD", n):
                who.setdefault(str(i), [n, set()])[1].add(ln(on))
    for f in FIGHTS:                                 # every man the board has him facing
        for n, i, on in ((f[3], f[4], f[5]), (f[5], f[6], f[3])):
            if str(i) in who:
                who[str(i)][1].add(ln(on))
    miss = []
    for i, (n, opps) in sorted(who.items()):
        r = build(n, i, opps)
        if r:
            out[i] = r
        else:
            miss.append(n)
    if "--dry" in sys.argv:
        print("ufc_records: %d fighters (dry, not written)" % len(out)); return
    json.dump(out, open(OUT, "w"), separators=(",", ":"))
    print("ufc_records: %d fighters, %d KB%s" % (len(out), os.path.getsize(OUT) // 1024,
                                                  ("; no record for " + ", ".join(miss)) if miss else ""))


if __name__ == "__main__":
    main()
