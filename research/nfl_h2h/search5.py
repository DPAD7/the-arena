import pandas as pd, numpy as np, itertools
X=pd.read_pickle('X5.pkl')
F=[c for c in X.columns if c[:2] in ('o_','d_','m_','l_')]
tr=(X.yr<=2023).values; v1=(X.yr==2024).values; v2=(X.yr==2025).values; te=(X.yr==2026).values
won=X.won.values.astype(bool); p=X.p.values; po=X.po.values
conds={}
for f in F:
    v=X[f].values.astype(float); a=np.abs(v[tr & ~np.isnan(v)])
    if len(a)<80: continue
    for q in (0.5,0.67,0.83):
        c=np.quantile(a,q)
        if c==0: continue
        vv=np.nan_to_num(v,nan=0)
        conds[f"{f}>={c:.3g}"]=vv>=c; conds[f"{f}<=-{c:.3g}"]=vv<=-c
names=list(conds); M=np.array([conds[n] for n in names]); print(len(names),'conditions')
def ok(m, w=won):
    a=m&tr; n=a.sum()
    if n<30 or w[a].mean()<0.68: return None
    b=m&v1; c=m&v2
    if b.sum()<15 or c.sum()<15: return None
    if w[b].mean()<0.68 or w[c].mean()<0.68: return None
    return True
def row(label,m):
    h=m&(v1|v2); exp=(p[h]/(p[h]+po[h])).mean(); prof=((won[h]*(100/p[h]-100))-(~won[h])*100).sum()
    t=m&te
    return (label,(m&tr).sum(),round(won[m&tr].mean()*100,1),(m&v1).sum(),round(won[m&v1].mean()*100,1),(m&v2).sum(),round(won[m&v2].mean()*100,1),
            round(won[h].mean()*100,1),round(exp*100,1),round(prof),t.sum(),round(won[t].mean()*100,1) if t.sum() else None)
res=[]; masks=[]
for i,n in enumerate(names):
    if ok(M[i]): res.append(row(n,M[i])); masks.append(M[i])
base=lambda n: n.split('>=')[0].split('<=')[0]
for i,j in itertools.combinations(range(len(names)),2):
    if base(names[i])==base(names[j]): continue
    m=M[i]&M[j]
    if ok(m): res.append(row(names[i]+' & '+names[j],m)); masks.append(m)
R=pd.DataFrame(res,columns=['rule','n21-23','w21-23','n24','w24','n25','w25','hold%','price%','$hold','n26','w26'])
R['edge']=R['hold%']-R['price%']
R.to_pickle('search5.pkl'); np.save('search5_masks.npy',np.array(masks))
print(len(R),'rules hold 68%+ in 2021-23 AND blind 2024 AND blind 2025')
# luck: scramble 2024 and 2025 outcomes, count how many of ALL conditions/pairs would pass
rng=np.random.default_rng(3); fakes=[]
idx=np.where(v1|v2)[0]
for t in range(10):
    w=won.copy(); w[idx]=rng.permutation(w[idx]); cnt=0
    for i in range(len(names)):
        if ok(M[i],w): cnt+=1
    for i,j in itertools.combinations(range(len(names)),2):
        if base(names[i])!=base(names[j]) and ok(M[i]&M[j],w): cnt+=1
    fakes.append(cnt)
print('by luck (scrambled 2024+2025):', fakes)
pd.set_option('display.width',260)
print(R.sort_values(['edge'],ascending=False).head(25).to_string(index=False))
