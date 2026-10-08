"""Full pro MMA records for every UFC / DWCS / upcoming-card fighter.

gidstats.com first (live page, else the mma-pipeline cache), Sherdog as fallback.
A page is taken only when the man is confirmed: his known opponents
(ufcstats bouts, DWCS bout, upcoming card bout) show up on it, or his age /
date of birth agrees. A disagreeing age or DOB always rejects the page.
"""
import csv, datetime as dt, glob, html, json, os, re, sys, collections
from concurrent.futures import ThreadPoolExecutor
from common import fetch, norm, tokkey, compact, last, HERE

SP = os.path.dirname(HERE)
TODAY = dt.date(2026, 10, 7)
GCACHE = '/Users/joe/mma-pipeline/.cache/gidstats'
log = open(f'{HERE}/run.log', 'a')


def say(*a):
    s = ' '.join(str(x) for x in a)
    print(s, flush=True)
    log.write(s + '\n'); log.flush()


# ---------------------------------------------------------------- inputs
fights_ufc = list(csv.DictReader(open(f'{SP}/ufc2/fights.csv')))
uname = {}
for r in csv.DictReader(open(f'{SP}/ufc2/fighters.csv')):
    uname[r['fighter_url']] = r
opps_of = collections.defaultdict(set)
for f in fights_ufc:
    for a, b in (('red', 'blue'), ('blue', 'red')):
        opps_of[f[a + '_url']].add(f[b + '_name'])

people = []          # dicts: key, fighter_url, name, dob, opps(set), sherdog_hint, origin
by_norm = collections.defaultdict(list)


def add(p):
    people.append(p)
    by_norm[norm(p['name'])].append(p)


for url, r in uname.items():
    add(dict(fighter_url=url, name=r['name'], dob=r.get('dob', '') or '',
             opps=set(opps_of.get(url, ())), sherdog_hint='', origin='ufcstats'))

for r in csv.DictReader(open(f'{SP}/dwcs/dwcs.csv')):
    for a, b in (('a', 'b'), ('b', 'a')):
        nm, dob = r[f'fighter_{a}'], r[f'fighter_{a}_dob'] or ''
        hint = r.get(f'fighter_{a}_sherdog_url', '') or ''
        cand = [p for p in by_norm[norm(nm)] if not p['dob'] or not dob or p['dob'] == dob]
        if len(cand) == 1:
            p = cand[0]
            p['opps'].add(r[f'fighter_{b}'])
            p['sherdog_hint'] = p['sherdog_hint'] or hint
            p['dob'] = p['dob'] or dob
            if 'dwcs' not in p['origin']:
                p['origin'] += '+dwcs'
        else:
            add(dict(fighter_url='', name=nm, dob=dob, opps={r[f'fighter_{b}']},
                     sherdog_hint=hint, origin='dwcs'))

for fn in ('card_rest.json', 'card_oct10.json'):
    for row in json.load(open(f'{SP}/ufc2/{fn}')):
        for nm, op in ((row[0], row[1]), (row[1], row[0])):
            if 'tba' in norm(nm).split():
                continue
            cand = by_norm[norm(nm)]
            if len(cand) == 1:
                cand[0]['opps'].add(op)
                if 'card' not in cand[0]['origin']:
                    cand[0]['origin'] += '+card'
            else:
                add(dict(fighter_url='', name=nm, dob='', opps={op},
                         sherdog_hint='', origin='card'))
say('people', len(people), collections.Counter(p['origin'] for p in people))

# ---------------------------------------------------------------- gidstats index
IX = [(s, html.unescape(html.unescape(n))) for s, n in json.load(open(f'{HERE}/gid_index.json'))]
ix_norm, ix_tok, ix_comp, ix_last = (collections.defaultdict(list) for _ in range(4))
for s, n in IX:
    ix_norm[norm(n)].append(s); ix_tok[tokkey(n)].append(s); ix_comp[compact(n)].append(s)
    for t in norm(n).split():
        ix_last[t].append(s)
ix_name = dict(IX)
ix_comp_keys = list(ix_comp)


def okeys(name):
    n = norm(name).split()
    if not n:
        return set()
    ks = {compact(name)}
    if len(n) > 1:
        ks.add(n[0][0] + ' ' + n[-1])          # first initial + surname
        ks.add(n[0][0] + ' ' + n[1])           # first initial + first surname (Iberian names)
    return ks


