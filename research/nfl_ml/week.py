import pandas as pd, numpy as np, json, pickle, sys
B='/private/tmp/claude-501/-Users-joe-Desktop-the-arena/3f4a5d15-c5a9-4028-a759-343c1831a343/scratchpad/'
src=open(B+'ml/build.py').read(); exec(src[:src.index('out=[]')])
qsrc=open(B+'ml/qb.py').read().replace("f'nfv/","B+f'nfv/"); exec(qsrc[:qsrc.index("X=pd.read_pickle")])
i=qsrc.index('def qprof'); j=qsrc.index('for side in'); exec(qsrc[i:j])
S,WK=2026,int(sys.argv[1])
GA=pd.read_csv(B+'intang/games.csv'); g=GA[(GA.season==S)&(GA.week==WK)&(GA.game_type=='REG')]
PL=pd.read_csv(B+'intang/players.csv'); e2g={str(int(r.espn_id)):r.gsis_id for r in PL.itertuples() if pd.notna(r.espn_id) and pd.notna(r.gsis_id)}
DEP=json.load(open('/Users/joe/Desktop/the arena/site/depth.json')); AL={'LA':'LAR','WAS':'WSH','JAX':'JAX'}
def starter(team,fallback):
    d=DEP.get(AL.get(team,team)) or DEP.get(team) or {}
    s=d.get('starter'); nm=next((q['name'] for q in d.get('qbs',[]) if q['id']==s),None)
    return (e2g.get(str(s),fallback), nm)
starts={}
for r in GA[GA.game_type=='REG'].sort_values(['season','week']).itertuples():
    for t,q in ((r.home_team,r.home_qb_id),(r.away_team,r.away_qb_id)):
        if pd.notna(q) and not (r.season==S and r.week>=WK): starts.setdefault((t,r.season),[]).append(q)
def backup(t,q):
    p=starts.get((t,S),[]); p=(starts.get((t,S-1),[])[-8:]+p) if len(p)<2 else p
    if not p: return 0
    u=max(set(p),key=p.count); return int(q!=u and p.count(u)>=3)
m,cols=pickle.load(open(B+'ml/model.pkl','rb'))
out=[]
for r in g.itertuples():
    h,a=prof(r.home_team,S,WK),prof(r.away_team,S,WK)
    hq,hn=starter(r.home_team,r.home_qb_id); aq,an=starter(r.away_team,r.away_qb_id)
    hqe,hcp,_=qprof(hq,S,WK); aqe,acp,_=qprof(aq,S,WK)
    h.update(qe=hqe,cp=hcp,backup=backup(r.home_team,hq)); a.update(qe=aqe,cp=acp,backup=backup(r.away_team,aq))
    z={c:(h.get(c,np.nan) if c not in('rest','div') else 0)-(a.get(c,np.nan) if c not in('rest','div') else 0) for c in cols}
    z['rest']=(r.home_rest or 0)-(r.away_rest or 0); z['div']=r.div_game
    Z=pd.DataFrame([z])[cols].fillna(0); p=m.predict_proba(Z)[0,1]
    pick,conf=(r.home_team,p) if p>=0.5 else (r.away_team,1-p)
    contrib=dict(zip(cols,m.coef_[0]*Z.values[0]))
    sgn=1 if p>=0.5 else -1
    LAB={'qe':('QB play (EPA per dropback)','{:+.2f}'),'o_sr':('Offense success rate','{:.0%}'),'d_epa':('Defense, EPA allowed per play','{:+.2f}'),'d_pepa':('Pass defense, EPA allowed','{:+.2f}'),
         'l3_win':('Last 3 games, win %','{:.0%}'),'backup':('Backup QB starting','{:.0f}'),'o_sack':('Sacks taken per dropback','{:.1%}'),'win':('Win % this season','{:.0%}'),
         'o_pepa':('Passing offense (EPA)','{:+.2f}'),'o_epa':('Offense EPA per play','{:+.2f}'),'d_sr':('Defense success rate allowed','{:.0%}'),'o_repa':('Rushing offense (EPA)','{:+.2f}'),
         'pf':('Points per game','{:.1f}'),'pa':('Points allowed per game','{:.1f}'),'o_to':('Turnovers per game','{:.1f}'),'d_to':('Takeaways per game','{:.1f}'),'d_sack':('Sacks per dropback','{:.1%}'),'l3_pd':('Last 3 games, point margin','{:+.1f}')}
    hv,av=h,a
    why=[];against=[]
    for k,v in sorted(contrib.items(),key=lambda kv:-abs(kv[1])):
        if k not in LAB or v==0: continue
        lab,f=LAB[k]; hh,aa=hv.get(k),av.get(k)
        if hh is None or aa is None or hh!=hh or aa!=aa: continue
        pk,ot=(r.home_team,r.away_team) if p>=0.5 else (r.away_team,r.home_team)
        pv,ov=(hh,aa) if p>=0.5 else (aa,hh)
        if k=='backup':
            if ov==1 and pv==0: txt='%s is starting a backup QB'%ot
            else: continue
        else: txt='%s: %s %s, %s %s'%(lab,pk,f.format(pv),ot,f.format(ov))
        (why if v*sgn>0 else against).append((abs(v),txt))
    out.append((round(conf,3),pick,r.away_team,r.home_team,an,hn,r.gameday,[t for _,t in why[:4]],[t for _,t in against[:2]]))
for o in sorted(out,reverse=True): print(o[:2],o[7],o[8])
json.dump(out,open(B+f'ml/week{WK}.json','w'))
