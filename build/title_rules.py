"""The fifteen checks that can name a card without anybody writing the name.

   A hand-written title is one week's work and detaches the moment a card's
   legs move. A rule keyed on what is *on* the card — a surname, a repeated
   name, the shape of the legs — fires again next week on cards nobody has
   seen yet. These are those rules.

   Each returns a name or nothing. The caller tries them in order and takes
   the first that fires, then holds it against the same gate every title
   passes: the name must be true of the legs.

   Run:  python3 build/title_rules.py        what they produce on the shelf
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from collections import Counter


# ---- 1. A surname that is also a word ----
#
# Reviewed once and kept here, the way `alias` is: the wordplay is a judgment
# and belongs where somebody can read it, not in a rule that guesses. Keyed on
# the surname, so it fires for that man on any card, this week or in October.
PUNS = {
    "Likely":   ["A Likely Story", "Most Likely"],
    "Pickens":  ["Slim Pickens"],
    "Golden":   ["Golden Hour", "Golden Touch"],
    "Swift":    ["Swift Work"],
    "Worthy":   ["Worthy Of It"],
    "Flowers":  ["Flowers In Bloom"],
    "Fannin":   ["Fannin The Flames"],
    "Kupp":     ["Kupp Runneth Over"],
    "Purdy":    ["Sittin' Purdy", "Purdy Good Day"],
    "Evans":    ["Evans Above"],
    "Price":    ["The Price Is Right"],
    "Kraft":    ["Kraft Work"],
    "London":   ["London Calling"],
    "Adams":    ["The Adams Family"],
    "Love":     ["Love Language"],
    "Hall":     ["Hall Of Fame Stuff"],
    "Sutton":   ["Sutton Impact"],
    "Nix":      ["Nix It"],
    "Ward":     ["Ward Off"],
    "Downs":    ["No Downs About It"],
    "Pierce":   ["Pierce The Line"],
    "Bowers":   ["Bowers Of Power"],
    "Rice":     ["Rice And Easy"],
    "Cook":     ["Now We're Cooking"],
    "Young":    ["Young And Willing"],
    "Hubbard":  ["Mother Hubbard's Cupboard"],
}

# The first name a man is known by, where the surname is not the story.
FIRST = {"Rome": ["All Roads To Rome"]}


def surnames(card):
    for man in card.get("players") or []:
        parts = str(man.get("name") or "").split()
        if parts:
            yield parts[-1].strip(".,"), parts[0], man


def leads(card, last, first):
    """Whether this is the man the card is built around.

       The first leg, in the order the card is drawn — nothing sorts them, so
       the array order is the reading order. A pun on the third name of four
       is true and still points at the wrong man: "Sittin' Purdy" over a card
       whose first line is Drake Maye is a headline about somebody who is
       barely on it."""
    legs = card.get("legs") or []
    if not legs:
        return False
    said = str(legs[0].get("says") or "")
    return last in said or first in said


def rule_pun(card, town):
    """1. A surname or first name that is also a word, on the man the card
       leads with."""
    for last, first, _ in surnames(card):
        if not leads(card, last, first):
            continue
        for said in PUNS.get(last, []) + FIRST.get(first, []):
            yield said


def rule_city(card, town):
    """2. A man whose name is the town he is playing in."""
    if not town:
        return
    short = re.sub(r"[^a-z]", "", town.lower())[:5]
    for last, first, _ in surnames(card):
        if not leads(card, last, first):
            continue
        flat = re.sub(r"[^a-z]", "", last.lower())
        if len(flat) >= 4 and short.startswith(flat[:5]):
            yield "%s In %s" % (last, town)


def rule_same_name(card, town):
    """3. Two men on the card who answer to the same name."""
    lasts = Counter(last for last, _, _ in surnames(card))
    firsts = Counter(first for _, first, _ in surnames(card))
    for name, many in list(lasts.items()) + list(firsts.items()):
        if many > 1:
            yield "The %s Is On" % name if name in ("Chase",) else \
                  "Two Of A %s" % name


def kinds_of(card):
    return {str(leg.get("kind") or "") for leg in card.get("legs") or []}


def figures(card):
    return [str(leg.get("figure") or "") for leg in card.get("legs") or []]


NUMBER = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven"}


def rule_all_under(card, town):
    """4. Every leg an under — a card that wants a quiet afternoon."""
    figs = figures(card)
    if figs and all(f.startswith("U ") for f in figs):
        yield "A Quiet Afternoon"
        yield "Keep It Quiet"


def rule_all_win(card, town):
    """5. Every leg a club to win."""
    figs = figures(card)
    if len(figs) > 1 and all(f == "WIN" for f in figs):
        yield "%s Straight Winners" % NUMBER.get(len(figs), "")
        yield "Nobody Loses"


def rule_all_spread(card, town):
    """6. Every leg a spread."""
    if kinds_of(card) == {"Spread"} and len(card.get("legs") or []) > 1:
        yield "Covering All %s" % NUMBER.get(len(card["legs"]), "")


def rule_all_td(card, town):
    """7. Every leg a touchdown, and the count said out loud."""
    kinds = kinds_of(card)
    legs = card.get("legs") or []
    if legs and kinds and kinds <= {"TD", "Anytime TD", "First TD",
                                    "Rushing TDs", "Receiving TDs"}:
        many = NUMBER.get(len(legs))
        if many:
            yield "%s In The End Zone" % many


def rule_many_games(card, town):
    """8. A card that spans more than one game."""
    clubs = card.get("clubs") or []
    if len(clubs) >= 4:
        yield "%s Clubs, One Card" % NUMBER.get(len(clubs), "Four")


def owned(said):
    """A man's name in the possessive, as English writes it."""
    return said + ("'" if said.endswith("s") else "'s")