def opp_hits(known, page_opps):
    """How many known opponents appear on the page (full name, or first initial + surname)."""
    keys = set()
    for o in page_opps:
        keys |= okeys(o)
    return sum(1 for k in known if okeys(k) & keys)


def age_on(dob, on):
    try:
        b = dt.date.fromisoformat(dob)
    except Exception:
        return None
    return on.year - b.year - ((on.month, on.day) < (b.month, b.day))


# ---------------------------------------------------------------- gidstats page
METH = [('no contest', 'NC'), ('overturned', 'NC'), ('dq', 'DQ'), ('disqual', 'DQ'),
        ('ko', 'KO/TKO'), ('tko', 'KO/TKO'), ('submission', 'Submission'),
        ('decision', 'Decision'), ('draw', 'Draw')]


def meth(m):
    m = (m or '').lower()
    for k, v in METH:
        if k in m:
            return v
    return m.title() if m else ''


def detail(m, fm):
    m, fm = (m or '').strip(), (fm or '').strip()
    if not fm or fm.lower() == m.lower():
        return m
    return f'{m} ({fm})' if m else fm


def fix_time(raw, rnd):
    """gidstats writes total elapsed fight time (m.ss); turn it into time in the round."""
    if not raw or not re.match(r'^\d+\.\d\d$', raw):
        return raw or ''
    mm, ss = raw.split('.')
    t = int(mm) * 60 + int(ss)
    if rnd and rnd > 1 and t > 300 * (rnd - 1):
        t -= 300 * (rnd - 1)
    return f'{t // 60}:{t % 60:02d}'


def parse_gid(text):
    out = {'name': '', 'age': None, 'fights': [], 'upcoming': [], 'non_mma': 0, 'cancelled': 0}
    m = re.search(r'<p class="fighter__title">([^<]+)</p>', text)
    out['name'] = html.unescape(m.group(1).strip()) if m else ''
    m = re.search(r'data-list__item">Age<br><span class="value">(\d+)</span>', text)
    out['age'] = int(m.group(1)) if m else None
    starts = [m.start() for m in re.finditer(r'<li class="history-list__item', text)]
    for k, i in enumerate(starts):
        ch = text[i:starts[k + 1] if k + 1 < len(starts) else len(text)]
        cm = re.match(r'<li class="([^"]*)"', ch)
        cls = re.findall(r'history-list__item--([\w-]+)', cm.group(1))
        cls = cls[-1] if cls else ''
        pm = re.search(r'<span class="pair">\s*<span class="pair-vs-custom">VS</span>\s*([\s\S]*?)</span>', ch)
        pair = pm.group(1) if pm else ''
        om = re.search(r'<a href="/fighters/([^"]+)\.html"[^>]*>([^<]+)</a>', pair)
        opp = html.unescape(om.group(2).strip() if om else re.sub('<[^>]+>', '', pair).strip())
        oslug = om.group(1) if om else ''
        if cls == '':
            out['upcoming'].append(opp); continue
        if cls == 'cancelled':
            out['cancelled'] += 1; continue
        if 'class="non-mma"' in ch.split('</p>')[0] or re.search(r'<p class="date"[^>]*>[^<]*<span class="non-mma">', ch):
            out['non_mma'] += 1; continue
        dm = re.search(r'<p class="date"[^>]*>\s*([\d.]+)\s*[•·]?\s*([^<•]*)', ch)
        date = ''
        if dm:
            try:
                date = dt.datetime.strptime(dm.group(1).strip(), '%d.%m.%Y').date().isoformat()
            except ValueError:
                date = dm.group(1)
        info = dict((html.unescape(a.strip()), html.unescape(b.strip())) for a, b in re.findall(
            r'<p class="top-text"[^>]*>([^<]+)</p>\s*<p class="bottom-text"[^>]*>([^<]+)</p>', ch))
        g = lambda c: (re.search(rf'<p class="{c}"[^>]*>[\s\S]*?<span>([^<]+)</span>', ch) or [None, ''])[1].strip()
        rnd = g('round'); rnd_i = int(rnd) if rnd.isdigit() else None
        m_raw = g('method')
        res = {'win': 'win', 'lose': 'loss', 'draw': 'draw'}.get(cls)
        if res is None:
            res = 'NC' if cls == 'not-confirmed' else cls
        odds = ''
        if info.get('ODDS'):
            om2 = re.match(r'([+\-]?\d+)', info['ODDS'])
            odds = om2.group(1) if om2 else ''
        out['fights'].append(dict(
            date=date, result=res, opponent=opp,
            opponent_url=f'https://gidstats.com/fighters/{oslug}.html' if oslug else '',
            event=info.get('Event') or (dm.group(2).strip() if dm else ''),
            method=meth(m_raw), method_detail=detail(m_raw, info.get('Finishing move', '')),
            round=rnd, time=fix_time(g('time'), rnd_i), time_raw=g('time'), odds=odds,
            odds_label=info.get('ODDS', ''), division=info.get('Division', ''),
            billing=info.get('BILLING', ''), title=info.get('Champ Bout', '')))
    return out


