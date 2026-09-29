"""Between sweeps: has anything changed on the injury report or from the insiders?

   The sweep reads everything three times a day. In between, the ten-minute
   tick asks two cheap questions and does nothing more unless one of them has
   a new answer (Jose, Sep 29, 2026: "if we get any new alerts from Adam
   Schefter or Ian Rapoport or if anything pops up on ESPN for their injuries,
   then we just update automatically"):

     ESPN's whole NFL injury report     one request: who is on it, and how
     the insiders' latest posts         Schefter, Rapoport, Thamel: their ids

   A new answer runs the jobs that read them -- news.py, wire.py, alerts.py,
   lineups.py, starters.py -- and deploys. The answers are kept in
   data/watch.json, so the same report twice is nothing.

       python3 build/watch_news.py
"""
import hashlib
import json
import os
import subprocess
import sys

from curl_cffi import requests as rq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import news
import pagefile

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEEP = os.path.join(D, "data", "watch.json")


def sign(x):
    return hashlib.sha1(json.dumps(x, sort_keys=True).encode()).hexdigest()


def main():
    try:
        was = json.load(open(KEEP))
    except (OSError, ValueError):
        was = {}
    now = {}
    try:
        lj = rq.get("https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries",
                    impersonate="chrome124", timeout=30).json()
        now["injuries"] = sign(sorted(
            [(i.get("athlete") or {}).get("displayName"), i.get("status")]
            for t in lj.get("injuries") or [] for i in t.get("injuries") or []
            if i.get("status") != "Active"))
    except Exception:
        now["injuries"] = was.get("injuries")
    posts = news.insiders()
    now["insiders"] = sign(sorted(p.get("id") or p.get("headline") for p in posts)) if posts else was.get("insiders")

    moved = [k for k in now if now[k] and now[k] != was.get(k)]
    if not moved:
        print("watch: nothing new")
        return 0
    print("watch: new on " + ", ".join(moved))
    for job in ("news.py", "wire.py", "starters.py", "alerts.py", "lineups.py"):
        r = subprocess.run([sys.executable, os.path.join(D, "build", job)], capture_output=True, text=True, cwd=D)
        for line in (r.stdout + r.stderr).strip().splitlines()[-2:]:
            print("   %s: %s" % (job[:-3], line))
    pagefile.deployable(pagefile.read())
    dep = subprocess.run(["npx", "wrangler", "pages", "deploy", ".", "--project-name=the-arenasports", "--branch=main"],
                         cwd=os.path.join(D, "site"), capture_output=True, text=True, timeout=300)
    print("watch: deployed" if dep.returncode == 0 else "watch: DEPLOY FAILED")
    if dep.returncode == 0:
        json.dump(now, open(KEEP, "w"), indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
