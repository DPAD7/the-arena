import re, json, csv, os, datetime, html as H
from cache import path
def txt(s): return re.sub(r'\s+',' ',H.unescape(re.sub(r'<[^>]+>',' ',s))).strip()
def ps(td): return [txt(p) for p in re.findall(r'<p class="b-fight-details__table-text">(.*?)</p>',td,re.S)]
def tds(row): return re.findall(r'<td[^>]*>(.*?)</td>',row,re.S)
def of(s):
    m=re.match(r'(\d+) of (\d+)',s or ''); return (m.group(1),m.group(2)) if m else ('','')
def cleanval(v): return '' if v in ('--','---') else v
def mdy(s):
    for f in ('%b %d, %Y','%b. %d, %Y','%B %d, %Y'):
        try: return datetime.datetime.strptime(s.strip(),f).date().isoformat()
        except: pass
    return ''
def raw(u): return open(path(u)).read()

# ---- fights
fl=json.load(open('fightlist.json'))
# event page rows: weight class + method abbrev by fight url
evrow={}
for eu in dict.fromkeys(x[0] for x in fl):
    h=raw(eu)
    for row in h.split('js-fight-details-click')[1:]:
        fu=re.search(r'data-link="([^"]+)"',row).group(1)
        c=tds(row)
        evrow[fu]={'weight_class':' '.join(ps(c[6])) , 'method':(ps(c[7]) or [''])[0]}
F=[]; fails=[]
for eu,en,ed,fu in fl:
    try:
        h=raw(fu)
        persons=re.findall(r'b-fight-details__person-status[^"]*">\s*(\w*)\s*</i>.*?fighter-details/([0-9a-f]+)\W*>(.*?)</a>',h,re.S)
        (rs,ru,rn),(bs,bu,bn)=persons[:2]
        if rs=='W': win='red'
        elif bs=='W': win='blue'
        elif rs=='D': win='draw'
        elif rs=='NC': win='nc'
        else: win=''
        title=txt(re.search(r'b-fight-details__fight-title">(.*?)</i>\s*</div>',h,re.S).group(1))
        def lab(l):
            m=re.search(l+r':\s*</i>(.*?)</i>',h,re.S); return txt(m.group(1)) if m else ''
        mdetail=txt(re.search(r'Method:\s*</i>\s*<i[^>]*>(.*?)</i>',h,re.S).group(1))
        tf=lab('Time format')
        m=re.match(r'(\d+) Rnd',tf)
        er=evrow.get(fu,{})
        r={'event_name':en,'event_date':ed,'fight_url':fu,'red_name':rn.strip(),'blue_name':bn.strip(),
           'red_url':'http://ufcstats.com/fighter-details/'+ru,'blue_url':'http://ufcstats.com/fighter-details/'+bu,
           'red_result':rs,'blue_result':bs,'winner':win,'method':er.get('method') or mdetail,'method_detail':mdetail,
           'round':lab('Round'),'time':lab('Time'),'time_format':tf,'scheduled_rounds':m.group(1) if m else '',
           'weight_class':er.get('weight_class',''),'bout_title':title,
           'title_bout':str(bool(re.match(r'UFC (Interim )?.*Title',title))).lower(),
           'referee':lab('Referee'),'stats_available':'false'}
        # totals table = first table after 'Totals'
        i=h.find('b-fight-details__collapse-link_tot')
        if i>0:
            tb=h[i:h.find('</table>',i)]
            rows=re.findall(r'<tr class="b-fight-details__table-row">(.*?)</tr>',tb,re.S)
            rows=[x for x in rows if '<td' in x]
            if rows:
                c=[ps(x) for x in tds(rows[0])]
                if len(c)>=10 and len(c[1])==2:
                    r['stats_available']='true'
                    for k,side in ((0,'red'),(1,'blue')):
                        r[f'{side}_kd']=c[1][k]
                        r[f'{side}_sig_landed'],r[f'{side}_sig_att']=of(c[2][k])
                        r[f'{side}_total_landed'],r[f'{side}_total_att']=of(c[4][k])
                        r[f'{side}_td_landed'],r[f'{side}_td_att']=of(c[5][k])
                        r[f'{side}_sub_att']=c[7][k]; r[f'{side}_rev']=c[8][k]; r[f'{side}_ctrl']=cleanval(c[9][k])
        F.append(r)
    except Exception as e: fails.append((fu,repr(e)))
