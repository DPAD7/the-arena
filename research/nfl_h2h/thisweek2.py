import json,re,numpy as np,pandas as pd
src=open('study5.py').read(); exec(src[:src.index('rows = []')])
X=pd.read_pickle(B+'intang/X12.pkl'); T=X[X.yr<=2023]
cut=lambda c,q=2/3: T[c].abs().quantile(q)
CUT={k:cut(k) for k in ('d_p_epa','d_yac','w_dwr1','o_epa','l_rec')}; CUT['l_price']=cut('l_price',0.33)
# WR1 allowed table (same as wr1.py)
pb=pd.concat([pd.read_parquet(B+f"nfv/pbp_{y}.parquet",columns=["season","week","season_type","posteam","defteam","pass_attempt","receiver_player_id","passing_yards"]) for y in (2025,2026)])
pb=pb[(pb.season_type=="REG")&(pb.pass_attempt==1)&pb.receiver_player_id.notna()].copy(); pb["passing_yards"]=pb.passing_yards.fillna(0)
tg=pb.groupby(["season","week","posteam","defteam","receiver_player_id"]).agg(t=("pass_attempt","size"),y=("passing_yards","sum")).reset_index()
def lead(s,w,tm):
    p=tg[(tg.season==s)&(tg.posteam==tm)&(tg.week<w)]
    if p.empty: p=tg[(tg.season==s-1)&(tg.posteam==tm)]
    return p.groupby("receiver_player_id").t.sum().idxmax() if len(p) else None
rec=[]
for (s,w,o,d),_ in tg[tg.season==2026].groupby(["season","week","posteam","defteam"]):
    pid=lead(s,w,o); x=tg[(tg.season==s)&(tg.week==w)&(tg.posteam==o)&(tg.receiver_player_id==pid)]
    rec.append((d,float(x.y.sum())))
W=pd.DataFrame(rec,columns=["def","y"]); wr1=W.groupby("def").y.mean()
G=pd.read_csv(B+"intang/games.csv"); g26=G[(G.season==2026)]
coach25={**{r.away_team:r.away_coach for r in G[G.season==2025].itertuples()},**{r.home_team:r.home_coach for r in G[G.season==2025].itertuples()}}
coach26={**{r.away_team:r.away_coach for r in g26.itertuples()},**{r.home_team:r.home_coach for r in g26.itertuples()}}
norm=lambda s:re.sub(r'[^a-z]','',(s or '').lower().replace(' jr','').replace(' sr','').replace(' iii','').replace(' ii',''))
ros=pd.read_csv(B+'nfv/roster_weekly_2026.csv'); last=ros[ros.week==ros.week.max()]
team_of={norm(r.full_name):r.team for r in last.itertuples()}
AL={'LAR':'LA','WSH':'WAS','JAC':'JAX'}; Tm=lambda t:AL.get(t,t)
def imp(c):
    c=float(c); return -c/(-c+100) if c<0 else 100/(c+100)
