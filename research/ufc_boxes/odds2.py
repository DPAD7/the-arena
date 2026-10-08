"""U.pkl + closing odds -> U4.pkl. BFO closing mid first (2015+), then the gidstats
archives (scratchpad ufc_odds_all.json and ~/mma-pipeline fighter pages). Matched by
date (+-1 day) and both last names."""
import pandas as pd, numpy as np, json, glob, unicodedata
def ln(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower().replace('.','').replace('-',' ').replace('_',' ')
    p=[w for w in s.split() if w not in('jr','sr','ii','iii')]; return p[-1] if p else ''
def num(x):
    try: return float(str(x).replace('+',''))
    except: return np.nan
O={}
def put(d,a,b,oa,ob):
    if np.isnan(oa) or np.isnan(ob) or oa==ob: return
    for k in (0,1,-1):
        dd=(pd.to_datetime(d)+pd.Timedelta(days=k)).strftime('%Y-%m-%d')
        O.setdefault((dd,ln(a),ln(b)),(oa,ob)); O.setdefault((dd,ln(b),ln(a)),(ob,oa))
for r in pd.read_csv('../ufc_bfo/bfo_ufc.csv').itertuples(): put(r.event_date,r.fighter_a,r.fighter_b,num(r.a_close_mid),num(r.b_close_mid))
for k,v in json.load(open('../ufc/ufc_odds_all.json')).items(): put(v['date'],v['left'],v['right'],num(v['lodds']),num(v['rodds']))
one={}
for f in glob.glob('/Users/joe/mma-pipeline/.cache/gidstats/fighter__*.json'):
    d=json.load(open(f))
    for x in d.get('fight_history') or []:
        o=num(x.get('odds_american'))
        if not np.isnan(o) and x.get('date_iso'):
            one[(x['date_iso'],ln(d['name']),ln(x.get('opponent') or x.get('opponent_slug','')))]=o
for (d,a,b),o in one.items():
    ob=one.get((d,b,a))
    put(d,a,b,o,ob if ob is not None else (-o if abs(o)>=100 else np.nan))
X=pd.read_pickle('U.pkl'); X['d']=X.date.dt.strftime('%Y-%m-%d')
oa=[];ob=[]
for r in X.itertuples():
    v=O.get((r.d,ln(r.a),ln(r.b))); oa.append(v[0] if v else np.nan); ob.append(v[1] if v else np.nan)
X['oa']=oa; X['ob']=ob
X=X[X.oa.notna()].copy()
fa=X.oa<X.ob; fo=np.minimum(X.oa,X.ob)
X['fav_won']=np.where(fa,X.a_won,1-X.a_won)
X['band']=np.where(fo<=-300,'1 heavy',np.where(fo<=-150,'2 medium','3 coin'))
X['score']=0; X['score_side']=0
X.to_pickle('U4.pkl'); print('with odds',len(X)); print(X.groupby('yr').size().to_dict())
