"""Take the first-quarter reception section off every card.

   It was the one first-quarter market on the board and he has cut it. The
   fight cards use the same `grow` row for SUB and the rest, so only the rows
   holding a receiver pair come out -- eight rows are left alone.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")

rows = re.findall(r'<div class="grow">.*?</div>\n', s, re.S)
gone = [r for r in rows if "recpair" in r]
assert len(gone) == 14, "expected 14 receiver rows, found %d" % len(gone)
for r in gone:
    s = s.replace(r, "", 1)

assert '<span class="gcell recpair">' not in s, "markup left behind"
assert s.count('<div class="grow">') == len(rows) - len(gone)

# the styling has nothing left to style
for dead in ('  .recpair { display: flex; gap: 10px; align-items: flex-start; '
             'justify-content: center; }\n',
             '  .recman .price { margin: 0; }\n',
             '  .recman .wrname { display: block; margin: 0; white-space: nowrap; }\n',
             '  .recman .wrname { position: relative; }\n',
             '  .recman .wrname .mk { margin-left: 4px; }\n'):
    s = s.replace(dead, "")
s = re.sub(r'  \.recman \{[^}]*\}\n', "", s)
print("rows removed: %d | prices: %d -> %d" % (len(gone), before, s.count("data-oid")))

open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
