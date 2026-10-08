import re, json
from cache import cached, fetch_all
fl=json.load(open('fightlist.json'))
fs=set()
for x in fl:
    h=cached(x[3])
    fs.update(re.findall(r'href=\W?(http://ufcstats.com/fighter-details/[0-9a-f]+)',h))
fs=sorted(fs); json.dump(fs,open('fighterlist.json','w'))
print('fighters',len(fs))
out,fails=fetch_all(fs)
print('fetched',len(out),'fails',fails)
