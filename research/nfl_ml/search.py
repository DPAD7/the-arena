import pandas as pd, numpy as np, itertools
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
X=pd.read_pickle('ml/XQ.pkl')
tr=(X.season<=2021).values; y=X.home_won.values
eras=[(2016,2021),(2022,2023),(2024,2025),(2026,2026)]
F=[c[2:] for c in X.columns if c.startswith('h_') and c[2:] not in('qb','coach') and 'a_'+c[2:] in X.columns]
Z=pd.DataFrame({c:X['h_'+c].astype(float)-X['a_'+c].astype(float) for c in F}); Z['rest']=X.rest; Z['div']=X['div']
Z=Z.fillna(0)
def show(lab,p,mask):
    c=np.maximum(p,1-p); pw=np.where(p>=0.5,y,1-y); r=[]
    for a,b in eras:
        m=mask&(X.season.between(a,b).values); r.append((pw[m].mean() if m.sum() else np.nan,m.sum()))
    ok=all(v>=0.75 for v,n in r[:3])
    print(('** ' if ok else '   ')+'%-40s'%lab+' | '.join('%.0f%% (%d)'%(100*v,n) for v,n in r))
    return ok
models={'logit':LogisticRegression(C=0.3,max_iter=5000),'logit_l1':LogisticRegression(C=0.1,penalty='l1',solver='liblinear',max_iter=5000),
        'gbm':HistGradientBoostingClassifier(max_depth=2,learning_rate=0.05,max_iter=200,min_samples_leaf=40,random_state=0)}
P={}
for k,m in models.items():
    m.fit(Z[tr],y[tr]); P[k]=m.predict_proba(Z)[:,1]
P['avg']=(P['logit']+P['gbm'])/2
wk=X.week.values
for k,p in P.items():
    c=np.maximum(p,1-p)
    for th in (0.72,0.75,0.78,0.8):
        cut_ok=c>=th
        show(f'{k} p>={th}',p,cut_ok)
        show(f'{k} p>={th} wk4+',p,cut_ok&(wk>=4))