def from_cache(slug):
    p = f'{GCACHE}/fighter__{slug}.json'
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    if 'fight_history' not in d:
        return None
    fights = []
    for x in d['fight_history']:
        if x.get('raw_class') == 'cancelled':
            continue
        res = {'W': 'win', 'L': 'loss', 'D': 'draw'}.get(x.get('result'))
        if res is None:
            res = 'NC' if x.get('raw_class') == 'not-confirmed' else '?'
        fights.append(dict(date=x.get('date_iso', ''), result=res, opponent=x.get('opponent', ''),
                           opponent_url=f"https://gidstats.com/fighters/{x['opponent_slug']}.html" if x.get('opponent_slug') else '',
                           event=x.get('event_name', ''), method=meth(x.get('method')),
                           method_detail=detail(x.get('method') or '', x.get('finishing_detail') or ''),
                           round=str(x.get('round') or ''), time=fix_time(x.get('time'), x.get('round')),
                           time_raw=x.get('time', ''), odds=x.get('odds_american', ''), odds_label=x.get('odds_raw', ''),
                           division=x.get('division', ''), billing=x.get('billing', ''), title=x.get('champ_bout', '')))
    age = d.get('bio', {}).get('age')
    return {'name': d['name'], 'age': int(age) if age and age.isdigit() else None, 'fights': fights,
            'upcoming': [], 'non_mma': 0, 'cancelled': 0, 'cache_date': d.get('fetched_at', '')[:10]}


gid_pages = {}


def gid_page(slug):
    if slug in gid_pages:
        return gid_pages[slug]
    st, t = fetch(f'https://gidstats.com/fighters/{slug}.html', f'gid_{slug}')
    if st == 200:
        pg = parse_gid(t); pg['src'] = 'gidstats'; pg['url'] = f'https://gidstats.com/fighters/{slug}.html'; pg['asof'] = TODAY.isoformat()
    else:
        pg = from_cache(slug)
        if pg:
            pg['url'] = f'https://gidstats.com/fighters/{slug}.html'; pg['src'] = 'gidstats_cache'; pg['asof'] = pg.pop('cache_date') or TODAY.isoformat()
    gid_pages[slug] = pg
    return pg


def judge(p, pg, exact):
    """Return (ok, how) for page pg against person p."""
    if pg and pg.get('url') in p.get('banned', ()):
        return False, 'taken by a namesake'
    if not pg or not pg['fights'] and not pg['upcoming']:
        return False, 'empty'
    hits = opp_hits(p['opps'], [f['opponent'] for f in pg['fights']] + pg['upcoming'])
    age_ok = None
    if p['dob'] and pg.get('age') is not None:
        exp = age_on(p['dob'], dt.date.fromisoformat(pg['asof']))
        if exp is not None:
            age_ok = abs(exp - pg['age']) <= 1
    need = 1 if exact else min(2, len(p['opps']))
    if age_ok is False:
        # gidstats' age is not a date of birth and is often stale; only a strong
        # opponent record outweighs it, and the row is flagged
        if hits >= 3 or (p['opps'] and hits >= (len(p['opps']) if exact else max(2, len(p['opps'])))):
            return True, ('name' if exact else 'alias') + f'+opponents({hits}) AGE_CONFLICT(gid {pg["age"]}, dob {p["dob"]})'
        return False, f'age {pg["age"]} vs dob {p["dob"]}, opponent hits {hits}'
    if p['opps'] and hits >= max(need, 1):
        return True, ('name' if exact else 'alias') + f'+opponents({hits})' + ('+age' if age_ok else '')
    if exact and age_ok:
        return True, 'name+age'
    if exact and not p['opps']:
        return True, 'name'
    return False, f'no opponent overlap (hits {hits}, age_ok {age_ok})'


