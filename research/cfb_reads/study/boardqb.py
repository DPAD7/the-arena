"""The board's own card QB for each college game and club: the models take
   him over the man who started the club's last game (Oct 9, 2026: Iowa's
   Hank Brown was hurt and the card already had Hecklinski)."""
import json, os, re, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "build"))
import pagefile


def board():
    cfb = json.loads(re.search(r"\bCFB\s*=\s*(\[.*?\]);\n", pagefile.read(), re.S).group(1))
    out = {}
    for g in cfb:
        out[(str(g[1]), g[3])] = (str(g[6] or ""), g[5])
        out[(str(g[1]), g[4])] = (str(g[8] or ""), g[7])
    return out
