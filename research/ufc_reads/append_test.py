"""The append path, end to end, without writing: take the Oct 10, 2026 event out of
the stored tables, let crawl() fetch and parse it from UFC Stats again, rebuild its
bout rows, and compare them with the audit's (D.pkl) rows."""
import os, sys, time
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "build"))
import ufc_reads as U
h = U.load_hist()
old = h["bouts"][h["bouts"].date == pd.Timestamp("2026-10-10")].set_index("fight_url")
ev = "http://ufcstats.com/event-details/7f98d9d5a10fa25c"
fus = set(old.index)
h["seen"].remove(ev)
h["fights"] = h["fights"][~h["fights"].fight_url.isin(fus)]
h["history"] = h["history"][~h["history"].fight_url.isin(fus)]
h["rounds"] = h["rounds"][h["rounds"].date != "2026-10-10"]
h["bouts"] = h["bouts"][~h["bouts"].fight_url.isin(fus)]
t = time.time()
added = U.crawl(h)
U.append_bouts(h, added)
print("crawl + append %.1fs" % (time.time() - t))
new = h["bouts"][h["bouts"].fight_url.isin(fus)].set_index("fight_url").loc[old.index]
bad = {}
for c in [c for c in U.BCOLS if c[:2] in ("a_", "b_") and c not in ("a_url", "b_url", "a_won")] + ["a_won"]:
    x, y = pd.to_numeric(old[c], errors="coerce").values.astype(float), pd.to_numeric(new[c], errors="coerce").values.astype(float)
    same = (np.isnan(x) & np.isnan(y)) | (np.abs(x - y) <= 1e-12)
    if (~same).sum():
        bad[c] = int((~same).sum())
print(len(new), "bouts re-crawled | mismatches vs audit:", bad or "none")
