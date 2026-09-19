"""Every football card carries all three sections, whether or not anything is
   priced in them.

   Filling the empty slots inside a section did nothing for a card that had no
   section at all: Atlanta had no head-to-head, Washington no receivers, and
   not one college card had either. So the card is rebuilt from a fixed list —
   head to head, passing, receivers — and any of the three it was missing is
   written out empty, at exactly the size it is elsewhere.

   NFL only for now. The fights have no quarterback and no receivers, and
   DraftKings serves no head-to-head passing market on the college board at
   all — that subcategory is league 88808, the NFL, and nothing else.
"""
import re

D = "/Users/joe/Desktop/odds"
s = open(D + "/master.html").read()
before = s.count("data-oid")

GHOST = '<span class="ghost" aria-hidden="true"></span>'
DASHNAME = '<span class="gdash">&mdash;</span>'
GOLD, BLUE = "var(--amber)", "#5aa9ff"
added = {"h2h": 0, "ptd": 0, "rec": 0}


def last(card, key):
    m = re.search(r'data-%s="([^"]*)"' % key, card)
    return m.group(1).split(" ")[-1] if m else None


def h2h_section(card):
    lq, rq = last(card, "lqb"), last(card, "rqb")
    return ('        <div class="h2hx">\n'
            '          <div class="ptdhead"><span style="color:%s">%s</span>'
            '<span class="gmk">H2H YDS</span><span style="color:%s">%s</span></div>\n'
            '          <div class="h2hrow">'
            '<span class="h2hend"><span class="trkbox">0</span>'
            '<span class="h2hodds">%s</span></span>'
            '<div class="h2hbar"><i class="h2hzero"></i>'
            '<div class="h2hfill" style="left:50%%; width:0"></div>'
            '<i class="h2htick" style="left:50%%"><b>0</b></i></div>'
            '<span class="h2hend"><span class="trkbox">0</span>'
            '<span class="h2hodds">%s</span></span></div>\n        </div>'
            % (GOLD, lq or DASHNAME, BLUE, rq or DASHNAME, GHOST, GHOST))


def ptd_section(card):
    lq, rq = last(card, "lqb"), last(card, "rqb")

    def side(which):
        edge = "right" if which == "l" else "left"
        chips = "".join(
            '<span class="ptdbtn ptdbtn--n%d"><span class="ptdline">%d+</span>%s</span>'
            % (k, k, GHOST) for k in (1, 2))
        ticks = "".join('<i class="ntick ntick--n%d" style="%s:%.1f%%"><b>%d</b></i>'
                        % (k, edge, k / 2.0 * 100.0, k) for k in (1, 2))
        return ('<div class="ptdside ptdside--%s">'
                '<div class="ptdbar"><div class="ptdfill" style="%s:0; width:0%%"></div>%s</div>'
                '<div class="ptdmarks">%s</div></div>' % (which, edge, ticks, chips))

    return ('        <div class="ptdx ptdx--v2" data-scale="2" data-kind="PTD">\n'
            '          <div class="ptdhead"><span style="color:%s">%s</span>'
            '<span class="gmk">PTD</span><span style="color:%s">%s</span></div>\n'
            '          <div class="ptdrow"><span class="trkbox ptdcount">0</span>%s'
            '<span class="ptdzero">0</span>%s'
            '<span class="trkbox ptdcount">0</span></div>\n        </div>'
            % (GOLD, lq or DASHNAME, BLUE, rq or DASHNAME, side("l"), side("r")))


def rec_section(_card):
    cell = ('<span class="gcell recpair">'
            + ('<span class="recman">%s<span class="wrname">&nbsp;</span></span>' % GHOST) * 2
            + '</span>')
    return ('        <div class="grow">%s<span class="gmk">1+ REC 1Q</span>%s</div>'
            % (cell, cell))


CARD = re.compile(r'<div class="gcard"[^>]*>(?:(?!<div class="gcard").)*?\n      </div>', re.S)


def rebuild(mm):
    card = mm.group(0)
    if 'data-lg="nfl"' not in card:
        return card        # the fights and the college board keep their shape

    if 'class="h2hx"' not in card:
        added["h2h"] += 1
        anchor = re.search(r'<div class="ghead">.*?</div>\n', card, re.S)
        card = card[:anchor.end()] + h2h_section(card) + "\n" + card[anchor.end():]

    if 'class="ptdx' not in card:
        added["ptd"] += 1
        anchor = re.search(r'<div class="h2hx">.*?\n        </div>\n', card, re.S)
        card = card[:anchor.end()] + ptd_section(card) + "\n" + card[anchor.end():]

    if "1+ REC 1Q" not in card:
        added["rec"] += 1
        last_ptd = None
        for m in re.finditer(r'<div class="ptdx[^"]*"[^>]*>.*?\n        </div>\n', card, re.S):
            last_ptd = m
        card = card[:last_ptd.end()] + rec_section(card) + "\n" + card[last_ptd.end():]
    return card


s = CARD.sub(rebuild, s)
assert s.count("data-oid") == before, "prices lost"
open(D + "/master.html", "w").write(s)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
       '<meta name="robots" content="noindex">\n</head>\n<body>\n')
open(D + "/site/index.html", "w").write(
    doc + s
    + "\n</body>\n</html>\n")
print("sections written:", added, "| prices:", s.count("data-oid"))