out=[]; READ=[]
for yr,wk,eid,home,vis,when in json.load(open(B+'wk6/events.json')):
    Bk=json.load(open(B+f'wk6/{eid}.json')); h=[x for x in Bk.get('74',[]) if x.get('cost') is not None][:2]
    if len(h)<2: continue
    teams=[Tm(home),Tm(vis)]
    tms=[team_of.get(norm(x['name'])) for x in h]
    tms=[t if t in teams else [b for b in teams if b!=(tms[1-i] if tms[1-i] in teams else None)][0] for i,t in enumerate(tms)]
    def ov(m,name):
        for x in Bk.get(m,[]):
            if x['sel']=='over' and norm(x['name'])==norm(name): return x['line']
    def recl(team): 
        L=[x['line'] for x in Bk.get('105',[]) if x['sel']=='over' and x.get('pos')!='QB' and x['line'] is not None and Tm(x.get('team') or '')==team]
        return sum(L),len(L)
    pro={t:(prof(OFF,t,2026,6),prof(DEF,t,2026,6)) for t in tms}
    sides=[]
    for i in (0,1):
        me,ot=tms[i],tms[1-i]; q,o=h[i],h[1-i]
        r_me,n_me=recl(me); r_ot,n_ot=recl(ot)
        cl=[ov('100',q['name']),ov('100',o['name'])]
        f=dict(d_p_epa=pro[ot][1]['p_epa']-pro[me][1]['p_epa'],d_yac=pro[ot][1]['yac']-pro[me][1]['yac'],w_dwr1=wr1.get(ot,np.nan)-wr1.get(me,np.nan),
               o_epa=pro[me][0]['epa']-pro[ot][0]['epa'],o_p_epa=pro[me][0]['p_epa']-pro[ot][0]['p_epa'],o_scr=pro[me][0]['scr']-pro[ot][0]['scr'],
               m_qb_repa=pro[me][0]['qb_repa']-pro[ot][1]['qb_repa'],l_rec=r_me-r_ot,l_cl=(cl[0]-cl[1]) if None not in cl else np.nan,
               l_price=imp(q['cost'])-imp(o['cost']),coach=int(coach25.get(me)!=coach26.get(me)),ncomplete=(n_me>=4 and n_ot>=4))
        sides.append(f)
    for i in (0,1):
        f,o=sides[i],sides[1-i]
        pts=0
        for k in ('d_p_epa','d_yac','w_dwr1','o_epa','l_rec'):
            v=f[k]
            if v==v and abs(v)>=CUT[k]: pts+=np.sign(v)
        pts+=f['coach']-o['coach']
        box=int(f['o_epa']>=0.1 and f['l_rec']>=45.5)+int(f['o_p_epa']>=0.207 and f['l_rec']>=33.5)+int(f['o_scr']<=-1 and f['l_rec']>=33.5)+int(f['m_qb_repa']>=0.378 and (f['l_cl'] or 0)>=2)
        f['score']=pts+2*box; f['box']=box
    a,b=sides
    lead_i=0 if a['score']>=b['score'] else 1
    out.append((h[0]['name'],h[0]['cost'],h[1]['name'],h[1]['cost'],a['score'],b['score'],h[lead_i]['name'],abs(a['score']-b['score']),round(a['l_rec'],1),a['ncomplete']))
    W=sides[lead_i]; nm=[h[0]['name'],h[1]['name']]; opp=nm[1-lead_i]; R=[]
    if W['d_p_epa']==W['d_p_epa'] and W['d_p_epa']>=CUT['d_p_epa']: R.append('Faces the softer pass defense (EPA per pass allowed)')
    if W['d_yac']==W['d_yac'] and W['d_yac']>=CUT['d_yac']: R.append('Faces a defense that gives up more yards after the catch')
    if W['w_dwr1']==W['w_dwr1'] and W['w_dwr1']>=CUT['w_dwr1']: R.append('Opponent gives up more yards to the top receiver (%+.0f a game)'%W['w_dwr1'])
    if W['o_epa']==W['o_epa'] and W['o_epa']>=CUT['o_epa']: R.append('His offense is more efficient (EPA per play)')
    if W['l_rec']==W['l_rec'] and W['l_rec']>=CUT['l_rec']: R.append('His receivers are set %.1f yards higher in total on their lines'%W['l_rec'])
    if W['box']: R.append('%d of 4 combined boxes checked'%W['box'])
    if W['coach'] and not sides[1-lead_i]['coach']: R.append('New coach for the other side')
    W['bx']=[int(W['o_epa']>=0.1 and W['l_rec']>=45.5),int(W['o_p_epa']>=0.207 and W['l_rec']>=33.5),int(W['o_scr']<=-1 and W['l_rec']>=33.5),int(W['m_qb_repa']>=0.378 and (W['l_cl'] or 0)>=2)]
    READ.append(dict(bx=W['bx'],qbs=nm,pick=nm[lead_i],lead=float(abs(a['score']-b['score'])),complete=bool(a['ncomplete']),score=[float(a['score']),float(b['score'])],why=R))
for r in sorted(out,key=lambda r:-r[7]): print(r)

import json as _j; _j.dump(READ,open(B+'intang/h2h_reads_wk.json','w'),indent=1)
