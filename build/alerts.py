"""What could sink a leg, per game, for the page to warn by when a leg is added.

   Grunkemeyer 2+ PTD went on a slip for a game in the rain with 31 mph gusts,
   and nothing said so (Jose, Sep 26, 2026: "anything else that would crush my
   parlay like the VT one"). ESPN's game summary carries all of it, read once a
   sweep for every game in the next eight days, into site/alerts.json:

     {game id: {
        "wx":     {"c": condition, "t": temp F, "g": gust mph, "p": precip %, "in": 1 if covered},
        "spread": the favorite's points, from ESPN's pickcenter,
        "total":  the game's over/under, the same place,
        "out":    [{"id", "name", "pos", "status", "team", "lead": "receiving" | "rushing" | ""}],
     }}

   The page reads the file; it never asks ESPN for this itself.

       python3 build/alerts.py
"""
import datetime as dt
import json
import os
import re
import sys

from curl_cffi import requests as rq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(D, "site", "alerts.json")
NOW = dt.datetime.now(dt.timezone.utc)
HURT = ("Out", "Doubtful", "Questionable", "Injured Reserve", "Suspension")
ROOF = {}
SHARE = 0.15     # of the club's targets and carries, or of its targets, to be worth a warning


def usage(rows, need):
    """Each man's share of his club's targets and carries this season, off
       ESPN's box score of every game the club has finished (targets in the
       NFL, catches in college, where ESPN writes no targets). Each game is
       read once and kept in data/usage.json; site/final keeps only the
       passers, so it cannot say this. A man hurt before he did anything is
       not news: Pacheco sat on the list all season without a snap (Jose,
       Sep 29, 2026: "he hasn't done anything"). Nor is one who has missed
       the club's last two games -- his passer's numbers already live
       without him.  need: {(club, league)}.
       {club: {id: {"g", "tg", "car", "sh", "recent"}}}"""
    path = os.path.join(D, "data", "usage.json")
    try:
        cache = json.load(open(path))
    except Exception:
        cache = {}
    use, grew = {}, False
    for ab, lg in need:
        gs = sorted((r for r in rows[lg] if ab in (r[3], r[4]) and
                     dt.datetime.fromisoformat(r[2].replace("Z", "+00:00")) < NOW - dt.timedelta(hours=4)),
                    key=lambda r: r[2])
        per = []
        for r in gs:
            gid = str(r[1])
            # [targets, carries, receiving yards, receiving TDs]; a game kept
            # before the yards were is read again
            old = next((m for men in (cache.get(gid) or {}).values() for m in men.values()), None)
            if gid not in cache or (old is not None and len(old) < 4):
                try:
                    d = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/%s/summary?event=%s" % (lg, gid),
                               impersonate="chrome124", timeout=20).json()
                except Exception:
                    continue
                box = {}
                for t in (d.get("boxscore") or {}).get("players") or []:
                    men = box.setdefault((t.get("team") or {}).get("abbreviation") or "", {})
                    for st in t.get("statistics") or []:
                        if st.get("name") not in ("receiving", "rushing"):
                            continue
                        lb = st.get("labels") or []
                        col = ("TGTS" if "TGTS" in lb else "REC") if st["name"] == "receiving" else "CAR"
                        if col not in lb:
                            continue
                        for x in st.get("athletes") or []:
                            v = x.get("stats") or []
                            num = lambda c: int(v[lb.index(c)]) if c in lb and lb.index(c) < len(v) and str(v[lb.index(c)]).lstrip("-").isdigit() else 0
                            m = men.setdefault(str((x.get("athlete") or {}).get("id")), [0, 0, 0, 0])
                            if st["name"] == "receiving":
                                m[0] += num(col); m[2] += num("YDS"); m[3] += num("TD")
                            else:
                                m[1] += num(col)
                if not box:
                    continue
                cache[gid] = box
                grew = True
            if ab in cache[gid]:
                per.append(cache[gid][ab])
        total = sum(m[0] + m[1] for men in per for m in men.values()) or 1
        tds = sum(m[3] for men in per for m in men.values())
        tgts = sum(m[0] for men in per for m in men.values()) or 1
        last = set(pid for men in per[-2:] for pid in men)
        club = use.setdefault(ab, {})
        for men in per:
            for pid, m in men.items():
                u = club.setdefault(pid, {"g": 0, "tg": 0, "car": 0, "ryd": 0, "rtd": 0, "tds": tds})
                u["g"] += 1; u["tg"] += m[0]; u["car"] += m[1]
                u["ryd"] += m[2] if len(m) > 2 else 0; u["rtd"] += m[3] if len(m) > 3 else 0
        for pid, u in club.items():
            u["sh"] = round((u["tg"] + u["car"]) / total, 3)
            u["tsh"] = round(u["tg"] / tgts, 3)
            u["recent"] = pid in last
    if grew:
        json.dump(cache, open(path, "w"), separators=(",", ":"), sort_keys=True)
    return use


