import json, sys, unicodedata, numpy as np, pandas as pd
src=open('feat.py').read(); exec(src[:src.index('rows = []')])   # loads F, FT, H, form(), rates()
D=pd.Timestamp(sys.argv[2] if len(sys.argv)>2 else '2026-10-10')
card=json.load(open(sys.argv[1]))
def norm(s): return unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower().replace('.','').strip()
names=FT.reset_index()[['fighter_url','name']]; names['n']=names.name.map(norm)
# prefer the fighter with the most recent UFC fight when names repeat
last=H.groupby('fighter_url').date.max()
def url(nm):
    m=names[names.n==norm(nm)]
    if len(m)==0:
        ln=norm(nm).split()[-1]; m=names[names.n.str.split().str[-1]==ln]
        m=m[m.fighter_url.isin(last.index)]
        if len(m)>1: m=m[m.fighter_url==last.reindex(m.fighter_url).idxmax()]
    if len(m)==0: return None
    return max(m.fighter_url, key=lambda u: last.get(u,pd.Timestamp(0)))
# Elo: final rating before D
Hh=H[H.result.isin(['W','L','D'])&(H.date<D)].copy()
Hh['pair']=Hh.apply(lambda r: tuple(sorted([r.fighter_url,r.opponent_url]))+(str(r.date.date()),),axis=1)
Rt={}
for r in Hh.sort_values('date').drop_duplicates('pair').itertuples():
    a,b=r.fighter_url,r.opponent_url; ra,rb=Rt.get(a,1500.0),Rt.get(b,1500.0); ea=1/(1+10**((rb-ra)/400))
    sa=1.0 if r.result=='W' else 0.0 if r.result=='L' else 0.5; k=40*(1.25 if any(x in str(r.method) for x in ('KO','SUB')) else 1.0)
    Rt[a]=ra+k*(sa-ea); Rt[b]=rb+k*((1-sa)-(1-ea))
R=pd.read_csv('rounds.csv'); R['date']=pd.to_datetime(R.date); R['diff']=R.sig-R.sig_abs; G={u:g for u,g in R.groupby('url')}
def prof(u):
    g=G.get(u)
    if g is None: return {}
    p=g[g.date<D]
    if p.date.nunique()<2: return {}
    r1=p[p.rnd==1]; late=p[p.rnd>=3]
    return dict(r1=r1['diff'].mean(), late=late['diff'].mean() if len(late) else np.nan)
def man(u):
    ft=FT.loc[u]; dob=pd.to_datetime(ft.dob) if isinstance(ft.dob,str) else pd.NaT
    v=dict(age=(D-dob).days/365.25 if pd.notna(dob) else np.nan, reach=pd.to_numeric(ft.reach_in,errors='coerce'))
    v.update(form(u,D)); v.update(rates(u,D)); v['elo']=Rt.get(u,1500.0); v.update(prof(u)); return v
def boxes(g,o):
    G_=lambda k: g.get(k,np.nan); O=lambda k: o.get(k,np.nan)
    B={'3+ yrs younger':O('age')-G_('age')>=3,'6+ yrs younger':O('age')-G_('age')>=6,'opp 35+':O('age')>=35,
       'absorbs less':G_('sapm')<O('sapm')-0.75,'lands more':G_('slpm')>O('slpm')+0.75,'more accurate':G_('acc')>O('acc')+0.05,
       'more takedowns':G_('tdpm')>O('tdpm')+1,'better TD def':G_('tddef')>O('tddef')+0.15,'more control':G_('ctrl_share')>O('ctrl_share')+0.15,
       'KO power vs KOd opp':(G_('kdpm')>=0.5)&(O('been_kod')>=2),'never KOd, opp has':(G_('been_kod')==0)&(O('been_kod')>=1),
       'opp KOd last':O('last_kod')==1,'opp lost last':O('last_loss')==1,'win streak 2+':G_('streak')>=2,'opp lost 2+':O('streak')<=-2,
       'opp off 1yr+':(O('layoff')>=365)&(G_('layoff')<365),'reach +3':G_('reach')-O('reach')>=3,'UFC experience':(G_('ufc_mins')>=60)&(O('ufc_mins')<20),
       'higher rating':G_('elo')-O('elo')>=75,'wins R1':G_('r1')-O('r1')>=8,'wins late rounds':G_('late')-O('late')>=8}
    return [k for k,v in B.items() if bool(v) and not (isinstance(v,float) and np.isnan(v))]
PP=pd.read_csv('../sherdog/people.csv'); FS=pd.read_csv('../sherdog/fights.csv'); FS['date']=pd.to_datetime(FS.date,errors='coerce')
FS=FS[FS.result.isin(['win','loss','draw'])].sort_values('date'); PG={u:g for u,g in FS.groupby('page_url')}
byurl={r.fighter_url:r.page_url for r in PP.itertuples() if isinstance(r.fighter_url,str)}
byname={norm(r.name):r.page_url for r in PP.itertuples()}
def pro(u,nm):
    g=PG.get(byurl.get(u) or byname.get(norm(nm)))
    o=dict(pw=np.nan,pl=np.nan,pfin=np.nan,pkod=np.nan,pstreak=np.nan,psubbed=np.nan)
    if g is None: return o
    p=g[g.date<D]
    if p.empty: return o
    w=p[p.result=='win']; l=p[p.result=='loss']; m=w.method.astype(str); lm=l.method.astype(str); k=m.ne('nan').sum(); s=0
    for r in p.result.values[::-1]:
        if r=='win' and s>=0: s+=1
        elif r=='loss' and s<=0: s-=1
        else: break
    return dict(pw=len(w),pl=len(l),pfin=(m.str.contains('KO|Sub',case=False).sum()/k) if k else np.nan,pkod=int(lm.str.contains('KO',case=False).sum()),psubbed=int(lm.str.contains('Sub',case=False).sum()),pstreak=s)
def proboxes(me,op):
    pct=lambda x: x['pw']/(x['pw']+x['pl']) if (x['pw']+x['pl'])>0 else np.nan
    b={'pro win% +15':(pct(me)-pct(op))>=0.15,'pro unbeaten':(me['pl']==0)&(me['pw']>=5)&(op['pl']>=1),'pro 4+ fewer losses':(op['pl']-me['pl'])>=4,
       'pro never KOd':(me['pkod']==0)&(op['pkod']>=2),'pro finisher':(me['pfin']>=0.7)&(op['pfin']<0.5),'pro streak 4+':(me['pstreak']>=4)&(op['pstreak']<=1),
       'opp pro skid':op['pstreak']<=-2,'opp subbed 2+':(op['psubbed']>=2)&(me['psubbed']==0)}
    return [k for k,v in b.items() if bool(v) and not (isinstance(v,float) and np.isnan(v))]
out=[]
for row in card:
    a,b,wc=row[:3]
    ua,ub=url(a),url(b)
    A=man(ua) if ua else {}; B_=man(ub) if ub else {}
    ba=(boxes(A,B_) if ua and ub else [])+proboxes(pro(ua,a),pro(ub,b)); bb=(boxes(B_,A) if ua and ub else [])+proboxes(pro(ub,b),pro(ua,a))
    out.append((a,b,wc,ba,bb,''))
for a,b,wc,ba,bb,note in out:
    if ba is None: print(f'{a} vs {b}: {note}'); continue
    lead=len(ba)-len(bb); pick=a if lead>0 else b if lead<0 else '-'
    print(f'{a} {len(ba)} vs {len(bb)} {b} | lead {abs(lead)} | pick {pick}')
    print('   ',a,':',', '.join(ba) or '-'); print('   ',b,':',', '.join(bb) or '-')
