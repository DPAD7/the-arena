"""Whether a clip's title says it is some other play (Oct 4, 2026).

   A clip is matched to a touchdown by the scorer's name, and twice that put a
   wrong video under a passer: Cousins' 20-yard pass to Bowers wore "Brock
   Bowers overpowers Saints defender for 4-yard TD" from another game, and
   Maye's 23-yard pass to Chism wore a "Sights & Sounds" tailgate reel. A title
   is the wrong clip when it names a club not in this game, gives a yardage
   that is not the play's, or is a reel, a presser or a highlights package.
"""
import re

NICK = {
    "ARI": "cardinals", "ATL": "falcons", "BAL": "ravens", "BUF": "bills", "CAR": "panthers",
    "CHI": "bears", "CIN": "bengals", "CLE": "browns", "DAL": "cowboys", "DEN": "broncos",
    "DET": "lions", "GB": "packers", "HOU": "texans", "IND": "colts", "JAX": "jaguars",
    "KC": "chiefs", "LV": "raiders", "LAC": "chargers", "LAR": "rams", "MIA": "dolphins",
    "MIN": "vikings", "NE": "patriots", "NO": "saints", "NYG": "giants", "NYJ": "jets",
    "PHI": "eagles", "PIT": "steelers", "SF": "49ers", "SEA": "seahawks", "TB": "buccaneers",
    "TEN": "titans", "WSH": "commanders",
}
SHORT = {"pats": "NE", "niners": "SF", "bucs": "TB", "jags": "JAX", "fins": "MIA", "'fins": "MIA"}
REEL = re.compile(r"sights\s*(&|and)\s*sounds|highlights|best plays|every (td|touchdown)|mic'?d up|"
                  r"press conference|postgame|pregame|recap|all access|tunnel|tailgate|week \d+ preview|top \d+", re.I)


def wrong(headline, text, clubs):
    """True when the title is not this play. clubs: the game's two abbreviations."""
    h = str(headline or "")
    if not h:
        return False
    # the clubs' sites tag a single play "HIGHLIGHTS: ..." or "... | Saints vs.
    # Raiders Highlights": the tag is not the title
    h = re.sub(r"^\s*highlights\s*[:|]\s*", "", h, flags=re.I)
    parts = [p for p in re.split(r"\s+\|\s+", h) if not re.search(r"highlights\s*$", p, re.I)]
    h = " | ".join(parts) or h
    low = h.lower()
    if REEL.search(low):
        return True
    here = {c.upper() for c in clubs if c}
    for ab, nick in NICK.items():
        if ab not in here and re.search(r"\b" + re.escape(nick) + r"\b", low):
            return True
    for w, ab in SHORT.items():
        if ab not in here and re.search(r"(^|\W)" + re.escape(w) + r"\b", low):
            return True
    m = re.search(r"\b(\d+) Yd\b", str(text or ""))
    ys = re.findall(r"(\d+)-y(?:ar)?d(?!\s*(?:\w+\s+){0,2}drive)", low)
    # a yard either way is the same play: ESPN and the clubs round differently
    if m and ys and not any(abs(int(y) - int(m.group(1))) <= 1 for y in ys):
        return True
    return False
