"""Fetch gidstats' full fighter directory -> gid_index.json [[slug, name], ...]."""
import json, re, sys
from concurrent.futures import ThreadPoolExecutor
from common import fetch, HERE

st, t = fetch('https://gidstats.com/fighters/', 'gidx_1')
last = max(int(x) for x in re.findall(r'/fighters/page-(\d+)\.html', t))
print('pages', last, flush=True)


def one(n):
    url = 'https://gidstats.com/fighters/' if n == 1 else f'https://gidstats.com/fighters/page-{n}.html'
    st, t = fetch(url, f'gidx_{n}')
    if st != 200:
        print('FAIL', n, st, t, flush=True)
        return []
    return re.findall(r'<a href="/fighters/([a-z0-9_-]+)\.html">\s*<img[^>]*alt="([^"]*)"', t)


out = []
with ThreadPoolExecutor(5) as ex:
    for i, rows in enumerate(ex.map(one, range(1, last + 1))):
        out += rows
        if i % 25 == 0:
            print(i, len(out), flush=True)
seen = {}
for s, n in out:
    seen[s] = n
json.dump(sorted(seen.items()), open(f'{HERE}/gid_index.json', 'w'))
print('fighters', len(seen))
