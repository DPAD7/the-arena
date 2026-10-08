import re, glob, os, numpy as np, pandas as pd
F=pd.read_csv('fights.csv'); F=F[F.winner.isin(['red','blue'])]
def cells(t):
    return [re.sub(r'\s+',' ',re.sub(r'<[^>]+>',' ',c)).strip() for c in re.findall(r'<td[^>]*>(.*?)</td>',t,re.S)]
def of(s):
    m=re.match(r'(\d+) of (\d+)',s or ''); return (int(m.group(1)),int(m.group(2))) if m else (np.nan,np.nan)
def sec(s):
    try: a,b=s.split(':'); return int(a)*60+int(b)
    except: return np.nan
rows=[]
for r in F.itertuples():
    fid=r.fight_url.rstrip('/').split('/')[-1]; p=f'raw/fight/{fid}.html'
    if not os.path.exists(p): continue
    t=open(p,errors='ignore').read()
    i=t.find('Per round')
    if i<0: continue
    seg=t[i:t.find('Significant Strikes',i) if t.find('Significant Strikes',i)>0 else i+40000]
    for rn,block in enumerate(re.split(r'Round \d+',seg)[1:],start=1):
        c=cells(block)
        # each cell holds "red_value blue_value"; columns: fighter,KD,Sig str,Sig%,Total,TD,TD%,Sub,Rev,Ctrl
        if len(c)<10: continue
        def two(x):
            m=re.findall(r'\d+ of \d+|\d+:\d+|---|\d+%|\d+',x); return m
        kd=two(c[1]); sig=re.findall(r'\d+ of \d+',c[2]); td=re.findall(r'\d+ of \d+',c[5]); ctrl=re.findall(r'\d+:\d+|--',c[9])
        if len(sig)<2: continue
        for k,(side,o) in enumerate((('red',r.red_url),('blue',r.blue_url))):
            sl,sa=of(sig[k]); osl,_=of(sig[1-k]); tl,ta=of(td[k]) if len(td)>1 else (np.nan,np.nan)
            rows.append(dict(url=o,date=r.event_date,rnd=rn,sig=sl,sig_abs=osl,kd=int(kd[k]) if len(kd)>1 and kd[k].isdigit() else np.nan,
                             kd_abs=int(kd[1-k]) if len(kd)>1 and kd[1-k].isdigit() else np.nan,td=tl,ctrl=sec(ctrl[k]) if len(ctrl)>1 else np.nan))
R=pd.DataFrame(rows); R.to_csv('rounds.csv',index=False); print(len(R),'fighter-rounds from',R.date.nunique(),'dates')
