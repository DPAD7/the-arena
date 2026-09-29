"""The page, rendered and measured before it deploys.

   Half the faults on this board were invisible in the code and obvious on the
   screen: cards shrunk, fonts gone, faces blank, a page that scrolls sideways.
   So the sweep opens the built site/index.html in a headless Chrome at a
   phone's width, with every file served from site/ and the functions
   answered empty, and measures what is painted:

     errors       the page throws nothing while it loads and moves between views
     width        the page never scrolls sideways, at 430 and at 390
     fonts        Barlow and Barlow Condensed are loaded, not the fallback
     pictures     no image on screen came back broken
     HOT          a card is 55 px tall on a 430 screen, in step with the width
     All          one card for each of the 32 clubs
     search       the starters' row holds all 32

   Prints one line per fault, each starting LOOK:, and returns the list to
   build/guard.py. Needs playwright; on GitHub it drives the runner's own
   Chrome, so nothing is downloaded.

       python3 build/look.py
"""
import json
import os
import sys

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(D, "site")
HOST = "https://the-arenasports.pages.dev"


def serve(route):
    req = route.request
    u = req.url.split("?")[0].split("#")[0]
    if not u.startswith(HOST):
        # ESPN and the rest of the world are not what is being tested
        return route.abort()
    path = u[len(HOST):].lstrip("/") or "index.html"
    if req.method != "GET":
        return route.fulfill(status=200, body="{}", content_type="application/json")
    f = os.path.join(SITE, path)
    if os.path.isfile(f):
        return route.fulfill(path=f)
    # /face/<league>/<id>.png is a function on the site; locally it is the mirror
    if path.startswith("face/"):
        f = os.path.join(SITE, "faces", path[5:])
        return route.fulfill(path=f) if os.path.isfile(f) else route.fulfill(status=404, body="")
    # the functions: state, ask, bets, clip, espn, face
    if path.startswith(("state", "ask", "bets", "clip", "espn")):
        return route.fulfill(status=200, body="{}", content_type="application/json")
    return route.fulfill(status=404, body="")


def launch(p):
    for kw in ({"channel": "chrome"}, {}):
        try:
            return p.chromium.launch(**kw)
        except Exception:
            continue
    return None


def drag(pg, cdp, x, y, dy):
    """A finger put down at x, y and drawn dy pixels down, the way a phone
    sends it."""
    pts = lambda yy: [{"x": x, "y": yy}]
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pts(y)})
    for k in range(1, 11):
        cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pts(y + dy * k / 10)})
        pg.wait_for_timeout(16)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    pg.wait_for_timeout(600)