STATE = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
         "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia",
         "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
         "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts",
         "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
         "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico",
         "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
         "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
         "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
         "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
GEOF = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "geo.json")


def load_geo():
    try:
        return json.load(open(GEOF))
    except (OSError, ValueError):
        return {}


def save_geo(g):
    json.dump(g, open(GEOF, "w"), indent=0, sort_keys=True)


def main():
    s = pagefile.read()
    games, rows = [], {}
    for var, lg in (("SCHED", "nfl"), ("CFB", "college-football")):
        m = re.search(r"  var %s = (\[\[.*?\]\]);" % var, s, re.S)
        rows[lg] = json.loads(m.group(1)) if m else []
        for r in rows[lg]:
            try:
                k = dt.datetime.fromisoformat(r[2].replace("Z", "+00:00"))
            except ValueError:
                continue
            if NOW - dt.timedelta(hours=5) < k < NOW + dt.timedelta(days=8):
                games.append((str(r[1]), lg, r[3], r[4]))
    out, hurts = {}, []
    # the NFL's whole report, every club and every man on it: a game's summary
    # stops at five a side, so Jalen Coker (Q) was never read (Jose, Sep 29,
    # 2026: "did you check that or did you just talk about it?")
    # college the same way: its game summaries carry no injuries at all
    league = {"nfl": {}, "college-football": {}}
    for lg0 in league:
        try:
            lj = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/%s/injuries" % lg0,
                        impersonate="chrome124", timeout=30).json()
            for t in lj.get("injuries") or []:
                for i in t.get("injuries") or []:
                    a = i.get("athlete") or {}
                    ab = ((a.get("team") or {}).get("abbreviation")) or ""
                    if not a.get("id"):
                        m = re.search(r"/id/(\d+)", json.dumps(a.get("links") or []))
                        a = dict(a, id=m.group(1) if m else None)
                    league[lg0].setdefault(ab, []).append(dict(i, athlete=a))
        except Exception:
            league[lg0] = {}
    GEO = load_geo()
    FCST = {}

    def hourly(v, d):
        """The stadium's worst hour of rain chance and wind (mph) from kickoff
           to three and a half hours on, off Open-Meteo's free forecast."""
        addr = v.get("address") or {}
        place = "%s, %s" % (addr.get("city") or "", addr.get("state") or "")
        if not addr.get("city"):
            return None
        if place not in GEO:
            try:
                g = rq.get("https://geocoding-api.open-meteo.com/v1/search", params={
                    "name": addr["city"], "count": 10, "country": "US"}, timeout=20).json().get("results") or []
                g = [x for x in g if not addr.get("state") or (x.get("admin1") or "").lower().startswith(STATE.get(addr["state"], addr["state"]).lower())] or g
                GEO[place] = [g[0]["latitude"], g[0]["longitude"]] if g else None
            except Exception:
                return None
            save_geo(GEO)
        ll = GEO.get(place)
        kick = ((d.get("header") or {}).get("competitions") or [{}])[0].get("date")
        if not ll or not kick:
            return None
        k = dt.datetime.fromisoformat(kick.replace("Z", "+00:00"))
        key = "%.3f,%.3f" % (ll[0], ll[1])
        f = FCST.get(key)
        # one forecast a stadium, asked again once if the service is busy
        for _try in range(3):
            if f:
                break
            try:
                r = rq.get("https://api.open-meteo.com/v1/forecast", params={
                    "latitude": ll[0], "longitude": ll[1], "hourly": "precipitation_probability,wind_speed_10m",
                    "wind_speed_unit": "mph", "timezone": "UTC", "forecast_days": 4}, timeout=20)
                if r.status_code == 200:
                    f = FCST[key] = r.json()["hourly"]
                else:
                    import time; time.sleep(2)
            except Exception:
                import time; time.sleep(2)
        if not f:
            return None
        rain, gust = [], []
        for t, pp, wg in zip(f["time"], f["precipitation_probability"], f["wind_speed_10m"]):
            at = dt.datetime.fromisoformat(t + "+00:00")
            if k - dt.timedelta(minutes=30) <= at <= k + dt.timedelta(hours=3, minutes=30):
                rain.append(pp or 0); gust.append(wg or 0)
        return (max(rain), round(max(gust))) if rain else None

    for gid, lg, away, home in games:
        try:
            d = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/%s/summary?event=%s" % (lg, gid),
                       impersonate="chrome124", timeout=20).json()
        except Exception:
            continue
        gi = d.get("gameInfo") or {}
        w, v = gi.get("weather") or {}, gi.get("venue") or {}
        # the summary can leave a roof blank (U.S. Bank Stadium read open air,
        # so a dome game warned of 20 mph gusts -- Sep 29, 2026); ESPN's own
        # venue record says so
        indoor = v.get("indoor")
        if indoor is None and v.get("id"):
            if v["id"] not in ROOF:
                try:
                    ROOF[v["id"]] = rq.get("https://sports.core.api.espn.com/v2/sports/football/leagues/%s/venues/%s"
                                           % ("nfl" if lg == "nfl" else "college-football", v["id"]),
                                           impersonate="chrome124", timeout=20).json().get("indoor")
                except Exception:
                    ROOF[v["id"]] = None
            indoor = ROOF[v["id"]]
        e = {"wx": {"c": w.get("conditionId"), "t": w.get("temperature"), "g": w.get("gust"),
                    "p": w.get("precipitation"), "in": 1 if indoor else 0}}
        # ESPN's figure is the day's chance for the whole area; the rain and
        # wind that matter are the stadium's, hour by hour, while the game is
        # played (Jose, Oct 3, 2026: a "rain likely 63%" for Starkville that an
        # hourly forecast had at 2-10% through the game)
        if not indoor:
            hw = hourly(v, d)
            if hw:
                e["wx"]["p"], e["wx"]["g"], e["wx"]["src"] = hw[0], hw[1], "hourly"
        pc = (d.get("pickcenter") or [{}])[0] or {}
        if pc.get("spread") is not None:
            e["spread"] = abs(float(pc["spread"]))
        if pc.get("overUnder") is not None:
            e["total"] = float(pc["overUnder"])
        # who leads each club in receiving and rushing
        lead = {}
        for t in d.get("leaders") or []:
            for cat in t.get("leaders") or []:
                if cat.get("name") in ("receivingYards", "rushingYards"):
                    for x in cat.get("leaders") or []:
                        lead[str((x.get("athlete") or {}).get("id"))] = "receiving" if cat["name"] == "receivingYards" else "rushing"
        hurt = []
        rep = d.get("injuries") or []
        if league[lg]:
            rep = [{"team": {"abbreviation": ab}, "injuries": league[lg].get(ab) or []} for ab in (away, home)]
        for t in rep:
            ab = ((t.get("team") or {}).get("abbreviation")) or ""
            for i in t.get("injuries") or []:
                a = i.get("athlete") or {}
                st = i.get("status") or ""
                pos = ((a.get("position") or {}).get("abbreviation")) or ""
                # every man on the report, both clubs, for the list under the
                # lineup (Jose, Sep 29, 2026: "a full list of the offense and
                # defensive injuries for team versus opponent")
                if st in HURT:
                    det0 = i.get("details") or {}
                    e.setdefault("inj", []).append({"n": a.get("displayName") or "", "p": pos, "s": st, "t": ab,
                                                    "w": det0.get("type") or "", "b": (det0.get("returnDate") or "")[:10]})
                if st not in HURT or pos not in ("QB", "WR", "TE", "RB"):
                    continue
                pid = str(a.get("id"))
                # what it is and when he is back, as ESPN has it: "Knee - ACL",
                # back 2027-02-15 is the season (Achane, Sep 28, 2026)
                det = i.get("details") or {}
                hurt.append({"id": pid, "name": a.get("displayName"), "pos": pos,
                             "status": st, "team": ab, "lead": lead.get(pid, ""), "lg": lg,
                             "why": det.get("type") or "", "back": (det.get("returnDate") or "")[:10]})
        if hurt:
            e["out"] = hurt
            hurts.extend(hurt)
        out[gid] = e
    use = usage(rows, set((x["team"], x["lg"]) for x in hurts if x["pos"] != "QB"))
    for e in out.values():
        keep = []
        for x in e.get("out") or []:
            lg = x.pop("lg")
            u = (use.get(x["team"]) or {}).get(x["id"])
            # a passer is judged on his own; anyone else has to matter now
            if x["pos"] != "QB" and not (u and u["recent"] and (u["sh"] >= SHARE or u["tsh"] >= SHARE or
                                                               (u["tds"] >= 2 and u["rtd"] * 4 >= u["tds"]))):
                continue
            if u and u["g"] and x["pos"] != "QB":
                x.update(sh=u["sh"], tsh=u["tsh"], tg=round(u["tg"] / u["g"], 1), car=round(u["car"] / u["g"], 1),
                         ryd=round(u["ryd"] / u["g"]), rtd=u["rtd"], tds=u["tds"],
                         tgw="targets" if lg == "nfl" else "catches")
            keep.append(x)
        if keep:
            e["out"] = keep
        else:
            e.pop("out", None)
    json.dump(out, open(OUT, "w"), separators=(",", ":"), sort_keys=True)
    print("alerts: %d games, %d in wind or rain, %d with injuries"
          % (len(out), sum(1 for x in out.values() if not x["wx"]["in"] and ((x["wx"]["g"] or 0) >= 15 or (x["wx"]["p"] or 0) >= 50)),
             sum(1 for x in out.values() if x.get("out"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
