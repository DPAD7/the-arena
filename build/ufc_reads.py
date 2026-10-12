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

   A card already under way keeps its picks. When it starts, its ranked picks
   are appended to data/boxpicks_log.csv; results are filled from ESPN after.

   Writes site/boxpicks.json:
     {"at", "card", "event", "name", "model",
      "picks": {espn bout id: {"rank", "pick", "vs", "box": [p, 100-p], "p",
                               "won", "why": [...], "id"}},
      "all":   {espn bout id: {"pick", "vs", "p"}}}

   Usage:  python3 build/ufc_reads.py            crawl, score, write
           python3 build/ufc_reads.py --dry      score and print, write nothing
           python3 build/ufc_reads.py --no-crawl skip UFC Stats' finished events
           python3 build/ufc_reads.py --fit [--before YYYY-MM-DD] [--out PATH]
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
TIERS = ((0.75, 84), (0.70, 74))       # model chance -> 2024-26 blind hit rate
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


def score_card(h, M, card, got, d):
    """every matched bout on the card, point in time at the card's date"""
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
        out.append(dict(bid=bid, pick=pk[0], id=str(pk[1]), vs=vs[0], conf=float(conf), p_a=float(p[i]), a=r.a, b=r.b,
                        wc=r.wc, why=why(r, s, M, Z[i], FE.iloc[i]), row=r))
    return sorted(out, key=lambda x: -x["conf"])


def picks_json(card, us, scored, M):
    picks, allb = {}, {}
    rank = 0
    for x in scored:
        pct = int(round(100 * x["conf"]))
        allb[x["bid"]] = dict(pick=x["pick"], vs=x["vs"], p=pct)
        won = next((w for t, w in TIERS if x["conf"] >= t), None)
        if won is None:
            continue
        rank += 1
        picks[x["bid"]] = dict(rank=rank, pick=x["pick"], vs=x["vs"], box=[pct, 100 - pct], p=pct, won=won,
                               why=x["why"], id=x["id"])
    return {"at": NOW.date().isoformat(), "card": us["date"], "event": card["event"], "name": us["name"],
            "model": M["last_bout"], "picks": picks, "all": allb}


# ---------------------------------------------------------------- the log
LOGCOLS = ["card_date", "bout_id", "rank", "pick", "vs", "boxes_pick", "boxes_vs", "lead", "hist_win_pct", "result", "method",
           "model_pct"]


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
                         hist_win_pct=p["won"], model_pct=p.get("p", "")))
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
    scored = score_card(h, M, card, got, us["date"])
    bp = picks_json(card, us, scored, M)
    unread = [f for f in card["rows"] if str(f[1]) not in got]
    print("ufc_reads: %s %s, model through %s | %d bouts read, %d ranked%s | %.1fs" % (
        us["date"], us["name"], M["last_bout"], len(scored), len(bp["picks"]),
        ("; unread: " + ", ".join("%s v %s" % (f[3], f[5]) for f in unread)) if unread else "", time.time() - t0))
    for x in scored:
        rk = bp["picks"].get(x["bid"], {}).get("rank")
        print("  %s %3.0f%%  %-24s over %-24s %s" % (("#%d" % rk) if rk else "  ", 100 * x["conf"], x["pick"], x["vs"],
                                                   "; ".join(x["why"]) if rk else ""))
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
