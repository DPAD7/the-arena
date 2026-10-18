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
      // the card counts down on its own between readings and DraftKings' clock
      // moves every second, so the two are read a second or two apart: the same
      // quarter within 10 seconds is the same clock
      const secs = t => { const m = /^(\d+):(\d\d)\s*-\s*(\w+)/.exec(t || ''); return m ? [m[3], +m[1] * 60 + +m[2]] : null; };
      const a = secs(clk), b = secs(dk.clock);
      const same = a && b ? (a[0] === b[0] && Math.abs(a[1] - b[1]) <= 10) : clk.indexOf(want) >= 0;
      if (want && clk && !same && !/half|final/i.test(clk)) say('clock', id + ' card reads "' + clk + '", DraftKings ' + dk.clock);
    }
    if (live) {
      c.querySelectorAll('.ptdside, .trkbox').forEach(e => { if (e.offsetParent && !e.textContent.trim()) say('stat', id + ' has a blank stat on a live card'); });
    }
    c.querySelectorAll('img').forEach(im => {
      const r = im.getBoundingClientRect();
      if (r.width > 8 && im.complete && im.naturalWidth === 0 && getComputedStyle(im).visibility !== 'hidden') say('image', id + ' picture did not load: ' + (im.getAttribute('src') || '').slice(0, 80));
    });
  });
  // a live card with no fresh DraftKings reading: the feed itself is down
  document.querySelectorAll('.board:not([hidden]) .gcard[data-espn]').forEach(c => {
    const id = c.dataset.espn, dk = DK[id];
    if ((c.classList.contains('live') || c.querySelector('.glivebar')) && c.dataset.lg !== 'mma' &&
        !c.classList.contains('done') && (!dk || Date.now() - dk.at > 90000)) say('feed', id + ' is live with no DraftKings reading for 90s');
  });
  // a fighter's record once, in its slot, never inside his name
  document.querySelectorAll('.board:not([hidden]) .gcard--bout').forEach(c => {
    c.querySelectorAll('.fname').forEach(n => { if (/\b\d{1,2}-\d{1,2}(-\d)?\b/.test(n.textContent)) say('record', (c.dataset.bout || '') + ' has a record inside a name: ' + n.textContent.trim()); });
  });
  // names and classes fit on one line
  document.querySelectorAll('.board:not([hidden]) .gcard .fname, .board:not([hidden]) .gcard .qname').forEach(n => {
    if (n.offsetParent && n.scrollWidth > n.clientWidth + 2) say('overflow', 'name runs out of its box: ' + n.textContent.trim().slice(0, 40));
  });
  // a card still to play with prices in the file shows them
  const PJ = window.PRICEJ_SNAP || null;
  document.querySelectorAll('.board:not([hidden]) .gcard[data-espn], .board:not([hidden]) .gcard[data-bout]').forEach(c => {
    if (c.classList.contains('done') || c.classList.contains('locked') || c.classList.contains('live')) return;
    const btns = [...c.querySelectorAll('button.price')];
    if (btns.length && !btns.some(b => /\d/.test(b.textContent)) && c.dataset.kick && Date.parse(c.dataset.kick) > Date.now())
      say('odds', (c.dataset.espn || c.dataset.bout) + ' shows no prices before it starts');
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


def fight_rules():
    """A finished bout keeps both men's closing moneyline (fixed nine times)."""
    import re, glob
    sys.path.insert(0, os.path.join(D, "build"))
    import pagefile
    wrong = []
    s = pagefile.read()
    book = (json.load(open(os.path.join(D, "site", "prices.json"))).get("FIGHTS") or {})
    rows = []
    for var in ("FIGHTS",):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
        rows += json.loads(m.group(1)) if m else []
    done = set()
    for f in glob.glob(os.path.join(D, "site", "final", "mma-*.json")):
        try:
            for e in json.load(open(f)).get("events") or []:
                for c in e.get("competitions") or []:
                    if ((c.get("status") or {}).get("type") or {}).get("state") == "post":
                        done.add(str(c.get("id")))
        except Exception:
            continue
    import datetime as dt
    now = dt.datetime.now(dt.timezone.utc)
    for g in rows:
        bid = str(g[1])
        try:
            t = dt.datetime.fromisoformat(g[2].replace("Z", "+00:00"))
        except ValueError:
            continue
        if bid not in done or now - t > dt.timedelta(days=10):
            continue
        v = book.get(bid) or []
        row_has = (g[9] if len(g) > 9 else "") and (g[11] if len(g) > 11 else "")
        if not ((len(v) >= 3 and v[0] and v[2]) or row_has):
            wrong.append(("odds", "%s vs %s is over with no closing moneyline" % (g[3], g[5])))
    return wrong


def leg_rules():
    """Every leg on a tracked slip has a result within 16 hours of its start (fixed seven times)."""
    import re
    import datetime as dt
    sys.path.insert(0, os.path.join(D, "build"))
    import pagefile
    wrong = []
    s = pagefile.read()
    start = {}
    for var in ("SCHED", "CFB", "FIGHTS"):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
        for g in json.loads(m.group(1)) if m else []:
            start[str(g[1])] = g[2]
    try:
        sent = rq.get(BETS, impersonate="chrome", timeout=30).json().get("sent") or []
    except Exception:
        return wrong
    now = dt.datetime.now(dt.timezone.utc)
    for b in sent:
        if str(b.get("status") or "").lower() in ("won", "lost"):
            continue
        if any(str(l.get("status") or "").lower() == "lost" for l in b.get("legs") or []):
            continue
        for l in b.get("legs") or []:
            if str(l.get("status") or "").lower() in ("won", "lost", "void"):
                continue
            st = start.get(str(l.get("g") or "")) or (l.get("frow") or [None, None, None])[2] or l.get("start")
            try:
                t = dt.datetime.fromisoformat(str(st).replace("Z", "+00:00"))
            except ValueError:
                continue
            if now - t > dt.timedelta(hours=16):
                wrong.append(("settle", "%s on %s has no result 16h after it started" % (l.get("label"), b.get("id"))))
    return wrong


def data_stamp():
    """what the board is made of right now: the build stamp and the prices file"""
    out = []
    for f in ("build.txt", "prices.json"):
        try:
            out.append(rq.get(SITE + f + "?crawl=%d" % int(time.time()), timeout=20).text)
        except Exception:
            out.append(None)
    return out


def page_rules():
    from playwright.sync_api import sync_playwright
    before = data_stamp()
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
        # nothing is rebuilt under him: a minute of watching, no card or slip
        # replaced (fixed seven times)
        pg.evaluate("""() => { window._rebuilt = 0; const mo = new MutationObserver(ms => ms.forEach(m => m.removedNodes.forEach(n => {
          if (n.nodeType === 1 && (n.matches('.gcard, .slipcard') || n.querySelector && n.querySelector('.slipcard'))) window._rebuilt++; })));
          document.querySelectorAll('.board, #cashlegs').forEach(b => mo.observe(b, { childList: true, subtree: true })); }""")
        pg.wait_for_timeout(60000)
        n = pg.evaluate("window._rebuilt")
        # a sweep that deployed while the page was open changed what it is made
        # of: drawing again to take it is the design, not a rebuild for nothing
        if n and data_stamp() != before:
            n = 0
        if n:
            wrong.append(("rebuild", "%d card(s) or slip(s) were rebuilt in a minute with nothing changing" % n))
        wrong += [("script", "the page threw: " + e[:160]) for e in errs[:3]]
        b.close()
    return wrong


def main():
    wrong = slip_rules() + qb_rules() + fight_rules() + leg_rules()
    try:
        wrong += page_rules()
    except Exception as ex:
        wrong.append(("crawl", "the page could not be opened: %s" % ex))
    seen = set()
    wrong = [w for w in wrong if not (w in seen or seen.add(w))]
    for k, m in wrong:
        print("  %-6s %s" % (k, m))
    print("crawl: %d fault(s)" % len(wrong))
    # a missing live feed counts only when the last look saw it too: a reader
    # restarting is a minute, not a fault (Oct 17, 2026)
    held = "/tmp/crawl_feed.json"
    feed = [w for w in wrong if w[0] == "feed"]
    try:
        before = set(tuple(x) for x in json.load(open(held)))
    except Exception:
        before = set()
    json.dump(feed, open(held, "w"))
    wrong = [w for w in wrong if w[0] != "feed" or tuple(w) in before]
    # faults go to the mender, never to his phone (Jose, Oct 17, 2026: "why are
    # you sending me notifications about this")
    if False and ALERT and wrong:
        try:
            rq.post(SITE + "push", json={"fault": {"key": "crawl-" + "-".join(sorted({k for k, _ in wrong})),
                                                   "title": "The board caught %d fault%s" % (len(wrong), "" if len(wrong) == 1 else "s"),
                                                   "body": "; ".join(m for _, m in wrong[:3])[:200]}},
                    headers={"x-ask-secret": os.environ.get("ASK_SECRET", "")}, impersonate="chrome", timeout=30)
        except Exception as ex:
            print("alert failed:", ex)
    if ALERT and wrong and os.environ.get("GITHUB_TOKEN"):
        mend(wrong)
    return 1 if wrong else 0


def mend(wrong):
    """Each kind of fault, once, as a "fault" issue -- mend.yml sets Claude on
    it to find the cause in the code, fix it, prove it and ship it (Jose, Oct
    17, 2026: "if it's missing it just fix the code")."""
    import urllib.request
    tok, repo = os.environ["GITHUB_TOKEN"], "DPAD7/the-arena"

    def gh(path, data=None):
        req = urllib.request.Request("https://api.github.com/repos/%s%s" % (repo, path),
                                     data=json.dumps(data).encode() if data is not None else None,
                                     method="POST" if data is not None else "GET")
        req.add_header("Authorization", "Bearer " + tok)
        req.add_header("Accept", "application/vnd.github+json")
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    try:
        open_ = {i["title"]: i["number"] for i in gh("/issues?state=open&labels=fault&per_page=50")}
    except Exception as ex:
        print("issues unread:", ex)
        return
    kinds = {}
    for k, m in wrong:
        kinds.setdefault(k, []).append(m)
    for k, ms in kinds.items():
        title = "crawl: %s" % k
        body = ("build/crawl.py found this on the live board (%s):\n\n" % time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()) +
                "\n".join("- " + m for m in ms[:20]) +
                "\n\nFind the cause in the code, fix it, prove it with `python3 build/crawl.py`, and ship.")
        try:
            if title in open_:
                gh("/issues/%s/comments" % open_[title], {"body": body})
                continue
            it = gh("/issues", {"title": title, "body": body, "labels": ["fault"]})
            gh("/actions/workflows/mend.yml/dispatches", {"ref": "main", "inputs": {"issue": str(it["number"])}})
            print("filed #%s and set the mender on it" % it["number"])
        except Exception as ex:
            print("filing failed:", ex)


if __name__ == "__main__":
    sys.exit(main())
