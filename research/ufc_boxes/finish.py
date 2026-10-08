import pandas as pd, numpy as np
U=pd.read_pickle('ufc2/BOX.pkl'); U['lead']=U.net.abs(); U['pick_won']=np.where(U.net>0,U.fav_won,1-U.fav_won)
m=U.method.astype(str); U['fin']=(~m.str.contains('DEC')).astype(int)
pa=U.net>0  # pick is the fav side? map pick/opp to a/b
fa=(U.oa<U.ob).values
pick_a=np.where(U.net.values>0,fa,~fa)
P=lambda c: np.where(pick_a,U['a_'+c],U['b_'+c]).astype(float)
O=lambda c: np.where(pick_a,U['b_'+c],U['a_'+c]).astype(float)
wc=U.wc.astype(str); women=wc.str.contains('Women').values
heavy=(wc.str.contains('Heavyweight')|wc.str.contains('Light Heavyweight')|wc.str.contains('Middleweight')).values
def rate(wins,n): return np.where(n>0,wins/np.maximum(n,1),np.nan)
FB=pd.DataFrame(index=U.index)
FB['pick_ko_rate']=rate(P('ko_wins')+P('sub_wins'),P('wins'))>=0.6         # finishes most of his wins
FB['pick_kd']=P('kdpm')>=0.5
FB['pick_sub']=P('subpm')>=1.0
FB['opp_kod2']=O('been_kod')>=2
FB['opp_kod_last']=O('last_kod')==1
FB['opp_35']=O('age')>=35
FB['opp_absorbs']=O('sapm')>=4.5
FB['opp_weak_tddef']=(O('tddef')<0.55)&(P('tdpm')>=1.5)
FB['opp_lost_by_fin']=O('losses')-0>=1   # placeholder refined below
FB['heavy_class']=heavy
FB['not_women']=~women
FB['opp_dec_fighter']=rate(O('dec_wins'),O('wins'))>=0.6
FB=FB.drop(columns=['opp_lost_by_fin','opp_dec_fighter']).fillna(False).astype(int)
U['fb_n']=FB.sum(1)
def show(lab,m,col):
    s=U[m]; w=s[col]
    print('%-46s %4d %.0f%% | '%(lab,len(s),100*w.mean())+' | '.join('%s %.0f%% (%d)'%(q,100*w[s.per==q].mean() if (s.per==q).sum() else 0,(s.per==q).sum()) for q in ['10-18','19-21','22-23','24-26']))
print('finish boxes:',list(FB.columns))
U['pick_fin']=((U.pick_won==1)&(U.fin==1)).astype(int)
print('\nPICK WINS BY FINISH (box lead 5+), by finish-box count:')
for k in range(3,9): show(' lead 5+, finish boxes %d+'%k,(U.lead>=5)&(U.fb_n>=k),'pick_fin')
print('\nPICK WINS BY FINISH (box lead 7+):')
for k in range(3,9): show(' lead 7+, finish boxes %d+'%k,(U.lead>=7)&(U.fb_n>=k),'pick_fin')
print('\nFIGHT ENDS INSIDE THE DISTANCE (any lead), by finish-box count:')
for k in range(3,10): show(' finish boxes %d+'%k,U.fb_n>=k,'fin')
print('\nsingle finish boxes -> pick wins by finish (lead 5+):')
for c in FB.columns: show(' '+c,(U.lead>=5)&(FB[c]==1),'pick_fin')
U['fb_n'].to_pickle('ufc2/FBN.pkl'); FB.to_pickle('ufc2/FB.pkl')
