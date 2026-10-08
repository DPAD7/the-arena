"""Elo-style rating for every UFC fighter from his whole UFC history (history.csv, incl. pre-2019),
rating taken BEFORE each bout. Finishes move ratings more than decisions."""
import pandas as pd, numpy as np
H=pd.read_csv('history.csv'); H['date']=pd.to_datetime(H.date)
# one row per bout (dedupe the two sides)
H=H[H.result.isin(['W','L','D'])]
H['pair']=H.apply(lambda r: tuple(sorted([r.fighter_url,r.opponent_url]))+(str(r.date.date()),),axis=1)
B=H.sort_values('date').drop_duplicates('pair')
R={}; pre={}
K0=40
for r in B.itertuples():
    a,b=r.fighter_url,r.opponent_url
    ra,rb=R.get(a,1500.0),R.get(b,1500.0)
    pre[(a,r.date)]=(ra,rb); pre[(b,r.date)]=(rb,ra)
    ea=1/(1+10**((rb-ra)/400))
    sa=1.0 if r.result=='W' else 0.0 if r.result=='L' else 0.5
    k=K0*(1.25 if any(x in str(r.method) for x in ('KO','SUB')) else 1.0)
    R[a]=ra+k*(sa-ea); R[b]=rb+k*((1-sa)-(1-ea))
X=pd.read_pickle('U4.pkl')
ea=[];eb=[]
for r in X.itertuples():
    v=pre.get((r.a_url,r.date)); ea.append(v[0] if v else np.nan); eb.append(v[1] if v else np.nan)
X['elo_a']=ea; X['elo_b']=eb; X['elo_gap']=X.elo_a-X.elo_b
X.to_pickle('U5.pkl')
fo=np.minimum(X.oa,X.ob); fa=X.oa<X.ob
g=np.where(fa,X.elo_gap,-X.elo_gap)
for lab,m in (('all',fo<0),('medium',(fo>-300)&(fo<=-150)),('coin',fo>-150)):
    out=[]
    for yl,yrs in (('20-23',[2020,2021,2022,2023]),('24',[2024]),('25-26',[2025,2026])):
        s=m&X.yr.isin(yrs)
        hi=s&(g>=100); lo=s&(g<=-100)
        out.append(f"{yl}: fav Elo +100 → fav {X.fav_won[hi].mean()*100:.0f}%({hi.sum()}) | dog Elo +100 → dog {(~X.fav_won[lo]).mean()*100:.0f}%({lo.sum()})")
    print(lab,' || '.join(out))
# Elo alone, no odds: higher Elo wins
for yl,yrs in (('2019-22',range(2019,2023)),('2023',[2023]),('2024',[2024]),('2025',[2025]),('2026',[2026])):
    s=X[X.yr.isin(yrs)&(X.elo_gap.abs()>=150)]
    print(yl,'Elo gap 150+, higher wins', f"{np.where(s.elo_gap>0,s.a_won,1-s.a_won).mean()*100:.0f}% ({len(s)})")
