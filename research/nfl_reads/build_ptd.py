"""1+ passing TD: one row per starting QB per game (2016->), pre-game features only."""
import pandas as pd, numpy as np
import sys
B=sys.argv[1].rstrip('/')+'/'   # a folder holding nfv/pbp_<year>.parquet and intang/games.csv
cols=['season','week','season_type','game_id','posteam','defteam','passer_player_id','pass_touchdown','qb_dropback','qb_epa','pass_attempt','yardline_100','drive','touchdown','epa','roof','wind','home_team','fixed_drive','fixed_drive_result']
P=pd.concat([pd.read_parquet(B+f'nfv/pbp_{y}.parquet',columns=cols) for y in range(2016,2027)])
P=P[P.season_type=='REG']
G=pd.read_csv(B+'intang/games.csv'); G=G[(G.season>=2016)&(G.game_type=='REG')]
# QB game lines
Q=P[P.passer_player_id.notna()].groupby(['season','week','game_id','posteam','passer_player_id']).agg(db=('qb_dropback','sum'),ptd=('pass_touchdown','sum'),qe=('qb_epa','mean')).reset_index()
# team offense per game: drives, red-zone trips, TD drives
d=P.dropna(subset=['fixed_drive']).groupby(['season','week','game_id','posteam','fixed_drive']).agg(rz=('yardline_100',lambda x:(x<=20).any()),res=('fixed_drive_result','first')).reset_index()
d['td']=d.res.eq('Touchdown')
TO=d.groupby(['season','week','game_id','posteam']).agg(drv=('td','size'),rz=('rz','sum'),tdd=('td','sum')).reset_index()
pt=P.groupby(['season','week','game_id','posteam']).agg(team_ptd=('pass_touchdown','sum'),opp=('defteam','first')).reset_index()
TO=TO.merge(pt,on=['season','week','game_id','posteam'])
# defense allowed per game
DA=TO.rename(columns={'posteam':'x','opp':'def'}).groupby(['season','week','def']).agg(a_ptd=('team_ptd','sum'),a_rz=('rz','sum'),a_tdd=('tdd','sum'),a_drv=('drv','sum')).reset_index()
Q=Q.sort_values(['season','week']); TO=TO.sort_values(['season','week']); DA=DA.sort_values(['season','week'])
QG={q:g for q,g in Q.groupby('passer_player_id')}; TG={t:g for t,g in TO.groupby('posteam')}; DG={t:g for t,g in DA.groupby('def')}
key=lambda s,w: s*100+w
def last(g,s,w,n):
    if g is None: return None
    k=g.season*100+g.week; return g[k<key(s,w)].tail(n)
rows=[]
starters=[]
for r in G.itertuples():
    for team,opp,qb,home in ((r.home_team,r.away_team,r.home_qb_id,1),(r.away_team,r.home_team,r.away_qb_id,0)):
        if pd.isna(qb): continue
        act=Q[(Q.game_id==r.game_id)&(Q.passer_player_id==qb)] if False else None
        q=last(QG.get(qb),r.season,r.week,16); t=last(TG.get(team),r.season,r.week,8); dd=last(DG.get(opp),r.season,r.week,8)
        row=dict(game_id=r.game_id,season=r.season,week=r.week,team=team,opp=opp,qb=qb,home=home,roof=r.roof,wind=r.wind if r.wind==r.wind else 0,div=r.div_game)
        if q is not None and len(q):
            q2=q[q.db>=10]; row.update(q_g=len(q2),q_tdpg=q2.ptd.mean() if len(q2) else np.nan,q_hit=(q2.ptd>=1).mean() if len(q2) else np.nan,q_hit8=(q2.tail(8).ptd>=1).mean() if len(q2) else np.nan,q_qe=(q2.qe*q2.db).sum()/max(q2.db.sum(),1) if len(q2) else np.nan,q_db=q2.db.mean() if len(q2) else np.nan,q_streak=int(((q2.ptd>=1)[::-1].cumprod()).sum()) if len(q2) else 0)
        if t is not None and len(t): row.update(t_rz=t.rz.mean(),t_tdd=t.tdd.mean(),t_ptd=t.team_ptd.mean(),t_rzconv=t.tdd.sum()/max(t.rz.sum(),1))
        if dd is not None and len(dd): row.update(d_ptd=dd.a_ptd.mean(),d_rz=dd.a_rz.mean(),d_tdd=dd.a_tdd.mean())
        rows.append(row)
X=pd.DataFrame(rows)
act=Q.groupby(['game_id','passer_player_id']).ptd.sum().rename('ptd_act').reset_index()
X=X.merge(act,left_on=['game_id','qb'],right_on=['game_id','passer_player_id'],how='left'); X['hit']=(X.ptd_act.fillna(0)>=1).astype(int)
X=X[X.passer_player_id.notna()]   # he actually played
X.to_pickle(B+'ptd/X.pkl'); print(len(X), X.hit.mean().round(3), X.groupby('season').hit.mean().round(3).to_dict())
