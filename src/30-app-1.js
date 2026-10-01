  function fsAny(row) {
    var k = row[0], lab = row[1], marks = row[2] || [], wide = row[3] === 2;
    /* five rounds across, the mark and the words underneath -- the shape the
       card's own method row uses (Jose, Sep 18, 2026) */
    if (row[3] === 5) {
      var mk5 = marks.map(function (m) {
        return '<svg aria-hidden="true"><use href="#' + m + '"/></svg>';
      }).join("");
      /* every button says what it is -- KO RD1, not RD1 -- so a price lifted
         out of the row still reads on its own (Jose, Sep 18, 2026) */
      /* the price on top and its mark and name underneath, the way the card's
         own method row reads. row[4] is the cells, each its own label and its
         own slot where we hold one (Jose, Sep 18, 2026) */
      var list = row[4] || [];
      var cells = list.map(function (c) {
        var key = c[1], pr = key ? ((FPROPS[FS_BOUT] || {})[key] || [])[0] : null;
        return '<span class="fs5cell"' + (key ? ' data-mkt="' + key + '"' : "") + '>' +
               (pr && pr[0] ? priceSlot(pr[0], pr[1]) : GHOST) +
               '<i><span class="mktmk">' + mk5 + '</span>' + c[0] + '</i></span>';
      }).join("");
      return '<div class="fs5"><div class="fs5row" style="grid-template-columns:repeat(' +
             list.length + ',1fr)">' + cells + '</div></div>';
    }
    var mk = marks.map(function (m) {
      return '<svg aria-hidden="true"><use href="#' + m + '"/></svg>';
    }).join("");
    var lb = '<span class="mktlab"><span class="mktmk">' + mk + '</span>' + lab + '</span>';
    if (wide) {
      return '<div class="mktrow"' + (k ? ' data-mkt="' + k + '"' : "") + '>' +
        (k ? fs(k, 0) : GHOST) + lb + (k ? fs(k, 1) : GHOST) + '</div>';
    }
    var pr = k ? ((FPROPS[FS_BOUT] || {})[k] || [])[0] : null;
    return '<div class="mktrow mktrow--one"' + (k ? ' data-mkt="' + k + '"' : "") + '>' + lb +
      (pr && pr[0] ? priceSlot(pr[0], pr[1]) : GHOST) + '</div>';
  }
  function fsName(lab, f) {
    /* a crossed pairing has to say which man each way belongs to. His face
       does it in the width a surname cannot -- SHAHBAZYAN KO OR FERREIRA SUB
       is two long names on one line (Jose, Sep 18, 2026). */
    function face(id, scoreId, name) {
      return mug(id, scoreId).replace('class="ffab"', 'class="ffab mkface" title="' + name + '"')
                             .replace('class="ffab ffab--none"', 'class="ffab ffab--none mkface"');
    }
    return String(lab || "").replace(/\{A\}/g, face(f[4], f[12], f[3]))
                            .replace(/\{B\}/g, face(f[6], f[13], f[5]));
  }
  function fsPane(rows, f) {
    /* BY KO, BY SUB and BY DEC are the card's own face rows -- the same
       DraftKings selections, 24 of 24 -- so the sheet leaves them to the card
       (Jose, Sep 30, 2026: "remove those from inside the modal since they are
       duplicate") */
    rows = rows.filter(function (r) { return !(r[3] === 2 && (r[0] === "ko" || r[0] === "sub" || r[0] === "dec")); });
    /* the across-blocks sit above the two names, because nobody's name is on
       them -- then the two-sided rows, then the rest, so every chip reads the
       same way down the page (Jose, Sep 18, 2026) */
    var blocks = rows.filter(function (r) { return r[3] === 5; });
    var rest = rows.filter(function (r) { return r[3] !== 5; }).sort(function (a, b) {
      return (b[3] === 2 ? 1 : 0) - (a[3] === 2 ? 1 : 0);
    });
    function draw(r) {
      var copy = r.slice();
      copy[1] = fsName(copy[1], f);
      return fsAny(copy);
    }
    return '<div class="mkt">' + blocks.map(draw).join("") +
      '<div class="mktrow mktrow--head"><span>' + lastName(f[3]) +
      '</span><span></span><span>' + lastName(f[5]) + '</span></div>' +
      rest.map(draw).join("") + '</div>';
  }
  function fightSheet(f) {
    /* the rows below read FS_BOUT, and every card overwrote it as the bill was
       built -- so a sheet could show another fight's prices under its own two
       names: Tsarukyan's card, titled Pantoja v Van, carrying Pitbull's KO
       price (Jose, Sep 22, 2026). It is set here, for this sheet, and again
       when one is opened. */
    FS_BOUT = f[1];
    /* one strip, no second row of chips: the five ways a fight ends and the
       two stat markets, each its own tab (Jose, Sep 18, 2026). The strip
       scrolls sideways rather than wrapping. */
    var R = fsRows((FPROPS[f[1]] || {}).rounds || 3);
    var panes = [
      ["KO", R["KO"]], ["SUB", R["SUB"]], ["DEC", R["DEC"]],
      ["FINISH", R["FINISH"]], ["DBL CHANCE", R["DBL CHANCE"]]
    ].filter(function (t) { return t[1]; });    /* boxing has no SUB tab */
    return '<div class="mtabs">' + panes.map(function (t, i) {
      return '<button class="mtab' + (i ? "" : " on") + '" type="button" data-tab="' +
             t[0] + '">' + t[0] + '</button>';
    }).join("") + '</div>' + panes.map(function (t, i) {
      return '<div class="tpane' + (i ? " off" : "") + '" data-tab="' + t[0] + '">' +
             fsPane(t[1], f) + '</div>';
    }).join("") + '<p class="mktnote" hidden></p>';
  }


  /* when the card is re-ordered, so are the sheet's two columns */
  var FS_FLIP = false;
  function fs(k, i) {
    var pr = FPROPS[FS_BOUT] || {}, slot = (pr[k] || [])[FS_FLIP ? 1 - i : i];
    return slot && slot[0] ? priceSlot(slot[0], slot[1]) : GHOST;
  }
  var FS_BOUT = "";
  /* a four-figure price, written short so the row keeps its shape: -1160 is
     "-1.2k". The full price stays on the button (data-odds) for the slip. */
  function shortOdds(o) {
    var n = parseInt(String(o).replace(/\u2212/g, "-"), 10);
    if (isNaN(n) || Math.abs(n) < 1000) return String(o).replace("-", "\u2212");
    /* whole thousands only: -2100 is "-2k", -1160 is "-1k" (Jose, Sep 16, 2026) */
    return (n < 0 ? "\u2212" : "+") + Math.round(Math.abs(n) / 1000) + "k";
  }
  /* how many characters the number is written in, which decides whether it is
     written smaller so the box need not grow */
  function longCls(shown) {
    var n = String(shown).length;
    return n >= 6 ? " price--vlong" : (n >= 5 ? " price--long" : "");
  }
  function priceSlot(odds, oid, short) {
    if (!odds) return GHOST;
    var shown = short ? shortOdds(odds) : odds.replace("-", "\u2212");
    var full = ' data-odds="' + odds.replace("-", "\u2212") + '"';
    if (!oid) {
      /* a closing line off our own record: what it paid, not what is on offer */
      return '<button class="price' + longCls(shown) + '" type="button" disabled' + full + '>' + shown + "</button>";
    }
    return '<button class="price' + longCls(shown) + '" type="button" data-oid="' + oid + '"' + full + '>' + shown + "</button>";
  }
  function last(name) {
    var bits = String(name || "").split(" ");
    return bits.length > 1 ? bits.slice(1).join(" ") : bits[0];
  }

  var BALLSVG = '<svg viewBox="0 0 50 50" aria-hidden="true"><use href="#fb"/></svg>';
  var RUSHSVG = '<svg class="rushmk" viewBox="0 0 52 47" aria-hidden="true"><use href="#rush"/></svg>';
  function ballChip(n, slot) {
    return '<span class="ptdbtn ptdbtn--n' + n + '">' +
      '<i class="ntick ntick--n' + n + ' ball">' + BALLSVG + '</i>' +
      '<span class="ptdline">' + n + '+</span>' +
      (slot && slot[0] ? priceSlot(slot[0], slot[1], true) : GHOST) + '</span>';
  }
  /* ---- the football card: one template for the NFL and college ----
     Every football card is this one layout, slot by slot, top to bottom:
       head       the away club, its moneyline | the kickoff | the home club, its moneyline
       h2h        the two passers' names, the head-to-head price each side, the yards bar
       ptd        the passing touchdowns, 1+ and 2+ a side, the count between
       atd        the rushing touchdowns
       foot       the arrow, its sheet, the play button
     A league changes what goes in a slot, never where the slot is (Jose, Sep
     29, 2026: "a template ... literally plug and play"; "they vary slightly"):
     college writes the ranking beside the club and the passers' names over
     the touchdown rows, and always shows the rushing row with both rungs; the
     NFL shows the club's badge and the rushing row, 1+ only, once it is priced. */
  var FOOTBALL = {
    "nfl": { ml: [9, 10, 11, 12], names: false, runAlways: false,
             attrs: function (g) { return ' data-lhome="0"'; },
             p4: function (g) { return ""; },
             club: function (g, side) { return badge(side ? g[4] : g[3]); },
             watch: function (g) { return watchLink(g[1]); } },
    "college-football": { ml: [10, 11, 12, 13], names: true, runAlways: true,
             attrs: function (g) { return ' data-sport="college-football" data-lhome="0" data-lab="' + g[3] + '" data-rab="' + g[4] + '"'; },
             p4: function (g) { return ' data-p4="' + g[9] + '"'; },
             club: function (g, side) { return side ? rank(g[15]) + g[4] : rank(g[14]) + g[3]; },
             watch: function (g) { return cfbWatch(g[3], g[4], g[1]); } }
  };
  function footballFrame(g, lg) {
    var T = FOOTBALL[lg];
    var id = g[1], kick = g[2], away = g[3], home = g[4];
    var aq = g[5], aqid = g[6], hq = g[7], hqid = g[8];
    var p = etParts(kick);
    var pr = PROPS[id] || {};
    /* the price where there is one, the empty slot where there is not: a game
       DraftKings has not priced still shows the row, so every card reads alike */
    var h2h = function (i) {
      var slot = (pr.h2h || [])[i];
      return slot && slot[0] ? priceSlot(slot[0], slot[1]) : GHOST;
    };
    var names = function (lab) {
      return '<div class="ptdhead"><span style="color:var(--amber)">' + last(aq) +
        '</span><span class="gmk">' + lab + '</span>' +
        '<span style="color:#ffffff">' + last(hq) + '</span></div>';
    };
    var counts = '<span class="trkbox ptdcount">0</span><span class="trkbox ptdcount">0</span>';
    /* the anytime mark is Sportradar's runner (site/ico/rush.svg), the
       football stays the passing mark (Jose, Sep 16, 2026) */
    var chip = function (kind, n, slot) {
      return '<span class="ptdbtn ptdbtn--n' + n + '">' +
        '<i class="ntick ntick--n' + n + ' ball' + (kind === "ATD" ? " ball--run" : "") + '">' + (kind === "ATD" ? RUSHSVG : BALLSVG) + '</i>' +
        '<span class="ptdline">' + n + '+</span>' +
        (slot && slot[0] ? priceSlot(slot[0], slot[1], true) : GHOST) + '</span>';
    };
    var pane = function (kind, w, rungs) {
      var mine = (pr[kind === "ATD" ? "atd" : "ptd"] || [])[w === "l" ? 0 : 1] || [];
      return '<div class="ptdside ptdside--' + w + '">' + chip(kind, 1, mine[0]) +
        (rungs === 2 ? chip(kind, 2, mine[1]) : '<span class="ptdbtn ptdbtn--n2"></span>') + '</div>';
    };
    var ptd = '<div class="ptdx ptdx--v2 ptdx--balls" data-scale="2" data-kind="PTD">' +
      (T.names ? names("PTD") : "") +
      '<div class="ptdrow">' + pane("PTD", "l", 2) + counts + pane("PTD", "r", 2) + '</div></div>';
    /* the NFL's anytime row, 1+ only and only once priced: we capture both
       rungs but draw the first (Jose, Sep 16, 2026) */
    var atd = T.runAlways
      ? '<div class="ptdx ptdx--v2 ptdx--balls" data-scale="2" data-kind="ATD">' + names("ATD") +
        '<div class="ptdrow">' + pane("ATD", "l", 2) + counts + pane("ATD", "r", 2) + '</div></div>'
      : ((pr.atd || []).some(function (x) { return (x || [])[0]; })
        ? '<div class="ptdx ptdx--v2 ptdx--balls ptdx--run" data-scale="2" data-kind="ATD">' +
          '<div class="ptdrow">' + pane("ATD", "l", 1) + counts + pane("ATD", "r", 1) + '</div></div>' : "");
    return '<div class="gcard" data-espn="' + id + '" data-lg="' + lg + '"' + T.attrs(g) +
      ' data-lqb="' + aq + '" data-lqbid="' + aqid + '"' +
      ' data-rqb="' + hq + '" data-rqbid="' + hqid + '"' +
      T.p4(g) + ' data-kick="' + kick + '">' +
      '<div class="ghead"><span class="gteam gteam--flip"><span class="gml">' +
      priceSlot(g[T.ml[0]], g[T.ml[1]]) +
      '</span>' + T.club(g, 0) + '</span><span class="gtime">' + p.time + '</span>' +
      '<span class="gteam">' + T.club(g, 1) + '<span class="gml">' +
      priceSlot(g[T.ml[2]], g[T.ml[3]]) + '</span></span></div>' +
      '<div class="h2hx">' + names("H2H") +
      '<div class="h2hrow"><span class="h2hend"><span class="trkbox">0</span>' +
      '<span class="h2hodds">' + h2h(0) + '</span></span><div class="h2hbar">' +
      '<i class="h2hzero"></i><div class="h2hfill" style="left:50%; width:0"></div>' +
      '<i class="h2htick" style="left:50%"><b></b></i></div>' +
      '<span class="h2hend"><span class="trkbox">0</span>' +
      '<span class="h2hodds">' + h2h(1) + '</span></span></div></div>' +
      ptd + atd +
      '<button class="gmorebtn" type="button" aria-label="More">' +
      '<svg viewBox="0 0 24 24" width="18" height="18">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg></button>' +
      sheetFor(away + ' v ' + home, false, lg) + T.watch(g) + '</div>';   /* the sheet must follow its arrow */
  }
  function frame(g) { return footballFrame(g, "nfl"); }

  /* the game on theScore Bet, whose phone app streams the NFL (BetVision):
     the book's own event address, which opens the app on a phone. Only games
     score_watch.py has tied get the mark. (Jose, Sep 16, 2026: NFL first.) */
  /* YouTube TV, where Jose watches: its app claims every path but a blocked
     list, so a plain tap opens the app on a phone that has it. theScore Bet's
     route is parked below -- WATCH and score_watch.py still keep the book's
     event ids, and SCORE_WATCH turns it back on. (Jose, Sep 16, 2026) */
  var SCORE_WATCH = false;
  /* who is showing it (networks.py, from theScore's listings): the exclusive
     ones get their own app, everything else YouTube TV (Jose, Sep 16, 2026) */
  var NETWORKS = {};
  var RECORDS = {};
  var NET_APP = [
    [/prime video|amazon/i, "Prime Video", "https://app.primevideo.com/"],
    [/netflix/i, "Netflix", "https://www.netflix.com/browse"],
    /* only a stream no channel carries gets its own app: a game on NBC and
       Peacock, or on NFL Network, is on YouTube TV like everything else
       (audit, Sep 28, 2026, against Jose's Sep 16 rule) */
    [/^(?!.*\bnbc\b).*peacock/i, "Peacock", "https://www.peacocktv.com/watch/sports"],
    [/^nfl\+$/i, "NFL+", "https://www.nfl.com/plus/"],
    [/espn\+/i, "ESPN", "https://www.espn.com/watch/"]
  ];
  function watchMark(eid) {
    var net = NETWORKS[eid] || "", where = "YouTube TV", url = "https://tv.youtube.com/live/";
    for (var i = 0; i < NET_APP.length; i++) {
      if (NET_APP[i][0].test(net)) { where = NET_APP[i][1]; url = NET_APP[i][2]; break; }
    }
    var on = NETWORKS[eid] || where;
    var hot = /prime video|amazon/i.test(on) ? " gwatch--blue" : " gwatch--red";
    return '<a class="gwatch gwatch--yt' + hot + '" href="' + url + '" aria-label="Watch on ' + where + '">' +
      '<svg class="tvplay" viewBox="0 0 22 22" aria-hidden="true"><use href="#tvplay"/></svg></a>';
  }
  /* every college card carries the mark, the same as an NFL card: a card
     Jose has hidden is off the board already, so nothing needs testing
     (Sep 16, 2026) */
  function cfbWatch(away, home, eid) {
    return watchMark(eid);
  }
  function watchLink(id) {
    var eid = WATCH[id];
    if (!SCORE_WATCH) return watchMark(id);
    if (!eid) return "";
    /* a plain tap, no new tab: iOS hands the address to the app only on a plain tap */
    return '<a class="gwatch" aria-label="Watch on theScore Bet" data-path="' + PATH_NFL + eid + '" href="' +
      /* the web address, for a desktop. On a phone the click handler below
         opens the app by its own scheme instead. Every universal-link host of
         theirs was tried on Sep 16, 2026 -- sportsbook.thescore.bet (malformed
         file), app.thescore.bet (names the old ESPN BET app), thescorebet.app.link
         and thescorebet.onelink.me (the app does not claim them) -- and none
         opened the app; the scheme does, with iOS's "Open in theScore Bet?" */
      "https://sportsbook.thescore.bet" + PATH_NFL + eid + '">' +
      '<svg class="tvplay" viewBox="0 0 22 22" aria-hidden="true"><use href="#tvplay"/></svg></a>';
  }
  var PATH_NFL = "/sport/football/organization/united-states/competition/nfl/event/";
  /* a fight card's mark opens Paramount+ on its UFC page: the app on a phone
     that has it (their Apple link file claims /brands/*), the site otherwise.
     Present and coming cards only -- a finished bout has nothing to watch. */
  function watchFight() {
    return '<a class="gwatch gwatch--pp gwatch--blue" href="https://www.paramountplus.com/brands/ufc/" aria-label="Watch on Paramount+">' +
      '<svg class="tvplay" viewBox="0 0 22 22" aria-hidden="true"><use href="#tvplay"/></svg></a>';
  }
  function onelinkKeys(path) {
    var web = "https://sportsbook.thescore.bet" + path, app = "espn-sportsbook:/" + path.replace(/^\//, "");
    return ["af_dp=" + encodeURIComponent(app), "deep_link_value=" + encodeURIComponent(path),
            "af_web_dp=" + encodeURIComponent(web), "pid=sports-odds"].join("&");
  }
  function branchKeys(path) {
    var web = "https://sportsbook.thescore.bet" + path, app = "espn-sportsbook:/" + path.replace(/^\//, "");
    return ["$deeplink_path=" + encodeURIComponent(path), "$canonical_url=" + encodeURIComponent(web),
            "$android_url=" + encodeURIComponent(app), "$fallback_url=" + encodeURIComponent(web)].join("&");
  }
  /* On a phone, try the app's own scheme first -- the one theScore Bet's API
     writes on every address it hands the app ("espn-sportsbook:/sport/...").
     If nothing answers inside a moment, go to the web address as before. */
  document.addEventListener("click", function (e) {
    var ball = e.target.closest(".ptdx--balls .ntick.ball.ball--clip");
    if (ball) {
      var go = ball.parentNode && ball.parentNode.querySelector(".ptdplay");
      if (go) { e.preventDefault(); e.stopPropagation(); go.click(); return; }
    }
    var a = e.target.closest("a.gwatch");
    if (!a || !a.dataset.path || !/iPhone|iPad|Android/i.test(navigator.userAgent)) return;
    e.preventDefault();
    /* no web fallback: iOS shows its prompt, and a timer under it also sent
       Jose to the App Store */
    window.location.href = "espn-sportsbook:/" + a.dataset.path.replace(/^\//, "");
  });

  /* a college card: moneyline, the head to head, passing and anytime touchdowns.
     DraftKings prices the passers' matchup for college too, under the same
     category, so the two boards are drawn the same (Jose, Sep 17, 2026). */
  function cfbFrame(g) { return footballFrame(g, "college-football"); }

  /* One fight, as a card: the two men with a slot for each price. */

  /* ---- the same bet, twice ----
     "Finish" and "KO or submission" are one outcome; so are "doesn't go the
     distance" and the two men's finish prices. Books price them from separate
     templates and do not always reconcile, so where a pair that should match
     does not, the better side is lit and the worse dimmed. */
  function asDec(btn) {
    if (!btn) return null;
    var n = parseInt((btn.childNodes[0] ? btn.childNodes[0].textContent : "")
      .replace(/\u2212|\u2013|\u2014/g, "-").replace(/[^\-0-9]/g, ""), 10);
    if (isNaN(n) || n === 0) return null;
    return n > 0 ? 1 + n / 100 : 1 + 100 / -n;
  }
  function markTwins(sheet) {
    var note = sheet.querySelector(".mktnote");
    var said = [];
    function pair(a, b, which) {
      if (!a || !b) return;
      [0, 1].forEach(function (col) {
        var x = a.querySelectorAll("button.price")[col];
        var y = b.querySelectorAll("button.price")[col];
        var dx = asDec(x), dy = asDec(y);
        if (dx === null || dy === null || Math.abs(dx - dy) < 0.005) return;
        var better = dx > dy ? x : y, worse = dx > dy ? y : x;
        better.classList.add("price--better");
        worse.classList.add("price--worse");
        said.push(which + " is priced twice and the two do not agree");
      });
    }
    /* every pair of rows the book says is one bet */
    var twins = {};
    sheet.querySelectorAll(".mktrow[data-twin]").forEach(function (r) {
      (twins[r.dataset.twin] = twins[r.dataset.twin] || []).push(r);
    });
    Object.keys(twins).forEach(function (k) {
      if (twins[k].length === 2) pair(twins[k][0], twins[k][1], k);
    });
    if (said.length) {
      note.textContent = said[0] + " \u2014 the longer one is lit.";
      note.hidden = false;
    } else {
      note.hidden = true;
    }
  }
  /* The divisions, abbreviated the way the sport abbreviates them. A women's
     division carries the W in front, which is the whole difference between
     WBW and BW. (Jose, Sep 17, 2026) */
  var WTSHORT = {
    "strawweight": "SW", "flyweight": "FLW", "bantamweight": "BW",
    "featherweight": "FW", "lightweight": "LW", "welterweight": "WW",
    "middleweight": "MW", "light heavyweight": "LHW", "heavyweight": "HW",
    "catchweight": "CW", "super heavyweight": "SHW", "openweight": "OW"
  };
  function evShort(n) {
    /* the bill as the row writes it: the long prefix shortened, the fight
       itself kept. Every row wears the octagon, so a numbered card is its
       number and a fight night is FN -- the UFC in front of them said what
       the mark already says. DWCS reads S10 Wk 7 (Jose, Sep 19, 2026).
       Noche UFC keeps its own name: the UFC is part of it. */
    return String(n || "")
      .replace(/^Dana White'?s Contender Series:?\s*/i, "DWCS ")
      .replace(/\bSeason\s+(\d+),?\s*Week\s+(\d+)\b/i, "S$1 Wk $2")
      .replace(/^UFC\s+(?=\d)/i, "")
      .replace(/^UFC Fight Night\b/i, "FN")
      .replace(/\bUFC Fight Night\b/i, "UFC FN")
      .replace(/\bFight Night\b/i, "FN");
  }
  function evTag(n) {
    /* the same bill for the slip, where a leg has one line to say which card
       it is on: a numbered card is its number, the rest are DWCS and UFC FN
       (Jose, Sep 18, 2026) */
    var t = String(n || "");
    var num = /\bUFC\s+(\d{2,4})\b/i.exec(t);
    if (num) return "UFC " + num[1];
    if (/Contender Series|\bDWCS\b/i.test(t)) return "DWCS";
    if (/Fight Night/i.test(t) || /\bUFC FN\b/i.test(t)) return "UFC FN";
    return evShort(t);
  }


  /* the UFC's own limits. A catchweight has none -- it is agreed fight by
     fight -- so a bout at one is written as the class the two men normally
     fight at, which their other bouts on the board settle (Jose, Sep 19, 2026) */
  var WTLBS = {
    "strawweight": 115, "flyweight": 125, "bantamweight": 135,
    "featherweight": 145, "lightweight": 155, "welterweight": 170,
    "middleweight": 185, "light heavyweight": 205, "heavyweight": 265
  };
  var USUAL = null;
  function usualClass(id) {
    if (!USUAL) {
      USUAL = {};
      (typeof FIGHTS === "undefined" ? [] : FIGHTS).forEach(function (g) {
        var w = String(g[7] || "").replace(/^\s*(w|women'?s)\b[\s.]*/i, "").toLowerCase();
        if (!WTLBS[w]) return;
        [g[4], g[6]].forEach(function (a) {
          if (!a) return;
          USUAL[a] = USUAL[a] || {};
          USUAL[a][w] = (USUAL[a][w] || 0) + 1;
        });
      });
    }
    var seen = USUAL[id];
    if (!seen) return "";
    var best = "", n = 0;
    Object.keys(seen).forEach(function (w) { if (seen[w] > n) { n = seen[w]; best = w; } });
    return best;
  }
  /* what stands behind a bout card: the class in initials and the weight it
     is fought at -- LHW 205. The W that marks a women's class is left off:
     the limit is the same number and the men and women's cards read alike. */
  /* boxing's own limits, which are not the UFC's: a boxing middleweight is 160 */
  var BOXLBS = {
    "heavyweight": ["HW", "200+"], "bridgerweight": ["BRW", 224], "cruiserweight": ["CRW", 200],
    "light heavyweight": ["LHW", 175], "super middleweight": ["SMW", 168], "middleweight": ["MW", 160],
    "super welterweight": ["SWW", 154], "light middleweight": ["SWW", 154], "welterweight": ["WW", 147],
    "super lightweight": ["SLW", 140], "light welterweight": ["SLW", 140], "lightweight": ["LW", 135],
    "super featherweight": ["SFW", 130], "featherweight": ["FW", 126], "super bantamweight": ["SBW", 122],
    "bantamweight": ["BW", 118], "super flyweight": ["SFLW", 115], "flyweight": ["FLW", 112],
    "light flyweight": ["LFLW", 108], "minimumweight": ["MINW", 105]
  };
  function wtMark(w, lid, rid) {
    var bx = /^boxing\s+(.*)$/i.exec(String(w || ""));
    if (bx) {
      var bt = BOXLBS[bx[1].replace(/^\s*(w|women'?s)\b[\s.]*/i, "").trim().toLowerCase()];
      return bt ? bt[0] + " \u00b7 " + bt[1] : "";
    }
    var t = String(w || "").replace(/^\s*(w|women'?s)\b[\s.]*/i, "").trim().toLowerCase();
    if (!WTLBS[t]) {
      var a = usualClass(lid), b = usualClass(rid);
      t = (a && b) ? (a === b ? a : "") : (a || b);
    }
    if (!t || !WTLBS[t]) return "";
    return (WTSHORT[t] || t.toUpperCase()) + " \u00b7 " + WTLBS[t];
  }
  function wtShort(w) {
    var t = String(w || "").replace(/^boxing\s+/i, "").trim();
    if (!t) return "";
    var fem = /^(w|women'?s)\b[\s.]*/i.exec(t);
    if (fem) t = t.slice(fem[0].length);
    var ab = WTSHORT[t.toLowerCase()];
    if (!ab) return String(w || "").toUpperCase();
    return (fem ? "W" : "") + ab;
  }
  /* the class written out -- Heavyweight, Light Heavyweight -- with a W in
     front of the women's (Jose, Sep 19, 2026). The short forms stay where a
     row has no room for the words. */
  function wtFull(w) {
    var t = String(w || "").replace(/^boxing\s+/i, "").trim();
    if (!t) return "";
    var fem = /^(w|women'?s)\b[\s.]*/i.exec(t);
    if (fem) t = t.slice(fem[0].length);
    if (!WTSHORT[t.toLowerCase()]) return String(w || "");
    return (fem ? "W " : "") + t;
  }
  function fightFrame(f) {
    FS_BOUT = f[1];          /* the sheet's rows read this bout's prices */
    var p = etParts(f[2]);
    return '<div class="gcard" data-bout="' + f[1] + '" data-event="' + f[0] + '" data-sport="mma"' +
      ' data-wt="' + esc(wtMark(f[7], f[4], f[6])) + '"' +
      ' data-lf="' + f[3] + '" data-rf="' + f[5] + '"' +
      ' data-lfid="' + (f[4] || "") + '" data-rfid="' + (f[6] || "") + '"' +
      ' data-kick="' + f[2] + '">' +
      '<div class="ghead ghead--fight"><span class="gteam gteam--flip"><span class="gml">' +
      priceSlot(f[8], f[9]) + '</span>' +
      '<span class="fman">' + mug(f[4], f[12]) +
      '<span class="fname">' + lastName(f[3]) + '</span></span></span>' +
      '<i class="fvs"><svg viewBox="0 0 26 22" aria-hidden="true"><use href="#vs"/></svg></i>' +
      '<span class="gtime">' + p.time + '</span>' +
      '<span class="gteam"><span class="fman">' + mug(f[6], f[13]) +
      '<span class="fname">' + lastName(f[5]) + '</span></span>' +
      '<span class="gml">' + priceSlot(f[10], f[11]) + '</span></span></div>' +
      /* the weight sits under the clock, which puts it on the names' own line
         rather than on a line of its own. The arrow opens the ways a fight
         can end -- no win probability, since ESPN publishes none for MMA. */
      '<button class="gmorebtn" type="button" aria-label="More">' +
      '<svg viewBox="0 0 24 24" width="18" height="18">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg></button>' +
      '<dialog class="sheet gsheet"><div class="sheet__head">' +
      '<button class="sheet__x" type="button" data-shut aria-label="Back">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<h2 class="sheet__title">' + lastName(f[3]) + ' v ' + lastName(f[5]) + '</h2>' +
      '<span aria-hidden="true"></span></div>' +
      '<div class="sheet__scroll"><div class="hits" hidden></div>' + fightSheet(f) + '</div></dialog>' +
      watchFight() + '</div>';
  }
  /* a face where ESPN has one, the empty box where it does not -- a card
     with no picture still has to line up with the one beside it */
  /* ---- pictures ----
     Every mark and every face is kept in site/ by mirror.py. The address it
     came from is left on the tag as the fallback, so a club or a fighter
     added between mirrors still draws (Jose, Sep 18, 2026). */
  var ESPN_CLUB = "https://a.espncdn.com/combiner/i?img=/i/teamlogos/";
  function clubPic(lg, key) {
    return "logos/" + lg + "/" + key + ".png";
  }
  function clubAway(lg, key) {
    return ESPN_CLUB + lg + "/500/" + key + ".png&w=96&h=96";
  }
  /* through the face function, like a passer's: a fighter we have not
     mirrored yet is a 404, never the web page cached for a month */
  /* the one picture that stands for a man we have none of */
  var UNKNOWN = "faces/mma/unknown.png";
  function facePic(id) { return "face/mma/" + id + ".png"; }
  function faceAway(id) {
    return "https://a.espncdn.com/combiner/i?img=/i/headshots/mma/players/full/" +
           id + ".png&w=220&h=220&scale=crop";
  }
  function scorePic(id) { return "face/mma/s" + id + ".png"; }
  function scoreAway(id) {
    return "https://assets-sports-gcp.thescore.com/mma/fighter/" + id + "/w192xh192_headshot.png";
  }
  /* Fighters neither ESPN nor theScore has a picture of, written by
     build/mirror.py. Their addresses were still in every chain, so a reader's
     browser asked two outside hosts for a picture that has never existed and
     was answered 404 both times -- fourteen of them on one card. A man on
     this list is not asked for (Jose, Sep 22, 2026). */
  var NOPIC = {};
  fetch("nopic.json", { cache: "no-store" })
    .then(function (r) { return r.ok ? r.json() : null; })
    .then(function (j) {
      if (!j || !j.length) return;
      var was = Object.keys(NOPIC).length;
      j.forEach(function (k) { NOPIC[String(k)] = 1; });
      /* the faces are already drawn by the time this lands, and a picture
         that is going to 404 should not be asked for twice */
      if (Object.keys(NOPIC).length !== was && typeof paintAll === "function") {
        document.querySelectorAll("img.ffab[data-next]").forEach(function (im) {
          im.dataset.next = (im.dataset.next || "").split("|")
            .filter(function (u) { return u && u.indexOf("http") !== 0; }).join("|");
        });
      }
    })
    .catch(function () {});
  function mug(id, scoreId) {
    /* UFC's own no-profile picture, held here rather than linked: a bout with
       nobody announced, or a debutant neither source has shot, draws the
       silhouette rather than an empty box (Jose, Sep 22, 2026). */
    if (!id && !scoreId) return '<img class="ffab ffab--un" alt="" src="' + UNKNOWN + '">';
    /* a boxer: the picture from his Wikipedia article, kept by boxing.py */
    if (/^box:/.test(String(id))) return '<img class="ffab" alt="" src="faces/box/' + String(id).slice(4) + '.jpg"' +
      ' onerror="this.onerror=null;this.src=\'' + UNKNOWN + '\';this.className=\'ffab ffab--un\'">';
    /* ours first, then ours of theScore's, then the two addresses themselves --
       and never an address for a man we have written down as having none */
    var chain = [];
    if (id) { chain.push(facePic(id)); }
    if (scoreId) { chain.push(scorePic(scoreId)); }
    if (id && !NOPIC[String(id)]) { chain.push(faceAway(id)); }
    if (scoreId && !NOPIC["s" + scoreId]) { chain.push(scoreAway(scoreId)); }
    var first = chain.shift() || "";
    var second = chain.join("|");
    /* ESPN has no picture of many Contender Series men; theScore does. Neither: the silhouette. */
    return '<img class="ffab" alt="" src="' + first + '" data-next="' + second + '"' +
           ' onerror="var q=(this.dataset.next||\'\').split(\'|\').filter(Boolean);' +
           'if(q.length){this.src=q.shift();this.dataset.next=q.join(\'|\');}' +
           'else if(this.src.indexOf(\'unknown\')<0){this.src=\'faces/mma/unknown.png\';this.className=\'ffab ffab--un\';}">';
  }
  function lastName(n) {
    var bits = String(n || "").trim().split(" ");
    return (bits.length > 1 ? bits.slice(1).join(" ") : bits[0]).toUpperCase();
  }
  /* the family name: the last word that is not a suffix, so Stetson
     Bennett IV reads Bennett, not IV (Jose, Sep 16, 2026) */
  function famName(n) {
    var bits = String(n || "").trim().split(" ").filter(function (b) { return !/^(Jr\.?|Sr\.?|II|III|IV|V)$/i.test(b); });
    return bits.length ? bits[bits.length - 1] : String(n || "");
  }

  /* The same chart the hand-built cards carry, with ids of its own. */
  var wpn = 0;
  function chartFor(lname, rname, lg) {
    var k = "d" + (++wpn);
    /* each side of the chart wears its own club, lifted enough to read on
       the near-black ground */
    var lc = readable(driveHue(lname, lg)) || "var(--amber)";
    var rc = readable(driveHue(rname, lg)) || "#ffffff";
    return '<div class="wprow"><span class="wpteam" style="color:' + lc + '">' +
      lname + '</span><span class="wpbig">&mdash;</span></div>' +
      '<div class="wpx"><svg viewBox="0 0 300 120" preserveAspectRatio="none">' +
      '<defs><clipPath id="' + k + '-over"><rect x="0" y="0" width="300" height="60"/>' +
      '</clipPath><clipPath id="' + k + '-under"><rect x="0" y="60" width="300" height="60"/>' +
      '</clipPath></defs>' +
      '<line class="wpq" x1="75" y1="0" x2="75" y2="120"/>' +
      '<line class="wpq" x1="150" y1="0" x2="150" y2="120"/>' +
      '<line class="wpq" x1="225" y1="0" x2="225" y2="120"/>' +
      '<line class="wpe" x1="0" y1="60" x2="300" y2="60"/>' +
      '<polygon points="" fill="' + lc + '" opacity="0.18" clip-path="url(#' + k + '-over)"/>' +
      '<polygon points="" fill="' + rc + '" opacity="0.18" clip-path="url(#' + k + '-under)"/>' +
      '<polyline points="" fill="none" stroke="' + lc + '" stroke-width="2" ' +
      'vector-effect="non-scaling-stroke" clip-path="url(#' + k + '-over)"/>' +
      '<polyline points="" fill="none" stroke="' + rc + '" stroke-width="2" ' +
      'vector-effect="non-scaling-stroke" clip-path="url(#' + k + '-under)"/>' +
      '</svg></div>' +
      '<div class="wprow"><span class="wpteam" style="color:' + rc + '">' + rname +
      '</span><span class="wpbig">&mdash;</span></div>';
  }


  /* bare: no win-probability chart. ESPN publishes none for MMA, so a fight
     sheet would only ever show two dashes over an empty box. */
  function sheetFor(title, bare, lg) {
    return '<dialog class="sheet gsheet"><div class="sheet__head">' +
      '<button class="sheet__x" type="button" data-shut aria-label="Back">' +
      '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
      '<path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" ' +
      'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
      '<h2 class="sheet__title">' + title + '</h2>' +
      '<span aria-hidden="true"></span></div>' +
      '<div class="sheet__scroll"><div class="hits" hidden></div>' +
      (bare ? "" : chartFor(title.split(" v ")[0], title.split(" v ").pop(), lg)) +
      '</div></dialog>';
  }

  function ptdSide(which) {
    var edge = which === "l" ? "right" : "left";
    return '<div class="ptdside ptdside--' + which + '"><div class="ptdbar">' +
      '<div class="ptdfill" style="' + edge + ':0; width:0%"></div>' +
      '<i class="ntick ntick--n1" style="' + edge + ':50.0%"><b>1</b></i>' +
      '<i class="ntick ntick--n2" style="' + edge + ':100.0%"><b>2</b></i></div>' +
      '<div class="ptdmarks"><span class="ptdbtn ptdbtn--n1">' +
      '<span class="ptdline">1+</span>' + GHOST + '</span>' +
      '<span class="ptdbtn ptdbtn--n2"><span class="ptdline">2+</span>' +
      GHOST + '</span></div></div>';
  }

  /* ---- the pool ----
     Every card built by hand lives here until a view asks for it. Moving the
     node keeps its prices, its handlers and whatever the settler has already
     written on it; drawing a fresh one would throw all three away. */
  var POOL = document.getElementById("pool");
  var BOARD = document.getElementById("board"), MAINBOARD = BOARD;
  var STATIC = {};
  POOL.querySelectorAll(".gcard").forEach(function (c) {
    var k = c.dataset.espn || c.dataset.bout || c.dataset.fight;
    if (k) { STATIC[k] = c; c.dataset.pooled = "1"; }
  });

  /* ---- what is put away ----
     Cards are remembered by the id they already carry, so a card hidden on
     Sunday is still hidden when Sunday is looked at again. */
  /* ---- the marks, kept on the site ----
     Hidden games, placed prices and the slip used to live in each browser, so
     the phone, the iPad and the desktop each had their own and none agreed.
     There is one reader, so there is one blob at /state, and whatever a
     device last wrote is what the others read (Jose, Sep 19, 2026). */
  /* the key rides in the page. It is not a secret from the reader -- the
     board is his -- it only keeps a passer-by from writing to the store by
     hand. Anyone who reads the source can see it, which is the price of
     every device working the moment it opens the site
     (Jose, Sep 19, 2026: "I don't want to have to change anything") */
  var ARENAOWN = "arena-001bff8ddf784985";
  var ARENAKEY = ARENAOWN;
  try { ARENAKEY = localStorage.getItem("arena.key") || ARENAOWN; } catch (e) {}
  var ARENAQ = function () { return ARENAKEY ? "state?k=" + encodeURIComponent(ARENAKEY) : "state"; };
  /* A key handed to a device by an older link outlives the key the store
     wants, and then every read comes back refused -- with nothing on the
     screen to say so. The device sat on its own marks for a whole evening
     that way (Jose, Sep 19, 2026: "i dont see it"). So a refusal drops the
     handed key, falls back to the one written in the page, and asks once
     more. It returns whether there was anything to drop: where the page's
     own key is the one being refused, there is nothing to retry with. */
  function arenaRefused() {
    if (ARENAKEY === ARENAOWN) return false;
    ARENAKEY = ARENAOWN;
    try { localStorage.removeItem("arena.key"); } catch (e) {}
    return true;
  }
  var pushTimer = null;
  /* the starred quarterbacks in the search's row, by ESPN id, synced like
     every other mark */
  var STARS = {};
  try { STARS = JSON.parse(localStorage.getItem("arena.stars") || "{}") || {}; } catch (e) { STARS = {}; }
  window.STARS = STARS;
  /* what the store held for each mark when this device last read or wrote it */
  var LASTSYNC = {};
  /* ---- this device's own changes, for two minutes ----
     The store is Cloudflare KV, and a read there can hand back the copy from
     before a write for up to a minute. Two things came of it: a second tap's
     write was laid over a stale copy that still held the first tap's gold,
     and put it back for good; and the page's own re-read painted the old
     gold over taps he had just taken off (Jose, Sep 29, 2026: "I un-click,
     two seconds later it refreshes and it's 17 bets"). So every change is
     logged the moment it is made, every write carries the whole log, and
     every read has the log laid back over it: nothing stale can undo a tap
     made in the last two minutes. */
  var JOURNAL = [], JWIN = 120000;
  try { JOURNAL = JSON.parse(sessionStorage.getItem("arena.journal") || "[]") || []; } catch (e) { JOURNAL = []; }
  function journalNow() {
    var cut = Date.now() - JWIN;
    JOURNAL = JOURNAL.filter(function (e) { return e.t > cut; });
    try { sessionStorage.setItem("arena.journal", JSON.stringify(JOURNAL)); } catch (e) {}
    return JOURNAL;
  }
  function journalOver(k, list) {
    var out = {};
    Object.keys(list || {}).forEach(function (x) { out[x] = list[x]; });
    journalNow().forEach(function (e) {
      if (e.k !== k) return;
      if (e.del) delete out[e.x]; else out[e.x] = e.v;
    });
    return out;
  }
  function marksNow() {
    return {hidden: hid || {}, placed: placed || {}, picks: saved || {}, stars: STARS || {},
            ring: (typeof RINGED === "object" && RINGED) || {},
            bank: (typeof BANKMET !== "undefined" && BANKMET && typeof BANK === "object" && BANK) || null};
  }
  var APPLYING = false;
  function pushState() {
    /* while a read of the store is being laid onto the page, the page is
       half old and half new: a save asked for then waits until the read is
       done, or it saw an empty slip beside a full store and sent deletes
       (Sep 29, 2026) */
    if (APPLYING) { setTimeout(pushState, 0); return; }
    /* the change is logged now, at the tap, before any read can land */
    var all0 = marksNow(), t0 = Date.now();
    Object.keys(all0).forEach(function (k) {
      if (k === "bank" || all0[k] === null || LASTSYNC[k] === undefined) return;
      var js = JSON.stringify(all0[k]);
      if (js === LASTSYNC[k]) return;
      var was = {};
      try { was = JSON.parse(LASTSYNC[k]) || {}; } catch (e) { was = {}; }
      var mine = journalOver(k, was);
      Object.keys(all0[k]).forEach(function (x) {
        if (all0[k][x] === undefined || all0[k][x] === null) return;
        if (JSON.stringify(all0[k][x]) !== JSON.stringify(mine[x])) JOURNAL.push({k: k, x: x, v: all0[k][x], t: t0});
      });
      /* gone, or left behind as an empty key: either way a removal */
      Object.keys(mine).forEach(function (x) {
        if (!(x in all0[k]) || all0[k][x] === undefined || all0[k][x] === null) JOURNAL.push({k: k, x: x, del: 1, t: t0});
      });
    });
    journalNow();
    clearTimeout(pushTimer);
    pushTimer = setTimeout(function () {
      /* only the marks this device changed go up, laid over what the site
         holds: sending the whole copy let a device left open put back gold
         he had taken off on another (Jose, Sep 28, 2026). Every change of the
         last two minutes goes, not only the newest, so a write laid over a
         stale copy still carries the tap before it. */
      var all = marksNow();
      var body = {patch: {}}, any = false, now = {};
      Object.keys(all).forEach(function (k) {
        if (all[k] === null) return;
        var js = JSON.stringify(all[k]);
        now[k] = js;
        if (k === "bank" || LASTSYNC[k] === undefined) {
          if (js === LASTSYNC[k]) return;
          any = true; body[k] = all[k]; return;
        }
        var set = {}, del = [];
        journalNow().forEach(function (e) {
          if (e.k !== k) return;
          if (e.del) { delete set[e.x]; if (del.indexOf(e.x) < 0) del.push(e.x); }
          else { set[e.x] = e.v; del = del.filter(function (d) { return d !== e.x; }); }
        });
        if (!Object.keys(set).length && !del.length) return;
        any = true;
        body.patch[k] = {set: set, del: del};
      });
      if (!any) return;
      var sent = function () { Object.keys(now).forEach(function (k) { LASTSYNC[k] = now[k]; }); };
      try {
        fetch(ARENAQ(), {
          method: "POST", headers: {"content-type": "application/json"},
          body: JSON.stringify(body)
        }).then(function (r) {
          if (r.ok) { sent(); return; }
          if (arenaRefused()) {
            fetch(ARENAQ(), {
              method: "POST", headers: {"content-type": "application/json"},
              body: JSON.stringify(body)
            }).then(function (r2) { if (r2.ok) sent(); }).catch(function () {});
          }
        }).catch(function () {});
      } catch (e) {}
    }, 700);
  }
  window.pushState = pushState;
  function pullState(again) {
    fetch(ARENAQ(), {cache: "no-store"})
      .then(function (r) {
        if (r.ok) return r.json();
        if (!again && arenaRefused()) pullState(1);
        return null;
      })
      .then(function (j) {
        if (!j) return;
        var moved = false;
        APPLYING = true;
        try {
        /* this device's own changes of the last two minutes are laid back
           over whatever the store answered: a stale copy never undoes a tap */
        ["hidden", "placed", "picks", "ring", "stars"].forEach(function (k) {
          if (j[k] !== undefined && j[k] !== null) j[k] = journalOver(k, j[k]);
        });
        /* what the store says now is what this device last saw of it */
        ["hidden", "placed", "picks", "ring", "stars", "bank"].forEach(function (k) {
          if (j[k] !== undefined && j[k] !== null) LASTSYNC[k] = JSON.stringify(j[k]);
        });
        /* the first time a device meets the store it hands over what it was
           already holding, so nothing any of them had is lost. After that the
           store is the truth, and an unhide travels the way a hide does */
        var first = false;
        try { first = !localStorage.getItem("arena.met"); } catch (e) {}
        if (first) {
          var fold = function (mine, theirs) {
            var out = {};
            Object.keys(theirs || {}).forEach(function (k) { out[k] = theirs[k]; });
            Object.keys(mine || {}).forEach(function (k) { out[k] = mine[k]; });
            return out;
          };
          j = {hidden: fold(hid, j.hidden), placed: fold(placed, j.placed), stars: fold(STARS, j.stars),
               picks: fold(saved, j.picks), ring: fold(RINGED, j.ring), bank: j.bank, at: Date.now()};
          try { localStorage.setItem("arena.met", "1"); } catch (e) {}
        } else if (!j.at) {
          return;
        }
        if (j.stars && JSON.stringify(j.stars) !== JSON.stringify(STARS)) {
          STARS = window.STARS = j.stars;
          try { localStorage.setItem("arena.stars", JSON.stringify(STARS)); } catch (e) {}
          if (window.qsRow) window.qsRow();
          if (window.clipsDraw) window.clipsDraw();
        } else if (!j.stars && Object.keys(STARS).length) pushState();
        if (j.hidden && JSON.stringify(j.hidden) !== JSON.stringify(hid)) {
          hid = j.hidden;
          try { localStorage.setItem(HIDEKEY, JSON.stringify(hid)); } catch (e) {}
          moved = true;
        }
        /* the balance is one number on every device; a store that has never
           held it is handed this device's */
        if (typeof BANK === "object") {
          if (j.bank && j.bank.bal != null) {
            if (JSON.stringify(j.bank) !== JSON.stringify(BANK)) { BANK = j.bank; BANK.legs = BANK.legs || {}; BANK.paid = BANK.paid || {}; bankKeep(); }
            BANKMET = true;
            /* after the marks below are read: drawn first, it saw no gold
               and dropped every leg's placed price (Sep 25, 2026) */
            setTimeout(bankDraw, 0);
          } else { BANKMET = true; pushState(); }
        }
        if (j.placed) {
          placed = j.placed;
          try { localStorage.setItem(PLACEDKEY, JSON.stringify(placed)); } catch (e) {}
        }
        /* a man ringed on the phone is ringed on the desktop: the store is the
           truth here as it is for the rest (Jose, Sep 20, 2026) */
        /* the rings predate the store, so a device holding some and a store
           holding none means the store has never been told -- hand them over
           rather than wiping them */
        /* the store is the truth for the rings too, empty included: handing a
           device's rings back to an empty store is what kept gold he had
           cleared coming back (Sep 28, 2026). Only a store that has never
           held the field at all is handed this device's. */
        if (!j.ring) {
          if (Object.keys(RINGED).length) pushState();
          j.ring = null;
        }
        if (j.ring && JSON.stringify(j.ring) !== JSON.stringify(RINGED)) {
          RINGED = j.ring;
          try { localStorage.setItem(RINGKEY, JSON.stringify(RINGED)); } catch (e) {}
          moved = true;
        }
        if (j.picks && JSON.stringify(j.picks) !== JSON.stringify(saved)) {
          Object.keys(saved).forEach(function (k) { delete saved[k]; });
          Object.keys(j.picks).forEach(function (k) { saved[k] = j.picks[k]; });
          try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
          /* the store handing this device its picks did not draw them. The
             legs were held, the bar stayed hidden and the count stayed at
             nought, so on any device but the one that tapped them the slip
             looked empty (Jose, Sep 19, 2026: "where is the bet slip").
             What used to stand here was a push straight back of what had
             just been read, which is not what was wanted. */
          moved = true;
        }
        } finally { APPLYING = false; }
        if (typeof markSaved === "function") markSaved(document);
        if (typeof placedState === "function") placedState();
        if (typeof slip === "function") slip();
        if (moved && typeof render === "function") render();
        if (first) pushState();
      })
      .catch(function () {});
  }
  var HIDEKEY = "odds.hidden.v1";
  var hid = {};
  try { hid = JSON.parse(localStorage.getItem(HIDEKEY) || "{}") || {}; } catch (e) { hid = {}; }
  function idOf(card) {
    return card.dataset.espn || card.dataset.bout || card.dataset.fight || "";
  }
  function saveHidden() {
    try { localStorage.setItem(HIDEKEY, JSON.stringify(hid)); } catch (e) {}
    pushState();
  }
  /* the eye Jose gave: a solid eye inside a rounded square -- lens filled,
     pupil cut out of it, the catchlight sat in the pupil. It rides the same
     line as the arrow and the watch mark (Jose, Sep 17, 2026) */
  var EYE = '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true">' +
    '<rect x="1.4" y="4.6" width="21.2" height="14.8" rx="4" fill="var(--ground)" ' +
    'stroke="currentColor" stroke-width="1.3"/>' +
    '<path fill="currentColor" fill-rule="evenodd" ' +
    'd="M3.4 12s3-4.6 8.6-4.6 8.6 4.6 8.6 4.6-3 4.6-8.6 4.6S3.4 12 3.4 12z' +
    'M12 9.2a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6z"/>' +
    '<circle cx="10.8" cy="10.9" r="0.95" fill="currentColor"/>' +
    /* the bar is cut through the eye first, so the slash reads on a solid shape */
    '<path class="slash" d="M5.4 16.6L18.6 7.4" stroke="var(--ground)" stroke-width="3.4" ' +
    'stroke-linecap="round"/>' +
    '<path class="slash" d="M5.4 16.6L18.6 7.4" stroke="currentColor" stroke-width="1.6" ' +
    'stroke-linecap="round"/></svg>';
  function hideBtn(on) {
    var b = document.createElement("button");
    b.className = "ghide";
    b.type = "button";
    b.setAttribute("aria-label", on ? "Show this game" : "Hide this game");
    b.innerHTML = EYE;
    b.querySelectorAll(".slash").forEach(function (s) { s.style.display = on ? "" : "none"; });
    return b;
  }
  /* the HBD bubble beside the passer's face on his birthday game: the first
     game he plays on or after the day, a bye moving it to the next one. A
     mark only; it touches no price (Jose, Sep 16, 2026). */
  /* each club's record entering the week, under its letters on the NFL head
     (Jose, Sep 17, 2026); from records.json, written by ledger.py on the sweep */
  function dressRecords(card) {
    var college = card.dataset.lg === "college-football";
    if (!college && card.dataset.lg !== "nfl") return;
    var rows = college ? CFB : SCHED, g = null;
    for (var i = 0; i < rows.length; i++) if (String(rows[i][1]) === card.dataset.espn) { g = rows[i]; break; }
    var week = g ? (RECORDS[college ? "ncaaf" : "nfl"] || {})[String(g[0])] : null;
    if (!week) return;
    card.querySelectorAll(".gclub .gabbr").forEach(function (ab) {
      if (ab.parentNode.querySelector(".grec")) return;
      var rec = week[ab.textContent.trim()];
      /* its own element after the letters, so the slip's label stays the letters alone (Jose, Sep 17, 2026) */
      if (rec) ab.insertAdjacentHTML("afterend", '<small class="grec">' + rec + "</small>");
    });
  }
  /* The birthday bubble is gone (Jose, Sep 22, 2026: "no birthday chips drop
     those"). It also cost a face: the wrapper it put round the picture was an
     inline-block where every other side is a block, so Shough's headshot
     measured 0x0 and the club mark showed through. */
  /* the names come out of the top line and go under the bar, once */
  function nameUnder(card) {
    var h = card.querySelector(".h2hx");
    if (!h || h.querySelector(".h2hnm")) return;
    var head = h.querySelector(".ptdhead");
    var row = h.querySelector(".h2hrow");
    if (!head || !row) return;
    var sides = head.querySelectorAll("span:not(.gmk)");
    if (!sides.length) { head.remove(); return; }
    /* the two names go directly under the bar, at its own two ends, so each
       stands over the half of the track that belongs to him */
    var bar = row.querySelector(".h2hbar");
    if (!bar) return;
    var stack = document.createElement("div");
    stack.className = "h2hstack";
    bar.parentNode.insertBefore(stack, bar);
    stack.appendChild(bar);
    var names = document.createElement("div");
    names.className = "h2hnames";
    /* the names ride above the bar, each over his own half, and the lead goes
       underneath it -- the two have changed places */
    names.className = "h2hnames h2hnames--over";
    var ends = h.querySelectorAll(".h2hend");
    [0, 1].forEach(function (i) {
      var nm = document.createElement("span");
      nm.className = "h2hnm";
      nm.textContent = sides[i] ? sides[i].textContent : "\u2014";
      nm.style.color = (sides[i] && sides[i].style.color) ||
                       (i ? "#ffffff" : "#ffffff");
      /* the line reads odds, name, face -- face, name, odds; the count boxes
         stay beside the bar under it (Jose, Sep 16, 2026) */
      var side = document.createElement("span");
      side.className = "h2hside" + (i ? " h2hside--r" : " h2hside--l");
      var odds = ends[i] && ends[i].querySelector(".h2hodds");
      var face = document.createElement("img");
      face.className = "qbface h2hqb"; face.alt = "";
      faceChain(face, "nfl", i ? card.dataset.rqbid : card.dataset.lqbid);
      face.src = faceSrc(card, i ? "r" : "l") || NOFACE;
      if (i) { side.appendChild(face); side.appendChild(nm); if (odds) side.appendChild(odds); }
      else { if (odds) side.appendChild(odds); side.appendChild(nm); side.appendChild(face); }
      names.appendChild(side);
    });
    var vs = document.createElement("i");
    vs.className = "h2hvs";
    vs.innerHTML = '<svg viewBox="0 0 26 22" aria-hidden="true"><use href="#vs"/></svg>';
    names.appendChild(vs);
    /* the whole name line goes above the row, so the count boxes flank only the bar */
    row.parentNode.insertBefore(names, row);
    /* the label goes too: the bar with a name under each end says what it is */
    head.remove();
    dressRecords(card);
  }


  /* ---- the fixture card, laid out as the mock draws it ------------------
     notes/mocks/mock_game.py is the drawing; this seats the card's own nodes
     into that shape. Every node the live code holds -- .gml, .ptdside,
     .ptdbtn, .trkbox, .h2hqb, .h2hbar -- is the same node it was, so nothing
     downstream has to know (Jose, Sep 21, 2026). */
  /* A man the board has no picture of reads as the man, not as a hole: his
     initials over his club's own colour and mark. The silhouette is a data:
     URI served with a 200, so waiting for an error never fired -- the source
     itself is what is asked (Jose, Sep 22, 2026: "if the image is not there
     we're putting initials"). A side with no passer named carries the club's
     letters, which is the only name that side has. */
  function lettersIfNoFace(face, card, which, ab, forced) {
    if (!face || !face.parentNode) return;
    var src = face.getAttribute("src") || "";
    if (!forced && src.indexOf("data:") !== 0) return;
    if (face.parentNode.querySelector(".gnoface")) { face.remove(); return; }
    var who = which === "l" ? card.dataset.lqb : card.dataset.rqb;
    var bits = String(who || "").trim().split(/\s+/).filter(Boolean);
    var ini = bits.slice(0, 2).map(function (w) { return w.charAt(0); })
                  .join("").toUpperCase();
    var box = document.createElement("span");
    box.className = "gnoface";
    box.textContent = ini || String(ab || "").toUpperCase() || "?";
    face.parentNode.insertBefore(box, face);
    face.remove();
  }
  /* ---- the bout card, in the same shape as a fixture card ----
     No clubs, so the sides take the corners, red and blue. His number rides
     the outer corner, or NR where the panel ranks him nowhere; his record
     goes under his name; the division stands in full under the eye and the
     play mark; and the strip counts the price to win, then KO, SUB and DEC.
     The foot is the fight's own rail rather than a yard bar
     (notes/mocks/mock_mma.py; the design note, Sep 21, 2026). */
  var FRANK = {};
  fetch("fighter_ranks.json").then(function (r) { return r.json(); })
    .then(function (j) { FRANK = j || {}; if (typeof paintAll === "function") paintAll(); })
    .catch(function () { FRANK = {}; });
  var DIVNAME = { FLW: "FLYWEIGHT", BW: "BANTAMWEIGHT", FW: "FEATHERWEIGHT",
                  LW: "LIGHTWEIGHT", WW: "WELTERWEIGHT", MW: "MIDDLEWEIGHT",
                  LHW: "LIGHT HEAVYWEIGHT", HW: "HEAVYWEIGHT",
                  SW: "STRAWWEIGHT", CW: "CATCHWEIGHT",
                  /* boxing's own divisions (build/boxing.py) */
                  CRW: "CRUISERWEIGHT", BRW: "BRIDGERWEIGHT", SMW: "SUPER MIDDLEWEIGHT",
                  SWW: "SUPER WELTERWEIGHT", SLW: "SUPER LIGHTWEIGHT", SFW: "SUPER FEATHERWEIGHT",
                  SBW: "SUPER BANTAMWEIGHT", SFLW: "SUPER FLYWEIGHT", LFLW: "LIGHT FLYWEIGHT",
                  MINW: "MINIMUMWEIGHT" };
  function boutRanked(name) { return FRANK[String(name || "").trim().toLowerCase()]; }
  /* "TBA", "TBD", "Opponent TBA" -- a side the promotion has not named */
  function isTBA(name) {
    return /\bTB[AD]\b/i.test(String(name || "")) || !String(name || "").trim();
  }
  function boutRank(name) {
    var f = boutRanked(name);
    if (!f) return "NR";
    return f.r === "C" ? "C" : "#" + f.r;
  }
  function boutDiv(card) {
    var ab = String(card.dataset.wt || "").split("\u00b7")[0].trim().toUpperCase();
    var full = DIVNAME[ab] || ab;
    if (!full) return "";
    /* a women's bout says so, and the panel's own division is what says it --
       there is no flag on the card to read (Jose, Sep 21, 2026) */
    var a = boutRanked(card.dataset.lf), b = boutRanked(card.dataset.rf);
    var women = (a && a.w) || (b && b.w) || ab === "SW";
    return (women ? "W-" : "") + full;
  }
  /* a price from the fight's own props, with the book's id on it so a tap
     sticks the way every other chip's does */
  function fchip(pair) {
    var v = pair && pair[0], oid = pair && pair[1];
    if (!v) {
      var g = document.createElement("span");
      g.className = "ghost";
      return g;
    }
    var b = document.createElement("button");
    b.className = "price" + longCls(v);
    b.type = "button";
    if (oid) b.dataset.oid = oid;
    b.dataset.odds = v;
    b.textContent = v;
    return b;
  }
  function boutRow(left, markHtml, right, tag) {
    var row = document.createElement("div");
    row.className = "gline";
    var a = document.createElement("span"); a.className = "gh2h";
    var m = document.createElement("i"); m.className = "gmk";
    m.innerHTML = markHtml + (tag ? '<em class="grn">' + tag + "</em>" : "");
    var b = document.createElement("span"); b.className = "gh2h";
    if (left) a.appendChild(left);
    if (right) b.appendChild(right);
    row.appendChild(a); row.appendChild(m); row.appendChild(b);
    return row;
  }
  var MKO = '<svg viewBox="0 0 50 50" aria-hidden="true"><use href="#mko"/></svg>';
  var MSUB = '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#msub"/></svg>';
  var MDEC = '<svg viewBox="0 0 66 32" aria-hidden="true"><use href="#mdec"/></svg>';
  var MLMK = '<img src="ico/moneyline.svg?v=2" alt="" width="21" height="9">';
  /* His record, once, on the head. The board re-renders a card's name block
     after it has been laid out -- the next event's cards most of all -- and
     each pass puts a fresh copy back beside his surname, so this runs on
     every paint rather than once (Jose, Sep 22, 2026). */
  function seatRecord(card) {
    if (!card || !card.classList.contains("gcard--bout")) return;
    var head = card.querySelector(".ghead--fight");
    if (!head) return;
    ["l", "r"].forEach(function (w) {
      var side = head.querySelector(".gside--" + w);
      if (!side) return;
      var recs = [].slice.call(side.querySelectorAll(".frec"));
      var held = head.querySelector(":scope > .frec--" + w);
      var keep = held || recs.shift();
      recs.forEach(function (x) { x.remove(); });
      /* the slot stands even where there is no record to put in it, so a bout
         still to be confirmed is laid out like every other one */
      if (!keep) {
        keep = document.createElement("i");
        keep.className = "frec";
      }
      var who1 = w === "l" ? card.dataset.lf : card.dataset.rf;
      if (isTBA(who1)) keep.textContent = "";
      keep.classList.add("frec--" + w);
      if (keep.parentNode !== head) head.appendChild(keep);
    });
  }
  window.seatRecord = seatRecord;
  function layoutBout(card) {
    if (!card || !card.dataset.bout || card.dataset.v3 === "1") return;
    var head = card.querySelector(".ghead--fight");
    if (!head) return;
    var sides = head.querySelectorAll(":scope > .gteam");
    if (sides.length !== 2) return;
    card.dataset.v3 = "1";
    card.classList.add("gcard--v3", "gcard--bout");

    /* The champion takes the left, the way the promotion names the bout: UFC
       331 is Van vs. Pantoja 2, and ESPN handed the challenger first
       (Jose, Sep 22, 2026). The names and the ids move with the pictures so
       everything that reads them after -- the settle, the faces, the ranks --
       still agrees. */
    /* The promotion names its own main event, and that naming is the order:
       "331: Van vs. Pantoja 2" puts Van on the left, "FN: Rosas Jr. vs.
       Barcelos" puts Rosas there, whoever holds the belt. The bill's heading
       carries the name, so it is read off the board itself (Jose, Sep 22,
       2026: "ESPN has him on the left too, he's the A side"). Any bout the
       title does not name keeps the order it came in. */
    var evName = "";
    var bill0 = card.closest(".bill");
    var hd0 = bill0 && bill0.previousElementSibling;
    var ev0 = hd0 && hd0.querySelector(".slotev");
    if (ev0) evName = ev0.textContent || "";
    var namedFirst = "";
    var mm = /(?::\s*)?([^:]+?)\s+vs\.?\s+/i.exec(evName);
    if (mm) namedFirst = mm[1].trim().toLowerCase();
    var surn = function (n) {
      return String(n || "").trim().split(/\s+/).filter(function (w) {
        return !/^(jr\.?|sr\.?|ii|iii|iv)$/i.test(w);
      }).pop() || "";
    };
    var lsur = surn(card.dataset.lf).toLowerCase(), rsur = surn(card.dataset.rf).toLowerCase();
    var titleWantsRight = !!namedFirst && rsur && namedFirst.indexOf(rsur) >= 0 &&
                          !(lsur && namedFirst.indexOf(lsur) >= 0);
    var lr = boutRanked(card.dataset.lf), rr = boutRanked(card.dataset.rf);
    var swapped = false;
    if (titleWantsRight) {
      swapped = true;
      card.dataset.flip = "1";
      /* the sheet is titled the way the card reads, and the way the promotion
         names the bout -- UFC 331 is Van vs. Pantoja 2, and the title was
         built from the order the data arrived in (Jose, Sep 22, 2026) */
      var ttl = card.querySelector(".sheet__title");
      if (ttl && ttl.textContent.indexOf(" v ") > 0) {
        var two = ttl.textContent.split(" v ");
        ttl.textContent = two[1].trim() + " v " + two[0].trim();
      }
      head.insertBefore(sides[1], sides[0]);
      sides[0].classList.remove("gteam--flip");
      sides[1].classList.add("gteam--flip");
      var swap = [card.dataset.lf, card.dataset.rf, card.dataset.lfid, card.dataset.rfid];
      card.dataset.lf = swap[1]; card.dataset.rf = swap[0];
      card.dataset.lfid = swap[3]; card.dataset.rfid = swap[2];
      sides = head.querySelectorAll(":scope > .gteam");
    }

    var strip = document.createElement("div");
    strip.className = "gmid";
    head.insertBefore(strip, sides[1]);

    var when = card.querySelector(".gwhen");
    if (when) { when.classList.add("gtop"); strip.appendChild(when); }
    /* a finished bout says so on its top line, evenly spaced with the eye, the
       rewind and the play mark -- where there is no rewind it simply stands in
       its place (Jose, Sep 22, 2026) */
    var wt = document.createElement("div");
    wt.className = "gweight";
    wt.textContent = boutDiv(card);
    if (wt.textContent.length > 12) wt.dataset.long = "1";
    strip.appendChild(wt);

    var stack = document.createElement("div");
    stack.className = "gstack";
    strip.appendChild(stack);

    /* the price to win keeps the nodes it already had, so a mark on it holds */
    var mls = head.querySelectorAll(":scope > .gteam > .gml");
    if (mls.length === 2) stack.appendChild(boutRow(mls[0], MLMK, mls[1]));
    var pr = (typeof FPROPS === "object" && FPROPS[card.dataset.bout]) || {};
    /* the prices are seated in the order the data names the two men, so when
       the champion is moved to the left his prices move with him -- otherwise
       every swapped bout wears the other man's numbers
       (Jose, Sep 22, 2026: "the odds are wrong") */
    var A = swapped ? 1 : 0, B = swapped ? 0 : 1;
    /* boxing has no submissions: its card carries KO and DEC only */
    var boxing = /^zb-/.test(card.dataset.event || "");
    [["ko", MKO, "KO"], ["sub", MSUB, "SUB"], ["dec", MDEC, "DEC"]].forEach(function (k) {
      if (boxing && k[0] === "sub") return;
      var got = pr[k[0]] || [];
      stack.appendChild(boutRow(fchip(got[A]), k[1], fchip(got[B]), k[2]));
    });

    /* his corner, his number, his name over the foot with his record under it */
    [["l", sides[0]], ["r", sides[1]]].forEach(function (p) {
      var side = p[1];
      side.classList.add("gside", "gside--" + p[0]);
      side.style.setProperty("--hue", p[0] === "l" ? "#3a1418" : "#0e1c33");
      /* our own picture of him, which is a cutout on a transparent ground --
         the /face/ function answers with ESPN's square photograph, and that
         covers the whole half and hides the corner he is fighting out of
         (Jose, Sep 22, 2026: mock-mma-states.png) */
      var pic = side.querySelector("img.ffab");
      var fid = p[0] === "l" ? card.dataset.lfid : card.dataset.rfid;
      /* ...but never for a man we have written down as having no picture.
         /faces/ is a real directory, so Pages answers a missing file under it
         with the web page itself, 200 and all, and _headers marks it
         immutable for a month -- the browser then draws that web page under
         his name on every load until the month is out. That is the whole
         reason the /face/ function exists. Two TBA placeholders were asking
         for one (Jose, Sep 22, 2026). */
      /* a man we hold no picture of takes the silhouette here too, rather
         than the bare corner (Jose, Sep 22, 2026) */
      if (pic && (!/^\d+$/.test(String(fid || "")) || NOPIC[String(fid)])) {
        if ((pic.getAttribute("src") || "").indexOf("unknown") < 0) {
          pic.removeAttribute("onerror");
          pic.dataset.next = "";
          pic.setAttribute("src", UNKNOWN);
          pic.classList.add("ffab--un");
        }
      } else if (pic && /^\d+$/.test(String(fid || ""))) {
        var mine = "faces/mma/" + fid + ".png";
        if ((pic.getAttribute("src") || "").indexOf(mine) < 0) {
          var was = pic.getAttribute("src") || "";
          pic.dataset.next = [was, pic.dataset.next || ""].filter(Boolean).join("|");
          pic.setAttribute("src", mine);
        }
      }
      /* his record rides the top of his own half, opposite his number
         (Jose, Sep 22, 2026) */
      /* the head, not his half: his half is masked at its inner edge and the
         record sits in that fade, which washed it out
         (Jose, Sep 22, 2026: "make sure its above the blur") */
      /* a card can carry his record twice -- once on the club line and once
         beside his name -- and moving only the first left the other sitting
         on his surname: MONTENEGRO6-3 (Jose, Sep 22, 2026). One is kept and
         seated on the head; every other copy goes. */
      var recs = [].slice.call(side.querySelectorAll(".frec"));
      var rec0 = head.querySelector(":scope > .frec--" + p[0]) || recs.shift();
      recs.forEach(function (x) { x.remove(); });
      if (rec0) {
        rec0.classList.add("frec--" + p[0]);
        if (rec0.parentNode !== head) head.appendChild(rec0);
      }
      if (!side.querySelector(".gdiv")) {
        var who0 = p[0] === "l" ? card.dataset.lf : card.dataset.rf;
        var rk = document.createElement("i");
        rk.className = "gdiv";
        /* a bout with nobody named yet keeps both corners, and says nothing in
           them until the fight is confirmed (Jose, Sep 22, 2026) */
        rk.textContent = isTBA(who0) ? "" : boutRank(who0);
        side.appendChild(rk);
      }
    });

    boutRail(card, head);
    if (typeof markSaved === "function") markSaved(card);
    seatEye(card);
  }
  window.layoutBout = layoutBout;
  /* the fight's own rail across the foot, a stretch a round. A bout whose
     length arrives with prices.json was laid out before it and drawn at
     three: a five-round main event showed R1-R3 (Jose, Sep 26, 2026:
     "main event is only 3 rounds?"), so a rail with nothing on it yet is
     drawn again once the length it was drawn at is wrong */
  function boutRail(card, head) {
    var rounds = parseInt((FPROPS[card.dataset.bout] || {}).rounds, 10) || 3;
    var old = card.querySelector(".frail");
    if (old && +old.dataset.n !== rounds && !old.querySelector(".frail__fill, .fend")) {
      head = old.previousSibling;
      old.parentNode.removeChild(old);
      old = null;
    }
    if (old || !head) return;
    var rail = document.createElement("div");
    rail.className = "gbody frail";
    rail.dataset.n = rounds;
    var bar = '<div class="frail__bar">';
    for (var k = 1; k < rounds; k++) {
      bar += '<i class="rtick" style="left:' + (100 * k / rounds).toFixed(2) + '%"></i>';
    }
    for (var n = 1; n <= rounds; n++) {
      bar += '<em class="rnum" style="left:' + (100 * (n - 0.5) / rounds).toFixed(2) + '%">' +
             '<svg viewBox="0 0 26 22" aria-hidden="true"><use href="#r' + n + '"/></svg></em>';
    }
    rail.innerHTML = bar + "</div>";
    head.parentNode.insertBefore(rail, head.nextSibling);
  }
  window.boutRail = boutRail;
  /* The club's record in the top corner, across from the house or the plane.
     It is seated on every paint, not once at layout: the record is read from
     the ledger, the ledger arrives after the first cards are drawn, and a card
     laid out before it landed kept no record and never tried again -- which is
     why some cards carried it and others did not, and why it always looked
     right in a slow test (Jose, Sep 22, 2026). */
  /* clubRec walks every week of the ledger, and seating runs once a card --
     288 cards was 288 walks of the same rows. The answer is held until the
     ledger itself changes. */
  var RECMEMO = null, RECOF = null;
  function recNow() {
    if (typeof clubRec !== "function" || typeof LEDGER === "undefined" || !LEDGER) return {};
    if (RECOF !== LEDGER) { RECOF = LEDGER; RECMEMO = clubRec(); }
    return RECMEMO || {};
  }
  /* The same red cross the ledger draws, on the fixture card beside the
     passer's own name. One mark, one source -- the wire -- so a man carries it
     from the season card to the NFL page to the week, and loses it everywhere
     the moment ESPN lifts him (Jose, Sep 22, 2026). Seated on every paint
     rather than built once, because the wire lands after the cards do. */
  /* a name and its price on one line inside his half: the name gives up a
     point of type at a time until the line fits, never its letters */
  function fitName(nm) {
    var tx = nm && nm.querySelector(".h2hnmtx");
    if (!tx) return;
    tx.style.fontSize = "";
    nm.style.paddingLeft = nm.style.paddingRight = "";
    /* his half runs under the middle column, so the room is only what shows
       beside it, and the line is centered in that */
    /* the panel fades out across its inner 14% (its mask), so a price put
       there fades with it: the line keeps to the solid 86% */
    var gs = nm.closest(".gside");
    if (gs) {
      var nr = nm.getBoundingClientRect(), gr = gs.getBoundingClientRect(), solid = gr.width * 0.86;
      if (gs.classList.contains("gside--l")) nm.style.paddingRight = Math.max(0, nr.right - (gr.left + solid)) + "px";
      else nm.style.paddingLeft = Math.max(0, (gr.right - solid) - nr.left) + "px";
    }
    var room = nm.clientWidth - (parseFloat(nm.style.paddingLeft) || 0) - (parseFloat(nm.style.paddingRight) || 0) - 8,
        fs = parseFloat(getComputedStyle(tx).fontSize) || 17;
    var line = function () {
      var w = 0;
      [].forEach.call(nm.children, function (k) {
        var cs = getComputedStyle(k);
        if (cs.display === "block" || cs.position === "absolute" || k.classList.contains("gschool")) return;
        w += k.getBoundingClientRect().width + (parseFloat(cs.marginLeft) || 0) + (parseFloat(cs.marginRight) || 0);
      });
      return w;
    };
    while (room > 0 && line() > room && fs > 10) { fs -= 1; tx.style.fontSize = fs + "px"; }
  }
  function seatHurt(card) {
    if (!card || card.dataset.v3 !== "1" || card.dataset.bout) return;
    [["l", card.dataset.lqbid], ["r", card.dataset.rqbid]].forEach(function (p) {
      var nm = card.querySelector(".h2hside--" + p[0] + " .h2hnm");
      if (!nm) return;
      var had = nm.querySelector(".hurt");
      var want = typeof hurtMark === "function" ? hurtMark(p[1]) : "";
      /* lifted means gone: the mark is rebuilt from the wire each pass rather
         than left behind, so a clearance clears it */
      if (!want) { if (had) had.remove(); return; }
      if (had && had.dataset.said === want) return;
      if (had) had.remove();
      nm.insertAdjacentHTML("beforeend", want);
      var mk = nm.querySelector(".hurt");
      if (mk) mk.dataset.said = want;
    });
  }
  window.seatHurt = seatHurt;
  /* The party border on the birthday man's half. birthdays.json is keyed by
     game and then by his ESPN id, and it already picks the right game -- the
     first he plays on or after the day -- so the page only has to ask whether
     this card is that game. Re-seated on every paint because the file lands
     after the cards are drawn. */
  var BIRTHDAYS = {};
  function seatBday(card) {
    if (!card || card.dataset.v3 !== "1" || card.dataset.bout) return;
    var men = (BIRTHDAYS.qb || {})[card.dataset.espn] || {};
    [["l", card.dataset.lqbid], ["r", card.dataset.rqbid]].forEach(function (p) {
      var side = card.querySelector(".gside--" + p[0]);
      if (!side) return;
      /* set from the file each pass, never left behind: a week that moves or
         a man swapped off the card loses it by himself */
      side.classList.toggle("gside--bday", !!men[String(p[1])]);
    });
  }
  window.seatBday = seatBday;
  /* Each league's own record, from its own source. clubRec() counts the NFL
     ledger, and a college card carries letters the NFL uses too -- CIN, HOU
     and MIA -- so Miami read the Dolphins' 0-2 instead of its own 2-0 (Jose,
     Sep 22, 2026). College is read per week from records.json, which
     dressRecords() has already put on the card, so the letters are never what
     decides: the league is. */
  function recFor(card) {
    if (card.dataset.lg === "nfl") return recNow();
    if (card.dataset.lg !== "college-football") return {};
    var id = card.dataset.espn;
    for (var i = 0; i < CFB.length; i++) {
      if (String(CFB[i][1]) === id) {
        return ((RECORDS || {}).ncaaf || {})[String(CFB[i][0])] || {};
      }
    }
    return {};
  }
  function seatClubRec(card) {
    if (!card || card.dataset.v3 !== "1" || card.dataset.bout) return;
    if (card.dataset.lg !== "nfl" && card.dataset.lg !== "college-football") return;
    var head = card.querySelector(":scope > .ghead");
    if (!head) return;
    var rec = recFor(card);
    ["l", "r"].forEach(function (w) {
      var side = head.querySelector(".gside--" + w);
      if (!side) return;
      var ab = ((side.querySelector("img.glogo") || {}).alt || "").trim();
      var wl = rec[ab];
      /* the ledger hands back a pair, records.json a written record */
      var said = !wl ? "" : (typeof wl === "string" ? wl : wl[0] + "-" + wl[1]);
      var el = head.querySelector(":scope > .grec--" + w) || side.querySelector(".grec");
      if (!el) {
        if (!said) return;
        el = document.createElement("small");
        el.className = "grec";
      }
      /* written every pass, not only the first: a card seated before the
         ledger landed held an empty corner, and one seated at halftime holds
         last week's count until this one is read again */
      if (said) el.textContent = said;
      el.classList.add("grec--top", "grec--" + w);
      if (el.parentNode !== head) head.appendChild(el);
    });
  }
  window.seatClubRec = seatClubRec;
  function layoutV3(card) {
    if (!card || card.dataset.v3 === "1") return;
    if (card.dataset.lg !== "nfl" && card.dataset.lg !== "college-football") return;
    var head = card.querySelector(":scope > .ghead");
    var sides = head ? head.querySelectorAll(":scope > .gteam") : [];
    var names = card.querySelector(".h2hnames");
    if (!head || sides.length !== 2 || !names) return;
    card.dataset.v3 = "1";
    card.classList.add("gcard--v3");
    var bar = card.querySelector(".h2hx");

    var strip = document.createElement("div");
    strip.className = "gmid";
    head.insertBefore(strip, sides[1]);

    /* the eye, the clock and the play mark, on one line at the head of the
       strip. seatEye may not have run yet, so they are gathered here rather
       than waiting for it (Jose, Sep 21, 2026: "I told you where it goes") */
    var when = card.querySelector(".gwhen");
    if (!when) {
      when = document.createElement("span");
      when.className = "gwhen";
      var clock = card.querySelector(".gtime");
      if (clock) clock.parentNode.insertBefore(when, clock);
    }
    when.classList.add("gtop");
    /* the card does not say when it kicks off -- the row's own heading does
       (the design note, Sep 21, 2026: "No kickoff time -- it is already at
       the top of the day") */
    var eye = card.querySelector(".ghide"), clock2 = card.querySelector(".gtime");
    var watch = card.querySelector(".gwatch");
    if (eye) when.insertBefore(eye, when.firstChild);
    if (clock2 && clock2.parentNode !== when) when.appendChild(clock2);
    if (watch) when.appendChild(watch);
    strip.appendChild(when);
    seatEye(card);
    if (typeof seatWatch === "function") seatWatch(card);

    var stack = document.createElement("div");
    stack.className = "gstack";
    strip.appendChild(stack);

    /* the club price, on its own line under the eye and the play mark */
    var mls = head.querySelectorAll(":scope > .gteam > .gml");
    if (mls.length === 2) {
      var row = document.createElement("div");
      row.className = "gline";
      var a = document.createElement("span"); a.className = "gh2h"; a.appendChild(mls[0]);
      var m = document.createElement("i"); m.className = "gmk";
      m.innerHTML = '<img src="ico/moneyline.svg?v=2" alt="" width="21" height="9">';
      var b = document.createElement("span"); b.className = "gh2h"; b.appendChild(mls[1]);
      row.appendChild(a); row.appendChild(m); row.appendChild(b);
      stack.appendChild(row);
    }

    /* a college card already carries its rushing section, marked ATD rather
       than by class -- taking it for a second passing pair drew four ball
       rows where the mock draws two (Jose, Sep 22, 2026) */
    card.querySelectorAll('.ptdx[data-kind="ATD"]').forEach(function (sec) {
      sec.classList.add("ptdx--run");
    });
    /* the rushing row stands whether a board has priced it or not */
    if (!card.querySelector(".ptdx--run")) {
      var run = document.createElement("div");
      run.className = "ptdx ptdx--v2 ptdx--balls ptdx--run";
      run.dataset.scale = "2"; run.dataset.kind = "ATD";
      run.innerHTML = '<div class="ptdrow">' +
        '<div class="ptdside ptdside--l"><span class="ptdbtn ptdbtn--n1">' + GHOST + '</span></div>' +
        '<span class="trkbox ptdcount">0</span><span class="trkbox ptdcount">0</span>' +
        '<div class="ptdside ptdside--r"><span class="ptdbtn ptdbtn--n1">' + GHOST + '</span></div></div>';
      head.appendChild(run);
    }
    /* each section keeps its own .ptdside -- everything that reads a rung
       expects that -- and the mark is drawn once a rung, down the middle */
    var secs = [].slice.call(card.querySelectorAll(".ptdx"));
    secs.sort(function (a, b) {
      return (a.classList.contains("ptdx--run") ? 1 : 0) -
             (b.classList.contains("ptdx--run") ? 1 : 0);
    });
    secs.forEach(function (sec) {
      stack.appendChild(sec);
      var prow = sec.querySelector(".ptdrow");
      if (!prow || prow.querySelector(".gvmid")) return;
      var runrow = sec.classList.contains("ptdx--run");
      var left = prow.querySelector(".ptdside--l");
      /* the rushing row is one rung and only ever one: a board that prices a
         second one is not drawn (Jose, Sep 21, 2026: "we don't do two rushing
         touchdowns"). Passing takes as many rungs as it has chips. */
      if (runrow) {
        prow.querySelectorAll(".ptdside").forEach(function (sd) {
          sd.querySelectorAll(".ptdbtn").forEach(function (btn, i) { btn.hidden = i > 0; });
        });
      }
      var rungs = left ? left.querySelectorAll(".ptdbtn:not([hidden])").length : 0;
      if (!rungs) rungs = 1;
      var mid = document.createElement("span");
      mid.className = "gvmid";
      var out = "";
      for (var i = 1; i <= rungs; i++) {
        /* the rung reads either side of its mark, so the row is even
           (Jose, Sep 21, 2026) */
        out += '<i class="gmk">' + (runrow ? RUSHSVG : BALLSVG) +
               '<em class="grn">' + i + '+</em></i>';
      }
      mid.innerHTML = out;
      prow.insertBefore(mid, prow.querySelector(".ptdside--r"));
    });

    /* each passer takes his own side, with his club's record under his name */
    [["l", sides[0]], ["r", sides[1]]].forEach(function (p) {
      var mine = names.querySelector(".h2hside--" + p[0]);
      if (mine) p[1].appendChild(mine);
      /* his head-to-head price rides his name, on the side toward the middle,
         and the bar takes the whole foot (Jose, Sep 25, 2026: "move the h2h
         to the right side of the qb name ... extend the bar to the full
         width") */
      var odds = mine && mine.querySelector(".h2hodds");
      var nm0 = mine && mine.querySelector(".h2hnm");
      if (odds && nm0) {
        /* the name in its own span, so a long one can shrink to fit beside
           the price rather than push it off the card (Grunkemeyer) */
        var tx0 = nm0.firstChild;
        if (tx0 && tx0.nodeType === 3) {
          var tx = document.createElement("span");
          tx.className = "h2hnmtx";
          nm0.insertBefore(tx, tx0);
          tx.appendChild(tx0);
        }
        if (p[0] === "l") nm0.insertBefore(odds, nm0.childNodes[1] || null);
        else nm0.insertBefore(odds, nm0.firstChild);
        requestAnimationFrame(function () { fitName(nm0); });
      }
      var lg0 = p[1].querySelector("img.glogo");
      var ab = (lg0 || {}).alt || "";
      /* his record sits beside his name; his club or school goes under it, and
         on a college card the AP number rides in front of the school in gold.
         The school used to be written OVER the record, which lost the record
         and left the NFL card with no club at all
         (Jose, Sep 22, 2026: "I don't see team underneath the name and then
         add their record next to the name to the right of the name") */
      /* his name, and under it his club with his record in brackets after it:
         Purdie / LIB (1-0). A college side ranked by the AP carries its number
         in gold in front of the school (Jose, Sep 22, 2026) */
      /* His club's record rides the top corner, across from the house or the
         plane, the way a fighter's does. His name stands alone at the foot of
         his half; a college card keeps the school under it, an NFL card does
         not (Jose, Sep 22, 2026). */
      var nm = mine && mine.querySelector(".h2hnm");
      var college = card.dataset.lg === "college-football";
      /* written again on every paint: the rankings file lands after the
         first cards are drawn, and a school line made before it never got
         its number (Jose, Sep 26, 2026: "some have them, some don't") */
      if (college && nm && ab) {
        var r = RANK[ab];
        var sch = nm.querySelector(".gschool");
        if (!sch) { sch = document.createElement("small"); sch.className = "gschool"; nm.appendChild(sch); }
        var want = (r ? '<em class="grank">#' + r + "</em> " : "") + ab;
        if (sch.innerHTML !== want) sch.innerHTML = want;
      }
      /* (the price stays by the name on a college card too, the same as the
         NFL's -- Jose, Sep 26, 2026: "keep it consistent") */
      if (!college && nm) {
        var drop = nm.querySelector(".gschool");
        if (drop) drop.remove();
      }
      p[1].style.setProperty("--hue", cardHue(ab, card.dataset.lg));
      /* the side's own mark, whichever league it came from -- a club's sits in
         logos/nfl, a school's in logos/ncaa under its ESPN id. The fall back
         is the NFL's folder, so it is only taken on an NFL card: a college
         side with no mark would otherwise have drawn the club that shares its
         letters (Jose, Sep 22, 2026). */
      var src = lg0 && lg0.getAttribute("src");
      if (!src && card.dataset.lg === "nfl") src = "logos/nfl/" + ab.toLowerCase() + ".png";
      p[1].style.setProperty("--mark", src ? "url(" + src + ")" : "none");
      if (card.dataset.lg === "college-football") p[1].dataset.school = ab;
      p[1].classList.add("gside", "gside--" + p[0]);
      var home = (card.dataset.lhome === "1") === (p[0] === "l");
      var face = mine && mine.querySelector("img.qbface");
      /* only once the chain has given up -- faceChain retries past the cache
         first, and that retry is what usually wins */
      if (face) lettersIfNoFace(face, card, p[0], ab);
      var trav = document.createElement("i");
      trav.className = "gtrav";
      trav.innerHTML = '<svg viewBox="0 0 1024 1024" aria-hidden="true"><use href="#' +
        (home ? "schome" : "scaway") + '"/></svg>';
      p[1].appendChild(trav);
    });
    if (!names.querySelector(".h2hside")) names.remove();

    /* the yard bar across the foot, the VS fixed on its middle */
    if (bar) {
      bar.classList.add("gbody");
      head.parentNode.insertBefore(bar, head.nextSibling);
      var rail = bar.querySelector(".h2hbar");
      if (rail && !rail.querySelector(".gvs")) {
        var vs = document.createElement("i");
        vs.className = "gvs";
        vs.innerHTML = '<svg viewBox="0 0 26 22" aria-hidden="true"><use href="#vs"/></svg>';
        rail.appendChild(vs);
      }
    }
    stateV3(card);
  }

