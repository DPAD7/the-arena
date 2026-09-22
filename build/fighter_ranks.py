"""Who the UFC ranks, flattened for the board.

   build/ufc_rankings.py reads their table into data/ufc_rankings.json, a list
   of divisions each with a champion and the fifteen behind him. A bout card
   needs one question answered -- what is this man's number, and is he in a
   women's division -- so this writes that, keyed by his name as the board
   writes it:

       { "islam makhachev": {"r": "C", "w": 0, "d": "Lightweight"}, ... }

   `r` is his number, or "C" for a champion. A man the panel has not ranked is
   simply absent, and the card reads NR -- an absence, not a placeholder
   (Jose, Sep 21, 2026).

   The pound-for-pound lists are skipped: they are a ranking OF the ranked, not
   a division, and a man's own division is what a bout card says.
"""
import json
import os

D = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    src = os.path.join(D, "data", "ufc_rankings.json")
    divs = json.load(open(src))
    out = {}

    def put(name, rank, div):
        key = (name or "").strip().lower()
        if not key:
            return
        # a man ranked in two places keeps the first, which is his own division
        if key in out:
            return
        out[key] = {"r": rank, "w": 1 if div.lower().startswith("women") else 0,
                    "d": div}

    for d in divs:
        div = d.get("division") or ""
        if "pound-for-pound" in div.lower():
            continue
        if d.get("champion"):
            put(d["champion"], "C", div)
        for m in (d.get("men") or []):
            put(m.get("name"), m.get("rank"), div)

    path = os.path.join(D, "site", "fighter_ranks.json")
    with open(path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"), sort_keys=True)
    print("fighter_ranks.json: %d ranked across %d divisions"
          % (len(out), len([d for d in divs
                            if "pound-for-pound" not in (d.get("division") or "").lower()])))


if __name__ == "__main__":
    main()
