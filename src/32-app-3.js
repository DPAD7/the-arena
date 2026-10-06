  function toDecOdds(o) {
    if (!o) return null;
    var v = parseInt(String(o).replace(/−/g, "-").replace("+", ""), 10);
    if (isNaN(v) || !v) return null;
    return 1 + (v > 0 ? v / 100 : 100 / -v);
  }
  function toUsOdds(d) {
    if (!d || d <= 1) return "";
    return d >= 2 ? "+" + Math.round((d - 1) * 100) : "−" + Math.round(100 / (d - 1));
  }
  /* the rung he reached, at the price of that rung */
  function rungPrice(list, hit, cap) {
    if (!hit) return null;
    var want = Math.min(hit, cap);
    for (var i = want; i >= 1; i--) {
      var v = (list || [])[i - 1];
      if (v) return { odds: v, rung: i };
    }
    return null;
  }
  /* ---- what counts, and when ----
     A touchdown cannot be taken back by the rest of the game: a man on two
     has won 2+ whatever happens next, and the week's ladder stops at 2, so
     the week's touchdown legs are settled the moment they land. The season's
     ladder runs to 5+, so it keeps climbing as he throws, which is the same
     thing said louder.

     The club result and the head to head are the two that can still turn, so
     they wait for the whistle -- and they do that by themselves, because
     neither is ever "W" until the game is post (Jose, Sep 20, 2026: "it can
     happen as the game is going, then 30 seconds after"). */
  function cardFor(r, capped) {
    var legs = [], dec = 1, any = false;
    var ladder = !capped && r.rungs && r.rungs.some(function (x) { return x; });
    var ptd = rungPrice(ladder ? r.rungs : (r.odds[0] || []), r.ptd, ladder ? 5 : 2);
    if (ptd) { legs.push({ what: ptd.rung + "+ PTD", odds: ptd.odds }); dec *= toDecOdds(ptd.odds); any = true; }
    var atd = rungPrice(r.odds[1] || [], r.atd, 2);
    if (atd) { legs.push({ what: atd.rung + "+ ATD", odds: atd.odds }); dec *= toDecOdds(atd.odds); any = true; }
    if (r.h2h === "W" && r.odds[2]) { legs.push({ what: "H2H", odds: r.odds[2] }); dec *= toDecOdds(r.odds[2]); any = true; }
    if (r.ml === "W" && r.odds[3]) { legs.push({ what: "ML", odds: r.odds[3] }); dec *= toDecOdds(r.odds[3]); any = true; }
    return { legs: legs, dec: any ? dec : 0, priced: hasPrice(r) };
  }
  function hasPrice(r) {
    var o = r.odds || [];
    return !!((o[0] || []).some(Boolean) || (o[1] || []).some(Boolean) || o[2] || o[3] ||
              (r.rungs || []).some(Boolean));
  }
  function moneyRows() {
    if (!LEDGER) return [];
    var read = function (r) {
      return { name: r[0], club: r[1], id: r[2], ptd: r[3], atd: r[4], h2h: r[5], ml: r[6],
               h2hw: r[5] === "W" ? 1 : 0, mlw: r[6] === "W" ? 1 : 0,
               yds: r[7] || 0, game: r[8] || "",
               odds: r[11] || [[null, null], [null, null], null, null],
               carded: r[12] !== 0, rungs: r[13] || [], fin: r[14] === 1 };
    };
    if (formWeek !== "season") {
      var wk = (LEDGER[formWeek] || []).map(read);
      layLive(wk);
      return wk.map(function (r) {
        var c = cardFor(r, true);
        r.legs = c.legs; r.dec = c.dec; r.priced = c.priced; r.units = c.dec ? c.dec : 0;
        return r;
      });
    }
    var by = {};
    Object.keys(LEDGER).forEach(function (w) {
      var all = LEDGER[w].map(read);
      layLive(all);
      all.forEach(function (r) {
        var c = cardFor(r);
        var m = by[r.id] || (by[r.id] = { name: r.name, club: r.club, id: r.id, ptd: 0, atd: 0,
                                          h2hw: 0, mlw: 0, legs: [], units: 0, weeks: 0, played: 0,
                                          priced: false, agg: true });
        m.club = r.club; m.ptd += r.ptd; m.atd += r.atd; m.weeks++;
        m.h2hw += r.h2hw; m.mlw += r.mlw;
        m.legs = m.legs.concat(c.legs);
        /* a week that has not been played is not a week he lost: the row sits
           at nothing until the game settles, and charging it a unit had Caleb
           Williams down one for Sunday's game on Friday (Jose, Sep 18, 2026) */
        var played = r.ml === "W" || r.ml === "L" || r.h2h === "W" || r.h2h === "L" ||
                     r.ptd > 0 || r.atd > 0 || r.yds > 0;
        m.units += c.dec ? c.dec - 1 : (c.priced && played ? -1 : 0);
        if (played) m.played++;
        m.priced = m.priced || c.priced;
      });
    });
    return Object.keys(by).map(function (k) { return by[k]; });
  }
  var MBALL = '<i class="fmk fmk--ball">' + BALLSVG + "</i>";
  var MRUN = '<i class="fmk fmk--run">' + RUSHSVG + "</i>";
  var MVS = '<i class="fmk fmk--vs"><svg viewBox="0 0 26 22" aria-hidden="true"><use href="#vs"/></svg></i>';
  var MML = '<img class="fmk--ml" src="ico/moneyline.svg" alt="Moneyline" width="34" height="13">';
  function MTIMES(mark, v) {
    return '<span class="fgrp' + (v ? "" : " fgrp--zero") + '">' + mark + '<em>\u00d7' + (v || 0) + '</em></span>';
  }

  /* ---- the season card ----
     One card a man: his picture on the club's own colour with the club's mark
     behind him, his marks down the right, his name laid over the foot. The
     record is the club's, counted once a game -- two passers in the same game
     cannot both bank the win (Jose, Sep 21, 2026). */
  var HUE = {ARI:"#a40227",ATL:"#a71930",BAL:"#29126f",BUF:"#00338d",CAR:"#0085ca",CHI:"#0b1c3a",CIN:"#fb4f14",CLE:"#472a08",DAL:"#002a5c",DEN:"#0a2343",DET:"#0076b6",GB:"#204e32",HOU:"#021018",IND:"#003b75",JAX:"#007487",KC:"#e31837",LAC:"#0080c6",LAR:"#003594",LV:"#000000",MIA:"#008e97",MIN:"#4f2683",NE:"#002a5c",NO:"#d3bc8d",NYG:"#003c7f",NYJ:"#115740",PHI:"#06424d",PIT:"#000000",SEA:"#002a5c",SF:"#aa0000",TB:"#bd1c36",TEN:"#4495d2",WSH:"#5a1414"};
  function sink(hex, by) {
    var n = parseInt(hex.slice(1), 16);
    var r = n >> 16, g = (n >> 8) & 255, b = n & 255;
    var f = function (c) { return Math.round(c * (1 - by) + 10 * by); };
    return "rgb(" + f(r) + "," + f(g) + "," + f(b) + ")";
  }
  function lumOf(hex) {
    var n = parseInt(hex.slice(1), 16);
    return (0.2126 * (n >> 16) + 0.7152 * ((n >> 8) & 255) + 0.0722 * (n & 255)) / 255;
  }
  function cardHue(club, lg) {
    /* The league picks the table, never the letters. HUE is the thirty-two
       NFL clubs; asking it first painted Miami's college card in the
       Dolphins' aqua, Houston's in the Texans' near-black and Cincinnati's in
       the Bengals' orange -- the same three letters, the same fault as the
       records (Jose, Sep 22, 2026: "if CFB mia, if NFL MIA, two different").
       A college card asks the schools only. */
    var school = lg === "college-football";
    var h = (school ? "" : HUE[club]) ||
            (typeof clubHue === "function" ? clubHue(club, lg) : "") || "#1a1d22";
    /* a club whose colour is all but black leaves the mark nothing to sit on */
    if (lumOf(h) < 0.07) {
      var n = parseInt(h.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255;
      var up = function (c) { return Math.round(c + (255 - c) * 0.16); };
      h = "#" + ((1 << 24) + (up(r) << 16) + (up(g) << 8) + up(b)).toString(16).slice(1);
    }
    return sink(h, 0.42);
  }
  /* the club's record for the season, one result a game */
  function clubRec() {
    var out = {}, seen = {};
    if (!LEDGER) return out;
    Object.keys(LEDGER).forEach(function (w) {
      LEDGER[w].forEach(function (r) {
        var club = r[1], key = club + "|" + r[8];
        if ((r[6] !== "W" && r[6] !== "L") || seen[key]) return;
        seen[key] = 1;
        var rec = out[club] || (out[club] = [0, 0]);
        if (r[6] === "W") rec[0]++; else rec[1]++;
      });
    });
    return out;
  }
  var VSMARK = '<svg viewBox="0 0 26 22" aria-hidden="true"><use href="#vs"/></svg>';
  var CHIPW = '<svg viewBox="0 0 26 22" aria-hidden="true"><rect x="1" y="1" width="24" height="20" rx="5" fill="#17c257"/><text x="13" y="16.4" text-anchor="middle" font-family="Barlow Condensed, Arial Narrow, sans-serif" font-weight="800" font-size="14" fill="#1c1c1e">W</text></svg>';
  var CHIPL = '<svg viewBox="0 0 26 22" aria-hidden="true"><rect x="1" y="1" width="24" height="20" rx="5" fill="#e2564d"/><text x="13" y="16.4" text-anchor="middle" font-family="Barlow Condensed, Arial Narrow, sans-serif" font-weight="800" font-size="14" fill="#1c1c1e">L</text></svg>';
  function qline(mark, label, n) {
    var dim = n ? "" : " ln--zero";
    return '<i class="lmk' + dim + '" title="' + label + '">' + mark + "</i>" +
           '<b class="lnum' + dim + '">' + n + "</b>";
  }
  /* ---- the picks: who was dragged into the eight, and how ---- */
  var PICKKEY = "arena.picks.v1";
  function loadPicks() { try { return JSON.parse(localStorage.getItem(PICKKEY) || "[]"); } catch (e) { return []; } }
  /* six picks, not eight (Jose, Sep 23, 2026: "move the QBs from 8 to 6") */
  /* three rows of six stand in the end zone (Jose, Sep 25, 2026) */
  /* twelve at most, two rows of six (Jose, Sep 28, 2026) */
  var MAXPICK = 12;
  function savePicks(p) { try { localStorage.setItem(PICKKEY, JSON.stringify(p.slice(0, MAXPICK))); } catch (e) {} }
  /* where the chips go, in the row's own coordinates: centered as a group on
     the squares' pitch, in the order they were picked */
  function pickSpots(slots, n) {
    var sq = slots.querySelectorAll("i"), row = slots.getBoundingClientRect();
    var a = sq[0].getBoundingClientRect(), b2 = sq[1].getBoundingClientRect();
    var w = a.width, h = a.height;
    /* six in one row, full size, all inside the back of the end zone: the
       pitch closes up until the row fits the far line, so on a phone they
       overlap a little rather than shrink or spill (Jose, Sep 23, 2026: "6
       inline") */
    var far = row.width * 0.84 - 8;                 /* the end zone's back line */
    /* rows of six, the first on the goal line and each next one stacked
       above it (Jose, Sep 25, 2026: "fit another row") */
    var per = 6, out = [];
    var t0 = (row.height - h) / 2;
    for (var i = 0; i < n; i++) {
      var r = Math.floor(i / per), inRow = Math.min(per, n - r * per), j = i - r * per;
      var pitch = Math.min(b2.left - a.left, inRow > 1 ? (far - w) / (per - 1) : 0);
      out.push({ left: row.width / 2 + (j - (inRow - 1) / 2) * pitch - w / 2, top: t0 - r * (h + 8), w: w, h: h });
    }
    return out;
  }
  /* the chips already in the row slide to their new places as the new one
     glides in, so nobody sits on anybody (Jose, Sep 23, 2026: "needs to
     simultaneously move over") */
  function shiftPicks(slots, n) {
    var spots = pickSpots(slots, n);
    slots.querySelectorAll(".fpick").forEach(function (c, i) {
      if (spots[i]) { c.style.left = spots[i].left.toFixed(1) + "px"; c.style.top = spots[i].top.toFixed(1) + "px"; }
    });
  }
  /* ---- the turf ----
     A field in perspective, drawn to the box it sits in: the end zone at the
     far end, the height of the pick row, then forty yards toward the reader
     with a line every five, the numbers every ten and the hash marks on
     every yard, in the dark slate the league's tracking charts use. */
  function drawTurf(wrap, slots) {
    var W = wrap.clientWidth, H = wrap.clientHeight;
    if (!W || !H) return;
    var ez = Math.max(40, slots.offsetHeight);
    var cx = W / 2, farH = W * 0.42, nearH = W * 0.66;   /* a wider far end: six picks stand in it */
    var half = function (y) { return farH + (nearH - farH) * (y / H); };
    /* yards from the back of the end zone: 0-10 is the end zone, 10-50 the field */
    var yAt = function (d) {
      if (d <= 10) return ez * d / 10;
      return ez + (H - ez - 14) * Math.pow((d - 10) / 40, 1.18);
    };
    var o = [];
    var poly = function (y0, y1, fill) {
      o.push('<polygon points="' + (cx - half(y0)).toFixed(1) + ',' + y0.toFixed(1) + ' ' +
             (cx + half(y0)).toFixed(1) + ',' + y0.toFixed(1) + ' ' + (cx + half(y1)).toFixed(1) + ',' +
             y1.toFixed(1) + ' ' + (cx - half(y1)).toFixed(1) + ',' + y1.toFixed(1) + '" fill="' + fill + '"/>');
    };
    var line = function (x1, y1, x2, y2, op, sw) {
      o.push('<line x1="' + x1.toFixed(1) + '" y1="' + y1.toFixed(1) + '" x2="' + x2.toFixed(1) + '" y2="' +
             y2.toFixed(1) + '" stroke="#fff" stroke-opacity="' + op + '" stroke-width="' + (sw || 1) + '"/>');
    };
    o.push('<defs><linearGradient id="tg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d5a2b"/>' +
           '<stop offset="1" stop-color="#247034"/></linearGradient>' +
           '<linearGradient id="tf" x1="0" y1="0" x2="0" y2="1"><stop offset=".93" stop-color="#000" stop-opacity="0"/>' +
           '<stop offset="1" stop-color="#000" stop-opacity="1"/></linearGradient></defs>');
    /* grass all round the field, as a stadium has it */
    o.push('<rect width="' + W + '" height="' + H + '" fill="#1b4a22"/>');
    poly(0, H, "url(#tg)");
    poly(0, ez, "#1a5026");                          /* the end zone, a shade down (Jose, Sep 23, 2026: "make the field green") */
    /* the sidelines, a band either side */
    [-1, 1].forEach(function (sd) {
      o.push('<polygon points="' + (cx + sd * farH).toFixed(1) + ',0 ' + (cx + sd * (farH + 10)).toFixed(1) + ',0 ' +
             (cx + sd * (nearH + 22)).toFixed(1) + ',' + H + ' ' + (cx + sd * nearH).toFixed(1) + ',' + H + '" fill="#ffffff"/>');   /* white sidelines (Jose, Sep 23, 2026) */
    });
    /* and the end line across the back, white to meet them (Jose, Sep 23, 2026) */
    o.push('<polygon points="' + (cx - farH - 10).toFixed(1) + ',0 ' + (cx + farH + 10).toFixed(1) + ',0 ' +
           (cx + farH + 10.6).toFixed(1) + ',6 ' + (cx - farH - 10.6).toFixed(1) + ',6" fill="#ffffff"/>');
    line(cx - half(0), 0, cx + half(0), 0, .35, 1.4);       /* the end line */
    line(cx - half(ez), ez, cx + half(ez), ez, .55, 2);     /* the goal line */
    for (var d = 11; d <= 50; d++) {
      var y = yAt(d), hw = half(y);
      if (y > H) break;
      var yd = d - 10;
      if (yd % 5 === 0) {
        line(cx - hw, y, cx + hw, y, yd % 10 === 0 ? .2 : .11, yd % 10 === 0 ? 1.3 : 1);
        if (yd % 10 === 0) {
          var fs = Math.max(9, 8 + 9 * (y / H));
          [-1, 1].forEach(function (sd) {
            o.push('<text x="' + (cx + sd * hw * 0.8).toFixed(1) + '" y="' + (y + fs * 0.36).toFixed(1) +
                   '" font-family="Barlow Condensed, Arial Narrow, sans-serif" font-weight="700" font-size="' +
                   fs.toFixed(1) + '" fill="#fff" fill-opacity=".22" text-anchor="middle">' + yd + '</text>');
          });
        }
      } else {
        /* the hashes line up with the uprights, the way an NFL field's do:
           exactly under them at the goal line, and spreading with the field
           toward the reader (Jose, Sep 23, 2026) */
        /* NFL hashes are 18'6" apart on a 160-foot field -- close in, near
           the middle, the way the league's tracking charts draw them */
        var hx = hw * 0.116;
        [-1, 1].forEach(function (sd) { var x = cx + sd * hx; line(x - 3, y, x + 3, y, .16); });
        [-1, 1].forEach(function (sd) { var x = cx + sd * hw; line(x - sd * 7, y, x, y, .13); });
      }
    }
    /* the line of scrimmage, on the 30, sideline to sideline, in the
       league's own tracking-chart blue (Jose, Sep 23, 2026) */
    var los = yAt(40);
    if (los < H) o.push('<line x1="' + (cx - half(los) - 10).toFixed(1) + '" y1="' + los.toFixed(1) + '" x2="' +
                        (cx + half(los) + 10).toFixed(1) + '" y2="' + los.toFixed(1) +
                        '" stroke="#2f6bff" stroke-opacity=".45" stroke-width="3"/>');
    /* the line on the line of scrimmage: tackle, guard, centre, guard,
       tackle -- rings, and a square for the centre, no letters, as the
       placeholders the league's charts draw (Jose, Sep 23, 2026) */
    if (false) {
      var r0 = 11, gap = 30;
      [-2, -1, 0, 1, 2].forEach(function (k) {
        var x = cx + k * gap;
        if (k === 0) o.push('<rect x="' + (x - r0).toFixed(1) + '" y="' + (los - r0).toFixed(1) + '" width="' + (2 * r0) +
                            '" height="' + (2 * r0) + '" fill="#1f5f2e" stroke="#fff" stroke-opacity=".75" stroke-width="1.6"/>');
        else o.push('<circle cx="' + x.toFixed(1) + '" cy="' + los.toFixed(1) + '" r="' + r0 +
                    '" fill="#1f5f2e" stroke="#fff" stroke-opacity=".75" stroke-width="1.6"/>');
      });
    }
    o.push('<rect width="' + W + '" height="' + H + '" fill="url(#tf)"/>');
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + ' ' + H + '">' + o.join("") + '</svg>';
    wrap.style.backgroundImage = 'url("data:image/svg+xml;utf8,' + encodeURIComponent(svg) + '")';
    /* the stadium behind the end zone: grass, a blue wall, the dark stands
       and a light sky over the rim -- no goalpost, no blimp (Jose, Sep 23,
       2026, from abcteach's end zone picture) */
    var SH = 120, st = wrap.querySelector(":scope > .fstadium");
    if (!st) {
      st = document.createElement("div");
      st.className = "fstadium";
      wrap.insertBefore(st, wrap.firstChild);
    }
    var rim = 'M0,' + (SH * 0.42) + ' Q' + (W / 2) + ',' + (SH * 0.08) + ' ' + W + ',' + (SH * 0.42) + ' L' + W + ',0 L0,0 Z';
    st.innerHTML = '<svg width="' + W + '" height="' + SH + '" viewBox="0 0 ' + W + ' ' + SH + '" preserveAspectRatio="none">' +
      '<defs><linearGradient id="skyf" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#000"/>' +
      '<stop offset="1" stop-color="#000" stop-opacity="0"/></linearGradient></defs>' +
      '<rect width="' + W + '" height="' + SH + '" fill="#080a2c"/>' +             /* the stands */
      '<path d="' + rim + '" fill="#7fcfd6"/>' +                                    /* the sky over the rim */
      '<rect y="' + (SH * 0.72) + '" width="' + W + '" height="' + (SH * 0.2) + '" fill="#0c2c72"/>' +   /* the wall */
      '<rect y="' + (SH * 0.92) + '" width="' + W + '" height="' + (SH * 0.08 + 1) + '" fill="#1b4a22"/>' + /* grass to the line */
      '<rect width="' + W + '" height="' + (SH * 0.35) + '" fill="url(#skyf)"/></svg>';
  }
  /* ---- HOT loops ----
     The gold row has no ends: a copy of it stands either side, and when a
     swipe settles in a copy the row is moved by exactly one row's width to
     the same card in the middle set -- the same picture, so nothing is seen
     to jump (Jose, Sep 23, 2026: "one continuous row... I can scroll through
     it endlessly"). Rebuilt whenever who is in it changes. */
  function loopRow(box) {
    box.querySelectorAll(".qcard--clone").forEach(function (c) { c.remove(); });
    if (box._loopOff) { box.removeEventListener("scroll", box._loopOff); box._loopOff = null; }
    if (!box.classList.contains("qcards--hot")) return;
    var real = [].slice.call(box.querySelectorAll(".qcard")).filter(function (c) {
      return getComputedStyle(c).display !== "none";
    });
    box.classList.remove("qcards--still");
    if (real.length < 2) { box.classList.add("qcards--still"); return; }
    /* only a row that runs off the screen loops; two or three that fit sit
       still in the middle, no copies (Jose, Sep 28, 2026: "the loop doesn't
       make sense for 2 players") */
    var lastR = real[real.length - 1];
    if (lastR.offsetLeft + lastR.offsetWidth - real[0].offsetLeft <= box.clientWidth + 1) {
      box.classList.add("qcards--still");
      box.scrollLeft = 0;
      box._seatFirst = null;
      return;
    }
    var mk = function (c) {
      var k = c.cloneNode(true);
      k.classList.add("qcard--clone");
      k.removeAttribute("id");
      return k;
    };
    var first = real[0], last = real[real.length - 1];
    real.forEach(function (c) { box.insertBefore(mk(c), first); });
    var after = last.nextSibling;
    real.forEach(function (c) { box.insertBefore(mk(c), after); });
    var span = function () { return first.offsetLeft - box.querySelector(".qcard--clone").offsetLeft; };
    /* open on the first real card, centered -- measured, not stepped by a
       clone span, which the HOT zoom changes after the fact and which left
       the row sitting on the sixth card (Jose, Sep 26, 2026) */
    box._seatFirst = function () {
      var prev = box.style.scrollSnapType;
      box.style.scrollSnapType = "none";
      /* by where the card sits on the screen: the row is zoomed to fit the
         field, and offsets and scroll do not share a scale under a zoom */
      for (var k = 0; k < 4; k++) {
        var br = box.getBoundingClientRect(), fr = first.getBoundingClientRect();
        var off = (fr.left + fr.width / 2) - (br.left + br.width / 2);
        if (Math.abs(off) < 1) break;
        var z = parseFloat(getComputedStyle(box).zoom) || 1;
        box.scrollLeft += off / z;
      }
      requestAnimationFrame(function () { box.style.scrollSnapType = prev; });
    };
    box._seatFirst();
    requestAnimationFrame(box._seatFirst);
    var wait = 0;
    box._loopOff = function () {
      clearTimeout(wait);
      wait = setTimeout(function () {
        /* on the screen, like the seat above: under the zoom, offsets and
           scroll are not one scale, and the wrap jumped cards */
        var br = box.getBoundingClientRect(), mid = br.left + br.width / 2;
        var fr = first.getBoundingClientRect(), lr = last.getBoundingClientRect();
        var c0 = box.querySelector(".qcard--clone"), z = parseFloat(getComputedStyle(box).zoom) || 1;
        var w = c0 ? (fr.left - c0.getBoundingClientRect().left) / z : 0;
        if (!w) return;
        if (mid < fr.left - 5) box.scrollLeft += w;
        else if (mid > lr.right + 5) box.scrollLeft -= w;
      }, 120);
    };
    box.addEventListener("scroll", box._loopOff, { passive: true });
  }
  /* ---- what the picks pay ----
     Each pick is his next game's 1+ or 2+ passing touchdown, read from the
     game's own price file; the two sides of a game's ptd are away then home.
     A pick with a price posted wears a green rim, one without a red; the
     picks that are priced, taken together, are written in green in the
     middle of the crossbar (Jose, Sep 23, 2026). */
  var PICKPX = {};
  function nextGame(pid) {
    var now = Date.now() - 4 * 3600000, best = null;
    (SCHED || []).forEach(function (r) {
      if (String(r[6]) !== String(pid) && String(r[8]) !== String(pid)) return;
      var k = Date.parse(r[2]);
      if (isNaN(k) || k < now) return;
      if (!best || k < Date.parse(best[2])) best = r;
    });
    return best ? { id: String(best[1]), side: String(best[6]) === String(pid) ? 0 : 1, row: best } : null;
  }
  function pickPrice(p, whole) {
    var g = nextGame(p.id);
    if (!g) return Promise.resolve(null);
    var read = function (props) {
      var rush = String(p.tier) === "r";
      var rung = ((((props || {})[rush ? "atd" : "ptd"] || [])[g.side] || [])[rush ? 0 : (parseInt(p.tier, 10) || 1) - 1]) || [];
      if (whole) return rung[0] ? { o: rung[0], oid: rung[1], g: g } : null;
      return rung[0] || null;
    };
    var have = read(PROPS[g.id]);
    if (PICKPX[g.id]) return PICKPX[g.id].then(read);
    PICKPX[g.id] = fetch("prices/" + g.id + ".json", { cache: "no-store" })
      .then(function (r) {
        var t = (r.headers.get("content-type") || "").toLowerCase();
        return r.ok && t.indexOf("json") >= 0 ? r.json() : null;
      })
      .then(function (j) { return (j && j.props) || PROPS[g.id] || null; })
      .catch(function () { return PROPS[g.id] || null; });
    return PICKPX[g.id].then(function (props) { return read(props) || have; });
  }
  /* the row's price is the button: a tap puts every leg in the eight on the
     slip, the same slip a tap on the board fills (Jose, Sep 23, 2026) */
  function eightToSlip(btn) {
    var picks = loadPicks(), was = btn.textContent;
    if (!picks.length) return;
    Promise.all(picks.map(function (p) { return pickPrice(p, true).then(function (x) { return { p: p, x: x }; }); })).then(function (all) {
      var n = 0;
      all.forEach(function (a) {
        if (!a.x || !a.x.oid) return;
        var r = a.x.g.row, name = String(a.x.g.side === 0 ? r[5] : r[7]);
        var what = a.p.tier === "r" ? "1+ ATD" : a.p.tier + "+ PTD";
        var when = new Date(r[2]).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });
        saved[a.x.oid] = { o: String(a.x.o).replace("-", "\u2212"), l: famName(name) + " " + what + " \u00b7 " + when,
                           g: a.x.g.id, gn: r[3] + " @ " + r[4] };
        document.querySelectorAll("button.price").forEach(function (b0) { if (b0.dataset.oid === a.x.oid) b0.classList.add("on"); });
        n++;
      });
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
      if (typeof pushState === "function") pushState();
      if (typeof slip === "function") slip();
      btn.classList.add("fpay--done");
      btn.textContent = n ? "Added " + n : "No prices";
      setTimeout(function () { btn.classList.remove("fpay--done"); btn.textContent = was; }, 1400);
    });
  }
  /* legs from anywhere on the page onto the slip, the way the eight's button
     puts them there: [{oid, o, l, g, gn}], a leg with no price id is left out
     (Jose, Sep 28, 2026: the search's parlay, "two out of three available,
     then two end up in the slip") */
  window.addLegs = function (legs) {
    var n = 0;
    (legs || []).forEach(function (x) {
      if (!x || !x.oid || !x.o) return;
      saved[x.oid] = { o: String(x.o).replace("-", "\u2212"), l: x.l, g: x.g || "", gn: x.gn || "" };
      document.querySelectorAll("button.price").forEach(function (b0) { if (b0.dataset.oid === x.oid) b0.classList.add("on"); });
      n++;
    });
    if (!n) return 0;
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
    if (typeof pushState === "function") pushState();
    if (typeof slip === "function") slip();
    return n;
  };
  function pricePicks(slots, picks) {
    var bar = document.querySelector(".fview--ptd");
    var out = bar && bar.querySelector(".fpay");
    /* in the end zone, at its right end, level with the picks -- off the
       field, where it sat on the hashes (Jose, Sep 23, 2026) */
    out = slots.querySelector(".fpay");
    if (!out) {
      out = document.createElement("button");
      out.type = "button";
      out.className = "fpay";
      out.addEventListener("click", function (e) { e.stopPropagation(); eightToSlip(out); });
      slots.appendChild(out);
    }
    var mine = picks.slice(0, MAXPICK);
    /* one argument only: .map hands the index along too, and a second
       argument asks pickPrice for the whole rung -- every pick after the
       first came back an object and fell out of the sum (Jose, Sep 23,
       2026: "those are definitely not accurate odds") */
    Promise.all(mine.map(function (p) { return pickPrice(p); })).then(function (odds) {
      var dec = 1, n = 0;
      odds.forEach(function (o, i) {
        var chip = slots.querySelector('.fpick[data-id="' + mine[i].id + '"]');
        if (chip) {
          chip.classList.toggle("fpick--priced", !!o);
          chip.classList.toggle("fpick--open", !o);
          chip.title = o ? ((mine[i].tier === "r" ? "1+ RTD " : mine[i].tier + "+ PTD ") + o) : "No price yet";
        }
        var d = toDecOdds(o);
        if (d) { dec *= d; n++; }
      });
      if (out) out.textContent = n ? toUsOdds(dec).replace("\u2212", "\u2212") : "";
    });
  }
  function drawPicks(slots, picks, box) {
    var layer = slots.querySelector(".fpicks");
    if (!layer) { layer = document.createElement("div"); layer.className = "fpicks"; slots.appendChild(layer); }
    var spots = pickSpots(slots, Math.min(MAXPICK, picks.length));
    layer.innerHTML = picks.slice(0, MAXPICK).map(function (p, i) {
      var sp = spots[i];
      return '<span class="fpick" data-id="' + p.id + '" style="' + (p.look || "") + ';left:' + sp.left.toFixed(1) + 'px;top:' + sp.top.toFixed(1) +
             'px;width:' + sp.w + 'px;height:' + sp.h + 'px"><img src="face/nfl/' + p.id +
             '.png" alt="" onerror="this.onerror=null;this.src=NOFACE"><b class="fpick__mk">' +
             (String(p.tier) === "2" ? "<em>2</em>" : "") + (String(p.tier) === "r" ? RUSHSVG : BALLSVG) + '</b></span>';
    }).join("");
    /* and the row: a picked passer is no longer in it */
    if (box) box.querySelectorAll(".qcard:not(.qcard--clone)").forEach(function (c) {
      var f = c.querySelector("[data-ring]");
      var on = !!f && picks.some(function (p) { return String(p.id) === String(f.dataset.ring); });
      if (on) c.dataset.picked = "1"; else delete c.dataset.picked;
    });
    if (box) loopRow(box);
    /* eight picked: the row goes grey and takes no more until one is tapped
       off the top (Jose, Sep 23, 2026) */
    if (box) box.classList.toggle("qcards--full", picks.length >= MAXPICK);
    pricePicks(slots, picks);
  }
  /* The white line, in page coordinates, as the fork stands now: the post's
     center from its foot up to the crossbar's middle, across to an upright's
     center, and up the upright to the word. The finger picks the distance
     along it; the chip is put on the line at that distance. */
  /* ---- the three routes ----
     One post rises from the cards to a crossbar. Left, it turns up a short
     white upright into a green line to the goal line: one passing
     touchdown. Right, the same, mirrored: two. Up the middle, a blue zigzag:
     a rushing touchdown. Points are in the forkbox's own pixels, x from its
     centre line, y down from the goal line (Jose, Sep 23, 2026). */
  /* From the snap: he drops back down-left and runs straight up for one
     passing touchdown, drops back down-right and runs up for two, or goes
     up the middle on the blue zigzag for the rushing one. The drop-backs
     and the runs up are a faint white, the zigzag the line of scrimmage's
     blue (Jose, Sep 23, 2026). */
  /* From the snap: he drops back down-left or down-right and steps up to
     the line of scrimmage -- halfway across it and let go is the throw, one
     passing touchdown on the left, two on the right. Up the middle on the
     blue zigzag is the rushing one, all the way to the goal line. The green
     lines outside are the receivers' routes, drawn for the picture only
     (Jose, Sep 23, 2026). */
  /* No lines any more, three boxes: the centre one at the snap -- straight
     up from it to the goal line is the rushing touchdown -- and one each
     side behind the line, between the hash and the sideline: drop back into
     it and go up and out at 45 degrees across the line of scrimmage for the
     throw, one on the left, two on the right (Jose, Sep 23, 2026). */
  var ROUTES = [
    /* the drop boxes sit behind the receivers, out wide (Jose, Sep 23,
       2026); from there the step up is straight up to the line -- up and out
       would leave the field */
    /* level with the linemen (Jose, Sep 25, 2026: "move the PTD in line
       with the linemen") */
    { tier: "1", label: "1 PTD", color: "#3fbf5a", pts: [[0, 185], [-160, 172]], at: [-160, 172], box: [-160, 172] },
    /* the rush has its own box above the centre, the same size as the
       other two (Jose, Sep 23, 2026) */
    { tier: "r", label: "RTD",   color: "#3b82f6", pts: [[0, 185], [0, 0]], at: [0, 106], box: [0, 106] },
    { tier: "2", label: "2 PTD", color: "#3fbf5a", pts: [[0, 185], [160, 172]], at: [160, 172], box: [160, 172] }
  ];
  var RECEIVERS = [
    /* each receiver on the line with the linemen, his box right under him
       (Jose, Sep 25, 2026) */
    /* they finish at the goal line, in front of the picks: with the
       formation lifted up the field its top is above the line, and a route
       run to the top ended in the stands (Jose, Sep 29, 2026) */
    [[-164, 135], [-157, 84], [-86, 52]],
    [[164, 135], [121, 96], [152, 58]]
  ];
  var POSTFOOT = 205;
  /* the formation's size on the field (the .forkbox.fork-on transform): a
     point y down the formation stands at forkbox.top + y * FSCALE on the
     screen, and x across it at the middle + x * FSCALE */
  var FSCALE = 0.82;
  /* a point a fraction of the way along a polyline */
  function alongPts(P, f) {
    var L = [], T = 0;
    for (var i = 1; i < P.length; i++) { var d = Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]); L.push(d); T += d; }
    var want = Math.max(0, Math.min(1, f)) * T, acc = 0;
    for (var j = 0; j < L.length; j++) {
      if (want <= acc + L[j] || j === L.length - 1) {
        var t = L[j] ? (want - acc) / L[j] : 0;
        return [P[j][0] + (P[j + 1][0] - P[j][0]) * t, P[j][1] + (P[j + 1][1] - P[j][1]) * t];
      }
      acc += L[j];
    }
    return P[P.length - 1];
  }
  function routeLen(P) {
    var T = 0;
    for (var i = 1; i < P.length; i++) T += Math.hypot(P[i][0] - P[i - 1][0], P[i][1] - P[i - 1][1]);
    return T;
  }
  /* the two starting receivers of each club, in their Kalshi jerseys */
  var WRS = null;
  function loadWrs() {
    if (!WRS) WRS = fetch("wr.json", { cache: "no-store" }).then(function (r) { return r.json(); }).catch(function () { return {}; });
    return WRS;
  }
  /* his club's five up front, from site/lineups.json (build/lineups.py): a
     starter who is out rings red, one who is questionable yellow, and they
     stand still (Jose, Sep 28, 2026: "do lineman here too based on injuries.
     No movement just stationary") */
  var HOTLU = null;
  function loadLu() {
    if (!HOTLU) HOTLU = fetch("lineups.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : {}; })
      .catch(function () { return {}; });
    return HOTLU;
  }
  /* lifted, his five stand in his club's Kalshi jerseys with their numbers,
     where the rings were, the hurt ones edged (Jose, Sep 28, 2026: "use the
     kalshi jerseys") */
  function olMarks(forkbox, club) {
    var routes = forkbox && forkbox.querySelector(".froutes");
    if (!routes || !club) return;
    loadLu().then(function (lu) {
      var line = {};
      Object.keys(lu || {}).some(function (gid) {
        var mine = (lu[gid] || {})[club];
        if (!mine) return false;
        (mine.off || []).forEach(function (m) { if (/^(lt|lg|c|rg|rt)$/.test(m.k)) line[m.k] = m; });
        return true;
      });
      if (!Object.keys(line).length) return;
      forkbox.querySelectorAll(".fol").forEach(function (x) { x.remove(); });
      ["lt", "lg", "c", "rg", "rt"].forEach(function (k, i) {
        var m = line[k] || { n: "", s: "" };
        var j = document.createElement("i");
        j.className = "fol" + (m.s ? " fol--" + m.s : "");
        j.style.left = (137 + (i - 2) * 30) + "px";
        j.style.backgroundImage = "url(ico/jersey/" + club.toLowerCase() + ".png)";
        j.innerHTML = "<em>" + (String(m.n || "").replace(/[^0-9]/g, "") || k.toUpperCase()) + "</em>";
        forkbox.appendChild(j);
      });
      routes.style.backgroundImage = 'url("data:image/svg+xml;utf8,' + encodeURIComponent(routeSvg(null, true)) + '")';
    });
  }
  function olClear(forkbox) {
    var routes = forkbox && forkbox.querySelector(".froutes");
    if (forkbox) forkbox.querySelectorAll(".fol").forEach(function (x) { x.remove(); });
    if (routes) routes.style.backgroundImage = 'url("data:image/svg+xml;utf8,' + encodeURIComponent(routeSvg()) + '")';
  }
  function routeSvg(marks, noLine) {
    marks = marks || {};
    var W = 420, H = 236, cx = W / 2, o = [];   /* tall enough for the quarterback's spot */
    /* the three boxes, faint -- where the finger goes, not a line to follow */
    ROUTES.forEach(function (r) {
      var bw = 64, bh = 30;
      o.push('<rect x="' + (cx + r.box[0] - bw / 2) + '" y="' + (r.box[1] - bh / 2) + '" width="' + bw + '" height="' + bh +
             '" rx="8" fill="' + r.color + '" fill-opacity=".10" stroke="' + r.color + '" stroke-opacity=".75" stroke-width="1.6"/>');
    });
    /* the quarterback's spot, the indicator's size, right behind the centre:
       he can be dragged into it and left there (Jose, Sep 23, 2026) */
    o.push('<rect x="' + (cx - 28.5) + '" y="' + (185 - 27.5) + '" width="57" height="55" rx="18" fill="#fff" fill-opacity=".04" ' +
           'stroke="#fff" stroke-opacity=".45" stroke-width="1.4" stroke-dasharray="4 4"/>');
    /* the line on top of everything */
    if (!noLine) [-2, -1, 0, 1, 2].forEach(function (k) {
      var x = cx + k * 30, y = 135, r0 = 11;   /* clear of the QB spot below (Sep 25, 2026) */
      var mk = marks[["lt", "lg", "c", "rg", "rt"][k + 2]];
      var ink = mk === "out" ? 'stroke="#ff3b30" stroke-opacity="1" stroke-width="2.6"'
              : mk === "q" ? 'stroke="#ffd60a" stroke-opacity="1" stroke-width="2.6"'
              : 'stroke="#fff" stroke-opacity=".8" stroke-width="1.6"';
      o.push(k === 0
        ? '<rect x="' + (x - r0) + '" y="' + (y - r0) + '" width="' + 2 * r0 + '" height="' + 2 * r0 +
          '" fill="none" ' + ink + '/>'
        : '<circle cx="' + x + '" cy="' + y + '" r="' + r0 + '" fill="none" ' + ink + '/>');
    });
    return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ' + W + ' ' + H + '">' + o.join("") + '</svg>';
  }
  function forkPath(forkbox) {
    var r = forkbox.getBoundingClientRect(), s = FSCALE;
    var top = r.top, left = r.left + (r.width - 274 * s) / 2;
    var mid = top + 94 * s, foot = top + 209 * s;
    return {
      post: { x: left + 137 * s, from: foot, to: mid },
      bar: { y: mid, from: left + 137 * s },
      ups: [{ x: left + 34.5 * s, tier: "1" }, { x: left + 239.5 * s, tier: "2" }],
      /* the chip's middle at the upright's top edge: half of him through the
         opening, and no further -- letting go there drops him in (Jose,
         Sep 23, 2026: "it doesn't go past 50% of the indicator until I let
         go") */
      wordY: mid, upTop: top,
      ox: left + 137 * s, oy: top
    };
  }
  function wirePick(box, slots, ptdbar, forkbox) {
    var picks = loadPicks();
    drawPicks(slots, picks, box);
    /* drawn again whenever HOT opens: measured while the row was hidden, the
       squares were 0 wide and every chip came out 0 by 0 */
    var chips0 = document.querySelector(".fview:not(.fview--ptd)");
    if (chips0) chips0.addEventListener("click", function () {
      requestAnimationFrame(function () { if (!slots.hidden) drawPicks(slots, picks, box); });
    });
    requestAnimationFrame(function () { if (!slots.hidden) drawPicks(slots, picks, box); });
    slots.addEventListener("click", function (e) {
      var c = e.target.closest(".fpick");
      if (!c) return;
      picks = picks.filter(function (p) { return String(p.id) !== c.dataset.id; });
      savePicks(picks);
      drawPicks(slots, picks, box);
    });
    var card = null, id = "", x0 = 0, y0 = 0, decided = false, live = false;
    var ghost = null, w0 = 0, h0 = 0, over = null, pid = null, path = null, side = 0;
    var px = 0, py = 0, u = 0, v = 0;       /* the last finger spot; sideways on the bar; up the upright */
    var rt = -1, rs = 0;                    /* the route he is on, and how far along it */
    var stage = 0, ax = 0, ay = 0, dir = null, parked = null;   /* 0 rising, 1 at the spot; its anchor; the way out; who is parked */
    var cw = 57, ch = 55;                   /* the indicator's size on this screen */
    /* where the finger wants it and where it is: each frame it closes most
       of the gap, so sparse input still reads as one motion and a turn onto
       the post or the bar is a glide, not a jump */
    var tgt = { x: 0, y: 0, w: 0, h: 0 }, cur = { x: 0, y: 0, w: 0, h: 0 }, raf = 0;
    function tick() {
      raf = 0;
      if (!live || !ghost) return;
      var k = 0.3;                            /* closes a third of the gap a frame: quick to the finger, never a jump */
      cur.x += (tgt.x - cur.x) * k; cur.y += (tgt.y - cur.y) * k;
      cur.w += (tgt.w - cur.w) * k; cur.h += (tgt.h - cur.h) * k;
      place(cur.x, cur.y, cur.w, cur.h);
      if (Math.abs(tgt.x - cur.x) + Math.abs(tgt.y - cur.y) + Math.abs(tgt.w - cur.w) > 0.3) raf = requestAnimationFrame(tick);
    }
    function aim(x, y, w, h) {
      tgt.x = x; tgt.y = y; tgt.w = w; tgt.h = h;
      if (!raf) raf = requestAnimationFrame(tick);
    }
    function place(x, y, w, h) {
      ghost.style.width = w + "px"; ghost.style.height = h + "px";
      ghost.style.transform = "translate(" + (x - w / 2) + "px," + (y - h / 2) + "px)";
      /* the card inside scales to the chip's height and is clipped to its
         width from the left, so the rank in the corner and the face column
         stay in view and it is the stats side that goes off the edge */
      var twin = ghost.firstElementChild;
      if (twin && h0) {
        var k = h / h0;
        twin.style.transform = "scale(" + k + ")";
        /* with the stats gone the card narrows to the chip instead of being
           clipped, so what is centered in the card is centered in the chip */
        twin.style.width = (ghost.classList.contains("pickghost--lite") ? w / k : w0) / (ghost._z || 1) + "px";
      }
    }
    function shed(p) {
      ghost.classList.toggle("pickghost--lite", p > 0.3);
      ghost.classList.toggle("pickghost--bare", p > 0.6);
    }
    function done() {
      if (card) card.style.opacity = "";
      document.querySelectorAll(".froute.drop").forEach(function (b) { b.classList.remove("drop"); });
      document.querySelectorAll(".fwr.on").forEach(function (im) { im.classList.remove("on"); });
      card = null; live = false; decided = false; over = null;
    }
    box.addEventListener("pointerdown", function (e) {
      if (e.button) return;
      var c = e.target.closest(".qcard");
      if (!c || !box.classList.contains("qcards--hot") || box.classList.contains("qcards--full")) return;
      var face = c.querySelector("[data-ring]");
      if (!face) return;
      card = c; id = face.dataset.ring; x0 = e.clientX; y0 = e.clientY; pid = e.pointerId;
      decided = false; live = false;
    });
    box.addEventListener("pointermove", function (e) {
      if (!card) return;
      var dx = e.clientX - x0, dy = e.clientY - y0;
      if (!decided) {
        if (Math.abs(dx) > 8 && Math.abs(dx) > Math.abs(dy)) { card = null; return; }   /* a swipe: the row's */
        if (dy > -8 || Math.abs(dy) <= Math.abs(dx)) return;
        decided = true; live = true;
        try { box.setPointerCapture(pid); } catch (err) {}
        var r = card.getBoundingClientRect();
        w0 = r.width; h0 = r.height;
        path = forkPath(forkbox);
        px = e.clientX; py = e.clientY; u = 0; v = 0; rt = -1; rs = 0; stage = 0; dir = null;
        if (parked) sendHome(parked);         /* one at the spot at a time */
        /* his receivers come out when he is lifted -- his own club's two
           starters, in their jerseys (Jose, Sep 23, 2026) */
        var mk = /logos\/nfl\/([a-z]+)\.png/.exec((card.querySelector(".qface") || {}).getAttribute ?
                 card.querySelector(".qface").getAttribute("style") || "" : "");
        var club = mk ? mk[1].toUpperCase() : "";
        olMarks(forkbox, club);
        loadWrs().then(function (w) {
          var two = w[club] || [];
          forkbox.querySelectorAll(".fwr").forEach(function (im, k) {
            if (!two[k]) { im.classList.remove("on"); return; }
            im.src = "ico/wr/" + two[k];
            im.style.left = (137 + RECEIVERS[k][0][0]) + "px"; im.style.top = RECEIVERS[k][0][1] + "px";
            im.style.opacity = "";
            im.classList.add("on");
          });
        });
        /* the chip ends at the size the row's indicators actually are on
           this screen -- 43 on a phone, 57 on a desktop -- not a fixed 57
           (Jose, Sep 23, 2026: "it should be the size of the indicator") */
        cw = 57; ch = 55;
        ghost = document.createElement("div");
        ghost.className = "pickghost";
        var twin = card.cloneNode(true);
        /* the card may be drawn larger than its own layout (HOT's zoom): the
           copy is laid out the same way, so it is the same card, only moved */
        /* every zoom it sits under, the card row's own included: read off the
           card alone it was 1, and the copy cut his face off (Sep 25, 2026) */
        var Z = 1;
        for (var zn = card; zn && zn.nodeType === 1; zn = zn.parentElement) Z *= parseFloat(getComputedStyle(zn).zoom) || 1;
        ghost._z = Z;
        twin.style.zoom = Z;
        twin.style.opacity = ""; twin.style.width = w0 / Z + "px"; twin.style.height = h0 / Z + "px";
        ghost.appendChild(twin);
        document.body.appendChild(ghost);
        cur.x = r.left + r.width / 2; cur.y = r.top + r.height / 2; cur.w = w0; cur.h = h0;
        place(cur.x, cur.y, cur.w, cur.h);
        card.style.opacity = "0.35";
      }
      if (!live) return;
      if (e.cancelable) e.preventDefault();
      /* it shrinks as it rises: full size at the card, the indicator's size
         by the time it reaches the post's foot, and no smaller after that */
      var lift = y0 - e.clientY;
      var toFoot = Math.max(1, y0 - path.post.from);
      var p = Math.max(0, Math.min(1, lift / toFoot));
      var w = w0 + (cw * FSCALE - w0) * p, h = h0 + (ch * FSCALE - h0) * p;
      shed(p);
      var cx, cy;
      /* Up to the quarterback's spot behind the centre, then straight out of
         it: left is one passing touchdown, right is two, up is the rush. No
         diagonals -- the first clear direction from the spot is the play
         (Jose, Sep 23, 2026). */
      var spotX = path.ox, spotY = path.oy + 185 * FSCALE;
      if (stage === 0) {
        cx = e.clientX + (spotX - e.clientX) * p; cy = Math.max(spotY, e.clientY);
        if (e.clientY <= spotY + 8) { stage = 1; ax = e.clientX; ay = e.clientY; dir = null; }
      }
      var hit = null;
      if (stage === 1) {
        var st = fromSpot((e.clientX - ax) / FSCALE, (e.clientY - ay) / FSCALE);
        cx = spotX + st.x * FSCALE; cy = spotY + st.y * FSCALE; hit = st.hit;
      }
      aim(cx, cy, w, h);
      over = hit;
    });
    /* from the spot: the offset of the finger since it got there, turned into
       a place on one of the three straight lines, the receivers kept in time */
    function fromSpot(rx, ry) {
      if (!dir) {
        if (Math.hypot(rx, ry) > 16) {
          if (Math.abs(rx) > Math.abs(ry)) dir = rx < 0 ? "1" : "2";
          else if (ry < 0) dir = "r";
        }
      }
      var out = { x: 0, y: 0, hit: null }, frac = 0;
      if (dir) {
        var L = dir === "r" ? 185 : 160;
        var along = dir === "1" ? -rx : dir === "2" ? rx : -ry;
        if (along < 4) { dir = null; along = 0; }
        along = Math.max(0, Math.min(L, along));
        frac = along / L;
        out.x = dir === "1" ? -along : dir === "2" ? along : 0;
        /* a pass slides him up into its box, which stands level with the
           linemen, not on his own line */
        out.y = dir === "r" ? -along : (172 - 185) * frac;
        if (along >= L - 0.5) out.hit = { tier: dir };
      }
      forkbox.querySelectorAll(".fwr.on").forEach(function (im) {
        var k = +im.dataset.k;
        if (dir === "r") { im.style.opacity = String(Math.max(0, 1 - frac)); return; }
        var mine = !dir || (dir === "1" ? 0 : 1) === k;
        im.style.opacity = mine ? "" : "0";
        /* he only starts his route while the swipe is on: the rest he runs
           while the ball is in the air, so the two meet in the end zone
           (Jose, Sep 25, 2026: "time it so the WR matches the ball") */
        im._f = dir && mine ? frac * 0.3 : 0;
        var at = alongPts(RECEIVERS[k], im._f);
        im.style.left = (137 + at[0]) + "px"; im.style.top = at[1] + "px";
      });
      forkbox.querySelectorAll(".froute").forEach(function (l) {
        l.classList.toggle("drop", !!out.hit && l.dataset.tier === out.hit.tier);
      });
      return out;
    }
    /* a pass: the ball goes out to his receiver the way the 2D passing chart
       throws it -- brown, white-rimmed, climbing an arc that is drawn behind
       it in the pass colour, growing as it rises and shrinking as it drops
       (Jose, Sep 23, 2026: "we have one from the 2D") */
    function throwTo(tier, from) {
      if (tier === "r") return;
      var im = forkbox.querySelectorAll(".fwr")[tier === "1" ? 0 : 1];
      if (!im) return;
      var ir = im.getBoundingClientRect(), fb = forkbox.getBoundingClientRect();
      /* from his hand: wherever he stands when he lets it go */
      var ax0 = from ? from[0] : fb.left + fb.width / 2, ay0 = from ? from[1] : fb.top + 185 * FSCALE;
      /* thrown to where he will be at the end of his route, and he runs
         there in the same time the ball takes */
      var route = RECEIVERS[tier === "1" ? 0 : 1], f0 = im._f || 0;
      var endAt = alongPts(route, 1), nowAt = alongPts(route, f0);
      var bx = ir.left + ir.width / 2 + (endAt[0] - nowAt[0]) * FSCALE, by = ir.top + ir.height / 2 + (endAt[1] - nowAt[1]) * FSCALE;
      var peak = 70 + Math.hypot(bx - ax0, by - ay0) * 0.25;
      var NS = "http://www.w3.org/2000/svg";
      var svg = document.createElementNS(NS, "svg");
      svg.setAttribute("class", "fthrow");
      svg.setAttribute("width", innerWidth); svg.setAttribute("height", innerHeight);
      var trail = document.createElementNS(NS, "path"), ball = document.createElementNS(NS, "g");
      trail.setAttribute("fill", "none"); trail.setAttribute("stroke", "#3fbf5a"); trail.setAttribute("stroke-width", "3.4");
      trail.setAttribute("stroke-linecap", "round"); trail.setAttribute("opacity", ".93");
      ball.innerHTML = '<ellipse rx="7" ry="5" fill="#7a3a13" stroke="#f2efe6" stroke-width="1"/>' +
                       '<line x1="-3" y1="0" x2="3" y2="0" stroke="#f2efe6" stroke-width="1"/>';
      svg.appendChild(trail); svg.appendChild(ball);
      document.body.appendChild(svg);
      var pt = function (t) {
        return [ax0 + (bx - ax0) * t, ay0 + (by - ay0) * t - Math.sin(Math.PI * t) * peak];
      };
      var t0 = performance.now(), T = 700, d = "";
      (function step(now) {
        var t = Math.min(1, (now - t0) / T), p = pt(t), q = pt(Math.min(1, t + 0.02));
        var run = alongPts(route, f0 + (1 - f0) * t);
        im.style.left = (137 + run[0]) + "px"; im.style.top = run[1] + "px";
        d += (d ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1);
        trail.setAttribute("d", d);
        var sc = 1 + 0.7 * Math.sin(Math.PI * t);
        var ang = Math.atan2(q[1] - p[1], q[0] - p[0]) * 180 / Math.PI;
        ball.setAttribute("transform", "translate(" + p[0] + "," + p[1] + ") rotate(" + ang + ") scale(" + sc + ")");
        if (t < 1) requestAnimationFrame(step);
        else { svg.style.opacity = "0"; setTimeout(function () { svg.remove(); }, 260); }
      })(t0);
    }
    function takeIn(g, c, tier) {
      spotName(null);
      if (picks.length >= MAXPICK || picks.some(function (p) { return String(p.id) === String(g.dataset.id); })) { sendHome(g); return; }
      var gr = g.getBoundingClientRect();
      throwTo(tier, [gr.left + gr.width / 2, gr.top + gr.height / 2]);
      var qf = c.querySelector(".qface");
      picks.push({ id: g.dataset.id, tier: tier, look: qf ? qf.getAttribute("style") || "" : "" });
      savePicks(picks);
      shiftPicks(slots, picks.length);
      var sp = pickSpots(slots, picks.length)[picks.length - 1], rr = slots.getBoundingClientRect();
      g.classList.add("pickghost--home"); g.classList.remove("pickghost--parked");
      if (tier !== "r") g.classList.add("pickghost--glide");
      /* the throw plays first; once the ball is caught he goes up to the end
         zone (Jose, Sep 25, 2026: "after the animation the QB goes up") */
      setTimeout(function () { var hold = ghost; ghost = g; place(rr.left + sp.left + sp.w / 2, rr.top + sp.top + sp.h / 2, sp.w, sp.h); ghost = hold; }, tier === "r" ? 0 : 720);
      setTimeout(function () { drawPicks(slots, picks, box); g.remove(); c.style.opacity = ""; }, tier === "r" ? 300 : 1250);
      if (parked === g) parked = null;
      forkbox.querySelectorAll(".fwr.on").forEach(function (im) { setTimeout(function () { im.classList.remove("on"); }, 700); });
      setTimeout(function () { olClear(forkbox); }, 700);
      forkbox.querySelectorAll(".froute.drop").forEach(function (l) { l.classList.remove("drop"); });
    }
    function sendHome(g) {
      spotName(null);
      var c = g._card, hold = ghost; ghost = g;
      g.classList.add("pickghost--home"); g.classList.remove("pickghost--parked");
      shed(0);
      if (c) { var cr = c.getBoundingClientRect(); place(cr.left + cr.width / 2, cr.top + cr.height / 2, g._w0, g._h0); }
      ghost = hold;
      g.style.opacity = "0";
      setTimeout(function () { g.remove(); if (c) c.style.opacity = ""; }, 280);
      if (parked === g) parked = null;
      forkbox.querySelectorAll(".fwr.on").forEach(function (im) { im.classList.remove("on"); });
      olClear(forkbox);
    }
    /* left at the spot, he waits there: a swipe on him straight left, right
       or up plays it from where he stands */
    /* his name under the spot he waits in, not squeezed into the tile
       (Jose, Sep 25, 2026: "name below the placeholder") */
    function spotName(g) {
      var tag = forkbox.querySelector(".fqbname");
      if (!tag) { tag = document.createElement("span"); tag.className = "fqbname"; forkbox.appendChild(tag); }
      var h = g && g.querySelector(".qname h3");
      tag.textContent = h ? h.textContent : "";
      tag.classList.toggle("on", !!(g && h));
    }
    function park(g) {
      parked = g;
      g.classList.remove("pickghost--home"); g.classList.add("pickghost--parked");
      spotName(g);
      var fb = forkbox.getBoundingClientRect();
      var hold = ghost; ghost = g; place(fb.left + fb.width / 2, fb.top + 185 * FSCALE, cw * FSCALE, ch * FSCALE); ghost = hold;
      /* he rides with the field: a scroll or another tab must not leave him
         floating over other cards (Jose, Sep 25, 2026: "leaking into other
         pages") */
      if (!park._ride) {
        park._ride = function () {
          var p = parked;
          if (!p || !p.isConnected) return;
          var r = forkbox.getBoundingClientRect();
          var on = r.width && forkbox.classList.contains("fork-on");
          if (!on) { sendHome(p); return; }
          var t = p.style.transition; p.style.transition = "none";
          var hold2 = ghost; ghost = p; place(r.left + r.width / 2, r.top + 185 * FSCALE, cw * FSCALE, ch * FSCALE); ghost = hold2;
          void p.offsetWidth; p.style.transition = t;
        };
        window.addEventListener("scroll", park._ride, true);
        window.addEventListener("resize", park._ride);
        document.addEventListener("click", function () { setTimeout(park._ride, 0); }, true);
      }
      if (g._wired) return;
      g._wired = true;
      var sx = 0, sy = 0, down = false;
      g.addEventListener("pointerdown", function (ev) {
        ev.stopPropagation(); down = true; sx = ev.clientX; sy = ev.clientY; dir = null;
        try { g.setPointerCapture(ev.pointerId); } catch (err) {}
      });
      g.addEventListener("pointermove", function (ev) {
        if (!down) return;
        if (ev.cancelable) ev.preventDefault();
        var fb2 = forkbox.getBoundingClientRect();
        var st = fromSpot((ev.clientX - sx) / FSCALE, (ev.clientY - sy) / FSCALE);
        var hold2 = ghost; ghost = g; place(fb2.left + fb2.width / 2 + st.x * FSCALE, fb2.top + (185 + st.y) * FSCALE, cw * FSCALE, ch * FSCALE); ghost = hold2;
        g._hit = st.hit;
      });
      var up = function () {
        if (!down) return;
        down = false;
        if (g._hit) { var t = g._hit.tier; g._hit = null; takeIn(g, g._card, t); }
        else { dir = null; fromSpot(0, 0); park(g); }
      };
      g.addEventListener("pointerup", up);
      g.addEventListener("pointercancel", up);
    }
    function letGo(e) {
      if (!card) return;
      if (!live) { card = null; return; }
      try { box.releasePointerCapture(pid); } catch (err) {}
      var g = ghost, c = card, z = over;
      if (raf) { cancelAnimationFrame(raf); raf = 0; }
      place(cur.x, cur.y, cur.w, cur.h);
      g._card = c; g.dataset.id = id; g._w0 = w0; g._h0 = h0;
      if (z) takeIn(g, c, z.tier);
      else if (stage === 1) park(g);
      else sendHome(g);
      card = null; live = false; decided = false; over = null;
    }
    box.addEventListener("pointerup", letGo);
    box.addEventListener("pointercancel", letGo);
  }
  function qcard(r, rank, rec) {
    var club = String(r.club || ""), w, l;
    if (rec) {
      w = (rec[club] || [0, 0])[0];
      l = (rec[club] || [0, 0])[1];
    } else {
      /* one week: the club's own result that week, not the season's record */
      w = r.ml === "W" ? 1 : 0;
      l = r.ml === "L" ? 1 : 0;
    }
    var face = /^\d+$/.test(r.id)
      ? '<img class="qbface qbface--card" data-ring="' + r.id + '" alt="" loading="lazy" src="face/nfl/' +
        r.id + '.png" onerror="this.onerror=null;this.src=NOFACE">'
      : '<img class="qbface qbface--card" alt="" src="' + NOFACE + '">';
    return '<article class="qcard' + (RINGED[String(r.id)] ? " qcard--gold" : "") + (r.bench ? " qcard--bench" : "") + '">' +
      '<div class="qface" style="--hue:' + cardHue(club) + ';--mark:url(logos/nfl/' +
        club.toLowerCase() + '.png)">' + face +
        '<span class="qrank">' + rank + "</span></div>" +
      '<div class="qside">' +
        qline(CHIPW, "Club wins", w) + qline(CHIPL, "Club losses", l) +
        qline(BALLSVG, "Passing touchdowns", r.ptd) +
        qline(RUSHSVG, "Rushing touchdowns", r.atd) +
        qline(VSMARK, "Head to head", r.h2hw === undefined ? (r.h2h === "W" ? 1 : 0) : r.h2hw) +
      "</div>" +
      '<footer class="qname"><h3>' + esc(famName(r.name)) + "</h3>" +
        '<small class="qrec">' + w + "-" + l + "</small>" +
        (String(rank).indexOf("hurt--corner") >= 0 ? "" : hurtMark(r.id)) + coldMark(r.id) + "</footer>" +
      "</article>";
  }
  /* ---- Clips ---- */
  var QBCLIPS = null;
  var STARSVG = function (on) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"><polygon points="12,2 15,9 22,9.5 16.5,14 18.5,21 12,17 5.5,21 7.5,14 2,9.5 9,9" ' +
      (on ? 'fill="#fff"' : 'fill="none" stroke="#8e8e93" stroke-width="1.8"') + '/></svg>';
  };
  function clipSeen() { try { return JSON.parse(localStorage.getItem("arena.clipseen") || "{}") || {}; } catch (e) { return {}; } }
  function clipKey(c) { return c.gid + "|" + c.text; }
  /* the ranked men first, in HOT's order -- the field is parked and its
     ranking is what the clips page opens on (Jose, Oct 6, 2026: "the number
     one clip, number two, then everything else") -- then everyone else,
     favorites first */
  var CLIPRANK = null;
  function clipOrder() {
    var st = window.STARS || {};
    var has = function (id) { return QBCLIPS[id] && (QBCLIPS[id].clips || []).length; };
    var top = (CLIPRANK || []).filter(has);
    var rest = Object.keys(QBCLIPS || {}).filter(function (id) { return has(id) && top.indexOf(id) < 0; })
      .sort(function (a, b) {
        var sa = st[a] ? 0 : 1, sb = st[b] ? 0 : 1;
        return sa - sb || QBCLIPS[b].clips.length - QBCLIPS[a].clips.length;
      });
    clipOrder.top = top.length;
    return top.concat(rest);
  }
  function renderClips(rank) {
    if (rank) CLIPRANK = rank.map(String).slice(0, 12);
    document.documentElement.classList.add("clipsview");
    window.scrollTo(0, 0);
    var page = document.createElement("div");
    page.className = "clipspage";
    BOARD.appendChild(page);
    var draw = function () {
      var seen = clipSeen(), st = window.STARS || {};
      var all = clipOrder(), n = clipOrder.top;
      var tile = function (id, i) {
        /* gold is a favorite, the way the search row marks one; the rest are
           grey and sit behind them (Jose, Sep 29, 2026) */
        var q = QBCLIPS[id];
        return '<button type="button" class="cliptile' + (st[id] ? "" : " seen") + '" data-qb="' + id + '">' +
          '<span class="cring"><span class="cface" style="background-image:url(face/nfl/' + id + '.png)"></span>' +
          (i < n ? '<span class="crank">' + (i + 1) + '</span>' : "") +
          '<span class="cstar" data-star="' + id + '">' + STARSVG(!!st[id]) + '</span></span>' +
          '<span class="cname">' + esc(famName(q.name)) + '</span></button>';
      };
      page.innerHTML = (n ? '<h3 class="cliphead">Top QBs</h3><div class="cliprow">' + all.slice(0, n).map(tile).join("") + "</div>" : "") +
        (all.length > n ? '<h3 class="cliphead">' + "Around the League" + '</h3><div class="cliprow">' +
          all.slice(n).map(function (id, j) { return tile(id, n + j); }).join("") + "</div>" : "") + clipHow();
    };
    if (QBCLIPS) draw();
    else fetch("qbclips.json", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(function (j) { QBCLIPS = j || {}; draw(); }).catch(function () { page.innerHTML = ""; });
    /* a star set in the search, or on another device, repaints the row */
    window.clipsDraw = function () { if (page.isConnected && QBCLIPS) draw(); };
    page.addEventListener("click", function (e) {
      var s0 = e.target.closest("[data-star]");
      if (s0) {
        /* the same stars the search row keeps, synced like every mark */
        e.stopPropagation();
        var id = s0.dataset.star, st = window.STARS || (window.STARS = {});
        if (st[id]) delete st[id]; else st[id] = 1;
        try { localStorage.setItem("arena.stars", JSON.stringify(st)); } catch (e2) {}
        if (typeof pushState === "function") pushState();
        if (window.qsRow) window.qsRow();
        draw();
        return;
      }
      var t = e.target.closest(".cliptile");
      if (t) clipStories(clipOrder(), clipOrder().indexOf(t.dataset.qb), draw);
    });
  }
  /* a week on Stacked: the games as tiles across the top, a tap plays that
     game's touchdowns in the order they happened, both passers mixed; a
     swipe sideways is the next or last game (Jose, Sep 29, 2026) */
  function renderWeekClips() {
    document.documentElement.classList.add("clipsview");
    window.scrollTo(0, 0);
    var page = document.createElement("div");
    page.className = "clipspage";
    BOARD.appendChild(page);
    var rows = formRows(), games = {};
    rows.forEach(function (r) { if (r.game) (games[r.game] = games[r.game] || []).push(r); });
    var when = {};
    SCHED.forEach(function (g) { when[String(g[1])] = g[2]; });
    var order = Object.keys(games).sort(function (a, b) { return String(when[a] || "") < String(when[b] || "") ? -1 : 1; });
    /* the game's clips, both men's, in the order the plays came */
    var pool = function () {
      var out = {};
      Object.keys(QBCLIPS || {}).forEach(function (id) {
        (QBCLIPS[id].clips || []).forEach(function (c) {
          if (!games[c.gid]) return;
          var g = out[c.gid] || (out[c.gid] = { name: "", clips: [] });
          g.clips.push(Object.assign({ qb: id, who: QBCLIPS[id].name }, c));
        });
      });
      Object.keys(out).forEach(function (gid) { out[gid].clips.sort(function (a, b) { return (a.seq || 0) - (b.seq || 0); }); });
      return out;
    };
    var draw = function () {
      var P = pool();
      var side = function (m, other, which) {
        var face = /^\d+$/.test(String(m.id))
          ? '<img class="qbface mface" alt="" loading="lazy" src="face/nfl/' + m.id + '.png" onerror="this.onerror=null;this.src=NOFACE">'
          : '<img class="qbface mface" alt="" src="' + NOFACE + '">';
        var has = m.score !== undefined && m.score !== null && other.score !== undefined && other.score !== null;
        var won = has && m.score > other.score;
        return '<span class="mside mside--' + which + '" style="--hue:' + cardHue(String(m.club || "")) +
          ';--mark:url(logos/nfl/' + String(m.club || "").toLowerCase() + '.png)">' + face +
          '<b class="mscore mscore--' + which + (won ? " won" : "") + '">' + (has ? m.score : "") + '</b>' +
          '<span class="mname">' + esc(famName(m.name)) + '</span></span>';
      };
      page.innerHTML = '<div class="gamerow">' + order.map(function (gid) {
        /* the man the board priced on each side; the road man on the left,
           the home man on the right */
        var all = games[gid].slice(), pair = all.filter(function (r) { return r.carded; });
        if (pair.length < 2) pair = all.slice(0, 2);
        pair.sort(function (a, b) { return (a.side || 0) - (b.side || 0); });
        var L = pair[0], R = pair[1] || { name: "", club: "", id: "", score: null };
        return '<button type="button" class="gtile' + (P[gid] ? " has" : "") + '" data-game="' + gid + '">' +
          side(L, R, "l") + side(R, L, "r") + '</button>';
      }).join("") + "</div>" + clipHow();
    };
    if (QBCLIPS) draw();
    else fetch("qbclips.json", { cache: "no-store" }).then(function (r) { return r.json(); })
      .then(function (j) { QBCLIPS = j || {}; draw(); }).catch(function () { QBCLIPS = QBCLIPS || {}; draw(); });
    page.addEventListener("click", function (e) {
      var t = e.target.closest(".gtile");
      if (!t) return;
      var P = pool(), run = order.filter(function (gid) { return P[gid]; });
      if (P[t.dataset.game]) clipStories(run, run.indexOf(t.dataset.game), draw, P);
    });
  }
  /* his season, one touchdown after another, as stories: tap for the next,
     hold to pause, the left edge for the one before, a swipe sideways for
     the next or last passer, a swipe down to close (Jose, Sep 29, 2026) */
  /* one hand for all five -- index up, three fingers curled, the thumb --
     only the gold mark changes (Jose, Oct 6, 2026: "some have 5 fingers,
     some have 2-3"; Oct 6 again: the first one read like a middle finger --
     now a foam finger, our own drawing, after his picture) */
  /* traced from the foam fingers he sent: the front of the hand for the
     taps and the hold, the back of it for the swipes */
  var HAND = '<g transform="translate(12 47.00) scale(0.00813 -0.00813)" fill="#fff" stroke="#fff" stroke-width="110"><path d="M662 4866 c-81 -27 -138 -77 -170 -150 -36 -82 -67 -437 -92 -1056 -16 -400 -20 -527 -30 -906 l-10 -362 -83 -130 c-46 -72 -119 -200 -162 -285 l-78 -154 12 -104 c57 -476 264 -981 495 -1209 l66 -64 0 -187 c0 -157 3 -190 16 -203 20 -21 1991 -25 2012 -4 9 9 12 91 12 306 l0 293 54 67 c214 268 280 550 256 1102 -6 145 -5 164 22 295 37 185 38 295 4 346 -84 123 -391 198 -502 123 -45 -31 -44 -32 -44 22 0 71 -19 129 -56 173 -90 104 -339 162 -467 108 -50 -21 -52 -21 -55 27 -12 176 -79 247 -282 302 -91 25 -283 26 -327 2 l-31 -18 -6 103 c-3 56 -13 237 -21 402 -31 588 -63 922 -95 986 -72 139 -285 225 -438 175z m211 -116 c55 -21 109 -65 132 -109 33 -66 96 -950 99 -1391 l1 -255 -35 -124 -35 -124 -150 -37 c-207 -52 -337 -103 -379 -149 -34 -37 -37 -25 -32 107 3 70 8 226 11 347 18 698 55 1390 86 1575 27 161 140 220 302 160z m718 -1649 c36 -11 84 -34 106 -50 90 -65 81 -227 -42 -746 -70 -296 -94 -355 -164 -402 -58 -39 -172 -30 -319 24 l-43 16 68 36 c244 128 365 309 365 541 0 108 -24 227 -50 246 -19 15 -194 18 -295 5 -32 -4 -59 -6 -61 -4 -10 10 53 222 84 284 37 72 61 82 180 76 65 -3 130 -13 171 -26z m564 -317 c148 -38 177 -78 176 -237 -1 -177 -23 -313 -92 -552 -98 -343 -135 -382 -327 -341 -153 32 -213 85 -220 191 -7 105 41 358 124 655 81 288 139 337 339 284z m-712 -128 c14 -35 18 -156 8 -211 -38 -204 -182 -339 -471 -439 -125 -44 -127 -46 -135 -104 -10 -72 -34 -161 -61 -224 -13 -32 -24 -62 -24 -68 0 -22 41 -50 72 -50 90 -1 266 -59 304 -101 27 -30 82 -26 94 7 24 62 -88 141 -256 180 -41 10 -74 20 -73 23 0 3 13 53 28 111 32 123 22 119 161 65 212 -83 348 -96 444 -42 l46 26 6 -40 c15 -89 103 -178 219 -220 91 -32 275 -38 329 -10 22 11 40 20 41 18 1 -1 9 -21 20 -45 47 -108 206 -182 393 -182 97 0 139 15 175 62 23 30 63 110 81 162 15 43 17 0 7 -137 -23 -313 -76 -460 -237 -657 l-64 -79 -2 -278 -3 -278 -912 -3 -912 -2 -3 177 -3 178 -95 95 c-214 215 -392 640 -457 1089 l-18 123 70 135 c118 227 288 481 365 547 62 52 351 140 557 170 135 19 299 21 306 2z m1282 -166 c98 -25 158 -60 175 -100 18 -44 -8 -208 -75 -477 -98 -384 -123 -443 -197 -457 -101 -20 -281 38 -327 105 -34 50 -24 138 48 420 136 531 160 564 376 509z"/></g>';
  var HANDB = '<g transform="translate(12 47.00) scale(0.00813 -0.00813)" fill="#fff" stroke="#fff" stroke-width="110"><path d="M2182 4864 c-138 -37 -230 -130 -252 -257 -22 -124 -73 -837 -86 -1213 l-7 -192 -36 16 c-58 26 -245 22 -341 -7 -197 -60 -260 -128 -260 -282 0 -70 -3 -73 -53 -47 -148 75 -451 -18 -512 -157 -7 -16 -16 -61 -20 -98 -7 -64 -8 -67 -25 -52 -92 83 -393 27 -502 -93 -59 -65 -62 -149 -13 -379 22 -107 23 -126 18 -346 -9 -362 17 -582 91 -763 36 -88 144 -260 190 -303 l26 -24 0 -298 c0 -257 2 -300 16 -313 21 -22 1994 -25 2012 -3 7 8 12 83 12 201 l2 189 53 51 c101 97 207 253 280 412 113 243 218 627 231 839 l6 90 -45 91 c-60 122 -126 237 -207 364 l-67 105 -12 455 c-24 950 -62 1626 -102 1808 -36 170 -206 258 -397 206z m208 -116 c58 -30 79 -69 95 -177 36 -236 72 -986 93 -1896 l8 -320 70 -105 c81 -121 168 -272 218 -380 39 -85 39 -102 -4 -317 -83 -419 -249 -781 -449 -978 l-81 -79 -2 -176 -3 -175 -912 -3 -913 -2 0 273 0 274 -30 39 c-16 21 -52 68 -80 104 -86 111 -146 251 -177 410 -14 68 -17 154 -19 430 -1 315 -3 354 -23 445 -33 150 -39 269 -15 296 47 53 208 105 297 96 83 -7 127 -72 183 -267 32 -113 38 -122 78 -118 48 5 57 35 35 118 -47 180 -52 419 -9 465 75 80 278 123 357 76 54 -34 99 -128 144 -306 23 -88 40 -115 75 -115 52 0 57 34 24 164 -49 197 -63 434 -30 497 29 54 185 103 328 104 l114 0 24 -30 c13 -16 34 -55 45 -85 17 -48 24 -56 48 -58 59 -4 61 2 66 243 11 516 69 1344 101 1432 42 117 226 181 344 121z"/></g>';
  var HANDS = {
    tap: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' + HAND + '<path stroke="#e3b341" d="M18.3 0.8v3M12.5 2.5l2 2M24 2.5l-2 2"/></svg>',
    hold: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' + HAND + '<path stroke="#e3b341" d="M15 5.2a3.3 3.3 0 0 1 6.6 0M12.5 5.6a5.8 5.8 0 0 1 11.6 0"/></svg>',
    back: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' + HAND + '<path stroke="#e3b341" d="M6 10v32M18.3 0.8v3M12.5 2.5l2 2M24 2.5l-2 2"/></svg>',
    swipe: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' + HANDB + '<path stroke="#e3b341" d="M20 5c7.5-3 15.5-3 23 0M20 5l1.4-3.3M20 5l3.5 1M43 5l-1.4-3.3M43 5l-3.5 1"/></svg>',
    down: '<svg viewBox="0 0 48 48" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">' + HANDB + '<path stroke="#e3b341" d="M6.5 12v24M6.5 36l-3-3M6.5 36l3-3"/></svg>'
  };





  /* the five gestures, on the how-to and under every clips row */
  function clipHow() {
    return '<div class="cliphow">' + [[HANDS.tap, "Go forward", "Tap the screen"], [HANDS.hold, "Pause", "Press and hold"],
      [HANDS.back, "Go back", "Tap the left edge"], [HANDS.swipe, "Move between stories", "Swipe left or right"],
      [HANDS.down, "Leave", "Swipe down"]]
      .map(function (r) { return '<div class="crow">' + r[0] + '<div><b>' + r[1] + '</b><span>' + r[2] + '</span></div></div>'; }).join("") + '</div>';
  }
  function clipStories(order, qi, after, pool) {
    var POOL = pool || QBCLIPS;
    var box = document.getElementById("clipstory");
    if (!box) {
      box = document.createElement("div"); box.id = "clipstory"; box.hidden = true;
      /* two players, one behind the other: while one clip plays the next is
         already loading in the other, so the change is a cut, not a wait
         (Jose, Sep 29, 2026: "it's not smooth at all"). Muted from the start,
         which a phone always lets play; the speaker turns sound on. */
      box.innerHTML = '<video class="cv" playsinline muted autoplay preload="auto"></video>' +
        '<video class="cv cv--back" playsinline muted preload="auto"></video>' +
        '<div class="cbars"></div><div class="cwho"></div><button type="button" class="csound" aria-label="Sound"></button>';
      document.body.appendChild(box);
    }
    var how = document.getElementById("clipshow");
    var shown = false;
    try { shown = localStorage.getItem("arena.clipshow") === "1"; } catch (e) {}
    var vids = box.querySelectorAll("video"), cur = vids[0], nxt = vids[1];
    var bars = box.querySelector(".cbars"), who = box.querySelector(".cwho"), snd = box.querySelector(".csound");
    var muted = true;
    var SPK = function (on) {
      return '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" fill="#fff"/>' +
        (on ? '<path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" stroke="#fff" stroke-width="2" fill="none" stroke-linecap="round"/>'
            : '<path d="M16 9l5 6M21 9l-5 6" stroke="#fff" stroke-width="2" stroke-linecap="round"/>') + '</svg>';
    };
    cur.muted = nxt.muted = true;
    snd.innerHTML = SPK(false);
    snd.onpointerdown = function (e) { e.stopPropagation(); };
    snd.onpointerup = function (e) { e.stopPropagation(); };
    snd.onclick = function (e) {
      e.stopPropagation();
      muted = !muted; cur.muted = muted; snd.innerHTML = SPK(!muted);
      cur.play().catch(function () {});
    };
    var ci = 0, alive = true;
    var close = function () {
      alive = false;
      [cur, nxt].forEach(function (v) { v.pause(); v.removeAttribute("src"); v.load(); v.dataset.for = ""; });
      box.hidden = true;
      document.documentElement.classList.remove("cashlock");
      if (after) after();
    };
    /* each clip's link, asked once and kept for ten minutes (nfl.com signs
       them for fifteen), and the sharpest rendition when there is one */
    var LINKS = clipStories._links || (clipStories._links = {});
    var urlOf = function (c) {
      if (c.src) return Promise.resolve(c.src);
      var k = clipKey(c), got = LINKS[k];
      if (got && Date.now() - got.at < 600000) return got.p;
      var ask = c.mcp ? "clip?mcp=" + encodeURIComponent(c.mcp) : "clip?game=" + encodeURIComponent(c.gid) + "&ext=" + encodeURIComponent(c.ext);
      var p = fetch(ask).then(function (r) { return r.json(); }).then(function (j) { return j.best || j.accessUrl || ""; });
      p.catch(function () { delete LINKS[k]; });
      LINKS[k] = { at: Date.now(), p: p };
      return p;
    };
    /* the clip at a place in the run, rolling over to the next passer */
    var at = function (q, c) {
      if (q < 0) return null;
      while (q < order.length) {
        var list = POOL[order[q]].clips;
        if (c < list.length) return { q: q, c: c, clip: list[c], key: q + ":" + c };
        q++; c = 0;
      }
      return null;
    };
    var q0name = function () { var q = POOL[order[qi]]; return q ? famName(q.name) : ""; };
    /* each clip reports how it went (Sep 29, 2026) */
    var report = function (c, how, extra) {
      try {
        fetch("push", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ cliplog: Object.assign({
          how: how, qb: q0name(), gid: c.gid, kind: c.kind, from: c.src ? "x" : c.mcp ? "club" : "nfl",
          err: cur.error ? cur.error.code : null, ready: cur.readyState, net: cur.networkState, t: +cur.currentTime.toFixed(1),
          ua: navigator.userAgent.slice(0, 60) }, extra || {}) }) });
      } catch (e) {}
    };
    /* the next clip, loaded in the back player while this one plays */
    var preload = function () {
      var n = at(qi, ci + 1);
      if (!n || nxt.dataset.for === n.key) return;
      nxt.dataset.for = n.key;
      urlOf(n.clip).then(function (u) {
        if (!alive || nxt.dataset.for !== n.key || !u) return;
        nxt.src = u; nxt.load();
      }).catch(function () {});
      // and the one after, asked for now so its link is ready
      var n2 = at(qi, ci + 2);
      if (n2) urlOf(n2.clip).catch(function () {});
    };
    var watch = function (want, c) {
      clearTimeout(box._kick); clearTimeout(box._skip);
      box._kick = setTimeout(function () {
        if (box.dataset.want === want && alive && cur.currentTime < 0.1 && !box._held) cur.play().catch(function () {});
      }, 2500);
      box._skip = setTimeout(function () {
        if (box.dataset.want === want && alive && cur.currentTime < 0.1 && !box._held) { report(c, "stuck"); ci++; play(); }
      }, 9000);
    };
    var play = function () {
      if (!alive) return;
      if (ci < 0) { if (qi > 0) { qi--; ci = POOL[order[qi]].clips.length - 1; } else ci = 0; }
      var here = at(qi, ci);
      if (!here) { close(); return; }
      qi = here.q; ci = here.c;
      var q = POOL[order[qi]], list = q.clips, c = here.clip;
      bars.innerHTML = list.map(function (x, i) { return '<i><b style="width:' + (i < ci ? 100 : 0) + '%"></b></i>'; }).join("");
      /* a game's story names the man who scored each one */
      who.innerHTML = '<i style="background-image:url(face/nfl/' + (c.qb || order[qi]) + '.png)"></i>' + esc(famName(c.who || q.name));
      var seen = clipSeen(); seen[clipKey(c)] = 1;
      try { localStorage.setItem("arena.clipseen", JSON.stringify(seen)); } catch (e) {}
      var want = here.key;
      box.dataset.want = want;
      cur.pause();
      if (nxt.dataset.for === want && nxt.getAttribute("src")) {
        /* already loaded behind: swap the two players, a straight cut */
        var t = cur; cur = nxt; nxt = t;
        cur.classList.remove("cv--back"); nxt.classList.add("cv--back");
        nxt.dataset.for = "";
        cur.muted = muted;
        try { if (cur.currentTime > 0) cur.currentTime = 0; } catch (e) {}
        cur.play().catch(function () {});
        watch(want, c);
        preload();
        return;
      }
      urlOf(c).then(function (u) {
        if (box.dataset.want !== want || !alive) return;
        if (!u) { report(c, "nolink"); ci++; play(); return; }
        cur.src = u; cur.dataset.for = want; cur.load(); cur.muted = muted;
        cur.play().catch(function () {});
        watch(want, c);
        preload();
      }).catch(function () { ci++; play(); });
    };
    [cur, nxt].forEach(function (v) {
      v.ontimeupdate = function () {
        if (v !== cur) return;
        var b = bars.querySelectorAll("b")[ci];
        if (b && v.duration) b.style.width = (v.currentTime / v.duration * 100).toFixed(1) + "%";
      };
      v.onended = function () { if (v === cur) { ci++; play(); } };
      v.oncanplay = function () { if (v === cur && !box._held && v.paused) v.play().catch(function () {}); };
      v.onplaying = function () {
        if (v !== cur || v._told === box.dataset.want) return;
        v._told = box.dataset.want;
        var h = at(qi, ci); if (h) report(h.clip, "played");
      };
      v.onerror = function () {
        if (!alive || !v.getAttribute("src")) return;
        if (v === cur) {
          var h = at(qi, ci);
          if (h) report(h.clip, "error", { msg: v.error ? String(v.error.message || "").slice(0, 80) : "" });
          ci++; play();
        } else { v.dataset.for = ""; }
      };
    });
    /* the gestures */
    var x0 = 0, y0 = 0, held = false, holdT = null;
    box.onpointerdown = function (e) {
      x0 = e.clientX; y0 = e.clientY; held = false;
      holdT = setTimeout(function () { held = true; box._held = true; cur.pause(); }, 260);
    };
    box.onpointerup = function (e) {
      clearTimeout(holdT);
      var dx = e.clientX - x0, dy = e.clientY - y0;
      if (held) { held = false; box._held = false; cur.play().catch(function () {}); return; }
      if (dy > 90 && Math.abs(dy) > Math.abs(dx)) { close(); return; }
      if (Math.abs(dx) > 60) { qi += dx < 0 ? 1 : -1; ci = 0; if (qi < 0) qi = 0; if (qi >= order.length) { close(); return; } play(); return; }
      if (e.clientX < innerWidth * 0.25) ci--; else ci++;
      play();
    };
    var go = function () {
      box.hidden = false;
      document.documentElement.classList.add("cashlock");
      /* called inside his tap: both players are allowed to play from here on */
      try { cur.play().catch(function () {}); nxt.play().catch(function () {}); nxt.pause(); } catch (e) {}
      play();
    };
    if (shown) { go(); return; }
    if (!how) {
      how = document.createElement("div"); how.id = "clipshow";
      how.innerHTML = '<h2>Navigating Stories</h2><p class="sub">Use the following gestures to browse story content:</p>' +
        clipHow() + '<button type="button">Tap to Start</button>';
      document.body.appendChild(how);
    }
    how.hidden = false;
    how.querySelector("button").onclick = function () {
      how.hidden = true;
      try { localStorage.setItem("arena.clipshow", "1"); } catch (e) {}
      go();
    };
  }
  function renderMoney() {
    clearBoard();
    /* CLIPS ranks on the season's totals, so the rows are read as the season */
    var fw0 = formWeek;
    if (formWeek === "clips") formWeek = "season";
    var rows = moneyRows();
    formWeek = fw0;
    /* a man who came on in garbage time or for an injury is not a week's card:
       Pickett threw one and Bennett three (Jose, Sep 17, 2026) */
    rows = rows.filter(function (r) { return r.priced || r.ptd > 0 || r.atd > 0; });
    /* one per club: the man named for its next game, and a starter who has
       lost the job only because he is hurt -- Lock, who started while
       Darnold was out and is healthy, is not shown (Jose, Sep 28, 2026) */
    (function () {
      var now = Date.now(), next = {};
      (typeof SCHED === "object" ? SCHED : []).forEach(function (g) {
        var t = Date.parse(g[2]);
        if (t < now - 5 * 3600000) return;
        [[g[3], g[6], g[5]], [g[4], g[8], g[7]]].forEach(function (p) {
          if (!next[p[0]] || t < next[p[0]].t) next[p[0]] = { t: t, id: String(p[1]), name: p[2] };
        });
      });
      /* a man named to start who has not thrown yet this season still gets
         his club's card -- Keenum for the Bears (Jose, Sep 28, 2026) */
      Object.keys(next).forEach(function (club) {
        var nx = next[club];
        if (!nx.id || rows.some(function (m) { return String(m.id) === nx.id; })) return;
        rows.push({ name: nx.name, club: club, id: nx.id, ptd: 0, atd: 0, h2hw: 0, mlw: 0, legs: [],
                    units: 0, weeks: 0, played: 0, priced: false, agg: true });
      });
      /* marked, not dropped: only the All grid leaves them out -- HOT keeps
         every man (Jose, Sep 28, 2026: "I was talking about the All tab") */
      /* a man traded mid-season is carded by the club that names him for its
         next game, not the one his old games were for -- McCarthy to the
         Giants (Jose, Sep 28, 2026) */
      Object.keys(next).forEach(function (club) {
        rows.forEach(function (m) { if (String(m.id) === next[club].id) m.club = club; });
      });
      rows.forEach(function (m) {
        var nx = next[m.club];
        if (!nx || nx.id === String(m.id)) return;
        var w = WIRE[String(m.id)];
        /* hurt means hurt: "Out" for a coach's decision is a benching, and
           Rush, who lost the job to Penix, is not an injured starter (Jose,
           Sep 28, 2026: "why is Cooper Rush still there") */
        /* one card a club, 32 in all: a man who is not this week's starter
           is not shown, hurt or not -- his backup, who is starting, has the
           card. A starter who might still play keeps it with his plaster in
           the corner (Jose, Sep 28, 2026: "just 32") */
        m.bench = true;
      });
    })();
    /* Touchdowns first, thrown and run together, and the club's record only to
       split men who scored the same. Leading with the record put two men who
       had scored nothing above the best passer in the league, because their
       clubs won without them (Jose, Sep 21, 2026). */
    var rec = clubRec();
    var ofClub = clubRecOf;
    /* a man on the wire sinks to the foot whatever he has scored, and comes
       back into the order the moment ESPN lifts him -- nothing about the sort
       is remembered, so a clearance restores him by itself (Jose, Sep 21,
       2026: "once they are lifted they fall into the sorted") */
    rows.sort(function (a, b) {
      var ha = hurtAt(a.id) ? 1 : 0, hb = hurtAt(b.id) ? 1 : 0;
      if (ha !== hb) return ha - hb;
      var ta = (a.ptd || 0) + (a.atd || 0), tb = (b.ptd || 0) + (b.atd || 0);
      if (tb !== ta) return tb - ta;
      var ra = ofClub(a), rb = ofClub(b);
      if ((rb[0] - rb[1]) !== (ra[0] - ra[1])) return (rb[0] - rb[1]) - (ra[0] - ra[1]);
      if (rb[0] !== ra[0]) return rb[0] - ra[0];
      var ha = a.h2hw === undefined ? (a.h2h === "W" ? 1 : 0) : a.h2hw;
      var hb = b.h2hw === undefined ? (b.h2h === "W" ? 1 : 0) : b.h2hw;
      if (hb !== ha) return hb - ha;
      return a.name < b.name ? -1 : 1;
    });
    /* the field is parked: the season opens on the clips, in this order
       (Jose, Oct 6, 2026). Its code stays below, untouched, for when it comes
       back -- set window.HOTFIELD = true to see it. */
    if (formWeek === "clips" || (formWeek === "season" && !window.HOTFIELD)) {
      document.documentElement.classList.remove("hotlock");
      renderClips(rows.filter(function (r) { return !r.bench && !hurtAt(r.id); }).map(function (r) { return r.id; }));
      return;
    }
    var box = document.createElement("div");
    box.className = "form money";
    if (!rows.length) {
      box.innerHTML = '<p class="formnote">Nothing settled yet.</p>';
      BOARD.appendChild(box); return;
    }
    /* the season is the passers' cards; a week keeps its own matchup card,
       which is a different thing and reads better as it is (Jose, Sep 21,
       2026: "no week 1 ledger") */
    var season = formWeek === "season";
    if (season) {
      /* the four squares, and the view they pick is kept on the device */
      var FVIEWS = [["all", "All"], ["hot", "Hot"], ["not", "Not"], ["out", "Out"]];
      var fv = "hot";
      try { fv = localStorage.getItem("arena.fview") || "hot"; } catch (e0) {}
      /* ALL is parked, not gone: its code stays, since the field's HOT, NOT
         and OUT are its lists, but it is never shown (Jose, Sep 29, 2026:
         "park it but keep the code") */
      if (fv === "all" || !FVIEWS.some(function (v) { return v[0] === fv; })) fv = "hot";
      var chips = document.createElement("div");
      chips.className = "fview";
      chips.innerHTML = FVIEWS.map(function (v) {
        return '<button type="button" data-fview="' + v[0] + '"' + (v[0] === "all" ? " hidden" : "") + ' aria-selected="' +
               (v[0] === fv ? "true" : "false") + '">' + v[1] + '</button>';
      }).join("") + '<span class="spmark"></span>';
      /* the glass mark slides to the open square, the way the nav's does */
      var fmark = chips.querySelector(".spmark");
      function seatF() {
        var t = chips.querySelector('button[aria-selected="true"]');
        if (!t) return;
        fmark.style.transform = "translateX(" + (t.offsetLeft + (t.offsetWidth - (fmark.offsetWidth || 57)) / 2) + "px)";
      }
      requestAnimationFrame(seatF);
      /* the mark rides the finger and snaps to the nearest square on the
         let go, the way the floating nav's does (Jose, Sep 23, 2026) */
      var fHold = false, fMoved = false;
      function fNear(x) {
        var best = null, gap = Infinity;
        chips.querySelectorAll("button[data-fview]").forEach(function (t) {
          var r = t.getBoundingClientRect(), d = Math.abs(x - (r.left + r.width / 2));
          if (d < gap) { gap = d; best = t; }
        });
        return best;
      }
      chips.addEventListener("pointerdown", function (e) {
        fHold = true; fMoved = false;
        fmark.classList.add("spmark--held");
        try { chips.setPointerCapture(e.pointerId); } catch (err) {}
      });
      chips.addEventListener("pointermove", function (e) {
        if (!fHold) return;
        if (!fMoved) { fMoved = true; fmark.classList.add("spmark--scrub"); }
        var b0 = chips.getBoundingClientRect(), w0 = fmark.offsetWidth || 57;
        var at = Math.max(4, Math.min(b0.width - w0 - 4, e.clientX - b0.left - w0 / 2));
        fmark.style.transform = "translateX(" + at + "px)";
        var t = fNear(e.clientX);
        chips.querySelectorAll("button[data-fview]").forEach(function (x) {
          x.setAttribute("aria-selected", x === t ? "true" : "false");
        });
      });
      function fLetGo(e) {
        if (!fHold) return;
        fHold = false;
        fmark.classList.remove("spmark--scrub", "spmark--held");
        if (fMoved) { var t = fNear(e.clientX); if (t) t.click(); }
        else seatF();
      }
      chips.addEventListener("pointerup", fLetGo);
      chips.addEventListener("pointercancel", fLetGo);
      box.className = "form qcards qcards--" + fv;
      /* the numbers count only the men the All grid shows: a benched or
         season-out man took a number while hidden, so Winston read 32 with
         29 before him (Jose, Sep 28, 2026) */
      var nShown = 0;
      box.innerHTML = rows.map(function (r) {
        /* a man on the wire has no number: his plaster takes its corner
           (Jose, Sep 28, 2026) */
        return qcard(r, r.bench ? "" : hurtAt(r.id) ? hurtMark(r.id).replace('class="hurt', 'class="hurt hurt--corner') : ++nShown, rec);
      }).join("");
      /* an odd count in a two-column view: the last card takes the middle */
      function soloLast() {
        var cards = [].slice.call(box.querySelectorAll(".qcard"));
        cards.forEach(function (c) { c.classList.remove("qcard--solo"); });
        var shown = cards.filter(function (c) { return getComputedStyle(c).display !== "none"; });
        if (shown.length % 2 === 1) shown[shown.length - 1].classList.add("qcard--solo");
      }
      requestAnimationFrame(soloLast);
      chips.addEventListener("click", function (e) {
        var t = e.target.closest("button[data-fview]");
        if (!t) return;
        fv = t.dataset.fview;
        try { localStorage.setItem("arena.fview", fv); } catch (e1) {}
        chips.querySelectorAll("button").forEach(function (x) {
          x.setAttribute("aria-selected", x === t ? "true" : "false");
        });
        box.className = "form qcards qcards--" + fv;
        box.scrollLeft = 0;                 /* a filter starts at its first card */
        loopRow(box);
        soloLast();
        seatF();
      });
      BOARD.appendChild(box);
      /* the second bar, under the row */
      var PTDS = [["1", "1 PTD"], ["2", "2 PTD"]];
      var pv = "1";
      try { pv = localStorage.getItem("arena.fptd") || "1"; } catch (e2) {}
      var ptdbar = document.createElement("div");
      ptdbar.className = "fview fview--ptd";
      ptdbar.innerHTML = PTDS.map(function (v) {
        return '<button type="button" data-fptd="' + v[0] + '" aria-selected="' +
               (v[0] === pv ? "true" : "false") + '">' + v[1] + '</button>';
      }).join("");
      /* no square behind the one that is on: the words alone, the open one
         in ink (Jose, Sep 23, 2026: "get rid of the buttons in there too but
         keep the text") */
      function seatP() {}

      /* HOT reads top to bottom: the four squares, then 1 PTD / 2 PTD, then
         the carousel (Jose, Sep 23, 2026: "the order for the hot tab is the
         regular all/hot/not/out, 1 PTD and 2 PTD, then carousel"). The tier
         keeps the hot passers who have thrown at least that many in every
         game they have played -- read off the season, touchdowns against
         games -- until Jose says what else it should mean. */
      /* the two words are labels, not buttons: static, white, nothing happens
         on a tap (Jose, Sep 23, 2026: "make sure the 1 PTD and 2 PTD are not
         clickable, they need to be static white") */
      var slots = document.createElement("div");
      slots.className = "fslots";
      slots.innerHTML = "<i></i><i></i><i></i><i></i><i></i><i></i><i></i><i></i>";
      var fup = document.createElement("div");
      fup.className = "fup";
      fup.innerHTML = "<i><b></b><b></b></i><i><b></b><b></b></i>";
      var tube = document.createElement("div");
      tube.className = "ftube";
      /* only under HOT (Jose, Sep 23, 2026: "sorry, only for hot") */
      ptdbar.hidden = tube.hidden = fup.hidden = slots.hidden = fv !== "hot";
      chips.addEventListener("click", function () {
        ptdbar.hidden = tube.hidden = fup.hidden = slots.hidden = fv !== "hot";
        if (!ptdbar.hidden) requestAnimationFrame(seatP);
      });
      var forkbox = document.createElement("div");
      forkbox.className = "forkbox" + (fv === "hot" ? " fork-on" : "");
      forkbox.innerHTML = '<div class="forkwrap"><div class="fork"></div></div>';
      chips.addEventListener("click", function () { forkbox.classList.toggle("fork-on", fv === "hot"); });
      forkbox.appendChild(fup);
      var routes = document.createElement("div");
      routes.className = "froutes";
      routes.style.backgroundImage = 'url("data:image/svg+xml;utf8,' + encodeURIComponent(routeSvg()) + '")';
      routes.innerHTML = ROUTES.map(function (r) {
        return '<span class="froute" data-tier="' + r.tier + '" style="left:' + (210 + r.at[0]) +
               'px;top:' + r.at[1] + 'px;color:' + r.color + '">' + r.label + '</span>';
      }).join("");
      forkbox.appendChild(routes);
      RECEIVERS.forEach(function (r, k) {
        var im = document.createElement("img");
        im.className = "fwr"; im.alt = ""; im.dataset.k = k;
        im.style.left = (137 + r[0][0]) + "px"; im.style.top = r[0][1] + "px";
        forkbox.appendChild(im);
      });
      forkbox.appendChild(ptdbar);
      forkbox.appendChild(tube);
      /* the top nav, then the eight across the page's own width, then the
         fork (Jose, Sep 23, 2026: "the 8 are the entire page width with a
         little padding... the page, not the website") */
      BOARD.insertBefore(chips, box);
      /* the field under the picks and the goalpost: the end zone is the pick
         row's own height, and forty yards run from its goal line down to the
         cards (Jose, Sep 23, 2026: "40 yards of field, the end zone the size
         of the indicators with the players in there, and the T still
         there") */
      var turf = document.createElement("div");
      turf.className = "fturf";
      turf.appendChild(slots);
      turf.appendChild(forkbox);
      BOARD.insertBefore(turf, box);
      turf.hidden = fv !== "hot";
      /* HOT fits the screen: the page does not scroll under it, so a drag is
         only ever a drag (Jose, Sep 23, 2026: "remove the scroll from the hot
         tab") */
      var lockHot = function () {
        var on = fv === "hot" && document.body.contains(chips);
        document.documentElement.classList.toggle("hotlock", on);
        if (on) window.scrollTo(0, 0);
        centerHot();
      };
      /* the field and the carousel sit in the middle, equal space to the top
         and to the nav (Jose, Sep 23, 2026) */
      /* HOT is laid on the FOX field behind it (img/fox-field.jpg, 768 x
         1361, drawn to cover the screen from its middle): the picks stand in
         the end zone at the goal line, and the carousel shrinks to sit
         between the two near yard lines (Jose, Sep 25, 2026: "QBs end up
         here when selected", "the carousel goes there") */
      var FIELD = { w: 768, h: 1361, goal: 712, band: [1050, 1245], board: [318, 261, 440, 383] };
      /* the carousel's one size, for the whole visit: HOT is built again when
         his saved marks arrive, and a size kept per build was lost with the
         old one -- the new row came up full size behind the slip (Jose,
         Sep 28, 2026). It is laid on the page as --hotz, so any row built
         later wears it from its first frame. */
      var HOTZ = window._hotz || 0;
      var centerHot = function () {
        requestAnimationFrame(function () {
          turf.style.marginTop = "";
          box.style.marginTop = "";
          /* off the field the cards are their own size again: HOT's size
             stayed on them and squashed the grid (Jose, Sep 28, 2026) */
          if (turf.hidden || !document.body.contains(turf)) { box.style.zoom = ""; return; }
          var W = window.innerWidth, H = window.innerHeight;
          /* as large as covers the screen, but never so large that the card
             band falls behind the nav: then the field stops a little short
             of the bottom, where the nav covers it anyway */
          var navTop = document.getElementById("sportbar").getBoundingClientRect().top;
          var k = Math.min(Math.max(W / FIELD.w, H / FIELD.h), (navTop - 12) / FIELD.band[1]);
          /* the field is never so tall that the card band falls behind the
             nav: on a short phone, an iPad or a desktop it stops at the height
             that fits and stands centered, dark either side, rather than
             pushing the row under the nav and off the screen (audit, Sep 28,
             2026: HOT could not be reached at 1280 or 375x667) */
          var FW = Math.min(W, FIELD.w * k);
          /* the field, and everything standing on it, lifted as one so the
             carousel and the sets under it sit clear above the betslip bar
             (or the nav when there is no slip) -- the same size, the same
             places on the field (Jose, Sep 27, 2026: "the icons and carousel
             sit above the bet slip") */
          var slipEl = document.getElementById("slipbar");
          var floor = slipEl && !slipEl.hidden && slipEl.getBoundingClientRect().height
            ? slipEl.getBoundingClientRect().top : navTop;
          /* the line the icons stand on clears the slip by their own height,
             so none of them is ever behind it (Jose, Sep 28, 2026) */
          var clear = (slipEl && !slipEl.hidden && slipEl.getBoundingClientRect().height) ? 26 : 10;
          /* the original field, in the original place, always: it never
             moves for the slip (Jose, Sep 28, 2026: "use the original field").
             The slip's own room is kept free below the cards instead, shown
             or not, so nothing shifts when it comes and goes */
          var oy = 0;
          var SLIPH = 76;
          var cardFloor = navTop - SLIPH - 8;
          document.documentElement.style.setProperty("--hotbg-w", Math.round(FIELD.w * k) + "px");
          document.documentElement.style.setProperty("--hotbg-y", oy + "px");
          /* the price the picks pay together is lit on the stadium's own
             scoreboard (Jose, Sep 25, 2026: "odds in the scoreboard") */
          var ox = (W - FIELD.w * k) / 2, sbd = FIELD.board, root = document.documentElement.style;
          var Y = function (y) { return oy + y * k; };
          /* the picks' row stands on the goal line */
          var sb = slots.getBoundingClientRect().bottom;
          turf.style.marginTop = Math.round(8 + Y(FIELD.goal) - sb) + "px";
          /* the scoreboard measured from the picks' own row, which is what
             the price is laid out in: the page's sliding track moves what a
             fixed position would be measured from */
          var sr = slots.getBoundingClientRect();
          /* twice the painted board's width, the same height, on its middle:
             drawn by us over the photo's, so a long price fits
             (Jose, Sep 25, 2026: "make the scoreboard wider") */
          var bw = (sbd[2] - sbd[0]) * k * 2, bcx = ox + (sbd[0] + sbd[2]) / 2 * k;
          /* the board is its own piece on the page, pinned over the photo's:
             nothing it sits inside can move or scale it */
          var brd = document.getElementById("hotboard");
          if (!brd) {
            brd = document.createElement("div"); brd.id = "hotboard"; document.body.appendChild(brd);
            /* the board is the price, and the price is the button: a tap puts
               the picks on the slip, as the old one did (Jose, Sep 25, 2026) */
            brd.addEventListener("click", function (e) {
              e.stopPropagation();
              var f3 = document.querySelector(".fturf .fslots .fpay");
              if (f3 && f3.textContent) f3.click();
            });
          }
          /* the mockup he picked: the black face the photo's height and 2.5
             times its width, a light-gray frame round it, the price large */
          var fw = (sbd[2] - sbd[0]) * k * 2.53, fh = (sbd[3] - sbd[1]) * k;
          var bx = Math.round(17.6 * k), by = Math.round(14.7 * k);
          brd.style.left = Math.round(bcx - fw / 2 - bx) + "px";
          brd.style.top = Math.round(oy + sbd[1] * k - by) + "px";
          brd.style.width = Math.round(fw) + "px";
          brd.style.height = Math.round(fh) + "px";
          brd.style.borderWidth = by + "px " + bx + "px";
          brd.style.fontSize = Math.round(47 * k) + "px";
          var fp = slots.querySelector(".fpay");
          brd.textContent = fp ? fp.textContent : "";
          brd.classList.toggle("on", !!(fp && fp.textContent));
          if (!slots._boardWatch) {
            slots._boardWatch = new MutationObserver(function () {
              var f2 = slots.querySelector(".fpay"), b2 = document.getElementById("hotboard");
              if (b2) { b2.textContent = f2 ? f2.textContent : ""; b2.classList.toggle("on", !!(f2 && f2.textContent)); }
            });
            slots._boardWatch.observe(slots, { childList: true, subtree: true, characterData: true });
          }
          /* the cards take one size and keep it: worked out the first time
             there is a card to measure, and never again -- a pass that found
             the row mid-rebuild used to reset them to full size, so they
             flipped big and small (Jose, Sep 28, 2026: "why are we doing
             resizing? ... never resize") */
          var top = Y(FIELD.band[0]), band = Y(FIELD.band[1]) - top;
          /* the room is what is left between the pick slot on the goal line
             and the icons above the line: nothing may overlap either */
          var floorY = Y(1239) - 44, ceilY = Math.max(top, slots.getBoundingClientRect().bottom + 8);
          var card = [].filter.call(box.querySelectorAll(".qcard"), function (c) { return c.getBoundingClientRect().height; })[0];
          var hs = hotSet();
          HOTZ = HOTZ || window._hotz || 0;
          if (card && !HOTZ) {
            var zNow = parseFloat(getComputedStyle(box).zoom) || 1;
            var natural = card.getBoundingClientRect().height / zNow;
            /* as tall as the band allows, and short enough to leave the sets
               their grass above the line */
            /* one size, always, worked out once: as tall as the room between
               the quarterback's spot and the top of the betslip, so the cards
               fill it (Jose, Sep 29, 2026: "make the containers this height,
               bottom on the line there and then the top of the bet slip") */
            var fb0 = forkbox.getBoundingClientRect();
            var roomNow = (cardFloor - 6) - (fb0.top + (185 + 27.5 + 2 + 14) * FSCALE + 10);
            HOTZ = window._hotz = Math.min(1, Math.max(0.1, roomNow) / natural);
            document.documentElement.style.setProperty("--hotz", HOTZ);
          }
          if (HOTZ) box.style.zoom = HOTZ;
          /* no card to measure yet: look again in a moment, never leave the
             row at full size */
          if (!HOTZ && (box._retry = (box._retry || 0) + 1) < 40) setTimeout(centerHot, 120);
          /* the stack, from the bottom up, never moving: the icons in their
             one place, the cards sitting right on top of them -- nothing above
             can push the cards down onto the icons (Jose, Sep 28, 2026) */
          hs.style.top = Math.round(Y(1239) - 22) + "px";
          if (card) {
            var z = HOTZ || 1, r = box.getBoundingClientRect();
            var iconTop = cardFloor;
            if (box.dataset.set) { delete box.dataset.set; loopRow(box); }
            /* the room is between the pick box (the bottom of the turf) and
               the icons. The cards fit in it: if they ever do not, they are
               made smaller once and keep that -- they never grow back, so
               nothing flips -- and they sit in the middle of it */
            /* the cards stand right under the quarterback's spot and his
               name, their own size, never on the icons (Jose, Sep 29, 2026:
               "move the carousel of the players below the QB placeholder") */
            var fbr = forkbox.getBoundingClientRect();
            var ceil = fbr.top + (185 + 27.5 + 2 + 14) * FSCALE + 10;
            var want = Math.min(ceil, iconTop - 6 - r.height);
            box.style.marginTop = ((parseFloat(getComputedStyle(box).marginTop) || 0) + (want - r.top) / z) + "px";
            if (box._seatFirst && !box._seated) { box._seated = true; box._seatFirst(); }
          }
        });
      };
      /* HOT, NOT and OUT, the long-press menu's own faces, centered */
      function hotSet() {
        var hs = document.getElementById("hotset");
        if (!hs) {
          hs = document.createElement("div"); hs.id = "hotset";
          document.body.appendChild(hs);
          hs.addEventListener("click", function (e) {
            var b = e.target.closest("button[data-set]");
            if (!b) return;
            e.stopPropagation();
            var cur = document.querySelector(".form.qcards.qcards--hot");
            if (!cur) return;
            if (b.dataset.set === "hot") delete cur.dataset.set; else cur.dataset.set = b.dataset.set;
            hs.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x === b ? "true" : "false"); });
            cur.scrollLeft = 0;
            cur._seated = false;         /* each set opens on its own first card */
            loopRow(cur);
            centerHot();
          });
        }
        if (!hs.firstChild) {
          var pop = document.querySelector(".fpop:not(.prail)");
          if (pop) hs.innerHTML = ["hot", "not", "out"].map(function (k) {
            var b0 = pop.querySelector('button[data-pv="' + k + '"]');
            return '<button type="button" data-set="' + k + '" aria-label="' + k.toUpperCase() + '" aria-pressed="' +
                   ((box.dataset.set || "hot") === k ? "true" : "false") + '">' + (b0 ? b0.innerHTML : k.toUpperCase()) + '</button>';
          }).join("");
        }
        var now = (document.querySelector(".form.qcards.qcards--hot") || box).dataset.set || "hot";
        hs.querySelectorAll("button").forEach(function (x) { x.setAttribute("aria-pressed", x.dataset.set === now ? "true" : "false"); });
        return hs;
      }
      window.addEventListener("resize", centerHot);
      lockHot();
      chips.addEventListener("click", lockHot);
      if (!window._hotUnlock) {
        window._hotUnlock = true;
        document.addEventListener("click", function () {
          requestAnimationFrame(function () {
            if (!document.querySelector(".fview .spmark") || !document.querySelector(".form.qcards.qcards--hot"))
              document.documentElement.classList.remove("hotlock");
          });
        }, true);
      }
      chips.addEventListener("click", function () {
        turf.hidden = fv !== "hot";
        if (!turf.hidden) requestAnimationFrame(function () { drawTurf(turf, slots); });
        centerHot();
      });
      requestAnimationFrame(function () { if (!turf.hidden) drawTurf(turf, slots); });
      /* opened straight onto HOT the box had no size yet on that first frame,
         and the field never drew; it is drawn whenever the box takes a size */
      if (window.ResizeObserver) new ResizeObserver(function () { if (!turf.hidden) drawTurf(turf, slots); }).observe(turf);
      window.addEventListener("resize", function () { if (!turf.hidden) drawTurf(turf, slots); });
      wirePick(box, slots, ptdbar, forkbox);
      /* everything in the eight, onto the slip -- the same slip, the same
         legs, as a tap on the board (Jose, Sep 23, 2026) */
      requestAnimationFrame(seatP);
      return;
    }
    box.innerHTML = rows.map(function (r, i) {
      var face = ledgerFace(r);
      var marks = season ? MTIMES(MBALL, r.ptd) + MTIMES(MRUN, r.atd) +
                           MTIMES(MVS, r.h2hw) + MTIMES(MML, r.mlw) : "";
      var n = (r.legs || []).length;
      /* what the week or the season was worth is off the row: the ticket
         still says how many legs he cleared, and the number itself stays in
         the file (Jose, Sep 21, 2026: "remove the units, leave the ticket") */
      var tick = '<span class="mtick' + (n ? "" : " mtick--none") + '" title="' +
        n + (n === 1 ? ' leg' : ' legs') + '">' +
        '<svg viewBox="0 0 26 18" aria-hidden="true"><use href="#ticket"/></svg></span>';
      return '<div class="frow mrow"><span class="frank">' + (i + 1) + '</span>' +
        '<span class="fwho">' + face + '<span class="fname">' + nameMark(r) +
        '<small>' + esc(r.club) + '</small></span></span>' +
        (marks ? '<span class="mmks">' + marks + tick + '</span>'
               : tick) + '</div>';
    }).join("");
    BOARD.appendChild(box);
  }
  /* a club's record, wherever it is wanted: the season ranks on it and so does
     every week (Jose, Sep 22, 2026) */
