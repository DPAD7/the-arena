import os, re
from concurrent.futures import ThreadPoolExecutor
from fetch import get
RAW=os.path.join(os.path.dirname(os.path.abspath(__file__)),'raw')
def path(url):
    kind,id_=re.search(r'/(event|fight|fighter)-details/([0-9a-f]+)',url).groups()
    d=os.path.join(RAW,kind); os.makedirs(d,exist_ok=True)
    return os.path.join(d,id_+'.html')
def cached(url):
    p=path(url)
    if os.path.exists(p) and os.path.getsize(p)>5000: return open(p).read()
    h=get(url); open(p,'w').write(h); return h
def fetch_all(urls, workers=8):
    fails={}; out={}
    def one(u):
        try: out[u]=cached(u)
        except Exception as e: fails[u]=str(e)
    with ThreadPoolExecutor(workers) as ex: list(ex.map(one,urls))
    return out,fails