def gestures(b, seen):
    """A drag belongs to what it starts on: the wallet drawn down never opens
    the search, and a pull at the top of the page always does (Sep 28, 2026)."""
    wrong = []
    c = b.new_context(viewport={"width": 430, "height": 932}, has_touch=True, is_mobile=True, device_scale_factor=1)
    pg = c.new_page()
    pg.route("**/*", serve)
    pg.goto(HOST + "/")
    pg.wait_for_timeout(4000)
    cdp = c.new_cdp_session(pg)
    opened = "document.querySelector('#qsearch').classList.contains('open')"
    close = "document.querySelector('#qsearch').classList.remove('open')"
    fab = pg.evaluate("""(() => { const f = document.querySelector('.cashfab'); if (!f) return null;
        const r = f.getBoundingClientRect(); return r.width ? [r.left + r.width / 2, r.top + r.height / 2] : null })()""")
    if fab:
        pg.evaluate("scrollTo(0, 0)")
        drag(pg, cdp, fab[0], fab[1], 160)
        if pg.evaluate(opened):
            wrong.append("drawing the wallet down opens the search")
        pg.evaluate(close)
        seen.append("wallet drag")
    for cls, what in ((".htrack", "the eye's track"), (".gcorner", "a hide corner"), (".drvg", "the live graph")):
        at = pg.evaluate("""s => { const f = [...document.querySelectorAll(s)].find(e => { const r = e.getBoundingClientRect();
            return r.width && r.top > 0 && r.bottom < innerHeight; }); if (!f) return null;
            const r = f.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2] }""", cls)
        if at:
            pg.evaluate("scrollTo(0, 0)")
            drag(pg, cdp, at[0], at[1], 120)
            if pg.evaluate(opened):
                wrong.append("drawing %s down opens the search" % what)
            pg.evaluate(close)
    # a price on the slip: the wallet rests above the slip bar's figures, and
    # steps out of the way of the slip's own sheet (audit, Sep 28, 2026)
    pg.evaluate("scrollTo(0, 0)")
    pg.evaluate("""(() => { if (!window.addLegs || typeof SCHED !== 'object') return;
        const g = SCHED.find(g => Date.parse(g[2]) > Date.now() && g[10]);
        if (g) window.addLegs([{ oid: g[10], o: g[9], g: String(g[1]), gn: g[3] + ' @ ' + g[4], l: g[3] + ' ML' }]); })()""")
    pg.wait_for_timeout(1200)
    lap = pg.evaluate("""(() => { const f = document.querySelector('.cashfab'), s = document.getElementById('slipbar');
        if (!f || !s || s.hidden) return null; const a = f.getBoundingClientRect(), b = s.getBoundingClientRect();
        return Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top)) *
               Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) > 0 })()""")
    if lap is None:
        seen.append("no slip bar to test")
    elif lap:
        wrong.append("the wallet sits on the slip bar")
    else:
        seen.append("wallet clear of slip")
        pg.evaluate("openSheet(document.getElementById('slipsheet'))")
        pg.wait_for_timeout(900)
        shown = pg.evaluate("""(() => { const d = document.querySelector('dialog.sheet[open]'), f = document.querySelector('.cashfab');
            return d && f ? getComputedStyle(f).opacity : null })()""")
        if shown is not None and float(shown) > 0.05:
            wrong.append("the wallet floats over an open sheet")
        pg.evaluate("document.querySelectorAll('dialog.sheet[open]').forEach(d => d.close())")
    pg.evaluate("scrollTo(0, 0)")
    top = pg.evaluate("""(() => { const m = document.querySelector('main, #board, .board') || document.body;
        const r = m.getBoundingClientRect(); return [innerWidth / 2, Math.max(r.top, 0) + 200] })()""")
    drag(pg, cdp, top[0], top[1], 160)
    if not pg.evaluate(opened):
        wrong.append("a pull down at the top of the page does not open the search")
    else:
        seen.append("pull-down")
    c.close()
    return wrong


def hot(b, seen):
    """HOT at every screen he uses: the cards 55px tall on a 430 phone and in
    step with the width, and the whole row above the nav -- on a short phone,
    an iPad and a desktop as much as on his own (audit, Sep 28, 2026)."""
    wrong = []
    for W, H, phone in ((430, 932, True), (390, 844, True), (1024, 1366, False), (1280, 900, False)):
        c = b.new_context(viewport={"width": W, "height": H}, device_scale_factor=1)
        pv = c.new_page()
        pv.route("**/*", serve)
        pv.add_init_script("try { localStorage.setItem('arena.fview', 'hot') } catch (e) {}")
        pv.goto(HOST + "/")
        pv.wait_for_timeout(3000)
        pv.evaluate("""(() => { const b = [...document.querySelectorAll('#sportbar button')]
            .find(b => (b.getAttribute('aria-label') || '') == 'Form'); if (b) b.click(); })()""")
        pv.wait_for_timeout(3000)
        r = pv.evaluate("""(() => { const cs = [...document.querySelectorAll('.qcards--hot .qcard')]
            .map(c => c.getBoundingClientRect()).filter(r => r.height && r.right > 0 && r.left < innerWidth);
            const nav = document.getElementById('sportbar').getBoundingClientRect();
            return cs.length ? { h: cs[0].height, bottom: Math.max(...cs.map(r => r.bottom)), nav: nav.top } : null })()""")
        if not r:
            wrong.append("HOT shows no cards at %dx%d" % (W, H))
        else:
            if phone:
                seen.append("HOT %.1fpx at %d" % (r["h"], W))
                if abs(r["h"] - 55 * W / 430) > 3:
                    wrong.append("HOT cards are %.0fpx tall at %d, not %.0f" % (r["h"], W, 55 * W / 430))
            if r["bottom"] > r["nav"] + 1:
                wrong.append("the HOT row runs under the nav at %dx%d (%.0f past %.0f)" % (W, H, r["bottom"], r["nav"]))
        c.close()
    return wrong