# recorded spellings: the board's name -> the name the source files him under
ALIAS = {'alatengheili': 'Heili Alateng'}


def gid_resolve(p):
    n = norm(ALIAS.get(norm(p['name']), p['name']))
    exact = list(dict.fromkeys(ix_norm.get(n, []) + ix_tok.get(tokkey(n), []) + ix_comp.get(compact(n), [])))
    tried = []
    for s in exact:
        pg = gid_page(s)
        ok, how = judge(p, pg, True)
        tried.append((s, how))
        if ok:
            return s, pg, how, tried
    # loose: same surname token (any of ours, len>=3), first initial agrees, or single-token names
    toks = n.split()
    loose = []
    if len(toks) == 1:
        loose = [s for s in ix_last.get(toks[0], [])]
    else:
        for t in toks[1:] + toks[:1]:
            if len(t) < 3:
                continue
            for s in ix_last.get(t, []):
                nm = norm(ix_name[s]).split()
                if s not in exact and nm and (set(nm) & set(toks) - {t} or
                                              any(a[0] == b[0] for a in toks for b in nm if a != t and b != t)):
                    loose.append(s)
    # then: same surname with any first name, and close spellings of the whole name
    for t in toks[-1:] if len(toks) > 1 else []:
        loose += [x for x in ix_last.get(t, []) if x not in exact]
    import difflib
    cl = difflib.get_close_matches(compact(p['name']), ix_comp_keys, 5, 0.8)
    loose = [x for c in cl for x in ix_comp[c] if x not in exact] + loose
    loose = list(dict.fromkeys(loose))[:45]
    for s in loose:
        pg = gid_page(s)
        ok, how = judge(p, pg, False)
        if ok:
            return s, pg, how, tried
    tried.append((f'{len(loose)} loose', 'none confirmed'))
    return None, None, None, tried


# ---------------------------------------------------------------- sherdog fallback
MON = {m: i for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(), 1)}


def parse_sherdog(t):
    out = {'name': '', 'dob': '', 'fights': [], 'upcoming': []}
    m = re.search(r'<span class="fn">([^<]+)</span>', t)
    out['name'] = html.unescape(m.group(1).strip()) if m else ''
    m = re.search(r'itemprop="birthDate">([A-Za-z]{3}) (\d+), (\d{4})<', t)
    if m:
        out['dob'] = f'{m.group(3)}-{MON[m.group(1)]:02d}-{int(m.group(2)):02d}'
    up = t.find('Upcoming Fights')
    pro = t.find('FIGHT HISTORY - PRO')
    if 0 <= up < pro:
        out['upcoming'] = [html.unescape(x) for x in re.findall(r'<span itemprop="name">([^<]+)</span>', t[up:pro])]
    if pro < 0:
        return out
    end = t.find('FIGHT HISTORY - AMATEUR', pro)
    seg = t[pro:end if end > 0 else len(t)]
    seg = seg[:seg.find('</table>')] if '</table>' in seg else seg
    for row in re.findall(r'<tr>([\s\S]*?)</tr>', seg):
        rm = re.search(r'final_result [^"]*">([^<]+)<', row)
        if not rm:
            continue
        tds = re.findall(r'<td[^>]*>([\s\S]*?)</td>', row)
        om = re.search(r'<a href="(/fighter/[^"]+)">([^<]+)</a>', tds[1]) if len(tds) > 1 else None
        em = re.search(r'<a href="/events/[^"]+">(?:<span[^>]*>)?([^<]+)', tds[2]) if len(tds) > 2 else None
        dm = re.search(r'sub_line">([A-Za-z]{3}) / (\d+) / (\d{4})<', tds[2]) if len(tds) > 2 else None
        mm = re.search(r'<b>([^<]+)</b>', tds[3]) if len(tds) > 3 else None
        md = html.unescape(mm.group(1).strip()) if mm else ''
        res = rm.group(1).strip().lower()
        out['fights'].append(dict(
            date=f'{dm.group(3)}-{MON[dm.group(1)]:02d}-{int(dm.group(2)):02d}' if dm else '',
            result={'nc': 'NC'}.get(res, res),
            opponent=html.unescape(om.group(2).strip()) if om else re.sub('<[^>]+>', '', tds[1]).strip() if len(tds) > 1 else '',
            opponent_url='https://www.sherdog.com' + om.group(1) if om else '',
            event=html.unescape(em.group(1).strip()) if em else '',
            method=meth(md.split('(')[0]), method_detail=md,
            round=re.sub('<[^>]+>', '', tds[4]).strip() if len(tds) > 4 else '',
            time=re.sub('<[^>]+>', '', tds[5]).strip() if len(tds) > 5 else '',
            time_raw='', odds='', odds_label='', division='', billing='', title=''))
    return out


