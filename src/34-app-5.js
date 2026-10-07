  function openingDay(list) {
    var now = Date.now() - 6 * 3600000;   /* a game that kicked tonight is still today */
    return list.filter(function (d) { return d[0] === today; })[0] ||
           list.filter(function (d) { return Date.parse(d[1]) >= now; })[0] ||
           list[list.length - 1];
  }
  /* the week we are standing in, not the next one whose first kickoff is
     still ahead: a Sunday afternoon belongs to the week being played */
  function openingWeek() {
    var now = Date.now();
    var sp = spans();
    for (var i = 0; i < sp.length; i++) {
      if (now >= sp[i].from && now < sp[i].to) return "W" + sp[i].w;
    }
    for (var j = 0; j < sp.length; j++) {
      if (sp[j].from > now) return "W" + sp[j].w;
    }
    return sp.length ? "W" + sp[sp.length - 1].w : today;
  }
  /* the board opens on the calendar, which counts in days */
  day = (openingDay(DAYS) || [today])[0];
  buildDays();
  render();
  /* Prices live in prices.json, not in this page. A price moving used to mean
     rewriting the whole page, so a price update and an edit to the page could
     never both happen at once -- one of the two always lost. The numbers
     written into the arrays above are the last known set: what a reader sees
     for the moment before the file lands, and what he sees if it never does.
     (Jose, Sep 18, 2026) */
  /* read again when a fight ends: the rest of the bill moves with it, and
     the new times are in the same file (Jose, Sep 18, 2026) */
  /* which bouts and games have had their prop prices off the file at least
     once, so a finished one can be frozen after that and not before */
  var TOOK = {};
  /* One card, one file. The board used to pull the whole price file every
     minute -- every game and bout on it, finished or not. A card asks for its
     own prices now, from prices/<id>.json, and a finished one asks once and is
     never asked for again (Jose, Sep 22, 2026: "it needs per card and once
     it's final it doesn't keep fetching, it's done and never starts again for
     that event"). */
  var CARDDONE = {};     /* events settled and already read: never asked again */
  /* the touchdown rows and the head to head, same job as seatMoneyline and
     for the same reason: the card is built from PROPS once, so a price file
     that lands afterwards put its numbers in the array and nothing on the
     screen. The moneyline was redrawn and these were not, so a college card
     showed its price and no touchdowns at all (Jose, Sep 22, 2026: "why cant
     i see it on the site but you got it"). */
  /* A re-seated price is the same leg. Carrying only .on across meant a leg
     he had placed lost its .placed, and grading skips anything not placed --
     so the gold border sat there for ever and never went green or red
     (Jose, Sep 22, 2026: "all golds picked need to settle too"). */
  function keepMarks(had, host) {
    if (!had) return;
    var b = host.querySelector("button.price");
    if (!b) return;
    ["on", "placed", "won", "lost"].forEach(function (c) {
      if (had.classList.contains(c)) b.classList.add(c);
    });
    if (had.dataset && had.dataset.oid && !b.dataset.oid) b.dataset.oid = had.dataset.oid;
  }
  function seatProps(card, pr) {
    if (!card || !pr) return;
    if (card.classList.contains("done") || card.dataset.settled === "1") return;
    var put = function (host, slot, short) {
      if (!host) return;
      var had = host.querySelector("button.price");
      if (!slot || !slot[0]) return;                 /* no price: leave the slot */
      var keep = host.querySelector(".ntick, .ptdline");
      var head = "";
      host.querySelectorAll(".ntick, .ptdline").forEach(function (n) { head += n.outerHTML; });
      host.innerHTML = head + priceSlot(slot[0], slot[1], short);
      keepMarks(had, host);
    };
    /* by data-kind, not by class: both rows carry ptdx--balls, and only the
       kind says which is the passing one and which the rushing */
    [["ptd", "PTD"], ["atd", "ATD"]].forEach(function (pair) {
      var rows = pr[pair[0]];
      if (!rows) return;
      /* every button knows its price: the row is found by its kind, and a
         passing row drawn without one is still the row that is not the
         rushing one -- the NFL card was built without the label, so its
         passing prices never found their buttons (Jose, Sep 23, 2026: "each
         button should be matched with the odds... they won't change") */
      var box = card.querySelector('.ptdx[data-kind="' + pair[1] + '"]') ||
                (pair[1] === "PTD" ? card.querySelector('.ptdx--balls:not([data-kind="ATD"])') : null);
      if (!box) return;
      ["l", "r"].forEach(function (w, i) {
        var side = box.querySelector(".ptdside--" + w);
        if (!side) return;
        (rows[i] || []).forEach(function (slot, n) {
          put(side.querySelector(".ptdbtn--n" + (n + 1)), slot, true);
        });
      });
    });
    if (pr.h2h) {
      var ends = card.querySelectorAll(".h2hodds");
      if (ends.length === 2) {
        [0, 1].forEach(function (i) {
          var slot = pr.h2h[i];
          if (!slot || !slot[0]) return;
          var had = ends[i].querySelector("button.price");
          ends[i].innerHTML = priceSlot(slot[0], slot[1]);
          keepMarks(had, ends[i]);
        });
      }
    }
  }
  /* the three ways a fight ends, on the card's own face. seatProps knows the
     football's rows -- the passing and rushing ladders and the head to head --
     and nothing else, so a bout whose price file landed after the card was
     drawn kept its dashes out front while the sheet, built later from the very
     same file, showed every one of them (Jose, Sep 22, 2026: "if we have the
     odds for Dana White, why don't we have it on the card outside?").

     The row is found by the tag on its own mark, not by its position, and the
     two ends are filled in the order the data names the men -- flipped with
     the card when the champion has been moved to the left. */
  function seatBout(card, pr) {
    if (!card || !pr) return;
    if (card.classList.contains("done") || card.dataset.settledBout === "1") return;
    var A = card.dataset.flip === "1" ? 1 : 0, B = A ? 0 : 1;
    [["ko", "KO"], ["sub", "SUB"], ["dec", "DEC"]].forEach(function (k) {
      var got = pr[k[0]];
      if (!got) return;
      var row = null;
      card.querySelectorAll(":scope > .ghead .gline").forEach(function (r) {
        var tag = r.querySelector(".gmk .grn");
        if (tag && tag.textContent.trim() === k[1]) row = r;
      });
      if (!row) return;
      var ends = row.querySelectorAll(".gh2h");
      if (ends.length !== 2) return;
      [[0, A], [1, B]].forEach(function (pair) {
        var slot = got[pair[1]];
        if (!slot || !slot[0]) return;
        var had = ends[pair[0]].querySelector("button.price");
        ends[pair[0]].innerHTML = "";
        ends[pair[0]].appendChild(fchip(slot));
        keepMarks(had, ends[pair[0]]);
      });
    });
  }
  /* the two moneyline buttons on a card, rewritten from a price file that
     landed after the card was drawn. A settled card is left alone: its prices
     are closed and the ghost slot is the truth. */
  function seatMoneyline(card, ml) {
    if (!card || !ml) return;
    if (card.classList.contains("done") || card.dataset.settled === "1") return;
    var slots = card.querySelectorAll(":scope > .ghead .gml");
    if (slots.length !== 2) return;
    /* a bout the page flips (the champion moved to the left) has its two
       slots the other way round from the data, so the prices follow the
       men, not the slots -- every flipped bout wore the other man's
       moneyline once the file landed (Sep 30, 2026) */
    var order = card.dataset.flip === "1" ? [[2, 3], [0, 1]] : [[0, 1], [2, 3]];
    order.forEach(function (pair, i) {
      var odds = ml[pair[0]], oid = ml[pair[1]];
      if (!odds) return;
      var had = slots[i].querySelector("button.price");
      slots[i].innerHTML = priceSlot(odds, oid);
      keepMarks(had, slots[i]);
    });
  }
  /* It answers with what happened -- "got", "none" or "bad" -- so the mark
     in the nav can say whether the asking worked, whether there was simply
     nothing to be had, or whether it could not be reached at all. Everything
     that called it before ignores the answer (Jose, Sep 23, 2026). */
  /* prices DraftKings handed back to a double tap: filled into whatever the
     board already holds -- an empty place takes the new price, a price the
     board has keeps it -- then seated on every card of that event, on every
     tab (Jose, Sep 23, 2026: "if we are waiting for 10 things and only have
     8 we should be able to get those remaining two") */
  function fillIn(had, got) {
    if (had === null || had === undefined || had === "") return got;
    if (Array.isArray(had) && Array.isArray(got)) {
      var out = had.slice();
      for (var i = 0; i < got.length; i++) out[i] = fillIn(had[i], got[i]);
      return out;
    }
    if (typeof had === "object" && had && got && typeof got === "object") {
      var o = {};
      Object.keys(had).forEach(function (k) { o[k] = had[k]; });
      Object.keys(got).forEach(function (k) { o[k] = fillIn(had[k], got[k]); });
      return o;
    }
    return had;
  }
  /* a fresh reading laid over what the card held: where DraftKings gave a
     price it stands, moved or not, and where it gave none the old one stays */
  function layOver(had, got) {
    if (got === null || got === undefined || got === "") return had;
    if (Array.isArray(got) && got.length === 2 && typeof got[0] === "string" && typeof got[1] === "string")
      return got[0] ? got : had;
    if (Array.isArray(had) && Array.isArray(got)) {
      var out = had.slice();
      for (var i = 0; i < got.length; i++) out[i] = layOver(had[i], got[i]);
      return out;
    }
    if (typeof had === "object" && had && got && typeof got === "object") {
      var o = {};
      Object.keys(had).forEach(function (k) { o[k] = had[k]; });
      Object.keys(got).forEach(function (k) { o[k] = layOver(had[k], got[k]); });
      return o;
    }
    return got;
  }
  window._seatAsked = function (id, j) {
    if (!j) return;
    var cards = document.querySelectorAll('.gcard[data-espn="' + id + '"], .gcard[data-bout="' + id + '"]');
    if (!cards.length) return;
    var bout = !!cards[0].dataset.bout, lg = cards[0].dataset.lg;
    var into = bout ? FPROPS : PROPS;
    if (j.props) into[id] = layOver(into[id], j.props);
    var ml = null;
    if (j.ml) {
      var shelf = bout ? FIGHTS : (lg === "college-football" ? CFB : SCHED);
      var col = bout ? 8 : (lg === "college-football" ? 10 : 9);
      for (var i = 0; i < shelf.length; i++) {
        if (String(shelf[i][1]) !== String(id)) continue;
        /* each side whole, price and id together, wherever DraftKings gave one */
        for (var k = 0; k < 4; k += 2) if (j.ml[k]) { shelf[i][col + k] = j.ml[k]; shelf[i][col + k + 1] = j.ml[k + 1]; }
        ml = shelf[i].slice(col, col + 4);
        break;
      }
      if (!ml) ml = j.ml;
    }
    cards.forEach(function (card) {
      try {
        if (ml) seatMoneyline(card, ml);
        if (into[id]) seatProps(card, into[id]);
        if (into[id] && bout) seatBout(card, into[id]);
      } catch (e) {}
    });
    /* a leg on the slip carries the price it was picked at; one that has
       moved is written again, so the slip and the balance pay what the card
       now says */
    var moved = false;
    Object.keys(saved).forEach(function (oid) {
      var v = saved[oid];
      if (!v || String(v.g) !== String(id)) return;
      var b = document.querySelector('button.price[data-oid="' + oid.replace(/"/g, '\\"') + '"]');
      var now = b && priceOf(b);
      if (now && now !== v.o) { v.o = now; moved = true; }
    });
    if (moved) {
      try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {}
      if (typeof pushState === "function") pushState();
      if (typeof slip === "function") slip();
    }
    if (typeof bankDraw === "function") bankDraw();
  };
  function pullCard(card) {
    if (!card) return Promise.resolve("none");
    var id = card.dataset.espn || card.dataset.bout;
    if (!id || CARDDONE[id]) return Promise.resolve("none");
    var over = card.dataset.settled === "1" || card.dataset.settledBout === "1" ||
               card.classList.contains("done");
    return fetch("prices/" + id + ".json", {cache: "no-store"})
      /* a file that is not there comes back as the page itself, 200 and
         HTML, not as a 404 -- read as JSON that throws, and the mark in the
         nav called an event with no file a failure (Jose, Sep 23, 2026:
         "double tap turned red?"). No file is nothing to be had, not a fault. */
      .then(function (r) {
        var kind = (r.headers.get("content-type") || "").toLowerCase();
        return (r.ok && kind.indexOf("json") >= 0) ? r.json() : null;
      })
      .then(function (j) {
        if (!j) return "none";
        if (j.props) {
          var into = card.dataset.bout ? FPROPS : PROPS;
          into[id] = j.props;
        }
        if (j.ml) {
          var shelf = card.dataset.bout ? FIGHTS : (card.dataset.lg === "college-football" ? CFB : SCHED);
          var col = card.dataset.bout ? 8 : (card.dataset.lg === "college-football" ? 10 : 9);
          for (var i = 0; i < shelf.length; i++) {
            if (String(shelf[i][1]) !== String(id)) continue;
            for (var k = 0; k < 4; k++) shelf[i][col + k] = j.ml[k];
            break;
          }
        }
        /* and the card is redrawn with them. Putting the prices into the
           array was only half of it: a card is built from that array once,
           so the numbers sat on the server while every college card drew
           dashes. The per-event file exists so a price never needs a page
           rebuild -- this is the step that makes that true
           (Jose, Sep 22, 2026: "why does this keep happening?"). */
        if (j.ml) seatMoneyline(card, j.ml);
        if (j.props) seatProps(card, j.props);
        if (j.props && card.dataset.bout) seatBout(card, j.props);
        /* read once, and that is that. A finished event can never change; an
           upcoming one moves on the sweep's own schedule, and the page takes
           the new build when it lands. */
        CARDDONE[id] = 1;
        return (j.ml || j.props) ? "got" : "none";
      })
      .catch(function () { return "bad"; });
  }
  /* every card on the board that still has something to learn */
  function pullCards() {
    var seen = {};
    document.querySelectorAll(".gcard[data-espn], .gcard[data-bout]").forEach(function (c) {
      var id = c.dataset.espn || c.dataset.bout;
      if (!id || seen[id] || CARDDONE[id]) return;
      seen[id] = 1;
      pullCard(c);
    });
  }
  window.pullCard = pullCard;
  window.pullCards = pullCards;
  function pullPrices() {
    var COL = { SCHED: [9, 10, 11, 12], CFB: [10, 11, 12, 13], FIGHTS: [8, 9, 10, 11] };
    var KEY = { SCHED: 1, CFB: 1, FIGHTS: 1 };
    return fetch("prices.json", {cache: "no-store"}).then(function (r) { return r.json(); }).then(function (j) {
      if (!j) return;
      var moved = 0, inPlace = [], rebuild = 0, nowPlease = 0;
      /* A game that is over keeps the price it closed at. prices.json is one
         file for the whole board and it is still asked for, but what it says
         about a finished game is some later board's number -- or the last one
         before the book took the game down -- and writing it onto the card
         moves a price he already took. Nothing about a final card can change,
         so nothing writes to one (Jose, Sep 19, 2026: "the ones that are
         final should not draw a fresh load because they are final").

         The flags come from refresh(), which may not have answered yet on the
         first pass after a load, so a kickoff well behind us counts too. That
         is not a guess at how long a game lasts -- six hours is past the end
         of any of them -- it only decides whether to leave a card alone. */
      var frozen = function (gid) {
        var card = document.querySelector('.gcard[data-espn="' + gid + '"], .gcard[data-bout="' + gid + '"]');
        if (!card) return false;
        if (card.dataset.settled === "1" || card.dataset.settledBout === "1" ||
            card.classList.contains("done")) return true;
        var k = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
        return !!k && Date.now() > k + 6 * 3600000;
      };
      /* The sheet's own prices come from PROPS and FPROPS, and nothing read
         them again after the page had loaded -- only the moneyline columns
         below. A tab open from before a sweep kept the prop prices it started
         with, and markets the book had since put up read as empty rows:
         Pantoja v Van sat on ANY KO +120 with its rounds blank while the file
         held +115 and every one priced.

         A game or a bout that is over is left exactly as it closed. Its
         numbers are taken once and never written again, the same rule the
         moneyline follows above (Jose, Sep 22, 2026: "once we get it and it's
         final they shouldn't be fetching them anymore"). */
      ["PROPS", "FPROPS"].forEach(function (name) {
        var got = j[name], into = name === "PROPS" ? PROPS : FPROPS;
        if (!got || !into) return;
        Object.keys(got).forEach(function (id) {
          /* A finished game or bout is frozen -- but frozen at what the FILE
             says, taken once, not at whatever was baked into the page when it
             was built. Freezing before the first read left Van v Pantoja on
             the page's own ANY KO +120 with three rounds and its round
             markets empty, while the file held +115, five rounds and every
             one of them priced (Jose, Sep 22, 2026). */
          if (frozen(id) && TOOK[name + id]) return;
          into[id] = got[id];
          TOOK[name + id] = 1;
        });
      });
      document.querySelectorAll(".gcard[data-bout]").forEach(function (c) { boutRail(c); });
      [["SCHED", SCHED], ["CFB", CFB], ["FIGHTS", FIGHTS]].forEach(function (pair) {
        var by = j[pair[0]] || {}, col = COL[pair[0]], key = KEY[pair[0]];
        pair[1].forEach(function (row) {
          var v = by[String(row[key])];
          if (!v) return;
          /* frozen at what the file says, taken once -- the same rule as the
             props above. A card the scoreboard settled before the first read
             froze with no moneyline at all, and every finished bout lost its
             prices (Jose, Oct 6, 2026: "why the fuck are the prices missing?") */
          if (frozen(String(row[key])) && TOOK[pair[0] + row[key]]) return;
          TOOK[pair[0] + row[key]] = 1;
          for (var i = 0; i < 4; i++) {
            while (row.length <= col[i]) row.push("");
            if (v[i] !== undefined && v[i] !== null && row[col[i]] !== v[i]) {
              row[col[i]] = v[i];
              if (i === 0 || i === 2) {
                moved++;
                inPlace.push([String(row[key]), i === 0 ? 0 : 1, v[i], v[i + 1] || ""]);
              }
            }
          }
        });
      });
      /* when each bout starts, off the book's own board: our rows carry one
         block time for a whole prelim card, and a card that runs fast moves
         the rest of the night forward (Jose, Sep 18, 2026) */
      var kicks = j.KICKS || {};
      FIGHTS.forEach(function (row) {
        if (frozen(String(row[1]))) return;
        var t = kicks[String(row[1])];
        /* our row carries one block time for a whole prelim card -- 5:30 for
           six bouts -- and the book's own clock is the real one. It only
           reaches the headings when the board is built again, so this one is
           taken at once rather than waiting for him to be still: it happens
           once a day, not every minute (Jose, Sep 19, 2026: "UFC times are
           still wrong on the day tab") */
        /* never before the block the bout is booked in: a clock off another
           listing put Black vs Amaya, a main-card bout, at 4 PM ahead of the
           whole card (Jose, Sep 26, 2026: "why is it listed as the first
           fight") */
        if (!row._block) row._block = row[2];
        if (t && Date.parse(t) < Date.parse(row._block) - 30 * 60000) t = null;
        /* and never once it has started: its real start is already on it */
        if (row._began) t = null;
        if (t && row[2] !== t) { row[2] = t; moved++; nowPlease++; }
        /* the card already drawn takes the bout's own start too, and one that
           locked on the block time reopens: Staines v Abushaar sat shut at the
           card's 7 PM with DraftKings pricing it for 9:15 and ESPN still
           calling it to come (Jose, Sep 29, 2026: "why aren't bets available") */
        var bc = t && document.querySelector('.gcard[data-bout="' + row[1] + '"]');
        if (bc) {
          bc.dataset.kick = t;
          if (bc.classList.contains("locked") && Date.now() < Date.parse(t) && !bc.classList.contains("live") &&
              bc.dataset.settledBout !== "1" && !bc.classList.contains("done")) {
            bc.classList.remove("locked");
            bc.querySelectorAll('button.price[data-shut="1"]').forEach(function (b) {
              delete b.dataset.shut; b.removeAttribute("aria-disabled");
            });
          }
        }
      });
      /* the chips a card already draws are written onto the buttons that are
         already there: the touchdown rungs, both sides, and the head to head.
         Deferring a rebuild had left the fight prices and the corrected start
         times off his board entirely, which is worse than the jumping it was
         meant to cure (Jose, Sep 19, 2026: "where are the MMA odds") */
      var chips = function (gid, v) {
        var card = document.querySelector('.gcard[data-espn="' + gid + '"], .gcard[data-bout="' + gid + '"]');
        if (!card) return true;
        /* drawn and finished: it keeps what it closed at, and it does not
           need the board built again either */
        if (frozen(gid)) return false;
        var rows = card.querySelectorAll(".ptdrow");
        /* a price for a slot the card never drew a button for -- the
           head-to-head DraftKings posted after the card was built -- cannot
           be written on; the card is forgotten and drawn again with it
           (Jose, Sep 20, 2026, 12:40 PM: "H2H are not on the board") */
        var missing = false;
        var say = function (b, cell) {
          var odds = cell && cell[0];
          if (!b) { if (odds) missing = true; return; }
          if (!odds) return;
          b.textContent = String(odds).replace("-", "\u2212");
          b.dataset.odds = odds;
          if (cell[1]) b.dataset.oid = cell[1];
        };
        [["ptd", 0], ["atd", 1]].forEach(function (pair) {
          var row = rows[pair[1]], got = v[pair[0]];
          if (!row || !got) return;
          [0, 1].forEach(function (side) {
            var box = row.querySelector(side ? ".ptdside--r" : ".ptdside--l");
            if (!box || !got[side]) return;
            [0, 1].forEach(function (rung) {
              say(box.querySelector(".ptdbtn--n" + (rung + 1) + " button.price"), got[side][rung]);
            });
          });
        });
        if (v.h2h) {
          var ends = card.querySelectorAll(".h2hside button.price, .h2hend button.price");
          [0, 1].forEach(function (i) { say(ends[i], v.h2h[i]); });
        }
        if (typeof markSaved === "function") markSaved(card);
        if (typeof placedState === "function") placedState(card);
        if (missing) { delete MADE[gid]; return true; }
        return false;
      };
      ["PROPS", "FPROPS"].forEach(function (name) {
        var mine = name === "PROPS" ? PROPS : FPROPS;
        var theirs = j[name] || {};
        Object.keys(theirs).forEach(function (k) {
          if (JSON.stringify(mine[k]) === JSON.stringify(theirs[k])) return;
          mine[k] = theirs[k]; moved++;
          /* only a card that is not on the screen, or one whose chips were
             never drawn, still needs the board built again */
          if (chips(k, theirs[k])) rebuild++;
        });
      });
      /* A moneyline that has moved is written straight onto its own button.
         Rebuilding the board for it threw him back to the top and every
         carousel to its first card, once a minute, which is unusable while a
         game is on (Jose, Sep 19, 2026: "why can't it just update it without
         doing that jump"). Only a market the board has never drawn -- a new
         rung, a bout whose clock moved -- still needs the board built again,
         and then his place is put back. */
      inPlace.forEach(function (one) {
        var card = document.querySelector('.gcard[data-espn="' + one[0] + '"], .gcard[data-bout="' + one[0] + '"]');
        if (!card) return;
        if (frozen(one[0])) return;
        var slots = card.querySelectorAll(":scope > .ghead .gml");
        var slot = slots[one[1]];
        var b = slot ? slot.querySelector("button.price") : null;
        if (!b) return;
        b.textContent = String(one[2]).replace("-", "\u2212");
        b.dataset.odds = one[2];
        if (one[3]) b.dataset.oid = one[3];
        if (typeof markSaved === "function") markSaved(card);
      });
      /* A chip that the board has never drawn needs it built again, and a
         rebuild moves rows under him: before today prices were read once at
         load, so this never happened. It waits until he has left the page
         alone, and a moneyline -- which is what actually moves during a game
         -- is written straight onto its button and needs none of this
         (Jose, Sep 19, 2026: "it never did it before") */
      if (nowPlease && busy()) {
        rebuild++;                 /* a sheet is open: it goes with the rest */
        nowPlease = 0;
      }
      /* a clock that moved waits, like everything else, until he has stopped
         scrolling: redrawing mid-scroll threw him back to where he had been */
      if (nowPlease) rebuild++;
      if (rebuild) {
        var takeIt = function () {
          if (busy() || (!document.hidden && Date.now() - LASTTOUCH < 12000)) {
            clearTimeout(window._buildWait);
            window._buildWait = setTimeout(takeIt, 15000);
            return;
          }
          var wasY = window.scrollY;
          render();
          window.scrollTo(0, wasY);
          setTimeout(function () { window.scrollTo(0, wasY); }, 60);
        };
        takeIt();
      }
    }).catch(function () {});
  }
  window.pullPrices = pullPrices;
  pullPrices();
  document.querySelectorAll(".gmorebtn").forEach(function (b) {
    b.addEventListener("click", function () {
      var sheet = b._sheet || (b._sheet = b.nextElementSibling && b.nextElementSibling.tagName === "DIALOG" ? b.nextElementSibling : null);
      if (sheet && sheet.tagName === "DIALOG") openSheet(sheet);
    });
  });

  /* Every spelling the play files use, pinned to the one id per man, so a name
     is never matched across sources by string. */
  var PLAYNAME = {"A.Mitchell": "4597500", "A.Mitchell.": "4597500", "A.Pierce": "4360078", "A.Pierce.": "4360078", "A.Rodgers": "8439", "A.Rodgers.": "8439", "A.St.": "4374302", "A.St. Brown": "4374302", "Aa.Rodgers": "8439", "B.Mayfield": "3052587", "B.Nix": "4426338", "B.Nix.": "4426338", "B.Thomas": "4432773", "B.Thomas.": "4432773", "B.Young": "4685720", "C.Godwin": "3116165", "C.Godwin.": "3116165", "C.Lamb": "4241389", "C.Lamb.": "4241389", "C.Olave": "4361370", "C.Olave.": "4361370", "C.Stroud": "4432577", "C.Sutton": "3128429", "C.Sutton.": "3128429", "C.Ward": "4688380", "C.Watson": "4248528", "C.Watson.": "4248528", "D.Goedert": "3121023", "D.Goedert.": "3121023", "D.Jones": "3917792", "D.Jones.": "3917792", "D.London": "4426502", "D.London.": "4426502", "D.Metcalf": "4047650", "D.Metcalf.": "4047650", "D.Moore": "3915416", "D.Moore.": "3915416", "D.Prescott": "2577417", "D.Prescott.": "2577417", "D.Schultz": "3117256", "D.Schultz.": "3117256", "D.Smith": "4241478", "D.Smith.": "4241478", "D.Vele": "4569559", "D.Vele.": "4569559", "D.Watson": "3122840", "DK.Metcalf": "4047650", "DK.Metcalf.": "4047650", "Dj.Moore": "3915416", "Dj.Moore.": "3915416", "E.Egbuka": "4567750", "E.Egbuka.": "4567750", "G.Pickens": "4426354", "G.Pickens.": "4426354", "G.Smith": "15864", "G.Wilson": "4569618", "G.Wilson.": "4569618", "I.Likely": "4361050", "I.Likely.": "4361050", "J.Addison": "4429205", "J.Addison.": "4429205", "J.Allen": "3918298", "J.Allen.": "3918298", "J.Brissett": "2578570", "J.Brissett.": "2578570", "J.Burrow": "3915511", "J.Chase": "4362628", "J.Chase.": "4362628", "J.Coker": "4695883", "J.Coker.": "4695883", "J.Dart": "4689114", "J.Downs": "4688813", "J.Downs.": "4688813", "J.Goff": "3046779", "J.Herbert": "4038941", "J.Hurts": "4040715", "J.Hurts.": "4040715", "J.Jeudy": "4241463", "J.Jeudy.": "4241463", "J.Nailor": "4382466", "J.Nailor.": "4382466", "J.Reed": "4362249", "J.Reed.": "4362249", "J.Waddle": "4372016", "J.Waddle.": "4372016", "Jos.Allen": "3918298", "K.Cousins": "14880", "K.Cousins.": "14880", "K.Murray": "3917315", "K.Pitts": "4360248", "K.Pitts.": "4360248", "K.Shakir": "4373678", "K.Shakir.": "4373678", "L.Burden": "4685278", "L.Burden.": "4685278", "L.Jackson": "3916387", "L.Jackson.": "3916387", "L.McConkey": "4612826", "L.McConkey.": "4612826", "M.Harrison": "4432708", "M.Harrison.": "4432708", "M.Nabers": "4595348", "M.Nabers.": "4595348", "M.Pittman": "4035687", "M.Pittman.": "4035687", "M.Willis": "4242512", "M.Willis.": "4242512", "M.Wilson": "4360761", "M.Wilson.": "4360761", "Mi.Wilson": "4360761", "Mi.Wilson.": "4360761", "N.Collins": "4258173", "N.Collins.": "4258173", "P.Mahomes": "3139477", "P.Washington": "4432620", "P.Washington.": "4432620", "Q.Johnston": "4429025", "Q.Johnston.": "4429025", "R.Bateman": "4360939", "R.Bateman.": "4360939", "R.Odunze": "4431299", "R.Odunze.": "4431299", "R.Rice": "4428331", "R.Rice.": "4428331", "S.Diggs": "2976212", "S.Diggs.": "2976212", "T.Higgins": "4239993", "T.Higgins.": "4239993", "T.Kelce": "15847", "T.Kelce.": "15847", "T.Lawrence": "4360310", "T.McLaurin": "3121422", "T.McLaurin.": "3121422", "T.McMillan": "4685472", "T.McMillan.": "4685472", "T.Shough": "4360689", "T.Tucker": "4428718", "T.Tucker.": "4428718", "W.Robinson": "4569587", "W.Robinson.": "4569587", "Z.Flowers": "4429615", "Z.Flowers.": "4429615"};
  /* ---- live from ESPN, asked by the page itself every half minute ---- */
  var GOLD = "#ffffff", BLUE = "#ffffff";
  /* ESPN answers no browser directly -- no Access-Control-Allow-Origin -- so
     every call goes through our own /espn, which passes it on and adds the
     header. A settled game comes from site/final/*.json and never noticed; a
     game still being played fell through to ESPN and silently got nothing, on
     every sport. (Jose spotted it on Syracuse at Pittsburgh, Sep 17, 2026) */
  function espnUrl(u) { return "/espn?u=" + encodeURIComponent(u); }
  /* theScore's box for a game, as ESPN writes one, for the two passers on
     the card only: each is found on his own side of the ball, by surname,
     or as the one man on that side who has thrown -- the two passers in the
     game are the only men it could be */
  var SCOREBOX = null;
  function scoreBox(card, lq, rq) {
    var gid = card.dataset.espn;
    if (!gid) return;
    if (SCOREBOX === null) {
      SCOREBOX = {};
      fetch("scoreboxes.json", { cache: "no-store" }).then(function (r) { return r.json(); })
        .then(function (j) { SCOREBOX = j || {}; }).catch(function () {});
      return;
    }
    var path = SCOREBOX[gid];
    if (!path || card._sboxBusy) return;
    card._sboxBusy = true;
    fetch(espnUrl("https://api.thescore.com" + path + "/player_records"), { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (recs) {
        card._sboxBusy = false;
        if (!Array.isArray(recs)) return;
        var sur = function (n) {
          return String(n || "").replace(/\s+(Jr\.?|Sr\.?|II|III|IV|V)$/i, "").split(" ").pop().toLowerCase();
        };
        var mk = function (id, name, side) {
          var mine = recs.filter(function (x) { return x.alignment === side && x.player; });
          var hit = mine.filter(function (x) { return sur(x.player.full_name) === sur(name); });
          if (hit.length !== 1) hit = mine.filter(function (x) { return (x.passing_attempts || 0) > 0; });
          if (hit.length !== 1) return null;
          var x = hit[0], him = { id: String(id), displayName: name, jersey: String(x.player.number || "") };
          return { athlete: him, x: x };
        };
        var men = [mk(card.dataset.lqbid, card.dataset.lqb, "away"), mk(card.dataset.rqbid, card.dataset.rqb, "home")]
          .filter(Boolean);
        if (!men.length) return;
        var cat = function (name, yk, tk) {
          return { name: name, labels: ["YDS", "TD"],
                   athletes: men.map(function (m) { return { athlete: m.athlete, stats: [String(m.x[yk] || 0), String(m.x[tk] || 0)] }; }) };
        };
        card._sbox = [{ team: {}, statistics: [
          cat("passing", "passing_yards", "passing_touchdowns"),
          cat("rushing", "rushing_yards", "rushing_touchdowns"),
          cat("receiving", "receiving_yards", "receiving_touchdowns")] }];
      })
      .catch(function () { card._sboxBusy = false; });
  }
  function statLine(box, who, cat, want) {
    var byId = /^\d+$/.test(String(who));
    var out = null;
    (box || []).forEach(function (team) {
      (team.statistics || []).forEach(function (c) {
        if (c.name !== cat) return;
        (c.athletes || []).forEach(function (a) {
          var him = a.athlete || {};
          if (byId ? String(him.id) !== String(who)
                   : (him.displayName || "") !== who) return;
          var i = (c.labels || []).indexOf(want);
          if (i >= 0) out = parseInt((a.stats || [])[i], 10);
        });
      });
    });
    return out;
  }
  function tdCount(box, who) {
    var t = 0, got = false;
    ["rushing", "receiving"].forEach(function (cat) {
      var v = statLine(box, who, cat, "TD");
      if (v !== null && !isNaN(v)) { t += v; got = true; }
    });
    return got ? t : null;
  }
  var CHECK = '<svg viewBox="0 0 24 24" width="15" height="15"><polyline points="4,13 9,18 20,6" fill="none" stroke="currentColor" stroke-width="3.4" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var CROSS = '<svg viewBox="0 0 24 24" width="15" height="15"><line x1="5" y1="5" x2="19" y2="19" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"/><line x1="19" y1="5" x2="5" y2="19" stroke="currentColor" stroke-width="3.4" stroke-linecap="round"/></svg>';
  function mark(cell, hit) {
    if (!cell || !cell.querySelector("button.price")) return;
    stamp(cell, hit, false);
  }
  /* host: where the mark lives. inward: true when it must face left. */
  function stamp(host, hit, inward) {
    if (!host) return;
    var old = host.querySelector(":scope > .mk");
    if (old) old.parentNode.removeChild(old);
    if (hit === null || hit === undefined) return;
    var m = document.createElement("span");
    m.className = "mk " + (hit === "draw" ? "dr" : hit === "nc" ? "nc" : hit ? "ok" : "no") + (inward ? " mk--first" : "");
    /* on the head line a club or a fighter gets a W, L, D or NC tile, the way
       STATSCORE writes form: green, red, yellow, grey. A price keeps its tick
       or cross (Jose, Sep 16, 2026) */
    if (host.classList.contains("gteam")) {
      m.innerHTML = '<b class="wl">' + (hit === "draw" ? "D" : hit === "nc" ? "NC" : hit ? "W" : "L") + "</b>";
    } else {
      m.innerHTML = hit ? CHECK : CROSS;
    }
    host.appendChild(m);
  }
  function rowCells(card, label) {
    var out = null;
    card.querySelectorAll(".grow").forEach(function (r) {
      var mk = r.querySelector(".gmk");
      if (mk && mk.textContent.trim() === label) out = r.querySelectorAll(".gcell");
    });
    return out;
  }
  /* every touchdown on the curve: a tick from the line to the floor and the
     ball or the runner under it, in the scoring club's color (Jose, Sep 17,
     2026). Kicks are not marked; the curve already shows them. */
  function markScores(card, d, series, lhome) {
    var svg = card.querySelector(".wpx > svg"), pts = card._wp;
    if (!svg || !pts || !pts.length) return;
    svg.querySelectorAll(".wptd").forEach(function (n) { n.remove(); });
    card.querySelectorAll(".wpmarks").forEach(function (n) { n.remove(); });   /* both rows, or a refresh stacks another copy (Jose, Sep 17, 2026) */
    var comp = (((d.header || {}).competitions) || [{}])[0] || {};
    var home = "", away = "";
    (comp.competitors || []).forEach(function (x, i) {
      var ab = (x.team || {}).abbreviation || "";
      if (x.homeAway === "home" || (!x.homeAway && i === 0)) home = ab; else away = ab;
    });
    var leftAb = lhome ? home : away;
    var lines = svg.querySelectorAll("polyline");
    var lc = lines[0] ? lines[0].getAttribute("stroke") : "#fff", rc = lines[1] ? lines[1].getAttribute("stroke") : "#fff";
    var at = {}; series.forEach(function (p, i) { at[p.playId] = i; });
    /* the passer's own scores only: every passing touchdown, and a rushing one
       only when he ran it in himself. The top club's marks hang from the top,
       the bottom club's stand on the floor (Jose, Sep 17, 2026). */
    var qbs = [card.dataset.lqb || "", card.dataset.rqb || ""];
    var top = document.createElement("div"), bot = document.createElement("div");
    top.className = "wpmarks wpmarks--top"; bot.className = "wpmarks wpmarks--bot";
    (d.scoringPlays || []).forEach(function (sp) {
      var t = sp.text || "", kind = "";
      /* two ways of writing it: "X 15 Yd pass from Y" and, in a college
         settled file, "A. Sheppard pass to C. Chase for 67 yds, for a TD" --
         the second never matched, so college charts had no marks at all
         (Jose, Sep 25, 2026: "can we make CFB match NFL") */
      var ran = function (q) {
        if (!q) return false;
        var b = q.split(" "), short = b[0].charAt(0) + ". " + b.slice(1).join(" ");
        return t.indexOf(q) === 0 || t.indexOf(short) === 0;
      };
      if (/ pass from /i.test(t) || / pass to .* for a TD/i.test(t)) kind = "ball";
      else if ((/\d+ Yd (Rush|Run)/i.test(t) || / run for \d+ yds?, for a TD/i.test(t)) && qbs.some(ran)) kind = "run";
      var i = at[sp.id];
      if (!kind || i === undefined || !pts[i]) return;
      var ab = (sp.team || {}).abbreviation || "", isTop = ab === leftAb, col = isTop ? lc : rc;
      var ln = document.createElementNS("http://www.w3.org/2000/svg", "line");
      ln.setAttribute("class", "wptd"); ln.setAttribute("x1", pts[i].x); ln.setAttribute("x2", pts[i].x);
      ln.setAttribute("y1", isTop ? "0" : "120"); ln.setAttribute("y2", "60"); ln.setAttribute("stroke", col);
      ln.setAttribute("stroke-width", "1"); ln.setAttribute("vector-effect", "non-scaling-stroke"); ln.setAttribute("opacity", "0.85");
      svg.appendChild(ln);
      var m = document.createElement("i");
      m.className = "wptd wptd--" + kind; m.style.left = (pts[i].x / 3) + "%"; m.style.color = col;
      m.title = t; m.innerHTML = kind === "ball" ? BALLSVG : RUSHSVG;
      (isTop ? top : bot).appendChild(m);
    });
    if (top.childNodes.length) svg.parentNode.insertBefore(top, svg);
    if (bot.childNodes.length) svg.parentNode.appendChild(bot);
  }
  function paintChart(card, series, lhome) {
    var svg = card.querySelector(".wpx > svg");
    if (!svg || !series || series.length < 2) return null;
    var pts = series.map(function (p, i) {
      var left = lhome ? p.homeWinPercentage : 1 - p.homeWinPercentage;
      return (i * 300 / (series.length - 1)).toFixed(1) + "," + (110 - left * 110).toFixed(1);
    });
    var line = pts.join(" ");
    svg.querySelectorAll("polyline").forEach(function (pl) {
      pl.setAttribute("points", line);
      pl.removeAttribute("stroke-dasharray");
    });
    svg.querySelectorAll("polygon").forEach(function (pg) {
      pg.setAttribute("points", line + " 300,55 0,55");
    });
    var last = series[series.length - 1];
    return (lhome ? last.homeWinPercentage : 1 - last.homeWinPercentage) * 100;
  }
  /* ---- one feed a game ----
     The cards and the form page were both reading the same game from ESPN on
     their own clocks, each with its own throttle, and only the cards ever
     looked at the settled file. They ask here now: the file where there is
     one, ESPN where there is not, and the same answer handed to both for
     twenty seconds (Jose, Sep 18, 2026). */
  /* the first render asks for a game before this line would have run, so the
     shelf is made on first use rather than on the way past (Jose, Sep 18,
     2026) */
  var FEED;
  function gameFeed(id, lg) {
    FEED = FEED || {};
    id = String(id);
    var hit = FEED[id];
    /* five seconds, the relay's own hold: a live clock read twenty seconds
       stale ran half a minute behind the broadcast (Jose, Sep 26, 2026) */
    if (hit && (hit.final || Date.now() - hit.at < 5000)) return hit.p;
    var league = lg === "college-football" ? "college-football" : "nfl";
    var box = { at: Date.now(), final: false, tried: hit ? hit.tried : false };
    var wire = function () {
      return fetch(espnUrl("https://site.web.api.espn.com/apis/site/v2/sports/football/" +
                           league + "/summary?event=" + id))
        .then(function (r) { return r.json(); });
    };
    /* the settled file is asked for once, and again only after a game reads
       final -- settle.py writes it hours later */
    box.p = (box.tried && !(hit && hit.done))
      ? wire()
      : fetch("final/" + id + ".json").then(function (r) {
          if (!r.ok) throw new Error("no file");
          return r.json().then(function (d) { box.final = true; return d; });
        }).catch(wire);
    box.tried = true;
    box.p = box.p.then(function (d) {
      var st = (((((d.header || {}).competitions) || [{}])[0] || {}).status || {}).type || {};
      box.done = st.state === "post" || st.completed === true;
      return d;
    });
    FEED[id] = box;
    return box.p;
  }
  /* games this page saw go final, told to the site in one breath */
  var FINALSEEN = {}, finalT = null;
  function finalSeen(id) {
    if (FINALSEEN[id]) return;
    FINALSEEN[id] = 1;
    clearTimeout(finalT);
    finalT = setTimeout(function () {
      var ids = Object.keys(FINALSEEN).filter(function (k) { return FINALSEEN[k] === 1; });
      ids.forEach(function (k) { FINALSEEN[k] = 2; });
      if (ids.length) fetch("settled", { method: "POST", headers: { "content-type": "application/json" },
                                       body: JSON.stringify({ games: ids }) }).catch(function () {});
    }, 3000);
  }
  function refresh(card) {
    var id = card.dataset.espn, lg = card.dataset.lg;
    if (!id) return;
    if (card.dataset.settled) return;           /* drawn from its file already; nothing changes */
    var kick = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
    if (kick && kick > Date.now() + 20 * 60000) return;   /* not kicked off: nothing to read yet */
    gameFeed(id, lg)
      .then(function (d) {
        if (((FEED || {})[String(id)] || {}).final) { card.dataset.settled = "1"; card._full = true; }
        return d;
      })
      .then(function (d) {
        var comp = (((d.header || {}).competitions) || [{}])[0] || {};
        var st = (comp.status || {}).type || {};
        var done = st.state === "post" || st.completed === true;
        var live = !done && st.state === "in";
        /* over: the head-to-head price beside each name goes (Jose, Sep 27,
           2026: "after the game we can remove the button for h2h") */
        card.classList.toggle("gdone", done);
        /* a finished game has nothing left to watch (Jose, Sep 17, 2026) --
           and nothing left to ask about either. It used to keep reading the
           same finished summary every thirty seconds for as long as the tab
           stayed open, because only the final file ever set this flag and the
           file is not written until hours later (Jose, Sep 18, 2026) */
        if (done) {
          /* read final from ESPN, not from a saved file: the site is told
             now, and saves it for every device (Jose, Sep 29, 2026) */
          if (!((FEED || {})[String(id)] || {}).final) finalSeen(id);
          card.classList.add("done");
          card.dataset.settled = "1";
          markOver(card.dataset.espn);
          dropHide(card);
          askSink();
          ledgerNow(card.dataset.espn, d);
        }
        if (live || done) {
          card.classList.add("locked");
          card.querySelectorAll("button.price").forEach(function (b) {
            shutPrice(b);
            b.classList.remove("on");
          });
        }
        var sides = {};
        (comp.competitors || []).forEach(function (c) { sides[c.homeAway] = c; });
        /* Stash these before anything reads them -- the buttons were being
           drawn first and always saw an empty list. The summary's own video
           list is short of the real one (Stefon Diggs' touchdown is in the
           dedicated feed and not in the summary), so ask for that once per
           card and keep it. */
        if (d.scoringPlays && d.scoringPlays.length) card._scoring = d.scoringPlays;
        if (!card._clips || !card._clips.length) card._clips = d.videos || [];
        mergeClips(card);
        if (!card._full) {
          card._full = true;
          fetch(espnUrl("https://site.web.api.espn.com/apis/site/v2/sports/football/" +
                (card.dataset.lg === "nfl" ? "nfl" : "college-football") +
                "/videos?event=" + card.dataset.espn + "&limit=200"))
            .then(function (r) { return r.json(); })
            .then(function (j) {
              if (j && j.videos && j.videos.length) {
                card._clips = j.videos;
                mergeClips(card);
                delete card.dataset.settled;   /* one more pass, for the buttons */
                refresh(card);
              }
            })
            .catch(function () {});
        }
        var lhome = card.dataset.lhome === "1";
        var lside = lhome ? sides.home : sides.away;
        var rside = lhome ? sides.away : sides.home;
        var when = card.querySelector(".gtime");
        /* both sides or neither, the same rule the ledger follows */
        var ls = (lside || {}).score, rs = (rside || {}).score;
        var score = (ls === undefined || ls === null || rs === undefined || rs === null)
                    ? "" : ls + "–" + rs;
        /* a game being played says so under the clock (Jose, Sep 17, 2026) */
        var mark = card.querySelector(".gwatch");
        if (when && live) {
          /* while the game is on, the play mark rides beside the LIVE badge,
             the two of them centered under the score (Jose, Sep 17, 2026) */
          if (mark) mark.remove();
          when.innerHTML = st.shortDetail + "<br>" + score +
            '<span class="glivebar"><img class="glive" src="ico/live-white.svg" alt="Live" ' +
            'width="34" height="34"></span>';
          /* the eye rides the live bar too. Rebuilding the bar left it behind
             and it fell back to the corner, so once a game kicked off the
             three of them stopped being one row
             (Jose, Sep 20, 2026: "the eye button needs to be [with] the live
             and play button in line, 1 row") */
          if (mark) when.querySelector(".glivebar").appendChild(mark);
          seatEye(card);
        } else if (when && done) when.innerHTML = "FINAL<br>" + score;
        /* the card's own state reads these back rather than the clock's
           innerHTML, so the strip can say what the mock says it says */
        if (ls !== undefined && ls !== null) card.dataset.ls = ls;
        if (rs !== undefined && rs !== null) card.dataset.rs = rs;
        card.dataset.clk = live ? (st.shortDetail || "LIVE") : (done ? "FINAL" : "");
        /* the clock between readings: ESPN gives it a play at a time, so it
           counts down here on its own while it is running -- running meaning
           it moved since the last reading -- and stops the moment ESPN's
           stops (Jose, Sep 26, 2026: "smoothly moving the tick") */
        var cs = /^(\d+):(\d\d)/.exec((comp.status || {}).displayClock || "");
        if (live && cs) {
          var sec = +cs[1] * 60 + +cs[2], was = card._clk;
          card._clk = { sec: sec, at: Date.now(), run: !!(was && was.sec !== sec && was.per === (comp.status || {}).period),
                        per: (comp.status || {}).period };
        } else card._clk = null;

        var series = d.winprobability;
        if (series && series.length > 1) {
          var plays = {};
          /* the drive being played is in `current`, not in `previous`, and
             without it the newest stretch of the curve -- the part somebody
             watching a live game is reading -- had no play under it at all */
          var drives = (((d.drives || {}).previous) || [])
            .concat(((d.drives || {}).current) ? [(d.drives || {}).current] : []);
          drives.forEach(function (dr) {
            (dr.plays || []).forEach(function (p) {
              var st = p.start || {};
              plays[p.id] = {
                q: (p.period || {}).number,
                c: (p.clock || {}).displayValue || "",
                d: st.downDistanceText || "",
                t: (p.text || "").slice(0, 120),
                /* what the card's own graph needs to put the field back the
                   way it stood on that play: the yard line ESPN counts from
                   the home goal, how far there was to go, and who had it */
                sd: st.shortDownDistanceText || "", dn: st.down,
                yl: st.yardLine, n: st.distance, g: st.yardsToEndzone,
                s: st.possessionText || "", o: (st.team || {}).id || ""
              };
            });
          });
          card._wp = series.map(function (p, i) {
            var left = lhome ? p.homeWinPercentage : 1 - p.homeWinPercentage;
            var pl = plays[p.playId] || {};
            return { x: i * 300 / (series.length - 1), y: 110 - left * 110,
                     l: left * 100, q: pl.q, c: pl.c, d: pl.d, t: pl.t,
                     sd: pl.sd, dn: pl.dn, yl: pl.yl, n: pl.n, g: pl.g,
                     s: pl.s, o: pl.o };
          });
          wireRead(card);
          markScores(card, d, series, lhome);
        }
        /* the field, under the score -- after the series, because on a live
           game the strip IS the graph and the graph is drawn from it */
        drawDrive(card, d, lside, rside, live);
        /* Before a ball is thrown there is no curve, only ESPN's own
           projection. It is still the number the sheet is asking for. */
        if (!series || series.length < 2) {
          var pr = d.predictor || {};
          var hp = parseFloat((pr.homeTeam || {}).gameProjection);
          if (!isNaN(hp)) {
            var left = lhome ? hp : 100 - hp;
            var reads0 = card.querySelectorAll(".wpbig");
            if (reads0.length === 2) {
              reads0[0].textContent = left.toFixed(1) + "%";
              reads0[1].textContent = (100 - left).toFixed(1) + "%";
            }
          }
        }
        var pct = paintChart(card, series, lhome);
        if (pct !== null && pct !== undefined) card._last = pct;
        if (pct !== null && pct !== undefined) {
          var reads = card.querySelectorAll(".wpbig");
          if (reads.length === 2) {
            reads[0].textContent = pct.toFixed(1) + "%";
            reads[1].textContent = (100 - pct).toFixed(1) + "%";
          }
        }

        var recCount = {}, firstOver = false;
        (((d.drives || {}).previous) || []).forEach(function (dr) {
          (dr.plays || []).forEach(function (p) {
            var per = (p.period || {}).number;
            if (per > 1) firstOver = true;
            if (per !== 1) return;
            var txt = p.text || "";
            var m = txt.match(/pass (?:short|deep) (?:left|right|middle) to ([A-Z][A-Za-z.'\-]*(?: [A-Z][A-Za-z.'\-]*)*)/);
            if (m && txt.indexOf("incomplete") < 0) {
              var wrote = m[1].trim();
              var id = PLAYNAME[wrote] || PLAYNAME[wrote + "."] ||
                       PLAYNAME[wrote.replace(/\.$/, "")] || null;
              var key = id || wrote.split(" ").pop();
              recCount[key] = (recCount[key] || 0) + 1;
            }
          });
        });
        if (done) firstOver = true;

        var box = (d.boxscore || {}).players || [];
        var lq = card.dataset.lqbid || card.dataset.lqb;
        var rq = card.dataset.rqbid || card.dataset.rqb;
        /* ESPN's box with nobody in it while the game is on: theScore's is
           read instead, and written in ESPN's shape for everything below.
           It lands a pass behind (Jose, Sep 26, 2026: Mestemaker at 260 and
           2 TD, the card at 0) */
        var espnEmpty = !box.some(function (tm) {
          return (tm.statistics || []).some(function (c) { return (c.athletes || []).length; });
        });
        if (espnEmpty && (live || done)) {
          scoreBox(card, lq, rq);
          if (card._sbox) box = card._sbox;
        }
        var stats = {};
        /* each passer's jersey number, from the box score, for the ball's
           shirt on the drive bar (Jose, Sep 26, 2026: "make it the QB's
           jersey") */
        card._qbjer = card._qbjer || ["", ""];
        [lq, rq].forEach(function (q, i) {
          box.forEach(function (tm) {
            (tm.statistics || []).forEach(function (c) {
              (c.athletes || []).forEach(function (a) {
                var him = a.athlete || {};
                if (String(him.id) === String(q) && him.jersey) card._qbjer[i] = String(him.jersey);
              });
            });
          });
        });
        [["l", lq], ["r", rq]].forEach(function (p) {
          if (!p[1]) return;
          stats[p[0]] = {
            ptd: statLine(box, p[1], "passing", "TD"),
            pyds: statLine(box, p[1], "passing", "YDS"),
            td: tdCount(box, p[1])
          };
        });

        card.querySelectorAll(".trk").forEach(function (t) {
          var head = t.querySelector(".trkhead").textContent;
          var who = null;
          if (rq && head.indexOf(rq.split(" ").pop()) >= 0) who = "r";
          else if (lq && head.indexOf(lq.split(" ").pop()) >= 0) who = "l";
          var mine = stats[who];
          if (!mine) return;
          var isPTD = head.indexOf("PTD") >= 0;
          var v = isPTD ? mine.ptd : mine.td;
          if (v === null || v === undefined || isNaN(v)) return;
          var need = parseInt(t.dataset.need, 10) || 1;
          var scale = parseInt(t.dataset.scale, 10) || (isPTD ? 4 : 3);
          t.querySelector(".trkfill").style.width =
            (Math.min(v, scale) / scale * 100).toFixed(0) + "%";
          var counter = t.querySelector(".trkbox");
          counter.textContent = v;
          counter.classList.toggle("hit", v >= need);
          var tk = t.querySelector(".tick");
          if (tk) tk.classList.toggle("hit", v >= need);
        });

        /* halftime on a game he has a leg in: say so when it has gone sideways
           (Jose, Sep 26, 2026: "a 55 total at 3 at the half ... up 30 at the
           half and I have a QB to throw 2 PTD") */
        if (live && typeof liveAlert === "function") liveAlert(card, comp, ls, rs, stats, box);
        /* the final line, kept for the box that says what the game paid */
        card._qbst = stats;
        if (done && typeof showHitsLater === "function") showHitsLater(card);
        /* the section is .h2hx — it was rebuilt under that name and this
           lookup was never moved, so the whole block sat dead */
        var h = card.querySelector(".h2hx") || card.querySelector(".h2h");
        /* a passer who has not thrown yet is not in the box score at all: he
           is nought, not missing, and one side missing held the other's yards
           at 0 too -- Manning 56 read 0 while Brandon had not thrown
           (Jose, Sep 26, 2026) */
        if (h && stats.l && stats.r && (stats.l.pyds !== null || stats.r.pyds !== null)) {
          var lv = stats.l.pyds || 0, rv = stats.r.pyds || 0, gap = lv - rv;
          var span = Math.max(Math.abs(gap), 60);
          var half = Math.min(Math.abs(gap) / span * 50, 50);
          var fill = h.querySelector(".h2hfill"), tick = h.querySelector(".h2htick");
          /* the lead rides the tick as a chip ("+38"); it is made once and then
             moved. No face on the bar any more -- the faces are on the name line
             (Jose, Sep 16, 2026). */
          var face = h.querySelector(".h2hchip");
          if (!face) {
            face = document.createElement("b");
            face.className = "h2hchip";
            (tick.parentNode || h).appendChild(face);
            var oldFace = h.querySelector(".h2hface"), oldLead = h.querySelector(".h2hlead");
            if (oldFace) oldFace.remove();
            if (oldLead) oldLead.remove();
          }
          /* the man on the left leads leftward from the zero, the man on the
             right leads rightward — it was drawing each lead into the other
             man's half */
          /* the club in front colours the bar */
          var clubs = card.querySelectorAll(".ghead .glogo");
          var leftClub = clubs[0] ? clubs[0].getAttribute("alt") : "";
          var rightClub = clubs[1] ? clubs[1].getAttribute("alt") : "";
          var hue = gap > 0 ? clubHue(leftClub, lgOf(card)) : clubHue(rightClub, lgOf(card));
          if (gap > 0) {
            fill.style.left = (50 - half) + "%"; fill.style.width = half + "%";
            fill.style.background = hue || GOLD; tick.style.left = (50 - half) + "%";
          } else if (gap < 0) {
            fill.style.left = "50%"; fill.style.width = half + "%";
            fill.style.background = hue || BLUE; tick.style.left = (50 + half) + "%";
          } else {
            fill.style.left = "50%"; fill.style.width = "0"; tick.style.left = "50%";
          }
          /* whoever is in front, at the edge of his own fill */
          var lead = gap > 0 ? card.dataset.lqbid : (gap < 0 ? card.dataset.rqbid : "");
          /* a chip wearing the Kalshi jersey is the card's own to draw
             (stateV3): the "+56" written here wiped the shirt off the bar */
          if (face.classList.contains("gjersey") || face.classList.contains("gyd")) {
            if (window.stateV3) setTimeout(function () { window.stateV3(card); }, 0);
          } else if (lead) {
            face.textContent = "+" + Math.abs(gap);
            face.style.color = readable(hue) || (gap > 0 ? GOLD : BLUE);
            /* the tick can sit hard against either end of the bar -- a big
               enough gap puts it at nought or a hundred -- and the chip is
               centred on it, so half of it would hang off onto the box
               beside it. It is held far enough in to stay on the track. */
            var bar = h.querySelector(".h2hbar");
            var edge = bar && bar.offsetWidth
                     ? (20 / bar.offsetWidth) * 100 : 13;
            var at = parseFloat(tick.style.left);
            if (isNaN(at)) at = 50;
            var held = Math.min(100 - edge, Math.max(edge, at));
            face.style.left = held + "%";
            /* the tick would otherwise stick out past a held-back face */
            tick.style.opacity = Math.abs(held - at) > 0.5 ? "0" : "";
            face.classList.add("on");
          } else {
            face.classList.remove("on");
            face.textContent = "";
            tick.style.opacity = "";
          }
          tick.querySelector("b").textContent = "";
          var foot = h.querySelectorAll(".h2hrow .trkbox");
          foot[0].textContent = lv;
          foot[1].textContent = rv;
          foot[0].classList.toggle("hit", gap > 0);
          foot[1].classList.toggle("hit", gap < 0);
        }


        /* the combined passing section, where one exists */
        card.querySelectorAll(".grow").forEach(function (r) {
          var lab = r.querySelector(".gmk");
          if (!lab || lab.textContent.trim() !== "1+ REC 1Q") return;
          r.querySelectorAll(".gcell").forEach(function (cellSide, ci) {
            cellSide.querySelectorAll(".recman").forEach(function (man) {
              var nm = man.querySelector(".wrname");
              if (!nm) return;
              var written = nm.textContent.replace(/[\u2713\u2715]/g, "").trim();
              var caught = man.dataset.pid ? recCount[man.dataset.pid] : undefined;
              if (caught === undefined) caught = recCount[written];
              if (caught === null || caught === undefined) return;
              stamp(nm, caught >= 1 ? true : (firstOver ? false : null), ci === 1);
            });
          });
        });

        card.querySelectorAll(".ptdx").forEach(function (ptd) {
          var scale = parseFloat(ptd.dataset.scale) || 4;
          var over = parseInt(ptd.dataset.need, 10) || 2;
          var kind = ptd.dataset.kind || "PTD";
          [["l", 0], ["r", 1]].forEach(function (sd) {
            var mine = stats[sd[0]];
            var pane = ptd.querySelector(".ptdside--" + sd[0]);
            if (!pane) return;
            if (!mine) { if (!done) return; mine = {}; }
            var v = kind === "ATD" ? mine.td : mine.ptd;
            /* A man who never carried the ball has no rushing line at all, and
               that was read as "not known yet" and left grey. On a finished
               game it is a nought, and a nought is red. Cooper Rush and Kyler
               Murray sat grey for it. (Jose, Sep 17, 2026) */
            if (v === null || v === undefined || isNaN(v)) {
              if (!done) return;
              v = 0;
            }
            /* the football sample has no bar to fill */
            var fill = pane.querySelector(".ptdfill");
            if (fill) {
              fill.style.width = (Math.min(v, scale) / scale * 100).toFixed(1) + "%";
            }
            /* A way into the highlights, one per touchdown he actually threw:
             the 1+ row carries the first, the 2+ row the second. ESPN has no
             link from a play to its clip -- the only join is headline prose,
             and it is ambiguous whenever a man scores twice in a game -- so
             these open the game's own video page rather than guess a clip. */
          pane.querySelectorAll(".ptdbtn").forEach(function (btn) {
            var line = btn.querySelector(".ptdline");
            var need = line ? parseInt(line.textContent, 10) : NaN;
            /* the rushing row carries no line to count to: its one button is
               the first run in, and the sheet it opens holds them all. With no
               number it never got a play at all (Jose, Sep 27, 2026: Allen's
               two rushing scores, no clip) */
            if (isNaN(need) && kind === "ATD") need = 1;
            var had = btn.querySelector(".ptdplay");
            /* No clip, no button. The summary already carries the scoring
               plays and the clip list, so whether THIS touchdown has one can
               be answered here without asking for anything more. */
            var pool = (card._clips || []).filter(function (c) {
              return ONEPLAY[(c.tracking || {}).coverageType] &&
                     ((c.links || {}).source || {}).href;
            });
            var mine = [];
            var whom = surnameKey(sd[0] === "l" ? card.dataset.lqb : card.dataset.rqb);
            (card._scoring || []).forEach(function (p) {
              var t = scoreLine(p.text, whom, kind);
              if (t) mine.push(t);
            });
            var td = mine[need - 1];
            var ord = { first: 1, "1st": 1, second: 2, "2nd": 2,
                        third: 3, "3rd": 3, fourth: 4, "4th": 4 };
            var any = !!(td && (nflRow(card.dataset.espn, td.text) ||
                                xRow(card.dataset.espn, td.text) ||
                                clubRow(card.dataset.espn, td.text) || pool.some(function (c) {
              var h = (c.headline || "").toLowerCase();
              if (h.indexOf(td.man) >= 0) return true;
              /* a clip writes him as the broadcast says him -- "Pat Mahomes",
                 not "Patrick" -- so a rushing score matches on the surname and
                 the word for the run (Jose, Sep 17, 2026) */
              if (td.run && h.indexOf(surnameKey(td.scorer)) >= 0 &&
                  /\brush|\brun|\bscramble|\bkeeper/.test(h)) return true;
              if (h.indexOf(td.qb) >= 0 &&
                  new RegExp("\\b" + td.yds + "\\b").test(h)) return true;
              if (h.indexOf(td.qb) < 0) return false;
              var o = /\b(first|1st|second|2nd|third|3rd|fourth|4th)\b[^.]{0,18}\btd\b/.exec(h);
              return !!o && ord[o[1]] === need;
            })));
            btn.dataset.why = pane.dataset.why = isNaN(need) ? "no need" : !(v >= need) ? "count " + v + " < " + need
              : !td ? "no play #" + need + " of " + mine.length + " (scoring " + ((card._scoring || []).length) + ")"
              : !any ? "no clip for " + td.text.slice(0, 30) + " (pool " + pool.length + ", x " + (xRow(card.dataset.espn, td.text) ? 1 : 0) + ")"
              : !covered(card, sd[0]) ? "not covered (" + (CFBCOVER ? "list" : "no list") + ")" : "ok";
            var ballEl = btn.querySelector(".ntick.ball");
            if (isNaN(need) || !(v >= need) || !any || !covered(card, sd[0])) {
              if (had) had.parentNode.removeChild(had);
              if (ballEl) ballEl.classList.remove("ball--clip");
              return;
            }
            if (had) return;
            /* the ball is the clip: it gets a ring and a tap on it plays. The
               button below still exists (hidden) and does the work. (Jose, Sep 16, 2026) */
            if (ballEl && !ptd.classList.contains("ptdx--run")) ballEl.classList.add("ball--clip");
            var go = document.createElement("button");
            go.className = "ptdplay";
            go.type = "button";
            go.setAttribute("aria-label", "Game highlights");
            go.innerHTML = '<svg aria-hidden="true"><use href="#play"/></svg>';
            go.addEventListener("click", function (e) {
              e.preventDefault();
              e.stopPropagation();
              var qb = sd[0] === "l" ? card.dataset.lqb : card.dataset.rqb;
              openTdSheet(card, qb, kind);
            });
            btn.appendChild(go);
          });

          pane.classList.toggle("has-play", !!pane.querySelector(".ptdplay"));

          var chip = ptd.querySelectorAll(".ptdcount")[sd[1]];
            if (chip) {
              chip.textContent = v;
              chip.classList.toggle("hit", v >= over);
            }
            var second = ptd.classList.contains("ptdx--v2");
            var tk = pane.querySelector(".tick");
            if (tk) tk.classList.toggle("hit", v >= over);
            if (second) {
              pane.querySelectorAll(".ntick").forEach(function (nt) {
                /* a number on the bar carries it as text; a football carries
                   it in its class, having no text of its own */
                var cls = (nt.className.baseVal || nt.className || "").toString();
                var m = cls.match(/ntick--n(\d+)/);
                var n = m ? parseInt(m[1], 10) : parseInt(nt.textContent, 10);
                if (isNaN(n)) return;
                var got = v >= n ? true : (done ? false : null);
                nt.classList.toggle("hit", got === true);
                nt.classList.toggle("miss", got === false);
              });
            }
            pane.querySelectorAll(".ptdbtn").forEach(function (b) {
              /* the rushing row carries one rung only, so its second chip has no
                 line to read -- reading it blind threw and killed the row, which
                 is why a scored rushing touchdown went unticked (Jose, Sep 17, 2026) */
              var ln0 = b.querySelector(".ptdline");
              if (!ln0) return;
              var need = parseInt(ln0.textContent, 10);
              var cell = b.querySelector(".price") ? b : null;
              if (!cell) return;
              var old = b.querySelector(".mk");
              if (old) old.parentNode.removeChild(old);
              var hit = v >= need ? true : (done ? false : null);
              var line = b.querySelector(".ptdline");
              /* in the second cut the bar's own numbers carry the result */
              if (second) return;
              if (hit === null) return;
              var m = document.createElement("span");
              m.className = "mk " + (hit ? "ok" : "no");
              m.innerHTML = hit ? CHECK : CROSS;
              line.appendChild(m);
            });
          });
        });

        /* the bars fill as the game runs, so a .hit only means "ahead right
         now" -- Mahomes leading 9-0 in the first is not a card that paid.
         Nothing has paid until the game is over. */
      if (done) {
        showHitsLater(card);
      } else {
        var hbox = card.querySelector(".hits");
        if (hbox) { hbox.hidden = true; hbox.innerHTML = ""; }
      }
        var clubs = card.querySelectorAll(".gteam");
        if (clubs.length === 2 && done && lside && rside) {
          stamp(clubs[0], lside.winner === true, false);
          stamp(clubs[1], rside.winner === true, true);
        }
        [["1+ PTD", 1, "ptd"], ["2+ PTD", 2, "ptd"],
         ["ATD", 1, "td"], ["2+ TDS", 2, "td"]].forEach(function (spec) {
          var cells = rowCells(card, spec[0]);
          if (!cells) return;
          [["l", 0], ["r", 1]].forEach(function (side) {
            var mine = stats[side[0]];
            if (!mine) return;
            var v = mine[spec[2]];
            if (v === null || v === undefined || isNaN(v)) return;
            if (v >= spec[1]) mark(cells[side[1]], true);
            else if (done) mark(cells[side[1]], false);
          });
        });
        /* last, so it seats the numbers the pass has just written and the bar
           it has just painted, rather than being painted over */
        stateV3(card);
        if (typeof placedState === "function") placedState(card);
      })
      .catch(function () { /* a board that cannot reach ESPN still shows its prices */ });
  }

  /* Reading the graph: the nearest play to the finger, from whatever the
     live pass last fetched. A chart with no series yet simply does nothing. */
  function wireRead(card) {
    var svg = card.querySelector(".wpx > svg");
    if (!svg || svg.dataset.wired) return;
    svg.dataset.wired = "1";
    var cur = document.createElementNS("http://www.w3.org/2000/svg", "line");
    cur.setAttribute("stroke", "#ffffff");
    cur.setAttribute("stroke-width", "1");
    cur.setAttribute("vector-effect", "non-scaling-stroke");
    cur.setAttribute("y1", "0");
    cur.setAttribute("y2", "110");
    cur.style.display = "none";
    var dot = document.createElementNS("http://www.w3.org/2000/svg", "circle");
    dot.setAttribute("r", "4");
    dot.setAttribute("fill", "#ffffff");
    dot.style.display = "none";
    svg.appendChild(cur);
    svg.appendChild(dot);
    var play = document.createElement("div");
    play.className = "wpplay";
    svg.parentNode.parentNode.insertBefore(play, svg.parentNode.nextSibling);

    function read(ev) {
      var pts = card._wp;
      if (!pts || !pts.length) return;
      var r = svg.getBoundingClientRect();
      var cx = (ev.touches ? ev.touches[0].clientX : ev.clientX) - r.left;
      var x = Math.max(0, Math.min(300, cx / r.width * 300));
      var near = pts[0];
      pts.forEach(function (p) { if (Math.abs(p.x - x) < Math.abs(near.x - x)) near = p; });
      cur.setAttribute("x1", near.x);
      cur.setAttribute("x2", near.x);
      cur.style.display = "";
      dot.setAttribute("cx", near.x);
      dot.setAttribute("cy", near.y);
      dot.style.display = "";
      var reads = card.querySelectorAll(".wpbig");
      if (reads.length === 2) {
        reads[0].textContent = near.l.toFixed(1) + "%";
        reads[1].textContent = (100 - near.l).toFixed(1) + "%";
      }
      play.innerHTML = near.t
        ? "<b>" + (near.q ? "Q" + near.q + " " : "") + (near.c || "") + "</b> " +
          (near.d ? "· " + near.d + " " : "") + "<br>" + near.t
        : "";
      if (ev.cancelable) ev.preventDefault();
    }
    svg.addEventListener("pointermove", read);
    svg.addEventListener("pointerdown", read);
    svg.addEventListener("pointerleave", function () {
      cur.style.display = "none";
      dot.style.display = "none";
      play.innerHTML = "";
      if (card._last !== undefined) {
        var reads = card.querySelectorAll(".wpbig");
        if (reads.length === 2) {
          reads[0].textContent = card._last.toFixed(1) + "%";
          reads[1].textContent = (100 - card._last).toFixed(1) + "%";
        }
      }
    });
  }

  /* ---- Boxing, entered by hand ----
     ESPN publishes no boxing API at all — every endpoint returns nothing or
     an error — so a major fight is settled from a result written here when it
     happens. Winner is a surname, method is KO / SUB / DEC. */
  var BOXING = {
    "garcia-benn": { winner: "Garcia", method: "KO", round: 2 }
  };

  function settleBoxing() {
    document.querySelectorAll(".gcard[data-fight]").forEach(function (card) {
      var r = BOXING[card.dataset.fight];
      if (!r || !r.winner) return;
      card.classList.add("locked");
      card.querySelectorAll("button.price").forEach(function (b) { shutPrice(b); });
      settleFight(card, r.winner, r.method);
    });
  }

  /* ---- The fights, off ESPN's MMA board ----
     One request covers every bout on the card. A finished bout gives the
     winner in competitors[].winner and how he won in details[], written
     "Unofficial Winner Decision" / "Kotko" / "Submission". */
  var MMA = "https://site.web.api.espn.com/apis/site/v2/sports/mma/ufc/scoreboard";

  function wonBy(how, market) {
    var k = (how || "").toLowerCase();
    var ko = k.indexOf("ko") === 0 || k.indexOf("tko") >= 0;
    var sub = k.indexOf("sub") >= 0;
    var dec = k.indexOf("dec") >= 0;
    if (market === "KO") return ko;
    if (market === "SUB") return sub;
    if (market === "DEC") return dec;
    if (market === "FIN") return ko || sub;
    if (market === "DEC/SUB") return dec || sub;
    if (market === "KO/SUB") return ko || sub;
    return null;
  }

  function surname(n) {
    return (n || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "")
      .trim().split(" ").pop().toLowerCase();
  }

  function settleFight(card, winner, how) {
    var lf = surname(card.dataset.lf), rf = surname(card.dataset.rf);
    var w = surname(winner);
    var leftWon = w && w === lf, rightWon = w && w === rf;
    var drawn = !w && /draw/i.test(how || ""), nc = !w && /no contest/i.test(how || "");

    var clubs = card.querySelectorAll(".ghead .gteam");
    if (clubs.length === 2) {
      stamp(clubs[0], nc ? "nc" : drawn ? "draw" : leftWon, false);
      stamp(clubs[1], nc ? "nc" : drawn ? "draw" : rightWon, true);
      /* the frame the mock puts round the half that won, and the one that
         lost -- a draw or a no contest frames neither */
      /* the settle can land before the card has been laid out, so the classes
         go on regardless -- the frame itself is scoped to a bout card in CSS
         (Jose, Sep 22, 2026) */
      {
        [[clubs[0], leftWon], [clubs[1], rightWon]].forEach(function (q) {
          q[0].classList.toggle("gside--drew", !!drawn);
          q[0].classList.toggle("gside--nc", !!nc);
          q[0].classList.toggle("gside--won", !drawn && !nc && !!w && !!q[1]);
          q[0].classList.toggle("gside--lost", !drawn && !nc && !!w && !q[1]);
        });
      }
    }
    /* the rail is drawn again once the result is known: another path may have
       flagged the bout settled before the one carrying the method ran, which
       left the fill standing with no mark on it (Jose, Sep 22, 2026) */
    var bar0 = card.querySelector(".frail__bar");
    if (bar0 && card._how) {
      var pct0 = card._railPct;
      if (typeof pct0 === "number") fillRail(bar0, { how: card._how }, "post", card._how.round || 1, pct0);
    }
    card.querySelectorAll(".grow").forEach(function (row) {
      var lab = row.querySelector(".gmk");
      if (!lab) return;
      var by = wonBy(how, lab.textContent.trim());
      if (by === null) return;
      var cells = row.querySelectorAll(".gcell");
      if (cells[0]) mark(cells[0], !!(leftWon && by));
      if (cells[1]) mark(cells[1], !!(rightWon && by));
    });
  }

  /* the sheet's method rows: every price the result paid turns green.
     how: theScore's words ("Unanimous Decision", "Submission", "KO/TKO")
     or ESPN's ("Kotko", "Decision"); a draw or no contest pays nothing.
     The round and the clock settle the rest -- which round it ended in, and
     whether it ended inside the first minute or the last ten seconds of a
     round (Jose, Sep 18, 2026). */
  /* What a result won, market by market, for EVERY market the bout's file
     holds -- not a list picked by hand. paidMethods uses it to colour the
     sheet and boutPaid to find the best price, so the two can never disagree
     (Jose, Sep 22, 2026: "it should be automated based on what the results
     were and what is in the modal"). */
  function boutWon(card, winner, how, round, clock) {
    var k = (how || "").toLowerCase();
    var ko = k.indexOf("ko") >= 0 || k.indexOf("knockout") >= 0 || k.indexOf("dq") >= 0;
    var sub = k.indexOf("sub") >= 0;
    var dec = k.indexOf("dec") >= 0 || k === "ud" || k === "md" || k === "sd";
    var ud = dec && (k.indexOf("unanimous") >= 0 || k === "ud");
    var sdmd = dec && (k.indexOf("split") >= 0 || k.indexOf("majority") >= 0 || k === "sd" || k === "md");
    var rn = parseInt(round, 10) || 0;
    var secs = -1, mm = /^(\d+):(\d\d)$/.exec(String(clock || "").trim());
    if (mm) secs = parseInt(mm[1], 10) * 60 + parseInt(mm[2], 10);
    var fin = ko || sub;
    var w = surname(winner);
    var side = w && w === surname(card.dataset.lf) ? 0
             : w && w === surname(card.dataset.rf) ? 1 : -1;
    var MAN = { ml: 1, ko: ko, sub: sub, dec: dec, kosub: fin, finish: fin,
                kodec: ko || dec, subdec: sub || dec, koonly: ko, subonly: sub,
                deconly: dec, finishonly: fin, cards: dec, ud: ud, sdmd: sdmd,
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
    var nr = (FPROPS[card.dataset.bout] || {}).rounds || 3;
    MAN.rdlastdec = dec || (fin && rn === nr);
    return { MAN: MAN, FIGHT: FIGHT, side: side };
  }
  /* the sheet is lifted onto the body while it is open, so a bout that ends
     with its sheet up had nothing under the card to mark: the prices that
     paid stayed white until the sheet was shut and opened again. The rows
     are looked for in both places (Jose, Sep 22, 2026: "shabazayan i still
     see gold"). */
