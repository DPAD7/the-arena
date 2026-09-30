  function inBout(card, sel) {
    var out = [].slice.call(card.querySelectorAll(sel));
    document.querySelectorAll("dialog.sheet").forEach(function (d) {
      if (d._card === card) out = out.concat([].slice.call(d.querySelectorAll(sel)));
    });
    return out;
  }
  function paidMethods(card, winner, how, round, clock) {
    /* kept on the card: the sheet is written again whenever it is opened, and
       the green on the prices that paid has to go back on with it
       (Jose, Sep 22, 2026: "highlight the buttons in there that won") */
    card._paid = [winner, how, round, clock];
    if (typeof markBoutWay === "function") markBoutWay(card);
    var k = (how || "").toLowerCase();
    var ko = k.indexOf("ko") >= 0 || k.indexOf("knockout") >= 0;
    var sub = k.indexOf("sub") >= 0;
    var dec = k.indexOf("dec") >= 0 || k === "ud" || k === "md" || k === "sd";
    var ud = dec && (k.indexOf("unanimous") >= 0 || k === "ud");
    var sdmd = dec && (k.indexOf("split") >= 0 || k.indexOf("majority") >= 0 || k === "sd" || k === "md");
    var rn = parseInt(round, 10) || 0;
    /* the clock reads as time elapsed in the round: 0:47 is inside the first
       minute, 4:55 is inside the last ten seconds */
    var secs = -1, mm = /^(\d+):(\d\d)$/.exec(String(clock || "").trim());
    if (mm) secs = parseInt(mm[1], 10) * 60 + parseInt(mm[2], 10);
    var fin = ko || sub;
    var w = surname(winner);
    var side = w && w === surname(card.dataset.lf) ? 0 : w && w === surname(card.dataset.rf) ? 1 : -1;
    var MAN = { ko: ko, sub: sub, dec: dec, kosub: fin, finish: fin, kodec: ko || dec,
                subdec: sub || dec, koonly: ko, subonly: sub, deconly: dec, finishonly: fin,
                cards: dec, ud: ud, sdmd: sdmd,
                rd1only: rn === 1 && fin, rd12: fin && rn > 0 && rn <= 2,
                rd34: fin && (rn === 3 || rn === 4) };
    var FIGHT = { dist: dec, nodist: fin, anyko: ko, anysub: sub, anydec: dec,
                  anyud: ud, anysdmd: sdmd,
                  first60: fin && rn === 1 && secs >= 0 && secs <= 60,
                  last10: fin && secs >= 290 };
    for (var n = 1; n <= 5; n++) {
      MAN["rd" + n] = fin && rn === n;
      MAN["kord" + n] = ko && rn === n;
      MAN["subrd" + n] = sub && rn === n;
      FIGHT["anykord" + n] = ko && rn === n;
      FIGHT["anysubrd" + n] = sub && rn === n;
    }
    /* the last round, or the cards: whichever way it went past the rest */
    var nr = (FPROPS[card.dataset.bout] || {}).rounds || 3;
    MAN.rdlastdec = dec || (fin && rn === nr);

    inBout(card, ".mkt .price.paid").forEach(function (b) { b.classList.remove("paid"); });
    inBout(card, ".mkt .mktrow[data-mkt]").forEach(function (row) {
      var m = row.dataset.mkt;
      if (m in FIGHT) {
        var b = row.querySelector(".mktcell .price") || row.querySelector(".price");
        if (b && FIGHT[m]) b.classList.add("paid");
      } else if (m in MAN && side >= 0 && MAN[m]) {
        var slot = row.children[side === 0 ? 0 : 2];
        if (slot && slot.classList.contains("price")) slot.classList.add("paid");
      }
    });
    /* the cells in an across-row are nobody's side -- any KO, goes the
       distance -- so the result alone decides them (Jose, Sep 18, 2026) */
    inBout(card, ".mkt .fs5cell[data-mkt]").forEach(function (cell) {
      var m = cell.dataset.mkt, b = cell.querySelector(".price");
      if (b && FIGHT[m]) b.classList.add("paid");
    });

    /* And his own. The marks above say which prices the fight paid; nothing
       said what HIS bets did, so a gold border sat on a leg for ever and
       settled nothing (Jose, Sep 22, 2026: "why would I want that without it
       settling?"). Every placed leg on the card turns green if it came in and
       red if it did not -- the round markets with the rest. */
    var settleLeg = function (b, m, side2) {
      if (!b || !b.classList.contains("placed")) return;
      var won = (m in FIGHT) ? !!FIGHT[m]
              : (m in MAN) ? (side2 >= 0 && side2 === side && !!MAN[m])
              : null;
      if (won === null) return;
      b.classList.toggle("won", !!won);
      b.classList.toggle("lost", !won);
    };
    inBout(card, ".mkt .mktrow[data-mkt]").forEach(function (row) {
      var m = row.dataset.mkt;
      if (m in FIGHT) {
        settleLeg(row.querySelector(".mktcell .price") || row.querySelector(".price"), m, -1);
        return;
      }
      [0, 2].forEach(function (i) {
        var slot = row.children[i];
        if (slot && slot.classList.contains("price")) settleLeg(slot, m, i === 0 ? 0 : 1);
      });
    });
    inBout(card, ".mkt .fs5cell[data-mkt]").forEach(function (cell) {
      settleLeg(cell.querySelector(".price"), cell.dataset.mkt, -1);
    });
    /* the card's own four rows: the club price and the way it ended */
    var rowKey = { KO: "ko", SUB: "sub", DEC: "dec" };
    card.querySelectorAll(".gstack .gline").forEach(function (ln) {
      var tag = ln.querySelector(".grn");
      var m = tag ? rowKey[tag.textContent.trim().toUpperCase()] : "ml";
      if (!m) return;
      ln.querySelectorAll(".gh2h").forEach(function (cell, i) {
        var b = cell.querySelector(".price");
        if (!b) return;
        var won = m === "ml" ? (i === side) : (i === side && !!MAN[m]);
        /* the price that paid is green on the card the way it is on the
           sheet -- only a leg he placed was ever marked here, so a finished
           bout sat with its four rows plain grey (Jose, Sep 23, 2026: "you
           know what we do in the modal?") */
        b.classList.toggle("paid", !!won);
        if (!b.classList.contains("placed")) return;
        b.classList.toggle("won", !!won);
        b.classList.toggle("lost", !won);
      });
    });
  }
  /* How a bout actually ended, from the one ESPN feed that says so.
     The scoreboard only writes "Unofficial Winner Decision", so every
     decision read DEC and the unanimous price was never marked -- and a
     decision has to be unanimous, split or majority, so one of those three
     paid every time (Jose, Sep 19, 2026: "if he won by dec he had to win by
     one of these"). The bout's own status carries "Decision - Unanimous",
     short "U Dec". It is asked once per bout, after it is settled. */
  /* ---- the fight, played back on the card ----
     Every strike ESPN logged, laid where it landed: red field for the man on
     the left, blue for the right, head at the top and legs at the bottom, a
     dot for the head, a square for the body, a diamond for the legs. A clinch
     slides the seam toward whoever has hold; a takedown turns the whole
     thing a quarter turn; a knockdown drops the downed man's field and only
     his. The clock runs down the middle, round bars across it, and the finish
     is one line from the clock to the mark. Drag to scrub; let go and it
     plays on; it plays once and REPLAY starts it over. The moments come from
     data/fight_plays.jsonl by way of site/anim/<bout>.json, so a card that
     has a file gets the rewind and one that does not gets nothing
     (Jose, Sep 20, 2026, built card by card through the night). */
  function fightAnim(svg, d, againBtn) {
    var NS = "http://www.w3.org/2000/svg";
    var W = 400, FH = 292, CX = 200, CY = 146, TOTAL = d.rounds * 300, SPEED = 30;
    var FL = 46, FR = 354;
    var RED = "#e04e3c", BLUE = "#567ae0";
    var HIT = {a: {1: "#b5392a", 0: "#e09183"}, b: {1: "#2f57b5", 0: "#8fabe8"}};
    var BAND = {head: [12, 84], body: [108, 184], leg: [206, 282]};
    var NEAR = {g: [0.04, 0.20], c: [0.18, 0.44], d: [0.42, 0.96]};
    var CLIP = "clipF" + d.bout;
    var el = function (n, at) { var e = document.createElementNS(NS, n); for (var k in at) e.setAttribute(k, at[k]); return e; };
    var y = function (t) { return (t / TOTAL) * FH; };

    var spin, redF, blueF, marksA, marksB, ctrl, nowL, tally, tallyG = [], foot, voidA, voidB, GROW = [];
    var laid = [], lastSeam = -1;
    var count = {}, placed = {}, i = 0, seam = CX, wantSeam = CX, turn = 0, wantTurn = 0, ground = false;
    var t0 = performance.now(), held = false, heldT = 0, shownT = 0, over = false, dead = false;
    var shakeUntil = 0, shakeSide = 0, subUntil = 0, subSide = 0, pauseUntil = 0, pauseInk = "#39ff88";
    var kdUntil = 0, kdDown = "", dropA = 0, dropB = 0, momAt = 0;

    function build() {
      svg.innerHTML = "";
      var defs = el("defs", {}), cp = el("clipPath", {id: CLIP});
      cp.appendChild(el("rect", {x: FL, y: 0, width: FR - FL, height: FH})); defs.appendChild(cp); svg.appendChild(defs);
      var holder = el("g", {"clip-path": "url(#" + CLIP + ")"});
      spin = el("g", {transform: "rotate(0 " + CX + " " + CY + ")"});
      redF = el("rect", {x: FL, y: -260, width: CX - FL, height: 820, fill: RED, "fill-opacity": 0.16});
      blueF = el("rect", {x: CX, y: -260, width: FR - CX, height: 820, fill: BLUE, "fill-opacity": 0.16});
      marksA = el("g", {}); marksB = el("g", {});
      spin.appendChild(redF); spin.appendChild(blueF); spin.appendChild(marksA); spin.appendChild(marksB);
      holder.appendChild(spin); svg.appendChild(holder);
      voidA = el("rect", {x: 0, y: 0, width: 0, height: 0, fill: "#0d0d0d"});
      voidB = el("rect", {x: 0, y: 0, width: 0, height: 0, fill: "#0d0d0d"});
      holder.appendChild(voidA); holder.appendChild(voidB);
      ctrl = el("g", {}); svg.appendChild(ctrl);
      /* control time grows while it is being had: each stretch's bar is laid
         empty now and fills as the clock runs through that stretch. A fight
         rebuilt from the round tables knows control only per round, and the
         whole round's bar used to appear at once when the round ended
         (Jose, Sep 29, 2026: "it needs to happen ... when it's happening
         during the fight") */
      GROW = [];
      var prevT = 0;
      d.ev.forEach(function (e) {
        if (!e.state) return;
        var from = Math.max(prevT, Math.floor(Math.max(0, e.t - 1) / 300) * 300);
        [["a", 189, e.ac], ["b", 205, e.bc]].forEach(function (q) {
          if (!(q[2] > 0)) return;
          var full = Math.max(3, (q[2] / TOTAL) * FH * 1.6);
          var r = el("rect", {x: q[1], y: y(from), width: 6, height: 0, rx: 3, fill: "#f0913c", "fill-opacity": 0.9});
          ctrl.appendChild(r);
          GROW.push({r: r, t0: from, t1: Math.max(from + 1, e.t), full: full});
        });
        prevT = e.t;
      });
      svg.appendChild(el("line", {x1: CX, y1: 0, x2: CX, y2: FH, stroke: "#fff", "stroke-width": 3}));
      for (var r = 0; r <= d.rounds; r++) {
        var yy = Math.max(4, Math.min(FH, y(r * 300))), w = (r === 0 || r === d.rounds) ? 24 : 16;
        svg.appendChild(el("line", {x1: CX - w, y1: yy, x2: CX + w, y2: yy, stroke: "#fff", "stroke-width": 4}));
        if (r < d.rounds)
          svg.appendChild(el("line", {x1: 190, y1: y(r * 300 + 150), x2: 210, y2: y(r * 300 + 150),
            stroke: "#fff", "stroke-opacity": 0.55, "stroke-width": 2.5}));
      }
      nowL = el("line", {x1: 148, y1: 0, x2: 252, y2: 0, stroke: "#fff", "stroke-opacity": 0.75, "stroke-width": 1.5});
      svg.appendChild(nowL);
      foot = el("text", {x: CX, y: 318, "text-anchor": "middle", fill: "#9a9a9a",
        "font-family": "Barlow Condensed, Arial Narrow, sans-serif", "font-size": 12, "font-weight": 700, "letter-spacing": 2.2});
      foot.textContent = "R1 5:00"; svg.appendChild(foot);
      tally = {}; tallyG = []; count = {ahead: 0, abody: 0, aleg: 0, bhead: 0, bbody: 0, bleg: 0};
      var R = 15;
      [["a", "head", 21, 32], ["a", "body", 21, 130], ["a", "leg", 21, 228],
       ["b", "head", 379, 32], ["b", "body", 379, 130], ["b", "leg", 379, 228]].forEach(function (q) {
        var wv = q[0], k = q[1], x = q[2], yy2 = q[3];
        var g = el("g", {});
        g.appendChild(el("circle", {cx: x, cy: yy2, r: R + 3, fill: "#0b0b0b", "fill-opacity": 0.72}));
        var shape;
        if (k === "head") shape = el("circle", {cx: x, cy: yy2, r: R, fill: "none", stroke: "#fff", "stroke-opacity": 0.30, "stroke-width": 1.5});
        else if (k === "body") shape = el("rect", {x: x - R, y: yy2 - R, width: R * 2, height: R * 2, rx: 2, fill: "none", stroke: "#fff", "stroke-opacity": 0.30, "stroke-width": 1.5});
        else shape = el("polygon", {points: x + "," + (yy2 - R * 1.25) + " " + (x + R) + "," + yy2 + " " + x + "," + (yy2 + R * 1.25) + " " + (x - R) + "," + yy2,
          fill: "none", stroke: "#fff", "stroke-opacity": 0.30, "stroke-width": 1.5});
        var e = el("text", {x: x, y: yy2 + 6, "text-anchor": "middle", fill: "#fff", "fill-opacity": 1,
          "font-family": "Barlow Condensed, Arial Narrow, sans-serif", "font-size": 18, "font-weight": 700, "letter-spacing": 0.5});
        e.textContent = "0";
        g.appendChild(shape); g.appendChild(e); svg.appendChild(g); tally[wv + k] = e; tallyG.push(g);
      });
    }

    function diamond(cx, cy, r) {
      return cx + "," + (cy - r * 1.25) + " " + (cx + r) + "," + cy + " " + cx + "," + (cy + r * 1.25) + " " + (cx - r) + "," + cy;
    }
    function addMark(e, live) {
      var onRed = (e.w === "b");
      var x, c;
      if (e.grey) {
        x = onRed ? FL + 8 + Math.random() * (seam - FL - 16) : seam + 8 + Math.random() * (FR - seam - 16);
        c = el("circle", {cx: x, cy: 10 + Math.random() * (FH - 20), r: 2.6, fill: "#9a9a9a", "fill-opacity": 0.34});
        (onRed ? marksA : marksB).appendChild(c);
        laid.push({el: c, side: onRed ? "a" : "b", kind: "head", r: 2.6, cy: +c.getAttribute("cy"),
                   frac: onRed ? (x - FL) / (CX - FL) : (x - CX) / (FR - CX)});
        return;
      }
      if (e.miss) {
        x = onRed ? FL + 8 + Math.random() * (seam - FL - 16) : seam + 8 + Math.random() * (FR - seam - 16);
        c = el("circle", {cx: x, cy: 10 + Math.random() * (FH - 20), r: 3.4, fill: "none",
                          stroke: "#9a9a9a", "stroke-opacity": 0.22, "stroke-width": 1.2});
        (onRed ? marksA : marksB).appendChild(c);
        laid.push({el: c, side: onRed ? "a" : "b", kind: "head", r: 3.4, cy: +c.getAttribute("cy"),
                   frac: onRed ? (x - FL) / (CX - FL) : (x - CX) / (FR - CX)});
        return;
      }
      var ink = HIT[e.w][e.sig ? 1 : 0], b = BAND[e.k];
      var zone = NEAR[e.p || "d"], reach = onRed ? CX - FL - 14 : FR - CX - 14;
      var key = (onRed ? "a" : "b") + e.k; placed[key] = placed[key] || [];
      var cx = 0, cy = 0, far = -1;
      for (var k = 0; k < 12; k++) {
        var off = (zone[0] + Math.random() * (zone[1] - zone[0])) * reach;
        var px = onRed ? CX - 10 - off : CX + 10 + off, py = b[0] + Math.random() * (b[1] - b[0]);
        var near = 1e9, seen = placed[key];
        for (var j = Math.max(0, seen.length - 70); j < seen.length; j++) {
          var dx = seen[j][0] - px, dy = seen[j][1] - py, dd = dx * dx + dy * dy;
          if (dd < near) near = dd;
        }
        if (near > far) { far = near; cx = px; cy = py; }
        if (far > 150) break;
      }
      placed[key].push([cx, cy]);
      var end = e.kd ? 12 : 4;
      if (e.k === "head") c = el("circle", {cx: cx, cy: cy, r: end, fill: ink});
      else if (e.k === "body") c = el("rect", {x: cx - end, y: cy - end, width: end * 2, height: end * 2, rx: 1, fill: ink});
      else c = el("polygon", {points: diamond(cx, cy, end), fill: ink});
      if (e.kd) {
        c.setAttribute("stroke", "#fff"); c.setAttribute("stroke-width", 2);
        var ended = Math.abs(e.t - d.stop) < 12 && (d.how === "TKO" || d.how === "KO");
        kdUntil = ended ? Infinity : performance.now() + 1100;
        kdDown = (e.w === "a") ? "b" : "a";
      }
      (onRed ? marksA : marksB).appendChild(c);
      laid.push({el: c, side: onRed ? "a" : "b", kind: e.k, r: end, cy: cy,
                 frac: onRed ? (cx - FL) / (CX - FL) : (cx - CX) / (FR - CX)});
      if (live) {
        var born = performance.now();
        (function pop(now) {
          var kk = Math.min(1, (now - born) / 300);
          var r = end * (0.25 + 0.75 * (1 - Math.pow(1 - kk, 3)) + 0.9 * kk * (1 - kk));
          if (e.k === "head") c.setAttribute("r", r);
          else if (e.k === "body") { c.setAttribute("x", cx - r); c.setAttribute("y", cy - r); c.setAttribute("width", r * 2); c.setAttribute("height", r * 2); }
          else c.setAttribute("points", diamond(cx, cy, r));
          if (kk < 1 && !dead) requestAnimationFrame(pop);
        })(born);
      }
      var side = e.w === "b" ? "a" : "b";
      count[side + e.k] += 1; tally[side + e.k].textContent = count[side + e.k];
    }

    function applyState(e) {
      var td = d.moments.some(function (m) { return m.what === "Takedown" && Math.abs(m.t - e.t) < 34; });
      var holding = (e.ac > 0 || e.bc > 0);
      if (e.gr > 0) ground = true;
      else if (e.cl > 0) ground = false;
      else if (holding && td) ground = true;
      else if (!holding) ground = false;
      var clinch = !ground && e.cl > 0;
      wantTurn = ground ? (e.ac >= e.bc ? 90 : -90) : 0;
      wantSeam = ground ? CX : (clinch ? (e.ac >= e.bc ? FL + (FR - FL) * 0.80 : FL + (FR - FL) * 0.20) : CX);
      /* the bars are grown by sayClock, stretch by stretch */
    }

    function paint() {
      var want = performance.now() < kdUntil ? FH * 0.20 : 0;
      var tA = (kdDown === "a") ? want : 0, tB = (kdDown === "b") ? want : 0;
      dropA += (tA - dropA) * 0.24;
      dropB += (tB - dropB) * 0.24;
      redF.setAttribute("width", Math.max(0, seam - FL));
      redF.setAttribute("y", -260 + dropA);
      blueF.setAttribute("x", seam);
      blueF.setAttribute("y", -260 + dropB);
      blueF.setAttribute("width", Math.max(0, FR - seam));
      marksA.setAttribute("transform", "translate(0 " + dropA.toFixed(1) + ")");
      marksB.setAttribute("transform", "translate(0 " + dropB.toFixed(1) + ")");
      voidA.setAttribute("x", FL); voidA.setAttribute("width", Math.max(0, seam - FL)); voidA.setAttribute("height", dropA);
      voidB.setAttribute("x", seam); voidB.setAttribute("width", Math.max(0, FR - seam)); voidB.setAttribute("height", dropB);
      spin.setAttribute("transform", "rotate(" + turn + " " + CX + " " + CY + ")");
      if (Math.abs(seam - lastSeam) > 0.3) {
        lastSeam = seam;
        for (var j = 0; j < laid.length; j++) {
          var m = laid[j];
          var x = m.side === "a" ? FL + m.frac * (seam - FL) : seam + m.frac * (FR - seam);
          if (m.kind === "head") m.el.setAttribute("cx", x.toFixed(1));
          else if (m.kind === "body") m.el.setAttribute("x", (x - m.r).toFixed(1));
          else m.el.setAttribute("points", diamond(x, m.cy, m.r));
        }
      }
    }
    function growControl(t) {
      for (var g = 0; g < GROW.length; g++) {
        var b = GROW[g];
        var f = t <= b.t0 ? 0 : Math.min(1, (t - b.t0) / (b.t1 - b.t0));
        var h = b.full * f, end = y(Math.min(t, b.t1));
        b.r.setAttribute("height", h.toFixed(1));
        b.r.setAttribute("y", Math.max(0, end - h).toFixed(1));
      }
    }
    function sayClock(t) {
      growControl(t);
      var rd = Math.min(d.rounds, Math.floor(t / 300) + 1), left = 300 - (t - (rd - 1) * 300);
      foot.textContent = "R" + rd + " " + Math.floor(left / 60) + ":" + ("0" + Math.floor(left % 60)).slice(-2);
      foot.setAttribute("fill", "#9a9a9a");
      nowL.setAttribute("y1", y(t)); nowL.setAttribute("y2", y(t));
    }
    function drawFinish() {
      if (d.won === null || d.won === undefined) return;
      if (d.how === "UD" || d.how === "SD" || d.how === "MD") return;
      var loser = (d.won === 0) ? "b" : "a";
      var band = BAND[d.fb || "head"];
      var sx = loser === "a" ? FL + (seam - FL) * 0.55 : seam + (FR - seam) * 0.55;
      var sy = (band[0] + band[1]) / 2;
      var yy = y(d.stop);
      var g = el("g", {});
      g.appendChild(el("line", {x1: CX, y1: yy, x2: sx, y2: sy, stroke: "#fff", "stroke-opacity": 0.85, "stroke-width": 1.5}));
      var sym = (d.how === "SUB") ? "msub" : "mko", size = 40;
      var u = document.createElementNS(NS, "use");
      u.setAttribute("href", "#" + sym);
      u.setAttribute("x", sx - size / 2); u.setAttribute("y", sy - size / 2);
      u.setAttribute("width", size); u.setAttribute("height", size);
      g.appendChild(u);
      svg.appendChild(g);
      tallyG.forEach(function (t) { svg.appendChild(t); });
    }
    function sayDone() {
      growControl(d.stop + 1);
      foot.textContent = d.how + (d.fr ? " · R" + d.fr : "") + (d.fc ? " " + d.fc : "");
      foot.setAttribute("fill", "#ffffff");
      nowL.setAttribute("y1", y(d.stop)); nowL.setAttribute("y2", y(d.stop));
      nowL.setAttribute("stroke-opacity", 1); nowL.setAttribute("stroke-width", 3);
      drawFinish();
    }
    function reset() {
      build(); placed = {}; laid = []; lastSeam = -1; i = 0; momAt = 0;
      shakeUntil = subUntil = pauseUntil = kdUntil = 0; kdDown = ""; dropA = dropB = 0;
      svg.style.background = "";
      seam = wantSeam = CX; turn = wantTurn = 0;
      ground = false; shownT = 0; over = false;
    }
    function seek(target) {
      if (target < shownT) reset();
      runMoments(target);
      while (i < d.ev.length && d.ev[i].t <= target) {
        var e = d.ev[i++];
        if (e.state) applyState(e); else addMark(e, false);
      }
      seam = wantSeam; turn = wantTurn; paint();
      shownT = target; sayClock(target);
    }
    function runMoments(t) {
      while (momAt < d.moments.length && d.moments[momAt].t <= t) {
        var m = d.moments[momAt++], w = m.what;
        if (w === "Takedown Attempt") { shakeUntil = performance.now() + 900; shakeSide = (Math.random() < 0.5) ? -1 : 1; }
        else if (w === "Submission Attempt") { subUntil = performance.now() + 2600; subSide = ground ? (turn >= 0 ? 1 : -1) : 1; }
        else if (w === "Round Pause" || w.indexOf("Pause Reason") === 0) { pauseUntil = performance.now() + 2200; pauseInk = w.indexOf("Eye Poke") > -1 ? "#f0913c" : "#39ff88"; }
        else if (w === "Round Unpause") { pauseUntil = 0; }
        else if (w === "Reversal") { if (ground) wantTurn = -wantTurn; }
      }
    }
    function frame(now) {
      if (held || dead) return;
      var t = ((now - t0) / 1000) * SPEED;
      if (t > d.stop) { over = true; seam = wantSeam; turn = wantTurn; paint(); sayDone(); return; }
      sayClock(t);
      while (i < d.ev.length && d.ev[i].t <= t) {
        var e = d.ev[i++];
        if (e.state) applyState(e); else addMark(e, true);
      }
      runMoments(t);
      var now2 = performance.now();
      var seamWant = wantSeam, turnWant = wantTurn;
      if (now2 < subUntil) {
        seamWant = ground ? CX : (subSide > 0 ? FL + (FR - FL) * 0.80 : FL + (FR - FL) * 0.20);
        if (ground) turnWant = wantTurn;
      }
      if (now2 < shakeUntil) {
        var kk = (shakeUntil - now2) / 900;
        seamWant = CX + shakeSide * 52 * Math.sin(kk * Math.PI * 3) * kk;
      }
      seam += (seamWant - seam) * 0.12;
      turn += (turnWant - turn) * 0.035;
      svg.style.background = now2 < pauseUntil
        ? (pauseInk === "#f0913c" ? "rgba(240,145,60,0.13)" : "rgba(57,255,136,0.13)") : "";
      paint(); shownT = t;
      requestAnimationFrame(frame);
    }
    var atY = function (ev) {
      var r = svg.getBoundingClientRect();
      var vy = ((ev.clientY - r.top) / r.height) * 330;
      return Math.max(0, Math.min(d.stop, (vy / FH) * TOTAL));
    };
    svg.addEventListener("pointerdown", function (ev) {
      held = true; over = false;
      try { svg.setPointerCapture(ev.pointerId); } catch (x) {}
      heldT = atY(ev); seek(heldT);
    });
    svg.addEventListener("pointermove", function (ev) { if (held) { heldT = atY(ev); seek(heldT); } });
    function letGo() {
      if (!held) return;
      held = false;
      t0 = performance.now() - (heldT / SPEED) * 1000;
      requestAnimationFrame(frame);
    }
    ["pointerup", "pointercancel", "pointerleave"].forEach(function (k) { svg.addEventListener(k, letGo); });
    if (againBtn) againBtn.addEventListener("click", function () {
      if (dead) return;
      reset(); t0 = performance.now(); requestAnimationFrame(frame);
    });
    reset();
    requestAnimationFrame(frame);
    return { kill: function () { dead = true; held = false; } };
  }

  /* which bouts we hold the moments for, read once from the site */
  var ANIMS = null, ANIMWAIT = [];
  function animList(then) {
    if (ANIMS) return then(ANIMS);
    ANIMWAIT.push(then);
    if (ANIMWAIT.length > 1) return;
    fetch("anim/index.json").then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (j) { ANIMS = j || {}; })
      .catch(function () { ANIMS = {}; })
      .then(function () { var w = ANIMWAIT; ANIMWAIT = []; w.forEach(function (f) { f(ANIMS); }); });
  }
  var REWIND = '<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="4" y="6" width="2.6" height="12" rx="0.8" fill="currentColor"/>' +
               '<polygon points="19,6 9,12 19,18" fill="currentColor"/></svg>';
  /* the rewind, beside FINAL, on a bout that has a file; and what it opens */
  function armRewind(card) {
    if (!card || !card.dataset.bout) return;
    var gt = card.querySelector(".gtime");
    /* the button is looked for on the CARD, not inside the clock: on a bout
       card it rides the top line instead, so a guard that only searched the
       clock never saw the one already made and built a second every pass
       (Jose, Sep 22, 2026: "why are there two rewind buttons?") */
    if (!gt || !gt.querySelector(".fhow") || card.querySelector(".frewind")) return;
    animList(function (list) {
      if (!list[card.dataset.bout]) return;
      var fh = gt.querySelector(".fhow");
      if (!fh || card.querySelector(".frewind")) return;
      var b = document.createElement("button");
      b.className = "frewind"; b.type = "button";
      b.setAttribute("aria-label", "Play the fight back");
      b.setAttribute("aria-pressed", "false");
      b.innerHTML = REWIND;
      b.addEventListener("click", function (e) {
        e.preventDefault(); e.stopPropagation();
        var open = card.querySelector(":scope > .fanim");
        if (open) {
          if (open._anim) open._anim.kill();
          open.parentNode.removeChild(open);
          b.setAttribute("aria-pressed", "false");
          return;
        }
        b.setAttribute("aria-pressed", "true");
        var box = document.createElement("div");
        box.className = "fanim";
        box.innerHTML = '<svg viewBox="0 0 400 330"></svg><button class="again" type="button">REPLAY</button>';
        /* under FINAL, above the rail: the head is the first child and the
           rail is the next, so it goes between them */
        var head = card.querySelector(":scope > .ghead");
        if (head && head.nextSibling) head.parentNode.insertBefore(box, head.nextSibling); else card.appendChild(box);
        fetch("anim/" + card.dataset.bout + ".json").then(function (r) { return r.ok ? r.json() : null; })
          .then(function (d) {
            if (!d || !card.contains(box)) return;
            /* the card knows how many rounds the bout was for; the file may
               have been cut with the default */
            var nr = (FPROPS[card.dataset.bout] || {}).rounds;
            if (nr) d.rounds = nr;
            box._anim = fightAnim(box.querySelector("svg"), d, box.querySelector(".again"));
          })
          .catch(function () {});
      });
      /* on a bout card the rewind rides the top line, between the eye and the
         play mark, the way the mock has it (mock-rewind.png). The clock it
         used to sit beside is not drawn there (Jose, Sep 22, 2026) */
      var topline = card.querySelector(".gcard--bout .gtop, .gtop");
      if (card.classList.contains("gcard--bout") && topline) {
        var watch = topline.querySelector(".gwatch");
        if (watch) topline.insertBefore(b, watch);
        else topline.appendChild(b);
      } else {
        fh.parentNode.insertBefore(b, fh.nextSibling);
      }
    });
  }
  window.armRewind = armRewind;
  var EXACT = { "u dec": "UD", "s dec": "SD", "m dec": "MD", "dec": "DEC",
                "ko/tko": "TKO", "ko": "KO", "tko": "TKO", "sub": "SUB",
                "submission": "SUB", "dq": "DQ", "nc": "NC", "draw": "DRAW",
                "t dec": "TD" };
  function exactMethod(card) {
    if (!card || card.dataset.exactMethod || !card.dataset.bout || !card.dataset.event) return;
    card.dataset.exactMethod = "1";
    var u = "https://sports.core.api.espn.com/v2/sports/mma/leagues/ufc/events/" +
            card.dataset.event + "/competitions/" + card.dataset.bout + "/status";
    fetch(espnUrl(u)).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      var res = d && d.result;
      if (!res) return;
      var lab = EXACT[String(res.shortDisplayName || "").toLowerCase().trim()] ||
                EXACT[String(res.displayName || "").toLowerCase().trim()];
      if (!lab) return;
      /* the method rides on the timeline, where a game card carries its down
         and distance. The clock row says FINAL, the same word a finished game
         says, instead of printing the method a second time an inch above it
         (Sep 19, 2026) */
      var gt = card.querySelector(".gtime");
      if (gt) {
        var fw = gt.querySelector(".fwt");
        gt.classList.remove("gtime--live");
        gt.innerHTML = '<span class="fhow">FINAL</span>' + (fw ? fw.outerHTML : "");
        armRewind(card);
      }
      var win = "";
      card.querySelectorAll(".ghead--fight .gteam").forEach(function (s) {
        if (s.querySelector(":scope > .mk.ok")) {
          var n = s.querySelector(".fname");
          if (n) { var cc = n.cloneNode(true), rr = cc.querySelector(".frec");
                   if (rr) rr.parentNode.removeChild(rr); win = cc.textContent.trim(); }
        }
      });
      paidMethods(card, win, lab, d.period, d.displayClock);
      /* the timeline stops where the bout stopped and says how it ended,
         which is the fight's answer to down and distance */
      drawTimeline(card, {format: card._fmt || {}}, d, d.period,
                   lab + (d.period ? " \u00b7 R" + d.period : "") +
                   (d.displayClock ? " " + d.displayClock : ""));
      showHits(card);
    }).catch(function () {});
  }
  /* How far through the bout we are, drawn once and written to after that.
     ESPN gives the round and the seconds elapsed inside it, and the format
     says how many rounds there are, so the whole fight is rounds x five
     minutes and the fill is simply where we have got to. A bout that is over
     stops at the moment it ended and says how. */
  /* The method arrives either shortened (UD, SUB, TKO) or as the words the
     source wrote ("Unanimous Decision", "Submission", "KO/TKO"), depending on
     which of the two settles the bout. Reading only the short form put the
     glove on forty-eight of fifty-four finishes, because everything it did
     not recognise fell through to it (Jose, Sep 22, 2026: "why did you do KO
     icon for all them?"). Both forms are read here, and a method neither
     names draws no mark at all rather than a wrong one. */
  function railMark(type) {
    var t = String(type || "").toUpperCase();
    if (!t) return null;
    /* a disqualification, a no contest and a draw say so in the same boxed
       letters as UD: DQ and NC where it was stopped, D at the end like a
       decision (Jose, Sep 27, 2026) -- a DQ used to wear the glove */
    if (t.indexOf("DQ") >= 0 || t.indexOf("DISQUALIF") >= 0) return { m: "mdq", dec: false };
    if (t === "NC" || t.indexOf("NO CONTEST") >= 0 || t.indexOf("NO-CONTEST") >= 0) return { m: "mnc", dec: false };
    if (t.indexOf("DRAW") >= 0 || t === "D" || t === "DREW") return { m: "mdraw", dec: true };
    if (t.indexOf("SUB") >= 0) return { m: "msub", dec: false };
    if (t.indexOf("DEC") >= 0 || t === "UD" || t === "SD" || t === "MD" || t === "TD") {
      return { m: t.indexOf("SPLIT") >= 0 || t === "SD" ? "msd"
                : t.indexOf("MAJORITY") >= 0 || t === "MD" ? "mmd" : "mud",
               dec: true };
    }
    if (t.indexOf("KO") >= 0 || t.indexOf("KNOCKOUT") >= 0) return { m: "mko", dec: false };
    return null;
  }
  /* The fight's own rail, filled to where it stands. A stoppage puts the
     glove or the submission mark on the line with the clock above it; a
     decision has no clock and its chip stands where the end cap would, so
     nothing straddles the last tick; a bout still on carries the round chip
     on the line with the clock above (Jose, Sep 21, 2026). */
  function fillRail(bar, c, state, rd, pct) {
    bar.querySelectorAll(".frail__fill, .fend").forEach(function (n) { n.remove(); });
    var card0 = cardOf(bar);
    var how = (c && c.how) || (card0 && card0._how) || {};
    if (card0 && c && c.how) card0._how = c.how;
    var got = railMark(how.type);
    var dec = !!(got && got.dec) && state === "post";
    var fill = document.createElement("i");
    fill.className = "frail__fill" + (state === "in" ? " frail__fill--live" : "");
    fill.style.width = (dec ? 100 : Math.max(0, Math.min(100, pct))).toFixed(2) + "%";
    bar.insertBefore(fill, bar.firstChild);
    bar.classList.toggle("frail__bar--dec", dec);

    var end = document.createElement("span");
    end.className = "fend" + (dec ? " fend--end" : "");
    if (!dec) end.style.left = Math.max(0, Math.min(97, pct)).toFixed(2) + "%";
    var mark = state === "post" ? (got && got.m) : ("r" + Math.max(1, rd));
    /* nothing to say, nothing drawn */
    if (!mark) { bar.classList.remove("frail__bar--dec"); return; }
    var clock = state === "post" ? (dec ? "" : (how.time || ""))
                                 : (c.status && c.status.displayClock) || "";
    if (clock) end.innerHTML = '<b class="fclock">' + clock + "</b>";
    end.innerHTML += '<i class="fmethod' + (state === "in" ? " fmethod--rnd" : "") +
      '"><svg viewBox="0 0 26 22" aria-hidden="true"><use href="#' + mark + '"/></svg></i>';
    bar.appendChild(end);
  }
  function drawTimeline(card, c, st, rd, label) {
    /* ESPN's own record first, then the rounds on the bout's card, never a
       guessed three: a five-round stoppage on a three-round rail lands in the
       wrong round (audit, Sep 28, 2026) */
    var rounds = (((c.format || {}).regulation || {}).periods) ||
      parseInt(((typeof FPROPS === "object" && FPROPS[card.dataset.bout]) || {}).rounds, 10) || 3;
    var each = (((c.format || {}).regulation || {}).clock) || 300;
    var state = ((st.type || {}).state) || "";
    var secs = typeof st.clock === "number" ? st.clock : 0;
    var on = (state === "in" && rd >= 1) || state === "post";
    var box = card.querySelector(".tline");
    if (!on) {
      card.classList.remove("has-tline");
      if (box) box.innerHTML = "";
      return;
    }
    if (!box) {
      var head = card.querySelector(".ghead");
      if (!head) return;
      box = document.createElement("div");
      box.className = "tline";
      head.parentNode.insertBefore(box, head.nextSibling);
    }
    /* ESPN's fight clock is time LEFT in the round, not time gone: the log
       shows it walking 4:07, 3:36, 3:04 inside one round and then starting
       again at the top of the next. Read as elapsed, the fill ran backwards
       through every round (Sep 19, 2026, caught in data/fight_log.jsonl). */
    var whole = rounds * each;
    var left = Math.max(0, Math.min(each, secs));
    /* Two different clocks wear the same name. While a bout is on, ESPN's is
       the time LEFT in the round. On a bout that is over, it is the official
       finish time -- how far INTO the round it ended, which is what the
       result reads: TKO R1 1:57 is one minute fifty-seven gone, not left.
       Read as time left, every finished bout was marked in the wrong place:
       a decision that went the full three rounds stopped two thirds along
       the rail, and a first-round knockout at 0:12 was marked a third of the
       way through the fight (Jose, Sep 20, 2026: "why is the settling as dec
       in the second round?"). */
    var into = state === "post" ? left : each - left;
    var gone = Math.max(0, Math.min(whole, (Math.max(1, rd) - 1) * each + into));
    var pct = whole ? (gone / whole) * 100 : 0;
    /* the bout card draws its own rail -- a stretch a round, the finish marked
       ON the line with the clock above it, a decision standing where the end
       cap would (notes/mocks/mock_mma.py). The old timeline stays for cards
       that have not been re-laid. */
    var fbar = card.querySelector(".frail__bar");
    if (fbar) {
      card._railPct = pct;
      if (c && c.how) card._how = c.how;
      fillRail(fbar, c, state, rd, pct);
      card.classList.remove("has-tline");
      if (box) box.innerHTML = "";
      return;
    }
    var wrap = box.querySelector(".tlwrap");
    if (!wrap) {
      /* the round line is marked once, by the tall tick under the rail. It
         used to be marked twice -- a cut on the rail and a tick beneath it at
         the same place, one directly over the other
         (Jose, Sep 19, 2026: "you have 2 ticks on top of each other") */
      var cuts = "";
      /* one tall mark where each round ends, one shorter at each round's
         half, and eight faint ones spread through every round */
      /* seven marks for a three round fight and nothing else: the two ends,
         the two round breaks, and the half of each round. The faint hairlines
         between them were the rail measuring itself, which is not something
         anybody reads (Jose, Sep 19, 2026: "drop em") */
      var ticks = '<i class="rnd" style="left:0"></i>';
      for (var r2 = 0; r2 < rounds; r2++) {
        var from = (r2 / rounds) * 100, span = (1 / rounds) * 100;
        ticks += '<i class="half" style="left:' + (from + span / 2) + '%"></i>';
        ticks += '<i class="rnd" style="left:' + (from + span) + '%"></i>';
      }
      box.innerHTML =
        '<div class="tlwrap">' +
          '<span class="tlat"></span>' +
          '<div class="tlbar"><i class="tlfill"></i>' + cuts +
            '<div class="tltick">' + ticks + "</div></div>" +
        "</div>";
      wrap = box.querySelector(".tlwrap");
    }
    card.classList.add("has-tline");
    /* ESPN's clock jumps: it sits still for fifteen or thirty seconds and
       then moves by that much at once, because it is written cageside when
       something is logged. So the card holds the last reading and walks it
       forward a second at a time, and every fresh reading resets it
       (Jose, Sep 19, 2026: "it should tick, no?"). The seconds between two
       readings are ours, not the cage's, and a correction can pull the clock
       back a little; it is never allowed past the end of the round it is in,
       which is where a guess would do real damage. */
    card._tl = {gone: gone, at: Date.now(), rd: rd, rounds: rounds,
                each: each, whole: whole, live: state === "in" && rd >= 1};
    card._tl.left = left;
    var fill = wrap.querySelector(".tlfill");
    if (fill) fill.style.width = pct + "%";
    /* the running clock rides over the head of the fill, kept off both ends
       so it never hangs off the card */
    var at = wrap.querySelector(".tlat");
    var said = state === "post"
      ? (label || "FINAL")
      : "R" + rd + (st.displayClock ? " " + st.displayClock : "");   /* as given: time left */
    if (at) {
      at.style.left = Math.max(10, Math.min(90, pct)) + "%";
      if (at.dataset.said !== said) {
        at.dataset.said = said;
        /* a finished bout wears the board's own marks: the glove for a
           knockout, the hold for a submission, UD / SD / MD for a decision,
           then the round's mark, then the official time. The words stay for
           anything the board has no mark for (Jose, Sep 20, 2026: "use the
           icon from the UD page, TKO is the KO icon, then R5") */
        var MK = {TKO: "mko", KO: "mko", SUB: "msub", UD: "mud", SD: "msd", MD: "mmd", DEC: "mdec"};
        var m = state === "post" ? /^([A-Z]+)(?:\s*·\s*R(\d))?(?:\s+(\d+:\d\d))?$/.exec(said) : null;
        if (m && MK[m[1]]) {
          var use = function (id, cls) {
            return '<svg class="' + (cls || "") + '" aria-hidden="true"><use href="#' + id + '"/></svg>';
          };
          at.innerHTML = use(MK[m[1]], MK[m[1]] === "mko" ? "mk--ko" : "") +
                         (m[2] && +m[2] >= 1 && +m[2] <= 5 ? use("r" + m[2]) : "") +
                         (m[3] ? "<span>" + m[3] + "</span>" : "");
          at.setAttribute("aria-label", said);
        } else {
          at.textContent = said;
          at.removeAttribute("aria-label");
        }
      }
    }
  }
  /* one clock for every bout on the board, a beat a second */
  /* a running football clock ticks down each second between readings, never
     further than the next reading can be (ten seconds) */
  setInterval(function () {
    document.querySelectorAll(".gcard[data-espn]").forEach(function (card) {
      var k = card._clk;
      if (!k || !k.run) return;
      var left = Math.max(0, k.sec - Math.min(12, (Date.now() - k.at) / 1000));
      var t = Math.floor(left / 60) + ":" + ("0" + Math.floor(left % 60)).slice(-2);
      card.querySelectorAll(".gclk--two b:first-child").forEach(function (b) { if (b.textContent !== t) b.textContent = t; });
    });
  }, 1000);
  function mmss(n) {
    n = Math.max(0, Math.round(n));
    var m = Math.floor(n / 60), s = n % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }
  setInterval(function () {
    document.querySelectorAll(".gcard[data-bout].live").forEach(function (card) {
      var t = card._tl;
      if (!t || !t.live) return;
      var on = t.gone + (Date.now() - t.at) / 1000;
      /* never past the end of the round we were told we are in */
      on = Math.min(on, t.rd * t.each);
      var wrap = card.querySelector(".tlwrap");
      if (!wrap) return;
      var at = wrap.querySelector(".tlat");
      var fill = wrap.querySelector(".tlfill");
      var pct = t.whole ? (on / t.whole) * 100 : 0;
      if (fill) fill.style.width = pct + "%";
      if (at) {
        at.style.left = Math.max(10, Math.min(90, pct)) + "%";
        /* the cage clock counts down, so that is what the card says */
        var say = "R" + t.rd + " " + mmss(t.each - (on - (t.rd - 1) * t.each));
        if (at.textContent !== say) at.textContent = say;
      }
      var gt = card.querySelector(".gtime .fhow");
      if (gt) {
        var g = "R" + t.rd + " " + mmss(t.each - (on - (t.rd - 1) * t.each));
        if (gt.textContent !== g) gt.textContent = g;
      }
    });
  }, 1000);
  function settleBoutCard(card, c) {
        var st = ((c.status || {}).type) || {};
        /* ESPN calls a bout "in" from the walkouts, with round 0 and the word
           Pre-fight on it. Locking on that killed every price on the card
           before a punch was thrown -- forty minutes before, in the Tuivasa
           bout (Jose, Sep 19, 2026: "why can't I bet Despaigne, buttons
           aren't working"). A bout is under way when it has a round. */
        var rd = parseInt((c.status || {}).period, 10) || 0;
        var going = st.state === "post" || (st.state === "in" && rd >= 1);
        card.classList.toggle("live", st.state === "in" && rd >= 1);
        if (going) {
          card.classList.add("locked");
          card.querySelectorAll("button.price").forEach(function (b) { shutPrice(b); });
        }
        /* the live mark goes into the clock that is already there. Writing a
           new one built a second line under the first (Jose, Sep 19, 2026:
           "you added a second one... it should just be on the original one"),
           so this only adds the badge, and only once, and takes it off again
           when the bout is over. */
        var gtl = card.querySelector(".gtime");
        if (gtl) {
          var onAir = st.state === "in" && rd >= 1;
          var bar = gtl.querySelector(".glivebar");
          gtl.classList.toggle("gtime--live", onAir);
          if (onAir) seatEye(card);
          if (onAir && !bar) {
            bar = document.createElement("span");
            bar.className = "glivebar";
            bar.innerHTML = '<img class="glive" src="ico/live-white.svg" alt="Live" ' +
                            'width="34" height="34">';
            gtl.appendChild(bar);
          } else if (!onAir) {
            if (bar) bar.parentNode.removeChild(bar);
            /* the badge is lifted into the top row while a fight is on, so it
               is no longer inside the bar and removing the bar left it behind
               -- a finished fight went on saying LIVE (Jose, Sep 22, 2026:
               "why is live still on a finished fight") */
            card.querySelectorAll(".glive").forEach(function (x) { x.remove(); });
          }
        }
        drawTimeline(card, c, c.status || {}, rd, "");
        if (st.state !== "post") return;
        var winner = "";
        (c.competitors || []).forEach(function (x) {
          if (x.winner) winner = ((x.athlete || {}).displayName || "");
        });
        var how = "";
        (c.details || []).forEach(function (dd) {
          var t = ((dd.type || {}).text || "");
          if (t.indexOf("Unofficial Winner") === 0) {
            how = t.replace("Unofficial Winner", "").trim();
          }
        });
        settleFight(card, winner, how);
        /* how it ended, in the clock's place: UD · R5 5:00, TKO · R2 3:41 */
        /* theScore's method where the names matched; ESPN's coarser word otherwise */
        if (!(c.how && c.how.type) && how) {
          var COARSE = { "Decision": "DEC", "Kotko": "TKO", "KO/TKO": "TKO", "Submission": "SUB", "Draw": "DRAW", "No Contest": "NC" };
          c.how = { type: COARSE[how] || how.toUpperCase(), round: (c.status || {}).period || "", time: (c.status || {}).displayClock || "" };
        }
        card._fmt = c.format || card._fmt;
        if (c.how && c.how.type) {
          var SHORT = { "Unanimous Decision": "UD", "Majority Decision": "MD", "Split Decision": "SD",
                        "Submission": "SUB", "KO/TKO": "TKO", "TKO": "TKO", "KO": "KO", "Knockout": "KO", "Technical Knockout": "TKO", "Technical Decision": "TD",
                        "Disqualification": "DQ", "DQ": "DQ", "Draw": "DRAW", "No Contest": "NC" };
          var lab = SHORT[c.how.type] || c.how.type;
          drawTimeline(card, c, c.status || {}, (c.how.round || rd),
                       lab + (c.how.round ? " \u00b7 R" + c.how.round : "") +
                       (c.how.time ? " " + c.how.time : ""));
          var gt = card.querySelector(".gtime");
          if (gt) {
            var fw = gt.querySelector(".fwt");
            gt.classList.remove("gtime--live");
            gt.innerHTML = '<span class="fhow">FINAL</span>' + (fw ? fw.outerHTML : "");
            armRewind(card);
          }
        }
        if (!card.dataset.toldPrices) {
          card.dataset.toldPrices = "1";
          if (Date.now() - (window._pricesAt || 0) > 60000) {
            window._pricesAt = Date.now();
            pullPrices();
          }
        }
        card.dataset.settledBout = "1";
        exactMethod(card);
        /* A bout that is over is over. Only football was ever marked done, so
           only football sank to the foot of the day, and a finished fight sat
           at the top of the board with its result on it (Jose, Sep 19, 2026:
           "why is this still on the top, it's over?"). Same word, same rule,
           both sports. */
        card.classList.add("done");
        markOver(card.dataset.bout);
        dropHide(card);
        askSink();
        if (typeof sinkDone === "function") sinkDone();
        paidMethods(card, winner, (c.how && c.how.type) || how,
                    (c.how && c.how.round) || (c.status || {}).period,
                    (c.how && c.how.time) || (c.status || {}).displayClock);
        showHits(card);
  }
  function applyBoard(cards, d) {
    var bouts = {};
    (d.events || []).forEach(function (e) {
      (e.competitions || []).forEach(function (c) { bouts[String(c.id)] = c; });
    });
    cards.forEach(function (card) {
      var c = bouts[card.dataset.bout];
      if (c) settleBoutCard(card, c);
    });
  }
  function refreshFights() {
    /* the shelf is not a board, so a hidden bout was never in this list at
       all: three of tonight's fights sat on the UFC tab with a start time and
       no result, hours after they were over (Jose, Sep 19, 2026: "these are
       all done, what is going on?"). Hidden means out of sight, not struck
       off -- the same rule the football sweep already follows. */
    var cards = [].slice.call(document.querySelectorAll(
      ".board:not([hidden]) .gcard[data-bout], .hidebox .gcard[data-bout]"));
    if (!cards.length) return;
    var now = Date.now(), live = [], byEvent = {};
    cards.forEach(function (card) {
      if (card.dataset.settledBout) return;
      var t = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
      /* boxing has no live feed: its results are the file boxing.py writes */
      if (/^zb-/.test(card.dataset.event || "")) {
        (byEvent[card.dataset.event] = byEvent[card.dataset.event] || []).push(card);
      } else if (t && t < now - 8 * 3600000 && card.dataset.event) {
        (byEvent[card.dataset.event] = byEvent[card.dataset.event] || []).push(card);
      } else if (!t || t < now + 20 * 60000) {
        live.push(card);
      }
    });
    /* Putting them back in the live list was no use: the live list had
       already been read and sent by the time this answer came back, so a
       card whose results file is not written yet was asked about by nobody
       and sat there with a start time and no result on it -- Chikadze and
       O'Neill, nine hours after they fought (Jose, Sep 20, 2026: "what's
       missing with these"). They are asked about here instead. */
    Object.keys(byEvent).forEach(function (eid) {
      fetch("final/mma-" + eid + ".json").then(function (r) { if (!r.ok) throw new Error(); return r.json(); })
        .then(function (d) {
          applyBoard(byEvent[eid], d);
          /* the file is written as each bout ends now, not once at the end of
             the night, so its being there does not mean the card is over. Only
             the bouts it calls post are settled; the rest are still asked
             about, and the night keeps its place in the order until the last
             one lands (Jose, Sep 22, 2026: "we are only on the second fight,
             why is it settled"). */
          var comps = ((((d || {}).events || [{}])[0] || {}).competitions) || [];
          var over = {};
          comps.forEach(function (c) {
            if ((((c.status || {}).type || {}).state) === "post") over[String(c.id)] = 1;
          });
          var waiting = [];
          byEvent[eid].forEach(function (c) {
            if (over[c.dataset.bout]) c.dataset.settledBout = "1";
            else waiting.push(c);
          });
          if (waiting.length && !/^zb-/.test(eid)) askNight(waiting);
        })
        .catch(function () { if (!/^zb-/.test(eid)) askNight(byEvent[eid]); });
    });
    askNight(live);
  }
  /* the scoreboard for the night each bout was on, one read per night */
  function askNight(cards) {
    if (!cards || !cards.length) return;
    /* The scoreboard answers for today, and only today. A bout that finished
       last night is neither today's nor eight hours old yet -- the window
       between the last bell and the results file being written -- so nothing
       carried it and every bout on that card sat at the top of the day with
       a start time and no result on it, which held the whole row up in the
       order (Jose, Sep 20, 2026: "it's actually annoying"). The scoreboard
       takes a date, so it is asked for the night the bout was on. */
    var byNight = {};
    cards.forEach(function (card) {
      var t = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
      var k = t ? new Date(t).toLocaleDateString("en-CA", { timeZone: "America/New_York" })
                    .replace(/-/g, "")
                : "";
      (byNight[k] = byNight[k] || []).push(card);
    });
    Object.keys(byNight).forEach(function (k) {
      fetch(espnUrl(MMA + (k ? "?dates=" + k : "")))
        .then(function (r) { return r.json(); })
        .then(function (d) { applyBoard(byNight[k], d); })
        .catch(function () {});
    });
  }

  /* ---- what the card paid ----
     A leg counts as a winner where the settler has already marked it: a tick
     against the club, the count box lit on the head-to-head, the number on
     the bar gone green, a tick by the receiver's name. */
  function priceOf(btn) {
    if (!btn) return "";
    return btn.dataset.odds || (btn.childNodes[0].textContent || "").trim();
  }
  /* A leg nobody would take is not a leg the card paid. Minus 1000 is the
     same floor the board uses: risk ten to win one is a deposit, not a bet. */
  var PAIDFLOOR = -1000;
  function tooShort(odds) {
    var n = parseInt(String(odds).replace(/\u2212|\u2013|\u2014/g, "-")
              .replace(/[^\-0-9]/g, ""), 10);
    return !isNaN(n) && n <= PAIDFLOOR;
  }
  function toDec(a) {
    var n = parseInt(String(a).replace(/\u2212|\u2013|\u2014/g, "-").replace(/[^\-0-9]/g, ""), 10);
    if (isNaN(n) || n === 0) return null;
    return n > 0 ? 1 + n / 100 : 1 + 100 / -n;
  }
  /* a paid leg reads the way the slip does: the club as its logo, the man as
     his face, the market as its own marks -- ML and H2H stay as words, and
     the yards drop off the head to head (Jose, Sep 17, 2026) */
  function paidLabel(text, gid) {
    var m = /^(.*?)\s+(ML|H2H|H2H|(\d)\+ (PTD|ATD))$/.exec(String(text || "").trim());
    if (!m) return esc(text);
    /* the card this was read off says which man it is, the same as a slip leg */
    var who = m[1], what = m[2], pic = slipPic(who, sportOf(gid), gid), marks = markFor(what);
    return (pic || '<span class="hitwho">' + esc(who) + "</span>") +
           (marks ? '<span class="slmks" aria-label="' + esc(what) + '">' + marks + "</span>"
                  : '<span class="hitwhat">' + esc(what === "H2H" ? "H2H" : what) + "</span>") +
           (pic ? '<span class="hitalt">' + esc(who) + "</span>" : "");
  }
  /* What a finished bout paid, worked out from its OWN prices and its own
     result -- not by scanning the page for prices marked green, which picked
     up other cards' numbers: Van v Pantoja was headed +425, a price that
     belongs to three other fights and to no market in this one
     (Jose, Sep 22, 2026). One button: the price, his picture, and the marks
     for the market that paid it. */
  /* DraftKings' own name for each market, so the chip says what the bet was
     (Jose, Sep 22, 2026: "give me the right market... how DraftKings has it") */
  /* KO stands for KO, TKO and DQ, the way the book means it; the words
     are too long for the chip (Jose, Sep 25, 2026: "for the visual it can
     be KO") */
  var DKNAME = {
    ml: "$1 to Win", ko: "$1 to Win by KO", sub: "$1 to Win by Submission",
    dec: "$1 to Win by Decision", ud: "$1 to Win by Unanimous Decision",
    sdmd: "$1 to Win by Split or Majority Decision",
    kosub: "$1 to Win by Any Knockout, Submission or DQ",
    finish: "$1 to Win by Any Knockout, Submission or DQ",
    kodec: "$1 to Win by KO or Decision",
    subdec: "$1 to Win by Submission or Decision",
    koonly: "$1 to Win by KO Only", subonly: "$1 to Win by Submission Only",
    deconly: "$1 to Win by Decision Only", finishonly: "$1 to Win by Finish Only",
    cards: "$1 to Win by Decision", rd1only: "$1 to Win in Round 1 Only",
    rd12: "$1 to Win in Rounds 1-2", rd34: "$1 to Win in Rounds 3-4",
    rdlastdec: "$1 to Win in the Final Round or on Decision",
    anyko: "Fight to End by KO", anysub: "Fight to End by Submission",
    anydec: "Fight to Go to Decision", anyud: "Fight to Be Won by Unanimous Decision",
    anysdmd: "Fight to Be Won by Split or Majority Decision",
    dist: "Fight to Go the Distance", nodist: "Fight Not to Go the Distance",
    first60: "Fight to End in the 1st 60 Seconds of Round 1",
    last10: "Fight to End in the Last 10 Seconds of Any Round"
  };
  function dkName(key, who) {
    var t = DKNAME[key];
    if (!t) {
      var m = /^(ko|sub|)rd(\d+)$/.exec(key);
      if (m) {
        t = m[1] === "ko" ? "$1 to Win by KO in Round " + m[2]
          : m[1] === "sub" ? "$1 to Win by Submission in Round " + m[2]
          : "$1 to Win in Round " + m[2];
      }
      var a = /^any(ko|sub)rd(\d+)$/.exec(key);
      if (a) t = a[1] === "ko" ? "Fight to End by KO in Round " + a[2]
                               : "Fight to End by Submission in Round " + a[2];
    }
    if (!t) {
      var g = /^rg(\d+)-(\d+)$/.exec(key);
      if (g) t = "$1 to Win in Rounds " + g[1] + "-" + g[2];
      if (key === "draw") t = "Fight to End in a Draw";
    }
    if (!t) return key.toUpperCase();
    return t.replace("$1", who || "");
  }
  /* the words the marks are read from, so a market gets its own icons */
  var MKWORD = {
    ml: "ML", ko: "BY KO", sub: "BY SUB", dec: "BY DEC", ud: "BY UD",
    sdmd: "BY SD / MD", kosub: "BY KO OR SUB", finish: "BY FINISH",
    kodec: "BY KO OR DEC", subdec: "BY SUB OR DEC", koonly: "BY KO ONLY",
    subonly: "BY SUB ONLY", deconly: "BY DEC ONLY", finishonly: "BY FINISH ONLY",
    cards: "BY DEC", rd1only: "RD1", rd12: "RD1 RD2", rd34: "RD3 RD4",
    rdlastdec: "BY DEC", anyko: "ANY KO", anysub: "ANY SUB", anydec: "ANY DEC",
    anyud: "BY UD", anysdmd: "BY SD / MD", dist: "BY DEC", nodist: "BY FINISH",
    first60: "RD1", last10: "BY FINISH"
  };
  function mkWord(key) {
    if (MKWORD[key]) return MKWORD[key];
    var m = /^(ko|sub|)rd(\d)$/.exec(key);
    if (m) return (m[1] === "ko" ? "BY KO RD" : m[1] === "sub" ? "BY SUB RD" : "RD") + m[2];
    var a = /^any(ko|sub)rd(\d)$/.exec(key);
    if (a) return (a[1] === "ko" ? "ANY KO RD" : "ANY SUB RD") + a[2];
    return key.toUpperCase();
  }
  /* The best price this bout actually paid, out of EVERY market in its own
     file -- no hand-picked list (Jose, Sep 22, 2026). */
  function boutPaid(card) {
    if (!card._paid) return null;
    var res = boutWon(card, card._paid[0], card._paid[1], card._paid[2], card._paid[3]);
    if (res.side < 0) return null;
    var pr = FPROPS[card.dataset.bout] || {};
    var flip = card.dataset.flip === "1";
    var best = null;
    Object.keys(pr).forEach(function (key) {
      var v = pr[key];
      if (key === "rounds" || !v || !v.length) return;
      var mine = key in res.MAN, fight = key in res.FIGHT;
      if (!mine && !fight) return;
      if (mine && !res.MAN[key]) return;
      if (fight && !res.FIGHT[key]) return;
      var slot = mine ? v[flip ? 1 - res.side : res.side] : v[0];
      if (!slot || !slot[0]) return;
      var d = toDec(slot[0]);
      if (d === null) return;
      if (!best || d > best.d) best = { d: d, price: slot[0], key: key };
    });
    if (!best) return null;
    best.who = res.side === 0 ? card.dataset.lf : card.dataset.rf;
    best.word = mkWord(best.key);
    best.name = dkName(best.key, best.who);
    return best;
  }
  function showHitsLater(card) { setTimeout(function () { showHits(card); }, 0); }
  function showHits(card) {
    var box = card.querySelector(".hits");
    if (!box) return;
    var legs = [];

    card.querySelectorAll(".ghead .gteam").forEach(function (side) {
      var b = side.querySelector(".gml button.price");
      if (b && side.querySelector(":scope > .mk.ok")) {
        /* the club is a badge now, so its letters live in the alt text; the
           written name only survives on the cards that have no badge */
        var badge = side.querySelector(".glogo");
        /* a bout has no badge, and reading the whole side as text swallowed the
           W out of the result tile sitting inside it -- WILLIAMSW. The
           fighter's own name is in .fname (Jose, Sep 18, 2026) */
        var fname = side.querySelector(".fname");
        /* his record is drawn inside the name, so reading the name element
           whole put it in the leg: "SHAHBAZYAN17-6 ML" in the box that says
           what the card paid (Jose, Sep 19, 2026: "why the fuck is 17-6 still
           there?"). Read a copy with the record taken out. */
        var bareName = function (e) {
          var c = e.cloneNode(true), r = c.querySelector(".frec");
          if (r) r.parentNode.removeChild(r);
          return c.textContent.trim();
        };
        var club = badge ? (badge.getAttribute("alt") || "")
                 : fname ? bareName(fname)
                 : side.textContent.replace(/[^A-Za-z& ]/g, "").trim();
        legs.push([priceOf(b), (club + " ML").trim()]);
      }
    });

    /* the moneyline lives in the middle column now, not the heading, so the
       one above never found it and a club that won never counted: Clemson
       won at -130 and the box showed -219 (Jose, Sep 26, 2026: "and -219
       was the best?"). The winner is read off the final score. */
    var mlb = card.querySelectorAll(".gline .gml button.price");
    var fin = card.classList.contains("done") || card.dataset.clk === "FINAL";
    if (!card.dataset.bout && fin && mlb.length >= 2 && !legs.some(function (l) { return / ML$/.test(l[1]); })) {
      var sl = parseInt(card.dataset.ls, 10), sr = parseInt(card.dataset.rs, 10);
      if (!isNaN(sl) && !isNaN(sr) && sl !== sr) {
        var wi = sl > sr ? 0 : 1, sides0 = card.querySelectorAll(".ghead .gteam");
        var lg0 = sides0[wi] && sides0[wi].querySelector("img.glogo");
        legs.push([priceOf(mlb[wi]), ((lg0 && lg0.getAttribute("alt")) || "") + " ML"]);
      }
    }

    var lq = famName(card.dataset.lqb);
    var rq = famName(card.dataset.rqb);
    var ends = card.querySelectorAll(".h2hend"), slots = card.querySelectorAll(".h2hodds");
    ends.forEach(function (end, i) {
      var b = slots[i] ? slots[i].querySelector("button.price") : null;
      var n = end.querySelector(".trkbox");
      if (b && n && n.classList.contains("hit")) {
        legs.push([priceOf(b), ((i === 0 ? lq : rq) + " H2H").trim()]);
      }
    });

    card.querySelectorAll(".ptdx").forEach(function (sec) {
      var kind = sec.dataset.kind || "PTD";
      var heads = sec.querySelectorAll(".ptdhead > span");
      sec.querySelectorAll(".ptdside").forEach(function (pane, si) {
        /* whoever this half belongs to: the name over it, else the card's own */
        var who = (si === 0 ? lq : rq);
        var cell = heads[si === 0 ? 0 : heads.length - 1];
        if (cell && !cell.classList.contains("gmk")) {
          var t = cell.textContent.replace(/[\u2713\u2715\u2014]/g, "").trim();
          if (t) who = t;
        }
        /* only the longest line he cleared — 2+ already says he got 1 */
        var best = null;
        pane.querySelectorAll(".ptdbtn").forEach(function (chip) {
          var b = chip.querySelector("button.price");
          var line = chip.querySelector(".ptdline");
          if (!b || !line) return;
          var need = parseInt(line.textContent, 10);
          var tick = pane.querySelector(".ntick--n" + need);
          if (tick && tick.classList.contains("hit") && (!best || need > best[0])) {
            best = [need, priceOf(b)];
          }
        });
        if (best) legs.push([best[1], (who + " " + best[0] + "+ " + kind).trim()]);
      });
    });

    /* every price the game paid, worked out from the prices it was offered
       and his final line -- the card only draws 1+ and 2+, so a 3+ that paid
       +558 never counted and the box said the Raiders at +150 was the best
       (Jose, Sep 27, 2026: "you're saying this is the best bet that won?") */
    var gpr = !card.dataset.bout && fin && typeof PROPS === "object" ? PROPS[card.dataset.espn] : null;
    var qs = card._qbst || {};
    if (gpr) {
      [["l", 0, lq], ["r", 1, rq]].forEach(function (sd) {
        var st = qs[sd[0]] || {}, lad = (gpr.ptd || [])[sd[1]] || [], atd = (gpr.atd || [])[sd[1]] || [];
        lad.forEach(function (slot, k) {
          if (slot && slot[0] && st.ptd !== null && st.ptd !== undefined && st.ptd >= k + 1)
            legs.push([slot[0], (sd[2] + " " + (k + 1) + "+ PTD").trim()]);
        });
        atd.forEach(function (slot, k) {
          if (slot && slot[0] && st.td !== null && st.td !== undefined && st.td >= k + 1)
            legs.push([slot[0], (sd[2] + " " + (k + 1) + "+ ATD").trim()]);
        });
      });
      var ly = (qs.l || {}).pyds, ry = (qs.r || {}).pyds, hh = gpr.h2h || [];
      if (ly !== null && ly !== undefined && ry !== null && ry !== undefined && ly !== ry) {
        var hw = ly > ry ? 0 : 1;
        if (hh[hw] && hh[hw][0]) legs.push([hh[hw][0], ((hw ? rq : lq) + " H2H").trim()]);
      }
    }

    /* a bout's sheet: every method price the result paid. It reads the way an
       NFL leg reads -- the man's face, then the market as its own marks, the
       words only where the marks do not say it (RD2, ANY KO)
       (Jose, Sep 18, 2026). The marks are the row's own, so nothing is
       guessed at here. */
    var lf = lastName(card.dataset.lf || ""), rf = lastName(card.dataset.rf || "");
    function fightLeg(who, marks, word) {
      var pic = who ? slipPic(who, "mma", card.dataset.bout) : "";
      var say = fightSay(String(word).replace(/\s*\u00b7\s*OTHER NO ACTION/i, " ONLY")
                                     .replace(/^BY /i, ""));
      return (pic || (who ? '<span class="hitwho">' + esc(who) + "</span>" : "")) +
             (say.marks ? '<span class="slmks">' + say.marks + "</span>" : "") +
             (say.words ? '<span class="hitwhat">' + esc(say.words) + "</span>" : "") +
             (pic ? '<span class="hitalt">' + esc(who) + "</span>" : "");
    }
    card.querySelectorAll(".mkt .price.paid").forEach(function (b) {
      var cell = b.closest(".fs5cell");
      if (cell) {
        var i = cell.querySelector("i"), mk = i ? i.querySelector(".mktmk") : null;
        legs.push([priceOf(b), "", fightLeg(lf && rf ? lf + " vs " + rf : "",
                                            mk ? mk.innerHTML : "",
                                            i ? i.textContent.trim() : "")]);
        return;
      }
      var row = b.closest(".mktrow");
      if (!row) return;
      var lab = row.querySelector(".mktlab"), m = lab ? lab.querySelector(".mktmk") : null;
      legs.push([priceOf(b), "", fightLeg(row.classList.contains("mktrow--one")
                                            ? (lf && rf ? lf + " vs " + rf : "")
                                            : (row.children[0] === b ? lf : rf),
                                          m ? m.innerHTML : "",
                                          lab ? lab.textContent.trim() : "")]);
    });

    /* a bout works its own out, off its own prices and its own result */
    if (card.dataset.bout) {
      var own = boutPaid(card);
      legs = own ? [[own.price, "",
        fightLeg(own.who, "", own.word) +
        '<span class="hitmkt">' + esc(own.name) + "</span>"]] : [];
    }
    legs = legs.filter(function (l) { return !tooShort(l[0]); });
    if (!legs.length) { box.hidden = true; box.innerHTML = ""; return; }
    /* the best of them, not the run: a fight that paid four ways was read as
       a four leg parlay nobody took (Jose, Sep 22, 2026: "just place the
       highest paying one") */
    legs.sort(function (a, b2) {
      var da = toDec(a[0]), db = toDec(b2[0]);
      return (db === null ? -1 : db) - (da === null ? -1 : da);
    });
    legs = legs.slice(0, 1);

    /* the heading is the payout itself: "4 leg parlay +620" (Jose, Sep 17, 2026) */
    var dec = 1, ok = true;
    legs.forEach(function (l) { var d = toDec(l[0]); if (d === null) ok = false; else dec *= d; });
    /* one heading everywhere: how many legs and what they paid. "What this
       card paid" was the fallback and it only ever showed on a single-leg
       card, which is exactly where the number matters most
       (Jose, Sep 18, 2026) */
    /* no heading: the chip is the whole of it, and it is the one that paid
       most (Jose, Sep 22, 2026: "we don't need 1 LEG, don't include that") */
    var html = '<div class="hitrow">';
    legs.forEach(function (l) {
      html += '<div class="hitleg"><span class="odds">' + l[0] +
              '</span><span class="mkt">' +
              (l[2] || paidLabel(l[1], card.dataset.espn || card.dataset.bout)) + '</span></div>';
    });
    html += "</div>";
    box.innerHTML = html;
    box.hidden = false;
  }

  /* Only games worth asking about: anything already under way or finished,
     and anything inside the next eight days. A card in November has nothing
     to tell us and there are ninety-nine of them on a Saturday. */
  /* A game that is over is not what a reader came for. Once every card in a
     slot reads FINAL the slot sinks below the ones still to come, so what is
     being played and what is still ahead stay at the top, in clock order.
     When the whole board is finished there is nothing to sink past and it
     reads in plain clock order again. It goes by the card's own settled
     state -- the class refresh() sets when ESPN says the game is post -- not
     by a guess at how long a game lasts. Nothing is added to the card: FINAL
     stays where it already is (Jose, Sep 18, 2026). */
  function sinkDone(force) {
    if (!BOARD) return;
    /* A game that ends is moved to the foot of the day, and moving it while
       he is watching pulls the next card up under his eyes: he was on Georgia
       and the board handed him Carolina. It is done on a board he has just
       been given, or once he has left it alone, never mid-read
       (Jose, Sep 19, 2026) */
    if (typeof busy === "function" && busy()) {
      clearTimeout(window._sinkWait);
      window._sinkWait = setTimeout(sinkDone, 15000);
      return;
    }
    if (!force && !document.hidden && Date.now() - LASTTOUCH < 12000) {
      clearTimeout(window._sinkWait);
      window._sinkWait = setTimeout(sinkDone, 15000);
      return;
    }
    var slots = [].slice.call(BOARD.querySelectorAll(":scope > .board"));
    /* ---- what "over" means for a row ----
       Two questions, and either one settles it. Was it long enough ago that
       it cannot still be on -- four hours for football, eight for a fight
       card, the same reach the refreshes use. Or does every card drawn in it
       say FINAL.

       It used to be one question, asked of the cards, and the cards are the
       one thing that is not always there to ask: a row is drawn as it is
       scrolled to, a bill folds away undrawn, a bout that never settled sits
       there saying nothing. So a row with no cards could not be judged and a
       row holding one unsettled bout was judged still running -- eight hours
       after the card was over. Either way it stayed at the top of the day
       with the afternoon's results beneath it (Jose, Sep 20, 2026: "it's just
       an order, why are we struggling to keep order"). The clock never waits
       on a fetch, so it is asked first and nothing can hold a finished row up
       any more. */
    var done = function (sl) {
      var k = sl.dataset.kick ? Date.parse(sl.dataset.kick) : 0;
      var far = +sl.dataset.far || 4 * 3600000;
      if (k && Date.now() > k + far) return true;
      var cards = sl.querySelectorAll(".gcard");
      return cards.length > 0 &&
             [].every.call(cards, function (c) { return c.classList.contains("done"); });
    };
    /* A row only ever becomes over; it never goes back. This used to toggle,
       and a row the build had already marked FINAL was un-marked half a
       second later because its cards are drawn as they are scrolled to and
       were not in it yet -- so a finished 11:00 PM row jumped up beside the
       live 11:00 PM row and then went back down (Jose, Sep 20, 2026: "please
       tell me why MONT vs ORST is there"). Nothing that has finished can
       start again, so the mark is put on and left on. */
    slots.forEach(function (sl) { if (done(sl)) sl.classList.add("done"); });
    /* a finished card leaves its row and goes to the foot of the day, with
       the games it kicked off alongside. A row is only a kickoff time, so
       Kansas State and Georgia sat at the top of the board, finished, because
       Clemson in the same row was not (Jose, Sep 19, 2026: "it should be at
       the bottom of the page") */
    /* A card that is over goes to the back of the line on its own, whatever
       else shares its kickoff: that is the rule for the whole board, not for
       whole rows (Jose, Sep 19, 2026: "it's like an order -- when it says
       final it goes to the back of the line").

       It was doing this before and the heading was the problem: the row at
       the foot copied the row at the top word for word, so 3:30 PM appeared
       twice and read as the board saying the same thing over. The seated row
       says FINAL now, the way the finished fight rows already do, so the two
       can never be mistaken for each other. */
    var tail = BOARD.querySelector(":scope > .hidewrap");
    slots.forEach(function (sl) {
      if (sl.dataset.overflow === "1") return;
      var row = sl.querySelector(":scope > .caro");
      if (!row) return;
      var cards = [].slice.call(row.children);
      var over = cards.filter(function (c) { return c.classList.contains("done"); });
      if (!over.length || over.length === cards.length) return;
      /* A bill is one night, not a kickoff time. Seating its finished bouts in
         a second row gave the board two DWCS S10 Wk 7 -- the same card listed
         twice, one of them saying FINAL with three fights still to come. A
         finished bout goes to the back of its own row instead, so five bouts
         read 1 2 3 4 5 and then 2 3 4 5 1 (Jose, Sep 22, 2026: "it needs to be
         within its own drop-down"). The row itself only says FINAL when every
         bout on it is done, which the rule above already does. */
      if (sl.dataset.lg === "mma") {
        over.forEach(function (c) { row.appendChild(c); });
        return;
      }
      var key = "done-" + (sl.dataset.ord || "0");
      var seat = BOARD.querySelector(':scope > .board[data-overflow="1"][data-of="' + key + '"]');
      if (!seat) {
        seat = document.createElement("div");
        seat.className = "board board--nfl done";
        seat.dataset.overflow = "1";
        seat.dataset.of = key;
        seat.dataset.ord = String(1000 + (+sl.dataset.ord || 0));
        seat.dataset.kick = sl.dataset.kick || "";
        seat.dataset.lg = sl.dataset.lg || "";
        seat.dataset.far = sl.dataset.far || "";
        var head = sl.querySelector(":scope > .slot-h");
        if (head) {
          var copy = head.cloneNode(true);
          /* the one thing that must differ from the row it came from */
          var sw = copy.querySelector(".swipe");
          if (sw) sw.parentNode.removeChild(sw);
          if (!copy.querySelector(".slotfin")) {
            var fin = document.createElement("span");
            fin.className = "slotfin";
            fin.textContent = "FINAL";
            copy.appendChild(fin);
          }
          seat.appendChild(copy);
        }
        var into = document.createElement("div");
        into.className = "caro";
        seat.appendChild(into);
        if (tail) BOARD.insertBefore(seat, tail); else BOARD.appendChild(seat);
      }
      var into2 = seat.querySelector(":scope > .caro");
      over.forEach(function (c) { into2.appendChild(c); });
    });
    /* The rows that were just seated are rows too. They were made after this
       list was taken, so they took no part in the ordering -- and since every
       other row is then moved in front of the shelf, the seated one ended up
       above all of them: a FINAL 11:00 PM at the very top with the live
       11:00 PM under it, which is what he was watching happen as he switched
       cards on and off (Jose, Sep 20, 2026). The list is taken again. */
    slots = [].slice.call(BOARD.querySelectorAll(":scope > .board"));
    /* one heading per kickoff: games of one slot that finished at different
       times were seated in separate rows, and the board read NFL SUN 9/27
       1:00 PM FINAL twice (Jose, Sep 27, 2026: "why do I have two"). Finished
       rows with the same heading are one row. */
    var byHead = {};
    slots.forEach(function (sl) {
      if (!sl.classList.contains("done") || sl.dataset.lg === "mma") return;
      var h = sl.querySelector(":scope > .slot-h"), row = sl.querySelector(":scope > .caro");
      if (!h || !row) return;
      var k = sl.dataset.lg + "|" + h.textContent.replace(/\s+/g, " ").trim();
      if (!byHead[k]) { byHead[k] = row; return; }
      [].slice.call(row.children).forEach(function (c) { byHead[k].appendChild(c); });
      sl.parentNode.removeChild(sl);
    });
    slots = [].slice.call(BOARD.querySelectorAll(":scope > .board"));
    var over = slots.filter(function (sl) { return sl.classList.contains("done"); });
    if (!over.length || over.length === slots.length) {
      // nothing settled, or everything is: the clock order stands
      over = [];
    }
    /* Both groups run by the clock. Sorting the back of the line by the order
       the rows were built in was right only while nothing moved between the
       groups -- and the whole point is that rows move. A row that finished
       while he watched was built near the front, so when it went to the back
       it went to the front of the back: 10:30 PM sat above 11:30 AM
       (Jose, Sep 20, 2026: "what, doesn't this make sense"). */
    var tick = function (sl) {
      var t = sl.dataset.kick ? Date.parse(sl.dataset.kick) : NaN;
      return isNaN(t) ? (+sl.dataset.ord || 0) : t;
    };
    var order = slots.slice().sort(function (a, b) {
      var ga = over.indexOf(a) >= 0 ? 1 : 0, gb = over.indexOf(b) >= 0 ? 1 : 0;
      if (ga !== gb) return ga - gb;
      var d = tick(a) - tick(b);
      if (d) return d;
      return (+a.dataset.ord || 0) - (+b.dataset.ord || 0);
    });
    var same = order.every(function (sl, i) { return sl === slots[i]; });
    if (same) return;
    /* the hidden-cards drawer sits at the foot, so the slots go in front of it */
    var tail = BOARD.querySelector(":scope > .hidewrap");
    order.forEach(function (sl) {
      if (tail) BOARD.insertBefore(sl, tail); else BOARD.appendChild(sl);
    });
  }

  /* The board was put in order once, when it was built, and again two and a
     half seconds later. Anything that finished after that stayed where it
     was: the cards said FINAL and the row above them did not move. A card
     that settles asks for the order now, and sinkDone stands down by itself
     while he is reading, so nothing moves under his eyes. */
  function askSink() {
    clearTimeout(window._sinkAsk);
    window._sinkAsk = setTimeout(function () { sinkDone(); }, 1200);
  }
  window.askSink = askSink;
  /* ---- when to look again ----
     Only while something on the board is on or about to be. Thirty seconds
     while any game or bout is live (five for a bout, below). Otherwise the
     next look waits for the next kickoff on the board -- twenty minutes
     before it -- and never comes sooner than a minute. Once the last thing
     on the board is over there is nothing left to ask about, and nothing is
     asked: 0 means stop. A college Saturday looks after college, a Sunday
     after the NFL, because the board is what is on the tab (Jose, Sep 20,
     2026: "no more polling for non-live events after they are done -- thin
     for CFB on CFB days and NFL on NFL days"). */
  /* ---- the game page (Jose, Sep 30, 2026) ----
     Off the ticket on a card: the two clubs with their moneylines, the two
     passers head to head, then the passing and the rushing ladders, a
     slider over the rungs the book holds. The moneyline and the head to
     head are one side or the other, and the side he taps gets its own
     case, said from the board's finals (site/suggest.json, build/suggest.py);
     the ladders can take both men, each with his own case for the rung. A
     price on the page is the same button the card has, so a tap puts the
     leg on the slip; what he picked is kept per game, so leaving and coming
     back finds it as he left it. */
  var SUGGEST = null;
  function suggestLoad(cb) {
    if (SUGGEST) { cb(SUGGEST); return; }
    fetch("suggest.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (j) { SUGGEST = j || {}; cb(SUGGEST); })
      .catch(function () { SUGGEST = {}; cb(SUGGEST); });
  }
  function gamePage(card) {
    var id = card.dataset.espn, lg = card.dataset.lg || "nfl";
    var rows = lg === "college-football" ? (typeof CFB !== "undefined" ? CFB : []) : SCHED;
    var g = null;
    for (var i = 0; i < rows.length; i++) if (String(rows[i][1]) === String(id)) { g = rows[i]; break; }
    if (!g) return;
    var T = FOOTBALL[lg], pr = PROPS[id] || {};
    var KEY = "arena.gp." + id, st = { ml: null, h2h: null, ptd: { n: 1, who: null }, atd: { n: 1, who: null } };
    try { st = Object.assign(st, JSON.parse(localStorage.getItem(KEY) || "{}")); } catch (e) {}
    /* a ladder is one man or the other, like the rest (Jose, Sep 30, 2026:
       "it's either or"); a pick kept the old way is read as that man */
    ["ptd", "atd"].forEach(function (k) {
      st[k] = st[k] || { n: 1, who: null };
      if (st[k].who === undefined) st[k].who = st[k].away ? "away" : st[k].home ? "home" : null;
    });
    var keep = function () { try { localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) {} };
    var side = { away: { club: g[3], qb: g[5], qid: g[6], ml: [g[T.ml[0]], g[T.ml[1]]] },
                 home: { club: g[4], qb: g[7], qid: g[8], ml: [g[T.ml[2]], g[T.ml[3]]] } };
    var logos = card.querySelectorAll(".gteam img.glogo");
    var lg0 = logos[0] ? logos[0].getAttribute("src") : "", lg1 = logos[1] ? logos[1].getAttribute("src") : "";
    var faceDir = lg === "college-football" ? "face/college-football/" : "face/nfl/";
    var dlg = document.querySelector('dialog.gamepage[data-espn="' + id + '"]');
    if (!dlg) {
      dlg = document.createElement("dialog");
      dlg.className = "sheet gsheet gamepage";
      dlg.dataset.espn = id;
      dlg.innerHTML = '<div class="sheet__head"><button class="sheet__x" type="button" data-shut aria-label="Back">' +
        '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M15 5l-7 7 7 7" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg></button>' +
        '</div><div class="sheet__scroll"><div class="gp"></div></div>';
      document.body.appendChild(dlg);
    }
    dlg._card = card;
    var root = dlg.querySelector(".gp");
    /* sel: whether this price is one he has chosen, which is what the
       button at the foot adds -- a side he has not picked is not a leg */
    var price = function (slot, leg, sel) {
      if (!slot || !slot[0]) return '<span class="ghost" aria-hidden="true"></span>';
      var h = priceSlot(slot[0], slot[1]);
      return h.replace("<button ", '<button data-leg="' + esc(leg) + '"' + (sel ? ' data-sel="1"' : "") + ' ');
    };
    var rungs = function (kind) {
      var n = 1, arr = pr[kind] || [];
      arr.forEach(function (list) { (list || []).forEach(function (x, k) { if (x && x[0] && k + 1 > n) n = k + 1; }); });
      return Math.min(6, n);
    };
    var box = function (call, text, tag) {
      if (!text) return "";
      var word = call === "take" ? "TAKE" : call === "lean" ? "LEAN" : call === "pass" ? "PASS" : (tag || "");
      return '<div class="gpbox">' + (word ? '<b class="gpc gpc--' + (call || "side") + '">' + esc(word) + '</b>' : "") + esc(text) + '</div>';
    };
    var draw = function (S) {
      var sg = (S || {})[id] || {}, lean = sg.lean || {};
      var h = "";
      /* the two clubs */
      h += '<div class="gpsides">';
      ["away", "home"].forEach(function (w) {
        var d = side[w];
        h += '<div class="gpside' + (st.ml === w ? " on" : "") + (lean.ml === w ? " lean" : "") + '" data-side="' + w + '"><div class="gpclub">' +
          ((w === "away" ? lg0 : lg1) ? '<img src="' + (w === "away" ? lg0 : lg1) + '" alt="">' : "") +
          esc(d.club) + '<small>' + (w === "away" ? "AWAY" : "HOME") + '</small></div>' +
          '<div class="gpml">' + price(d.ml, d.club + " ML", st.ml === w) + '</div></div>';
      });
      h += '<div class="gpvs"><svg><use href="#vs"/></svg></div></div>';
      if (st.ml && (sg.ml || {})[st.ml]) h += box(null, sg.ml[st.ml], side[st.ml].club);
      h += '<div class="gpsep"></div>';
      /* the two passers, head to head */
      var hh = pr.h2h || [];
      h += '<div class="gph2h">' + '<div class="gpp">' + price(hh[0], famName(side.away.qb) + " H2H", st.h2h === "away") + '<i>H2H</i></div>' +
        '<img class="gpface' + (st.h2h === "away" ? " on" : "") + (lean.h2h === "away" ? " lean" : "") + '" data-h2h="away" src="' + faceDir + esc(side.away.qid) + '.png" alt="">' +
        '<div class="gpvs2"><svg><use href="#vs"/></svg></div>' +
        '<img class="gpface' + (st.h2h === "home" ? " on" : "") + (lean.h2h === "home" ? " lean" : "") + '" data-h2h="home" src="' + faceDir + esc(side.home.qid) + '.png" alt="">' +
        '<div class="gpp">' + price(hh[1], famName(side.home.qb) + " H2H", st.h2h === "home") + '<i>H2H</i></div></div>' +
        '<div class="gpnames"><span>' + esc(famName(side.away.qb)).toUpperCase() + '</span><span>' + esc(famName(side.home.qb)).toUpperCase() + '</span></div>';
      if (st.h2h && (sg.h2h || {})[st.h2h]) h += box(null, sg.h2h[st.h2h], famName(side[st.h2h].qb));
      /* the ladders */
      [["ptd", "PASSING TOUCHDOWNS", "PTD"], ["atd", "RUSHING TOUCHDOWNS", "ATD"]].forEach(function (k) {
        var kind = k[0], mx = rungs(kind), s2 = st[kind];
        if (s2.n > mx) s2.n = mx;
        if (s2.n < 1) s2.n = 1;
        h += '<div class="gpsep"></div><div class="gpttl">' + k[1] + '</div>' +
          '<div class="gpsl"><input type="range" min="1" max="' + mx + '" step="1" value="' + s2.n + '" data-kind="' + kind + '" style="--p:' + (mx > 1 ? (s2.n - 1) / (mx - 1) * 100 : 0) + '%">' +
          '<div class="gplab"><small>MIN 1</small><small>MAX ' + mx + '</small></div><div class="gpval">' + s2.n + '</div></div>';
        /* one row: the two faces, then the lit man's name, his rung and his
           price in the same line (Jose, Sep 30, 2026: "in line, in one row");
           a second lit man takes a second row under, lined up with the first */
        var lit = s2.who ? [s2.who] : [];
        var info = function (w) {
          var slot = ((pr[kind] || [])[w === "away" ? 0 : 1] || [])[s2.n - 1], who = famName(side[w].qb);
          return '<span class="gpwho"><b>' + esc(who).toUpperCase() + '</b><small>' + s2.n + ' OR MORE</small></span>' +
            '<div class="gpp">' + price(slot, who + " " + s2.n + "+ " + k[2], true) + '</div>';
        };
        h += '<div class="gprow">' +
          '<img class="gpface' + (s2.who === "away" ? " on" : "") + (s2.n === 1 && lean[kind] === "away" ? " lean" : "") + '" data-pick="' + kind + ':away" src="' + faceDir + esc(side.away.qid) + '.png" alt="">' +
          '<img class="gpface' + (s2.who === "home" ? " on" : "") + (s2.n === 1 && lean[kind] === "home" ? " lean" : "") + '" data-pick="' + kind + ':home" src="' + faceDir + esc(side.home.qid) + '.png" alt="">' +
          (lit.length ? info(lit[0]) : '<b class="gpnone"></b>') + '</div>';
        lit.forEach(function (w) {
          var c = (((sg[kind] || {})[w] || {})[String(s2.n)]) || {};
          h += box(c.call, c.text);
        });
        h += "";
      });
      /* no button at the foot: a price on the page is the slip already (Jose, Sep 30, 2026) */
      h += '<div class="gpfoot"></div>';
      root.innerHTML = h;
      root.querySelectorAll("button.price").forEach(function (b) {
        if (window.slipHas && window.slipHas(b.dataset.oid)) b.classList.add("on");
      });
      count();
    };
    var count = function () {
      var n = 0;
      root.querySelectorAll("button.price[data-sel]").forEach(function (b) { if (!b.classList.contains("on")) n++; });
      var add = root.querySelector(".gpadd");
      if (add) add.textContent = "ADD TO BETSLIP" + (n ? " (" + n + ")" : "");
    };
    if (!root._wired) {
      root._wired = true;
      root.addEventListener("click", function (e) {
        if (e.target.closest("button.price")) { setTimeout(count, 0); return; }
        var sd = e.target.closest(".gpside");
        if (sd) { st.ml = st.ml === sd.dataset.side ? null : sd.dataset.side; keep(); draw(SUGGEST); return; }
        var f = e.target.closest("img.gpface");
        if (f && f.dataset.h2h) { st.h2h = st.h2h === f.dataset.h2h ? null : f.dataset.h2h; keep(); draw(SUGGEST); return; }
        if (f && f.dataset.pick) {
          var kv = f.dataset.pick.split(":");
          st[kv[0]].who = st[kv[0]].who === kv[1] ? null : kv[1]; keep(); draw(SUGGEST); return;
        }
      });
      root.addEventListener("input", function (e) {
        var r = e.target.closest("input[type=range]");
        if (!r) return;
        st[r.dataset.kind].n = +r.value; keep(); draw(SUGGEST);
      });
    }
    draw(SUGGEST || {});
    if (typeof openSheet === "function") openSheet(dlg); else dlg.show();
    suggestLoad(function (S) { if (dlg.open) draw(S); });
  }
  window.gamePage = gamePage;
