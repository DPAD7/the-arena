import pandas as pd, numpy as np
X=pd.read_pickle('ml/X.pkl'); X=X[~X.tie].reset_index(drop=True)
G=pd.read_csv('intang/games.csv'); G=G[(G.game_type=='REG')]
# usual starter: most starts in the team's earlier games this season (last season early)
starts={}
for r in G.sort_values(['season','week']).itertuples():
    for t,q in ((r.home_team,r.home_qb_id),(r.away_team,r.away_qb_id)): starts.setdefault((t,r.season),[]).append((r.week,q))
def backup(t,s,w,q):
    p=[x for wk,x in starts.get((t,s),[]) if wk<w]
    if len(p)<2: p=[x for wk,x in starts.get((t,s-1),[])][-8:]+p
    if not p: return 0
    usual=max(set(p),key=p.count); return int(q!=usual and p.count(usual)>=3)
X['h_backup']=[backup(r.home,r.season,r.week,r.h_qb) for r in X.itertuples()]
X['a_backup']=[backup(r.away,r.season,r.week,r.a_qb) for r in X.itertuples()]
def boxes(me,op,home_flag):
    g=lambda c: X[me+c].astype(float); o=lambda c: X[op+c].astype(float)
    B={}
    B['epa']=g('o_epa')-g('d_epa')-(o('o_epa')-o('d_epa'))>=0.10
    B['off_epa']=g('o_epa')-o('o_epa')>=0.08
    B['def_epa']=o('d_epa')-g('d_epa')>=0.08
    B['pass_off']=g('o_pepa')-o('o_pepa')>=0.10
    B['pass_def']=o('d_pepa')-g('d_pepa')>=0.10
    B['sr']=(g('o_sr')-g('d_sr'))-(o('o_sr')-o('d_sr'))>=0.04
    B['pd']=(g('pf')-g('pa'))-(o('pf')-o('pa'))>=7
    B['win']=g('win')-o('win')>=0.25
    B['form']=g('l3_pd')-o('l3_pd')>=10
    B['to']=(g('d_to')-g('o_to'))-(o('d_to')-o('o_to'))>=0.75
    B['sacks']=(g('d_sack')-g('o_sack'))-(o('d_sack')-o('o_sack'))>=0.03
    B['opp_backup']=(X[op+'backup']==1)&(X[me+'backup']==0)
    B['home']=pd.Series(home_flag,index=X.index)
    B['rest']=(X.rest>=3) if home_flag else (X.rest<=-3)
    return pd.DataFrame({k:v.fillna(False).astype(int) if hasattr(v,'fillna') else v for k,v in B.items()})
H=boxes('h_','a_',True); A=boxes('a_','h_',False)
net=H.sum(axis=1)-A.sum(axis=1); X['lead']=net.abs(); X['pw']=np.where(net>0,X.home_won,1-X.home_won); X['net']=net
tr=X.season<=2021
keep=[]
for c in H.columns:
    w=pd.concat([X.home_won[tr&(H[c]==1)],1-X.home_won[tr&(A[c]==1)]])
    print('%-10s %4d %.0f%%'%(c,len(w),100*w.mean()))
    if len(w)>=100 and w.mean()>=0.55: keep.append(c)
print('kept on 2016-21:',keep)
net=H[keep].sum(axis=1)-A[keep].sum(axis=1); lead=net.abs(); pw=np.where(net>0,X.home_won,1-X.home_won)
cut=None
for k in range(2,15):
    m=tr&(lead>=k)
    if m.sum()>=60 and pw[m].mean()>=0.75: cut=k; break
print('cutoff locked on 2016-21: lead %s+ -> %.0f%% (%d)'%(cut,100*pw[tr&(lead>=cut)].mean(),(tr&(lead>=cut)).sum()))
for lab,yrs in [('2022-23 BLIND',(2022,2023)),('2024-25 BLIND',(2024,2025)),('2026 BLIND',(2026,2026))]:
    m=(X.season>=yrs[0])&(X.season<=yrs[1]); s=m&(lead>=cut)
    print('%s: %.0f%% (%d of %d games, %.1f a week)'%(lab,100*pw[s].mean(),s.sum(),m.sum(),s.sum()/X[m].groupby(['season','week']).ngroups))
for k in range(cut-2,cut+3):
    print(' lead %d+:'%k,' | '.join('%s %.0f%% (%d)'%(y,100*pw[(X.season.between(*r))&(lead>=k)].mean(),((X.season.between(*r))&(lead>=k)).sum()) for y,r in [('16-21',(2016,2021)),('22-23',(2022,2023)),('24-25',(2024,2025)),('26',(2026,2026))]))
X['mlead']=lead; X['mpw']=pw; X.to_pickle('ml/XB.pkl'); H[keep].to_pickle('ml/H.pkl'); A[keep].to_pickle('ml/A.pkl')
