import re, datetime, json
from cache import fetch_all
h=open('raw/events.html').read()
ev=re.findall(r'href="(http://ufcstats.com/event-details/[0-9a-f]+)"[^>]*>\s*(.*?)\s*</a>\s*<span class="b-statistics__date">\s*(.*?)\s*</span>',h,re.S)
rows=[]
for u,n,d in ev:
    dt=datetime.datetime.strptime(d,'%B %d, %Y').date()
    if datetime.date(2010,1,1)<=dt<datetime.date(2026,10,7): rows.append((u,n,dt.isoformat()))
print(len(ev),len(rows),rows[0],rows[-1])
json.dump(rows,open('events.json','w'))
out,fails=fetch_all([r[0] for r in rows])
print('fetched',len(out),'fails',fails)
