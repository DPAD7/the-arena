"""The UFC fight-winner read, every sweep: the next UFC card on the board,
   every bout scored by a stats model, the 70%+ ones ranked onto the card.

   The model replaced the 19 boxes on Oct 12, 2026 (the audit found the box
   lead was the betting favorite under another name). It is a gradient-boosted
   tree model on each man's numbers as of the morning of the bout -- age, reach,
   height, UFC rating (Elo), strikes landed and absorbed, takedowns against the
   other man's defense, control, knockdowns, round 1 and late-round margins,
   UFC minutes, layoff, form, pro record, finish rate against the other man's
   durability, KO power against his chin -- and NO odds. Walk-forward, refit
   each year on the years before only (research/ufc_reads/):

       model 75%+    2019-23  77.5% (231, 1.09 a card)   2024-26  84.2% (146, 1.23 a card)
       model 70-74%  2019-23  69.5% (210)                 2024-26  73.5% (151)
       model 70%+    2019-23  73.7% (441, 2.09 a card)   2024-26  78.8% (297, 2.50 a card)
       (2024-26 counts the Oct 10, 2026 card, 1-1 at 75%+; without it 84.7% / 79.0%)
   Women's bouts are scored by the same model, fit on men: 70%+ 78.4% (111) and
   80.4% (46) blind.

   Only a 70%+ bout gets a rank (the ticket on the card); "won" is that tier's
   2024-26 blind rate (84 at 75%+, 74 at 70-74%).

   History lives in data/ufc_hist/ (UFC Stats from 2010 plus every man's UFC
   history back to 1994 for the rating; pro records are read from
   data/ufc_records/, the gidstats pull, and topped up with UFC Stats results
   after that pull). Each run reads UFC Stats' completed-events list, fetches
   only the events not on the seen list, appends them, and scores the next
   card. The model is kept as JSON in data/models/ufc_ml.json and run with
   numpy. When scikit-learn is installed (pin scikit-learn==1.9.0) and UFC Stats
   has bouts newer than the model, it is refit on every bout before the card
   and the JSON rewritten; without it the committed JSON is used.

   Fight-week facts (Oct 12, 2026): the card's Wikipedia page is read every run
   from 7 days out until the first bell (cached in data/ufc_hist/wiki_<card>.json)
   for replacements, the notice they took the fight on, short-notice UFC debuts
   and missed weight. A men's 70-74% pick whose OPPONENT is a replacement on 14
   days' notice or less, a short-notice debut, or missed weight -- while the pick
   himself is none of these -- is tier 2: won 89 (blind 2022-26 90.0%, 20 bouts;
   2015-21 86.7%, 15). The facts ride every pick as own_facts / opp_facts and a
   why line, whatever the %; they never move p.

   The call (Oct 12, 2026): every men's pick also carries "call", the likeliest
   side on the bout sheet -- the moneyline favorite or a side of Fight to Go the
   Distance (every other sheet market is a part of one of those) -- from the
   winner model and a distance model (data/models/ufc_dist.json, --fit-dist).
   Best call per bout, blind: 2022-23 67.0% (75%+ calls 80.1%, 1.60 a card),
   2024-26 66.6% (75%+ 84.5%, 1.62 a card). "won" is the blind 2022-26 rate of
   that side in its 5-point band; "price" is DraftKings' price when posted,
   information only.

   A card already under way keeps its picks. When it starts, its ranked picks
   are appended to data/boxpicks_log.csv; results are filled from ESPN after.

   Writes site/boxpicks.json:
     {"at", "card", "event", "name", "model",
      "picks": {espn bout id: {"rank", "pick", "vs", "box": [p, 100-p], "p",
                               "won", "why": [...], "id", "own_facts", "opp_facts",
                               "opp_flag", "flag": "tier2" (only on a tier-2 pick),
                               "call": {"market", "sel", "side", "p", "won", "won_n", "p_ml",
                                        "p_dist", "why": [...], "price" (when DK has it)}}},
      "all":   {espn bout id: {"pick", "vs", "p"}}}

   Usage:  python3 build/ufc_reads.py            crawl, score, write
           python3 build/ufc_reads.py --dry      score and print, write nothing
           python3 build/ufc_reads.py --no-crawl skip UFC Stats' finished events
           python3 build/ufc_reads.py --fit [--before YYYY-MM-DD] [--out PATH]
           python3 build/ufc_reads.py --fit-dist [--before YYYY-MM-DD] [--out PATH]   the distance model
           python3 build/ufc_reads.py --replay YYYY-MM-DD   score a past card point-in-time
           pip: pandas numpy pyarrow curl_cffi (scikit-learn only for --fit)
"""
import csv
import datetime as dt
import hashlib
import html as H
import json
import os
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(D, "data", "ufc_hist")
PRO = os.path.join(D, "data", "ufc_records")
MODEL = os.path.join(D, "data", "models", "ufc_ml.json")
OUT = os.path.join(D, "site", "boxpicks.json")
LOG = os.path.join(D, "data", "boxpicks_log.csv")
sys.path.insert(0, os.path.join(D, "build"))

NOW = dt.datetime.now(dt.timezone.utc)
TIERS = ((0.75, 82),)                   # men's 75%+ only: 82.2% blind 2022-26, 1.24 a card; the 70% tier is
                                         # dropped (Jose, Oct 12, 2026: "we need something that gets us 75-85+")
TIER2 = (0.70, 89)                      # 70-74% with the opponent's fight-week flag: blind 2022-26 90.0% (20)
WIKI_FROM = dt.timedelta(days=7)        # the Wikipedia page is reread every run from 7 days out to the bell
WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_UA = "TheArenaBoard/1.0 (https://the-arenasports.pages.dev; one page a run, UFC fight-week facts)"
LIVE_FOR = dt.timedelta(hours=4)        # a card is current until 4 h after its last bout's bell
GBM = dict(max_depth=3, learning_rate=0.05, max_iter=300, l2_regularization=1.0, random_state=0)
SKLEARN = "1.9.0"

try:
    from curl_cffi import requests as _rq
except Exception:
    _rq = None


# ---------------------------------------------------------------- fetching
_local = threading.local()


def _sess():
    s = getattr(_local, "s", None)
    if s is None:
        s = _rq.Session(impersonate="chrome")
        _local.s = s
    return s


def _solve(s, page, url):
    """UFC Stats' browser check: a sha256 proof of work, posted back."""
    nonce = re.search(r'var nonce="([0-9a-f]+)"', page).group(1)
    k = int(re.search(r"new Array\((\d+)\+1\)", page).group(1))
    t, n = "0" * k, 0
    while not hashlib.sha256(f"{nonce}:{n}".encode()).hexdigest().startswith(t):
        n += 1
    host = re.match(r"(https?://[^/]+)", url).group(1)
    s.post(host + "/__c", data={"nonce": nonce, "n": str(n)}, timeout=30, headers={"Referer": url})


def get(url, tries=6):
    last = None
    for i in range(tries):
        try:
            s = _sess()
            r = s.get(url, timeout=30)
            if "Checking your browser" in r.text and "/__c" in r.text:
                _solve(s, r.text, url)
                continue
            if r.status_code == 200:
                return r.text
            last = r.status_code
        except Exception as e:
            last = e
        time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def get_json(url):
    r = _rq.get(url, impersonate="chrome", timeout=20)
    return r.json()


# ---------------------------------------------------------------- UFC Stats pages
def _txt(s):
    return re.sub(r"\s+", " ", H.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _ps(td):
    return [_txt(p) for p in re.findall(r'<p class="b-fight-details__table-text">(.*?)</p>', td, re.S)]


def _tds(row):
    return re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)


def _of(s):
    m = re.match(r"(\d+) of (\d+)", s or "")
    return (m.group(1), m.group(2)) if m else ("", "")


def _clean(v):
    return "" if v in ("--", "---") else v


