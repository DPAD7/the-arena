import pandas as pd, numpy as np, re, unicodedata
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
def ln(s):
    s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower().replace('.','').replace('-',' ')
    p=[w for w in s.split() if w not in('jr','sr','ii','iii')]; return p[-1] if p else ''
def ip(o): return np.where(o<0,-o/(-o+100),100/(o+100))
U=pd.read_pickle('ufc2/U6.pkl'); U=U[U.oa.notna()&U.ob.notna()&(U.oa!=U.ob)].copy()
U['d']=pd.to_datetime(U.date).dt.strftime('%Y-%m-%d')
fa=(U.oa<U.ob).values
# fav-perspective features: fav value, dog value, difference
num=[c[2:] for c in U.columns if c.startswith('a_') and c[2:] not in('url','stance','won') and 'b_'+c[2:] in U.columns and pd.api.types.is_numeric_dtype(U[c])]
X=pd.DataFrame(index=U.index)
for c in num:
    f=np.where(fa,U['a_'+c],U['b_'+c]).astype(float); d=np.where(fa,U['b_'+c],U['a_'+c]).astype(float)
    X['f_'+c]=f; X['d_'+c]=d; X['x_'+c]=f-d
sign=np.where(fa,1,-1)
for c in [c for c in U.columns if c.startswith('rp_')]: X[c]=U[c].astype(float)*sign
X['elo']=np.where(fa,U.elo_a-U.elo_b,U.elo_b-U.elo_a)
X['p_fav']=ip(np.minimum(U.oa,U.ob)); X['title']=U.title.astype(float); X['rounds']=U.rounds.astype(float)
# fight week
W=pd.read_csv('ufc_week/fightweek.csv'); W=W[W.in_results.astype(str)=='True']; idx={}
for _,r in W.iterrows():
    for k in (0,1,-1): idx[((pd.to_datetime(r.event_date)+pd.Timedelta(days=k)).strftime('%Y-%m-%d'),frozenset([ln(r.fighter_a),ln(r.fighter_b)]))]=r
T=pd.read_csv('tapology/picks.csv'); tk={}
for r in T.itertuples():
    for k in (0,1,-1):
        dd=(pd.to_datetime(r.event_date)+pd.Timedelta(days=k)).strftime('%Y-%m-%d')
        tk[(dd,ln(r.fighter_a),ln(r.fighter_b))]=(r.pct_a,r.pct_a_ko+r.pct_a_sub,r.pct_b_ko+r.pct_b_sub)
        tk[(dd,ln(r.fighter_b),ln(r.fighter_a))]=(r.pct_b,r.pct_b_ko+r.pct_b_sub,r.pct_a_ko+r.pct_a_sub)
fw=[];tp=[]
for j,(i,u) in enumerate(U.iterrows()):
    F,D=(u.a,u.b) if fa[j] else (u.b,u.a)
    w=idx.get((u.d,frozenset([ln(u.a),ln(u.b)])))
    sp=lambda col: [ln(x) for x in re.split(r'[;|,]',str(w[col]) if w is not None and pd.notna(w[col]) else '') if x.strip()]
    rp,mw=sp('replacement_fighter'),sp('missed_weight')
    fw.append((ln(D) in rp, ln(F) in rp, ln(D) in mw, ln(F) in mw, w is not None and str(w.catchweight)=='True'))
    t=tk.get((u.d,ln(F),ln(D))); tp.append(t if t else (np.nan,np.nan,np.nan))
X[['dog_rep','fav_rep','dog_mw','fav_mw','cw']]=np.array(fw,dtype=float)
X[['tap_fav','tap_ffin','tap_dfin']]=np.array(tp,dtype=float)
y=U.fav_won.values; yr=U.yr.values; band=U.band.str[0].values
X.to_pickle('ufc2/MX.pkl'); pd.Series(y,index=U.index).to_pickle('ufc2/My.pkl')
print('rows',len(X),'features',X.shape[1]); tr=None
for tr_end,te in [(2018,(2019,2021)),(2021,(2022,2023)),(2023,(2024,2026))]:
    tr=yr<=tr_end; ts=(yr>=te[0])&(yr<=te[1])
    cols=[c for c in X.columns if X.loc[tr,c].nunique()>1]
    m=HistGradientBoostingClassifier(max_depth=3,learning_rate=0.05,max_iter=300,min_samples_leaf=40,l2_regularization=1.0,random_state=0).fit(X.loc[tr,cols],y[tr])
    p=m.predict_proba(X.loc[ts,cols])[:,1]; yy=y[ts]; bb=band[ts]
    print('\ntrain<=%d test %d-%d (n=%d)'%(tr_end,te[0],te[1],ts.sum()))
    for b,lab in [('2','medium'),('3','coin')]:
        mb=bb==b
        line=[lab,'base %.0f%%(%d)'%(100*yy[mb].mean(),mb.sum())]
        for th in [.70,.75,.80]:
            s=mb&(p>=th); line.append('fav p>=%.2f: %.0f%% (%d)'%(th,100*yy[s].mean() if s.sum() else 0,s.sum()))
        for th in [.40,.35,.30]:
            s=mb&(p<=th); line.append('dog p<=%.2f: dog %.0f%% (%d)'%(th,100*(1-yy[s].mean()) if s.sum() else 0,s.sum()))
        print(' | '.join(line))
