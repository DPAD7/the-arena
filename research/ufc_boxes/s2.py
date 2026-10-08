import re, json
from cache import cached, fetch_all
evs=json.load(open('events.json'))
fl=[]
for u,n,d in evs:
    h=cached(u)
    for f in dict.fromkeys(re.findall(r'data-link="(http://ufcstats.com/fight-details/[0-9a-f]+)"',h)):
        fl.append((u,n,d,f))
json.dump(fl,open('fightlist.json','w'))
print('fights',len(fl))
out,fails=fetch_all([x[3] for x in fl])
print('fetched',len(out),'fails',fails)