def rule_one_man(card, town):
    """9. Every leg on the same man — and enough legs for it to be a hand.

       Three or more. Two legs on one man is a pair, not the whole of him,
       and a card of one leg is not a hand at all: this fired on ninety-five
       cards the first time, most of them a single line."""
    men = {man["name"] for man in card.get("players") or []}
    legs = card.get("legs") or []
    if len(men) != 1 or len(legs) < 3:
        return
    his = [leg for leg in legs
           if list(men)[0].split()[-1] in str(leg.get("says") or "")]
    if len(his) < 3:
        return
    yield "%s Whole Hand" % owned(list(men)[0].split()[-1])
    yield "All Of %s" % list(men)[0].split()[-1]


def rule_arm_and_legs(card, town):
    """10. One man asked to do it with his arm and his legs."""
    for man in card.get("players") or []:
        his = [leg for leg in card["legs"]
               if man["name"].split()[-1] in str(leg.get("says") or "")]
        kinds = {str(leg.get("kind") or "") for leg in his}
        if any("Passing" in k for k in kinds) and any("Rush" in k for k in kinds):
            yield "One Throw, One Run"
            return


def rule_matching_arms(card, town):
    """11. Two quarterbacks asked for the same number."""
    passing = [leg for leg in card.get("legs") or []
               if str(leg.get("kind")) == "Passing Yards"]
    if len(passing) == 2 and passing[0].get("mark") == passing[1].get("mark"):
        yield "Arm For Arm"
        yield "Matching Throws"


def rule_spots(card, town):
    """12. The shape of the cast: a tight end and a back, two targets and an
       arm, two backs against each other."""
    spots = Counter(man.get("spot") for man in card.get("players") or [])
    if spots.get("TE") and spots.get("RB") and sum(spots.values()) == 2:
        yield "Tight End And Tailback"
    if spots.get("WR", 0) == 2 and spots.get("QB", 0) == 1:
        yield "Two Targets, One Arm"
    if spots.get("RB", 0) == 2 and sum(spots.values()) == 2:
        yield "Backs Against Backs"


def rule_abroad(card, town):
    """13. A game played outside the country."""
    if town and town in ABROAD:
        yield "Both Ways %s" % ABROAD[town]


