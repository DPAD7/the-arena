"""How DraftKings writes a club, pinned to how ESPN writes it.

   Matched as written, "MIA FL" and "MIA" are two different schools and "WAS"
   is not "WSH". The pairs are learned once rather than guessed at read time:
   a fixture whose date and one club already agree tells us what the other
   club's two spellings mean, and that is written down here for review.

   Writes clubs.json. Rerun when a league starts writing somebody a new way.
"""
import collections
import datetime
import json
import os

D = os.path.dirname(os.path.abspath(__file__))


def dk_events(name):
    out = {}
    for e in json.load(open("/tmp/dk_%s.json" % name)):
        shorts = [(p.get("metadata") or {}).get("shortName", "")
                  for p in (e.get("participants") or [])]
        out[e["id"]] = ((e.get("startEventDate") or "")[:10],
                        tuple(sorted(shorts)), e.get("name"))
    return out


def espn_nfl():
    sched = json.load(open("/tmp/nfl2026.json"))
    return {g["id"]: (g["date"][:10], tuple(sorted([g["away"][0], g["home"][0]])))
            for w in sched for g in sched[w]}


def espn_cfb():
    return {g[1]: (g[2][:10], tuple(sorted([g[3], g[4]])))
            for g in json.load(open("/tmp/cfb_all.json"))}


def days(d):
    """A kickoff after eight lands on the next day in UTC."""
    base = datetime.date.fromisoformat(d)
    return [d, (base - datetime.timedelta(days=1)).isoformat(),
            (base + datetime.timedelta(days=1)).isoformat()]


def learn(dk, espn, alias):
    """One pass: match what we can, and note what the near misses teach."""
    byday = collections.defaultdict(list)
    for eid, (d, pair) in espn.items():
        byday[d].append((eid, set(pair)))
    hit, taught = {}, {}
    for did, (d, pair, nm) in dk.items():
        want = {alias.get(x, x) for x in pair}
        best = None
        for dd in days(d):
            for eid, theirs in byday[dd]:
                shared = len(want & theirs)
                if shared == 2:
                    best = (2, eid, theirs)
                    break
                if shared == 1 and (best is None or best[0] < 1):
                    best = (1, eid, theirs)
            if best and best[0] == 2:
                break
        if not best:
            continue
        if best[0] == 2:
            hit[did] = best[1]
        else:
            # one side agrees, so the two odd spellings are the same club
            odd_dk = list(want - best[2])
            odd_espn = list(best[2] - want)
            if len(odd_dk) == 1 and len(odd_espn) == 1:
                for raw in pair:
                    if alias.get(raw, raw) == odd_dk[0]:
                        taught[raw] = odd_espn[0]
    return hit, taught


out = {"alias": {}, "nfl": {}, "cfb": {}}
for key, dkname, table in (("nfl", "nfl", espn_nfl()), ("cfb", "ncaaf", espn_cfb())):
    dk = dk_events(dkname)
    alias = {}
    for _ in range(4):
        hit, taught = learn(dk, table, alias)
        new = {k: v for k, v in taught.items() if alias.get(k) != v}
        if not new:
            break
        alias.update(new)
    hit, _ = learn(dk, table, alias)
    print("%-4s matched %d of %d | learned %d spellings"
          % (key.upper(), len(hit), len(dk), len(alias)))
    for k in sorted(alias):
        print("        %-10s -> %s" % (k, alias[k]))
    # what is left had both clubs written differently, so nothing anchored it.
    # The location ESPN prints for a club settles those without guessing.
    missing = [(d, v) for d, v in dk.items() if d not in hit]
    if missing and key == "cfb":
        place = {}
        for ab, disp, short, loc in json.load(open("/tmp/cfbnames_flat.json")):
            for w in (loc, short, disp):
                if w:
                    place.setdefault(w.lower(), ab)
        raw = {e["id"]: [(p.get("name") or "",
                          (p.get("metadata") or {}).get("shortName", ""))
                         for p in (e.get("participants") or [])]
               for e in json.load(open("/tmp/dk_ncaaf.json"))}
        byday = collections.defaultdict(list)
        for eid, (dd, pair) in table.items():
            byday[dd].append((eid, set(pair)))
        for did, (d, pair, nm) in missing:
            want = set()
            for full, short in raw.get(did, []):
                ab = place.get(full.lower())
                if ab:
                    want.add(ab)
                    if short and short not in alias and ab != short:
                        alias[short] = ab
            if len(want) != 2:
                continue
            for dd in days(d):
                for eid, theirs in byday[dd]:
                    if want == theirs:
                        hit[did] = eid
                        break
                if did in hit:
                    break
        out["alias"].update(alias)
        print("        after reading the locations: %d of %d" % (len(hit), len(dk)))
    for d, v in dk.items():
        if d not in hit:
            print("        still unmatched:", v[2])
    out[key] = hit
    out["alias"].update(alias)

json.dump(out, open(D + "/clubs.json", "w"), indent=1, sort_keys=True)
print("\nwrote clubs.json")