def fight_tab(b, seen):
    """The fights tab opens on the next card's month, wherever the other tabs
    were: week 8 of the NFL, then UFC, landed in November (Sep 28, 2026)."""
    c = b.new_context(viewport={"width": 430, "height": 932}, device_scale_factor=1)
    pv = c.new_page()
    pv.route("**/*", serve)
    pv.goto(HOST + "/")
    pv.wait_for_timeout(3000)
    tab = """s => { const b = [...document.querySelectorAll('#sportbar .sptab')].find(b => b.dataset.sp == s); if (b) b.click(); }"""
    pv.evaluate(tab, "nfl")
    pv.wait_for_timeout(1200)
    pv.evaluate("""(() => { const t = document.querySelector('#daybar [data-day="W8"]'); if (t) t.click(); })()""")
    pv.wait_for_timeout(1200)
    pv.evaluate(tab, "mma")
    pv.wait_for_timeout(1500)
    got, want = pv.evaluate("""(() => {
        const on = document.querySelector('#daybar [aria-selected="true"]');
        let n = null; FIGHTS.forEach(f => { const t = Date.parse(f[2]); if (t >= Date.now() - 8 * 3600000 && (n === null || t < n)) n = t; });
        const et = new Date(new Date(n || Date.now()).toLocaleString('en-US', { timeZone: 'America/New_York' }));
        return [on ? on.dataset.day : null, et.getFullYear() + '-' + ('0' + (et.getMonth() + 1)).slice(-2)] })()""")
    c.close()
    if got != want:
        return ["the fights tab opens on %s, not the next card's month %s" % (got, want)]
    seen.append("fights tab %s" % got)
    return []


def tracker(b, seen, board="SCHED"):
    """A DraftKings slip opened in the wallet draws its games: built here from
    the newest finished game with a saved result and a passing-TD price, so
    the check uses real ids and a real box score (Sep 29, 2026)."""
    import glob
    prices = json.load(open(os.path.join(SITE, "prices.json")))
    pick = None
    for f in sorted(glob.glob(os.path.join(SITE, "final", "4*.json")), key=os.path.getmtime, reverse=True):
        gid = os.path.basename(f)[:-5]
        ml = (prices.get(board) or {}).get(gid)
        ptd = ((prices.get("PROPS") or {}).get(gid) or {}).get("ptd") or []
        if not ml:
            continue
        # the winning side, so the slip lives: a lost leg drops it (Sep 29, 2026)
        try:
            d = json.load(open(f))
            won = [x["homeAway"] for x in d["header"]["competitions"][0]["competitors"] if x.get("winner")]
        except Exception:
            won = []
        s = 1 if won == ["home"] else 0 if won == ["away"] else None
        if s is not None and ml[2 * s + 1] and len(ptd) > s and ptd[s] and ptd[s][0] and ptd[s][0][1]:
            pick = (gid, ml[2 * s + 1], ptd[s][0][1]); break
    if not pick:
        seen.append("no finished %s game to test the tracker on" % board)
        return []
    bet = {"balance": 1, "at": 9e12, "bets": [{"id": "look", "odds": "+100", "wager": 1, "topay": 2, "legs": [
        {"sel": pick[1], "pick": "", "market": "Moneyline", "label": "ML", "odds": "+100", "status": "open"},
        {"sel": pick[2], "pick": "1+", "market": "Passing Touchdowns", "label": "1+ PTD", "odds": "-200", "status": "open"}]}]}
    def serve2(route):
        if "/bets" in route.request.url and route.request.method == "GET":
            return route.fulfill(body=json.dumps(bet), content_type="application/json")
        return serve(route)
    c = b.new_context(viewport={"width": 430, "height": 932})
    pg = c.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e).splitlines()[0][:160]))
    pg.route("**/*", serve2)
    pg.goto(HOST + "/")
    pg.wait_for_timeout(4000)
    pg.evaluate("document.getElementById('cashsheet').hidden = false; window.bankDraw && bankDraw()")
    pg.wait_for_timeout(1200)
    pg.evaluate("""(() => { for (const d of ['0', '-1', '1']) { const b = document.querySelector('#cashdays [data-d="' + d + '"]');
        if (b) cashDay(b); if (document.querySelector('#cashlegs .slview')) break; } })()""")
    pg.wait_for_timeout(300)
    pg.evaluate("document.querySelectorAll('#cashlegs .slview').forEach(b => slipOpen(b))")
    pg.wait_for_timeout(3500)
    got = pg.evaluate("""(() => { const t = document.querySelector('#cashlegs .slipcard--open .sltrk');
        if (!t) return null; return { games: t.querySelectorAll('.trkg').length, rows: t.querySelectorAll('.trkr').length,
        fin: /FINAL/.test(t.innerText), h: t.getBoundingClientRect().height } })()""")
    if os.environ.get("LOOKSHOT"):
        el = pg.query_selector("#cashlegs .slipcard--open")
        if el: el.screenshot(path=os.path.join(os.environ["LOOKSHOT"], "tracker_%s.png" % board))
    c.close()
    wrong = ["the wallet tracker threw: " + e for e in errs[:2]]
    if not got or not got["games"] or got["rows"] < 2 or not got["h"]:
        wrong.append("the wallet tracker did not draw game %s (%s)" % (pick[0], got))
    elif not got["fin"]:
        wrong.append("the wallet tracker did not read game %s as final" % pick[0])
    else:
        seen.append("tracker %s" % pick[0])
    return wrong


