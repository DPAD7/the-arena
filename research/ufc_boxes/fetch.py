import re, hashlib, os, time, threading
from curl_cffi import requests as rq
BASE='http://ufcstats.com'
_local=threading.local()
def sess():
    s=getattr(_local,'s',None)
    if s is None:
        s=rq.Session(impersonate='chrome'); _local.s=s
    return s
def solve(s,html,url):
    nonce=re.search(r'var nonce="([0-9a-f]+)"',html).group(1)
    k=int(re.search(r'new Array\((\d+)\+1\)',html).group(1))
    t='0'*k; n=0
    while not hashlib.sha256(f'{nonce}:{n}'.encode()).hexdigest().startswith(t): n+=1
    host=re.match(r'(https?://[^/]+)',url).group(1)
    r=s.post(host+'/__c',data={'nonce':nonce,'n':str(n)},timeout=30,headers={'Referer':url})
    return r.status_code
def get(url, tries=6):
    last=None
    for i in range(tries):
        try:
            s=sess()
            r=s.get(url,timeout=30)
            if 'Checking your browser' in r.text and '/__c' in r.text:
                solve(s,r.text,url); continue
            if r.status_code==200: return r.text
            last=r.status_code
        except Exception as e:
            last=e
        time.sleep(1.5*(i+1))
    raise RuntimeError(f'{url}: {last}')
