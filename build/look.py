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
                for view in ("all", "hot"):
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
                            .map(c => (c.querySelector('.qname h3') || {}).textContent)).size""")
                        seen.append("All %d" % n)
                        if n != 32:
                            wrong.append("the All tab shows %d passers, not 32" % n)
                    else:
                        h = pv.evaluate("""(() => { const c = [...document.querySelectorAll('.qcards--hot .qcard')]
                            .find(c => c.getBoundingClientRect().height); return c ? c.getBoundingClientRect().height : 0 })()""")
                        want = 55 * W / 430
                        seen.append("HOT %.1fpx" % h)
                        if abs(h - want) > 3:
                            wrong.append("HOT cards are %.0fpx tall, not %.0f" % (h, want))
                    pv.close()
                # the row is drawn when search opens and its file has come in
                pg.evaluate("window.openSearch && window.openSearch()")
                pg.wait_for_timeout(2500)
                n = pg.evaluate("document.querySelectorAll('#qsearch .qst').length")
                seen.append("search row %d" % n)
                if n != 32:
                    wrong.append("the search row holds %d starters, not 32" % n)
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
