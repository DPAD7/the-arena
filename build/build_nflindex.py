"""Which NFL.com clip is which touchdown, keyed.

   NFL.com stamps a clip with the play it shows, and that play carries the
   snap clock; ESPN's scoring line carries the clock after the play. They are
   the same moment three to ten seconds apart, so the join is quarter plus
   nearest earlier snap, touchdown plays only, each clip used once. The few
   clips NFL.com publishes without a play key fall back to the scorer's
   surname plus the distance, which within one game is exact.

   Rushing touchdowns are indexed as well as passing ones. Keying only passes
   is why Baker Mayfield's 9-yard scramble and Lamar Jackson's 5-yard run had
   no clip on the board while NFL.com carried both. (Jose, Sep 17, 2026)
"""
import json, re, collections
try:
    from curl_cffi import requests as rq
except ImportError:
    import requests as rq
nfl=json.load(open("site/nflclips.json"))
Q={"1st":1,"2nd":2,"3rd":3,"4th":4,"OT":5}
def secs(c):
    m=re.match(r"(\d*):(\d\d)", c or ""); return int(m.group(1) or 0)*60+int(m.group(2)) if m else None
tot=hit=fb=0; index={}; miss=[]
for eid,g in nfl.items():
    d=rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event=%s"%eid, impersonate="chrome124", timeout=40).json()
    sp=[]
    for p in (d.get("scoringPlays") or []):
        t=p.get("text") or ""
        if " Yd pass from " in t: sp.append(("pass", p))
        elif re.match(r"^(.+?) (\d+) Yd (?:Rush|Run)\b", t): sp.append(("rush", p))
    def isTd(c, kind):
        if not (c["playId"] and c["play"] and "TOUCHDOWN" in c["play"]): return False
        # a pass clip says pass; a rushing one says neither pass nor interception
        has_pass = re.search(r"\bpass\b", c["play"], re.I) is not None
        picked = "INTERCEPTED" in c["play"]
        return has_pass and not picked if kind=="pass" else not has_pass and not picked
    unkeyed=[c for c in g["clips"] if not c["playId"]]
    rows=[]; used=set()
    for kind, p in sp:
        tot+=1
        keyed=[c for c in g["clips"] if isTd(c, kind)]
        per=(p.get("period") or {}).get("number"); es=secs((p.get("clock") or {}).get("displayValue"))
        m=(re.match(r"^(.+?) (\d+) Yd pass from ([^(]+)", p["text"]) if kind=="pass"
           else re.match(r"^(.+?) (\d+) Yd (?:Rush|Run)\b", p["text"]))
        man=m.group(1).split()[-1].lower(); yds=m.group(2)
        cands=sorted([(secs(c["clock"])-es, c) for c in keyed
                      if Q.get(c["quarter"])==per and c["externalId"] not in used
                      and secs(c["clock"]) is not None and es is not None and 0<=secs(c["clock"])-es<=45],
                     key=lambda x:x[0])
        c=None
        if cands: c=cands[0][1]; hit+=1
        else:
            alt=[c2 for c2 in unkeyed if c2["externalId"] not in used and man in (c2["headline"] or "").lower()
                 and re.search(r"\b%s-yard\b"%yds, (c2["headline"] or "").lower())]
            if len(alt)==1: c=alt[0]; fb+=1
        if c:
            used.add(c["externalId"])
            rows.append({"text":p["text"],"ext":c["externalId"],"headline":c["headline"]})
        else: miss.append((eid, per, (p.get("clock") or {}).get("displayValue"), p["text"][:44]))
    index[eid]=rows
json.dump(index, open("site/nflindex.json","w"), separators=(",",":"))
print("touchdowns %d   keyed %d   by name+yards %d   total %d (%.0f%%)   left %d"%(tot,hit,fb,hit+fb,100.0*(hit+fb)/tot,len(miss)))
for x in miss: print("   %s Q%s %-5s %s"%x)
