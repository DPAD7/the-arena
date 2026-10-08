"""Pro-record features (all promotions) as of each bout, and new boxes; retest by era and per card."""
import pandas as pd, numpy as np
P=pd.read_csv('sherdog/people.csv'); FS=pd.read_csv('sherdog/fights.csv'); FS['date']=pd.to_datetime(FS.date,errors='coerce')
FS=FS[FS.result.isin(['win','loss','draw'])].sort_values('date')
page={r.fighter_url:r.page_url for r in P.itertuples() if isinstance(r.fighter_url,str)}
G={u:g for u,g in FS.groupby('page_url')}
def pro(u,d):
    g=G.get(page.get(u))
    out=dict(pw=np.nan,pl=np.nan,pfin=np.nan,pkod=np.nan,pstreak=np.nan,pyrs=np.nan,psubbed=np.nan,pn=0)
    if g is None: return out
    p=g[g.date<d]
    if p.empty: return out|{'pn':0}
    w=p[p.result=='win']; l=p[p.result=='loss']; m=w.method.astype(str); lm=l.method.astype(str)
    s=0
    for r in p.result.values[::-1]:
        if r=='win' and s>=0: s+=1
        elif r=='loss' and s<=0: s-=1
        else: break
    known=m.ne('nan').sum()
    return dict(pw=len(w),pl=len(l),pfin=(m.str.contains('KO|Sub',case=False).sum()/known) if known else np.nan,
                pkod=int(lm.str.contains('KO',case=False).sum()),psubbed=int(lm.str.contains('Sub',case=False).sum()),
                pstreak=s,pyrs=(d-p.date.iloc[0]).days/365.25,pn=len(p))
U=pd.read_pickle('ufc2/BOX.pkl'); F=pd.read_pickle('ufc2/BOXF.pkl').copy(); D=pd.read_pickle('ufc2/BOXD.pkl').copy()
fa=(U.oa<U.ob).values
rows=[]
for j,r in enumerate(U.itertuples()):
    A,B=pro(r.a_url,r.date),pro(r.b_url,r.date)
    f,d=(A,B) if fa[j] else (B,A); rows.append((f,d))
def boxes(me,op):
    pct=lambda x: x['pw']/(x['pw']+x['pl']) if (x['pw']+x['pl'])>0 else np.nan
    b={}
    b['pro_winpct']=(pct(me)-pct(op))>=0.15
    b['pro_unbeaten']=(me['pl']==0)&(me['pw']>=5)&(op['pl']>=1)
    b['pro_fewer_losses']=(op['pl']-me['pl'])>=4
    b['pro_never_kod']=(me['pkod']==0)&(op['pkod']>=2)
    b['pro_finisher']=(me['pfin']>=0.7)&(op['pfin']<0.5)
    b['pro_streak']=(me['pstreak']>=4)&(op['pstreak']<=1)
    b['pro_opp_skid']=op['pstreak']<=-2
    b['pro_subbed']=(op['psubbed']>=2)&(me['psubbed']==0)
    return {k:int(bool(v)) if not (isinstance(v,float) and np.isnan(v)) else 0 for k,v in b.items()}
PF=pd.DataFrame([boxes(f,d) for f,d in rows],index=U.index); PD=pd.DataFrame([boxes(d,f) for f,d in rows],index=U.index)
F2=pd.concat([F,PF],axis=1); D2=pd.concat([D,PD],axis=1)
net=F2.sum(axis=1)-D2.sum(axis=1); U['lead']=net.abs(); U['pw']=np.where(net>0,U.fav_won,1-U.fav_won)
U['card']=U.date.dt.strftime('%Y-%m-%d'); pers=['10-18','19-21','22-23','24-26']
era=lambda s: ' | '.join('%s %.0f%% (%d)'%(q,100*s[s.per==q].pw.mean(),(s.per==q).sum()) for q in pers)
print('pro boxes single:'); 
for c in PF.columns:
    w=pd.concat([U.fav_won[PF[c]==1],1-U.fav_won[PD[c]==1]]); print('  %-18s %5d %.0f%%'%(c,len(w),100*w.mean()))
for k in range(7,13):
    s=U[U.lead>=k]; print('lead %d+: %.0f%% n=%d | %s | cards with one %.0f%%'%(k,100*s.pw.mean(),len(s),era(s),100*s.card.nunique()/U.card.nunique()))
b=U.sort_values('lead',ascending=False).groupby('card').head(1); print('best per card: %.0f%% | %s'%(100*b.pw.mean(),era(b)))
F2.to_pickle('ufc2/BOXF2.pkl'); D2.to_pickle('ufc2/BOXD2.pkl'); U[['lead','pw']].to_pickle('ufc2/LEAD2.pkl')
