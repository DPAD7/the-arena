"""NFL moneyline: pre-game team profile from earlier games only (this season, blended with last
season early on), one row per game from the home side. No odds used for the read."""
import pandas as pd, numpy as np
B='/private/tmp/claude-501/-Users-joe-Desktop-the-arena/3f4a5d15-c5a9-4028-a759-343c1831a343/scratchpad/'
G=pd.read_csv(B+'intang/games.csv'); G=G[(G.season>=2016)&G.home_score.notna()&(G.game_type=='REG')].copy()
cols=['season','week','season_type','game_id','posteam','defteam','epa','success','pass','rush','sack','interception','fumble_lost','qb_epa','pass_attempt','qb_scramble','penalty']
P=pd.concat([pd.read_parquet(B+f'nfv/pbp_{y}.parquet',columns=[c for c in cols if c!='penalty']) for y in range(2016,2027)])
P=P[(P.season_type=='REG')&P.posteam.notna()&P.epa.notna()&((P['pass']==1)|(P.rush==1))]
P['to']=P.interception.fillna(0)+P.fumble_lost.fillna(0)
P['pepa']=np.where(P['pass']==1,P.epa,np.nan); P['repa']=np.where(P.rush==1,P.epa,np.nan)
off=P.groupby(['season','week','posteam']).agg(o_epa=('epa','mean'),o_sr=('success','mean'),o_pepa=('pepa','mean'),o_repa=('repa','mean'),o_to=('to','sum'),o_sack=('sack','mean'),n=('epa','size')).reset_index().rename(columns={'posteam':'team'})
dfn=P.groupby(['season','week','defteam']).agg(d_epa=('epa','mean'),d_sr=('success','mean'),d_pepa=('pepa','mean'),d_repa=('repa','mean'),d_to=('to','sum'),d_sack=('sack','mean')).reset_index().rename(columns={'defteam':'team'})
W=off.merge(dfn,on=['season','week','team'])
# per-game points and results
rows=[]
for r in G.itertuples():
    for t,o,pf,pa,home in ((r.home_team,r.away_team,r.home_score,r.away_score,1),(r.away_team,r.home_team,r.away_score,r.home_score,0)):
        rows.append(dict(season=r.season,week=r.week,team=t,pf=pf,pa=pa,win=float(pf>pa)+0.5*(pf==pa)))
R=pd.DataFrame(rows); W=W.merge(R,on=['season','week','team'],how='left')
W=W.sort_values(['team','season','week'])
F=['o_epa','o_sr','o_pepa','o_repa','o_to','o_sack','d_epa','d_sr','d_pepa','d_repa','d_to','d_sack','pf','pa','win']
def prof(team,season,week):
    cur=W[(W.team==team)&(W.season==season)&(W.week<week)]
    prev=W[(W.team==team)&(W.season==season-1)]
    if len(cur)>=4 or prev.empty: base=cur
    else: base=pd.concat([prev.tail(8-2*len(cur)) if len(cur)<4 else prev.iloc[0:0],cur])
    if base.empty: return {k:np.nan for k in F}|{'g':0}
    v={k:base[k].mean() for k in F}; v['g']=len(cur)
    v['l3_win']=cur.tail(3).win.mean() if len(cur) else np.nan
    v['l3_pd']=(cur.tail(3).pf-cur.tail(3).pa).mean() if len(cur) else np.nan
    return v
out=[]
for r in G.itertuples():
    if r.season<2016: continue
    h,a=prof(r.home_team,r.season,r.week),prof(r.away_team,r.season,r.week)
    row=dict(season=r.season,week=r.week,home=r.home_team,away=r.away_team,home_won=float(r.home_score>r.away_score),tie=r.home_score==r.away_score,
             rest=(r.home_rest or 0)-(r.away_rest or 0),div=r.div_game,home_ml=r.home_moneyline,away_ml=r.away_moneyline,
             h_qb=r.home_qb_id,a_qb=r.away_qb_id,h_coach=r.home_coach,a_coach=r.away_coach,roof=r.roof,wind=r.wind)
    for k,v in h.items(): row['h_'+k]=v
    for k,v in a.items(): row['a_'+k]=v
    out.append(row)
X=pd.DataFrame(out); X.to_pickle(B+'ml/X.pkl'); print(len(X),X.season.min(),X.season.max())