def fight_tracker(b, seen):
    """The same for a fight: the newest settled bout with a method and the
    winner's method price, drawn from the night's file, must read FINAL and
    keep its slip (a won leg), with no error (Sep 29, 2026)."""
    import glob, re
    prices = json.load(open(os.path.join(SITE, "prices.json")))
    page = open(os.path.join(SITE, "index.html")).read()
    pick = None
    for f in sorted(glob.glob(os.path.join(SITE, "final", "mma-6*.json")), key=os.path.getmtime, reverse=True):
        for e in json.load(open(f)).get("events") or []:
            for c in e.get("competitions") or []:
                how = str((c.get("how") or {}).get("type") or "").lower()
                key = "sub" if "sub" in how else "dec" if "dec" in how else "ko" if ("ko" in how or "knock" in how) else ""
                fp = ((prices.get("FPROPS") or {}).get(str(c["id"])) or {}).get(key) or []
                w = [m["id"] for m in c.get("competitors") or [] if m.get("winner")]
                row = re.search(r'\["[^"]*","%s","[^"]*","[^"]*","(\d*)","[^"]*","(\d*)"' % c["id"], page)
                if key and len(fp) == 2 and w and row and w[0] in row.groups():
                    s = row.groups().index(w[0])
                    if fp[s] and fp[s][1]:
                        pick = (str(c["id"]), fp[s][1]); break
            if pick: break
        if pick: break
    if not pick:
        seen.append("no settled bout to test the fight tracker on")
        return []
    bet = {"balance": 1, "at": 9e12, "bets": [{"id": "lookf", "odds": "+100", "wager": 1, "topay": 2, "legs": [
        {"sel": pick[1], "pick": "", "market": "Method of Victory", "label": "", "odds": "+300", "status": "open"}]}]}
    def serve2(route):
        if "/bets" in route.request.url and route.request.method == "GET":
            return route.fulfill(body=json.dumps(bet), content_type="application/json")
        return serve(route)
    c = b.new_context(viewport={"width": 430, "height": 932})
    pg = c.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e).splitlines()[0][:160]))
    pg.route("**/*", serve2)
    pg.goto(HOST + "/")
    pg.wait_for_timeout(4000)
    pg.evaluate("document.getElementById('cashsheet').hidden = false; window.bankDraw && bankDraw()")
    pg.wait_for_timeout(1200)
    pg.evaluate("""(() => { for (const d of ['0', '-1', '1']) { const b = document.querySelector('#cashdays [data-d="' + d + '"]');
        if (b) cashDay(b); if (document.querySelector('#cashlegs .slview')) break; } })()""")
    pg.wait_for_timeout(300)
    pg.evaluate("document.querySelectorAll('#cashlegs .slview').forEach(b => slipOpen(b))")
    pg.wait_for_timeout(3500)
    got = pg.evaluate("""(() => { const t = document.querySelector('#cashlegs .slipcard--open .sltrk');
        if (!t) return null; return { rows: t.querySelectorAll('.mw').length, fin: /FINAL/.test(t.innerText),
        won: !!t.querySelector('.trkn--won') } })()""")
    c.close()
    wrong = ["the fight tracker threw: " + e for e in errs[:2]]
    if not got or not got["rows"]:
        wrong.append("the fight tracker did not draw bout %s (%s)" % (pick[0], got))
    elif not got["fin"] or not got["won"]:
        wrong.append("the fight tracker did not settle bout %s as won (%s)" % (pick[0], got))
    else:
        seen.append("fight tracker %s" % pick[0])
    return wrong


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("look: playwright is not installed here; not rendered")
        return []
    wrong, seen = [], []
    with sync_playwright() as p:
        b = launch(p)
        if not b:
            print("look: no Chrome to render with; not rendered")
            return []
        for W in (430, 390):
            c = b.new_context(viewport={"width": W, "height": 932}, device_scale_factor=1)
            pg = c.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e).splitlines()[0][:160]))
            pg.route("**/*", serve)
            pg.goto(HOST + "/")
            pg.wait_for_timeout(4000)
            wide = pg.evaluate("document.scrollingElement.scrollWidth - innerWidth")
            if wide > 1:
                wrong.append("the page scrolls sideways by %dpx at %d wide" % (wide, W))
            if W == 430:
                pg.evaluate("document.fonts.ready")
                for face in ("Barlow", "Barlow Condensed"):
                    if not pg.evaluate("f => [...document.fonts].some(x => x.family.replace(/[\"']/g, '') == f && x.status == 'loaded')", face):
                        wrong.append("the %s font did not load" % face)
                broken = pg.evaluate("""[...document.images].filter(i => {
                    const r = i.getBoundingClientRect();
                    return r.width && r.bottom > 0 && r.top < innerHeight && i.complete && !i.naturalWidth;
                  }).map(i => i.getAttribute('src'))""")
                if broken:
                    wrong.append("%d pictures on screen are broken: %s" % (len(broken), ", ".join(broken[:5])))
                # the Form tab, opened once on All and once on HOT
                for view in ("all",):
                    pv = c.new_page()
                    pv.route("**/*", serve)
                    pv.add_init_script("try { localStorage.setItem('arena.fview', '%s') } catch (e) {}" % view)
                    pv.goto(HOST + "/")
                    pv.wait_for_timeout(3000)
                    pv.evaluate("""(() => { const b = [...document.querySelectorAll('#sportbar button')]
                        .find(b => (b.getAttribute('aria-label') || '') == 'Form'); if (b) b.click(); })()""")
                    pv.wait_for_timeout(3000)
                    if view == "all":
                        n = pv.evaluate("""new Set([...document.querySelectorAll('.qcard:not(.qcard--clone)')]
                            .filter(c => c.getBoundingClientRect().height)
                            /* by the face's ESPN id: two starters share a surname
                               (Jayden and Jalon Daniels, Sep 29, 2026) */
                            .map(c => ((c.querySelector('img[data-ring]') || {}).dataset || {}).ring + '|' +
                                      (c.querySelector('.qname h3') || {}).textContent)).size""")
                        seen.append("All %d" % n)
                        if n != 32:
                            wrong.append("the All tab shows %d passers, not 32" % n)
                    pv.close()
                # the row is drawn when search opens and its file has come in
                pg.evaluate("window.openSearch && window.openSearch()")
                pg.wait_for_timeout(2500)
                n = pg.evaluate("document.querySelectorAll('#qsearch .qst').length")
                seen.append("search row %d" % n)
                if n != 32:
                    wrong.append("the search row holds %d starters, not 32" % n)
            if W == 430:
                wrong += gestures(b, seen)
                wrong += hot(b, seen)
                wrong += fight_tab(b, seen)
                wrong += tracker(b, seen)
                wrong += tracker(b, seen, "CFB")
                wrong += fight_tracker(b, seen)
            for e in errs[:3]:
                wrong.append("the page threw at %d wide: %s" % (W, e))
            c.close()
        b.close()
    for w in wrong:
        print("LOOK: " + w)
    print("look: %s" % ("the page passed (%s)" % ", ".join(seen) if not wrong else "%d faults" % len(wrong)))
    return wrong


if __name__ == "__main__":
    sys.exit(1 if main() else 0)