def sher_page(path):
    slug = path.rsplit('/', 1)[-1]
    st, t = fetch('https://www.sherdog.com/fighter/' + slug, f'sher_{slug}')
    if st != 200:
        return None
    pg = parse_sherdog(t); pg['url'] = 'https://www.sherdog.com/fighter/' + slug
    return pg


def sher_search(q):
    out, page = [], 1
    while page <= 8:
        url = 'https://www.sherdog.com/stats/fightfinder?SearchTxt=' + q.replace(' ', '+') + (f'&page={page}' if page > 1 else '')
        st, t = fetch(url, f'sherq_{q}_{page}')
        if st != 200:
            break
        tb = t[t.find('fightfinder_result'):]
        tb = tb[:tb.find('</table>')]
        out += [(u, html.unescape(n)) for u, n in re.findall(r'<a href="(/fighter/[^"]+)">([^<]+)</a>', tb)]
        if f'page={page + 1}"' not in t.split('rpage=')[0]:
            break
        page += 1
    return out


def sher_judge(p, pg, exact):
    if pg and pg.get('url') in p.get('banned', ()):
        return False, 'taken by a namesake'
    if not pg:
        return False, 'no page'
    if p['dob'] and pg['dob']:
        if p['dob'] != pg['dob']:
            return False, f'dob {pg["dob"]} vs {p["dob"]}'
        return True, ('name' if exact else 'alias') + '+dob'
    hits = opp_hits(p['opps'], [f['opponent'] for f in pg['fights']] + pg['upcoming'])
    if p['opps'] and hits >= (1 if exact else min(2, len(p['opps']))):
        return True, ('name' if exact else 'alias') + f'+opponents({hits})'
    if exact and not p['opps']:
        return True, 'name'
    return False, f'no dob, opponent hits {hits}'


def sher_resolve(p):
    tried = []
    if p['sherdog_hint']:
        pg = sher_page(p['sherdog_hint'])
        ok, how = sher_judge(p, pg, True)
        tried.append((p['sherdog_hint'], how))
        if ok:
            return 'https://www.sherdog.com/fighter/' + p['sherdog_hint'].rsplit('/', 1)[-1], pg, 'dwcs_url+' + how, tried
    n = norm(p['name'])
    res = sher_search(n)
    exact = [u for u, nm in res if norm(nm) == n or tokkey(nm) == tokkey(p['name'])]
    for u in exact[:10]:
        pg = sher_page(u)
        ok, how = sher_judge(p, pg, True)
        tried.append((u, how))
        if ok:
            return 'https://www.sherdog.com' + u, pg, how, tried
    toks = n.split()
    if toks and (p['dob'] or p['opps']):
        res = sher_search(toks[-1]) if len(toks) > 1 else res
        loose = [u for u, nm in res if u not in exact and norm(nm).split() and
                 norm(nm).split()[0][:1] == toks[0][:1]][:12]
        for u in loose:
            pg = sher_page(u)
            ok, how = sher_judge(p, pg, False)
            if ok:
                return 'https://www.sherdog.com' + u, pg, how, tried
        tried.append((f'{len(loose)} loose', 'none confirmed'))
    return None, None, None, tried


# ---------------------------------------------------------------- run
def work(p):
    try:
        s, pg, how, tried = gid_resolve(p)
        if s:
            return dict(p=p, src=pg['src'], url=f'https://gidstats.com/fighters/{s}.html', pg=pg, how=how)
        u, spg, show, stried = sher_resolve(p)
        if u:
            return dict(p=p, src='sherdog', url=u, pg=spg, how=show, gid_tried=tried)
        return dict(p=p, miss={'gidstats': tried, 'sherdog': stried})
    except Exception as e:
        import traceback
        return dict(p=p, miss={'error': traceback.format_exc()[-400:]})


