"""Each defense vs the other team's No. 1 target, season-to-date; each offense's No. 1 target's yards."""
import json, numpy as np, pandas as pd
B="/private/tmp/claude-501/-Users-joe-Desktop-the-arena/3f4a5d15-c5a9-4028-a759-343c1831a343/scratchpad/"
X=pd.read_pickle(B+"intang/X6.pkl")
D=json.load(open(B+"DS.json"))+json.load(open(B+"old/DS_old.json"))
G=pd.read_csv(B+"intang/games.csv")
pb=pd.concat([pd.read_parquet(B+f"nfv/pbp_{y}.parquet",columns=["season","week","season_type","posteam","defteam","pass_attempt","receiver_player_id","passing_yards"]) for y in (2021,2022,2023,2024,2025,2026)])
pb=pb[(pb.season_type=="REG")&(pb.pass_attempt==1)&pb.receiver_player_id.notna()].copy()
pb["passing_yards"]=pb.passing_yards.fillna(0)
tg=pb.groupby(["season","week","posteam","defteam","receiver_player_id"]).agg(t=("pass_attempt","size"),y=("passing_yards","sum")).reset_index()
lead={}
for (s,tm),grp in tg.groupby(["season","posteam"]):
    for w in sorted(grp.week.unique()):
        prev=grp[grp.week<w]
        if prev.empty: prev=tg[(tg.season==s-1)&(tg.posteam==tm)]
        if prev.empty: continue
        lead[(s,w,tm)]=prev.groupby("receiver_player_id").t.sum().idxmax()
gm=tg.groupby(["season","week","posteam","defteam"]).size().reset_index()[["season","week","posteam","defteam"]]
idx=tg.set_index(["season","week","posteam","receiver_player_id"])
rec=[]
for r in gm.itertuples():
    pid=lead.get((r.season,r.week,r.posteam))
    if not pid: continue
    try: x=idx.loc[(r.season,r.week,r.posteam,pid)]; yv=float(np.sum(x.y)); tv=float(np.sum(x.t))
    except KeyError: yv,tv=0.0,0.0
    rec.append((r.season,r.week,r.posteam,r.defteam,yv,tv))
W=pd.DataFrame(rec,columns=["season","week","off","def","y","t"])
def prof(col,team,s,w):
    q=W[(W[col]==team)&(W.season==s)&(W.week<w)]
    if q.empty: q=W[(W[col]==team)&(W.season==s-1)]
    return (q.y.mean(),q.t.mean()) if len(q) else (np.nan,np.nan)
rows=[]
for r in D:
    a,h=r["S"]
    if a["home"]: a,h=h,a
    g=G[(G.season==r["yr"])&(G.week==r["wk"])&(G.away_team==a["team"])&(G.home_team==h["team"])]
    if g.empty: continue
    g=g.iloc[0]
    for me,ot in ((g.away_team,g.home_team),(g.home_team,g.away_team)):
        dy_ot,_=prof("def",ot,g.season,g.week); dy_me,_=prof("def",me,g.season,g.week)
        oy_me,t_me=prof("off",me,g.season,g.week); oy_ot,t_ot=prof("off",ot,g.season,g.week)
        rows.append({"w_dwr1":dy_ot-dy_me,"w_owr1":oy_me-oy_ot,"w_owr1t":t_me-t_ot,"w_match":(oy_me+dy_ot)-(oy_ot+dy_me)})
N=pd.DataFrame(rows); assert len(N)==len(X)
X7=pd.concat([X.reset_index(drop=True),N],axis=1); X7.to_pickle(B+"intang/X7.pkl")
for c in N.columns:
    cut=X7[X7.yr<=2023][c].abs().quantile(2/3)
    out=[]
    for lab,yrs in (("21-23",[2021,2022,2023]),("24",[2024]),("25",[2025])):
        k=X7[X7.yr.isin(yrs)&(X7[c]>=cut)]; out.append(f"{lab} {k.won.mean()*100:.0f}% ({len(k)}) price {(k.p/(k.p+k.po)).mean()*100:.0f}%")
    print(c, f"cut {cut:.1f} |", " | ".join(out))