ABROAD = {"Melbourne": "Down Under", "London": "Over There",
          "Munich": "Over There", "Dublin": "Over There",
          "Mexico City": "Down South", "Sao Paulo": "Down South",
          "Madrid": "Over There", "Berlin": "Over There"}


def rule_both_clubs_score(card, town):
    """14. A man from each club asked to score."""
    clubs = {man.get("club") for man in card.get("players") or []}
    kinds = kinds_of(card)
    if len(clubs) == 2 and kinds and kinds <= {"TD", "Anytime TD", "First TD",
                                               "Rushing TDs", "Receiving TDs"}:
        yield "Both Ends Of It"


def rule_whole_bench(card, town):
    """15. Four or more men named on one card."""
    men = {man["name"] for man in card.get("players") or []}
    if len(men) >= 4:
        yield "Both Benches Busy"
        yield "Everything On Show"


RULES = [rule_pun, rule_city, rule_same_name, rule_all_under, rule_all_win,
         rule_all_spread, rule_all_td, rule_many_games, rule_one_man,
         rule_arm_and_legs, rule_matching_arms, rule_spots, rule_abroad,
         rule_both_clubs_score, rule_whole_bench]


# ---- the gate every name passes ----
CLAIMS = [
    (re.compile(r"\b(ground|land|legs?|run|running|rush\w*|carry|carries)\b", re.I),
     ("Rushing Yards", "Rushing TDs")),
    (re.compile(r"\b(air|arm|arms|heave\w*|throw\w*|pass\w*|aerial)\b", re.I),
     ("Passing Yards", "Passing TDs", "Pass Attempts", "Completions")),
    (re.compile(r"\b(hands|catch\w*|receiv\w*|reception\w*|target\w*)\b", re.I),
     ("Receiving Yards", "Receiving TDs", "Receptions")),
    (re.compile(r"\b(six|tuddy|touchdown\w*|endzone|end zone)\b", re.I),
     ("TD", "Anytime TD", "First TD", "Rushing TDs", "Passing TDs",
      "Receiving TDs")),
]
COUNTS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}


def true_of(said, card):
    legs = card.get("legs") or []
    kinds = kinds_of(card)
    for word, many in COUNTS.items():
        if re.search(r"\b%s\b" % word, said, re.I) and len(legs) != many:
            return False
    for shape, wanted in CLAIMS:
        if shape.search(said) and not (kinds & set(wanted)):
            return False
    return True


def name_for(card, town, taken):
    """The first rule that fires with a name this card can stand behind."""
    for rule in RULES:
        for said in rule(card, town) or []:
            if said and said not in taken and true_of(said, card):
                return said, rule.__name__
    return None, None


def every_name(card, town):
    """Every name the rules can give this card, best first.

       The caller holds them against the names already used and against its
       own reading of what fits, so this offers rather than decides."""
    for rule in RULES:
        for said in rule(card, town) or []:
            if said and true_of(said, card):
                yield said


def main():
    said = open("data/cards.js").read()
    cards = json.loads(said[said.index("["):said.rindex("]") + 1])

    import sqlite3
    db = sqlite3.connect("data/qbspy.db")
    town = {}
    for away, home, where in db.execute(
            "SELECT away, home, location FROM league_game"):
        town["%s @ %s" % (away, home)] = (where or "").split(",")[0].strip()

    taken, hits, by_rule = set(), [], Counter()
    for card in cards:
        name, rule = name_for(card, town.get(card.get("fixture"), ""), taken)
        if name:
            taken.add(name)
            hits.append((name, rule, card))
            by_rule[rule] += 1

    print("%d of %d cards named by rule alone\n" % (len(hits), len(cards)))
    for rule, many in by_rule.most_common():
        print("   %-22s %d" % (rule.replace("rule_", ""), many))

    print("\n--- every one of them ---")
    for name, rule, card in hits:
        legs = " / ".join(
            "%s %s" % (leg.get("figure", ""), leg.get("says", ""))
            for leg in card["legs"])[:74]
        print("  %-26s %-16s %s" % (name, rule.replace("rule_", ""), legs))


if __name__ == "__main__":
    main()
