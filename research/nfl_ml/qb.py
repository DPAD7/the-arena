import pandas as pd, numpy as np
P=pd.concat([pd.read_parquet(f'nfv/pbp_{y}.parquet',columns=['season','week','season_type','passer_player_id','qb_epa','qb_dropback','cpoe']) for y in range(2016,2027)])
P=P[(P.season_type=='REG')&(P.qb_dropback==1)&P.passer_player_id.notna()]
Q=P.groupby(['passer_player_id','season','week']).agg(qe=('qb_epa','mean'),cp=('cpoe','mean'),n=('qb_epa','size')).reset_index().sort_values(['season','week'])
Q['k']=Q.season*100+Q.week
QG={q:g for q,g in Q.groupby('passer_player_id')}
X=pd.read_pickle('ml/XB.pkl')
def qprof(q,s,w):
    g=QG.get(q)
    if g is None: return (np.nan,np.nan,0)
    p=g[g.k<s*100+w].tail(16); p=p[p.n>=10]
    if p.empty: return (np.nan,np.nan,0)
    return ((p.qe*p.n).sum()/p.n.sum(),p.cp.mean(),len(p))
for side in 'ha':
    v=[qprof(getattr(r,side+'_qb'),r.season,r.week) for r in X.itertuples()]
    X[side+'_qe']=[x[0] for x in v]; X[side+'_cp']=[x[1] for x in v]; X[side+'_qn']=[x[2] for x in v]
X.to_pickle('ml/XQ.pkl'); print(X[['h_qe','a_qe']].notna().mean())
