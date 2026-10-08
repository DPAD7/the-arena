import pandas as pd, numpy as np
U=pd.read_pickle('ufc2/U6.pkl'); U=U[U.oa.notna()&U.ob.notna()&(U.oa!=U.ob)].copy().reset_index(drop=True)
fa=(U.oa<U.ob).values
def side(c,me):  # me='f' fav or 'd' dog
    a,b=U['a_'+c].astype(float).values,U['b_'+c].astype(float).values
    return np.where(fa,a,b) if me=='f' else np.where(fa,b,a)
def boxes(me):
    op='d' if me=='f' else 'f'
    g=lambda c: side(c,me); o=lambda c: side(c,op)
    sg=np.where(fa,1,-1) if me=='f' else np.where(fa,-1,1)
    B={}
    B['younger3']=o('age')-g('age')>=3
    B['younger6']=o('age')-g('age')>=6
    B['opp35']=o('age')>=35
    B['abs_less']=g('sapm')<o('sapm')-0.75
    B['lands_more']=g('slpm')>o('slpm')+0.75
    B['acc']=g('acc')>o('acc')+0.05
    B['td_edge']=g('tdpm')>o('tdpm')+1
    B['tddef']=g('tddef')>o('tddef')+0.15
    B['ctrl']=g('ctrl_share')>o('ctrl_share')+0.15
    B['kd_power']=(g('kdpm')>=0.5)&(o('been_kod')>=2)
    B['chin']=(g('been_kod')==0)&(o('been_kod')>=1)
    B['opp_last_kod']=o('last_kod')==1
    B['opp_lost_last']=o('last_loss')==1
    B['streak']=g('streak')>=2
    B['opp_cold']=o('streak')<=-2
    B['layoff']=(o('layoff')>=365)&(g('layoff')<365)
    B['reach']=g('reach')-o('reach')>=3
    B['exp']=(g('ufc_mins')>=60)&(o('ufc_mins')<20)
    B['elo']=(np.where(fa,U.elo_a-U.elo_b,U.elo_b-U.elo_a)*(1 if me=='f' else -1))>=75
    for c in ['rp_r1_diff','rp_late_diff']:
        if c in U: B[c]=(U[c].astype(float).values*sg)>=8
    if 'rp_r1_kdabs' in U: B['r1_safe']=False
    return pd.DataFrame({k:np.nan_to_num(v.astype(float)) for k,v in B.items() if not isinstance(v,bool)})
F=boxes('f'); D=boxes('d')
U['fb']=F.sum(axis=1).values; U['db']=D.sum(axis=1).values; U['net']=U.fb-U.db
U['per']=pd.cut(U.yr,[2009,2018,2021,2023,2026],labels=['10-18','19-21','22-23','24-26'])
print('boxes',list(F.columns))
def show(lab,m,pick_fav=True):
    s=U[m]; w=s.fav_won if pick_fav else 1-s.fav_won
    print('%-44s %4d %.0f%% | '%(lab,len(s),100*w.mean())+' | '.join('%s %.0f%% (%d)'%(q,100*w[s.per==q].mean() if (s.per==q).sum() else 0,(s.per==q).sum()) for q in ['10-18','19-21','22-23','24-26']))
for b,lab in [('2','medium'),('3','coin')]:
    M=U.band.str.startswith(b)
    show(lab+' base',M)
    for k in range(3,9):
        show(' fav net +%d'%k,M&(U.net>=k))
    for k in range(2,7):
        show(' DOG net +%d (pick dog)'%k,M&(U.net<=-k),False)
    for k in range(5,10):
        show(' fav %d+ boxes, dog <=2'%k,M&(U.fb>=k)&(U.db<=2))
    print()
U.to_pickle('ufc2/BOX.pkl'); F.to_pickle('ufc2/BOXF.pkl'); D.to_pickle('ufc2/BOXD.pkl')
