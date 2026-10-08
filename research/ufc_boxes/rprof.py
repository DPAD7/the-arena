import pandas as pd, numpy as np
R=pd.read_csv('rounds.csv'); R['date']=pd.to_datetime(R.date); R['diff']=R.sig-R.sig_abs
X=pd.read_pickle('U5.pkl')
G={u:g for u,g in R.groupby('url')}
def prof(u,d):
    g=G.get(u)
    if g is None: return {}
    p=g[g.date<d]
    if p.date.nunique()<2: return {}
    r1=p[p.rnd==1]; late=p[p.rnd>=3]; r2=p[p.rnd==2]
    out=dict(r1_diff=r1['diff'].mean(), r1_out=r1.sig.mean(), r1_kdabs=r1.kd_abs.mean(), r1_kd=r1.kd.mean(),
             late_diff=late['diff'].mean() if len(late) else np.nan,
             fade=(late.sig.mean()-r1.sig.mean()) if len(late) else np.nan,
             late_abs_up=(late.sig_abs.mean()-r1.sig_abs.mean()) if len(late) else np.nan,
             r2_diff=r2['diff'].mean() if len(r2) else np.nan, ctrl_r1=r1.ctrl.mean())
    return out
rows=[]
for r in X.itertuples():
    a=prof(r.a_url,r.date); b=prof(r.b_url,r.date)
    rows.append({('rp_'+k):a.get(k,np.nan)-b.get(k,np.nan) for k in ('r1_diff','r1_out','r1_kdabs','r1_kd','late_diff','fade','late_abs_up','r2_diff','ctrl_r1')})
N=pd.DataFrame(rows); X=pd.concat([X.reset_index(drop=True),N],axis=1); X.to_pickle('U6.pkl')
fo=np.minimum(X.oa,X.ob); fa=(X.oa<X.ob).values; mc=(fo>-300).values; won=X.fav_won.values
print('ALL BOUTS (no odds): side with the edge wins | MEDIUM+COIN from the favorite: fav with edge / dog with edge')
for c in N.columns:
    v=X[c].values; sgn=-1 if c in ('rp_r1_kdabs','rp_late_abs_up') else 1; v=v*sgn
    T=(X.yr<=2022).values; cut=np.nanquantile(np.abs(v[T]),2/3)
    out=[]
    for yl,yrs in (('19-22',range(2019,2023)),('23',[2023]),('24',[2024]),('25-26',[2025,2026])):
        m=X.yr.isin(yrs).values&~np.isnan(v)&(np.abs(v)>=cut)
        w=np.where(v[m]>0,X.a_won.values[m],1-X.a_won.values[m]); out.append(f"{yl} {w.mean()*100:.0f}%({m.sum()})")
    fv=np.where(fa,v,-v); o2=[]
    for yl,yrs in (('20-23',[2020,2021,2022,2023]),('24',[2024]),('25-26',[2025,2026])):
        s=mc&X.yr.isin(yrs).values
        hi=s&(fv>=cut); lo=s&(fv<=-cut)
        o2.append(f"{yl} fav {won[hi].mean()*100:.0f}%({hi.sum()}) dog {(1-won[lo]).mean()*100:.0f}%({lo.sum()})")
    print(f"{c:16s} cut {cut:5.2f} | "+' | '.join(out)+' || '+' | '.join(o2))
