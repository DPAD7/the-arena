  function started(card) {
    return !!card.dataset.kick && Date.now() >= Date.parse(card.dataset.kick);
  }

  /* Once the game is on, the card stops being prices and becomes what he has
     done -- exactly the rows the mock draws (notes/mocks/mock_game.py, the
     `under_way` half): the score with the clock between it, the passing yards
     over the VS, his passing touchdowns with the clip on the count, and his
     rushing touchdowns. The 2+ rung and the club price come off; one count
     answers both rungs. A leg he had double tapped keeps its gold box and
     turns green or red when it settles; a leg he never touched stays plain
     (Jose, Sep 21, 2026: "we marked the pregame live final").

     Every number is MIRRORED out of the node the live pass already writes --
     the .trkbox counts, the yard boxes -- so nothing upstream had to change
     and no count can go missing because this rewrote its seat. */
  /* one test for every leg on a card, whatever kind: marked on the board, kept
     in his marks by its id, or on a slip from the book. The head to head had
     all three and the moneyline and the touchdown rungs had only the first,
     so a moneyline he had on a DraftKings slip never turned green
     (Jose, Sep 28, 2026: "take your one edit and apply it to everything") */
  function legMine(btn, oid) {
    oid = oid || (btn && btn.dataset.oid) || "";
    if (btn && (btn.classList.contains("on") || btn.classList.contains("placed"))) return true;
    if (window.isPlaced && window.isPlaced(oid)) return true;
    return !!(oid && typeof DKB === "object" && DKB && (DKB.bets || []).some(function (bt) {
      return (bt.legs || []).some(function (lg) { return lg.sel === oid; });
    }));
  }
  function mlOids(gid) {
    var got = ["", ""];
    [[typeof SCHED === "object" ? SCHED : [], 9], [typeof CFB === "object" ? CFB : [], 10]].forEach(function (pair) {
      pair[0].forEach(function (row) {
        if (String(row[1]) === String(gid)) got = [row[pair[1] + 1] || "", row[pair[1] + 3] || ""];
      });
    });
    return got;
  }
  function numChip(v, on, placed, won) {
    var b = document.createElement("b");
    b.className = "pnum" + (on ? " on" : "") + (placed ? " placed" : "") +
      (won === true ? " won" : won === false ? " lost" : "");
    b.appendChild(document.createTextNode(v === "" || v === null ? "\u2013" : String(v)));
    return b;
  }
  function stateV3(card) {
    if (!card || card.dataset.v3 !== "1") return;
    var on = isOver(card) || started(card);
    card.classList.toggle("gcard--on", on);
    var stack = card.querySelector(".gmid > .gstack");
    if (!stack) return;
    /* the clock is never read off the card itself: before kickoff the row's
       heading carries it, and once the game is on the score row does */
    var clk0 = card.querySelector(".gtime");
    if (clk0) clk0.hidden = true;
    if (!on) {
      card.querySelectorAll(".pnum, .gyds").forEach(function (n) {
        var keep0 = n.querySelector(".ptdplay");
        if (keep0) { var st = n.closest(".ptdbtn"); if (st) st.appendChild(keep0); }
        n.remove();
      });
      return;
    }
    var done = isOver(card);

    /* the eye, LIVE and the play mark stay one row at the top: the live pass
       rebuilds them inside the clock, so they are lifted back out before the
       clock itself goes down into the score row */
    var when = card.querySelector(".gwhen"), gt = card.querySelector(".gtime");
    var lbar = gt && gt.querySelector(".glivebar");
    if (lbar && when && lbar.parentNode !== when) {
      /* only ever one: the older bars go before the new one is seated */
      when.querySelectorAll(".glivebar").forEach(function (old0) { old0.remove(); });
      when.appendChild(lbar);
      /* the new bar brought its own badge; the old one had already been
         lifted beside the trend and outlived its bar, so the row wore two
         (Jose, Sep 25, 2026: "why is there 2 live icons again"). The badge
         is seated now, the older one dropped. */
      if (window.orderTop) window.orderTop(card);
    }

    /* the score, the clock or FINAL between the two of them */
    var line = stack.querySelector(".gline"), ends = line ? line.querySelectorAll(".gh2h") : [];
    if (line && ends.length === 2) {
      line.querySelectorAll(".pnum").forEach(function (n) { n.remove(); });
      var mk = line.querySelector(".gmk");
      if (mk) {
        mk.innerHTML = "";
        var clk = document.createElement("i");
        clk.className = "gclk" + (done ? " gclk--fin" : "");
        /* the time over the quarter, stacked, so "3:51 - 1ST" never runs
           into the score beside it (Jose, Sep 25, 2026) */
        var said = card.dataset.clk || (done ? "FINAL" : "");
        var two = said.split(/\s+-\s+/);
        /* "End of 1st" stacks the same way: END over 1ST (Jose, Sep 25, 2026) */
        var endOf = /^end of (.+)$/i.exec(said);
        if (endOf) two = ["End", endOf[1]];
        /* and Halftime: HALF over TIME (Jose, Sep 26, 2026) */
        if (/^half\s*time$/i.test(said)) two = ["Half", "Time"];
        if (two.length === 2) {
          clk.classList.add("gclk--two");
          two.forEach(function (x) { var b = document.createElement("b"); b.textContent = x; clk.appendChild(b); });
        } else clk.textContent = said;
        mk.appendChild(clk);
      }
      var ls = card.dataset.ls, rs = card.dataset.rs;
      if (ls !== undefined && rs !== undefined) {
        var l = parseInt(ls, 10), r = parseInt(rs, 10);
        /* a club price he had marked keeps its gold on the score that
           answered it (Jose, Sep 22, 2026: "where is the gold box around the
           stuff I checked off") */
        var mo = mlOids(card.dataset.espn);
        [[ends[0], l, r, 0], [ends[1], r, l, 1]].forEach(function (e) {
          var ml = e[0].querySelector(".gml button.price");
          var mk = legMine(ml, (ml && ml.dataset.oid) || mo[e[3]]);
          e[0].appendChild(numChip(e[1], e[1] > e[2], mk,
            mk && done ? e[1] > e[2] : null));
        });
      }
    }

    /* the passing yards, the VS mark between them, under the touchdown rows */
    var yb = card.querySelectorAll(".gbody .h2hrow .h2hend > .trkbox");
    var yrow = stack.querySelector(".gyds");
    if (yb.length === 2) {
      if (!yrow) {
        yrow = document.createElement("div");
        yrow.className = "gline gyds";
        yrow.innerHTML = '<span class="gh2h"></span><i class="gmk">' +
          '<svg viewBox="0 0 26 22" aria-hidden="true"><use href="#vs"/></svg>' +
          '</i><span class="gh2h"></span>';
      }
      /* the order down the middle: the score, the touchdowns, then the
         head to head on passing yards last (Jose, Sep 26, 2026: "PTD 1-2,
         RTD, then H2H") */
      if (stack.lastElementChild !== yrow) stack.appendChild(yrow);
      var ye = yrow.querySelectorAll(".gh2h");
      ye[0].innerHTML = ""; ye[1].innerHTML = "";
      var ly = parseInt(yb[0].textContent, 10) || 0, ry = parseInt(yb[1].textContent, 10) || 0;
      /* the head to head he marked wears the same box the moneyline does:
         gold while it is on, green or red once the game is over -- the price
         beside the name goes then, so the box is what says it (Jose, Sep 27,
         2026: "the box goes around the H2H section like ML does") */
      var hslots = card.querySelectorAll(".h2hodds");
      var hpr = ((typeof PROPS === "object" && PROPS[card.dataset.espn]) || {}).h2h || [];
      [[ye[0], ly, ry, 0], [ye[1], ry, ly, 1]].forEach(function (e) {
        var hb = hslots[e[3]] ? hslots[e[3]].querySelector("button.price") : null;
        /* once the game is over the button has gone, so the price is found
           by its own id: marked on the board, or on a slip from the book */
        var oid = (hb && hb.dataset.oid) || (hpr[e[3]] && hpr[e[3]][1]) || "";
        var mine = legMine(hb, oid);
        e[0].appendChild(numChip(e[1], e[1] > e[2], mine, mine && done ? e[1] > e[2] : null));
      });
      /* the margin under the VS, in the room below the rows, leaning to the
         side that leads (Jose, Sep 26, 2026: "put the difference under the
         VS column") */
      var gap = stack.querySelector(".gydsgap");
      if (!gap) { gap = document.createElement("div"); gap.className = "gydsgap"; }
      if (stack.lastElementChild !== gap) stack.appendChild(gap);
      var dd = ly - ry;
      /* a chevron on the leader's side, pointing at him, in place of the
         plus (Jose, Sep 27, 2026: "make it an arrow < for who's winning") */
      var chev = function (pts) {
        return '<svg class="gydsarr" viewBox="0 0 10 12" aria-hidden="true"><polyline points="' + pts +
          '" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>';
      };
      gap.innerHTML = !dd ? "" : dd > 0 ? chev("7,1.5 2.5,6 7,10.5") + Math.abs(dd)
                                      : Math.abs(dd) + chev("3,1.5 7.5,6 3,10.5");
      gap.classList.toggle("gydsgap--l", dd > 0);
      gap.classList.toggle("gydsgap--r", dd < 0);
    }

    /* his touchdowns, in the seat the price sat in, and the clip on the count */
    card.querySelectorAll(".ptdx").forEach(function (sec) {
      var prow = sec.querySelector(".ptdrow");
      if (!prow) return;
      prow.querySelectorAll(".pnum").forEach(function (n) {
        /* the play mark is the card's, not the chip's: put it back in its seat
           before the chip goes, or it is destroyed with it */
        var keep = n.querySelector(".ptdplay");
        if (keep) {
          var seat0 = n.closest(".ptdbtn");
          if (seat0) seat0.appendChild(keep);
        }
        n.remove();
      });
      var counts = sec.querySelectorAll(".ptdcount");
      [["l", 0], ["r", 1]].forEach(function (sd) {
        var side = prow.querySelector(".ptdside--" + sd[0]);
        var box = counts[sd[1]];
        if (!side || !box) return;
        var v = parseInt(box.textContent, 10);
        if (isNaN(v)) v = 0;
        /* the gold he put on the first rung carries over to the count */
        /* he may have marked the 2+ rung rather than the 1+, and that rung's
           chip is not drawn once the game is on -- so the count answers for
           any rung of his he had marked */
        var placed = false, wonAt = 0;
        side.querySelectorAll(".ptdbtn button.price").forEach(function (b0, i0) {
          if (legMine(b0)) {
            placed = true;
            var ln0 = b0.closest(".ptdbtn").querySelector(".ptdline");
            var n0 = ln0 ? parseInt(ln0.textContent, 10) : i0 + 1;
            if (!isNaN(n0)) wonAt = Math.max(wonAt, n0);
          }
        });
        /* and every rung the card does not draw -- 3+, 4+ and up -- by its id */
        var lad0 = ((((typeof PROPS === "object" && PROPS[card.dataset.espn]) || {})[sec.dataset.kind === "ATD" ? "atd" : "ptd"]) || [])[sd[1]] || [];
        lad0.forEach(function (slot, k) {
          if (slot && slot[1] && legMine(null, slot[1])) { placed = true; wonAt = Math.max(wonAt, k + 1); }
        });
        var oth = counts[sd[1] ? 0 : 1];
        var ov = oth ? parseInt(oth.textContent, 10) : 0;
        if (isNaN(ov)) ov = 0;
        var chip = numChip(v, v > ov, placed,
          placed && done ? v >= (wonAt || 1) : null);
        chip.classList.add("pnum--" + sd[0]);
        /* each count opens its own kind: the passing count every touchdown he
           threw, the rushing count every one he ran in
           (Jose, Sep 22, 2026: "if we hit rushing play button, it should be
           the rushing") */
        var play = side.querySelector(".ptdplay");
        if (play) chip.appendChild(play);
        chip.classList.toggle("has-clip", !!play);
        if (!done) {
          var rungs0 = [].slice.call(side.querySelectorAll(".ptdbtn button.price"));
          var live0 = rungs0.filter(function (b1) { return b1.classList.contains("on"); })[0];
          var want0 = live0 || rungs0[0];
          if (want0) {
            chip.classList.add("pnum--tap");
            chip.addEventListener("click", function (ev) {
              ev.stopPropagation();
              want0.click();
              stateV3(card);
            });
          }
        }
        var seat = side.querySelector(".ptdbtn:not([hidden])");
        if (seat) seat.appendChild(chip);
        else side.appendChild(chip);
      });
      /* one count answers every rung, so only the first mark is drawn */
      var marks = sec.querySelectorAll(".gvmid .gmk");
      marks.forEach(function (m, i) { m.hidden = i > 0; });
      sec.querySelectorAll(".grn").forEach(function (r) { r.hidden = true; });
    });

    /* The foot, the way the mock draws it: the bar grows OUT OF the VS toward
       whoever is up on passing yards, how far it reaches being the margin as a
       share of the two totals, and it wears that club's own colour. The margin
       is written under the bar, centred on his half. The old bar filled a whole
       half and hung the margin off the tick, which is not what we drew. */
    var bar = card.querySelector(".h2hbar");
    if (bar && yb.length === 2) {
      var a = parseInt(yb[0].textContent, 10) || 0, b2 = parseInt(yb[1].textContent, 10) || 0;
      var tot = a + b2, lead = a - b2;
      var fill = bar.querySelector(".h2hfill"), chip2 = bar.querySelector(".h2hchip");
      /* The whole bar is the two clubs, one color blending into the other,
         and whoever is up on passing yards fills more of it: the blend sits
         at his share of the two totals. His margin rides his own corner,
         "+45" (Jose, Sep 26, 2026, the red-to-blue bar he sent). */
      var teams = card.querySelectorAll(".gteam");
      var abL = teams[0] ? ((teams[0].querySelector("img.glogo") || {}).alt || "") : "";
      var abR = teams[1] ? ((teams[1].querySelector("img.glogo") || {}).alt || "") : "";
      var cL = driveHue(abL, lgOf(card)) || "#8e8e93", cR = driveHue(abR, lgOf(card)) || "#8e8e93";
      /* two blues read as one bar: the left club takes its second color,
         the rule the card's own lettering already follows */
      if (hueGap(cL, cR) < 30) {
        var alt0 = ALTCOLOR[abL], alt1 = ALTCOLOR[abR];
        if (alt0 && hueGap(alt0, cR) >= 30) cL = alt0;
        else if (alt1 && hueGap(cL, alt1) >= 30) cR = alt1;
      }
      var at = tot ? Math.max(12, Math.min(88, 100 * a / tot)) : 50;
      /* the VS stands where the two colors meet (Jose, Sep 26, 2026) */
      var vs0 = bar.querySelector(".gvs");
      if (vs0) vs0.style.left = at + "%";
      var G = "linear-gradient(90deg, " + cL + " 0%, " + cL + " " + Math.max(0, at - 18) + "%, " +
              cR + " " + Math.min(100, at + 18) + "%, " + cR + " 100%)";
      var yr = card.querySelector(".gyds");
      if (yr) {
        yr.classList.add("gyds--blend");
        yr.style.setProperty("--blend", G);
        var ymk = yr.querySelector(".gmk");
        /* the VS stays in the middle, in line with the marks above it; only
           the colors move (Jose, Sep 26, 2026) */
        if (ymk) ymk.style.left = "50%";
        /* each name and his price stand level with the glass row
           (Jose, Sep 26, 2026: "why isn't it in line with the name") */
        requestAnimationFrame(function () { levelNames(card, yr); });
      }
      bar.classList.add("h2hbar--blend");
      bar.style.background = "";
      bar.style.setProperty("--blend", "linear-gradient(90deg, " + cL + " 0%, " + cL + " " + Math.max(0, at - 18) + "%, " +
                             cR + " " + Math.min(100, at + 18) + "%, " + cR + " 100%)");
      if (fill) fill.style.width = "0";
      if (chip2) {
        chip2.classList.add("gyd");
        chip2.classList.remove("gjersey");
        chip2.removeAttribute("data-jersey");
        chip2.innerHTML = "";
        chip2.textContent = (tot && lead !== 0) ? "+" + Math.abs(lead) : "";
        chip2.classList.toggle("gyd--r", lead < 0);
        chip2.style.opacity = (tot && lead !== 0) ? "" : "0";
        chip2.style.left = chip2.style.right = chip2.style.transform = chip2.style.color = "";
      }
    }
  }
  window.stateV3 = stateV3;
  function levelNames(card, row) {
    if (!row || !row.offsetHeight) return;
    var rr = row.getBoundingClientRect(), mid = rr.top + rr.height / 2;
    card.querySelectorAll(".gside .h2hnm").forEach(function (nm) {
      /* the line that holds the name: the price if he has one, else the name */
      var ln = nm.querySelector(":scope > .h2hodds") || nm.querySelector(".h2hnmtx") || nm;
      var lr = ln.getBoundingClientRect();
      if (!lr.height) return;
      var now = parseFloat(getComputedStyle(nm).bottom) || 0;
      nm.style.bottom = Math.round(now + (lr.top + lr.height / 2 - mid)) + "px";
    });
  }
  /* the Kalshi shirt as two shading layers, dyed at runtime and kept */
  var DYED = {}, DYETPL = null;
  function dyeJersey(body, sleeve, done) {
    var key = body + sleeve;
    if (DYED[key]) { done(DYED[key]); return; }
    if (!DYETPL) DYETPL = Promise.all(["ico/jersey/_body.png", "ico/jersey/_sleeve.png"].map(function (u) {
      return new Promise(function (ok) { var im = new Image(); im.onload = function () { ok(im); }; im.onerror = function () { ok(null); }; im.src = u; });
    }));
    DYETPL.then(function (tpl) {
      if (!tpl[0] || !tpl[1]) { done(null); return; }
      var W = tpl[0].naturalWidth, H = tpl[0].naturalHeight;
      var out = document.createElement("canvas"); out.width = W; out.height = H;
      var ctx = out.getContext("2d");
      [[tpl[0], body], [tpl[1], sleeve]].forEach(function (p) {
        var c = document.createElement("canvas"); c.width = W; c.height = H;
        var x = c.getContext("2d");
        x.fillStyle = p[1]; x.fillRect(0, 0, W, H);
        x.globalCompositeOperation = "multiply"; x.drawImage(p[0], 0, 0);
        x.globalCompositeOperation = "destination-in"; x.drawImage(p[0], 0, 0);
        ctx.drawImage(c, 0, 0);
      });
      try { DYED[key] = out.toDataURL("image/png"); } catch (e) { DYED[key] = null; }
      done(DYED[key]);
    });
  }
  /* A college card carries two sections and each was repeating the same two
     names and a label. The names go up once, above both, and the labels come
     off -- the football says one thing and the bolt says the other. */
  function cfbOnce(card) {
    if (card.dataset.lg !== "college-football") return;
    var secs = card.querySelectorAll(".ptdx");
    if (!secs.length || card.querySelector(".cfbnames")) return;
    /* with a head to head on the card the names ride its bar, the way they do
       on an NFL card, so no separate name row is built (Jose, Sep 17, 2026) */
    if (card.querySelector(".h2hx")) {
      card.querySelectorAll(".ptdx .ptdhead").forEach(function (h) { h.remove(); });
      return;
    }
    var first = secs[0].querySelector(".ptdhead");
    var sides = first ? first.querySelectorAll("span:not(.gmk)") : [];
    if (sides.length === 2) {
      var row = document.createElement("div");
      row.className = "cfbnames";
      /* the row mirrors the ball row below it -- side, count, count, side --
         so each name stands centered over its own prices and balls */
      [0, 1].forEach(function (i) {
        var nm = document.createElement("span");
        nm.textContent = sides[i].textContent;
        nm.style.color = sides[i].style.color ||
                         (i ? "#ffffff" : "#ffffff");
        if (i === 1) {
          [0, 1].forEach(function () {
            var sp = document.createElement("i");
            sp.className = "cfbgap";
            sp.textContent = "0";
            row.appendChild(sp);
          });
        }
        row.appendChild(nm);
      });
      secs[0].parentNode.insertBefore(row, secs[0]);
    }
    card.querySelectorAll(".ptdx .ptdhead").forEach(function (h) { h.remove(); });
    dressFaces(card);
  }

  /* the play mark belongs beside the kickoff time, not in the card's bottom
     corner: it is built at the end of the card, so it is seated here once the
     node exists (Jose, Sep 17, 2026) */
  function seatWatch(card) {
    /* the seat may already be built: a card is kept between renders now, so
       the clock is inside it the second time round and looking for a clock
       that is a direct child of the head found nothing, which left the eye
       down in the corner instead of on the row */
    /* the clock's seat, wherever the card keeps it: the fixture card carries
       it in the strip between the two passers now (Sep 21, 2026) */
    var seat = card.querySelector(".gwhen");
    var when = seat ? seat.querySelector(":scope > .gtime") : card.querySelector(".gtime");
    var mark = card.querySelector(":scope > .gwatch");
    if (!when) return;
    if (!seat) {
      seat = document.createElement("span");
      seat.className = "gwhen";
      when.parentNode.insertBefore(seat, when);
      seat.appendChild(when);
    }
    /* the eye on the left of the time, the play mark on the right, the three
       of them on one line (Jose, Sep 18, 2026) */
    var eye = card.querySelector(".ghide");
    if (eye) seat.insertBefore(eye, when);
    if (mark) seat.appendChild(mark);
  }

  /* whether a card has nothing left to say */
  /* which ids have actually finished, however we came to know it */
  /* What has finished is remembered on the device, not for the session. The
     order is worked out from this before any card is drawn, so a fresh tab
     that had forgotten everything would hand him plain clock order and then
     move it once the results came in -- the jump he is not supposed to see
     (Jose, Sep 20, 2026: "it should not need to load"). An id is one game
     for ever, so remembering it is over can never be wrong later. */
  var OVER = {};
  try { OVER = JSON.parse(localStorage.getItem("arena.over") || "{}") || {}; } catch (e) { OVER = {}; }
  function markOver(id) {
    if (!id || OVER[id]) return;
    OVER[id] = 1;
    try { localStorage.setItem("arena.over", JSON.stringify(OVER)); } catch (e) {}
    /* A card settles after the board has already been drawn, so a hidden one
       that has just finished would sit in the shelf until something else
       caused a render. It asks for one -- once he has left the board alone,
       so nothing moves under him (Jose, Sep 20, 2026: "hidden things get
       added later, fall back into order"). */
    if (hid && hid[id]) {
      clearTimeout(window._freeWait);
      window._freeWait = setTimeout(function again() {
        if (!document.hidden && Date.now() - LASTTOUCH < 12000) {
          clearTimeout(window._freeWait);
          window._freeWait = setTimeout(again, 6000);
          return;
        }
        var at = window.scrollY;
        if (typeof render === "function") render();
        window.scrollTo(0, at);
      }, 1500);
    }
  }
  window.markOver = markOver;
  function isOver(card) {
    return !!card && (card.classList.contains("done") ||
                      card.dataset.settled === "1" ||
                      card.dataset.settledBout === "1");
  }
  window.isOver = isOver;
  /* and the eye comes off the moment it is */
  function dropHide(card) {
    var b = card && card.querySelector(".ghide");
    if (b) b.parentNode.removeChild(b);
  }
  window.dropHide = dropHide;
  /* The eye, the LIVE mark and the play button are one row, on every card,
     on the board and inside the shelf alike, and they stay there for as long
     as the thing can still change. When it is final all three go and the card
     is just a result. Three places used to seat the eye and each one only
     handled the card it knew about, so a card that went live while folded
     away came back without it (Jose, Sep 20, 2026: "the eye icon still needs
     to be on the hidden ones... eye, live, play button until final. That's
     standard across all pages"). This is the one rule; everything calls it. */
  /* There is no eye any more -- the corner swipe is the eye (Sep 23, 2026)
     -- but this is still what seats the play mark and builds the top row a
     bout card lifts into its capsule. It stopped at "no eye" and the bout
     card lost its whole top row (Jose, Sep 23, 2026: "check out MMA, look
     what you did to the card"). The eye is optional here now. */
  function seatEye(card) {
    if (!card) return;
    if (isOver(card)) { dropHide(card); return; }
    var eye = card.querySelector(".ghide");
    var own = card.querySelector(".htrack");
    if (eye && own) { if (eye.parentNode !== own) own.appendChild(eye); return; }
    /* a live card has a bar of its own -- football builds one inside the
       clock, a bout turns the clock itself into one -- and the play mark
       rides it */
    var bar = card.querySelector(".glivebar") ||
              card.querySelector(".gtime--live");
    if (bar) {
      if (eye && eye.parentNode !== bar) bar.insertBefore(eye, bar.firstChild);
      var wat = card.querySelector(".gwatch");
      if (wat && wat.parentNode !== bar) bar.appendChild(wat);
      return;
    }
    seatWatch(card);
  }
  window.seatEye = seatEye;
  /* the same monoline the home and away marks are drawn in -- an outline, in
     its own colour, rather than a solid shape (Jose, Sep 22, 2026, picking the
     middle of three) */
  var TREND_SVG =
    '<svg viewBox="0 0 32 32" width="26" height="26" aria-hidden="true" ' +
    'fill="none" stroke="#76CE4F" stroke-width="1.9" stroke-linejoin="miter">' +
    '<path d="M3 23 L11 14 L17 20 L25 11"/>' +
    '<path d="M19 6.6 H27.4 V15 Z"/></svg>';

  /* the mark that opens the sheet, in the top row. It took the chevron's job
     so the chevron's seat at the foot could become the eye's track
     (Jose, Sep 22, 2026). The bouts are not touched. */
  function seatTrend(card) {
    if (!card) return;
    var top = card.querySelector(".gtop");
    if (!top || top.querySelector(".gtrend")) return;
    var b = document.createElement("button");
    b.className = "gtrend";
    b.type = "button";
    b.setAttribute("aria-label", "Matchup");
    b.innerHTML = TREND_SVG;
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      var more = card.querySelector(".gmorebtn");
      if (more) more.click();
    });
    /* the trend always sits last, so it is in the same place whatever else is
       in the row: play + trend before, play + LIVE + trend during, rewind +
       trend after (Jose, Sep 22, 2026: "make sure that the trend is always in
       the same spot") */
    top.appendChild(b);
  }
  /* the ticket, beside the trend: it opens the game's own page, the two
     clubs and the two passers with every price and the case for each
     (Jose, Sep 30, 2026: "when I click that it opens this for the specific
     game and has the odds there") */
  /* a pregame thing, and the NFL's alone for now: none on a college card,
     and gone from a card once its game kicks off (Jose, Sep 30, 2026: "it
     should disappear once a game's live and final ... only be on NFL") */
  function ticketDue(card) {
    return card.dataset.lg === "nfl" && !!card.dataset.kick && Date.now() < Date.parse(card.dataset.kick);
  }
  setInterval(function () {
    document.querySelectorAll(".gtix").forEach(function (t) {
      var c = t.closest(".gcard");
      if (!c || !ticketDue(c)) t.remove();
    });
  }, 60000);
  function seatTicket(card) {
    if (!card || card.dataset.bout || !ticketDue(card)) return;
    var top = card.querySelector(".gtop");
    if (!top || top.querySelector(".gtix")) return;
    var b = document.createElement("button");
    b.className = "gtix";
    b.type = "button";
    b.setAttribute("aria-label", "The game");
    b.innerHTML = '<img src="ico/ticket.svg" alt="">';
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      if (typeof gamePage === "function") gamePage(card);
    });
    var t = top.querySelector(".gtrend");
    if (t) top.insertBefore(b, t); else top.appendChild(b);
  }
  window.seatTicket = seatTicket;
  /* the rewind and the live badge are built after the first paint, so the
     trend is sent to the back again once they exist */
  function orderTop(card) {
    var top = card && card.querySelector(".gtop");
    if (!top) return;
    var b = top.querySelector(".gtrend");
    if (!b) return;
    /* while it is on, the LIVE badge stands in the row immediately to the
       trend's left -- play, LIVE, trend -- rather than under the score where
       it was built (Jose, Sep 22, 2026: "for MMA and live, add a live icon
       next to the left side of the trend"). It is the same badge moved, not a
       second one, so nothing has to keep two in step. */
    /* and nothing that is over wears it, wherever it got to */
    if (card.classList.contains("done") || card.dataset.settledBout === "1" ||
        card.dataset.settled === "1") {
      card.querySelectorAll(".glive").forEach(function (x) { x.remove(); });
    }
    /* one badge only: every live refresh builds a new one under the clock,
       and the one already lifted into the top row was left there, so a game
       wore two (Jose, Sep 25, 2026: "why am I getting two live icons") */
    var all = [].slice.call(card.querySelectorAll(".glive"));
    var fresh = all.filter(function (x) { return x.parentNode !== top; })[0];
    all.forEach(function (x) { if (x.parentNode === top && fresh) x.remove(); });
    all.filter(function (x) { return x.parentNode === top; }).slice(1).forEach(function (x) { x.remove(); });
    var lit = fresh || card.querySelector(".glive");
    if (lit && lit.parentNode !== top) {
      lit.style.margin = "0";
      top.insertBefore(lit, b);
    }
    if (b !== top.lastElementChild) top.appendChild(b);
    /* the play mark first, LIVE in the middle, the trend last
       (Jose, Sep 25, 2026: "play button then live then trend") */
    var pbar = top.querySelector(":scope > .glivebar");
    var badge = top.querySelector(":scope > .glive");
    if (pbar && badge && pbar.nextElementSibling !== badge) top.insertBefore(pbar, badge);
  }
  window.orderTop = orderTop;

  /* The eye sits in the middle of a track at the foot and is dragged to the
     right corner to hide the card; on the hidden shelf the same drag brings it
     back. A tap still works, because a thumb that means to press should not
     have to swipe. Only a card that can still change has one at all -- a
     finished game is not something to decide about (Jose, Sep 19, 2026). */
  function seatTrack(card) {
    if (!card) return;
    var id = idOf(card);
    /* the class as well as isOver(), and before anything else: a card that
       settled while it was on screen keeps its track otherwise, and an empty
       track under a finished game looks like something failed to draw */
    if (!id || isOver(card) || card.classList.contains("done") ||
        card.dataset.settled === "1") {
      var gone = card.querySelector(".htrack");
      if (gone) gone.remove();
      return;
    }
    wireCorner(card, id);
    /* the corner is the eye now, on every card that can still be hidden;
       the button and its track are not built (Jose, Sep 23, 2026: "we can
       remove the eye button since we have this") */
    var oldTrack = card.querySelector(".htrack");
    if (oldTrack) oldTrack.remove();
    var oldEye = card.querySelector(".ghide");
    if (oldEye) oldEye.remove();
    return;
    var more = card.querySelector(".gmorebtn");
    if (!more) return;
    var track = card.querySelector(".htrack");
    if (!track) {
      track = document.createElement("div");
      track.className = "htrack";
      /* at the end, never straight after the chevron: the sheet is the
         chevron's next sibling and that is how the opener finds it, so a track
         put in between made the trend open a div instead of the dialog
         (Jose, Sep 22, 2026: "the trend button doesn't open the modal") */
      more.parentNode.appendChild(track);
    }
    var eye = card.querySelector(".ghide");
    if (!eye) { armHide(card); eye = card.querySelector(".ghide"); }
    if (!eye) return;
    if (eye.parentNode !== track) track.appendChild(eye);
    if (eye.dataset.dragged === "1") return;
    eye.dataset.dragged = "1";

    var from = 0, wide = 0, at = 0, live = false;
    /* how far it has to go: the eye starts at the left end, so the reach is
       the whole track less its own width and the padding either end */
    function reach() { return track.clientWidth - 46; }
    eye.addEventListener("pointerdown", function (e) {
      if (e.button) return;
      e.stopPropagation();
      live = true; at = 0; from = e.clientX; wide = reach();
      track.classList.add("htrack--pulling");
      eye.setPointerCapture(e.pointerId);
    });
    eye.addEventListener("pointermove", function (e) {
      if (!live) return;
      e.stopPropagation();
      at = Math.max(0, Math.min(wide, e.clientX - from));
      eye.style.transform = "translateX(" + at + "px)";
      track.classList.toggle("htrack--armed", at >= wide - 4);
      if (at > 3) e.preventDefault();
    });
    function letGo(e) {
      if (!live) return;
      live = false;
      track.classList.remove("htrack--pulling", "htrack--armed");
      eye.style.transform = "";
      try { eye.releasePointerCapture(e.pointerId); } catch (err) {}
      if (at < wide - 4) return;            /* short of the end: nothing happened */
      if (hid[id]) { delete hid[id]; } else { hid[id] = 1; }
      saveHidden();
      render();
    }
    eye.addEventListener("pointerup", letGo);
    eye.addEventListener("pointercancel", letGo);
  }

  /* the corner swipe. Progress is the finger's travel projected onto the
     diagonal, so an off-line swipe still counts for as far as it went that
     way; ARM is how far along the diagonal it has to reach. */
  var CORNER_ARM = 56;
  function wireCorner(card, id) {
    var zone = card.querySelector(":scope > .gcorner");
    if (!zone) {
      zone = document.createElement("div");
      zone.className = "gcorner";
      zone.innerHTML = "<i></i>";
      card.appendChild(zone);
    }
    if (zone.dataset.wired === "1") return;
    zone.dataset.wired = "1";
    var wedge = zone.firstElementChild;
    var x0 = 0, y0 = 0, p = 0, live = false;
    zone.addEventListener("pointerdown", function (e) {
      if (e.button) return;
      e.stopPropagation();                   /* not the board's day swipe */
      live = true; p = 0; x0 = e.clientX; y0 = e.clientY;
      zone.classList.add("gcorner--pulling");
      try { zone.setPointerCapture(e.pointerId); } catch (err) {}
    });
    zone.addEventListener("pointermove", function (e) {
      if (!live) return;
      e.stopPropagation();
      var dx = e.clientX - x0, dy = e.clientY - y0;
      /* toward the corner, to hide and to bring back alike -- the same pull
         on the shelf undoes it (Jose, Sep 23, 2026: "no, just towards") */
      var along = (dx + dy) / Math.SQRT2;
      p = Math.max(0, Math.min(1, along / CORNER_ARM));
      /* nothing drawn: the card itself dims as the finger comes, and is at
         its dimmest where letting go hides it (Jose, Sep 23, 2026: "make it
         invisible and the card turns dim, that's the indicator") */
      /* a hidden card rests dim on the shelf, and the reverse brings it up to
         full as the finger comes: let go bright and it is back
         (Jose, Sep 23, 2026: "the hidden is dimmer... it goes from dimmed to
         regular for the reverse") */
      card.style.opacity = !p ? "" : (hid[id] ? 0.4 + 0.6 * p : 1 - 0.6 * p).toFixed(3);
      zone.classList.toggle("gcorner--armed", p >= 1);
      if (p > 0.05 && e.cancelable) e.preventDefault();
    });
    function letGo(e) {
      if (!live) return;
      live = false;
      var armed = p >= 1;
      zone.classList.remove("gcorner--pulling", "gcorner--armed");
      card.style.opacity = "";
      try { zone.releasePointerCapture(e.pointerId); } catch (err) {}
      /* a tap, not a swipe: it was meant for what lies under the corner --
         the head to head's right price sits in it, and could not be pressed
         (Jose, Sep 24, 2026: "why can't I click it?") */
      if (e.type === "pointerup" && Math.abs(e.clientX - x0) < 10 && Math.abs(e.clientY - y0) < 10) {
        zone.style.pointerEvents = "none";
        var under = document.elementFromPoint(e.clientX, e.clientY);
        zone.style.pointerEvents = "";
        if (under && under !== zone) {
          var hit = under.closest("button, a, [role=button]") || under;
          if (typeof hit.click === "function") hit.click();
        }
        return;
      }
      if (!armed) return;                    /* short of red: nothing happened */
      flipHide(card, id);
    }
    zone.addEventListener("pointerup", letGo);
    zone.addEventListener("pointercancel", letGo);
  }

  /* Hiding touches the one card: it leaves its row for the shelf and the
     rest of the board stays exactly where it is. Redrawing the whole board
     for it made the page jump under him (Jose, Sep 28, 2026: "it's rebuilding
     it every time I hide something"). Bringing one back, or the first hide
     of the day when there is no shelf yet, still needs the board drawn --
     and then whatever he was looking at is put back on the same spot. */
  function flipHide(card, id) {
    var hiding = !(hid[id] || card.closest(".hidebox"));
    if (hiding) hid[id] = 1; else delete hid[id];
    if (card.dataset.lg === "college-football" && cfbStarred()) {
      cfbStar(id, !hiding);
      if (!hiding) { var y0 = window.scrollY; saveHidden(); render(); window.scrollTo(0, y0); return; }
    }
    saveHidden();
    var box = BOARD.querySelector(".hidebox"), label = BOARD.querySelector(".hidebar span");
    var row = card.closest(".caro, .bill"), slot = card.closest(".board");
    if (hiding && box && label && row && slot && !card.closest(".hidebox")) {
      card.style.opacity = "";
      box.appendChild(card);
      if (!row.querySelector(".gcard")) slot.remove();
      var n = parseInt(String(label.textContent).replace(/\D+/g, ""), 10) || 0;
      label.textContent = "Hidden \u00B7 " + (n + 1);
      return;
    }
    var ref = null, top = 0;
    [].some.call(BOARD.querySelectorAll(".gcard"), function (c) {
      if (c === card || c.closest(".hidebox")) return false;
      var r = c.getBoundingClientRect();
      if (!r.height || r.top < 0) return false;
      ref = c; top = r.top; return true;
    });
    var y = window.scrollY;
    render();
    if (ref && ref.isConnected && ref.getBoundingClientRect().height) window.scrollBy(0, ref.getBoundingClientRect().top - top);
    else window.scrollTo(0, y);
  }

  function armHide(card) {
    /* the eye rides in the head beside the time now, so it is no longer a
       child of the card -- looked for anywhere (Jose, Sep 18, 2026) */
    var old = card.querySelector(".ghide");
    if (old) old.remove();
    var id = idOf(card);
    if (!id) return;
    /* the eye stays on a card for as long as the card can still change: not
       to come, kicked off, being played. It goes when the thing is over,
       because a finished game is not something to decide about any more
       (Jose, Sep 19, 2026: "the hidden should always be an icon on the card,
       live or pregame, so before the end of the day I can swap them between
       lists -- no final card will have an eye icon"). */
    if (isOver(card)) return;
    return;                                  /* the corner swipe took the eye's job (Sep 23, 2026) */
    var b = hideBtn(!!hid[id]);
    b.addEventListener("click", function (e) {
      e.stopPropagation();
      if (hid[id]) { delete hid[id]; } else { hid[id] = 1; }
      saveHidden();
      render();
    });
    card.appendChild(b);
  }

  /* A row is rebuilt from scratch whenever anything changes, which used to
     throw away how far along it had been swiped -- hide the third card and
     the row snapped back to the first. The offsets are kept by the row's own
     heading and put back once the new row is standing. */
  var scrolled = {};
  function rowKey(row) {
    var board = row.parentElement;
    var head = board && board.querySelector(".slot-h");
    var day = board && board.previousElementSibling;
    return ((day && day.classList.contains("dayhead") ? day.textContent : "") +
            "|" + (head ? head.textContent : ""));
  }
  /* a row says when it is being swiped. A scroll on an element does not
     bubble and the capture listener on the document proved unreliable here,
     so each row is asked directly as it is built (Jose, Sep 19, 2026) */
  function watchRow(row) {
    if (!row || row.dataset.watched) return;
    row.dataset.watched = "1";
    row.addEventListener("scroll", function () { LASTTOUCH = Date.now(); }, {passive: true});
  }
  function rememberScroll() {
    BOARD.querySelectorAll(".caro").forEach(function (row) {
      /* every position, nought as well. Only a row swiped away from its first
         card used to be written down, so swiping back to the first left the
         old place on file and the next rebuild put him there: he was watching
         Georgia and the row handed him Carolina, three cards along
         (Jose, Sep 19, 2026) */
      if (row.clientWidth) scrolled[rowKey(row)] = row.scrollLeft;
    });
  }
  function restoreScroll() {
    BOARD.querySelectorAll(".caro").forEach(function (row) {
      watchRow(row);
      var was = scrolled[rowKey(row)];
      if (was !== undefined) row.scrollLeft = was;
    });
  }
  function clearBoard() {
    document.documentElement.classList.remove("clipsview");
    rememberScroll();
    BOARD.querySelectorAll(".gcard").forEach(function (c) {
      if (c.dataset.pooled) POOL.appendChild(c);
    });
    BOARD.innerHTML = "";
  }

  function lockOne(card) {
    if (!card.dataset.kick || Date.now() < Date.parse(card.dataset.kick)) return;
    card.classList.add("locked");
    card.querySelectorAll("button.price").forEach(function (b) {
      shutPrice(b);
      b.classList.remove("on");
    });
  }

  /* Every card the page draws is kept and handed back next time it is asked
     for. It used to be drawn fresh from its own HTML on every render, which
     threw away everything the settler had written -- the score, the FINAL,
     the class that says it is over -- so after each tab change the board knew
     nothing until the reads came back, and the order could not be right until
     they did (Jose, Sep 20, 2026: "it needs to be instant... if it has a
     FINAL badge it should not be above a live"). */
  var MADE = {};
  function nodeFor(id, html) {
    if (STATIC[id]) return STATIC[id];
    if (MADE[id]) return MADE[id];
    var box = document.createElement("div");
    box.innerHTML = html;
    var card = box.firstElementChild;
    MADE[id] = card;
    card.dataset.pooled = "1";
    card.querySelectorAll(".gmorebtn").forEach(function (b) {
      b.addEventListener("click", function () {
        var sheet = b._sheet || (b._sheet = b.nextElementSibling && b.nextElementSibling.tagName === "DIALOG" ? b.nextElementSibling : null) || b.nextElementSibling;
        /* whose sheet this is, taken off the card it hangs on */
        var own = cardOf(b);
        if (own && own.dataset.bout) {
          FS_BOUT = own.dataset.bout;
          /* The rows are written once, when the card is built, so a price
             landing after that never reaches them: the numbers in memory were
             right while the panel still showed what it was made with. They are
             written again on every open, off whatever the page holds now.
             And where the card was re-ordered to the promotion's own naming,
             the two columns and the prices under them follow it
             (Jose, Sep 22, 2026: "are you changing it in the modal?"). */
          var row = null;
          for (var i = 0; i < FIGHTS.length; i++) {
            if (String(FIGHTS[i][1]) === own.dataset.bout) { row = FIGHTS[i]; break; }
          }
          FS_FLIP = own.dataset.flip === "1";
          if (row && FS_FLIP) {
            row = row.slice();
            var sw = function (a, bi) { var t = row[a]; row[a] = row[bi]; row[bi] = t; };
            sw(3, 5); sw(4, 6); sw(8, 10); sw(9, 11); sw(12, 13);
          }
          var scroll = sheet && sheet.querySelector(".sheet__scroll");
          if (row && scroll) {
            var hits = scroll.querySelector(".hits");
            scroll.innerHTML = "";
            if (hits) scroll.appendChild(hits);
            scroll.insertAdjacentHTML("beforeend", fightSheet(row));
            if (typeof markSaved === "function") markSaved(scroll);
            if (typeof seatSheetWant === "function") seatSheetWant(scroll, own);
            if (own._paid && typeof paidMethods === "function") {
              paidMethods(own, own._paid[0], own._paid[1], own._paid[2], own._paid[3]);
            }
          }
        }
        if (sheet && sheet.tagName === "DIALOG") openSheet(sheet);
      });
    });
    return card;
  }

  /* ---- building a view ----
     An item is [league, id, kickoff, how to draw it if we have no card].
     They are grouped league, then day, then kickoff. */
  function head(cls, html) {
    var h = document.createElement("div");
    h.className = cls;
    h.innerHTML = html;
    return h;
  }

  var LEAGUE_MARK = {
    "nfl": '<img src="ico/nfl-shield.png" alt=""> NFL',
    "college-football": '<img src="ico/cfp-new.png" alt=""> CFB',
    "mma": '<img src="ico/octagon-2.svg" alt=""> UFC'
  };

  function build(all, showLeague) {
    clearBoard();
    var drawn = 0, later = [], slotN = 0;
    /* a folded card is off screen, so the watcher below never fires for it and
       its fights are never built. Opening one builds them then and there
       (Jose, Sep 18, 2026) */
    var flush = function (row) {
      /* a pair already built is skipped, and marked before it is built rather
         than after: three paths build these -- opening a row, scrolling one
         into view, and the idle pass that fills folded bills -- and each one
         made a fresh card, so the same bout was drawn twice in one row
         (Jose, Sep 19, 2026, two Menifield cards under one 9:15 PM) */
      later.filter(function (pair) { return pair[0] === row && !pair[2]; })
           .forEach(function (pair) { pair[2] = 1; pair[1](); });
      later = later.filter(function (pair) { return !pair[2]; });
    };
    var items = [], away = [], now = Date.now();
    /* A game you put away stays away while it is on: it was hidden because it
       is a blowout or a card you are not following, and having it walk back
       onto the board at kickoff is the opposite of what the eye is for. The
       whole day's marks are cleared at once, when the last game and the last
       bout are finished -- not at midnight, because a late kick and a main
       event are still running then. Football is done four hours after
       kickoff, a fight card eight hours after the first bell, which is the
       reach the fight refresh already uses (Jose, Sep 19, 2026). */
    /* Eight hours was the reach of a whole fight card, from the first bell.
       Every item here is one bout with its own start time, though, so it was
       holding a bout that finished at nine o'clock at the top of the day
       until five in the morning. A bout is twenty-five minutes at the most;
       two hours covers a delayed one and nothing longer. */
    var reach = function (it) { return it[0] === "mma" ? 2 * 3600000 : 4 * 3600000; };
    /* A thing is over when it says it is over. The clock was the only test,
       so six fights that had all finished sat in the shelf waiting out eight
       hours from the first bell (Jose, Sep 20, 2026: "why are these still in
       hidden, the others are over"). The cards mark themselves done as they
       settle, and OVER remembers which -- the clock is only the fallback for
       something we have never had a card for. */
    /* Over, in order of what we actually know: the card itself if we have
       drawn one, then what has finished on this device, then the clock. The
       card is read first because it is the thing he is looking at -- a row of
       FINAL badges can never sit above a live one again. */
    var finished = function (it) {
      var card = STATIC[it[1]] || MADE[it[1]];
      if (card) return card.classList.contains("done");
      if (OVER[String(it[1])]) return true;
      var off = Date.parse(it[2]);
      return !!off && now >= off + reach(it);
    };
    /* every bill already given a row this render, so a bout that sorted away
       from its brothers joins the row it belongs to rather than starting a
       second one with the same name */
    var BILLS = {};
    var dayOver = all.length > 0 && all.every(finished);
    all.forEach(function (it) {
      /* A card that has finished comes back out and takes its place in the
         order, on its own. Waiting for the whole list to be over never fired
         on the UFC tab, where the list is a month and there are always fights
         still to come (Jose, Sep 20, 2026: "they get placed back in the order
         of events"). */
      var put = (hid[it[1]] || cfbOff(it)) && !OVER[String(it[1])] && !dayOver;
      if (hid[it[1]] && !put) { delete hid[it[1]]; saveHidden(); }
      (put ? away : items).push(it);
    });
    /* the day runs in clock order across the leagues; the league mark is
       written wherever the league changes (Jose, Sep 16, 2026: "why is 7:30
       after 8:15") */
    /* on the UFC tab a card is one block at its first bell. On the day page
       every bout takes its own line at its own clock, among the kickoffs,
       the way a game does (Jose, Sep 18, 2026: "on the day page we don't
       need the UFC all in the same drop down") */
    var firstBell = {};
    items.forEach(function (it) {
      if (it[0] !== "mma") return;
      var k = it[4] || "Fight card", t = Date.parse(it[2]);
      if (!firstBell[k] || t < firstBell[k]) firstBell[k] = t;
    });
    var when = function (it) {
      return it[0] === "mma" && !showLeague ? firstBell[it[4] || "Fight card"] : Date.parse(it[2]);
    };
    /* ---- the order ----
       Whatever is still to come or on now leads, in clock order. Whatever is
       over follows, in clock order behind it. So the one being played sits at
       the top, and the moment it is over the next one takes its place and it
       goes to the back -- and when the last of them is over the two groups
       are one group and the list reads straight through by time.

       This is worked out from the list, here, before a single card is drawn.
       It used to be worked out from the cards after they had loaded, so the
       board he was handed was in plain clock order and then jumped under him
       (Jose, Sep 20, 2026: "it should not need to load... I see it jump from
       the original first event to the 5th"). The same rule runs on every
       tab and over both lists -- the day, the NFL week, the college week,
       the fight card, and the shelf under each. */
    var byOrder = function (a, b) {
      var fa = finished(a) ? 1 : 0, fb = finished(b) ? 1 : 0;
      if (fa !== fb) return fa - fb;
      var d = when(a) - when(b);
      if (d) return d;
      if (a[0] === "mma" && b[0] === "mma") {
        d = Date.parse(a[2]) - Date.parse(b[2]);
        if (d) return d;
      }
      var o = ["nfl", "college-football", "mma"];
      return o.indexOf(a[0]) - o.indexOf(b[0]);
    };
    items.sort(byOrder);
    var lg = "", dy = "", tm = "", fy = null, row = null;
    /* a fight card is dated by its first bell: the bouts after midnight
       Eastern split UFC 332 into a 10/3 row and a 10/4 row (Jose, Sep 28, 2026) */
    var dateOf = function (it) {
      var at = it[0] === "mma" && !showLeague && firstBell[it[4] || "Fight card"]
        ? new Date(firstBell[it[4] || "Fight card"]).toISOString() : it[2];
      return etParts(at);
    };
    items.forEach(function (it) {
      var p = etParts(it[2]), pd = dateOf(it), key = pd.day + " " + pd.date;
      /* the league rides the clock now -- "CFB 7:30 PM" on one line, on every
         slot, rather than a heading of its own above them (Jose, Sep 17, 2026) */
      if (showLeague && it[0] !== lg) {
        lg = it[0]; dy = ""; tm = ""; fy = null; row = null;
      }
      /* no date heading: the rail names the day, and one under each league
         read as a repeat (Jose, Sep 16, 2026) */
      if (key !== dy) {
        dy = key; tm = ""; fy = null; row = null;
      }
      /* A fight card is one bill, in fight order -- it gets the event's name
         and no clock rows, because every fight already carries its own. */
      var slot = it[0] === "mma" && !showLeague ? (it[4] || "Fight card") : p.time;
      /* the same kickoff can stand in both groups -- one game of the 3:30s
         over, another still on -- so the row is keyed by the group as well as
         the clock, and the two never merge */
      var fin = finished(it);
      /* A bill is one row whatever state its bouts are in. Keying on finished
         as well as the clock is right for football -- one of the 3:30s over,
         another still on -- but it cut a fight card in two: the board showed
         DWCS S10 Wk 7 twice, once with the fights to come and once saying
         FINAL, with three still to happen (Jose, Sep 22, 2026: "it needs to be
         within its own drop-down"). The bill's own row says FINAL only when
         every bout on it is done, which the rule further down already works
         out, and a finished bout goes to the back of the row it is in. */
      var bill = it[0] === "mma" && !showLeague;
      /* A bill already built is reused, wherever its remaining bouts have
         sorted to. A finished bout goes to the back of the order on its own,
         which put it well away from its brothers -- so the builder, which only
         starts a row when the name changes, met the name again at the foot and
         made a second DWCS S10 Wk 7 (Jose, Sep 22, 2026: "I shouldn't have two
         of the same events"). */
      if (bill) {
        var seen = BILLS[key + "|" + slot];
        if (seen) { row = seen; tm = slot; fy = fin; }
      }
      if ((!bill || !BILLS[key + "|" + slot]) && (slot !== tm || (!bill && fin !== fy))) {
        tm = slot; fy = fin;
        var n = items.filter(function (x) {
          var q = etParts(x[2]), qd = dateOf(x);
          return x[0] === it[0] && qd.day + " " + qd.date === key &&
                 (x[0] === "mma" && !showLeague ? (x[4] || "Fight card") : q.time) === slot;
        }).length;
        var board = document.createElement("div");
        board.className = "board board--nfl" + (fin && !bill ? " done" : "");
        board.dataset.ord = String(slotN++);
        board.dataset.kick = it[2] || "";
        board.dataset.lg = it[0];
        var isCard = it[0] === "mma";
        /* how long after its clock this row cannot still be running. One bout
           on the day page is its own row, so it is the bout's two hours; a
           whole bill on the UFC tab is one row at its first bell, so it is
           the card's eight. Written here because this is the only place that
           knows which of the two it is -- worked out again further down, it
           was got wrong, and the second guess turned off the marks the first
           had just put on. */
        board.dataset.far = String(isCard && !showLeague ? 8 * 3600000 : reach(it));
        /* on the day page a fight card's line is the game's line -- icon,
           UFC, day, clock -- and the bill opens open (Jose, Sep 18, 2026:
           "icon UFC SAT 9/19 then time"). On the UFC tab it is what it was:
           the mark alone, day, date, the bill's name, folded until opened. */
        var onDay = showLeague;
        var mk = LEAGUE_MARK[it[0]] || "";
        /* a Zuffa card is boxing, not the UFC: the glove and BOXING
           (Jose, Sep 26, 2026) */
        if (isCard && /^zb-/.test(String(it[1] || ""))) mk = '<img src="ico/boxing-b365.svg" alt=""> BOXING';
        /* on the UFC tab the tab itself says which sport it is, so the row
           carries no mark at all (Jose, Sep 19, 2026) */
        if (isCard && !onDay) mk = "";
        var line = (mk ? '<span class="slotlg">' + mk + "</span>" : "") +
          (isCard && !onDay
            /* the date alone: a month of evenings does not need the
               weekday said twice (Jose, Sep 19, 2026) */
            ? '<span class="slotdate">' + pd.date + '</span>' +
              '<span class="slotev">' + slot + '</span>'
            : '<span class="slotday">' + p.day.toUpperCase() + " " + p.date + "</span>" +
              (isCard ? p.time : slot)) +
          /* every row can say FINAL, not only a fight card's. It shows only
             on a row that is over -- the rule is on .board.done -- and it is
             what tells a seated row apart from the one it came from */
          '<span class="slotfin">FINAL</span>' +
          "" +
          (isCard && !onDay
            ? '<svg class="slotmore" viewBox="0 0 24 24" aria-hidden="true">' +
              '<polygon points="4,9 12,17 20,9" fill="currentColor"/></svg>' : "");
        var h = head("slot-h" + (isCard ? " slot-h--card" + (onDay ? "" : " slot-h--bill") : ""), line);
        if (isCard && !onDay) {
          h.setAttribute("role", "button");
          h.setAttribute("tabindex", "0");
          h.addEventListener("click", function () {
            var open = board.classList.toggle("open");
            h.setAttribute("aria-expanded", open ? "true" : "false");
            if (open) flush(board.querySelector(".bill"));
          });
          h.setAttribute("aria-expanded", "false");
        }
        board.appendChild(h);
        row = document.createElement("div");
        row.className = isCard ? "bill" : "caro";
        board.appendChild(row);
        BOARD.appendChild(board);
        if (bill) BILLS[key + "|" + slot] = row;
      }
      /* A college Saturday is ninety-odd games. Building them all before the
         first one is on screen costs about a second, so only the rows near the
         viewport are built and the rest fill in as they come into view. */
      var slotRow = row;
      var make = function () {
        var card = nodeFor(it[1], it[3]);
        paintSides(card);
        card.hidden = false;
        lockOne(card);
        armHide(card);
        seatEye(card);
        fightRec(card);
        nameUnder(card);
        cfbOnce(card);
        slotRow.appendChild(card);
        /* a card built late used to wait for the next 30-second tick before it
           read its result; it reads it the moment it is on the page */
        if (card.dataset.espn && typeof refresh === "function") refresh(card);
        if (card.dataset.bout) { clearTimeout(window._fightTick); window._fightTick = setTimeout(refreshFights, 150); }
      };
      if (drawn < 10) { drawn++; make(); } else { later.push([slotRow, make]); }
    });
    /* A folded bill is put away, not struck off -- the same rule as a hidden
       game. Its bouts were built only when he tapped the row open, so on the
       UFC tab a whole card carried no records, no results and no method: there
       was nothing on the page for the refresh to write into
       (Jose, Sep 19, 2026: "why aren't the UFC fighters updating on the UFC
       tab?"). They are built on the browser's idle moments now, one at a time,
       and the row stays folded until he opens it. */
    (function fillBills() {
      var idle = function (fn) {
        if (window.requestIdleCallback) window.requestIdleCallback(fn, {timeout: 400});
        else window.setTimeout(fn, 24);
      };
      var step = function () {
        var pair = null;
        for (var i = 0; i < later.length; i++) {
          if (later[i][0] && later[i][0].classList &&
              later[i][0].classList.contains("bill") && !later[i][2]) { pair = later[i]; break; }
        }
        if (!pair) return;
        pair[2] = 1;
        pair[1]();
        idle(step);
      };
      idle(step);
    }());
    /* the results land a moment after the cards, so the first sink waits for
       them rather than running on a board that is still all unsettled */
    sinkDone(true);
    setTimeout(function () { sinkDone(true); }, 2500);
    if (later.length) {
      var watch = new IntersectionObserver(function (es) {
        es.forEach(function (e) {
          if (!e.isIntersecting) return;
          watch.unobserve(e.target);
          later.forEach(function (pair) {
            if (pair[0] !== e.target || pair[2]) return;
            pair[2] = 1;
            pair[1]();
          });
          /* a row filled in late had its offset put back while it was still
             empty, so it clamped to nought: hide the third of four and the
             row snapped to the first. Put back once the cards stand
             (Jose, Sep 18, 2026: "it should go to 4") */
          var was = scrolled[rowKey(e.target)];
          if (was) e.target.scrollLeft = was;
        });
      }, { rootMargin: "600px 0px" });
      later.forEach(function (pair) { watch.observe(pair[0]); });
    }
    if (!items.length && !away.length) {
      BOARD.appendChild(head("wkempty", "Nothing on the board."));
    } else if (!items.length) {
      BOARD.appendChild(head("wkempty", "Everything here is hidden."));
    }
    if (away.length) putAway(away, byOrder);
    /* one sweep over whatever ended up on the board, so a hand-built
       card and one the page drew itself get the same treatment */
    BOARD.querySelectorAll(".gcard").forEach(paintSides);
    if (window.markSaved) markSaved(BOARD);
    restoreScroll();
    refreshVisible();
  }

  /* the dashed line, the count, and the cards folded behind it */
  var hideOpen = false;
  function putAway(away, order) {
    away.sort(order);
    var wrap = document.createElement("div");
    wrap.className = "hidewrap";
    var rule = document.createElement("hr");
    rule.className = "hiderule";
    wrap.appendChild(rule);
    var bar = document.createElement("button");
    bar.type = "button";
    bar.className = "hidebar" + (hideOpen ? " open" : "");
    bar.innerHTML = '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true">' +
      '<polygon points="4,9 12,17 20,9" fill="var(--amber)"/></svg>' +
      "<span>Hidden \u00B7 " + away.length + "</span>";
    wrap.appendChild(bar);
    var box = document.createElement("div");
    box.className = "hidebox";
    box.hidden = !hideOpen;
    /* A hidden card used to be left unbuilt until the shelf was opened, which
       meant sixty-seven games were not on the page at all: nothing asked ESPN
       about them, they carried no score, and a placed mark on one never went
       green or red, because the settling reads counts off a card that was
       never there. Hidden means put out of sight, not struck off
       (Jose, Sep 19, 2026: "build the hidden in case I want to see it later").

       They are built now and the shelf is still shut. The building is spread
       over idle moments rather than done in the render, so opening the board
       is no slower than it was; the shelf opening before they are all done
       finishes the rest on the spot. */
    var pending = away;
    function fillBox() {
      if (!pending) return;
      pending.forEach(function (it) {
        var card = nodeFor(it[1], it[3]);
        card.hidden = false;
        paintSides(card);
        lockOne(card);
        armHide(card);
        seatEye(card);
        fightRec(card);
        nameUnder(card);
        cfbOnce(card);
        box.appendChild(card);
      });
      pending = null;
    }
    /* one card at a time, whenever the browser has nothing better to do.
       requestIdleCallback has to be called on window: handed round as a bare
       reference it throws "Illegal invocation" in Chrome, and that took the
       whole shelf down with it (Sep 19, 2026) */
    var idle = function (fn) {
      if (window.requestIdleCallback) window.requestIdleCallback(fn, {timeout: 300});
      else window.setTimeout(fn, 16);
    };
    function fillSlowly() {
      if (!pending) return;
      if (!pending.length) { pending = null; return; }
      var it = pending.shift();
      var card = nodeFor(it[1], it[3]);
      card.hidden = false;
      paintSides(card);
      lockOne(card);
      armHide(card);
      seatEye(card);
      fightRec(card);
      nameUnder(card);
      cfbOnce(card);
      box.appendChild(card);
      var k = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
      if (card.dataset.espn && (!k || k < Date.now() + 8 * 86400000) &&
          typeof refresh === "function") refresh(card);
      idle(fillSlowly);
    }
    if (hideOpen) fillBox();
    else idle(fillSlowly);
    wrap.appendChild(box);
    bar.addEventListener("click", function () {
      fillBox();
      hideOpen = !hideOpen;
      box.hidden = !hideOpen;
      bar.classList.toggle("open", hideOpen);
    });
    BOARD.appendChild(wrap);
  }

  function nflItems(list) {
    return list.map(function (g) { return ["nfl", g[1], g[2], frame(g)]; });
  }
  /* the college board is the teams he has starred (Jose, Oct 3, 2026: "if I
     star it that means I wanna see it, if I don't that means I don't"). With
     no college star at all, everything shows, so the page is never empty. */
  function cfbStarred() {
    var st = window.STARS || {};
    for (var k in st) if (k.indexOf("cfb:") === 0) return st;
    return null;
  }
  function cfbOff(it) {
    if (it[0] !== "college-football") return false;
    var st = cfbStarred();
    if (!st) return false;
    for (var i = 0; i < CFB.length; i++) {
      var g = CFB[i];
      if (String(g[1]) === String(it[1])) return !st["cfb:" + g[3]] && !st["cfb:" + g[4]];
    }
    return false;
  }
  function cfbStar(gid, on) {
    var st = window.STARS || {};
    CFB.forEach(function (g) {
      if (String(g[1]) !== String(gid)) return;
      [g[3], g[4]].forEach(function (ab) { if (on) st["cfb:" + ab] = Date.now(); else delete st["cfb:" + ab]; });
    });
    window.STARS = st;
    try { STARS = st; } catch (e) {}
    try { localStorage.setItem("arena.stars", JSON.stringify(st)); } catch (e) {}
    if (typeof pushState === "function") pushState();
  }
  function cfbItems(list) {
    return list.map(function (g) {
      return ["college-football", g[1], g[2], cfbFrame(g)];
    });
  }
  function fightItems(list) {
    var named = {};
    FIGHTCARDS.forEach(function (e) { named[e[1]] = e[3]; });
    return list.map(function (f) {
      return ["mma", f[1], f[2], fightFrame(f), evShort(named[f[0]]) || "Fight card"];
    });
  }

  /* ---- the three views ---- */
  var day = "", week = 1, cfbWeek = 1, sport = "all";

  /* The day is always what is shown. A week, where one exists, only decides
     which days the rail offers. */
  /* ---- the passers' form: a leaderboard, the season or one week ----
     Counts only, no prices: passing touchdowns as footballs, rushing ones as
     runners, then W/L tiles for the passing-yards head to head and the club.
     Ranked by touchdowns, passing over rushing, then the head to head, then
     the moneyline. Read from site/ledger.json (ledger.py, on the sweep).
     (Jose, Sep 16, 2026) */
  var LEDGER = null, formWeek = "season";
  /* ---- the wire ----
     Who is hurt, by ESPN id, from site/wire.json (build/wire.py on the sweep).
     A man ESPN says nothing about is not in the file at all -- an absence is
     an absence, not a clean bill of health, so nothing is drawn for it.
     (Jose, Sep 21, 2026: the mark goes next to the name.) */
  var WIRE = {}, WIREAT = 0;
  /* who is cold, from site/cold.json (build/qb_search.py): one TD or fewer per
     full start, with two starts at least (Jose, Sep 28, 2026) */
  var COLD = {};
  /* the name and the plaster on one line: .fname is a column, so a bare
     mark beside the text became a row of its own under it */
  /* cold is worked out from his starts, not from the gold ring: it was every
     man he had not ringed, so QBs who were not cold wore it (Jose, Sep 28, 2026) */
  function coldMark(id) {
    /* a man on the wire is hurt, not cold: the plaster says everything the
       snowflake would and two marks on one name says neither clearly
       (Jose, Sep 21, 2026: "if you're injured you don't get it") */
    if (!COLD[String(id)] || hurtAt(id)) return "";
    return '<i class="cold" title="Cold" aria-label="Cold">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#cold"/></svg></i>';
  }
  function nameMark(r) {
    var m = hurtMark(r.id) + coldMark(r.id);
    return m ? '<span class="fnmrow">' + esc(famName(r.name)) + m + '</span>'
             : esc(famName(r.name));
  }
  /* What his club's chart says about him: his rung in the room, the letter
     beside his name and whether it stops him. ESPN's own legend, which is the
     only place these letters are defined (Jose, Sep 22, 2026). */
  var DEPTH = {};
  var MARKWORD = {P: "Probable", Q: "Questionable", D: "Doubtful", O: "Out",
                  IR: "Injured reserve", PUP: "Physically unable to perform",
                  SUS: "Suspended", SUSP: "Suspended", NFI: "Non-football injury"};
  var DEPTHAT = null, DEPTHBY = null;
  function depthSays(id) {
    /* one walk of the file, not one a man: the season card asks this for every
       passer it draws */
    if (DEPTHBY !== DEPTH) {
      DEPTHBY = DEPTH; DEPTHAT = {};
      for (var club in DEPTH) {
        var qbs = (DEPTH[club] || {}).qbs || [];
        for (var i = 0; i < qbs.length; i++) {
          DEPTHAT[String(qbs[i].id)] = {
            club: club, rank: qbs[i].rank, mark: qbs[i].mark,
            go: qbs[i].go === 1
              ? (String(DEPTH[club].starter) === String(qbs[i].id) ? "starts" : "a go")
              : "not a go"};
        }
      }
    }
    return DEPTHAT[String(id)] || null;
  }
  /* The one red cross, from either source. The wire is the only place that
     says what is wrong with him and when he is due back; the chart is the only
     place that carries a letter for men the wire has never heard of -- Tua
     Tagovailoa read O on Atlanta's chart with nothing on the wire at all. So a
     mark on either draws the icon, and where both speak both are said
     (Jose, Sep 22, 2026: "if you see they are injured put the injury icon next
     to them"). */
  /* Is anything against him at all -- either source. Whatever sinks a man to
     the foot of the ledger uses this, so the wire and the chart cannot put him
     in two different places. */
  function hurtAt(id) {
    var d = depthSays(id);
    return !!(WIRE[String(id)] || (d && d.mark));
  }
  function hurtMark(id) {
    var h = WIRE[String(id)], d = depthSays(id);
    var letter = (d && d.mark) || (h && h.abbr) || "";
    if (!h && !letter) return "";
    var status = (h && h.status) || MARKWORD[letter.toUpperCase()] || letter;
    var said = [status, h && h.type,
                h && h.side && h.side !== "Not Specified" ? h.side : ""]
      .filter(Boolean).join(" · ");
    if (d) said += " — QB" + d.rank + ", " + d.go;
    /* where the chart and the wire disagree, both are shown rather than one
       quietly chosen */
    if (h && h.abbr && d && d.mark && h.abbr !== d.mark) {
      said += " (chart " + d.mark + ", wire " + h.abbr + ")";
    }
    return '<i class="hurt hurt--' + String(status).toLowerCase().replace(/[^a-z]/g, "") +
      (d && d.go === "not a go" ? " hurt--nogo" : "") +
      '" data-mark="' + esc(letter) +
      '" title="' + esc(said) + '" aria-label="' + esc(said) + '">' +
      '<svg viewBox="0 0 24 24" aria-hidden="true"><use href="#hurt"/></svg></i>';
  }
  /* Men wearing a gold ring on the ledger. Two taps on a face put it on, two
     more take it off -- the same two taps that place a price, so the board
     answers a double tap the same way wherever he makes it (Jose, Sep 20,
     2026: "allow a double click to turn it on and off"). Kept by ESPN id,
     never by the written name, since two men answer to J.Allen. */
  var RINGKEY = "arena.ring.v1";
  var RINGED = {};
  try { RINGED = JSON.parse(localStorage.getItem(RINGKEY) || "{}") || {}; } catch (e) { RINGED = {}; }
  function ringOn(id) { return RINGED[String(id)] ? " qbface--ring" : ""; }
  function toggleRing(id) {
    id = String(id);
    var on = !RINGED[id];
    if (on) RINGED[id] = 1; else delete RINGED[id];
    /* every copy of his face at once: he is one man on the season list and
       again on the week's rail, and ringing one and not the other would read
       as two answers to the same question */
    document.querySelectorAll('img.qbface[data-ring="' + id + '"]').forEach(function (im) {
      im.classList.toggle("qbface--ring", on);
    });
    try { localStorage.setItem(RINGKEY, JSON.stringify(RINGED)); } catch (e) {}
    if (typeof pushState === "function") pushState();
    /* the snowflake is drawn from the same store, so the row is drawn again
       rather than left saying cold about a man he has just marked */
    if (sport === "form") { var at = window.scrollY; render(); window.scrollTo(0, at); }
  }
  /* the id, not the element: the ledger redraws on its own beat, and a redraw
     between the two taps would otherwise lose the second one */
  var RINGAT = 0, RINGWHO = null;
  document.addEventListener("click", function (e) {
    var im = e.target.closest && e.target.closest("img.qbface[data-ring]");
    if (!im) return;
    var who = im.dataset.ring, now = Date.now();
    if (RINGWHO === who && now - RINGAT < 400) { RINGAT = 0; RINGWHO = null; toggleRing(who); }
    else { RINGAT = now; RINGWHO = who; }
  });
  /* one img, every ledger face, so the ring cannot be on one page and off
     another */
  function ledgerFace(r) {
    var cls = "qbface" + ringOn(r.id);
    return /^\d+$/.test(r.id)
      ? '<img class="' + cls + '" data-ring="' + r.id + '" alt="" loading="lazy" src="face/nfl/' + r.id +
        '.png" onerror="this.onerror=null;this.src=NOFACE">'
      : '<img class="' + cls + '" alt="" src="' + NOFACE + '">';
  }
  function formTabs() {
    var weeks = LEDGER ? Object.keys(LEDGER).sort(function (a, b) { return a - b; }) : [];
    wbar.innerHTML = "";
    /* the field has no tab: the Stacked button is its tab; the bar is CLIPS
       and the weeks (Jose, Sep 29, 2026) */
    [["clips", "CLIPS"]].concat(weeks.map(function (w) { return [w, "WEEK " + w]; })).forEach(function (pair) {
      var t = document.createElement("button");
      t.className = "wktab"; t.type = "button"; t.setAttribute("role", "tab");
      t.dataset.lw = pair[0]; t.textContent = pair[1];
      t.setAttribute("aria-selected", pair[0] === formWeek ? "true" : "false");
      wbar.appendChild(t);
    });
  }
  function formRows() {
    if (!LEDGER) return [];
    if (formWeek !== "season") return (LEDGER[formWeek] || []).map(function (r) {
      return { name: r[0], club: r[1], id: r[2], ptd: r[3], atd: r[4], h2h: r[5], ml: r[6], yds: r[7] || 0, game: r[8] || "", side: r[9] || 0, score: r[10], odds: r[11] || [[null, null], [null, null], null, null], carded: r[12] !== 0, games: 1, fin: r[14] === 1 };
    });
    var by = {};
    Object.keys(LEDGER).forEach(function (w) {
      LEDGER[w].forEach(function (r) {
        var m = by[r[2]] || (by[r[2]] = { name: r[0], club: r[1], id: r[2], ptd: 0, atd: 0, h2hw: 0, h2hl: 0, mlw: 0, mll: 0, games: 0, agg: true });
        m.club = r[1]; m.ptd += r[3]; m.atd += r[4]; m.games++;
        if (r[5] === "W") m.h2hw++; else if (r[5] === "L") m.h2hl++;
        if (r[6] === "W") m.mlw++; else if (r[6] === "L") m.mll++;
      });
    });
    return Object.keys(by).map(function (k) { return by[k]; });
  }
  function tile(v) {
    if (v === "W" || v === "L") return '<b class="wl wl--' + v.toLowerCase() + '">' + v + '</b>';
    if (v === "") return '<b class="wl wl--none">\u2013</b>';
    return v;   /* a record, already marked up */
  }
  function record(w, l) {
    return '<b class="wl wl--rec ' + (w > l ? "wl--w" : l > w ? "wl--l" : "wl--none") + '">' + w + "-" + l + "</b>";
  }
  /* ---- what the week was worth ----
     A man's card is the legs he actually cleared, each at the rung he reached:
     the passing rung comes from the ladder alt_ptd.py wrote (1+ through 5+),
     the rushing rung and the head to head and the club from the prices the
     board already holds. The legs are multiplied, which is what a card is.

     A week is one card and reads as a price: what a hundred dollars on him
     that week would have paid. A season is a run of cards, so it reads as
     units won -- a unit staked every week a book priced him, the winnings kept
     and the stake lost where the card missed, rounded down (Jose, Sep 18,
     2026). The season card is his whole production, uncapped: three passing
     touchdowns are priced at the 3+ rung, which is why a week can be worth
     more to the season than the week page shows. Multiplying the weeks instead
     would only ever grow, because we only ever multiply the legs he hit -- by
     December it would rank longevity, not quality.

     A man no book priced has no card and no number: Wentz threw three and Lock
     played the whole game, and neither was on a board before kickoff. They are
     shown for what they did and left at nothing. (Jose, Sep 17, 2026) */
