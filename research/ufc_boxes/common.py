"""Shared fetch + name helpers for the gidstats / Sherdog record pull."""
import hashlib, os, re, time, unicodedata, random
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw')
os.makedirs(RAW, exist_ok=True)
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_s = requests.Session()
_s.headers.update({"User-Agent": UA, "Accept": "text/html,*/*",
                   "Accept-Language": "en-US,en;q=0.9"})
ad = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
_s.mount('https://', ad)


def cache_path(key):
    key = re.sub(r'[^A-Za-z0-9_.=-]', '_', key)
    if len(key) > 150:
        key = key[:100] + hashlib.md5(key.encode()).hexdigest()
    return os.path.join(RAW, key)


def fetch(url, key, tries=5):
    """Return (status, text). Cached: 200 pages as <key>.html, 404s as <key>.404."""
    p = cache_path(key)
    if os.path.exists(p + '.html'):
        return 200, open(p + '.html', encoding='utf-8', errors='replace').read()
    if os.path.exists(p + '.404'):
        return 404, ''
    last = None
    for i in range(tries):
        try:
            r = _s.get(url, timeout=30)
            if r.status_code == 200:
                open(p + '.html', 'w', encoding='utf-8').write(r.text)
                return 200, r.text
            if r.status_code == 404:
                open(p + '.404', 'w').write(url)
                return 404, ''
            last = r.status_code
        except Exception as e:
            last = repr(e)[:80]
        time.sleep(2 * (i + 1) + random.random())
    return -1, str(last)


SUFFIX = {'jr', 'sr', 'ii', 'iii', 'iv', 'junior'}


def norm(name):
    s = unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r"[.'`’]", '', s)
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    toks = [t for t in s.split() if t not in SUFFIX]
    return ' '.join(toks)


def tokkey(name):
    return ' '.join(sorted(norm(name).split()))


def compact(name):
    return norm(name).replace(' ', '')


def last(name):
    t = norm(name).split()
    return t[-1] if t else ''