def _mdy(s):
    for f in ("%b %d, %Y", "%b. %d, %Y", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(s.strip(), f).date().isoformat()
        except Exception:
            pass
    return ""


EV_RE = (r'href="(http://ufcstats.com/event-details/[0-9a-f]+)"[^>]*>\s*(.*?)\s*</a>\s*'
         r'<span class="b-statistics__date">\s*(.*?)\s*</span>')


def event_list(kind):
    """[(url, name, iso date)] from the completed or upcoming list."""
    page = get("http://ufcstats.com/statistics/events/%s?page=all" % kind)
    out = []
    for u, n, d in re.findall(EV_RE, page, re.S):
        try:
            out.append((u, _txt(n), dt.datetime.strptime(d.strip(), "%B %d, %Y").date().isoformat()))
        except ValueError:
            pass
    return out


def event_rows(page):
    """the event page's bout rows: fight url, the two men (red first), weight
       class and method, as the event page writes them"""
    out = []
    for row in page.split("js-fight-details-click")[1:]:
        fu = re.search(r'data-link="([^"]+)"', row).group(1)
        c = _tds(row)
        men = re.findall(r'href="(http://ufcstats.com/fighter-details/[0-9a-f]+)"\s*>\s*(.*?)\s*</a>', c[1], re.S)
        out.append(dict(fight_url=fu, men=[(u, _txt(n)) for u, n in men],
                        weight_class=" ".join(_ps(c[6])), method=(_ps(c[7]) or [""])[0]))
    return out


STAT = ("kd", "sig_landed", "sig_att", "total_landed", "total_att", "td_landed", "td_att", "sub_att", "rev", "ctrl")


def parse_fight(page, fu, ev_name, ev_date, er):
    """one finished bout: the fights row (parse.py's), the two history rows and
       the per-round lines (rounds.py's, decided bouts only)"""
    persons = re.findall(r'b-fight-details__person-status[^"]*">\s*(\w*)\s*</i>.*?fighter-details/([0-9a-f]+)\W*>(.*?)</a>',
                         page, re.S)
    (rs, ru, rn), (bs, bu, bn) = persons[:2]
    win = "red" if rs == "W" else "blue" if bs == "W" else "draw" if rs == "D" else "nc" if rs == "NC" else ""
    title = _txt(re.search(r'b-fight-details__fight-title">(.*?)</i>\s*</div>', page, re.S).group(1))

    def lab(l):
        m = re.search(l + r":\s*</i>(.*?)</i>", page, re.S)
        return _txt(m.group(1)) if m else ""
    mdetail = _txt(re.search(r"Method:\s*</i>\s*<i[^>]*>(.*?)</i>", page, re.S).group(1))
    tf = lab("Time format")
    m = re.match(r"(\d+) Rnd", tf)
    r = {"event_name": ev_name, "event_date": ev_date, "fight_url": fu, "red_name": rn.strip(), "blue_name": bn.strip(),
         "red_url": "http://ufcstats.com/fighter-details/" + ru, "blue_url": "http://ufcstats.com/fighter-details/" + bu,
         "red_result": rs, "blue_result": bs, "winner": win, "method": er.get("method") or mdetail, "method_detail": mdetail,
         "round": lab("Round"), "time": lab("Time"), "time_format": tf, "scheduled_rounds": m.group(1) if m else "",
         "weight_class": er.get("weight_class", ""), "bout_title": title,
         "title_bout": str(bool(re.match(r"UFC (Interim )?.*Title", title))).lower(), "stats_available": "false"}
    i = page.find("b-fight-details__collapse-link_tot")
    if i > 0:
        tb = page[i:page.find("</table>", i)]
        rows = [x for x in re.findall(r'<tr class="b-fight-details__table-row">(.*?)</tr>', tb, re.S) if "<td" in x]
        if rows:
            c = [_ps(x) for x in _tds(rows[0])]
            if len(c) >= 10 and len(c[1]) == 2:
                r["stats_available"] = "true"
                for k, side in ((0, "red"), (1, "blue")):
                    r[f"{side}_kd"] = c[1][k]
                    r[f"{side}_sig_landed"], r[f"{side}_sig_att"] = _of(c[2][k])
                    r[f"{side}_total_landed"], r[f"{side}_total_att"] = _of(c[4][k])
                    r[f"{side}_td_landed"], r[f"{side}_td_att"] = _of(c[5][k])
                    r[f"{side}_sub_att"] = c[7][k]
                    r[f"{side}_rev"] = c[8][k]
                    r[f"{side}_ctrl"] = _clean(c[9][k])
    hist = []
    for me, ot, res in (("red", "blue", rs), ("blue", "red", bs)):
        if res not in ("W", "L", "D", "NC"):
            continue
        hist.append(dict(fighter_url=r[me + "_url"], date=ev_date, event_name=ev_name, fight_url=fu,
                         opponent_url=r[ot + "_url"], opponent_name=r[ot + "_name"], result=res,
                         method=r["method"], method_detail=mdetail, round=r["round"], time=r["time"]))
    rounds = []
    if win in ("red", "blue"):
        rounds = parse_rounds(page, r["red_url"], r["blue_url"], ev_date)
    return r, hist, rounds


def parse_rounds(t, red_url, blue_url, date):
    def cells(x):
        return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", x, re.S)]

    def of(s):
        m = re.match(r"(\d+) of (\d+)", s or "")
        return (int(m.group(1)), int(m.group(2))) if m else (np.nan, np.nan)
    i = t.find("Per round")
    if i < 0:
        return []
    j = t.find("Significant Strikes", i)
    seg = t[i:j if j > 0 else i + 40000]
    out = []
    for rn, block in enumerate(re.split(r"Round \d+", seg)[1:], start=1):
        c = cells(block)
        if len(c) < 10:
            continue
        sig = re.findall(r"\d+ of \d+", c[2])
        if len(sig) < 2:
            continue
        for k, u in enumerate((red_url, blue_url)):
            sl, _ = of(sig[k])
            osl, _ = of(sig[1 - k])
            out.append(dict(url=u, date=date, rnd=rn, sig=sl, sig_abs=osl))
    return out


def parse_fighter(page, fu):
    def lab(l):
        m = re.search(r">\s*" + re.escape(l) + r"\s*</i>(.*?)</li>", page, re.S)
        return _clean(_txt(m.group(1))) if m else ""
    name = _txt(re.search(r'b-content__title-highlight">(.*?)</span>', page, re.S).group(1))
    ht = lab("Height:")
    m = re.match(r"(\d+)' (\d+)\"", ht)
    hin = float(int(m.group(1)) * 12 + int(m.group(2))) if m else np.nan
    m = re.match(r'([\d.]+)"', lab("Reach:"))
    rin = float(m.group(1)) if m else np.nan
    dob = lab("DOB:")
    # his fight list too (parse.py's): it carries his Contender Series bouts, which no
    # UFC event page does, and the audit's history had them
    hist = []
    body = page[page.find("b-fight-details__table-body"):]
    for row in body.split("js-fight-details-click")[1:]:
        c = _tds(row)
        flag = re.search(r"b-flag__text\">(\w+)", row)
        res = {"win": "W", "loss": "L", "draw": "D", "nc": "NC"}.get(flag.group(1).lower()) if flag else None
        if not res:
            continue
        ppl = re.findall(r"fighter-details/([0-9a-f]+)", c[1])
        opp = [x for x in ppl if not fu.endswith(x)]
        ev = _ps(c[6])
        hist.append(dict(fighter_url=fu, date=_mdy(ev[1]) if len(ev) > 1 else "",
                         fight_url=re.search(r'data-link="([^"]+)"', row).group(1),
                         opponent_url="http://ufcstats.com/fighter-details/" + opp[0] if opp else "",
                         result=res, method=(_ps(c[7]) or [""])[0]))
    return dict(fighter_url=fu, name=name, dob=_mdy(dob) if dob else None, height_in=hin, reach_in=rin,
                stance=lab("STANCE:") or None, checked=NOW.date().isoformat()), hist


# ---------------------------------------------------------------- history store
FCOLS = ["event_name", "event_date", "fight_url", "red_name", "blue_name", "red_url", "blue_url", "winner", "method",
         "method_detail", "round", "time", "scheduled_rounds", "weight_class", "title_bout"] + \
        [f"{s}_{k}" for s in ("red", "blue") for k in ("kd", "sig_landed", "sig_att", "td_landed", "td_att", "sub_att", "ctrl")]
HCOLS = ["fighter_url", "date", "fight_url", "opponent_url", "result", "method", "o1", "o2"]
# o1, o2: the row's place in build.py's two date sorts, frozen at the seed. A man
# who fought twice in a night (the tournaments) has two rows on one day, and which
# comes first moves every rating after it; new rows are numbered on in crawl order.
TCOLS = ["fighter_url", "name", "dob", "height_in", "reach_in", "stance", "checked"]
RCOLS = ["url", "date", "rnd", "sig", "sig_abs"]
NUMF = ["round", "scheduled_rounds"] + [f"{s}_{k}" for s in ("red", "blue") for k in ("kd", "sig_landed", "sig_att", "td_landed", "td_att", "sub_att")]


def load_hist():
    h = {k: pd.read_parquet(os.path.join(HIST, k + ".parquet")) for k in ("fights", "history", "fighters", "rounds", "bouts")}
    h["seen"] = json.load(open(os.path.join(HIST, "seen.json")))
    p = os.path.join(HIST, "pro_map.json")
    h["pro_map"] = json.load(open(p)) if os.path.exists(p) else {}
    return h


def save_hist(h):
    for k in ("fights", "history", "fighters", "rounds", "bouts"):
        h[k].reset_index(drop=True).to_parquet(os.path.join(HIST, k + ".parquet"), index=False, compression="zstd")
    json.dump(sorted(h["seen"]), open(os.path.join(HIST, "seen.json"), "w"), indent=0)
    json.dump(h["pro_map"], open(os.path.join(HIST, "pro_map.json"), "w"), indent=1, sort_keys=True)


def _norm_fights(df):
    df = df.reindex(columns=FCOLS)
    for c in NUMF:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("red_ctrl", "blue_ctrl", "time", "method", "method_detail", "title_bout"):
        df[c] = df[c].astype(object).where(df[c].notna(), None)
    return df


def fetch_fighters(h, urls):
    urls = [u for u in dict.fromkeys(urls) if u]
    got = []

    rows = []

    def one(u):
        try:
            bio, hist = parse_fighter(get(u), u)
            got.append(bio)
            rows.extend(hist)
        except Exception as e:
            print("  fighter page failed", u, e)
    with ThreadPoolExecutor(2) as ex:
        list(ex.map(one, urls))
    if got:
        new = pd.DataFrame(got).reindex(columns=TCOLS)
        h["fighters"] = pd.concat([h["fighters"][~h["fighters"].fighter_url.isin(new.fighter_url)], new], ignore_index=True)
    have = set(zip(h["history"].fighter_url, h["history"].fight_url))
    rows = sorted([r for r in rows if r["date"] and (r["fighter_url"], r["fight_url"]) not in have], key=lambda r: r["date"])
    if rows:
        HI = pd.DataFrame(rows).reindex(columns=HCOLS)
        HI["o1"] = h["history"].o1.max() + 1 + np.arange(len(HI))
        HI["o2"] = h["history"].o2.max() + 1 + np.arange(len(HI))
        h["history"] = pd.concat([h["history"], HI], ignore_index=True)
    return len(got)


def crawl(h):
    """append every finished UFC event since the seen list, 2010 on"""
    today = NOW.date().isoformat()
    evs = [e for e in event_list("completed") if "2010-01-01" <= e[2] <= today and e[0] not in set(h["seen"])]
    if not evs:
        return []
    added = []
    for eu, en, ed in sorted(evs, key=lambda e: e[2]):
        try:
            rows = event_rows(get(eu))
        except Exception as e:
            print("  event page failed", en, e)
            continue
        pages = {}

        def one(r):
            pages[r["fight_url"]] = get(r["fight_url"])
        try:
            with ThreadPoolExecutor(2) as ex:
                list(ex.map(one, rows))
        except Exception as e:
            print("  fight pages failed", en, e)
            continue
        F, HI, RO = [], [], []
        try:
            for r in rows:
                f, hi, ro = parse_fight(pages[r["fight_url"]], r["fight_url"], en, ed, r)
                F.append(f)
                HI += hi
                RO += ro
        except Exception as e:
            print("  not finished on UFC Stats yet:", en, e)
            continue
        if not F or any(f["red_result"] not in ("W", "L", "D", "NC") for f in F):
            print("  results not all posted yet:", en)
            continue
        F = _norm_fights(pd.DataFrame(F))
        h["fights"] = pd.concat([h["fights"][~h["fights"].fight_url.isin(F.fight_url)], F], ignore_index=True)
        HI = pd.DataFrame(HI).reindex(columns=HCOLS)
        HI["o1"] = h["history"].o1.max() + 1 + np.arange(len(HI))
        HI["o2"] = h["history"].o2.max() + 1 + np.arange(len(HI))
        h["history"] = pd.concat([h["history"][~h["history"].fight_url.isin(HI.fight_url)], HI], ignore_index=True)
        if RO:
            RO = pd.DataFrame(RO).reindex(columns=RCOLS)
            h["rounds"] = pd.concat([h["rounds"][~((h["rounds"].date == ed) & h["rounds"].url.isin(RO.url))], RO],
                                    ignore_index=True)
        new = set(F.red_url) | set(F.blue_url)
        fetch_fighters(h, sorted(new - set(h["fighters"].fighter_url)))
        h["seen"].append(eu)
        added.append((eu, en, ed, list(F.fight_url)))
        print("  added %s %s: %d bouts" % (ed, en, len(F)))
    return added


# ---------------------------------------------------------------- point-in-time features (build.py's, unchanged)
def _ln(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower().replace(".", "").replace("-", " ")
    p = [w for w in s.split() if w not in ("jr", "sr", "ii", "iii")]
    return p[-1] if p else ""


def _nz(x):
    x = unicodedata.normalize("NFKD", str(x)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", x.replace(".", "").replace("-", " ").replace("'", "")).strip()


class Feats:
    """build.py's form / rates / prof / pro / Elo, over the stored tables"""

    def __init__(self, h, extra_pro=None):
        F = h["fights"].copy()
        F["date"] = pd.to_datetime(F.event_date)
        self.FT = h["fighters"].drop_duplicates("fighter_url", keep="last").set_index("fighter_url")
        Hh = h["history"].copy()
        Hh["date"] = pd.to_datetime(Hh.date)
        Hh = Hh.sort_values(["date", "o1"], kind="mergesort")
        self.last_hist = Hh.date.max()

        def mins(rnd, tm):
            t = str(tm).split(":")
            try:
                return (int(rnd) - 1) * 5 + int(t[0]) + int(t[1]) / 60
            except Exception:
                return np.nan

        def sec(s):
            try:
                a, b = str(s).split(":")
                return int(a) * 60 + int(b)
            except Exception:
                return np.nan
        lines = []
        for r in F.itertuples(index=False):
            m = mins(r.round, r.time)
            for me, ot in (("red", "blue"), ("blue", "red")):
                g = lambda c: getattr(r, c)
                lines.append(dict(url=g(me + "_url"), date=r.date, mins=m, sig=g(me + "_sig_landed"), sig_att=g(me + "_sig_att"),
                                  sig_abs=g(ot + "_sig_landed"), td=g(me + "_td_landed"), td_att=g(me + "_td_att"),
                                  tda=g(ot + "_td_landed"), tda_att=g(ot + "_td_att"), kd=g(me + "_kd"), kd_abs=g(ot + "_kd"),
                                  ctrl=sec(g(me + "_ctrl")), ctrl_abs=sec(g(ot + "_ctrl")), sub=g(me + "_sub_att")))
        L = pd.DataFrame(lines)
        for c in L.columns[3:]:
            L[c] = pd.to_numeric(L[c], errors="coerce")
        L = L[L.sig.notna()]
        self.Lg = {u: g for u, g in L.groupby("url")}
        self.Hg = {u: g for u, g in Hh.groupby("fighter_url")}
        # Elo before each bout, whole UFC history
        Hr = Hh[Hh.result.isin(["W", "L", "D"])].copy()
        Hr["pair"] = [tuple(sorted([a, b])) + (str(d.date()),) for a, b, d in zip(Hr.fighter_url, Hr.opponent_url, Hr.date)]
        Rt, PRE = {}, {}
        for r in Hr.sort_values(["date", "o2"], kind="mergesort").drop_duplicates("pair").itertuples():
            a, b = r.fighter_url, r.opponent_url
            ra, rb = Rt.get(a, 1500.0), Rt.get(b, 1500.0)
            PRE[(a, r.date)] = ra
            PRE[(b, r.date)] = rb
            ea = 1 / (1 + 10 ** ((rb - ra) / 400))
            sa = 1.0 if r.result == "W" else 0.0 if r.result == "L" else 0.5
            k = 40 * (1.25 if any(x in str(r.method) for x in ("KO", "SUB")) else 1.0)
            Rt[a] = ra + k * (sa - ea)
            Rt[b] = rb + k * ((1 - sa) - (1 - ea))
        self.Rt, self.PRE = Rt, PRE
        R = h["rounds"].copy()
        R["date"] = pd.to_datetime(R.date)
        R["diff"] = R.sig - R.sig_abs
        self.RG = {u: g for u, g in R.groupby("url")}
        # pro records: the gidstats pull (fighter_url -> page), pages this script found, and
        # UFC Stats results dated after the pull, so a record is never a card behind
        P = pd.read_csv(os.path.join(PRO, "people.csv"))
        FS = pd.read_csv(os.path.join(PRO, "fights.csv"))
        xp = os.path.join(HIST, "pro_extra.csv")
        if os.path.exists(xp):
            FS = pd.concat([FS, pd.read_csv(xp)], ignore_index=True)
        FS["date"] = pd.to_datetime(FS.date, errors="coerce")
        self.page = {r.fighter_url: r.page_url for r in P.itertuples() if isinstance(r.fighter_url, str)}
        self.asof = {}
        for r in P.itertuples():
            if isinstance(r.page_url, str) and isinstance(r.asof, str):
                self.asof[r.page_url] = max(self.asof.get(r.page_url, ""), r.asof)
        for u, v in h.get("pro_map", {}).items():
            self.page.setdefault(u, v["page"])
            self.asof[v["page"]] = max(self.asof.get(v["page"], ""), v.get("asof", ""))
        FSr = FS[FS.result.isin(["win", "loss", "draw"])].sort_values("date")
        self.PG = {u: g for u, g in FSr.groupby("page_url")}
        self.P, self.FS = P, FS

    def form(self, u, d):
        o = dict(n=0, wins=0, losses=0, streak=0, ko_wins=0, sub_wins=0, been_kod=0, been_subbed=0, last_kod=0, last_loss=0,
                 layoff=np.nan, l3=np.nan, last_date=pd.NaT)
        h = self.Hg.get(u)
        if h is None:
            return o
        p = h[(h.date < d) & h.result.isin(["W", "L", "D"])]
        if p.empty:
            return o
        o["n"] = len(p)
        o["wins"] = int((p.result == "W").sum())
        o["losses"] = int((p.result == "L").sum())
        s = 0
        for res in p.result.values[::-1]:
            if res == "W" and s >= 0:
                s += 1
            elif res == "L" and s <= 0:
                s -= 1
            else:
                break
        o["streak"] = s
        w = p[p.result == "W"]
        l = p[p.result == "L"]
        o["ko_wins"] = int(w.method.astype(str).str.contains("KO").sum())
        o["sub_wins"] = int(w.method.astype(str).str.contains("SUB").sum())
        o["been_kod"] = int(l.method.astype(str).str.contains("KO").sum())
        o["been_subbed"] = int(l.method.astype(str).str.contains("SUB").sum())
        last = p.iloc[-1]
        o["last_loss"] = int(last.result == "L")
        o["last_kod"] = int(last.result == "L" and "KO" in str(last.method))
        o["layoff"] = (d - last.date).days
        o["l3"] = (p.result.values[-3:] == "W").mean()
        o["last_date"] = last.date
        return o

    RK = ["slpm", "sapm", "acc", "tdpm", "tdacc", "tddef", "kdpm", "kdabs", "ctrl_share", "subpm", "strdef"]

    def rates(self, u, d):
        g = self.Lg.get(u)
        if g is None:
            return {k: np.nan for k in self.RK} | {"ufc_mins": 0.0}
        p = g[g.date < d]
        m = p.mins.sum()
        if p.empty or m < 1:
            return {k: np.nan for k in self.RK} | {"ufc_mins": 0.0}
        return dict(slpm=p.sig.sum() / m, sapm=p.sig_abs.sum() / m, acc=p.sig.sum() / max(p.sig_att.sum(), 1),
                    tdpm=p.td.sum() / m * 15, tdacc=p.td.sum() / max(p.td_att.sum(), 1),
                    tddef=(1 - p.tda.sum() / p.tda_att.sum()) if p.tda_att.sum() > 0 else np.nan,
                    kdpm=p.kd.sum() / m * 15, kdabs=p.kd_abs.sum() / m * 15,
                    ctrl_share=p.ctrl.sum() / max(p.ctrl.sum() + p.ctrl_abs.sum(), 1), subpm=p["sub"].sum() / m * 15,
                    strdef=np.nan, ufc_mins=m)

    def prof(self, u, d):
        g = self.RG.get(u)
        if g is None:
            return dict(r1=np.nan, late=np.nan)
        p = g[g.date < d]
        if p.date.nunique() < 2:
            return dict(r1=np.nan, late=np.nan)
        r1 = p[p.rnd == 1]
        late = p[p.rnd >= 3]
        return dict(r1=r1["diff"].mean(), late=late["diff"].mean() if len(late) else np.nan)

    def pro_rows(self, u):
        pu = self.page.get(u)
        g = self.PG.get(pu)
        if g is None:
            return None
        cut = self.asof.get(pu, "")
        h = self.Hg.get(u)
        if cut and h is not None:
            x = h[(h.date > pd.Timestamp(cut)) & h.result.isin(["W", "L", "D"])]
            if len(x):
                add = pd.DataFrame(dict(date=x.date.values, result=x.result.map({"W": "win", "L": "loss", "D": "draw"}).values,
                                        method=x.method.astype(str).values))
                g = pd.concat([g, add], ignore_index=True).sort_values("date", kind="mergesort")
        return g

    def pro(self, u, d):
        o = dict(pw=np.nan, pl=np.nan, pfin=np.nan, pkod=np.nan, psubbed=np.nan, pstreak=np.nan, pn=np.nan, has_page=0)
        g = self.pro_rows(u)
        if g is None:
            return o
        o["has_page"] = 1
        p = g[g.date < d]
        if p.empty:
            return o | dict(pn=0, pw=0, pl=0, pkod=0, psubbed=0, pstreak=0)
        w = p[p.result == "win"]
        l = p[p.result == "loss"]
        m = w.method.astype(str)
        lm = l.method.astype(str)
        k = m.ne("nan").sum()
        s = 0
        for r in p.result.values[::-1]:
            if r == "win" and s >= 0:
                s += 1
            elif r == "loss" and s <= 0:
                s -= 1
            else:
                break
        return dict(pw=len(w), pl=len(l), pfin=(m.str.contains("KO|Sub", case=False).sum() / k) if k else np.nan,
                    pkod=int(lm.str.contains("KO", case=False).sum()), psubbed=int(lm.str.contains("Sub", case=False).sum()),
                    pstreak=s, pn=len(p), has_page=1)

    def elo(self, u, d):
        v = self.PRE.get((u, d))
        if v is not None:
            return v
        if d > self.last_hist:          # a bout still to come: his rating now
            return self.Rt.get(u, 1500.0)
        return np.nan

    def row(self, d, a_url, b_url, **meta):
        row = dict(date=d, yr=d.year) | meta | dict(a_url=a_url, b_url=b_url)
        for side, u in (("a", a_url), ("b", b_url)):
            ft = self.FT.loc[u] if u in self.FT.index else None
            dob = pd.to_datetime(ft.dob) if ft is not None and isinstance(ft.dob, str) else pd.NaT
            row[side + "_age"] = (d - dob).days / 365.25 if pd.notna(dob) else np.nan
            row[side + "_reach"] = pd.to_numeric(ft.reach_in, errors="coerce") if ft is not None else np.nan
            row[side + "_height"] = pd.to_numeric(ft.height_in, errors="coerce") if ft is not None else np.nan
            for k, v in self.form(u, d).items():
                row[side + "_" + k] = v
            for k, v in self.rates(u, d).items():
                row[side + "_" + k] = v
            for k, v in self.prof(u, d).items():
                row[side + "_" + k] = v
            for k, v in self.pro(u, d).items():
                row[side + "_" + k] = v
            row[side + "_elo"] = self.elo(u, d)
        return row


SIDE = ["age", "reach", "height", "elo", "slpm", "sapm", "acc", "tdpm", "tddef", "ctrl_share", "kdpm", "kdabs", "subpm",
        "r1", "late", "ufc_mins", "n", "wins", "losses", "streak", "l3", "last_loss", "layoff", "ko_wins", "sub_wins",
        "been_kod", "been_subbed", "pw", "pl", "pn", "pstreak", "pfin", "pkod", "psubbed", "has_page"]
META = ["date", "yr", "event", "wc", "a", "b", "a_url", "b_url", "winner", "a_won", "method", "fight_url", "train"]
BCOLS = META + ["%s_%s" % (s, c) for s in "ab" for c in SIDE]


def bout_rows(h, fe, fights):
    """bouts-table rows for finished UFC Stats bouts"""
    rows = []
    for r in fights.itertuples(index=False):
        d = pd.Timestamp(r.event_date)
        row = fe.row(d, r.red_url, r.blue_url, event=r.event_name, wc=r.weight_class, a=r.red_name, b=r.blue_name,
                     winner=r.winner, a_won=int(r.winner == "red"), method=r.method, fight_url=r.fight_url,
                     train=r.winner in ("red", "blue"))
        rows.append(row)
    return pd.DataFrame(rows).reindex(columns=BCOLS)


# ---------------------------------------------------------------- the model's features (walk.py's FEAT, unchanged)
def feat(X):
    f = lambda s, c: X[s + "_" + c].astype(float)

    def d(c):
        return f("a", c) - f("b", c)

    def ppct(s):
        return f(s, "pw") / (f(s, "pw") + f(s, "pl")).where((f(s, "pw") + f(s, "pl")) > 0)

    def dur(s):
        return (f(s, "pkod").fillna(f(s, "been_kod")) + f(s, "psubbed").fillna(f(s, "been_subbed")))
    return pd.DataFrame({
        "age": -d("age"),
        "reach": d("reach"), "height": d("height"), "elo": d("elo"),
        "strike_diff": (f("a", "slpm") - f("a", "sapm")) - (f("b", "slpm") - f("b", "sapm")),
        "sapm": -d("sapm"), "slpm": d("slpm"), "acc": d("acc"),
        "td_vs_def": f("a", "tdpm") * (1 - f("b", "tddef")) - f("b", "tdpm") * (1 - f("a", "tddef")),
        "tddef": d("tddef"), "tdpm": d("tdpm"), "ctrl": d("ctrl_share"), "kdpm": d("kdpm"), "kdabs": -d("kdabs"), "subpm": d("subpm"),
        "r1": d("r1"), "late": d("late"),
        "ufc_exp": np.log1p(f("a", "ufc_mins")) - np.log1p(f("b", "ufc_mins")), "ufc_n": d("n"),
        "layoff": -(f("a", "layoff").clip(upper=1000) - f("b", "layoff").clip(upper=1000)),
        "streak": d("streak"), "l3": d("l3"), "last_loss": -d("last_loss"),
        "pro_pct": ppct("a") - ppct("b"), "pro_losses": -d("pl"), "pro_n": d("pn"), "pro_streak": d("pstreak"),
        "pro_fin": f("a", "pfin") - f("b", "pfin"),
        "fin_vs_dur": f("a", "pfin").fillna(0) * dur("b").clip(upper=6) - f("b", "pfin").fillna(0) * dur("a").clip(upper=6),
        "ko_vs_chin": f("a", "kdpm").fillna(0) * f("b", "been_kod") - f("b", "kdpm").fillna(0) * f("a", "been_kod"),
        "durability": -(dur("a") - dur("b")),
        "debut": (f("b", "n") == 0).astype(int) - (f("a", "n") == 0).astype(int),
    }, index=X.index)


def women(X):
    return X.wc.astype(str).str.contains("Women").values


def train_mask(X, before):
    return ((X.date < pd.Timestamp(before)).values & ~women(X) & X.winner.isin(["red", "blue"]).values
            & X.train.astype(bool).values)


def fit(h, before, out):
    """the production fit: men's decided bouts before the card (the audit's sample),
       walk2.py's prep and settings; exported as trees and checked against sklearn"""
    import sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    X = h["bouts"].reset_index(drop=True)
    FE = feat(X)
    FC = list(FE.columns)
    F = FE.copy()
    for c in FC:
        F[c + "_na"] = F[c].isna().astype(int)
        F[c] = F[c].fillna(0)
    tr = train_mask(X, before)
    F = F.loc[:, F[tr].std() > 0]
    mu, sd = F[tr].mean(), F[tr].std()
    Z = ((F - mu) / sd).values
    y = X.a_won.values
    m = HistGradientBoostingClassifier(**GBM).fit(np.vstack([Z[tr], -Z[tr]]), np.concatenate([y[tr], 1 - y[tr]]))
    trees = []
    for it in m._predictors:
        n = it[0].nodes
        trees.append(dict(f=n["feature_idx"].tolist(), t=n["num_threshold"].tolist(), l=n["left"].tolist(),
                          r=n["right"].tolist(), leaf=n["is_leaf"].astype(int).tolist(), v=n["value"].tolist(),
                          ml=n["missing_go_to_left"].astype(int).tolist()))
    M = dict(model="HistGradientBoostingClassifier", sklearn=sklearn.__version__, params=GBM,
             before=str(pd.Timestamp(before).date()), last_bout=str(X.date[tr].max().date()), n_train=int(tr.sum()),
             fc=FC, cols=list(F.columns), mean=mu.tolist(), std=sd.tolist(),
             baseline=float(np.ravel(m._baseline_prediction)[0]), trees=trees,
             tiers=[dict(min=t, won=w) for t, w in TIERS],
             note="symmetric: p = (P(a|z) + 1 - P(a|-z)) / 2; z = (x - mean) / std, missing -> 0 plus a _na flag")
    # parity: the JSON trees against sklearn on every training row and the newest 500
    Zs = np.vstack([Z[tr][-1500:], Z[-500:]])
    ps = (m.predict_proba(Zs)[:, 1] + 1 - m.predict_proba(-Zs)[:, 1]) / 2
    pj = sym_p(M, Zs)
    err = float(np.max(np.abs(ps - pj)))
    M["parity_max_abs"] = err
    assert err < 1e-9, err
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(M, open(out, "w"), separators=(",", ":"))
    print("model fit on %d bouts before %s (%d trees), JSON vs sklearn max |dp| %.2e -> %s"
          % (tr.sum(), M["before"], len(trees), err, os.path.relpath(out, D)))
    return M


def raw_p(M, Z):
    out = np.full(len(Z), M["baseline"])
    rows = np.arange(len(Z))
    for t in M["trees"]:
        f, th, l, r = np.array(t["f"]), np.array(t["t"]), np.array(t["l"]), np.array(t["r"])
        leaf, v, ml = np.array(t["leaf"], bool), np.array(t["v"]), np.array(t["ml"], bool)
        idx = np.zeros(len(Z), int)
        while True:
            live = ~leaf[idx]
            if not live.any():
                break
            x = Z[rows, f[idx]]
            go = np.where(np.isnan(x), ml[idx], x <= th[idx])
            idx = np.where(live, np.where(go, l[idx], r[idx]), idx)
        out = out + v[idx]
    return 1.0 / (1.0 + np.exp(-out))


def sym_p(M, Z):
    return (raw_p(M, Z) + 1 - raw_p(M, -Z)) / 2


def zmat(M, X):
    FE = feat(X)
    F = FE[M["fc"]].copy()
    for c in M["fc"]:
        F[c + "_na"] = F[c].isna().astype(int)
        F[c] = F[c].fillna(0)
    F = F.reindex(columns=M["cols"])
    return ((F - np.array(M["mean"])) / np.array(M["std"])).values, FE


# ---------------------------------------------------------------- the why, in words
def _sur(n):
    p = [w for w in str(n).split() if w.lower().strip(".") not in ("jr", "sr", "ii", "iii")]
    return p[-1] if p else str(n)


def _yrs(x):
    return "%.0f" % x


def why(r, s, M, z, FE):
    """the stat edges that move the model most for the pick: each feature taken
       back to the average (z = 0) and the drop in the pick's chance measured;
       the biggest three or four, said with both men's numbers"""
    o = "b" if s == "a" else "a"
    g = lambda side, c: r[side + "_" + c]
    me, op = _sur(r[s]), _sur(r[o])
    base = sym_p(M, z[None, :])[0]
    base = base if s == "a" else 1 - base
    cols = M["cols"]
    drops = []
    for c in M["fc"]:
        z2 = z.copy()
        for k in (c, c + "_na"):
            if k in cols:
                z2[cols.index(k)] = 0.0
        p2 = sym_p(M, z2[None, :])[0]
        p2 = p2 if s == "a" else 1 - p2
        v = FE[c]
        v = v if s == "a" else -v
        if base - p2 > 0.003 and v == v and v > 0:
            drops.append((base - p2, c))
    drops.sort(reverse=True)

    def num(x, f="%.1f"):
        return f % x if x == x else "n/a"

    def rec(side):
        w, l = g(side, "pw"), g(side, "pl")
        return "%d-%d" % (w, l) if w == w and l == l else "n/a"
    T = {
        "age": lambda: "%s years younger (%s vs %s)" % (_yrs(g(o, "age") - g(s, "age")), _yrs(g(s, "age")), _yrs(g(o, "age")))
                       if g(o, "age") - g(s, "age") >= 1.5 else "Younger (%.1f vs %.1f)" % (g(s, "age"), g(o, "age")),
        "reach": lambda: '%.0f" more reach (%.0f vs %.0f)' % (g(s, "reach") - g(o, "reach"), g(s, "reach"), g(o, "reach")),
        "height": lambda: '%.0f" taller' % (g(s, "height") - g(o, "height")),
        "elo": lambda: "Higher UFC rating (%.0f vs %.0f)" % (g(s, "elo"), g(o, "elo")),
        "strike_diff": lambda: "Strike margin %+.1f a minute vs %+.1f" % (g(s, "slpm") - g(s, "sapm"), g(o, "slpm") - g(o, "sapm")),
        "sapm": lambda: "Absorbs %.1f strikes a minute, %s %.1f" % (g(s, "sapm"), op, g(o, "sapm")),
        "slpm": lambda: "Lands %.1f strikes a minute, %s %.1f" % (g(s, "slpm"), op, g(o, "slpm")),
        "acc": lambda: "Lands %.0f%% of strikes, %s %.0f%%" % (100 * g(s, "acc"), op, 100 * g(o, "acc")),
        "td_vs_def": lambda: "Takedowns: %s per 15 min into %s's %s defense" % (
            num(g(s, "tdpm")), op, ("%.0f%%" % (100 * g(o, "tddef"))) if g(o, "tddef") == g(o, "tddef") else "untested"),
        "tddef": lambda: "Stops %.0f%% of takedowns, %s %.0f%%" % (100 * g(s, "tddef"), op, 100 * g(o, "tddef")),
        "tdpm": lambda: "%.1f takedowns per 15 min, %s %.1f" % (g(s, "tdpm"), op, g(o, "tdpm")),
        "ctrl": lambda: "Controls %.0f%% of grappling time, %s %.0f%%" % (100 * g(s, "ctrl_share"), op, 100 * g(o, "ctrl_share")),
        "kdpm": lambda: "%.2f knockdowns per 15 min, %s %.2f" % (g(s, "kdpm"), op, g(o, "kdpm")),
        "kdabs": lambda: "Knocked down %.2f times per 15 min, %s %.2f" % (g(s, "kdabs"), op, g(o, "kdabs")),
        "subpm": lambda: "%.1f submission tries per 15 min, %s %.1f" % (g(s, "subpm"), op, g(o, "subpm")),
        "r1": lambda: "Round 1 margin %s strikes, %s %s" % (num(g(s, "r1"), "%+.0f"), op, num(g(o, "r1"), "%+.0f")),
        "late": lambda: "Late-round margin %s strikes, %s %s" % (num(g(s, "late"), "%+.0f"), op, num(g(o, "late"), "%+.0f")),
        "ufc_exp": lambda: "UFC minutes %.0f vs %.0f" % (g(s, "ufc_mins"), g(o, "ufc_mins")),
        "ufc_n": lambda: "%d UFC fights vs %d" % (g(s, "n"), g(o, "n")),
        "layoff": lambda: "Fought %s months ago, %s %s" % (
            num(g(s, "layoff") / 30.4, "%.0f"), op, num(g(o, "layoff") / 30.4, "%.0f")),
        "streak": lambda: "UFC streak %s vs %s" % (("W%d" % g(s, "streak")) if g(s, "streak") > 0 else ("L%d" % -g(s, "streak")),
                                                   ("W%d" % g(o, "streak")) if g(o, "streak") > 0 else ("L%d" % -g(o, "streak"))),
        "l3": lambda: "Won %d of last 3 UFC fights, %s %d" % (round(3 * g(s, "l3")), op, round(3 * g(o, "l3"))),
        "last_loss": lambda: "%s lost his last fight" % op if not women_row(r) else "%s lost her last fight" % op,
        "pro_pct": lambda: "Pro record %s vs %s" % (rec(s), rec(o)),
        "pro_losses": lambda: "%d pro losses vs %d" % (g(s, "pl"), g(o, "pl")),
        "pro_n": lambda: "%d pro fights vs %d" % (g(s, "pn"), g(o, "pn")),
        "pro_streak": lambda: "Pro streak %s vs %s" % (("W%d" % g(s, "pstreak")) if g(s, "pstreak") > 0 else ("L%d" % -g(s, "pstreak")),
                                                     ("W%d" % g(o, "pstreak")) if g(o, "pstreak") > 0 else ("L%d" % -g(o, "pstreak"))),
        "pro_fin": lambda: "Finishes %.0f%% of pro wins, %s %.0f%%" % (100 * g(s, "pfin"), op, 100 * g(o, "pfin")),
        "fin_vs_dur": lambda: "Finishes %.0f%% of wins; %s finished %s" % (
            100 * (g(s, "pfin") if g(s, "pfin") == g(s, "pfin") else 0), op, times(durn(r, o))),
        "ko_vs_chin": lambda: "KO power (%.2f knockdowns per 15 min) vs %s, KO'd %s in the UFC" % (
            g(s, "kdpm"), op, times(g(o, "been_kod"))),
        "durability": lambda: "Finished %s as a pro, %s %s" % (times(durn(r, s)), op, times(durn(r, o))),
        "debut": lambda: "%s makes a UFC debut" % op,
    }
    out = []
    for _, c in drops:
        try:
            out.append(T[c]())
        except Exception:
            continue
        if len(out) == 4:
            break
    return out


def times(n):
    n = int(n)
    return "once" if n == 1 else "never" if n == 0 else "%d times" % n


def women_row(r):
    return "Women" in str(r.get("wc", ""))


def durn(r, s):
    k = r[s + "_pkod"] if r[s + "_pkod"] == r[s + "_pkod"] else r[s + "_been_kod"]
    b = r[s + "_psubbed"] if r[s + "_psubbed"] == r[s + "_psubbed"] else r[s + "_been_subbed"]
    return int(k + b)


# ---------------------------------------------------------------- the call: one side on every men's bout
# Every market the bout sheet carries was modeled walk-forward (research: scratchpad
# ufc_call/; fit on the years before, men's decided bouts, no odds): moneyline, each
# man by KO/TKO/DQ, submission or decision, the Method of Victory double chances,
# Exact Method of Victory, Fight to Go the Distance yes/no, Round Betting, Alternate
# Round Betting and Winning Round. Every one of them is a part of one man winning or
# of the fight ending early / going the distance, so the likeliest side on the sheet
# is always the moneyline favorite or a side of Fight to Go the Distance -- the
# call is whichever of the two the models rate higher. "won" is the blind
# 2022-26 hit rate of that market's side in that 5-point band (CALL_WON).
#
#   best call per bout, blind   all      75%+ calls
#     2022-23                   67.0%    80.1% (136, 1.60 a card, 17% of bouts)
#     2024-26                   66.6%    84.5% (193, 1.62 a card, 16% of bouts)
#
# The distance model: a depth-2 boosted tree on both men's stats (scored from both
# corners and averaged) and a ridge logistic on the pair's means and gaps, the two
# averaged -- chosen on 2019-21 only (scratchpad ufc_call/dist_tune.py). Kept in
# data/models/ufc_dist.json; refit like the winner model when scikit-learn is here.
DMODEL = os.path.join(D, "data", "models", "ufc_dist.json")
EXTRA = os.path.join(HIST, "extra.parquet")      # per-bout side stats the distance model adds, cached by fight
DGBM = dict(GBM, max_depth=2)
DLR_C = 0.05
# blind 2022-26 hit rate, best call per bout, by market side and band: [won %, bouts]
CALL_WON = {
    "ml": {80: (88, 81), 75: (80, 164), 70: (74, 201), 65: (67, 289), 60: (62, 255), 0: (60, 242)},
    "fin": {80: (88, 34), 75: (78, 45), 70: (67, 82), 65: (68, 122), 60: (64, 102), 0: (55, 120)},
    "dist": {70: (70, 30), 65: (63, 57), 60: (59, 99), 0: (55, 119)},   # 75%+ merged into 70: 5 bouts only
}
WLB = (("Light Heavyweight", 205), ("Heavyweight", 265), ("Flyweight", 125), ("Bantamweight", 135),
       ("Featherweight", 145), ("Lightweight", 155), ("Welterweight", 170), ("Middleweight", 185))
EXCOLS = ["u_n", "u_dec", "u_mins_mean", "pkow", "psubw", "pdecw", "pkol", "psubl", "pdecl"]


def wc_lb(wc):
    s = str(wc)
    if "Women" in s:
        return np.nan
    return next((v for k, v in WLB if k in s), np.nan)


def side_extra(fe, u, d):
    """his decisions and average UFC fight length, and his pro wins and losses by
       method, as of the morning of the bout"""
    o = {}
    h = fe.Hg.get(u)
    p = h[(h.date < d) & h.result.isin(["W", "L", "D"])] if h is not None else None
    if p is None or p.empty:
        o.update(u_dec=0, u_n=0)
    else:
        o["u_n"] = len(p)
        o["u_dec"] = int(p.method.astype(str).str.contains("DEC|Decision").sum())
    g = fe.Lg.get(u)
    q = g[g.date < d] if g is not None else None
    o["u_mins_mean"] = q.mins.mean() if q is not None and len(q) else np.nan
    for k in ("pkow", "psubw", "pdecw", "pkol", "psubl", "pdecl"):
        o[k] = np.nan
    pr = fe.pro_rows(u)
    if pr is not None:
        q = pr[pr.date < d]
        w = q[q.result == "win"].method.astype(str)
        l = q[q.result == "loss"].method.astype(str)
        o["pkow"] = int(w.str.contains("KO|DQ", case=False).sum())
        o["psubw"] = int(w.str.contains("Sub", case=False).sum())
        o["pdecw"] = int(w.str.contains("Dec", case=False).sum())
        o["pkol"] = int(l.str.contains("KO|DQ", case=False).sum())
        o["psubl"] = int(l.str.contains("Sub", case=False).sum())
        o["pdecl"] = int(l.str.contains("Dec", case=False).sum())
    return o


def extras(fe, X, cache=None):
    """the extra side stats for each row of X: from the cache by fight url, else computed"""
    rows = []
    for r in X.itertuples(index=False):
        fu = getattr(r, "fight_url", None)
        if cache is not None and isinstance(fu, str) and fu in cache.index:
            rows.append(cache.loc[fu].to_dict())
            continue
        row = {}
        for s, u in (("a", r.a_url), ("b", r.b_url)):
            for k, v in side_extra(fe, u, r.date).items():
                row[s + "_" + k] = v
        rows.append(row)
    return pd.DataFrame(rows, index=X.index).reindex(columns=["%s_%s" % (s, c) for s in "ab" for c in EXCOLS])


def side_tab(X, s):
    g = lambda c: X[s + "_" + c].astype(float)
    n = g("n").where(g("n") > 0)
    pn = g("pn").where(g("pn") > 0)
    un = g("u_n").where(g("u_n") > 0)
    o = {}
    for c in ("age", "reach", "height", "elo", "slpm", "sapm", "acc", "tdpm", "tddef", "ctrl_share", "kdpm", "kdabs",
              "subpm", "r1", "late", "ufc_mins", "n", "layoff", "pn", "pfin", "u_mins_mean", "streak", "l3"):
        o[c] = g(c)
    o["ko_rate"] = g("ko_wins") / n
    o["sub_rate"] = g("sub_wins") / n
    o["kod_rate"] = g("been_kod") / n
    o["subbed_rate"] = g("been_subbed") / n
    o["udec_share"] = g("u_dec") / un
    o["pko_rate"] = g("pkow") / pn
    o["psub_rate"] = g("psubw") / pn
    o["pdec_rate"] = g("pdecw") / pn
    o["pkol_rate"] = g("pkol") / pn
    o["psubl_rate"] = g("psubl") / pn
    o["pdecl_rate"] = g("pdecl") / pn
    return pd.DataFrame(o, index=X.index)


def ordered_tab(X, a="a", b="b"):
    """the bout from a's corner: both men's stats, each man's weapon into the other's
       weakness, the scheduled rounds, the weight and a title"""
    SA, SB = side_tab(X, a), side_tab(X, b)
    F = pd.concat([SA.add_prefix("A_"), SB.add_prefix("B_")], axis=1)
    F["A_ko_vs_chin"] = SA.ko_rate.fillna(SA.pko_rate) * SB.kod_rate.fillna(SB.pkol_rate)
    F["B_ko_vs_chin"] = SB.ko_rate.fillna(SB.pko_rate) * SA.kod_rate.fillna(SA.pkol_rate)
    F["A_sub_vs_def"] = SA.sub_rate.fillna(SA.psub_rate) * SB.subbed_rate.fillna(SB.psubl_rate)
    F["B_sub_vs_def"] = SB.sub_rate.fillna(SB.psub_rate) * SA.subbed_rate.fillna(SA.psubl_rate)
    F["A_kd_vs_kdabs"] = SA.kdpm * SB.kdabs
    F["B_kd_vs_kdabs"] = SB.kdpm * SA.kdabs
    F["A_td_vs_def"] = SA.tdpm * (1 - SB.tddef)
    F["B_td_vs_def"] = SB.tdpm * (1 - SA.tddef)
    F["A_pace"] = SA.slpm + SB.sapm
    F["B_pace"] = SB.slpm + SA.sapm
    F["elo_gap"] = SA.elo - SB.elo
    F["sched"] = pd.to_numeric(X.scheduled_rounds, errors="coerce").astype(float)
    F["wlb"] = X.wc.map(wc_lb).astype(float)
    F["title"] = (X.title_bout.astype(str) == "true").astype(int)
    return F


def sym_tab(X, FA):
    SA, SB = side_tab(X, "a"), side_tab(X, "b")
    S = pd.concat([((SA + SB) / 2).add_prefix("m_"), (SA - SB).abs().add_prefix("d_")], axis=1)
    S["kochin"] = FA.A_ko_vs_chin + FA.B_ko_vs_chin
    S["subdef"] = FA.A_sub_vs_def + FA.B_sub_vs_def
    S["kdkd"] = FA.A_kd_vs_kdabs + FA.B_kd_vs_kdabs
    S["sched"], S["wlb"], S["title"] = FA.sched, FA.wlb, FA.title
    S["elo_gap"] = FA.elo_gap.abs()
    return S


def mclass(m):
    m = str(m)
    return "DEC" if "DEC" in m else "SUB" if m == "SUB" else "KO" if m in ("KO/TKO", "DQ") else None


def dist_tables(h, X, fe=None, cache=True):
    """X (bouts rows plus scheduled_rounds / title_bout) -> FA, FB, S"""
    fe = fe or Feats(h)
    C = None
    if cache and os.path.exists(EXTRA):
        C = pd.read_parquet(EXTRA).drop_duplicates("fight_url", keep="last").set_index("fight_url")
    E = extras(fe, X, C)
    if cache and "fight_url" in X:
        have = set(C.index) if C is not None else set()
        new = X.fight_url.notna() & ~X.fight_url.isin(have)
        if new.any():
            add = E[new.values].assign(fight_url=X.fight_url[new].values)
            C2 = pd.concat([C.reset_index() if C is not None else None, add], ignore_index=True)
            C2.to_parquet(EXTRA, index=False, compression="zstd")
    X = pd.concat([X.drop(columns=[c for c in E.columns if c in X], errors="ignore"), E], axis=1)
    FA, FB = ordered_tab(X, "a", "b"), ordered_tab(X, "b", "a")
    return FA, FB[FA.columns], sym_tab(X, FA)


def fit_dist(h, before, out):
    """the distance model, fit on men's decided bouts before the card; trees and the
       logistic exported to JSON and checked against scikit-learn"""
    import sklearn
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    F = h["fights"][["fight_url", "scheduled_rounds", "title_bout"]].drop_duplicates("fight_url")
    X = h["bouts"].reset_index(drop=True).merge(F, on="fight_url", how="left")
    FA, FB, S = dist_tables(h, X)
    mc = X.method.map(mclass)
    tr = train_mask(X, before) & mc.notna().values
    y = (mc == "DEC").astype(int).values
    m = HistGradientBoostingClassifier(**DGBM).fit(pd.concat([FA[tr], FB[tr]]).values, np.concatenate([y[tr], y[tr]]))
    trees = []
    for it in m._predictors:
        n = it[0].nodes
        trees.append(dict(f=n["feature_idx"].tolist(), t=n["num_threshold"].tolist(), l=n["left"].tolist(),
                          r=n["right"].tolist(), leaf=n["is_leaf"].astype(int).tolist(), v=n["value"].tolist(),
                          ml=n["missing_go_to_left"].astype(int).tolist()))
    St = S[tr].values
    med = np.nanmedian(St, 0)
    fz = np.where(np.isnan(St), med, St)
    mu, sd = fz.mean(0), fz.std(0) + 1e-9
    lr = LogisticRegression(C=DLR_C, max_iter=2000).fit((fz - mu) / sd, y[tr])
    M = dict(model="HistGradientBoostingClassifier + LogisticRegression", sklearn=sklearn.__version__, gbm=DGBM, C=DLR_C,
             before=str(pd.Timestamp(before).date()), last_bout=str(X.date[tr].max().date()), n_train=int(tr.sum()),
             cols_o=list(FA.columns), cols_s=list(S.columns), baseline=float(np.ravel(m._baseline_prediction)[0]),
             trees=trees, med=med.tolist(), mu=mu.tolist(), sd=sd.tolist(), coef=lr.coef_[0].tolist(),
             icpt=float(lr.intercept_[0]), won=CALL_WON,
             note="P(goes the distance) = mean of the trees (scored from both corners, averaged) and the logistic")
    k = np.r_[np.flatnonzero(tr)[-1500:], np.arange(len(X))[-300:]]
    ps = ((m.predict_proba(FA.values[k])[:, 1] + m.predict_proba(FB.values[k])[:, 1]) / 2
          + lr.predict_proba((np.where(np.isnan(S.values[k]), med, S.values[k]) - mu) / sd)[:, 1]) / 2
    pj = dist_p(M, FA.iloc[k], FB.iloc[k], S.iloc[k])[0]
    err = float(np.max(np.abs(ps - pj)))
    M["parity_max_abs"] = err
    assert err < 1e-9, err
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(M, open(out, "w"), separators=(",", ":"))
    print("distance model fit on %d bouts before %s (%d trees), JSON vs sklearn max |dp| %.2e -> %s"
          % (tr.sum(), M["before"], len(trees), err, os.path.relpath(out, D)))
    return M


def dist_p(M, FA, FB, S):
    """P(goes the distance) and the logistic's per-feature pushes (+ toward the cards)"""
    A = FA.reindex(columns=M["cols_o"]).values.astype(float)
    B = FB.reindex(columns=M["cols_o"]).values.astype(float)
    p1 = (raw_p(M, A) + raw_p(M, B)) / 2
    Q = S.reindex(columns=M["cols_s"]).values.astype(float)
    z = (np.where(np.isnan(Q), np.array(M["med"]), Q) - np.array(M["mu"])) / np.array(M["sd"])
    push = z * np.array(M["coef"])
    p2 = 1 / (1 + np.exp(-(push.sum(1) + M["icpt"])))
    return (p1 + p2) / 2, push


def dist_why(r, push, cols, toward_dec):
    """the logistic's biggest pushes toward the call, said with both men's numbers;
       only stats whose plain reading points the same way (a high finish rate toward
       a finish, long fights toward the cards)"""
    a, b = _sur(r["a"]), _sur(r["b"])
    g = lambda s, c: r[s + "_" + c]

    def pct(x):
        return "%.0f%%" % (100 * x) if x == x else "n/a"

    def rate(s, k):
        pn = g(s, "pn")
        return g(s, k) / pn if pn == pn and pn > 0 else np.nan

    def both(lab, fa, fb):
        return "%s: %s %s, %s %s" % (lab, a, fa, b, fb)
    # feature -> (plain direction: +1 toward the cards, -1 toward a finish, text)
    T = {
        "m_pdec_rate": (1, lambda: both("Pro fights won on the cards", pct(rate("a", "pdecw")), pct(rate("b", "pdecw")))),
        "m_pdecl_rate": (1, lambda: both("Pro losses on the cards", "%d" % g("a", "pdecl"), "%d" % g("b", "pdecl"))),
        "m_u_mins_mean": (1, lambda: both("Average UFC fight", "%.1f min" % g("a", "u_mins_mean"), "%.1f min" % g("b", "u_mins_mean"))),
        "m_udec_share": (1, lambda: both("UFC fights to the cards", "%d of %d" % (g("a", "u_dec"), g("a", "u_n")),
                                          "%d of %d" % (g("b", "u_dec"), g("b", "u_n")))),
        "m_ufc_mins": (1, lambda: both("UFC minutes", "%.0f" % g("a", "ufc_mins"), "%.0f" % g("b", "ufc_mins"))),
        "m_pfin": (-1, lambda: both("Pro wins by finish", pct(g("a", "pfin")), pct(g("b", "pfin")))),
        "kochin": (-1, lambda: "KO wins vs KO losses: %s %d KO wins, %s KO'd %s; %s %d KO wins, %s KO'd %s" % (
            a, g("a", "pkow"), b, times(g("b", "pkol")), b, g("b", "pkow"), a, times(g("a", "pkol")))),
        "m_sapm": (-1, lambda: both("Strikes absorbed a minute", "%.1f" % g("a", "sapm"), "%.1f" % g("b", "sapm"))),
        "m_psubl_rate": (-1, lambda: both("Submitted as a pro", times(g("a", "psubl")), times(g("b", "psubl")))),
        "m_pkol_rate": (-1, lambda: both("KO'd as a pro", times(g("a", "pkol")), times(g("b", "pkol")))),
        "m_subpm": (-1, lambda: both("Submission tries per 15 min", "%.1f" % g("a", "subpm"), "%.1f" % g("b", "subpm"))),
        "elo_gap": (-1, lambda: "UFC rating gap %.0f points (%s %.0f, %s %.0f)" % (abs(g("a", "elo") - g("b", "elo")), a, g("a", "elo"), b, g("b", "elo"))),
        "sched": (-1, lambda: "Five-round fight"),
    }
    want = 1 if toward_dec else -1
    out = []
    for j in np.argsort(-push * want):
        c = cols[j]
        if push[j] * want <= 0:
            break
        if c in T and T[c][0] == want:
            try:
                out.append(T[c][1]())
            except Exception:
                continue
        if len(out) == 3:
            break
    return out


def call_won(kind, p):
    tab = CALL_WON[kind]
    k = max(t for t in tab if 100 * p >= t)
    return tab[k]


def make_call(x, pdist, push, cols):
    """the likeliest side on the sheet: the moneyline favorite or a side of the distance"""
    pml = x["conf"]
    cand = [(pml, "ml"), (1 - pdist, "fin"), (pdist, "dist")]
    p, kind = max(cand, key=lambda c: (c[0], c[1] == "ml"))
    won, n = call_won(kind, p)
    if kind == "ml":
        c = dict(market="Moneyline", sel=x["pick"], side="%s wins" % _sur(x["pick"]), why=list(x["why"]))
    else:
        dec = kind == "dist"
        c = dict(market="Fight to Go the Distance", sel="Yes" if dec else "No",
                 side="Fight goes the distance" if dec else "Fight does not go the distance",
                 why=dist_why(x["row"], push, cols, dec))
    c.update(p=int(round(100 * p)), won=won, won_n=n, p_ml=int(round(100 * pml)), p_dist=int(round(100 * pdist)))
    return c


# ---------------------------------------------------------------- fight-week facts from Wikipedia
# The research parser (research: scratchpad ufc_ctx/parse_wiki.py), cut down to
# what the card needs: who stepped in and on how much notice, and who missed
# weight and by how much. Everything here is known by Friday's weigh-in.
WLIM = {"Women's Strawweight": 115, "Women's Flyweight": 125, "Women's Bantamweight": 135, "Women's Featherweight": 145,
        "Light Heavyweight": 205, "Flyweight": 125, "Bantamweight": 135, "Featherweight": 145, "Lightweight": 155,
        "Welterweight": 170, "Middleweight": 185, "Heavyweight": 265}
_MON = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
_NUMW = {"a": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
         "eleven": 11, "twelve": 12, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30}
_REF = re.compile(r"<ref[^>/]*/>|<ref[^>]*>.*?</ref>", re.S)
_REPL_BY = re.compile(r"replaced by|replacement (?:was|being)|in favou?r of|opponent (?:was|became|changed to)|will now face|"
                      r"would now face|instead (?:face[sd]?|fought|met|took on)", re.I)
_REPL_SUBJ = re.compile(r"stepp(?:ed|ing) in|stepp(?:ed|ing) up|as (?:a|his|her|the) (?:late |short[- ]notice )?replacement|"
                        r"filled in|took (?:the|his|her) place|took over|was tabbed|agreed to (?:fill|step)|\breplaced\b(?! by)|"
                        r"replac(?:e|ing) (?!by)", re.I)
_MISS = re.compile(r"missed (?:the )?(?:required )?weight|missed the [\w\s'-]*limit|failed to make weight|came in (?:\w+ )?over|"
                   r"weighed in (?:at|heavy)|came in at \d|tipped the scales at", re.I)
_SHORT = re.compile(r"short[- ]notice|late[- ]notice|last[- ]minute|eleventh[- ]hour|days before|fight week|"
                    r"on (?:\w+ )?(?:days|weeks)'? notice", re.I)
_NEWC = re.compile(r"newcomer|promotional debut|UFC debut|making (?:his|her) debut", re.I)
_NOTPERSON = re.compile(r"Championship|UFC|Bellator|Arena|Center|Centre|Fight|Ultimate|Olympic|Grand|Contender|PFL|ONE|Series|"
                        r"Nevada|Commission|Agency|Kickboxing|Wrestling|Judo|Boxing|COVID|Jiu")
_DELINK = re.compile(r"\[\[(?:[^\]|]+\|)?([^\]]+)\]\]")


def _wtoks(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\(.*?\)", " ", s)
    s = re.sub(r"[^a-z ]+", " ", s.replace("-", " "))
    return [t for t in s.split() if t not in ("jr", "sr", "ii", "iii", "iv")]


def wc_limit(wc, title=False):
    """the scale's limit for a bout: the class limit, plus a pound off a title bout"""
    s = str(wc).lower()
    for k, v in WLIM.items():
        if k.lower() in s and ("women" in s) == k.startswith("Women"):
            return v if title else v + 1
    return None


class WikiCard:
    """the card's men, by every spelling we hold (UFC Stats, the board, the
       Wikipedia fight card), so a sentence's names land on the right man"""

    def __init__(self, men, gidx):
        self.f = []                     # (url, tokens, written name)
        for u, names in men.items():
            for n in dict.fromkeys(names):
                if _wtoks(n):
                    self.f.append((u, _wtoks(n), n))
        self.gidx = gidx
        self.last = {}
        for u, tk, _ in self.f:
            self.last.setdefault(tk[-1], set()).add(u)

    def match(self, text):
        tk = _wtoks(text)
        if not tk:
            return None
        for u, ft, _ in self.f:
            if tk == ft or set(tk) == set(ft):
                return u
        for u, ft, _ in self.f:         # 'Kim Ji-yeon' vs 'Ji Yeon Kim', middle names
            if len(tk) >= 2 and tk[-1] in ft and tk[0] in ft:
                return u
        if len(tk) == 1 and len(self.last.get(tk[0], ())) == 1:
            return next(iter(self.last[tk[0]]))
        if len(tk) >= 2 and len(self.last.get(tk[-1], ())) == 1:
            u = next(iter(self.last[tk[-1]]))
            if any(x[0] == u and x[1][0][:1] == tk[0][:1] for x in self.f):
                return u
        return None

    def mentions(self, s):
        """[(pos, card url or None, any known url or None, text)] in reading order:
           wiki links, then card men's full names, then their bare surnames"""
        out = []
        for m in re.finditer(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", s):
            txt, tgt = m.group(2) or m.group(1), re.sub(r"\(.*?\)", "", m.group(1))
            u = self.match(txt) or self.match(tgt)
            g = u or self.gidx.get(" ".join(_wtoks(txt))) or self.gidx.get(" ".join(_wtoks(tgt)))
            person = bool(re.match(r"^[A-Z][\w'\-\.]+(?: [A-Z\w'\-\.]+){0,4}$", txt.strip())) and not _NOTPERSON.search(txt)
            if u or g or person:
                out.append((m.start(), u, g, txt))
        plain = re.sub(r"\[\[[^\]]*\]\]", lambda m: " " * len(m.group(0)), s)
        for u, ft, name in self.f:
            for m in re.finditer(r"\b%s\b" % re.escape(name), plain):
                out.append((m.start(), u, u, m.group(0)))
                plain = plain[:m.start()] + " " * len(m.group(0)) + plain[m.end():]
        for u, ft, name in self.f:
            for m in re.finditer(r"\b%s\b" % re.escape(name.split()[-1]), plain):
                if len(self.last.get(ft[-1], ())) == 1 and m.group(0)[0].isupper():
                    out.append((m.start(), u, u, m.group(0)))
        for m in re.finditer(r"\b[A-Z][\w'\-]+(?: [A-Z][\w'\-]+){1,2}", plain):
            g = self.gidx.get(" ".join(_wtoks(m.group(0))))
            if g and not any(abs(m.start() - o[0]) < 3 for o in out):
                out.append((m.start(), self.match(m.group(0)), g, m.group(0)))
        out.sort()
        return out


def _background(t):
    m = re.search(r"==\s*Background\s*==", t)
    if not m:
        return ""
    j = len(t)
    for h in (r"==\s*Results", r"==\s*Fight card", r"==\s*Bonus", r"==\s*Announced"):
        k = re.compile(h).search(t, m.end())
        if k and k.start() < j:
            j = k.start()
    return t[m.start():j]


def _sentences(b):
    """sentences with each ref turned into a date token, None at a paragraph break"""
    def rep(m):
        d = re.search(r"\|\s*date\s*=\s*(\d{4}-\d{2}-\d{2})", m.group(0))
        return " ⟦%s⟧ " % (d.group(1) if d else "")
    b = _REF.sub(rep, b)
    b = re.sub(r"\.((?:\s*⟦[^⟧]*⟧)+)", r"\1.", b)    # a ref after the stop belongs to the sentence before
    for _ in range(2):
        b = re.sub(r"\{\{[^{}]*\}\}", "", b)
    b = re.sub(r"'''?", "", b)
    out = []
    for para in re.split(r"\n\s*\n|\n\*|\n=+", b):
        p = re.sub(r"\b(vs|Jr|Sr|St|Dr|Mt|U\.S|No)\.", lambda m: m.group(0).replace(".", "․"), para.replace("\n", " "))
        out += [s.replace("․", ".") for s in re.split(r"(?<=\.)\s+(?=[A-Z\[⟦\"'])", p) if s.strip()]
        out.append(None)
    return out


def _notice_days(s):
    m = re.search(r"(\w+|\d+)[- ](day|week)s?(?:'s|s')?[- ]notice", s, re.I)
    if m:
        n = int(m.group(1)) if m.group(1).isdigit() else _NUMW.get(m.group(1).lower())
        if n:
            return n * (7 if m.group(2).lower() == "week" else 1)
    m = re.search(r"(?:less than|under|just|only) (\w+) (day|week)s?", s, re.I)
    if m and re.search(r"notice|replace|step", s, re.I):
        n = _NUMW.get(m.group(1).lower()) or (int(m.group(1)) if m.group(1).isdigit() else None)
        if n:
            return n * (7 if m.group(2).lower() == "week" else 1)
    return None


def _text_date(s, ev):
    """'on November 25' -> a date in the card's year (the year before when that is after the card)"""
    m = re.search(r"\b(January|February|March|April|May|June|July|August|September|October|November|December) (\d{1,2})\b"
                  r"(?!,? \d{4}\s*\])", s)
    if not m:
        return None
    try:
        d = dt.date(ev.year, _MON[m.group(1).lower()], int(m.group(2)))
    except ValueError:
        return None
    return dt.date(ev.year - 1, d.month, d.day) if d > ev else d


def wiki_fight_card(t):
    """the page's {{MMAevent bout}} rows: (weight class, name, name, title bout)"""
    out = []
    for chunk in t.split("{{MMAevent bout")[1:]:
        chunk = _REF.sub("", chunk.split("\n}}")[0].split("}}\n")[0])
        ps = [_DELINK.sub(r"\1", p).strip() for p in chunk.split("\n|")]
        if len(ps) >= 5 and ps[3].lower().rstrip(".") in ("vs", "def"):
            title = any(re.search(r"\((?:c|ic)\)", p) for p in ps[2:5:2])
            out.append((ps[1], re.sub(r"\((?:c|ic)\)", "", ps[2]).strip(), re.sub(r"\((?:c|ic)\)", "", ps[4]).strip(), title))
    return out


def wiki_facts(t, day, bouts, gidx):
    """facts per man from one event page.
       bouts: [(a_url, [a's names], b_url, [b's names], weight class, title bout)]
       -> {url: {replacement, rebook, notice_days, short_words, newcomer, missed_weight, lbs_over}}"""
    men = {}
    bout_of = {}
    for au, an, bu, bn, wc, title in bouts:
        men.setdefault(au, list(an))
        men.setdefault(bu, list(bn))
        bout_of[au] = bout_of[bu] = [wc, title]
    # the page's own spellings, tied by the pair: one man's surname and any of the other's names
    for wwc, w1, w2, wt in wiki_fight_card(t):
        t1, t2 = set(_wtoks(w1)), set(_wtoks(w2))
        for au, an, bu, bn, wc, title in bouts:
            ta = {x for n in an for x in _wtoks(n)}
            tb = {x for n in bn for x in _wtoks(n)}
            for (x1, x2, n1, n2) in ((t1, t2, w1, w2), (t2, t1, w2, w1)):
                if x1 & ta and x2 & tb and (_wtoks(n1)[-1] in ta or _wtoks(n2)[-1] in tb):
                    men[au].append(n1)
                    men[bu].append(n2)
                    if wc_limit(wc) is None:    # after a miss the page writes 'Catchweight (139.75 lb)'
                        bout_of[au][0] = wwc
                    bout_of[au][1] = title or wt
    card = WikiCard(men, gidx)
    side = {}
    lastsubj = None
    for s in _sentences(_background(t)):
        if s is None:
            lastsubj = None
            continue
        ms = card.mentions(s)
        clean = re.sub(r"⟦[^⟧]*⟧", "", s)
        rd = [dt.date.fromisoformat(x) for x in re.findall(r"⟦(\d{4}-\d{2}-\d{2})⟧", s)]
        when = _text_date(clean, day) or (min(rd) if rd else None)
        oncard = [m for m in ms if m[1]]
        # who stepped in
        repl = None
        mby = _REPL_BY.search(s)
        if mby:
            after = [m for m in ms if m[0] >= mby.end() - 1]
            if after:
                repl = after[0]
                if re.search(r"instead|will now face|would now face|to face", mby.group(0), re.I):
                    repl = ("rebook",) + repl[1:]
        msub = _REPL_SUBJ.search(s)
        if not repl and msub:
            before = [m for m in ms if m[0] < msub.start()]
            if before:
                repl = before[-1]
        if repl and repl[1]:
            d = side.setdefault(repl[1], {})
            kind = "rebook" if repl[0] == "rebook" else "replacement"
            if kind == "replacement" or d.get("role") != "replacement":
                d["role"] = kind
            if when:
                d["repl_date"] = when
            nd = _notice_days(clean)
            if nd:
                d["notice_text"] = nd
            if _SHORT.search(clean):
                d["short_words"] = True
            if _NEWC.search(clean):
                d["newcomer"] = True
        # who missed weight
        if _MISS.search(clean) or re.search(r"\bover the\b.*\blimit", clean):
            missers = []
            mpos = _MISS.search(s)
            if mpos:
                before = [m for m in oncard if m[0] < mpos.start()]
                if re.search(r"missed|failed", mpos.group(0)) and before:
                    missers = before[-4:] if re.search(r",| and ", s[before[0][0]:mpos.start()]) else before[-1:]
                elif before:
                    missers = before[-1:]
            for m in re.finditer(r"weighed in at|came in at|tipped the scales at", s):
                before = [x for x in oncard if x[0] < m.start()]
                if before and before[-1] not in missers:
                    missers.append(before[-1])
            if not missers and re.match(r"\s*(He|She)\b", clean) and lastsubj and lastsubj[1]:
                missers = [lastsubj]
            for x in missers:
                u = x[1]
                wc, title = bout_of.get(u, ("", False))
                lim = wc_limit(wc, title)
                seg = _DELINK.sub(r"\1", s[x[0]:])
                seg = re.sub(r"⟦[^⟧]*⟧", "", seg)[:260]
                # the sentence's own 'over the bantamweight non-title fight limit' outranks the card:
                # the first class named after 'over' ('one pound over the lightweight and three
                # pounds over the flyweight non-title fights limit respectively')
                ml = re.search(r"\bover the ((?:women's )?(?:light heavyweight|heavyweight|flyweight|bantamweight|featherweight|"
                               r"lightweight|welterweight|middleweight|strawweight))(\s+(?:non-)?title)?", seg, re.I)
                if ml:
                    t2 = (ml.group(2) or "").strip().lower()
                    lims = [wc_limit(ml.group(1), (t2 == "title") if t2 else title), lim]
                else:
                    lims = [lim]
                w = None
                mm = re.search(r"(?:weighed in at|weighing in at|coming in at|came in at|tipped the scales at|weighed)\s*"
                               r"(\d{3}(?:\.\d+)?)", seg)
                ws = [float(mm.group(1))] if mm else [float(v) for v in re.findall(r"(\d{3}(?:\.\d+)?)\s*(?:pounds|lb|lbs)\b", seg)]
                # the first limit the weight is over (a 'respectively' sentence names two classes)
                lim, w = next(((li, v) for li in lims if li for v in ws if li < v < li + 15), (None, None))
                mo = re.search(r"(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|half a|a half|a quarter|a)"
                               r"( and a half| and a quarter)? (?:pounds?|lbs?) over", seg)
                d = side.setdefault(u, {})
                d["missed"] = True
                if w and lim and lim < w < lim + 15:
                    d["lbs"] = round(w - lim, 2)
                elif mo:
                    v = {"half a": .5, "a half": .5, "a quarter": .25, "a": 1}.get(mo.group(1))
                    if v is None:
                        v = float(mo.group(1)) if mo.group(1)[0].isdigit() else _NUMW.get(mo.group(1))
                    if v is not None:
                        d["lbs"] = v + (.5 if mo.group(2) == " and a half" else .25 if mo.group(2) else 0)
        if oncard:
            lastsubj = oncard[0]
        elif ms:
            lastsubj = ms[0]
    out = {}
    for u in men:
        v = side.get(u, {})
        nd = v.get("notice_text")
        if nd is None and v.get("repl_date"):
            nd = (day - v["repl_date"]).days
        out[u] = dict(replacement=v.get("role") == "replacement", rebook=v.get("role") == "rebook",
                      notice_days=nd if v.get("role") else None, short_words=bool(v.get("short_words")),
                      newcomer=bool(v.get("newcomer")), missed_weight=bool(v.get("missed")), lbs_over=v.get("lbs"))
    return out


def wiki_api(params, tries=4):
    """one MediaWiki API call, polite: our user agent, maxlag, backing off on 429 / 5xx"""
    q = dict(params, format="json", formatversion=2, maxlag=5)
    last = None
    for i in range(tries):
        wait = 2 ** i
        try:
            r = _rq.get(WIKI_API, params=q, headers={"User-Agent": WIKI_UA, "Accept": "application/json"}, timeout=20)
            if r.status_code == 200 and r.text.lstrip().startswith("{"):
                j = r.json()
                if (j.get("error") or {}).get("code") != "maxlag":
                    return j
            last = r.status_code
            ra = r.headers.get("Retry-After")
            if ra and ra.isdigit():
                wait = int(ra)
        except Exception as e:
            last = e
        time.sleep(min(wait, 10))
    raise RuntimeError("wikipedia: %s" % last)


def _wiki_pages(titles):
    j = wiki_api(dict(action="query", prop="revisions", rvprop="content|ids|timestamp", rvslots="main", redirects=1,
                      titles="|".join(titles)))
    out = []
    for p in (j.get("query") or {}).get("pages", []):
        if p.get("revisions"):
            rv = p["revisions"][0]
            out.append(dict(title=p["title"], revid=rv.get("revid"), edited=rv.get("timestamp"), wikitext=rv["slots"]["main"]["content"]))
    return out


def _card_fit(t, surnames, day):
    """how well a page fits the card: the share of the card's surnames on it, 0 if the date is not"""
    if str(day.year) not in t:
        return 0.0
    low = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return sum(1 for s in surnames if s and s in low) / max(len(surnames), 1)


def wiki_card_facts(card, us, got, h, dry=False):
    """fight-week facts per UFC Stats fighter url for the card, from its Wikipedia
       page (cached; reread every run from 7 days out until the card starts)"""
    day = dt.date.fromisoformat(us["date"])
    fn = os.path.join(HIST, "wiki_%s_%s.json" % (us["date"], re.sub(r"[^A-Za-z0-9]+", "_", us["name"]).strip("_")))
    cache = None
    try:
        cache = json.load(open(fn))
    except Exception:
        pass
    surnames = [_ln(n) for _, r in got.values() for _, n in r["men"]]
    due = cache is None or (card["start"] - WIKI_FROM <= NOW < card["start"])
    page = cache
    if due and _rq is not None:
        try:
            tried = [cache["title"]] if cache else []
            tried += [us["name"], us["name"].split(":")[0]] if re.match(r"UFC \d+:", us["name"]) else [us["name"]]
            pages = _wiki_pages(list(dict.fromkeys(tried)))
            best = max(pages, key=lambda p: _card_fit(p["wikitext"], surnames, day), default=None)
            if not best or _card_fit(best["wikitext"], surnames, day) < 0.5:
                hits = []
                for q in (us["name"], "UFC %s %d, %d" % (day.strftime("%B"), day.day, day.year)):
                    j = wiki_api(dict(action="query", list="search", srsearch=q, srlimit=5, srnamespace=0))
                    hits += [x["title"] for x in (j.get("query") or {}).get("search", [])]
                if hits:
                    pages = _wiki_pages(list(dict.fromkeys(hits))[:10])
                    best = max(pages, key=lambda p: _card_fit(p["wikitext"], surnames, day), default=None)
            if best and _card_fit(best["wikitext"], surnames, day) >= 0.5:
                page = dict(best, card=us["date"], event=us["name"], fetched=NOW.isoformat(timespec="seconds"))
            else:
                print("  wikipedia: no page fits %s %s" % (us["date"], us["name"]))
        except Exception as e:
            print("  wikipedia failed (%s); %s" % (e, "using the cached page" if cache else "no fight-week facts"))
    if not page:
        return {}, None
    fighters = h["fighters"].drop_duplicates("fighter_url", keep="last")
    gidx = {}
    for u, n in zip(fighters.fighter_url, fighters.name):
        k = " ".join(_wtoks(n))
        gidx[k] = None if k in gidx and gidx[k] != u else u
    gidx = {k: v for k, v in gidx.items() if v}
    bouts = []
    for f, r in got.values():
        if len(r["men"]) != 2:
            continue
        board = {_ln(f[3]): f[3], _ln(f[5]): f[5]}
        (au, an), (bu, bn) = r["men"]
        bouts.append((au, [an] + [board[_ln(an)]] * (_ln(an) in board), bu, [bn] + [board[_ln(bn)]] * (_ln(bn) in board),
                      r.get("weight_class", ""), "title" in str(r.get("weight_class", "")).lower()))
    facts = wiki_facts(page["wikitext"], day, bouts, gidx)
    if not dry and page is not cache:
        page["facts"] = {u: dict(v, name=next((n for b in bouts for x, n in ((b[0], b[1][0]), (b[2], b[3][0])) if x == u), ""))
                         for u, v in facts.items() if v["replacement"] or v["rebook"] or v["missed_weight"]}
        json.dump(page, open(fn, "w"), indent=1, ensure_ascii=False)
    return facts, page


def ufc_events_before(h, u, d):
    """his UFC event bouts before the day (UFC Stats' event pages; the Contender Series is not one)"""
    F = h["fights"]
    return int(((F.event_date < str(d)[:10]) & ((F.red_url == u) | (F.blue_url == u))).sum())


def fact_lines(name, v):
    """a man's fight-week facts, said plainly; [] when there are none"""
    if not v:
        return []
    sur = _sur(name)
    out = []
    if v.get("replacement") or v.get("rebook"):
        nd = v.get("notice_days")
        s = ("%s took the fight on %d days' notice" % (sur, nd)) if nd is not None and nd >= 0 else \
            ("%s took the fight on short notice" % sur) if v.get("short_words") else "%s stepped in as a replacement" % sur
        if v.get("debut"):
            s += ", his UFC debut"
        out.append(s)
    if v.get("missed_weight"):
        out.append(("%s missed weight by %g lb" % (sur, v["lbs_over"])) if v.get("lbs_over") else "%s missed weight" % sur)
    return out


def fw_flag(v):
    """the tested fight-week flag: a replacement on 14 days' notice or less (or written as short
       notice), a short-notice UFC debut, or a missed weight"""
    if not v:
        return False
    stepped = v.get("replacement") or v.get("rebook")
    nd = v.get("notice_days")
    short14 = bool(stepped and ((nd is not None and nd <= 14) or v.get("short_words")))
    return short14 or bool(v.get("short_notice_debut")) or bool(v.get("missed_weight"))


# ---------------------------------------------------------------- the board's card
def board_fights():
    import pagefile
    s = pagefile.read()
    return json.loads(re.search(r"var FIGHTS = (\[\[.*?\]\]);", s, re.S).group(1))


def T(x):
    return dt.datetime.fromisoformat(x.replace("Z", "+00:00"))


def cards(fights):
    kicks = {}
    try:
        kicks = json.load(open(os.path.join(D, "site", "prices.json"))).get("KICKS") or {}
    except Exception:
        pass
    ev = {}
    for f in fights:
        if re.search(r"\bTBA\b|TBD", f[3] + " " + f[5]):
            continue
        t = T(kicks.get(str(f[1])) or f[2])
        ev.setdefault(f[0], []).append((f, min(t, T(f[2]))))
    out = []
    for e, rows in ev.items():
        out.append(dict(event=e, rows=[r for r, _ in rows], start=min(t for _, t in rows), end=max(t for _, t in rows)))
    return sorted(out, key=lambda c: c["start"])


def match_card(card, us_events):
    """the UFC Stats event on the same day (a day either way) whose bouts carry the
       same two last names; a bout must match both men or it is left unread"""
    day = card["start"].date()
    for eu, en, ed in us_events:
        if abs((dt.date.fromisoformat(ed) - day).days) > 1:
            continue
        rows = event_rows(get(eu))
        pairs = {}
        for r in rows:
            if len(r["men"]) == 2:
                pairs[frozenset((_ln(r["men"][0][1]), _ln(r["men"][1][1])))] = r
        got = {}
        for f in card["rows"]:
            r = pairs.get(frozenset((_ln(f[3]), _ln(f[5]))))
            if r:
                got[str(f[1])] = (f, r)
        if got:
            return dict(url=eu, name=en, date=ed), got
    return None, {}


def resolve_pro(h, fe, urls, names):
    """a man with no gidstats page under his UFC Stats id: the pull's own row by the
       same name (one only, or the one who has fought his UFC opponents), else his
       gidstats page fetched by name and kept in data/ufc_hist/"""
    import gidstats
    P = fe.P
    added = False
    for u in urls:
        if u in fe.page or u in h["pro_map"]:
            continue
        nm = names.get(u, "")
        c = P[(P.name.map(_nz) == _nz(nm)) | (P.page_name.astype(str).map(_nz) == _nz(nm))]
        c = c[c.page_url.isin(fe.PG.keys())].drop_duplicates("page_url")
        if len(c) > 1:
            hu = fe.Hg.get(u)
            opps = set() if hu is None else {_ln(x) for x in h["history"][h["history"].fighter_url == u].opponent_url.map(
                lambda x: names.get(x, ""))}
            c = c[[len({_ln(o) for o in fe.FS[fe.FS.page_url == pu].opponent.astype(str)} & opps) > 0 for pu in c.page_url]]
        if len(c) == 1:
            r = c.iloc[0]
            h["pro_map"][u] = dict(page=r["page_url"], asof=r["asof"] if isinstance(r["asof"], str) else NOW.date().isoformat(),
                                   name=nm, by="name")
            added = True
            continue
        if len(c) > 1:
            continue
        slug = _nz(nm).replace(" ", "_")
        url = "https://gidstats.com/fighters/%s.html" % slug
        try:
            rr = _rq.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
        except Exception:
            continue
        if rr.status_code != 200:
            continue
        pg = gidstats.parse_gid(rr.text)
        if _nz(pg.get("name")) != _nz(nm) or not pg.get("fights"):
            continue
        xp = os.path.join(HIST, "pro_extra.csv")
        new = not os.path.exists(xp)
        with open(xp, "a", newline="") as f:
            w = csv.DictWriter(f, gidstats.FCOLS)
            if new:
                w.writeheader()
            for x in sorted(pg["fights"], key=lambda f: f["date"]):
                w.writerow(dict(page_url=url, source="gidstats", fighter=pg["name"], **x))
        h["pro_map"][u] = dict(page=url, asof=NOW.date().isoformat(), name=nm, by="gidstats page")
        added = True
    return added


def score_card(h, M, card, got, d, facts=None, DM=None, rounds=None):
    """every matched bout on the card, point in time at the card's date; facts are
       wiki_card_facts()' per-man fight-week facts, carried onto each side; with the
       distance model DM, each bout's P(goes the distance) too (rounds: bout id ->
       scheduled rounds)"""
    facts = facts or {}
    rounds = rounds or {}
    need = set()
    names = {}
    for _, r in got.values():
        for u, n in r["men"]:
            names[u] = n
            need.add(u)
    have = h["fighters"].set_index("fighter_url")
    miss = [u for u in need if u not in have.index or
            (not isinstance(have.loc[u].dob, str) and have.loc[u].checked != NOW.date().isoformat())]
    if miss:
        print("  fighter pages: %d" % fetch_fighters(h, miss))
    fe = Feats(h)
    allnames = dict(zip(h["fights"].red_url, h["fights"].red_name)) | dict(zip(h["fights"].blue_url, h["fights"].blue_name)) | names
    if resolve_pro(h, fe, sorted(need), allnames):
        fe = Feats(h)
    rows, keys = [], []
    for bid, (f, r) in got.items():
        (au, an), (bu, bn) = r["men"]
        rows.append(fe.row(pd.Timestamp(d), au, bu, event=card.get("name", ""), wc=r["weight_class"], a=an, b=bn))
        keys.append((bid, f))
    X = pd.DataFrame(rows)
    Z, FE = zmat(M, X)
    p = sym_p(M, Z)
    pdist, push = [None] * len(X), [None] * len(X)
    if DM is not None and len(X):
        first = next(iter(got), None)
        X["scheduled_rounds"] = [rounds.get(bid) or (5 if bid == first or "title" in str(r["weight_class"]).lower() else 3)
                                 for bid, (f, r) in got.items()]
        X["title_bout"] = ["true" if "title" in str(r["weight_class"]).lower() else "false" for f, r in got.values()]
        FA, FB, S = dist_tables(h, X, fe, cache=False)
        pdist, push = dist_p(DM, FA, FB, S)
        X = pd.concat([X, extras(fe, X)], axis=1)
    out = []
    for i, (bid, f) in enumerate(keys):
        r = X.iloc[i]
        s = "a" if p[i] > 0.5 else "b"
        o = "b" if s == "a" else "a"
        conf = max(p[i], 1 - p[i])
        # the board's own spelling and ESPN id for the pick
        bs = {_ln(f[3]): (f[3], f[4]), _ln(f[5]): (f[5], f[6])}
        pk = bs.get(_ln(r[s]), (r[s], ""))
        vs = bs.get(_ln(r[o]), (r[o], ""))
        fw = {}
        for k in (s, o):
            v = dict(facts.get(r[k + "_url"]) or {})
            if v:
                v["debut"] = ufc_events_before(h, r[k + "_url"], d) == 0
                v["short_notice_debut"] = bool(v.get("replacement") and v["debut"])
            fw[k] = v
        out.append(dict(bid=bid, pick=pk[0], id=str(pk[1]), vs=vs[0], conf=float(conf), p_a=float(p[i]), a=r.a, b=r.b,
                        wc=r.wc, why=why(r, s, M, Z[i], FE.iloc[i]), row=r, own=fw[s], opp=fw[o],
                        pdist=None if pdist[i] is None else float(pdist[i]), push=push[i], f=f))
    return sorted(out, key=lambda x: -x["conf"])


def call_price(book, x, c):
    """DraftKings' price for the call's side from site/prices.json, if posted"""
    bid, f = x["bid"], x.get("f")
    try:
        if c["market"] == "Moneyline":
            row = (book.get("FIGHTS") or {}).get(bid)
            if row and f:
                return row[0] if _ln(f[3]) == _ln(x["pick"]) else row[2] if _ln(f[5]) == _ln(x["pick"]) else None
        else:
            v = ((book.get("FPROPS") or {}).get(bid) or {}).get("dist" if c["sel"] == "Yes" else "nodist") or [None]
            return v[0][0] if v[0] else None
    except Exception:
        return None
    return None


def picks_json(card, us, scored, M, DM=None, book=None):
    picks, allb = {}, {}
    rank = 0
    for x in scored:
        pct = int(round(100 * x["conf"]))
        allb[x["bid"]] = dict(pick=x["pick"], vs=x["vs"], p=pct, women=bool(women_row(x["row"])))
        won = next((w for t, w in TIERS if x["conf"] >= t), None)
        # every bout is scored, but only men's bouts are picks (Jose, Oct 12,
        # 2026: "it can read everything but don't tell me about women's fights").
        # Every card gets its top three men's bouts as tickets; only a 75%+ one
        # carries the tested rate, the rest say they are under the cutoff
        # (Jose, Oct 12, 2026: "what is the purpose if we're not getting picks")
        # every men's bout gets a winner (Jose, Oct 12, 2026: "for each one we
        # should have a decision, winner and loser")
        if women_row(x["row"]):
            continue
        rank += 1
        # fight-week facts (Oct 12, 2026): said on every pick, whatever the %; a 70-74%
        # pick whose opponent carries the flag and who carries none himself is tier 2
        own, opp = fact_lines(x["pick"], x["own"]), fact_lines(x["vs"], x["opp"])
        opp_flag = fw_flag(x["opp"]) and not fw_flag(x["own"])
        tier2 = won is None and opp_flag and x["conf"] >= TIER2[0]
        why_ = (opp + x["why"] + own) if tier2 else (x["why"] + own + opp)
        picks[x["bid"]] = dict(rank=rank, pick=x["pick"], vs=x["vs"], box=[pct, 100 - pct], p=pct,
                               won=TIER2[1] if tier2 else won, why=why_, id=x["id"],
                               own_facts="; ".join(own), opp_facts="; ".join(opp), opp_flag=bool(opp_flag))
        if tier2:
            picks[x["bid"]]["flag"] = "tier2"
        # the call (Oct 12, 2026): the likeliest side on the bout sheet, the moneyline
        # favorite or a side of Fight to Go the Distance, with its blind hit rate
        if x.get("pdist") is not None:
            c = make_call(dict(x, why=why_), x["pdist"], x["push"], DM["cols_s"])
            pr = call_price(book or {}, x, c)
            if pr:
                c["price"] = pr         # information only: never in the model
            picks[x["bid"]]["call"] = c
    out = {"at": NOW.date().isoformat(), "card": us["date"], "event": card["event"], "name": us["name"],
           "model": M["last_bout"], "picks": picks, "all": allb}
    if DM is not None:
        out["dist_model"] = DM["last_bout"]
    return out


# ---------------------------------------------------------------- the log
LOGCOLS = ["card_date", "bout_id", "rank", "pick", "vs", "boxes_pick", "boxes_vs", "lead", "hist_win_pct", "result", "method",
           "model_pct", "flag", "facts"]       # flag: the opponent's fight-week flag (1/0); facts: both men's, in words


def read_log():
    if not os.path.exists(LOG):
        return []
    return [dict({k: "" for k in LOGCOLS}, **{k: (v or "") for k, v in r.items() if k}) for r in csv.DictReader(open(LOG))]


def write_log(rows):
    with open(LOG, "w", newline="") as f:
        w = csv.DictWriter(f, LOGCOLS)
        w.writeheader()
        w.writerows(rows)


def log_card(bp):
    rows = read_log()
    if any(r["card_date"] == bp["card"] for r in rows):
        return 0
    n = 0
    for bid, p in sorted(bp["picks"].items(), key=lambda kv: kv[1]["rank"]):
        rows.append(dict({k: "" for k in LOGCOLS}, card_date=bp["card"], bout_id=bid, rank=p["rank"], pick=p["pick"], vs=p["vs"],
                         hist_win_pct=p["won"], model_pct=p.get("p", ""),
                         flag=int(bool(p.get("opp_flag"))) if "opp_flag" in p else "",
                         facts=" | ".join(x for x in (p.get("own_facts"), p.get("opp_facts")) if x)))
        n += 1
    # every other men's bout too, unranked, so a card with no pick still grades
    # the model: do the 60s win about 60%, the 70s about 70% (Jose, Oct 12,
    # 2026: "how will I know if it's true. Just miss the entire card")
    for bid, a in sorted((bp.get("all") or {}).items(), key=lambda kv: -kv[1]["p"]):
        if bid in bp["picks"] or a.get("women"):
            continue
        rows.append(dict({k: "" for k in LOGCOLS}, card_date=bp["card"], bout_id=bid, pick=a["pick"], vs=a["vs"], model_pct=a["p"]))
        n += 1
    write_log(rows)
    return n


def fill_results(fights):
    rows = read_log()
    ev = {str(f[1]): (f[0], f) for f in fights}
    n = 0
    for r in rows:
        if r["result"] or r["bout_id"] not in ev:
            continue
        e, f = ev[r["bout_id"]]
        try:
            c = get_json("https://sports.core.api.espn.com/v2/sports/mma/leagues/ufc/events/%s/competitions/%s" % (e, r["bout_id"]))
            st = get_json(c["status"]["$ref"])
        except Exception:
            continue
        if not (st.get("type") or {}).get("completed"):
            continue
        pid = f[4] if _ln(f[3]) == _ln(r["pick"]) else f[6] if _ln(f[5]) == _ln(r["pick"]) else None
        win = [str(x.get("id")) for x in c.get("competitors", []) if x.get("winner")]
        if not win:
            r["result"] = "D/NC"
        elif pid is None:
            continue
        else:
            r["result"] = "W" if str(pid) in win else "L"
        r["method"] = ((st.get("result") or {}).get("displayName")) or (st.get("type") or {}).get("description", "")
        n += 1
    if n:
        write_log(rows)
    return n


# ---------------------------------------------------------------- main
def load_model():
    return json.load(open(MODEL))


def maybe_refit(h, M, before):
    """refit when scikit-learn is here and UFC Stats has decided bouts newer than the model"""
    try:
        import sklearn  # noqa: F401
    except Exception:
        return M
    X = h["bouts"]
    newest = X.date[train_mask(X, before)].max()
    if pd.Timestamp(M["last_bout"]) >= newest:
        return M
    return fit(h, before, MODEL)


def load_dist():
    try:
        return json.load(open(DMODEL))
    except Exception:
        return None


def maybe_refit_dist(h, DM, before):
    """refit the distance model when scikit-learn is here and there are decided bouts newer than it"""
    try:
        import sklearn  # noqa: F401
    except Exception:
        return DM
    X = h["bouts"]
    newest = X.date[train_mask(X, before) & X.method.map(mclass).notna().values].max()
    if DM is not None and pd.Timestamp(DM["last_bout"]) >= newest:
        return DM
    try:
        return fit_dist(h, before, DMODEL)
    except Exception as e:
        print("  distance model refit failed (%s); %s" % (e, "keeping the committed one" if DM else "no calls"))
        return DM


def append_bouts(h, added):
    if not added:
        return
    fe = Feats(h)
    urls = [u for a in added for u in a[3]]
    F = h["fights"][h["fights"].fight_url.isin(urls)]
    B = bout_rows(h, fe, F)
    h["bouts"] = pd.concat([h["bouts"][~h["bouts"].fight_url.isin(B.fight_url)], B], ignore_index=True)
    print("  bouts table: +%d (%d)" % (len(B), len(h["bouts"])))


def replay(day):
    """a past card scored point in time: the model fit on everything before it
       (scikit-learn needed), the card's rows from the bouts table"""
    h = load_hist()
    out = os.path.join(D, "research", "ufc_reads", "model_before_%s.json" % day)
    M = fit(h, day, out)
    X = h["bouts"]
    X = X[X.date == pd.Timestamp(day)].reset_index(drop=True)
    Z, FE = zmat(M, X)
    p = sym_p(M, Z)
    hit = {t: [0, 0] for t, _ in TIERS}
    print("\n%s  %s" % (day, X.event.iloc[0] if len(X) else ""))
    order = np.argsort(-np.maximum(p, 1 - p))
    for i in order:
        r = X.iloc[i]
        s = "a" if p[i] > 0.5 else "b"
        conf = max(p[i], 1 - p[i])
        res = "W" if (r.winner == "red") == (s == "a") and r.winner in ("red", "blue") else ("L" if r.winner in ("red", "blue") else r.winner)
        tier = next((t for t, _ in TIERS if conf >= t), None)
        if tier is not None and res in ("W", "L"):
            hit[tier][0] += res == "W"
            hit[tier][1] += 1
        print("%3.0f%%  %-24s over %-24s %-4s %-8s %s" % (100 * conf, r[s], r["b" if s == "a" else "a"], res, r.method,
                                                          "; ".join(why(r, s, M, Z[i], FE.iloc[i])[:3])))
    print("tiers:", {("%.0f%%+" % (100 * t)): "%d-%d" % (w, n - w) for t, (w, n) in hit.items()})


def main():
    a = sys.argv[1:]
    if "--fit" in a:
        h = load_hist()
        before = a[a.index("--before") + 1] if "--before" in a else (NOW.date() + dt.timedelta(days=1)).isoformat()
        out = a[a.index("--out") + 1] if "--out" in a else MODEL
        fit(h, before, out)
        return 0
    if "--fit-dist" in a:
        h = load_hist()
        before = a[a.index("--before") + 1] if "--before" in a else (NOW.date() + dt.timedelta(days=1)).isoformat()
        out = a[a.index("--out") + 1] if "--out" in a else DMODEL
        fit_dist(h, before, out)
        return 0
    if "--replay" in a:
        replay(a[a.index("--replay") + 1])
        return 0
    dry = "--dry" in a
    t0 = time.time()
    h = load_hist()
    fights = board_fights()
    if "--no-crawl" not in a:
        try:
            added = crawl(h)
        except Exception as e:
            print("UFC Stats crawl failed:", e)
            added = []
        append_bouts(h, added)
    # results for logged picks, then the card
    if not dry:
        n = fill_results(fights)
        if n:
            print("log: %d results filled" % n)
    held = {}
    try:
        held = json.load(open(OUT))
    except Exception:
        pass
    cur = [c for c in cards(fights) if c["end"] + LIVE_FOR > NOW]
    try:
        up = event_list("upcoming")
    except Exception as e:
        print("UFC Stats upcoming list failed:", e)
        up = []
    recent = []
    if cur and cur[0]["start"] <= NOW:
        try:
            recent = event_list("completed")[:3]
        except Exception:
            pass
    card = us = None
    got = {}
    for c in cur:
        us, got = match_card(c, up + recent)
        if us:
            card = c
            break
    if not card:
        print("ufc_reads: no UFC card on the board matches UFC Stats; boxpicks.json left as it is")
        if not dry:
            save_hist(h)
        return 0
    started = card["start"] <= NOW
    if started and held.get("card") == us["date"] and str(held.get("event", card["event"])) == str(card["event"]):
        print("ufc_reads: %s %s is under way; its picks stand" % (us["date"], us["name"]))
        if not dry:
            n = log_card(held)
            if n:
                print("log: %d picks for %s" % (n, us["date"]))
            save_hist(h)
        return 0
    M = load_model()
    if not dry:
        M = maybe_refit(h, M, us["date"])
    DM = load_dist()
    if not dry:
        DM = maybe_refit_dist(h, DM, us["date"])
    book = {}
    try:
        book = json.load(open(os.path.join(D, "site", "prices.json")))
    except Exception:
        pass
    rounds = {bid: ((book.get("FPROPS") or {}).get(bid) or {}).get("rounds") for bid in got}
    facts, wpage = wiki_card_facts(card, us, got, h, dry=dry)
    if wpage:
        n = sum(1 for v in facts.values() if v["replacement"] or v["rebook"] or v["missed_weight"])
        print("  wikipedia: %s (fetched %s): %d men with fight-week facts" % (wpage["title"], wpage.get("fetched", "")[:16], n))
    scored = score_card(h, M, card, got, us["date"], facts, DM, rounds)
    bp = picks_json(card, us, scored, M, DM, book)
    unread = [f for f in card["rows"] if str(f[1]) not in got]
    print("ufc_reads: %s %s, model through %s | %d bouts read, %d ranked%s | %.1fs" % (
        us["date"], us["name"], M["last_bout"], len(scored), len(bp["picks"]),
        ("; unread: " + ", ".join("%s v %s" % (f[3], f[5]) for f in unread)) if unread else "", time.time() - t0))
    for x in scored:
        pk = bp["picks"].get(x["bid"], {})
        rk = pk.get("rank")
        print("  %s %3.0f%%  %-24s over %-24s %s%s" % (("#%d" % rk) if rk else "  ", 100 * x["conf"], x["pick"], x["vs"],
                                                     "[TIER 2, won %s] " % pk["won"] if pk.get("flag") == "tier2" else "",
                                                     "; ".join(pk.get("why", [])) if rk else ""))
        c = pk.get("call")
        if c:
            print("        CALL %s: %s  %d%% (won %d%% blind, %d bouts)%s | %s" % (
                c["market"], c["side"], c["p"], c["won"], c["won_n"], (" DK " + c["price"]) if c.get("price") else "",
                "; ".join(c["why"])))
    if dry:
        return 0
    json.dump(bp, open(OUT, "w"), indent=1, ensure_ascii=False)
    if started:
        n = log_card(bp)
        if n:
            print("log: %d picks for %s" % (n, us["date"]))
    save_hist(h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
