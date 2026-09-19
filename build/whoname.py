"""One man's name, written the several ways the boards write it.

   A suffix is not a different man. Neither is an accent, a full stop, or a
   capital letter: DraftKings writes Billy Edwards where our row says Billy
   Edwards Jr., and Edgar Chairez where ours says Édgar Cháirez. Matched as
   written, his whole side of a card goes unread -- the Carolina passer had
   no touchdowns, no anytime and half a head-to-head on Sep 19, 2026.

   key() takes what does not tell two men apart back out of the name. It is
   a rule, not a guess: nothing here reaches for a near-miss, and the caller
   still has to be looking at the right game. Where a real difference stands
   between two men -- a different surname, a different first name -- the
   keys differ and nothing matches, which is what we want.

   A club tag in brackets goes too. DraftKings tags college men with their
   school, "Jayden Maiava (USC)", and the tag is not part of the name.
"""
import re
import unicodedata

SUFFIX = re.compile(r"\b(jr|sr|ii|iii|iv|v)\b\.?\s*$")
TAG = re.compile(r"\s*\([^)]*\)\s*$")
NOISE = re.compile(r"[^a-z0-9 ]+")


def key(name):
    """What two spellings of the same man have in common."""
    t = TAG.sub("", str(name or "")).strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    t = NOISE.sub(" ", t)
    t = SUFFIX.sub("", t).strip()
    return re.sub(r"\s+", " ", t)


def same(a, b):
    """Whether two written names are the one man. Blank is nobody."""
    ka, kb = key(a), key(b)
    return bool(ka) and ka == kb
