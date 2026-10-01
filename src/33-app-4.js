  function clubRecOf(r) {
    var rec = clubRec();
    return rec[String((r && r.club) || "")] || [0, 0];
  }
  function renderForm() {
    if (formWeek === "clips") { clearBoard(); renderClips(); return; }
    /* a week on Stacked is its games' clips now (Jose, Sep 29, 2026: "since
       it's essentially the same, make it clips for that week"); the week
       card below stays for the day he wants it back */
    if (/^\d+$/.test(String(formWeek))) { clearBoard(); renderWeekClips(); return; }
    clearBoard();
    var rows = formRows();
    layLive(rows);
    /* rank on everything together: each passing touchdown, each rushing one,
       a head-to-head win and a club win all count one. Four passing scores
       with both losses (4) sits under two and two with both wins (6).
       Level on the total, the man who did it across more of the four columns
       is first: Allen's two and two with both wins beat Lawrence's four
       passing and no run, and it was the other way round. (Jose, Sep 17, 2026)
       Then: passing, rushing, the head to head. */
    /* One rule for the season and for every week: combined touchdowns, then
       the club's record, then its wins, then the head to heads, then the name.
       A week used to be scored differently -- a head-to-head and a club win
       counting a touchdown each, then how many of the four columns he showed
       up in -- so the same man read one way on the season and another on the
       week (Jose, Sep 22, 2026: "that's the way we rank them, season and all
       the weeks"). */
    var wins = function (r, k) { return r.agg ? r[k + "w"] : (r[k] === "W" ? 1 : 0); };
    rows.sort(function (a, b) {
      var ta = (a.ptd || 0) + (a.atd || 0), tb = (b.ptd || 0) + (b.atd || 0);
      if (tb !== ta) return tb - ta;
      var ra = clubRecOf(a), rb = clubRecOf(b);
      if ((rb[0] - rb[1]) !== (ra[0] - ra[1])) return (rb[0] - rb[1]) - (ra[0] - ra[1]);
      if (rb[0] !== ra[0]) return rb[0] - ra[0];
      if (wins(b, "h2h") !== wins(a, "h2h")) return wins(b, "h2h") - wins(a, "h2h");
      return a.name < b.name ? -1 : 1;
    });
    var BALL = '<i class="fmk fmk--ball">' + BALLSVG + "</i>", RUN = '<i class="fmk fmk--run">' + RUSHSVG + "</i>";
    var VS = '<i class="fmk fmk--vs"><svg viewBox="0 0 26 22" aria-hidden="true"><use href="#vs"/></svg></i>';
    var MLP = '<img class="fmk--ml" src="ico/moneyline.svg" alt="Moneyline" width="34" height="13">';
    var W = function (lab) {
      if (lab === "H2H") return '<b class="wl wl--w wl--vs">' + VS + '</b>';
      if (lab === "ML") return '<b class="wl wl--w wl--ml">' + MLP + '</b>';
      return '<b class="wl wl--w">' + lab + '</b>';
    };
    var box = document.createElement("div");
    box.className = "form";
    if (!rows.length) {
      box.innerHTML = '<p class="formnote">Nothing settled yet.</p>';
      BOARD.appendChild(box); return;
    }
    if (formWeek !== "season") {
      /* the week: one container a game, the two passers either side with
         their ranks, then a line each for the moneyline, the head to head
         (yards and the gap), the footballs and the runners, down the middle
         (Jose, Sep 16, 2026) */
      /* the week is ranked on what the card paid, capped at two a prop, so the
         cards read in the same order the money page does (Jose, Sep 17, 2026) */
      var toD = function (o) {
        var n = parseInt(String(o).replace(/\u2212/g, "-").replace("+", ""), 10);
        return n > 0 ? 1 + n / 100 : 1 + 100 / -n;
      };
      var payDec = function (r) {
        var dec = 1, any = false;
        var pick = function (list, hit) {
          var at = null;
          for (var k = 0; k < Math.min(hit, 2); k++) {
            var o = list && list[k];
            if (o && (at === null || toD(o) > toD(at))) at = o;
          }
          return at;
        };
        var a = pick(r.odds[0], r.ptd); if (a) { dec *= toD(a); any = true; }
        var b = pick(r.odds[1], r.atd); if (b) { dec *= toD(b); any = true; }
        if (r.h2h === "W" && r.odds[2]) { dec *= toD(r.odds[2]); any = true; }
        if (r.ml === "W" && r.odds[3]) { dec *= toD(r.odds[3]); any = true; }
        return any ? dec : 0;
      };
      /* the same rule the season uses: combined touchdowns, the club's record,
         its wins, the head to heads, the name. It used to rank on what the
         legs would have paid, so the card's number one was whoever priced
         longest rather than whoever did the most
         (Jose, Sep 22, 2026: "that's the way we rank them, season and all
         the weeks") */
      var hw = function (r) { return r.h2hw === undefined ? (r.h2h === "W" ? 1 : 0) : r.h2hw; };
      rows.sort(function (a, b) {
        var ta = (a.ptd || 0) + (a.atd || 0), tb = (b.ptd || 0) + (b.atd || 0);
        if (tb !== ta) return tb - ta;
        var ra = clubRecOf(a), rb = clubRecOf(b);
        if ((rb[0] - rb[1]) !== (ra[0] - ra[1])) return (rb[0] - rb[1]) - (ra[0] - ra[1]);
        if (rb[0] !== ra[0]) return rb[0] - ra[0];
        if (hw(b) !== hw(a)) return hw(b) - hw(a);
        return a.name < b.name ? -1 : 1;
      });
      rows.forEach(function (r, i) { r.rank = i + 1; });
      var games = {};
      rows.forEach(function (r) { (games[r.game] = games[r.game] || []).push(r); });
      var order = Object.keys(games).sort(function (a, b) {
        return Math.min.apply(null, games[a].map(function (r) { return r.rank; })) - Math.min.apply(null, games[b].map(function (r) { return r.rank; }));
      });
      var faceOf = function (r) {
        return ledgerFace(r);
      };
      /* STATSCORE's own marks, from their icon font: the house by the home
         man's club, the plane by the man who travelled (Jose, Sep 16, 2026) */
      var HOUSE = '<svg class="fhome" aria-hidden="true"><use href="#schome"/></svg>';
      var PLANE = '<svg class="fhome" aria-hidden="true"><use href="#scaway"/></svg>';
      var who = function (r, right) {
        var club = esc(r.club);   /* the house and plane sit by the score now (Jose, Sep 17, 2026) */
        var name = '<span class="fname">' + nameMark(r) + '<small>' + club + '</small></span>';
        var rank = '<span class="frank">' + r.rank + '</span>';
        return right ? '<span class="fwho fwho--r">' + name + faceOf(r) + rank + '</span>'
                     : '<span class="fwho">' + rank + faceOf(r) + name + '</span>';
      };
      /* a mark we hold a price for wears a border; only the rungs DraftKings
         prices (1+ and 2+) can have one (Jose, Sep 16, 2026) */
      /* the ring goes on the one rung that counts, not on every priced one */
      var marks = function (mark, n, prices, left, use) {
        var out = [];
        for (var k = 0; k < n; k++) {
          var pr = prices && prices[k];
          out.push(k === use && pr ? '<span class="fpz" title="' + esc(pr) + '">' + mark + '</span>' : mark);
        }
        if (!out.length) return '<i class="fmk fmk--none">none</i>';
        /* both sides count outward from the middle, so the priced rungs meet
           in the centre (Jose, Sep 16, 2026) */
        return (left ? out.reverse() : out).join("");
      };
      /* everything counted that carries a price, multiplied out */
      /* a card carries one leg a market: 1+ and 2+ are the same market, so the
         better-paying rung he cleared is the one that counts (Jose, Sep 16,
         2026). A passing leg, a rushing leg and the head to head can ride
         together. */
      var toDec = function (o) {
        var n = parseInt(String(o).replace(/\u2212/g, "-").replace("+", ""), 10);
        return n > 0 ? 1 + n / 100 : 1 + 100 / -n;
      };
      var bestAt = function (prices, hit) {
        var at = -1;
        for (var k = 0; k < Math.min(hit, 2); k++) {
          var o = prices && prices[k];
          if (o && (at < 0 || toDec(o) > toDec(prices[at]))) at = k;
        }
        return at;
      };
      var best = function (prices, hit) {
        var at = bestAt(prices, hit);
        return at < 0 ? null : prices[at];
      };
      var paid = function (r) {
        var legs = [];
        /* touchdowns as they land, the club and the head to head at the
           whistle -- see cardFor */
        var a = best(r.odds[0], r.ptd); if (a) legs.push(a);
        var b2 = best(r.odds[1], r.atd); if (b2) legs.push(b2);
        if (r.h2h === "W" && r.odds[2]) legs.push(r.odds[2]);
        if (r.ml === "W" && r.odds[3]) legs.push(r.odds[3]);   /* the club he won with */
        if (!legs.length) return "";
        var dec = 1;
        legs.forEach(function (o) { dec *= toDec(o); });
        var a = dec >= 2 ? Math.round((dec - 1) * 100) : -Math.round(100 / (dec - 1));
        /* beside what the week paid, what it could have paid: every market the
           board priced that week, at its top rung, whether he cleared it or not.
           So the number reads as a share of the week, not on its own
           (Jose, Sep 18, 2026) */
        var top = function (prices) {
          for (var i = (prices || []).length - 1; i >= 0; i--) if (prices[i]) return prices[i];
          return null;
        };
        var could = [];
        var ta = top(r.odds[0]); if (ta) could.push(ta);
        var tb = top(r.odds[1]); if (tb) could.push(tb);
        if (r.odds[2]) could.push(r.odds[2]);
        if (r.odds[3]) could.push(r.odds[3]);
        var mdec = 1;
        could.forEach(function (o) { mdec *= toDec(o); });
        var m = could.length ? (mdec >= 2 ? Math.round((mdec - 1) * 100) : -Math.round(100 / (mdec - 1))) : 0;
        var outof = (m && Math.abs(m) > Math.abs(a))
          ? '<i class="fof">/ ' + (m > 0 ? "+" : "\u2212") + Math.abs(m) + '</i>' : '';
        /* the price and its ceiling are one thing, so flipping the left side
           swaps the legs against the pair, not against the slash */
        return '<span class="fpaid"><b class="fnum">' + (a > 0 ? "+" : "\u2212") + Math.abs(a) + outof +
               '</b><em>' + legs.length + " leg" + (legs.length > 1 ? "s" : "") + '</em></span>';
      };
      var wl = function (v) { return v === "W" || v === "L" ? '<b class="wl wl--' + v.toLowerCase() + '">' + v + '</b>' : '<b class="wl wl--none">\u2013</b>'; };
      box.innerHTML = order.map(function (gid) {
        /* the better rank stands on the left (Jose, Sep 16, 2026) */
        /* the card shows the man the board priced on each side; anybody else
           who threw is named underneath (Jose, Sep 16, 2026) */
        var all = games[gid].slice().sort(function (a, b) { return a.rank - b.rank; });
        var pair = all.filter(function (r) { return r.carded; });
        var extra = all.filter(function (r) { return !r.carded; });
        if (pair.length < 2) pair = all.slice(0, 2);
        var L = pair[0], R = pair[1] || { name: "", club: "", id: "", ptd: 0, atd: 0, h2h: "", ml: "", yds: 0, rank: "", odds: [[null, null], [null, null], null, null] };
        var gap = Math.abs(L.yds - R.yds);
        /* The week's card, Sep 21, 2026: the two passers on the outside on
           their club's own colour with the club mark behind them, and
           everything counted down the middle -- the score, the yards under
           the VS mark, the passing touchdowns, the rushing ones. The travel
           mark sits in the outer corner, his rank before his name, and a man
           he has ringed takes the gold around the outside of his own half. */
        var hueOfClub = function (club) { return cardHue(String(club || "")); };
        var side = function (m, which) {
          var face = /^\d+$/.test(m.id)
            ? '<img class="qbface mface" data-ring="' + m.id + '" alt="" loading="lazy" src="face/nfl/' +
              m.id + '.png" onerror="this.onerror=null;this.src=NOFACE">'
            : '<img class="qbface mface" alt="" src="' + NOFACE + '">';
          return '<div class="mside mside--' + which +
            (RINGED[String(m.id)] ? " mside--gold" : "") +
            '" style="--hue:' + hueOfClub(m.club) + ';--mark:url(logos/nfl/' +
            String(m.club || "").toLowerCase() + '.png)">' + face +
            '<span class="mname"><em>' + (m.rank || "") + "</em>" +
            esc(famName(m.name)) + hurtMark(m.id) + coldMark(m.id) + "</span>" +
            '<i class="mtrav">' + (m.side === 1 ? HOUSE : PLANE) + "</i></div>";
        };
        var line = function (mark, a, b, big) {
          var cls = function (mine, his) { return mine > his ? " mv--on" : ""; };
          return '<div class="wrow' + (big ? " wrow--big" : "") + '">' +
            '<b class="mv' + cls(a, b) + '">' + a + "</b>" +
            '<i class="mmk">' + mark + "</i>" +
            '<b class="mv' + cls(b, a) + '">' + b + "</b></div>";
        };
        var shown = (L.score === undefined || L.score === null ||
                     R.score === undefined || R.score === null);
        return '<div class="mcard">' + side(L, "l") +
          '<div class="mmid">' +
            '<div class="wrow wrow--score"><b class="msc' +
              ((L.score || 0) > (R.score || 0) ? " msc--won" : "") + '">' +
              (shown ? "\u2013" : L.score) + "</b>" +
              '<i class="mmk"><span class="myd">' + (shown ? "" : "FINAL") + "</span></i>" +
              '<b class="msc' + ((R.score || 0) > (L.score || 0) ? " msc--won" : "") + '">' +
              (shown ? "\u2013" : R.score) + "</b></div>" +
            line(VSMARK, L.yds, R.yds, true) +
            line(BALLSVG, L.ptd, R.ptd) +
            line(RUSHSVG, L.atd, R.atd) +
          "</div>" + side(R, "r") + "</div>";
      }).join("");
      BOARD.appendChild(box); return;
    }
    /* a week: one football per passing touchdown, one runner per rushing one,
       a W tile for the head to head and one for the club -- only when won;
       nothing is written for what did not happen. The season: each mark once
       with a count, and the tiles with how many won. (Jose, Sep 16, 2026) */
    /* the season writes all four, x0 included, so the rows read as four even columns */
    var times = function (mark, n) { return '<span class="fgrp' + (n ? "" : " fgrp--zero") + '">' + mark + '<em>\u00d7' + n + '</em></span>'; };
    box.innerHTML = rows.map(function (r, i) {
      var face = ledgerFace(r);
      var marks;
      if (r.agg) {
        marks = times(BALL, r.ptd) + times(RUN, r.atd) + times(W("H2H"), r.h2hw) + times(W("ML"), r.mlw);
      } else {
        marks = "";
        for (var k = 0; k < r.ptd; k++) marks += BALL;
        for (var k2 = 0; k2 < r.atd; k2++) marks += RUN;
        if (r.h2h === "W") marks += W("H2H");
        if (r.ml === "W") marks += W("ML");
      }
      return '<div class="frow' + (r.agg ? " frow--agg" : "") + '"><span class="frank">' + (i + 1) + '</span>' +
        '<span class="fwho">' + face + '<span class="fname">' + nameMark(r) + '<small>' + esc(r.club) + '</small></span></span>' +
        '<span class="fmks">' + (marks || '<i class="fmk fmk--none">\u2013</i>') + '</span></div>';
    }).join("");
    BOARD.appendChild(box);
  }
  /* what each fighter has done: wins-losses, and the draws only where there
     are any. ESPN keeps it on the athlete, records_mma.py asks once a man
     and writes site/fighters.json (Jose, Sep 19, 2026) */
  var FIGHTREC = {};
  function fightRec(card) {
    if (!card || !card.dataset.bout) return;
    var sides = card.querySelectorAll(".ghead--fight .gteam");
    var ids = [card.dataset.lfid, card.dataset.rfid];
    for (var i = 0; i < sides.length && i < 2; i++) {
      var nm = sides[i].querySelector(".fname");
      if (!nm) continue;
      /* the record's place is the top of the card, inside, across from the
         rank: the slot seatRecord made. Written beside the name instead, it
         left that slot empty on every bout drawn before the file came in --
         the whole DWCS card (Jose, Sep 29, 2026) */
      var head = card.querySelector(".ghead--fight");
      var slot = head && head.querySelector(":scope > .frec--" + (i === 0 ? "l" : "r"));
      var old = slot || nm.querySelector(".frec");
      if (slot) nm.querySelectorAll(".frec").forEach(function (x) { x.remove(); });
      var rec = FIGHTREC[ids[i]];
      if (!rec) { if (old && !slot) old.remove(); else if (old) old.textContent = ""; continue; }
      var bits = String(rec).split("-");
      var say = bits.length > 2 && bits[2] !== "0"
              ? bits[0] + "-" + bits[1] + "-" + bits[2]
              : bits[0] + "-" + bits[1];
      if (!old) { old = document.createElement("i"); old.className = "frec"; nm.appendChild(old); }
      old.textContent = say;
    }
  }
  fetch("fighters.json").then(function (r) { return r.json(); }).then(function (j) {
    FIGHTREC = j;
    document.querySelectorAll(".gcard[data-bout]").forEach(fightRec);
  }).catch(function () {});
  fetch("records.json").then(function (r) { return r.json(); }).then(function (j) {
    RECORDS = j;
    document.querySelectorAll(".gcard[data-lg=nfl], .gcard[data-lg=college-football]").forEach(dressRecords);
  }).catch(function () {});
  fetch("networks.json").then(function (r) { return r.json(); }).then(function (j) {
    NETWORKS = j;
    document.querySelectorAll(".gcard[data-espn] a.gwatch--yt").forEach(function (a) {
      var card = cardOf(a), fresh = watchMark(card.dataset.espn);
      a.outerHTML = fresh;
    });
  }).catch(function () {});
  var LIVEROWS = {};          /* game id -> { espn id: {ptd, atd, yds} } */
  var LIVEASK = {};
  var LIVEKICK = null;
  function liveWeek(rows, after) {
    var want = {};
    rows.forEach(function (r) {
      /* a game is still open until its club result is settled: a score alone
         means nothing, because the ledger stamps one the moment it is rebuilt
         mid-game, and reading that as final stopped the page asking ESPN about
         a game being played (Jose, Sep 17, 2026) */
      if (r.game && (r.score === undefined || r.score === null || r.ml === "")) want[r.game] = 1;
    });
    /* a fixture that has not kicked has nothing to read: the ledger writes a
       row for every game in the week, so without this the form page asked
       ESPN about Sunday's games all through Friday (Jose, Sep 18, 2026) */
    if (!LIVEKICK) {
      LIVEKICK = {};
      (typeof SCHED !== "undefined" ? SCHED : []).forEach(function (g) {
        LIVEKICK[String(g[1])] = Date.parse(g[2]) || 0;
      });
    }
    var ids = Object.keys(want).filter(function (g) {
      var k = LIVEKICK[String(g)];
      if (k && k > Date.now() + 20 * 60000) return false;
      return !LIVEASK[g] || Date.now() - LIVEASK[g] > 20000;
    });
    if (!ids.length) return;
    ids.forEach(function (g) { LIVEASK[g] = Date.now(); });
    Promise.all(ids.map(function (g) {
      return gameFeed(g, "nfl")
        .then(function (d) {
          var st = ((((d.header || {}).competitions || [{}])[0].status || {}).type || {});
          /* and a game that is over, not only one being played. It stopped
             reading at the whistle, which is the one moment everything the
             money page wants is finally true, so the page sat on the last
             live figures until a rebuild came round hours later
             (Jose, Sep 20, 2026: "once we get a stat on the page from the
             NFL card it can take it there... it's not that hard to connect
             them") */
          if (st.state !== "in" && st.state !== "post") return;
          var by = {};
          ((d.boxscore || {}).players || []).forEach(function (t) {
            (t.statistics || []).forEach(function (c) {
              if (c.name !== "passing" && c.name !== "rushing") return;
              (c.athletes || []).forEach(function (a) {
                var id = String(((a.athlete || {}).id) || "");
                if (!id) return;
                var line = {};
                (c.labels || []).forEach(function (L, i) { line[L] = (a.stats || [])[i]; });
                by[id] = by[id] || {};
                if (c.name === "passing") {
                  by[id].ptd = parseInt(line.TD, 10);
                  by[id].yds = parseInt(line.YDS, 10);
                } else {
                  by[id].atd = parseInt(line.TD, 10);
                }
              });
            });
          });
          /* the score on the card comes with the same read, so it moves with
             the numbers instead of sitting at whatever the last rebuild saw */
          var sc = {};
          ((((d.header || {}).competitions || [{}])[0]).competitors || []).forEach(function (x) {
            var ab = ((x.team || {}).abbreviation) || "";
            if (ab) sc[ab] = parseInt(x.score, 10);
          });
          by._sc = sc;
          /* who won, and whether it is over: the two things the head to head
             and the moneyline wait for */
          var won = {};
          ((((d.header || {}).competitions || [{}])[0]).competitors || []).forEach(function (x) {
            var ab = ((x.team || {}).abbreviation) || "";
            if (ab) won[ab] = !!x.winner;
          });
          by._won = won;
          by._fin = st.state === "post";
          LIVEROWS[g] = by;
        }).catch(function () {});
    })).then(after);
  }
  /* The same read, wherever it comes from: the week's poll or a card that has
     just settled. A card's refresh already holds the whole summary the moment
     the game goes final, so the ledger settles off that read rather than
     waiting for the next minute to come round (Jose, Sep 20, 2026: "as soon
     as it settles on the card it can settle in the ledger immediately"). */
  function takeBox(gid, d) {
    var st = ((((d.header || {}).competitions || [{}])[0].status || {}).type || {});
    if (st.state !== "in" && st.state !== "post") return false;
    var by = {};
    ((d.boxscore || {}).players || []).forEach(function (t) {
      (t.statistics || []).forEach(function (c) {
        if (c.name !== "passing" && c.name !== "rushing") return;
        (c.athletes || []).forEach(function (a) {
          var id = String(((a.athlete || {}).id) || "");
          if (!id) return;
          var line = {};
          (c.labels || []).forEach(function (L, i) { line[L] = (a.stats || [])[i]; });
          by[id] = by[id] || {};
          if (c.name === "passing") {
            by[id].ptd = parseInt(line.TD, 10);
            by[id].yds = parseInt(line.YDS, 10);
          } else {
            by[id].atd = parseInt(line.TD, 10);
          }
        });
      });
    });
    var sc = {}, won = {};
    ((((d.header || {}).competitions || [{}])[0]).competitors || []).forEach(function (x) {
      var ab = ((x.team || {}).abbreviation) || "";
      if (!ab) return;
      sc[ab] = parseInt(x.score, 10);
      won[ab] = !!x.winner;
    });
    by._sc = sc; by._won = won; by._fin = st.state === "post";
    LIVEROWS[String(gid)] = by;
    return true;
  }
  /* and the money page is redrawn there and then if he is looking at it */
  function ledgerNow(gid, d) {
    if (!takeBox(gid, d)) return;
    if (sport !== "form" || !LEDGER) return;
    var at = window.scrollY;
    if (formWeek === "season") renderMoney(); else renderForm();
    window.scrollTo(0, at);
  }
  window.ledgerNow = ledgerNow;
  function layLive(rows) {
    rows.forEach(function (r) {
      var by = LIVEROWS[r.game];
      if (by && by._sc && r.club && !isNaN(by._sc[r.club])) r.score = by._sc[r.club];
      var mine = by && by[String(r.id)];
      if (!mine) return;
      if (!isNaN(mine.ptd)) r.ptd = mine.ptd;
      if (!isNaN(mine.atd)) r.atd = mine.atd;
      if (!isNaN(mine.yds)) r.yds = mine.yds;
      /* and at the whistle the rest of it settles here, off the same read,
         rather than waiting for the ledger to be built again: the club result
         from who ESPN says won, the head to head from the two men's yards.
         The prices were already on the row before the game (Jose, Sep 20,
         2026) */
      if (!by._fin) return;
      r.fin = true;
      if (by._won && r.club && (r.club in by._won)) r.ml = by._won[r.club] ? "W" : "L";
      var him = rows.filter(function (o) {
        return o.game === r.game && String(o.id) !== String(r.id);
      })[0];
      var his = him && LIVEROWS[r.game] && LIVEROWS[r.game][String(him.id)];
      if (his && !isNaN(his.yds) && !isNaN(mine.yds) && his.yds !== mine.yds) {
        r.h2h = mine.yds > his.yds ? "W" : "L";
      }
    });
  }
  function loadLedger(then) {
    /* the wire is asked for the first time the ledger is, so the marks are
       on the page the moment it draws rather than a minute later */
    if (!WIREAT) { WIREAT = 1; pullWire(); }
    if (LEDGER) return then();
    fetch("ledger.json").then(function (r) { return r.json(); }).then(function (j) { LEDGER = j; then(); })
      .catch(function () { LEDGER = {}; then(); });
  }
  /* the wire rides with the ledger: it is read once on the way in and
     again on the ledger's own beat, and a read that fails leaves it empty
     rather than leaving yesterday's marks on the page */
  function pullWire() {
    fetch("wire.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || JSON.stringify(j) === JSON.stringify(WIRE)) return;
        WIRE = j;
        /* the cards wear the mark too, so an arrival re-seats them rather than
           only redrawing the Form tab (Jose, Sep 22, 2026) */
        if (sport === "form") { var at = window.scrollY; render(); window.scrollTo(0, at); return; }
        if (typeof seatHurt === "function") document.querySelectorAll(".gcard").forEach(seatHurt);
      })
      .catch(function () {});
    fetch("cold.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var c = (j && j.cold) || {};
        if (JSON.stringify(c) === JSON.stringify(COLD)) return;
        COLD = c;
        if (sport === "form") { var at = window.scrollY; render(); window.scrollTo(0, at); }
      })
      .catch(function () {});
    /* the birthdays ride along too: the file is keyed by game and the border
       is seated the same way the mark is */
    fetch("birthdays.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || JSON.stringify(j) === JSON.stringify(BIRTHDAYS)) return;
        BIRTHDAYS = j;
        if (typeof seatBday === "function") document.querySelectorAll(".gcard").forEach(seatBday);
      })
      .catch(function () {});
    /* the chart rides with the wire, since neither answers alone: the wire
       says he is hurt, the chart says whether he still plays */
    fetch("depth.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (!j || JSON.stringify(j) === JSON.stringify(DEPTH)) return;
        DEPTH = j;
        if (sport === "form") { var at = window.scrollY; render(); window.scrollTo(0, at); return; }
        if (typeof seatHurt === "function") document.querySelectorAll(".gcard").forEach(seatHurt);
      })
      .catch(function () {});
  }
  /* The ledger was read once, when the tab was opened, and never again -- so
     the cards moved with the games and the money page sat at whatever it said
     an hour ago. It is asked for on the same beat as the prices now, and the
     page is drawn again only when a digit of it has actually changed, so
     nothing moves under him for nothing (Jose, Sep 20, 2026: "when one
     updates they all should"). */
  var LEDGERAT = "";
  /* The record in a card's top corner is read out of the ledger, and the
     ledger was only ever fetched for the Form tab -- so a game card drawn
     before its beat had nothing to read and no reason to look again. That is
     why the corners showed on some week 3 cards and not others, and why a
     headless test never caught it: the test was slow enough that the fetch
     always won (Jose, Sep 22, 2026: "it didnt appear for all the teams").
     Every arrival re-seats the corners now. */
  function ledgerLanded() {
    if (sport === "form") { var at = window.scrollY; render(); window.scrollTo(0, at); return; }
    if (typeof seatClubRec !== "function") return;
    document.querySelectorAll(".gcard").forEach(seatClubRec);
  }
  function pullLedger() {
    if (document.hidden) return;
    fetch("ledger.json", { cache: "no-store" })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (t) {
        if (!t || t === LEDGERAT) return;
        var j;
        try { j = JSON.parse(t); } catch (e) { return; }
        LEDGERAT = t;
        LEDGER = j;
        ledgerLanded();
      })
      .catch(function () {});
    pullWire();
  }
  function render() {
    /* HOT's field, scoreboard and scroll lock belong to HOT alone: any other
       board drawn -- a week's cards on Form, another sport -- takes them down,
       or the field and the black scoreboard showed through behind a week's
       cards (Jose, Sep 28, 2026: "there's a leak") */
    if (BOARD === MAINBOARD && (sport !== "form" || formWeek !== "season"))
      document.documentElement.classList.remove("hotlock");
    if (sport === "form") {
      loadLedger(function () {
        if (BOARD === MAINBOARD) formTabs();
        /* the season is what the weeks paid; a week is its own cards */
        if (formWeek === "season") renderMoney(); else renderForm();
      });
      if (BOARD === MAINBOARD) formLive();
      return;
    }
    var items = [], kind = railKind(), byWeek = kind === "week";
    var on = function (iso) {
      if (kind === "week") return weekKeyOf(iso) === day;
      if (kind === "month") return monthKeyOf(iso) === day;
      return dayKeyOf(iso) === day;
    };
    /* the rail's week already says which dates are wanted, and a college week
       number is not an NFL one, so the league's own week is only asked about
       when the rail is still on a day (Jose, Sep 18, 2026) */
    if (sport === "all" || sport === "nfl") {
      items = items.concat(nflItems(SCHED.filter(function (g) {
        return on(g[2]) && (byWeek || sport !== "nfl" || g[0] === week);
      })));
    }
    if (sport === "all" || sport === "college-football") {
      items = items.concat(cfbItems(CFB.filter(function (g) {
        return on(g[2]) && (byWeek || sport !== "college-football" || g[0] === cfbWeek);
      })));
    }
    if (sport === "mma") {
      /* one card at a time: the poster the row is stopped on */
      var ev = ufcCard();
      items = items.concat(fightItems(FIGHTS.filter(function (f) { return f[0] === ev; })));
    } else if (sport === "all") {
      items = items.concat(fightItems(FIGHTS.filter(function (f) { return on(f[2]); })));
    }
    build(items, sport === "all");
    if (sport === "mma" && BOARD === MAINBOARD) {
      posterRow();
      /* one card under its poster: it opens by itself */
      var hb = BOARD.querySelector(".slot-h--bill");
      if (hb && hb.getAttribute("aria-expanded") !== "true") hb.click();
    }
  }
  /* ---- the posters (build/posters.py keeps them, from Wikipedia) ---- */
  var UFCEV = null, POSTERS = null, PCAR = null;
  /* the month the rail is on, its cards only (Jose, Sep 25, 2026: "sorting
     by the month") */
  function ufcCards() {
    var has = {}, mo = /^\d{4}-\d{2}$/.test(day) ? day : "";
    FIGHTS.forEach(function (f) { has[f[0]] = 1; });
    return FIGHTCARDS.filter(function (c) { return has[c[1]] && (!mo || monthKeyOf(c[2]) === mo); })
      .sort(function (a, b) { return Date.parse(a[2]) - Date.parse(b[2]); });
  }
  /* the card on show: the one picked, kept while the rail's month holds it;
     a new month opens on its next card to come, else its first */
  function ufcCard() {
    var cs = ufcCards(), mo = /^\d{4}-\d{2}$/.test(day) ? day : "";
    var cur = cs.filter(function (c) { return c[1] === UFCEV; })[0];
    if (cur && (!mo || monthKeyOf(cur[2]) === mo)) return UFCEV;
    var soon = Date.now() - 12 * 3600e3;
    var pool = mo ? cs.filter(function (c) { return monthKeyOf(c[2]) === mo; }) : cs;
    if (!pool.length) pool = cs;
    var pick = pool.filter(function (c) { return Date.parse(c[2]) >= soon; })[0] || (mo ? pool[0] : pool[pool.length - 1]);
    UFCEV = pick ? pick[1] : null;
    return UFCEV;
  }
  function posterRow() {
    var cs = ufcCards();
    if (!cs.length) return;
    if (!PCAR) {
      PCAR = document.createElement("div");
      PCAR.className = "pcar";
      var settle = 0;
      PCAR.addEventListener("scroll", function () {
        clearTimeout(settle);
        settle = setTimeout(function () {
          var mid = PCAR.scrollLeft + PCAR.clientWidth / 2, best = null, gap = Infinity;
          PCAR.querySelectorAll(".pc").forEach(function (el) {
            var d = Math.abs(el.offsetLeft + el.offsetWidth / 2 - mid);
            if (d < gap) { gap = d; best = el; }
          });
          if (!best || best.dataset.ev === UFCEV) return;
          UFCEV = best.dataset.ev;
          PCAR.querySelectorAll(".pc").forEach(function (el) { el.classList.toggle("on", el === best); });
          /* the rail follows the poster to its month */
          var mk = monthKeyOf(best.dataset.at);
          if (mk !== day) {
            day = mk;
            dbar.querySelectorAll(".dtab").forEach(function (x) {
              x.setAttribute("aria-selected", x.dataset.day === day ? "true" : "false");
            });
          }
          var keep = PCAR.scrollLeft;
          render();
          PCAR.scrollLeft = keep;
        }, 140);
      });
      PCAR.addEventListener("click", function (e) {
        var el = e.target.closest(".pc");
        if (el) PCAR.scrollTo({ left: el.offsetLeft + el.offsetWidth / 2 - PCAR.clientWidth / 2, behavior: "smooth" });
      });
    }
    var draw = function () {
      PCAR.innerHTML = cs.map(function (c) {
        var src = POSTERS && POSTERS[c[1]];
        var nm = String(c[3] || ""), when = new Date(c[2]).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "America/New_York" }).toUpperCase();
        var face, wk = /Contender Series.*Week (\d+)/i.exec(nm), zb = /^Zuffa Boxing (\d+)/i.exec(nm);
        /* the Contender Series wears its own art, the week on it (Jose, Sep 25, 2026) */
        if (wk) face = '<img src="img/posters/dwcs.jpg" alt="Contender Series week ' + wk[1] + '" loading="lazy">' +
                       '<span class="pcwk">WEEK ' + wk[1] + '</span>';
        /* a numbered Zuffa show has no poster of its own: the Zuffa art, its number on it */
        else if (zb && !src) face = '<img src="img/posters/zuffa.jpg" alt="Zuffa Boxing ' + zb[1] + '" loading="lazy">' +
                       '<span class="pcwk pcwk--zb">' + zb[1] + '</span>';
        else if (src) face = '<img src="' + src + '" alt="' + nm.replace(/"/g, "&quot;") + '" loading="lazy">';
        else {
          /* no poster yet: the card's own name, drawn */
          var dw = /Contender Series.*Week (\d+)/i.exec(nm), num = /^(UFC \d+|Noche UFC|UFC Freedom 250)/.exec(nm);
          var top = dw ? "DWCS" : num ? num[1].toUpperCase() : "UFC FIGHT NIGHT";
          var sub = dw ? "WEEK " + dw[1] : (nm.split(": ")[1] || "");
          face = '<div class="pcx"><b>' + top + '</b><i>' + sub + '</i><u>' + when + '</u></div>';
        }
        return '<div class="pc' + (c[1] === UFCEV ? " on" : "") + '" data-ev="' + c[1] + '" data-at="' + c[2] + '">' + face + '</div>';
      }).join("");
    };
    draw();
    BOARD.insertBefore(PCAR, BOARD.firstChild);
    var seat = function (smooth) {
      var el = PCAR.querySelector('.pc[data-ev="' + UFCEV + '"]');
      if (el) PCAR.scrollTo({ left: el.offsetLeft + el.offsetWidth / 2 - PCAR.clientWidth / 2, behavior: smooth ? "smooth" : "auto" });
    };
    requestAnimationFrame(function () { seat(false); });
    if (!POSTERS) {
      POSTERS = {};
      fetch("posters.json", { cache: "no-store" }).then(function (r) { return r.json(); })
        .then(function (j) { POSTERS = j || {}; var keep = PCAR.scrollLeft; draw(); PCAR.scrollLeft = keep; })
        .catch(function () {});
    }
  }

  function dayKeyOf(iso) {
    var p = etParts(iso);
    return p.day + " " + p.date;
  }

  /* ---- the day rail ---- */
  var DAYS = (function () {
    var seen = {}, all = [], now = Date.now();
    function add(iso) {
      var k = dayKeyOf(iso);
      if (seen[k]) return;
      var t = Date.parse(iso);
      if (t < now - 4 * 86400000 || t > now + 22 * 86400000) return;
      seen[k] = 1;
      all.push([k, iso]);
    }
    SCHED.forEach(function (g) { add(g[2]); });
    CFB.forEach(function (g) { add(g[2]); });
    FIGHTS.forEach(function (f) { add(f[2]); });
    all.sort(function (a, b) { return Date.parse(a[1]) - Date.parse(b[1]); });
    return all;
  })();

  var dbar = document.getElementById("daybar");
  var wbar = document.getElementById("weekbar");
  var today = dayKeyOf(new Date().toISOString());

  /* Which days the rail offers depends on what is selected: the whole run
     when there is no week, and only that week's days when there is one. */
  /* ---- the rail lists weeks ----
     The day used to be the rail and the board showed one day at a time. The
     day now rides the slot line instead -- "CFB FRI 9/18 7:30 PM" -- so the
     rail carries the week and the board shows every day in it, in clock order
     (Jose, Sep 18, 2026).

     A week is the NFL's: it begins a day and a half before that week's first
     kickoff, which puts the Tuesday and Wednesday college games in the week
     they belong to, and runs until the next one begins. */
  /* A week is a span of dates, and the two leagues do not share one. College
     week 3 runs Sep 17 to 20, which falls inside the NFL's week 2, so college
     games were being filed a week early -- the rail said WEEK 2 and drew week
     3's fixtures (Jose, Sep 22, 2026). Each league gets its own table, built
     from its own schedule, and nothing reads the other's.
     NFL is NFL; anything that is not NFL is college (Jose, Sep 22, 2026:
     "nfl is NFL and if not NFL its CFB"). */
  function spansOf(rows) {
    var first = {};
    rows.forEach(function (g) {
      var t = Date.parse(g[2]), w = +g[0];
      if (!first[w] || t < first[w]) first[w] = t;
    });
    var ws = Object.keys(first).map(Number).sort(function (a, b) { return a - b; });
    return ws.map(function (w, i) {
      return { w: w, at: first[w],
               from: first[w] - 36 * 3600000,
               to: i + 1 < ws.length ? first[ws[i + 1]] - 36 * 3600000
                                     : first[w] + 14 * 86400000 };
    });
  }
  var WEEKSPAN = spansOf(SCHED);
  var CFBSPAN = spansOf(CFB);
  /* whichever league the rail is counting for */
  function spans() { return sport === "college-football" ? CFBSPAN : WEEKSPAN; }
  function weekKeyOf(iso) {
    var t = Date.parse(iso), sp = spans();
    for (var i = 0; i < sp.length; i++) {
      if (t >= sp[i].from && t < sp[i].to) return "W" + sp[i].w;
    }
    return "";
  }
  function weeksNow() {
    var now = Date.now();
    /* every week the season has had, and a month ahead. There used to be a
       nine-day look back, which was fine while both leagues counted on the
       NFL's calendar -- but college starts a fortnight earlier, so its week
       one ended on Sep 9 and fell straight off the rail the moment it began
       counting its own (Jose, Sep 22, 2026: "you dont have week 1"). The rail
       scrolls and opens on the current week, so carrying the earlier ones
       costs nothing. */
    /* and every week still to come, not only a month ahead: the long-press
       picker runs to Week 18 (Jose, Sep 23, 2026: "why aren't you doing all
       the weeks that are available") */
    return spans().map(function (x) { return ["W" + x.w, new Date(x.at).toISOString()]; });
  }

  /* what the rail carries, per sport: the calendar keeps its days, the two
     football leagues run on weeks, and the fights run on months -- a card is
     an evening, not a week (Jose, Sep 18, 2026) */
  function railKind() {
    if (sport === "nfl" || sport === "college-football") return "week";
    if (sport === "mma") return "month";
    return "day";
  }
  function daysNow() {
    var k = railKind();
    if (k === "week") return weeksNow();
    if (k === "month") return monthsNow();
    return DAYS;
  }
  function monthsNow() {
    var seen = {}, out = [];
    FIGHTS.slice().sort(function (a, b) { return Date.parse(a[2]) - Date.parse(b[2]); })
      .forEach(function (f) {
        var k = monthKeyOf(f[2]);
        if (seen[k]) return;
        seen[k] = 1; out.push([k, f[2]]);
      });
    return out;
  }
  function daysOld() {
    if (sport === "nfl") return daysOf(SCHED, week);
    if (sport === "college-football") return daysOf(CFB, cfbWeek);
    return DAYS;
  }
  function mmaDays() {
    {
      var seen = {}, out = [];
      FIGHTS.forEach(function (f) {
        var k = dayKeyOf(f[2]);
        if (seen[k] || monthKeyOf(f[2]) !== mmaMonth) return;
        seen[k] = 1; out.push([k, f[2]]);
      });
      out.sort(function (a, b) { return Date.parse(a[1]) - Date.parse(b[1]); });
      return out;
    }
    return DAYS;
  }
  function daysOf(list, w) {
    var seen = {}, out = [];
    list.forEach(function (g) {
      if (g[0] !== w) return;
      var k = dayKeyOf(g[2]);
      if (!seen[k]) { seen[k] = 1; out.push([k, g[2]]); }
    });
    out.sort(function (a, b) { return Date.parse(a[1]) - Date.parse(b[1]); });
    return out;
  }
  function buildDays() {
    var list = daysNow();
    dbar.innerHTML = "";
    list.forEach(function (d) {
      var t = document.createElement("button");
      t.className = "dtab";
      t.type = "button";
      t.setAttribute("role", "tab");
      t.dataset.day = d[0];
      if (/^W\d+$/.test(d[0])) {
        t.innerHTML = "<b>WEEK " + d[0].slice(1) + "</b>";
      } else if (/^\d{4}-\d{2}$/.test(d[0])) {
        /* the month alone: "SEP 26" was read as the twenty-sixth, not 2026,
           and every card on the board is this year anyway (Jose, Sep 18, 2026) */
        var mn = ["JAN","FEB","MAR","APR","MAY","JUN",
                  "JUL","AUG","SEP","OCT","NOV","DEC"][+d[0].slice(5) - 1];
        t.innerHTML = "<b>" + mn + "</b>";
      } else {
        var bits = d[0].split(" ");
        t.innerHTML = "<b>" + (d[0] === today ? "Today" : bits[0]) + "</b><i>" +
                      bits[1] + "</i>";
      }
      dbar.appendChild(t);
    });
    if (!list.some(function (d) { return d[0] === day; })) {
      var pick = openingDay(list);
      day = pick ? pick[0] : day;
    }
    markDay();
  }

  function markDay(scroll) {
    dbar.querySelectorAll(".dtab").forEach(function (t) {
      var on = t.dataset.day === day;
      t.setAttribute("aria-selected", on ? "true" : "false");
      if (on && scroll !== false) {
        t.scrollIntoView({block: "nearest", inline: "center"});
      }
    });
  }
  /* two taps on a day -- or a week, on the football rails -- ask DraftKings
     for every price its cards are still short of, there and then: the job
     the Stacked mark's double tap did, on the tab it is about (Jose, Oct 1,
     2026). Timed by when the finger tapped, since the first tap redraws */
  var dayTapAt = 0, dayTapOn = null, nflTapAt = 0;
  /* heard on the page before the tab change's crossfade takes the tap and
     replays it; the replay is not a second tap */
  var allTapAt = 0, tapFreeAt = 0;
  /* heard last, once the tab's own handlers have drawn the board */
  document.addEventListener("click", function (e) {
    if (e.target.closest && e.target.closest(".sptab")) tapFreeAt = performance.now();
  });
  document.addEventListener("click", function (e) {
    var sp = e.target.closest && e.target.closest(".sptab");
    /* the first tap starts the tab change's crossfade, and on the phone the
       second lands on the fade's picture, not on the icon: the tab is found
       by where the finger is instead (Jose, Oct 1, 2026: "it's not filling
       up like it did for the stacked logo") */
    if (!sp && e.clientX != null) {
      sbar.querySelectorAll(".sptab").forEach(function (x) {
        var r = x.getBoundingClientRect();
        if (e.clientX >= r.left && e.clientX <= r.right && e.clientY >= r.top && e.clientY <= r.bottom) sp = x;
      });
    }
    if (window._vtNow || !sp) return;
    /* the first tap redraws the board, and the second waits behind the
       drawing: the gap is counted from when the drawing was done */
    /* one clock for both: Safari stamps events on its own, not on
       performance.now(), so a tap is timed when it is heard */
    var heard = performance.now();
    var since = function (at) { return heard - Math.max(at, tapFreeAt); };
    if (sp.dataset.sp === "nfl") {
      if (nflTapAt && since(nflTapAt) < 420) {
        nflTapAt = 0;
        if (typeof window._askWeek === "function") window._askWeek(sp);
        return;
      }
      nflTapAt = heard;
    }
    /* the day page's own icon, at the end of the nav: two taps ask
       DraftKings for every price the day's cards are short of, the job the
       Stacked mark's double tap did, with its fill on this icon (Jose, Oct 1,
       2026: "the day tab next to the NFL logo in the nav") */
    if (sp.dataset.sp === "all") {
      if (allTapAt && since(allTapAt) < 420) {
        allTapAt = 0;
        /* after the first tap has drawn the day */
        setTimeout(function () { if (typeof window._askDay === "function") window._askDay(sp); }, 60);
        return;
      }
      allTapAt = heard;
    }
  }, true);
  dbar.addEventListener("click", function (e) {
    var t = e.target.closest(".dtab");
    if (!t) return;
    if (dayTapOn === t.dataset.day && e.timeStamp - dayTapAt < 420) {
      dayTapAt = 0; dayTapOn = null;
      if (typeof window._askDay === "function") window._askDay(t);
      return;
    }
    dayTapAt = e.timeStamp; dayTapOn = t.dataset.day;
    day = t.dataset.day;
    markDay();
    render();
  });

  /* ---- a swipe slides a day ----
     The neighbouring days are drawn into the side panes as the finger starts
     to move, and the track follows it; on release it glides to the neighbour
     and that day becomes the day, or glides back. A carousel row that can
     scroll keeps its own sideways movement; the rails, the sport bar and an
     open sheet keep theirs. Past the last day of a week the next pane is the
     next week's first day, and back the same way; for the fights it is the
     month. (Jose, Sep 16, 2026: "I should be able to see the previous page
     and the next page") */
  var TRACK = document.getElementById("track");
  var PANES = { "-1": document.getElementById("paneprev"), "1": document.getElementById("panenext") };
  function stateNow() { return { day: day, week: week, cfbWeek: cfbWeek, mmaMonth: mmaMonth, formWeek: formWeek }; }
  function applyState(st) { day = st.day; week = st.week; cfbWeek = st.cfbWeek; mmaMonth = st.mmaMonth; formWeek = st.formWeek; }
  function neighborState(dir) {
    if (sport === "form") {
      /* the form page swipes along its own rail: season, then the weeks */
      var lws = [].slice.call(wbar.querySelectorAll(".wktab")).map(function (t) { return t.dataset.lw; });
      var k = lws.indexOf(formWeek) + dir;
      if (k < 0 || k >= lws.length) return null;
      var sf = stateNow(); sf.formWeek = lws[k]; return sf;
    }
    var list = daysNow(), i = -1;
    list.forEach(function (d, k) { if (d[0] === day) i = k; });
    var j = i + dir;
    if (j >= 0 && j < list.length) { var st0 = stateNow(); st0.day = list[j][0]; return st0; }
    if (wbar.hidden) return null;
    var tabs = [].slice.call(wbar.querySelectorAll(".wktab"));
    var on = -1;
    tabs.forEach(function (t, k) { if (t.getAttribute("aria-selected") === "true") on = k; });
    var next = tabs[on + dir];
    if (!next) return null;
    var st = stateNow();
    if (sport === "mma") st.mmaMonth = next.dataset.mo;
    else if (sport === "nfl") st.week = Number(next.dataset.wk);
    else st.cfbWeek = Number(next.dataset.wk);
    var keep = stateNow(); applyState(st); var fresh = daysNow(); applyState(keep);
    if (!fresh.length) return null;
    st.day = (dir > 0 ? fresh[0] : fresh[fresh.length - 1])[0];
    return st;
  }
  function clearPane(pane) {
    pane.querySelectorAll(".gcard").forEach(function (c) { if (c.dataset.pooled) POOL.appendChild(c); });
    pane.innerHTML = "";
  }
  function renderInto(pane, st) {
    var keep = stateNow(), keepBoard = BOARD;
    applyState(st); BOARD = pane;
    try { render(); } finally { applyState(keep); BOARD = keepBoard; }
  }
  function commit(st) {
    applyState(st);
    if (sport === "form") { formTabs(); render(); window.scrollTo(0, 0); return; }
    wbar.querySelectorAll(".wktab").forEach(function (x) {
      var on = sport === "mma" ? x.dataset.mo === mmaMonth
             : Number(x.dataset.wk) === (sport === "nfl" ? week : cfbWeek);
      x.setAttribute("aria-selected", on ? "true" : "false");
      if (on) x.scrollIntoView({ block: "nearest", inline: "center" });
    });
    buildDays();
    markDay(true);
    render();
    window.scrollTo(0, 0);
  }
  /* every piece that is dragged for its own sake: the wallet, the eye's
     track, a hide corner, the live graph, the slip, the pick ghost, the
     field, the search. A finger that starts on one of them belongs to it --
     never to the board's swipe and never to the pull-down search (Jose, Sep
     28, 2026: "I hold the wallet and swipe down and it thinks I'm swiping
     down for the search"). One list, read by both. */
  /* the clips rows slide on their own, and a swipe down on a story leaves it
     (Jose, Sep 29, 2026: the row took him to the next week, and the swipe
     down out of a clip opened the search) */
  var OWNDRAG = window.OWNDRAG = ".fturf, .fslots, .pickghost, dialog, .slipbar, .htrack, .gcorner, .drvg, .cashfab, .cashsheet, #qsearch, input, textarea, .cliprow, .gamerow, #clipstory, #clipshow";
  (function () {
    var x0 = 0, y0 = 0, t0 = 0, ok = false, drag = false, dx = 0, sides = {};
    function width() { return TRACK.getBoundingClientRect().width; }
    document.addEventListener("touchstart", function (e) {
      var t = e.touches[0], caro = e.target.closest(".caro, .form.qcards");
      /* .htrack is the eye's own room: a finger that starts there is hiding a
         card, not swiping the board, and both at once means the card slides
         out from under the thumb (Jose, Sep 22, 2026: "if I'm on that actual
         piece it should not swipe"). .drvg is the live graph, read by holding
         a finger on it and dragging along it, which is the same argument.The
         dollar button is dragged the same way (Jose, Sep 25, 2026). */
      ok = !e.target.closest(".pcar, .daybar, .weekbar, .tabbar, .fview, " + OWNDRAG) &&
           !(caro && caro.scrollWidth > caro.clientWidth + 2);   /* a row that scrolls keeps the gesture */
      /* the search sits over the board: while it is open nothing under it is
         swiped (Jose, Sep 28, 2026: its row of quarterbacks swiped the page) */
      if (document.querySelector("#qsearch.open")) ok = false;
      x0 = t.clientX; y0 = t.clientY; t0 = Date.now(); drag = false; dx = 0;
    }, { passive: true });
    document.addEventListener("touchmove", function (e) {
      if (!ok) return;
      var t = e.touches[0], mx = t.clientX - x0, my = t.clientY - y0;
      if (!drag) {
        if (Math.abs(mx) < 12 || Math.abs(mx) < Math.abs(my) * 1.3) {
          if (Math.abs(my) > 12) ok = false;        /* a scroll, not a swipe */
          return;
        }
        drag = true;
        sides = { "-1": neighborState(-1), "1": neighborState(1) };
        [-1, 1].forEach(function (d) {
          var pane = PANES[String(d)];
          clearPane(pane);
          if (sides[String(d)]) renderInto(pane, sides[String(d)]);
        });
        TRACK.classList.remove("gliding");
      }
      if (e.cancelable) e.preventDefault();
      dx = mx;
      var short = (dx < 0 && !sides["1"]) || (dx > 0 && !sides["-1"]);   /* nothing that way: a tug */
      TRACK.style.transform = "translateX(" + (short ? dx / 3 : dx) + "px)";
    }, { passive: false });
    document.addEventListener("touchend", function () {
      if (!drag) return;
      drag = false;
      var dir = dx < 0 ? 1 : -1, st = sides[String(dir)];
      var go = !!st && (Math.abs(dx) > width() / 4 || (Math.abs(dx) > 40 && Date.now() - t0 < 300));
      var settled = false;
      var done = function () {
        if (settled) return;
        settled = true;
        TRACK.removeEventListener("transitionend", done);
        TRACK.classList.remove("gliding");
        if (go) commit(st);
        TRACK.style.transform = "translateX(0)";
        clearPane(PANES["-1"]); clearPane(PANES["1"]);
      };
      TRACK.classList.add("gliding");
      TRACK.addEventListener("transitionend", done);
      TRACK.style.transform = go ? "translateX(" + (-dir * width()) + "px)" : "translateX(0)";
      setTimeout(done, 400);
    }, { passive: true });
  })();

  /* ---- months, for the fights: the year's events, a month at a time ---- */
  var MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
  function monthKeyOf(iso) {
    var d = new Date(iso);
    var et = new Date(d.toLocaleString("en-US", { timeZone: "America/New_York" }));
    return et.getFullYear() + "-" + ("0" + (et.getMonth() + 1)).slice(-2);
  }
  var mmaMonth = monthKeyOf(new Date().toISOString());
  function monthTabs() {
    wbar.innerHTML = "";
    var seen = {}, keys = [];
    FIGHTS.forEach(function (f) { var k = monthKeyOf(f[2]); if (!seen[k]) { seen[k] = 1; keys.push(k); } });
    keys.sort();
    if (keys.length && keys.indexOf(mmaMonth) < 0) {
      /* no event this month: the nearest month that has one */
      mmaMonth = keys.filter(function (k) { return k >= mmaMonth; })[0] || keys[keys.length - 1];
    }
    keys.forEach(function (k) {
      var t = document.createElement("button");
      t.className = "wktab";
      t.type = "button";
      t.setAttribute("role", "tab");
      t.dataset.mo = k;
      t.textContent = MONTHS[Number(k.slice(5)) - 1];
      t.setAttribute("aria-selected", k === mmaMonth ? "true" : "false");
      wbar.appendChild(t);
    });
    var on = wbar.querySelector('[aria-selected="true"]');
    if (on) on.scrollIntoView({block: "nearest", inline: "center"});
  }

  /* ---- the week rail, whichever league is asking ---- */
  function weekTabs(n, current) {
    wbar.innerHTML = "";
    for (var w = 1; w <= n; w++) {
      var t = document.createElement("button");
      t.className = "wktab";
      t.type = "button";
      t.setAttribute("role", "tab");
      t.dataset.wk = w;
      t.textContent = "WEEK " + w;
      t.setAttribute("aria-selected", w === current ? "true" : "false");
      wbar.appendChild(t);
    }
    var on = wbar.querySelector('[aria-selected="true"]');
    if (on) on.scrollIntoView({block: "nearest", inline: "center"});
  }
  wbar.addEventListener("click", function (e) {
    var t = e.target.closest(".wktab");
    if (!t) return;
    if (sport === "form") {
      formWeek = t.dataset.lw;
      wbar.querySelectorAll(".wktab").forEach(function (x) {
        x.setAttribute("aria-selected", x.dataset.lw === formWeek ? "true" : "false");
      });
      render();
      return;
    }
    if (sport === "mma") {
      mmaMonth = t.dataset.mo;
      wbar.querySelectorAll(".wktab").forEach(function (x) {
        x.setAttribute("aria-selected", x.dataset.mo === mmaMonth ? "true" : "false");
      });
      day = "";
      buildDays();
      render();
      return;
    }
    var w = Number(t.dataset.wk);
    if (sport === "nfl") { week = w; } else { cfbWeek = w; }
    wbar.querySelectorAll(".wktab").forEach(function (x) {
      x.setAttribute("aria-selected", Number(x.dataset.wk) === w ? "true" : "false");
    });
    day = "";            /* the week decides which days exist */
    buildDays();
    render();
  });

  function weekOf(list, n) {
    var now = Date.now(), pick = 1;
    for (var w = 1; w <= n; w++) {
      var of = list.filter(function (g) { return g[0] === w; });
      if (!of.length) continue;
      var hi = Math.max.apply(null, of.map(function (g) { return Date.parse(g[2]); }));
      if (now <= hi + 6 * 3600000) return w;
      pick = Math.min(n, w + 1);
    }
    return pick;
  }
  week = weekOf(SCHED, WEEKS);
  cfbWeek = weekOf(CFB, CFB_WEEKS);

  /* ---- the sport pills ---- */
  var sbar = document.getElementById("sportbar");
  SPORTS.forEach(function (sp) {
    var t = document.createElement("button");
    t.className = "sptab";
    t.type = "button";
    t.setAttribute("role", "tab");
    t.dataset.sp = sp.key;
    /* a flat picture with nothing to recolour: its alpha is the mask and the
       colour comes from the stylesheet, the way the boost mark does it */
    /* the day tab carries the month we are actually in, drawn rather than
       fetched, so it reads 09 in September and 10 in October without anybody
       redrawing a file (Jose, Sep 21, 2026) */
    t.innerHTML = sp.key === "all" ? dayIcon()
                : sp.mask ? '<i class="spmask" style="--m:url(\'' + sp.ico + '\')"></i>'
                          : '<img src="' + sp.ico + '" alt="">';
    t.setAttribute("aria-label", sp.label);
    t.setAttribute("aria-selected", sp.key === sport ? "true" : "false");
    sbar.appendChild(t);
  });
  /* ---- the mark that says which sport is open ----------------------------
     One element that slides between the pills rather than a border on each,
     so it can travel with a finger. Press the bar and it follows; the board
     does not change until the finger comes off, and a tap is just a press
     that did not move (Jose, Sep 22, 2026, mocked in notes/mocks/mock_nav.html).
  */
  var spmark = document.createElement("span");
  spmark.className = "spmark";
  sbar.appendChild(spmark);

  /* seatMark, not markOver: markOver(id) already existed and is what marks a
     finished game as settled. This one overwrote it, so every result -- NFL,
     college and every bout -- stopped being drawn the moment the nav shipped
     (Jose, Sep 22, 2026: "why are you breaking it?"). */
  /* the mark wears the picture's own size rather than one square for all
     of them. Every mark used to be 39 in a 39 box, so a single 57 square
     fitted every pill; the form mark is landscape and 65 across, and sat in
     that square with room to spare above and below and none at the sides
     (Jose, Sep 23, 2026: "make the indication grow to the size of the icon").
     Eight pixels of glass all round, and it stays centered in the bar however
     tall the picture is. */
  /* the mark is the tab's own height, eight wider than its picture, and it
     answers with the size it is heading for -- read back off the element
     mid-glide it was still the old width, and the mark settled eight pixels
     off center (Jose, Sep 23, 2026: "it needs to snap to the center... it
     needs to be exact and it needs to be the height") */
  function markSize(t) {
    var mk = t && t.querySelector("img, .spmask, .allmk, .daycal");
    if (!mk) return null;
    var r = mk.getBoundingClientRect(), tr = t.getBoundingClientRect();
    if (!r.width || !r.height) return null;   /* a picture that has not loaded yet */
    var inner = sbar.clientHeight;
    var w = Math.round(r.width + 8), h = Math.round(tr.height);
    spmark.style.width = w + "px";
    spmark.style.height = h + "px";
    spmark.style.top = Math.max(0, Math.round((inner - h) / 2)) + "px";
    return { w: w, h: h };
  }
  function seatMark(t) {
    if (!t) return;
    var size = markSize(t);
    var r = t.getBoundingClientRect(), b = sbar.getBoundingClientRect();
    var w = size ? size.w : (spmark.offsetWidth || 57);
    spmark.style.transform =
      "translateX(" + (r.left - b.left + (r.width - w) / 2) + "px)";
  }
  function markNow() {
    seatMark(sbar.querySelector('.sptab[aria-selected="true"]') ||
             sbar.querySelector(".sptab"));
  }
  markNow();
  requestAnimationFrame(markNow);          /* once the pictures have laid out */
  window.addEventListener("resize", markNow);
  /* whatever changed the sport, the mark follows it: this listener is added
     after the one that does the switching, so it runs on the far side of it
     even when that one returns early */
  sbar.addEventListener("click", function () { requestAnimationFrame(markNow); });

  var spHold = false, spOver = null, spMoved = false;
  function spNearest(x) {
    var best = null, gap = Infinity;
    sbar.querySelectorAll(".sptab").forEach(function (t) {
      var r = t.getBoundingClientRect(), d = Math.abs(x - (r.left + r.width / 2));
      if (d < gap) { gap = d; best = t; }
    });
    return best;
  }
  function spShow(t) {
    sbar.querySelectorAll(".sptab").forEach(function (x) {
      x.setAttribute("aria-selected", x === t ? "true" : "false");
    });
    seatMark(t);
  }
  /* the mark under the finger, wherever the finger is -- not snapped to a
     pill. It may not leave the bar, so it is held between its two ends. */
  function markAt(x) {
    var b = sbar.getBoundingClientRect(), w = spmark.offsetWidth || 57;
    var lo = 5, hi = b.width - w - 5;
    var at = x - b.left - w / 2;
    spmark.style.transform =
      "translateX(" + Math.max(lo, Math.min(hi, at)) + "px)";
  }
  sbar.addEventListener("pointerdown", function (e) {
    if (!e.target.closest(".sptab") && e.target !== sbar) return;
    spHold = true; spMoved = false;
    spOver = spNearest(e.clientX);
    /* held only. The ease is left on, so a tap glides across rather than
       snapping (Jose, Sep 22, 2026: "it's not smooth from one tab to the
       other") */
    spmark.classList.add("spmark--held");
    spShow(spOver);
  });
  window.addEventListener("pointermove", function (e) {
    if (!spHold) return;
    if (!spMoved) { spMoved = true; spmark.classList.add("spmark--scrub"); }
    var t = spNearest(e.clientX);            /* the picture under it lights up */
    if (t !== spOver) {
      spOver = t;
      markSize(t);                           /* and the glass grows to it */
      sbar.querySelectorAll(".sptab").forEach(function (x) {
        x.setAttribute("aria-selected", x === t ? "true" : "false");
      });
    }
    markAt(e.clientX);                       /* it rides the finger */
  });
  window.addEventListener("pointerup", function () {
    if (!spHold) return;
    spHold = false;
    /* the ease comes back first, so the mark snaps to the nearest pill
       rather than jumping to it */
    spmark.classList.remove("spmark--scrub");
    spmark.classList.remove("spmark--held");
    seatMark(spOver);
    /* and it commits, on release. A tap that never moved is left to its own
       click; a drag has to be told, because the click lands where it started. */
    if (spMoved && spOver && spOver.dataset.sp !== sport) { spOver.click(); }
  });
  window.addEventListener("pointercancel", function () {
    if (!spHold) return;
    spHold = false;
    spmark.classList.remove("spmark--held", "spmark--scrub");
    requestAnimationFrame(markNow);
  });

  /* ---- double tap the mark: go and get what the day is missing ----------
     A price is missing when the board holds no moneyline for an event and
     nothing under it either. An event already over is never asked about --
     its price is the one it closed at. If the open day has nothing to ask
     for, the next day that does is taken (Jose, Sep 23, 2026: "it nothing on
     the day it takes the next day"), and it is the same job for football and
     for fights, which is all three sports the board carries.

     The tap is caught on the way down and held for a moment, because a single
     tap on this pill opens the form and a double tap must not: the first tap
     only becomes a sport change once the moment has passed without a second
     (Jose, Sep 23, 2026: "workds on the double tab"). */
  var formTab = sbar.querySelector('.sptab[data-sp="form"]');
  if (formTab) {
    var fill = document.createElement("span");
    fill.className = "spfill";
    fill.innerHTML = "<i></i>";
    formTab.appendChild(fill);
    var fillBar = fill.querySelector("i");

    /* the fill rides whichever icon was double tapped: the Stacked mark for
       the open day, the NFL shield for the week ahead */
    var fillTab = formTab;
    function fillOn(tab) {
      fillTab = tab;
      if (fill.parentNode !== tab) tab.appendChild(fill);
    }
    /* the fill is the picture's own shape, in the picture's own place */
    function fillSeat() {
      /* a day tab has no picture: the fill covers the tab and its words take
         the colour (Jose, Oct 1, 2026: "the green indicator goes to the nfl
         logo and the day") */
      var img = fillTab.querySelector("img, svg") || fillTab;
      var r = img.getBoundingClientRect(), t = fillTab.getBoundingClientRect();
      fill.style.width = r.width + "px";
      fill.style.height = r.height + "px";
      fill.style.left = (r.left - t.left + r.width / 2) + "px";
      fill.style.top = (r.top - t.top + r.height / 2) + "px";
      var m = "none";
      if (img.tagName === "IMG") m = "url('" + img.getAttribute("src") + "')";
      else if (img.tagName.toLowerCase() === "svg") {
        /* the day page's calendar is drawn inline: its own shape, as a picture,
           is the mask, so the fill stays inside the icon */
        var c = img.cloneNode(true);
        c.setAttribute("xmlns", "http://www.w3.org/2000/svg");
        c.setAttribute("width", r.width); c.setAttribute("height", r.height);
        m = "url(\"data:image/svg+xml;utf8," + encodeURIComponent(new XMLSerializer().serializeToString(c)) + "\")";
      }
      fill.style.setProperty("--m", m);
    }
    function fillAt(pc, how) {
      fill.classList.remove("spfill--ok", "spfill--none", "spfill--bad");
      if (how) fill.classList.add("spfill--" + how);
      fillBar.style.height = pc + "%";
    }
    /* the colour stays: it is the day's standing until the next asking, not
       a flash (Jose, Sep 23, 2026: "does it stay?") */
    function fillDone(how) {
      fillAt(100, how);
    }

    /* what the board already holds for one event */
    function heldFor(id) {
      var ml = false;
      [[SCHED, 9], [CFB, 10], [FIGHTS, 8]].forEach(function (pair) {
        (pair[0] || []).forEach(function (row) {
          if (String(row[1]) !== String(id)) return;
          for (var k = 0; k < 4; k++) if (row[pair[1] + k]) ml = true;
        });
      });
      return { ml: ml, props: !!(PROPS[id] || FPROPS[id]) };
    }
    /* every card on the open day that is still short of a price */
    /* every price a card carries. A game is whole only when each one is on
       the card, or DraftKings itself has been asked and does not offer it
       (Jose, Sep 23, 2026: "for each card what do we get?" and "some can be
       not offered, how will that be determined?").
         NFL and college, both sides: moneyline, 1+ and 2+ passing TD,
           1+ rushing TD, head-to-head -- fourteen.
         UFC, both fighters: moneyline, KO/TKO, submission, decision on the
           card, and every market on the fight sheet. */
    var BOUTKEYS = ["ko", "sub", "dec", "koonly", "subonly", "deconly", "finishonly", "rd1only",
      "ud", "sdmd", "kosub", "finish", "kodec", "subdec", "cards", "rd1", "kord1", "subrd1",
      "anykord1", "anysubrd1", "rd2", "kord2", "subrd2", "anykord2", "anysubrd2", "rd3", "kord3",
      "subrd3", "anykord3", "anysubrd3", "rd12", "rdlastdec", "anyko", "anysub", "anydec", "dist",
      "nodist", "anyud", "anysdmd", "first60", "last10"];
    var ASKED = {};                 /* events DraftKings has answered for this visit */
    function mlRow(id) {
      var got = null;
      [[SCHED, 9], [CFB, 10], [FIGHTS, 8]].forEach(function (pair) {
        (pair[0] || []).forEach(function (row) {
          if (String(row[1]) === String(id)) got = [row[pair[1]], row[pair[1] + 2]];
        });
      });
      return got || [null, null];
    }
    function isWhole(c, id) {
      var has = function (x) { return !!(x && (typeof x === "string" ? x : x[0])); };
      var ml = mlRow(id);
      if (!ml[0] || !ml[1]) return false;
      if (c.dataset.bout) {
        var f = FPROPS[id];
        if (!f) return false;
        for (var k = 0; k < BOUTKEYS.length; k++) {
          var v = f[BOUTKEYS[k]];
          if (!v) return false;
          for (var m = 0; m < v.length; m++) if (!has(v[m])) return false;
        }
        return true;
      }
      var p = PROPS[id];
      if (!p) return false;
      var at = function (rows, side, n) { return has(rows && rows[side] && rows[side][n]); };
      return at(p.ptd, 0, 0) && at(p.ptd, 1, 0) && at(p.ptd, 0, 1) && at(p.ptd, 1, 1) &&
             at(p.atd, 0, 0) && at(p.atd, 1, 0) &&
             has(p.h2h && p.h2h[0]) && has(p.h2h && p.h2h[1]);
    }
    function shortOfPrice() {
      var out = [], seen = {};
      document.querySelectorAll(".gcard[data-espn], .gcard[data-bout]").forEach(function (c) {
        var id = c.dataset.espn || c.dataset.bout;
        if (!id || seen[id]) return;
        if (c.dataset.settled === "1" || c.dataset.settledBout === "1" ||
            c.classList.contains("done")) return;
        if (ASKED[id] || isWhole(c, id)) return;
        seen[id] = 1;
        out.push(c);
      });
      return out;
    }
    /* every card on the open day whose game is not over: a double tap reads
       all of them again, so a price that has moved since the sweep is
       brought up to date, not only one that was never there
       (Jose, Sep 25, 2026: "if there are changes re seed those changes") */
    function stillOpen() {
      var out = [], seen = {};
      document.querySelectorAll(".gcard[data-espn], .gcard[data-bout]").forEach(function (c) {
        var id = c.dataset.espn || c.dataset.bout;
        if (!id || seen[id]) return;
        if (c.dataset.settled === "1" || c.dataset.settledBout === "1" ||
            c.classList.contains("done")) return;
        seen[id] = 1;
        out.push(c);
      });
      return out;
    }
    /* the next slot on the rail, whatever the rail is counting in */
    function stepDay() {
      var tabs = [].slice.call(dbar.querySelectorAll(".dtab"));
      for (var i = 0; i < tabs.length - 1; i++) {
        if (tabs[i].dataset.day !== day) continue;
        day = tabs[i + 1].dataset.day;
        markDay();
        render();
        return true;
      }
      return false;
    }

    /* what the files did not hold is asked of DraftKings itself: /ask starts
       a run on GitHub for just these events, and the page watches for its
       answer. The bar climbs green while it waits; it only finishes green
       when every one came back priced, grey when the run finished short,
       red when the asking or the run failed (Jose, Sep 23, 2026: "while
       fetching it doesn't turn all the way green until it gets the status
       back") */
    function askDK(cards) {
      var ids = [], seen = {};
      cards.forEach(function (c) {
        var id = c.dataset.espn || c.dataset.bout;
        if (id && !seen[id]) { seen[id] = 1; ids.push(id); }
      });
      var t0 = Date.now(), LIMIT = 240000;   /* the store can lag a minute behind a finished run: red only if it truly failed */
      var climb = function () {
        var p = Math.min(1, (Date.now() - t0) / 60000);
        fillAt(Math.round(40 + 52 * (1 - Math.pow(1 - p, 2))), "ok");
      };
      fillAt(40, "ok");
      fetch("ask", { method: "POST", headers: { "content-type": "application/json" },
                     body: JSON.stringify({ games: ids.slice(0, 40) }) })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (run) {
          if (!run || !run.key) { fillDone("bad"); return; }
          var look = function () {
            climb();
            fetch("ask?key=" + encodeURIComponent(run.key), { cache: "no-store" })
              .then(function (r) { return r.ok ? r.json() : null; })
              .then(function (st) {
                if (st && st.prices) Object.keys(st.prices).forEach(function (id) { window._seatAsked(id, st.prices[id]); });
                if (st && st.state === "done" && st.prices) Object.keys(st.prices).forEach(function (id) { ASKED[id] = 1; });
                /* green: read, and every price on every card it asked about is
                   there; grey: read, with something still missing; red: the
                   read failed (Jose, Sep 28, 2026: "green is both -- all prices
                   present and updated -- if not, then gray") */
                if (st && st.state === "done") {
                  var whole = cards.every(function (c) { return isWhole(c, c.dataset.espn || c.dataset.bout); });
                  fillDone(whole ? "ok" : "none"); return;
                }
                if (st && st.state === "failed") { fillDone("bad"); return; }
                if (Date.now() - t0 > LIMIT) { fillDone("bad"); return; }
                setTimeout(look, 3000);
              })
              .catch(function () {
                if (Date.now() - t0 > LIMIT) { fillDone("bad"); return; }
                setTimeout(look, 3000);
              });
          };
          setTimeout(look, 2500);
        })
        .catch(function () { fillDone("bad"); });
    }

    window._askDay = function (tab) { askDay(tab); };
    /* the NFL shield, double tapped: every game of the week we are on that is
       still short of a price, asked of DraftKings there and then, whatever day
       is open; the fill rides the shield (Jose, Oct 1, 2026) */
    window._askWeek = function (tab) {
      fillOn(tab);
      fillSeat();
      fill.classList.add("spfill--on");
      fillAt(0);
      requestAnimationFrame(function () { fillAt(14); });
      if (navigator.onLine === false) { fillDone("none"); return; }
      var now = Date.now(), rows = (typeof SCHED === "object" ? SCHED : []).filter(function (r) {
        return Date.parse(r[2]) > now;
      });
      if (!rows.length) { fillDone("none"); return; }
      var wk = Math.min.apply(null, rows.map(function (r) { return r[0]; }));
      var short = rows.filter(function (r) {
        return r[0] === wk && !isWhole({ dataset: { espn: String(r[1]) } }, String(r[1]));
      }).map(function (r) { return { dataset: { espn: String(r[1]) } }; });
      if (!short.length) { fillDone("ok"); return; }
      fillAt(28);
      askDK(short);
    };
    function askDay(tab) {
      fillOn(tab || dbar.querySelector('.dtab[aria-selected="true"]') || formTab);
      /* the first of the two taps lit this pill on the way down; the board
         never changed, so the light goes back to the sport that is open */
      sbar.querySelectorAll(".sptab").forEach(function (x) {
        x.setAttribute("aria-selected", x.dataset.sp === sport ? "true" : "false");
      });
      /* quick out to the goggles on the press, slow and smooth on the way
         back (Jose, Sep 23, 2026: "responsive to get there... slow on the
         way back... smoother and slower") */
      spmark.classList.add("spmark--back");
      markNow();
      spmark.addEventListener("transitionend", function off() {
        spmark.classList.remove("spmark--back");
        spmark.removeEventListener("transitionend", off);
      });
      fillSeat();
      fill.classList.add("spfill--on");
      fillAt(0);
      requestAnimationFrame(function () { fillAt(14); });
      /* nothing to ask with: grey, and no red, because nothing failed
         (Jose, Sep 23, 2026: "if offiline grey") */
      if (navigator.onLine === false) { fillDone("none"); return; }
      var cards = stillOpen(), hops = 0;
      while (!cards.length && hops < 6 && stepDay()) { cards = stillOpen(); hops++; }
      /* nothing short of a price: the day is complete, and that is green */
      if (!cards.length) {
        fillDone(document.querySelector(".gcard[data-espn], .gcard[data-bout]") ? "ok" : "none");
        return;
      }
      var done = 0, got = 0, bad = 0;
      fillAt(28);
      Promise.all(cards.map(function (c) {
        var id = c.dataset.espn || c.dataset.bout;
        var was = heldFor(id);
        delete CARDDONE[id];             /* ask again: that is what this is for */
        return pullCard(c).then(function (how) {
          if (how === "bad") { bad++; return; }
          var now = heldFor(id);
          if ((now.ml && !was.ml) || (now.props && !was.props)) got++;
        }).then(function () {
          done++;
          fillAt(28 + Math.round(done / cards.length * 68));
        });
      })).then(function () {
        /* green is the day complete -- 128 of 128 -- grey is some still
           missing after the asking, red is a fetch that failed
           (Jose, Sep 23, 2026: "once we get 128 out of 128... if not grey,
           if failing red") */
        askDK(stillOpen());
      });
    }

    var tapWait = null, tapPass = false;
    /* ---- long press the mark: ALL / HOT / NOT / OUT rise above the nav ----
       Held, the four come up in their own glass bar just over the floating
       nav; the finger slides up onto one and lets go to open it, or lets go
       anywhere else and the bar sinks back (Jose, Sep 23, 2026). */
    var pop = document.createElement("div");
    pop.className = "fview fpop";
    /* HOT wears the flame from the reactions set, not the word
       (Jose, Sep 25, 2026) */
    pop.innerHTML = [["all", "All"], ["hot", "Hot"], ["not", "Not"], ["out", "Out"]].map(function (v) {
      /* NOT the worried face he sent; OUT the board's own band-aid */
      var face = v[0] === "hot" ? '<img class="fpopico" src="data:image/png;base64,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" alt="Hot">'
               : v[0] === "not" ? '<img class="fpopico" src="data:image/png;base64,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" alt="Not">'
               : v[0] === "out" ? '<svg class="fpopico fpopico--out" viewBox="0 0 26 26" aria-hidden="true"><use href="#hurt"/></svg>'
               : v[1];
      return '<button type="button" data-pv="' + v[0] + '"' + (v[0] === "all" ? " hidden" : "") + ' aria-label="' + v[1] + '">' + face + '</button>';
    }).join("") + '<span class="spmark"></span>';
    document.body.appendChild(pop);
    var popMark = pop.querySelector(".spmark"), popOn = false, longT = null, longFired = false, popPick = null;
    function popSeat(b0) {
      if (!b0) return;
      popMark.style.transform = "translateX(" + (b0.offsetLeft + (b0.offsetWidth - (popMark.offsetWidth || 57)) / 2) + "px)";
    }
    function popShow() {
      var cur = "hot";
      try { cur = localStorage.getItem("arena.fview") || "hot"; } catch (e0) {}
      if (cur === "all") cur = "hot";      /* ALL is parked */
      popPick = null;
      pop.querySelectorAll("button").forEach(function (b0) {
        b0.setAttribute("aria-selected", b0.dataset.pv === cur ? "true" : "false");
        if (b0.dataset.pv === cur) requestAnimationFrame(function () { popSeat(b0); });
      });
      pop.classList.add("fpop--on"); popOn = true;
      /* the nav's own drag stands down while the four are up */
      spHold = false; spmark.classList.remove("spmark--held", "spmark--scrub"); markNow();
    }
    function popHide() { pop.classList.remove("fpop--on"); popOn = false; }
    formTab.addEventListener("pointerdown", function () {
      longFired = false;
      clearTimeout(longT);
      /* the four and the weeks are one strip now, in the picker below; this
         only marks the hold so its tap is not read as a tap */
      longT = setTimeout(function () { longFired = true; }, 380);
    });
    window.addEventListener("pointermove", function (e) {
      if (!popOn) {
        /* a finger that has moved off before the hold is a drag of the nav */
        if (longT && !longFired) {
          var r0 = formTab.getBoundingClientRect();
          if (e.clientY < r0.top - 12 || Math.abs(e.clientX - (r0.left + r0.width / 2)) > r0.width) { clearTimeout(longT); longT = null; }
        }
        return;
      }
      var pr = pop.getBoundingClientRect(), best = null, gap = Infinity;
      if (e.clientY <= pr.bottom + 30) {
        pop.querySelectorAll("button").forEach(function (b0) {
          var r1 = b0.getBoundingClientRect(), d = Math.abs(e.clientX - (r1.left + r1.width / 2));
          if (d < gap) { gap = d; best = b0; }
        });
      }
      popPick = best;
      pop.querySelectorAll("button").forEach(function (b0) { b0.setAttribute("aria-selected", b0 === best ? "true" : "false"); });
      if (best) popSeat(best);
    }, { passive: true });
    window.addEventListener("pointerup", function () {
      clearTimeout(longT); longT = null;
      if (!popOn) return;
      var v = popPick && popPick.dataset.pv;
      popHide();
      if (!v) return;
      try { localStorage.setItem("arena.fview", v); } catch (e1) {}
      /* on the form's season already: press the matching square; anywhere
         else, open the form first and it reads the choice on the way in */
      var here = document.querySelector('.fview:not(.fpop) button[data-fview="' + v + '"]');
      if (here && sport === "form") { here.click(); return; }
      longFired = false; tapPass = true; formTab.click();
      setTimeout(function () {
        var season = [].slice.call(document.querySelectorAll(".wktab")).find(function (x) { return /SEASON/i.test(x.textContent); });
        if (season && !season.classList.contains("on") && season.getAttribute("aria-selected") !== "true") season.click();
        setTimeout(function () {
          var b1 = document.querySelector('.fview:not(.fpop) button[data-fview="' + v + '"]');
          if (b1 && b1.getAttribute("aria-selected") !== "true") b1.click();
        }, 120);
      }, 120);
    });
    window._openForm = function () { longFired = false; tapPass = true; formTab.click(); };
    formTab.addEventListener("click", function (e) {
      if (longFired) { longFired = false; e.stopPropagation(); if (e.cancelable) e.preventDefault(); return; }
      if (tapPass) { tapPass = false; return; }   /* the held tap, let through */
      e.stopPropagation();
      if (e.cancelable) e.preventDefault();
      /* the second tap reads the wallet now: the odds' double tap moved to
         the day tab and the NFL shield, and the wallet gave up its own
         (Jose, Oct 1, 2026: "the logo of the stack now does the wallet") */
      if (tapWait) {
        clearTimeout(tapWait); tapWait = null;
        if (typeof window._walletPull === "function") window._walletPull();
        return;
      }
      tapWait = setTimeout(function () {
        tapWait = null;
        /* a tap opens HOT, the season's field, not the last view it was on
           (Jose, Sep 25, 2026: "on click it loads the hot page") */
        try { localStorage.setItem("arena.fview", "hot"); } catch (e1) {}
        tapPass = true;
        formTab.click();                          /* a single tap, a moment late */
        setTimeout(function () {
          var season = [].slice.call(document.querySelectorAll(".wktab")).find(function (x) { return /SEASON/i.test(x.textContent); });
          if (season && !season.classList.contains("on") && season.getAttribute("aria-selected") !== "true") season.click();
          setTimeout(function () {
            var b1 = document.querySelector('.fview:not(.fpop) button[data-fview="hot"]');
            if (b1 && b1.getAttribute("aria-selected") !== "true") b1.click();
          }, 120);
        }, 120);
      }, 420);                                    /* 260 read two mouse clicks as two singles (Jose, Sep 23, 2026) */
    }, true);
  }

  /* ---- long press a sport: its weeks, months or days rise above the nav ----
     The same glass bar as ALL / HOT / NOT / OUT, the same width, three at a
     time. The finger slides along them; held at the left edge they run back
     to the first, at the right edge on to the last; let go on one and that
     is where the board goes. UFC is months, college and the NFL are weeks,
     the calendar is days (Jose, Sep 23, 2026). */
  (function () {
    var rail = document.createElement("div");
    rail.className = "fview fpop prail";
    rail.innerHTML = '<div class="prail__win"><div class="prail__strip"></div></div><span class="spmark"></span>';
    document.body.appendChild(rail);
    var strip = rail.querySelector(".prail__strip"), rmark = rail.querySelector(".spmark");
    var IW = 88, items = [], sel = 0, win = 0, on = false, fired = false, lt = null, tab = null, edgeT = null, lastX = 0, lastY = 0;
    function paint() {
      strip.style.transform = "translateX(" + (-win * IW) + "px)";
      rmark.style.transform = "translateX(" + (5 + (sel - win) * IW + (IW - 57) / 2) + "px)";
      strip.querySelectorAll("button").forEach(function (b0, k) { b0.setAttribute("aria-selected", k === sel ? "true" : "false"); });
    }
    function open(t) {
      tab = t;
      /* the rail belongs to the sport, so the sport is opened first */
      var switched = sport !== t.dataset.sp;
      if (switched) {
        if (t.dataset.sp === "form" && window._openForm) window._openForm();
        else { t._pass = true; t.click(); }
      }
      /* a sport just opened redraws its rail; read it once that has happened --
         the form draws its weeks later than the others, so it is waited for */
      var tries = 0;
      (function ready() {
        var have = t.dataset.sp === "form" ? document.querySelector(".weekbar .wktab") : dbar.querySelector(".dtab");
        if ((!have || switched && tries < 2) && tries++ < 20) { setTimeout(ready, 60); return; }
        fill();
      })();
      function fill() {
        if (t.dataset.sp === "form") {
          /* the form: ALL (the season), HOT, NOT, OUT, then every week, one
             strip (Jose, Sep 23, 2026) */
          var wk = [].slice.call(document.querySelectorAll(".weekbar .wktab"));
          var seasonTab = wk.find(function (x) { return /SEASON/i.test(x.textContent); });
          var onSeason = !seasonTab || seasonTab.getAttribute("aria-selected") === "true" || seasonTab.classList.contains("on");
          var fv0 = "hot"; try { fv0 = localStorage.getItem("arena.fview") || "hot"; } catch (e2) {}
          if (fv0 === "all") fv0 = "hot";      /* ALL is parked; the field is the season's page */
          /* HOT, NOT and OUT live on the HOT page now; the hold is the
             weeks (Jose, Sep 25, 2026: "long press does weeks") */
          items = [["hot", "FIELD"]].map(function (v) {
            return { key: v[0], label: v[1], view: v[0], season: seasonTab, cur: onSeason && fv0 === v[0] };
          }).concat(wk.filter(function (x) { return x !== seasonTab; }).map(function (x) {
            return { key: x.textContent, label: x.textContent.replace(/\s+/g, " ").trim(), el: x,
                     cur: x.getAttribute("aria-selected") === "true" || x.classList.contains("on") };
          }));
        } else {
          var tabs = [].slice.call(dbar.querySelectorAll(".dtab"));
          items = tabs.map(function (d) { return { key: d.dataset.day, label: d.textContent.replace(/\s+/g, " ").trim(), el: d,
                                                   cur: d.getAttribute("aria-selected") === "true" }; });
        }
        if (!items.length) return;
        strip.innerHTML = items.map(function (it) { return '<button type="button">' + it.label + '</button>'; }).join("");
        sel = Math.max(0, items.findIndex(function (it) { return it.cur; }));
        win = Math.max(0, Math.min(items.length - 3, sel - 1));
        paint();
        rail.classList.add("fpop--on"); on = true;
        spHold = false; spmark.classList.remove("spmark--held", "spmark--scrub"); markNow();
      }
    }
    function over(x, y) {
      var r = rail.getBoundingClientRect();
      if (y > r.bottom + 30) return null;
      return x - r.left;
    }
    /* a thumb held on an edge is never still -- it trembles, and every tremble
       is a move. The run keeps going while the finger stays in the edge
       zone, and only a move out of it stops it; restarting it on each move
       meant it never ticked at all on a phone (Jose, Sep 23, 2026) */
    var edgeDir = 0;
    function edgeRun() {
      var lx = over(lastX, lastY);
      var dir = lx === null ? 0 : lx < 40 ? -1 : lx > rail.offsetWidth - 40 ? 1 : 0;
      if (dir === edgeDir) return;
      clearInterval(edgeT); edgeT = null; edgeDir = dir;
      if (!dir) return;
      var step = function () {
        win = Math.max(0, Math.min(items.length - 3, win + dir));
        sel = dir < 0 ? win : Math.min(items.length - 1, win + 2);
        paint();
      };
      step();
      edgeT = setInterval(step, 250);
    }
    sbar.querySelectorAll(".sptab").forEach(function (t) {
      t.addEventListener("pointerdown", function () {
        fired = false; clearTimeout(lt);
        lt = setTimeout(function () { fired = true; open(t); }, 380);
      });
      if (t.dataset.sp !== "form") t.addEventListener("click", function (e) {
        if (t._pass) { t._pass = false; return; }
        if (fired) { fired = false; e.stopPropagation(); if (e.cancelable) e.preventDefault(); }
      }, true);
    });
    window.addEventListener("pointermove", function (e) {
      lastX = e.clientX; lastY = e.clientY;
      if (!on) {
        if (lt && !fired && tab === null) {}
        return;
      }
      var lx = over(e.clientX, e.clientY);
      if (lx === null || !items.length) { clearInterval(edgeT); edgeT = null; edgeDir = 0; return; }
      edgeRun();
      if (edgeDir) return;                     /* the run owns the choice while it goes */
      var k = Math.max(0, Math.min(2, Math.floor((lx - 5) / IW)));
      sel = Math.min(items.length - 1, win + k);
      paint();
    }, { passive: true });
    window.addEventListener("pointerup", function (e) {
      clearTimeout(lt); lt = null;
      clearInterval(edgeT); edgeT = null; edgeDir = 0;
      if (!on) { tab = null; return; }
      on = false; rail.classList.remove("fpop--on");
      var picked = over(e.clientX, e.clientY) !== null && items[sel];
      tab = null;
      if (!picked) return;
      if (picked.view) {
        /* a view is the season with that filter on it */
        try { localStorage.setItem("arena.fview", picked.view); } catch (e3) {}
        var toView = function () {
          var b1 = document.querySelector('.fview:not(.fpop) button[data-fview="' + picked.view + '"]');
          if (b1 && b1.getAttribute("aria-selected") !== "true") b1.click();
        };
        if (picked.season && picked.season.getAttribute("aria-selected") !== "true" && !picked.season.classList.contains("on")) {
          picked.season.click(); setTimeout(toView, 120);
        } else if (formWeek !== "season") {
          /* the field has no tab of its own now: from CLIPS or a week the
             season is drawn first, then the view put on it */
          formWeek = "season"; formTabs(); render(); setTimeout(toView, 120);
        } else toView();
        return;
      }
      if (picked.el && picked.el.getAttribute("aria-selected") !== "true") picked.el.click();
    });
  })();

  /* a tab change crossfades like an app's, not a jump (Jose, Sep 29, 2026):
     the browser keeps a picture of the old board and fades it into the new.
     The stack's own tab keeps its double tap untouched. */
  sbar.addEventListener("click", function (e) {
    var t = e.target.closest(".sptab");
    if (!t || window._vtNow || t.dataset.sp === "form" || !document.startViewTransition ||
        (window.matchMedia && matchMedia("(prefers-reduced-motion: reduce)").matches)) return;
    e.stopImmediatePropagation(); e.preventDefault();
    var vt0 = document.startViewTransition(function () { window._vtNow = true; try { t.click(); } finally { window._vtNow = false; } });
    /* a transition cut short by the next tap is not an error */
    vt0.ready.catch(function () {}); vt0.finished.catch(function () {});
  }, true);
  sbar.addEventListener("click", function (e) {
    var t = e.target.closest(".sptab");
    if (!t) return;
    sport = t.dataset.sp;
    sbar.querySelectorAll(".sptab").forEach(function (x) {
      x.setAttribute("aria-selected", x.dataset.sp === sport ? "true" : "false");
    });
    var weekly = sport === "nfl" || sport === "college-football";
    /* the top rail carries the week itself now, so a league's own week picker
       would be the same row twice. The fights keep theirs -- a card is not a
       week -- and so does the form page (Jose, Sep 18, 2026). */
    wbar.hidden = sport !== "form";
    dbar.hidden = sport === "form";
    /* the Stacked button lands on the field every time; CLIPS and the weeks
       are reached from the bar under it (Jose, Sep 29, 2026) */
    if (sport === "form") { formWeek = "season"; formTabs(); render(); return; }
    /* the rail counts in days on the calendar, weeks on the football and
       months on the fights, so the key is translated when the sport changes
       rather than carried over (Jose, Sep 18, 2026) */
    var want = railKind(), was = day;
    var anchor = /^W\d+$/.test(was)
      ? (spans().filter(function (x) { return "W" + x.w === was; })[0] || {}).at
      : (/^\d{4}-\d{2}$/.test(was)
          ? Date.parse(was + "-15T18:00:00Z")
          : (DAYS.filter(function (d2) { return d2[0] === was; })[0] || [])[1]);
    anchor = anchor ? new Date(anchor).toISOString() : new Date().toISOString();
    /* a league tab opens on the week being played, not on the week holding
       whatever day he was last looking at: reading Sunday's cards and then
       tapping NFL was landing him back in week one (Jose, Sep 21, 2026) */
    if (want === "week") {
      day = "W" + (sport === "nfl" ? weekOf(SCHED, WEEKS) : weekOf(CFB, CFB_WEEKS));
    }
    /* the fights open on the month of the next card -- or the one on now --
       never on the month of the week he was reading elsewhere: week 8 of the
       NFL was landing him in November's cards (Jose, Sep 28, 2026) */
    else if (want === "month") {
      var soon = Date.now() - 8 * 3600000, nextCard = null;
      (typeof FIGHTS === "object" ? FIGHTS : []).forEach(function (f) {
        var t = Date.parse(f[2]);
        if (t >= soon && (nextCard === null || t < nextCard)) nextCard = t;
      });
      day = monthKeyOf(new Date(nextCard || Date.now()).toISOString());
    }
    /* the calendar opens on today, not on the first day of the week he was
       just looking at: coming off Week 2 it landed on Thursday 9/17, the
       week's first kickoff, three days behind (Jose, Sep 20, 2026: "it needs
       to take me to today, it's been taking me to 9/17") */
    else day = (openingDay(DAYS) || [dayKeyOf(anchor)])[0];
    if (sport === "mma") {
      mmaMonth = day;
      monthTabs();
    }
    if (weekly) {
      /* open on the week holding the day already chosen, if it holds one */
      if (sport === "nfl") week = weekOf(SCHED, WEEKS);
      else cfbWeek = weekOf(CFB, CFB_WEEKS);
      weekTabs(sport === "nfl" ? WEEKS : CFB_WEEKS,
               sport === "nfl" ? week : cfbWeek);
    }
    buildDays();
    render();
  });

  (function ticking() {
    var face = document.getElementById("clock");
    if (!face) return;          /* the clock row came off the header */
    function show() {
      face.textContent = new Date().toLocaleString("en-US", {
        timeZone: "America/New_York", weekday: "short", month: "numeric",
        day: "numeric", hour: "numeric", minute: "2-digit", second: "2-digit"
      }).replace(",", "") + " ET";
    }
    show();
    setInterval(show, 1000);
  })();
  /* Lift each percentage out of its chip and stand it over the bar. Read at
     load, so a price rewritten by refresh.py brings its own number with it. */
  document.querySelectorAll(".ptdx--v2:not(.ptdx--balls) .ptdside").forEach(function (pane) {
    pane.querySelectorAll(".ptdbtn").forEach(function (chip) {
      var pct = chip.querySelector(".pct");
      var line = chip.querySelector(".ptdline");
      if (!pct || !line) return;
      var n = parseInt(line.textContent, 10);
      var out = document.createElement("span");
      out.className = "ptdpct ptdpct--n" + n;
      out.textContent = pct.textContent.trim();
      pane.appendChild(out);
    });
  });

  /* today when today has games; otherwise the next day that does, and only
     when the whole list is behind us, its last day. Opening on last Saturday
     on a Wednesday was the old rule (Jose, Sep 16, 2026). */
