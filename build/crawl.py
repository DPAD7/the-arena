"""The board read the way his phone reads it, against the rules every card and
slip must keep -- so a fault is caught before he finds it (Jose, Oct 17, 2026:
"you have to catch the things I'm not catching").

It opens the live site in a headless phone, waits for the board and the live
line, opens the wallet, and checks:

  cards   every live card's score and clock match DraftKings' live state; no
          blank stat on a live card; every face and logo on screen loaded
  QBs     every card's passer is the one DraftKings prices, where it prices one
  slips   every open slip is drawn once; every leg has a picture or a mark;
          no fight leg falls to the plain row; no two slips are the same bet

A fault is printed, and with --alert sent to his phone through /push {fault}.

    python3 build/crawl.py            check and print
    python3 build/crawl.py --alert    and tell the phone
"""
import json
import os
import sys
import time

from curl_cffi import requests as rq

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = "https://the-arenasports.pages.dev/"
BETS = SITE + "bets?k=arena-001bff8ddf784985"
ALERT = "--alert" in sys.argv

PAGE_CHECKS = r"""() => {
  const out = [];
  const say = (k, m) => out.push([k, m]);
  const DK = window.DKLIVE || {};
  // every live card against DraftKings' word
  document.querySelectorAll('.board:not([hidden]) .gcard[data-espn]').forEach(c => {
    const id = c.dataset.espn, dk = DK[id];
    const live = c.classList.contains('live') || !!c.querySelector('.glivebar');
    if (dk && !dk.final && Date.now() - dk.at < 60000) {
      const sc = [...c.querySelectorAll('.gscore, .trkbox, .gsc')].map(e => e.textContent.trim());
      const clk = (c.dataset.clk || '');
      const want = (dk.clock || '').split(' - ')[0];
      if (want && clk && clk.indexOf(want) < 0 && !/half|final/i.test(clk)) say('clock', id + ' card reads "' + clk + '", DraftKings ' + dk.clock);
    }
    if (live) {
      c.querySelectorAll('.ptdside, .trkbox').forEach(e => { if (e.offsetParent && !e.textContent.trim()) say('stat', id + ' has a blank stat on a live card'); });
    }
    c.querySelectorAll('img').forEach(im => {
      const r = im.getBoundingClientRect();
      if (r.width > 8 && im.complete && im.naturalWidth === 0 && getComputedStyle(im).visibility !== 'hidden') say('image', id + ' picture did not load: ' + (im.getAttribute('src') || '').slice(0, 80));
    });
  });
  // the wallet: every open slip once, every leg drawn properly
  const seen = {};
  document.querySelectorAll('#cashlegs .slipcard[data-bet]').forEach(c => {
    const id = c.dataset.bet;
    if (seen[id]) say('slip', id + ' is drawn twice');
    seen[id] = 1;
    c.querySelectorAll('.slav').forEach((a, i) => {
      if (!a.querySelector('img') && !a.textContent.trim()) say('slip', id + ' leg ' + (i + 1) + ' has no picture and no mark');
    });
    if (c.querySelector('.trkloose--fight')) say('slip', id + ' has a fight leg on the plain row');
  });
  return out;
}"""


def slip_rules():
    """What the record says, independent of the page: no bet twice."""
    wrong = []
    try:
        sent = rq.get(BETS, impersonate="chrome", timeout=30).json().get("sent") or []
    except Exception as ex:
        return [("slips", "the wallet could not be read: %s" % ex)]
    open_ = [b for b in sent if str(b.get("status") or "").lower() not in ("won", "lost")]
    sig = {}
    for b in open_:
        k = tuple(sorted(str(l.get("label") or "").split(" ")[0].upper() for l in b.get("legs") or [])) + (str(b.get("odds")),)
        if k in sig:
            wrong.append(("slip", "%s and %s are the same bet" % (sig[k], b["id"])))
        sig[k] = b["id"]
    return wrong


def qb_rules():
    """Every card's passer is the one DraftKings prices, where it prices one."""
    import re
    sys.path.insert(0, os.path.join(D, "build"))
    import pagefile
    wrong = []
    s = pagefile.read()
    dkq = json.load(open(os.path.join(D, "data", "dk_qbs.json"))) if os.path.exists(os.path.join(D, "data", "dk_qbs.json")) else {}
    named = json.load(open(os.path.join(D, "data", "qb_named.json"))) if os.path.exists(os.path.join(D, "data", "qb_named.json")) else {}
    wire = json.load(open(os.path.join(D, "site", "wire.json"))) if os.path.exists(os.path.join(D, "site", "wire.json")) else {}
    now = time.time()
    for var in ("SCHED", "CFB"):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
        for g in json.loads(m.group(1)) if m else []:
            try:
                import datetime as dt
                k = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00")).timestamp()
            except ValueError:
                continue
            if not (now - 4 * 3600 < k < now + 36 * 3600):
                continue
            for side, i, club in ((0, 5, g[3]), (1, 7, g[4])):
                book = [x for x in ((dkq.get(str(g[1])) or [[], []])[side]) if x and x[0]]
                held = named.get("%s|%s" % (g[1], club))
                # the injury report outranks a naming, as on the board
                if held and (wire.get(str(held["id"])) or {}).get("status", "").lower() in ("out", "injured reserve", "suspended", "doubtful"):
                    held = None
                if held and str(held["id"]) != str(g[i + 1]):
                    wrong.append(("qb", "%s card has %s; %s is named to start" % (club, g[i], held["name"])))
                elif len(book) == 1 and str(book[0][0]) != str(g[i + 1]) and not held:
                    wrong.append(("qb", "%s card has %s; DraftKings prices %s" % (club, g[i], book[0][1])))
    return wrong


def page_rules():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(channel="chrome")    # the runner's own Chrome, as look.py uses
        c = b.new_context(viewport={"width": 430, "height": 932}, is_mobile=True, has_touch=True, service_workers="block")
        pg = c.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(SITE + "?crawl=%d" % int(time.time()), wait_until="load")
        pg.wait_for_timeout(20000)
        pg.evaluate("window._dkPull && window._dkPull()")
        pg.wait_for_timeout(3000)
        pg.evaluate("document.getElementById('cashsheet').hidden = false; window.bankDraw && bankDraw();"
                    "document.querySelectorAll('#cashlegs .slipcard .slview').forEach(v => { var c = v.closest('.slipcard'); if (c && !c.classList.contains('slipcard--open')) slipOpen(v); })")
        pg.wait_for_timeout(4000)
        wrong = [tuple(x) for x in pg.evaluate(PAGE_CHECKS)]
        wrong += [("script", "the page threw: " + e[:160]) for e in errs[:3]]
        b.close()
    return wrong


def main():
    wrong = slip_rules() + qb_rules()
    try:
        wrong += page_rules()
    except Exception as ex:
        wrong.append(("crawl", "the page could not be opened: %s" % ex))
    seen = set()
    wrong = [w for w in wrong if not (w in seen or seen.add(w))]
    for k, m in wrong:
        print("  %-6s %s" % (k, m))
    print("crawl: %d fault(s)" % len(wrong))
    if ALERT and wrong:
        try:
            rq.post(SITE + "push", json={"fault": {"key": "crawl-" + "-".join(sorted({k for k, _ in wrong})),
                                                   "title": "The board caught %d fault%s" % (len(wrong), "" if len(wrong) == 1 else "s"),
                                                   "body": "; ".join(m for _, m in wrong[:3])[:200]}},
                    headers={"x-ask-secret": os.environ.get("ASK_SECRET", "")}, impersonate="chrome", timeout=30)
        except Exception as ex:
            print("alert failed:", ex)
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
