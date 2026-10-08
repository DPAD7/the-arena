"""Read one fighter's pro record off his gidstats page (gidstats.com/fighters/<slug>.html).

The parser from the Oct 7, 2026 pull of every UFC fighter's record; ufc_records.py
asks it for a man the board has added since."""
import datetime as dt, html, re


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

ALIAS = {'alatengheili': 'Heili Alateng'}

MON = {m: i for i, m in enumerate('Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec'.split(), 1)}

FCOLS = ['page_url', 'source', 'fighter', 'date', 'result', 'opponent', 'opponent_url', 'event',
         'method', 'method_detail', 'round', 'time', 'time_raw', 'odds', 'odds_label',
         'division', 'billing', 'title']

PCOLS = ['fighter_url', 'name', 'origin', 'source', 'page_url', 'sherdog_url', 'gidstats_url',
         'page_name', 'dob_ufcstats', 'dob_sherdog', 'age_gidstats', 'matched_by', 'n_fights',
         'first_fight', 'last_fight', 'non_mma_skipped', 'asof']