statcols=[f'{s}_{k}' for s in ('red','blue') for k in ('kd','sig_landed','sig_att','total_landed','total_att','td_landed','td_att','sub_att','rev','ctrl')]
cols=list(F[0].keys()); cols=[c for c in cols if c not in statcols]+statcols
F.sort(key=lambda r:(r['event_date'],r['event_name']))
with open('fights.csv','w',newline='') as f:
    w=csv.DictWriter(f,cols); w.writeheader(); w.writerows(F)
print('fights',len(F),'fail',fails[:5],len(fails))

# ---- fighters + history
fs=sorted({r['red_url'] for r in F}|{r['blue_url'] for r in F})
FR=[]; HI=[]; ffails=[]
for fu in fs:
    try: h=raw(fu)
    except Exception as e: ffails.append((fu,repr(e))); continue
    try:
        name=txt(re.search(r'b-content__title-highlight">(.*?)</span>',h,re.S).group(1))
        rec=txt(re.search(r'b-content__title-record">(.*?)</span>',h,re.S).group(1)).replace('Record:','').strip()
        nick=txt(re.search(r'b-content__Nickname">(.*?)</p>',h,re.S).group(1))
        def lab(l):
            m=re.search(r'>\s*'+re.escape(l)+r'\s*</i>(.*?)</li>',h,re.S); return cleanval(txt(m.group(1))) if m else ''
        ht=lab('Height:'); m=re.match(r"(\d+)' (\d+)\"",ht); hin=str(int(m.group(1))*12+int(m.group(2))) if m else ''
        rc=lab('Reach:'); m=re.match(r'([\d.]+)"',rc); rin=m.group(1) if m else ''
        dob=lab('DOB:')
        FR.append({'fighter_url':fu,'name':name,'nickname':nick,'record':rec,'dob':mdy(dob) if dob else '',
            'height_in':hin,'weight':lab('Weight:'),'reach_in':rin,'stance':lab('STANCE:'),
            'slpm':lab('SLpM:'),'str_acc':lab('Str. Acc.:'),'sapm':lab('SApM:'),'str_def':lab('Str. Def:'),
            'td_avg':lab('TD Avg.:'),'td_acc':lab('TD Acc.:'),'td_def':lab('TD Def.:'),'sub_avg':lab('Sub. Avg.:')})
        body=h[h.find('b-fight-details__table-body'):]
        for row in body.split('js-fight-details-click')[1:]:
            c=tds(row)
            flag=re.search(r'b-flag__text">(\w+)',row).group(1)
            res={'win':'W','loss':'L','draw':'D','nc':'NC'}.get(flag.lower())
            if not res: continue  # upcoming ("next")
            ppl=re.findall(r'fighter-details/([0-9a-f]+)',c[1])
            opp=[p for p in ppl if not fu.endswith(p)]
            ev=ps(c[6])
            HI.append({'fighter_url':fu,'date':mdy(ev[1]) if len(ev)>1 else '','event_name':ev[0] if ev else '',
                'fight_url':re.search(r'data-link="([^"]+)"',row).group(1),
                'opponent_url':'http://ufcstats.com/fighter-details/'+opp[0] if opp else '',
                'opponent_name':(ps(c[1])+['',''])[1] if ppl and fu.endswith(ppl[0]) else (ps(c[1])+[''])[0],
                'result':res,'method':(ps(c[7]) or [''])[0],'method_detail':(ps(c[7])+['',''])[1],
                'round':(ps(c[8]) or [''])[0],'time':(ps(c[9]) or [''])[0]})
    except Exception as e: ffails.append((fu,repr(e)))
HI.sort(key=lambda r:(r['fighter_url'],r['date']))
for fn,rows in (('fighters.csv',FR),('history.csv',HI)):
    with open(fn,'w',newline='') as f:
        w=csv.DictWriter(f,list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print('fighters',len(FR),'history',len(HI),'ffails',len(ffails),ffails[:5])