results = []
with ThreadPoolExecutor(10) as ex:
    for i, r in enumerate(ex.map(work, people)):
        results.append(r)
        if i % 100 == 0:
            say(i, len(people), 'matched', sum(1 for x in results if 'url' in x),
                collections.Counter(x.get('src', 'miss') for x in results))

# two different ufcstats men on one page: keep the better-evidenced, re-resolve the other without it
def score(r):
    pg = r['pg']
    return opp_hits(r['p']['opps'], [f['opponent'] for f in pg['fights']] + pg.get('upcoming', []))


for rnd in range(3):
    byurl = collections.defaultdict(list)
    for r in results:
        if 'url' in r and r['p']['fighter_url']:
            byurl[r['url']].append(r)
    clash = {u: rs for u, rs in byurl.items() if len(rs) > 1}
    if not clash:
        break
    for u, rs in clash.items():
        rs.sort(key=score, reverse=True)
        for r in rs[1:]:
            p = r['p']
            p.setdefault('banned', set()).add(u)
            say('clash', u, 'keeps', rs[0]['p']['name'], rs[0]['p']['dob'], '; re-resolving', p['name'], p['dob'])
            nr = work(p)
            r.clear(); r.update(nr)

# ---------------------------------------------------------------- write
FCOLS = ['page_url', 'source', 'fighter', 'date', 'result', 'opponent', 'opponent_url', 'event',
         'method', 'method_detail', 'round', 'time', 'time_raw', 'odds', 'odds_label',
         'division', 'billing', 'title']
PCOLS = ['fighter_url', 'name', 'origin', 'source', 'page_url', 'sherdog_url', 'gidstats_url',
         'page_name', 'dob_ufcstats', 'dob_sherdog', 'age_gidstats', 'matched_by', 'n_fights',
         'first_fight', 'last_fight', 'non_mma_skipped', 'asof']
seen_pages = set()
nf = 0
dates = []
with open(f'{HERE}/people.csv', 'w', newline='') as pf, open(f'{HERE}/fights.csv', 'w', newline='') as ff:
    pw = csv.DictWriter(pf, PCOLS); pw.writeheader()
    fw = csv.DictWriter(ff, FCOLS); fw.writeheader()
    misses = []
    for r in results:
        p = r['p']
        if 'url' not in r:
            misses.append(dict(name=p['name'], fighter_url=p['fighter_url'], dob=p['dob'],
                               origin=p['origin'], known_opponents=sorted(p['opps']), why=r['miss']))
            continue
        pg = r['pg']
        fs = sorted(pg['fights'], key=lambda f: f['date'])
        ds = [f['date'] for f in fs if f['date']]
        pw.writerow(dict(fighter_url=p['fighter_url'], name=p['name'], origin=p['origin'], source=r['src'],
                         page_url=r['url'], sherdog_url=r['url'] if r['src'] == 'sherdog' else '',
                         gidstats_url=r['url'] if r['src'] != 'sherdog' else '', page_name=pg['name'],
                         dob_ufcstats=p['dob'] if p['fighter_url'] else '', dob_sherdog=pg.get('dob', ''),
                         age_gidstats=pg.get('age') if pg.get('age') is not None else '',
                         matched_by=r['how'], n_fights=len(fs), first_fight=ds[0] if ds else '',
                         last_fight=ds[-1] if ds else '', non_mma_skipped=pg.get('non_mma', ''),
                         asof=pg.get('asof', TODAY.isoformat())))
        if r['url'] in seen_pages:
            continue
        seen_pages.add(r['url'])
        for f in fs:
            fw.writerow(dict(page_url=r['url'], source=r['src'], fighter=pg['name'] or p['name'], **f))
            nf += 1
            if f['date']:
                dates.append(f['date'])
json.dump(misses, open(f'{HERE}/misses.json', 'w'), indent=1)
say('DONE people', len(results), 'matched', len(results) - len(misses), 'pages', len(seen_pages),
    'fights', nf, 'range', min(dates), max(dates), 'misses', len(misses),
    collections.Counter(r.get('src', 'miss') for r in results))
