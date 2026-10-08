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
    out.append((round(conf,3),pick,r.away_team,r.home_team,an,hn,r.gameday))
for o in sorted(out,reverse=True): print(o)
json.dump(out,open(B+f'ml/week{WK}.json','w'))
