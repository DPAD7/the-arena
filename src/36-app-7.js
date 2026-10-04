  function nextLook() {
    var now = Date.now(), soonest = Infinity, live = false;
    document.querySelectorAll(".board:not([hidden]) .gcard, .hidebox .gcard").forEach(function (c) {
      if (c.classList.contains("done") || c.dataset.settled === "1" ||
          c.dataset.settledBout === "1") return;
      var k = c.dataset.kick ? Date.parse(c.dataset.kick) : 0;
      if (c.classList.contains("live") || c.querySelector(".glivebar") || (k && k <= now)) { live = true; return; }
      if (k) soonest = Math.min(soonest, k);
    });
    /* ten seconds while something is being played, not thirty. A knockout
       lands on any second and the card should stop saying LIVE on the same
       breath ESPN says final -- the same beat watch.py keeps on the machine
       (Jose, Sep 22, 2026: "it shouldn't be taking 30 seconds") */
    if (live) return LIVESOCK ? 120000 : 10000;
    if (soonest === Infinity) return 0;
    return Math.max(60000, Math.min(soonest - 20 * 60000 - now, 5 * 60000));
  }
  /* live without asking: while the page is open, the clock sends the games
     whose score, clock or down just moved, and only those cards are read
     again. The ten-second look stays only as a two-minute backstop while the
     line is up (Jose, Sep 29, 2026) */
  var LIVESOCK = null;
  function liveLine() {
    if (LIVESOCK || document.hidden || !window.WebSocket) return;
    try { LIVESOCK = new WebSocket(location.origin.replace(/^http/, "ws") + "/live"); } catch (e) { LIVESOCK = null; return; }
    LIVESOCK.onmessage = function (e) {
      var j = {}; try { j = JSON.parse(e.data); } catch (err) {}
      (j.changed || []).forEach(function (id) {
        document.querySelectorAll('.gcard[data-espn="' + id + '"]').forEach(function (c) { refresh(c); });
      });
      if ((j.changed || []).length) { setTimeout(sinkDone, 1200); setTimeout(placedState, 1400); if (typeof bankDraw === "function") bankDraw(); }
      /* a bout moved: the fight cards read again at once */
      if ((j.bouts || []).length && typeof refreshFights === "function") { refreshFights(); if (typeof bankDraw === "function") bankDraw(); }
    };
    LIVESOCK.onclose = function () { LIVESOCK = null; if (window.lookAgain) window.lookAgain(); };
  }
  liveLine();
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) { if (LIVESOCK) { try { LIVESOCK.close(); } catch (e) {} LIVESOCK = null; } }
    else liveLine();
  });
  function refreshVisible() {
    var now = Date.now(), soon = now + 8 * 86400000;
    document.querySelectorAll(".board:not([hidden]) .gcard[data-espn], .hidebox .gcard[data-espn]")
      .forEach(function (card) {
        var k = card.dataset.kick ? Date.parse(card.dataset.kick) : 0;
        if (k && k > soon) return;
        refresh(card);
      });
  }
  refreshVisible();
  refreshFights();
  settleBoxing();
  /* what the other devices left (Jose, Sep 19, 2026) */
  if (typeof pullState === "function") pullState();
  /* One rule, one place. Whatever adds a card -- the first render, a week
     change, a sport change, a card coming back out of the hide shelf -- it
     is colored here, so no two paths can disagree about a club again. */
  function paintCard(c) {
    dressClub(c); dressFaces(c); paintSides(c); layoutV3(c); layoutBout(c);
    seatRecord(c);
    if (typeof markBoutWay === "function") markBoutWay(c);
    if (typeof seatClubRec === "function") seatClubRec(c);
    if (typeof seatHurt === "function") seatHurt(c);
    if (typeof seatBday === "function") seatBday(c);
    if (typeof seatWant === "function") seatWant(c);
    if (typeof seatTrend === "function") seatTrend(c);
    if (typeof seatTicket === "function") seatTicket(c);
    if (typeof seatTrack === "function") seatTrack(c);
    if (typeof orderTop === "function") orderTop(c);
    if (typeof pullCard === "function") pullCard(c);
  }
  function paintAll(root) {
    (root || document).querySelectorAll(".gcard").forEach(paintCard);
  }
  paintAll();
  /* asked for on the way in, whichever board is open, because every card's
     top corner needs it -- not just the Form tab's rows */
  if (sport !== "form") loadLedger(ledgerLanded);
  new MutationObserver(function (recs) {
    var touched = false;
    recs.forEach(function (r) {
      [].forEach.call(r.addedNodes, function (n) {
        if (n.nodeType !== 1) return;
        /* the same seven steps as paintAll, by calling it rather than by
           copying it: this branch was a hand-written copy that had fallen four
           steps behind, so a card added on its own got its layout and no
           record at all (Jose, Sep 22, 2026) */
        if (n.classList && n.classList.contains("gcard")) { paintCard(n); touched = true; }
        else if (n.querySelector && n.querySelector(".gcard")) { paintAll(n); touched = true; }
      });
    });
    return touched;
  }).observe(document.body, { childList: true, subtree: true });
  /* the form and money pages keep step with the cards: every thirty seconds,
     the same as the board (Jose, Sep 17, 2026) */
  function formLive() {
    if (sport !== "form" || !LEDGER) return;
    var rows = [];
    Object.keys(LEDGER).forEach(function (w) {
      (LEDGER[w] || []).forEach(function (r) {
        rows.push({ game: r[8], id: r[2], score: r[10], ml: r[6] });
      });
    });
    liveWeek(rows, function () {
      if (sport === "form") { if (formWeek === "season") renderMoney(); else renderForm(); }
    });
  }
  setInterval(formLive, 30000);
  /* the games' beat: as often as nextLook() says, and when it says stop, a
     look at the board every five minutes with no reading behind it, so a tab
     change or a new day picks the beat back up */
  (function gameTicking() {
    var at = 0;
    var beat = function () {
      var want = nextLook();
      clearTimeout(at);
      at = setTimeout(function () {
        if (nextLook()) { refreshVisible(); setTimeout(sinkDone, 1200); setTimeout(placedState, 1400); }
        beat();
      }, want || 5 * 60000);
    };
    beat();
    window.lookAgain = beat;
  })();
  /* While a bout is actually being fought the board asks every five seconds
     instead of every thirty. ESPN's feed is entered cageside, so it runs
     ahead of a stream, which is half a minute or more behind; on a thirty
     second tick the board threw that lead away (Jose, Sep 19, 2026: "can we
     get the speed on the site?"). Nothing else changes: between fights, and
     on a tab he is not looking at, it goes back to thirty. */
  (function fightTicking() {
    var at = 0;
    var anyLive = function () {
      if (document.hidden) return false;
      return !![].slice.call(document.querySelectorAll(".gcard[data-bout]"))
        .filter(function (c) { return c.classList.contains("live"); }).length;
    };
    /* five seconds while a bout is on; otherwise the games' rule: wait for
       the next first bell, and once the last bout is over, nothing -- a look
       at the board every five minutes and no reading behind it */
    var beat = function () {
      var look = nextLook();
      var want = anyLive() ? 5000 : (look || 5 * 60000);
      clearTimeout(at);
      at = setTimeout(function () { if (anyLive() || nextLook()) refreshFights(); beat(); }, want);
    };
    beat();
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) { refreshFights(); beat(); }
    });
  })();
  /* the scores looked after themselves but the prices did not: they were read
     once at load, so a board left open all afternoon still showed the morning's
     numbers and only a reload moved them. They are asked for every minute now,
     and again the moment the tab is looked at, which is when a phone comes back
     out of a pocket (Jose, Sep 19, 2026: "so I don't have to refresh my page") */
  /* a placed price goes green the moment the man reaches its rung, rather
     than waiting for the game to settle. The counts are already on the card:
     each touchdown row carries the live number for each man, and the button
     says which rung it is. Johnson ran one in and his price stayed gold
     (Jose, Sep 19, 2026) */
  function placedState(root) {
    (root || document).querySelectorAll(".ptdrow").forEach(function (row) {
      var boxes = row.querySelectorAll(".trkbox");
      if (boxes.length < 2) return;
      var n = [parseInt(boxes[0].textContent, 10), parseInt(boxes[1].textContent, 10)];
      row.querySelectorAll("button.price.placed").forEach(function (b) {
        var m = /ptdbtn--n(\d)/.exec((b.parentElement || {}).className || "");
        if (!m) return;
        var side = b.closest(".ptdside--r") ? 1 : 0;
        if (isNaN(n[side])) return;
        var got = n[side] >= +m[1];
        var over = !!b.closest(".gcard.done");
        b.classList.toggle("won", got);
        b.classList.toggle("lost", over && !got);
      });
    });
  }
  /* it ran every five seconds all day for something that only changes when a
     count does. It is called where the counts are written instead
     (Jose, Sep 22, 2026) */
  placedState();
  /* the build this page was served as. site/build.txt carries the same stamp,
     so a page left open can tell when a new one has been deployed and take
     it, rather than sitting on old code until somebody reloads by hand */
  var BUILT = "__BUILD__";
  /* the stamp of the data the page was built with: new prices alone never
     reload a page he is looking at (Sep 29, 2026) */
  var BUILTD = "__DATA__";
  var LASTTOUCH = Date.now();
  /* a swipe along a card row is him using the board as much as a scroll down
     the page is. A scroll on an element does not reach the window, so it is
     caught on the way down instead -- without this the board waited out its
     idle count while he was swiping and then moved the row under him
     (Jose, Sep 19, 2026: "it's still jumping to Clemson") */
  ["scroll", "wheel", "pointerdown", "touchstart", "touchmove", "keydown"].forEach(function (ev) {
    document.addEventListener(ev, function () { LASTTOUCH = Date.now(); },
                              {passive: true, capture: true});
  });
  /* Whether he is in the middle of something the board must not move under.
     An open sheet is the case that bit: a rebuild takes the card's own dialog
     out of the document with it, which closes the sheet he was reading, and
     the version check a moment later then sees no open dialog and reloads.
     He was in another browser tab, so both gates read the page as idle and
     both fired (Jose, Sep 19, 2026: "i was in a modal and it reloaded").
     Being in another tab is not permission to throw his place away. */
  function busy() {
    /* the wallet, the search and the betslip are not dialogs, and a reload
       closed each of them under him (Jose, Sep 29, 2026) */
    var cash = document.getElementById("cashsheet"), qs = document.getElementById("qsearch");
    return !!document.querySelector("dialog[open]") || !!(cash && !cash.hidden) ||
           !!(qs && qs.classList.contains("open")) || document.documentElement.classList.contains("cashlock") ||
           /* a wallet refresh under way, or its green, grey or red still up:
              a reload took it just as the fill reached the top (Jose, Sep 29,
              2026: "I can never see if it checks out") */
           !!document.querySelector("#cashfab .wal.filling, #cashfab .wal.pop, #cashfab .wal.sink");
  }
  var AWAY = 0;        /* when the page went into the background, 0 while seen */
  /* Where he was reading, written on the way out. A phone throws away a tab
     it has not seen for a while and loads the page again by itself when he
     comes back -- nothing here asked for that and nothing here can stop it,
     and it is what actually put him back at the top of the home tab. So the
     place is kept whenever the page is put away, and taken up again by
     whatever loads next, whether that is this page's doing or the browser's
     (Jose, Sep 19, 2026: "i was in a modal and it reloaded"). */
  function keepPlace() {
    try {
      sessionStorage.setItem("arena.at", String(window.scrollY));
      sessionStorage.setItem("arena.sp", String(sport || ""));
    } catch (e) {}
  }
  window.addEventListener("pagehide", keepPlace);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden) keepPlace();
  });
  window.busy = busy;
  /* a new version is read from the network, never from the copy the phone
     keeps (?v= tells the service worker so), and asked for once: if it comes
     back the same, it is not asked again this session */
  function freshPage(v) {
    var tried = "";
    try { tried = sessionStorage.getItem("arena.tried") || ""; sessionStorage.setItem("arena.tried", v); } catch (e) {}
    if (tried === v) return;
    location.replace(location.pathname + "?v=" + encodeURIComponent(v) + location.hash);
  }
  if (/[?&]v=/.test(location.search)) history.replaceState(null, "", location.pathname + location.hash);
  function watchBuild() {
    fetch("build.txt", {cache: "no-store"})
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (v) {
        if (!v) return;
        /* two stamps: the code's, then the data's */
        var two = v.trim().split(/\s+/);
        v = two[0];
        /* the injury report and lineups, read again only when the sweep has
           written new ones */
        if (two[2] && two[2] !== watchBuild.files) {
          if (watchBuild.files && typeof window.alertsPull === "function") window.alertsPull();
          watchBuild.files = window.FILESTAMP = two[2];
        }
        /* the same code with new prices: taken only while the page is put
           away, so it is there when he comes back and never under his thumb */
        if (v === BUILT && two[1] && /^\d{14}$/.test(BUILTD) && two[1] !== BUILTD) {
          if (!document.hidden || busy()) return;
          keepPlace();
          try { sessionStorage.setItem("arena.quiet", "1"); } catch (e) {} freshPage(two.join("-"));
          return;
        }
        /* deployable() stamps the page by replacing every __BUILD__ in it,
           and this line used to compare against one of them -- so once built
           the test read BUILT === BUILT and the version check returned every
           single time. It never fired on any deployed build. A stamp is
           fourteen digits and the placeholder is not, so the shape decides
           it and nothing here can be rewritten out from under it. */
        if (!/^\d{14}$/.test(BUILT) || v === BUILT) return;
        /* A new version is never taken while he is reading. It waits for the
           page to be put away, or for five quiet minutes, because a reload in
           the middle of a scroll throws him back up the board -- ten deploys
           in an hour meant ten jumps (Jose, Sep 19, 2026: "the page is
           jumping, soooo annoying") */
        if (busy()) return;
        /* A page he is looking at never refreshes itself. No scores site or
           book does that, and it is not needed here: prices, marks, scores,
           clocks and finished games are all written onto the board where it
           stands. The only thing a reload buys is new code, which is a thing
           I ship, not a thing the board learns -- so it waits until the page
           is not the one in front of him (Jose, Sep 19, 2026: "a rebuild
           refreshes the page, that doesn't happen on stats sites").

           Five minutes in the background, and then it comes back on the tab
           and at the place he left, so returning to it looks like nothing
           happened. */
        /* A new build is taken the moment it lands, open or not. Holding it
           back meant he pushed a deploy and then looked at the old page --
           for hours, on a night of deploys every few minutes
           (Jose, Sep 22, 2026: "why am I pushing deployments if it takes so
           long to see it?"). He is put back exactly where he was reading, so
           the board does not jump; that was the worry the hold was for. */
        AWAY = 0;
        /* where he was, so the new version opens on it rather than at home */
        try {
          sessionStorage.setItem("arena.at", String(window.scrollY));
          sessionStorage.setItem("arena.sp", String(sport || ""));
        } catch (e) {}
        try { sessionStorage.setItem("arena.quiet", "1"); } catch (e) {} freshPage(two.join("-"));
      })
      .catch(function () {});
  }
  /* every ten minutes while it is open, and on coming back to it: the board
     changes no faster than the ten-minute tick that writes it, so asking any
     oftener only finds the same stamp (Jose, Sep 29, 2026: "why do we need to
     check so often") */
  setInterval(watchBuild, 600000);
  document.addEventListener("visibilitychange", function () { if (document.visibilityState === "visible") watchBuild(); });
  /* back to where he was reading, after a version change took the page */
  (function () {
    var at = 0, sp = "";
    try {
      at = parseInt(sessionStorage.getItem("arena.at") || "0", 10) || 0;
      sp = sessionStorage.getItem("arena.sp") || "";
    } catch (e) {}
    try {
      sessionStorage.removeItem("arena.at");
      sessionStorage.removeItem("arena.sp");
    } catch (e) {}
    /* the pill is pressed rather than the variable set, so the reload goes
       through the same switch a tap does and nothing is kept in two places */
    if (sp && sp !== sport) {
      var pill = document.querySelector('#sportbar .sptab[data-sp="' + sp + '"]');
      if (pill) pill.click();
    }
    if (!at) return;
    /* the tab he was on is pressed first and that draws its own board, so the
       place is put back after that render rather than before it -- three
       tries inside a second and a half all landed while the old board was
       still up, and he came back to the top (Sep 19, 2026) */
    var mine = false;
    ["touchstart", "wheel", "keydown"].forEach(function (ev) {
      addEventListener(ev, function () { mine = true; }, { passive: true, capture: true, once: true });
    });
    var put = function () {
      /* the moment he scrolls himself, the page stops putting him anywhere
         (Jose, Sep 28, 2026: "if I'm scrolling it's cause I wanna scroll") */
      if (mine) return;
      if (Math.abs(window.scrollY - at) < 4) return;
      if (document.body.scrollHeight < at) return;   /* not drawn that far yet */
      window.scrollTo(0, at);
    };
    [300, 900, 1800, 3000, 4500, 6000].forEach(function (ms) { setTimeout(put, ms); });
  })();
  document.addEventListener("visibilitychange", function () {
    /* coming back to the tab is the moment to take a new version: he is not
       mid-scroll, and the page he left is the page he expects to see move */
    if (document.visibilityState !== "visible") return;
    /* he is back and looking at it, so this is the last moment to reload it:
       take the fresh numbers, leave the version alone */
    AWAY = 0;
    LASTTOUCH = 0;
    pullState();
    pullPrices();
    setTimeout(function () { LASTTOUCH = Date.now(); }, 1500);
  });
  /* No timer. A card's prices are read once, when it is drawn, and that is
     the end of it -- the sweep is what moves them, and it is scheduled. The
     board was re-fetching every event on it every sixty seconds, nearly all of
     them finished and unable to change (Jose, Sep 22, 2026: "this one min
     shit is dumb"). */
  setInterval(pullLedger, 60000);
  /* the marks were only read when the page loaded, so a bet marked from
     another device never arrived until he reloaded. They are asked for on the
     same beat as the prices, and the gold lands without a rebuild
     (Jose, Sep 19, 2026: "I don't see it, so I have to refresh?") */
  setInterval(function () { pullState(); }, 60000);
  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState !== "visible") return;
    pullPrices();
    pullLedger();
    refreshVisible();
    refreshFights();
  });
  document.getElementById("weekbar").addEventListener("click", function () { setTimeout(refreshVisible, 50); });
  /* ---- the balance behind the dollar button ----
     It starts at $300, and the $100 unit comes out of it when the day's legs
     go gold, the way DraftKings keeps it. The legs are the prices wearing a gold
     edge, drawn as the slip draws its parlay card; each tile goes green as
     its leg lands and red if it cannot. When every leg has landed the whole
     return goes on -- the unit back and what it won -- and a miss changes
     nothing, the unit being gone already. Once per run of legs, kept in the
     store so every device agrees
     (Jose, Sep 25, 2026). */
  var BANKKEY = "arena.bank.v1", UNIT = 100;
  /* false until this device has read the store once: a new browser starts
     at $300 and must never push that over the real balance (Sep 25, 2026) */
  var BANKMET = false;
  var BANK = null;
  try { BANK = JSON.parse(localStorage.getItem(BANKKEY) || "null"); } catch (e) { BANK = null; }
  if (!BANK || BANK.bal == null) BANK = {bal: 300, legs: {}, paid: {}};
  BANK.legs = BANK.legs || {}; BANK.paid = BANK.paid || {};
  function bankKeep() { try { localStorage.setItem(BANKKEY, JSON.stringify(BANK)); } catch (e) {} }
  function money(n) { return "$" + (Math.round(n * 100) / 100).toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}); }
  /* ---- DraftKings' own numbers, from the Arena DK Bets extension ----
     The book fills at whatever it shows when the slip goes in, and the board
     only knew the price it had when a price was marked: Army -198 here, -192
     on the slip, $2.79 short (Jose, Sep 26, 2026: "math is off"). A sync from
     My Bets (tools/dk-bets) is the truth: its balance is the balance, its
     fills are the legs' prices, and a day it has settled is not paid twice. */
  var DKB = null, DKB_T = 0;
  function dkDay(placed) {
    var m = /([A-Z][a-z]{2})[a-z]* (\d{1,2}), (\d{4})/.exec(placed || "");
    if (!m) return "";
    var mo = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"].indexOf(m[1]);
    if (mo < 0) return "";
    return dayKeyOf(new Date(Date.UTC(+m[3], mo, +m[2], 16)).toISOString());
  }
  /* every leg of an open slip is gold on its card, every time the panel
     draws -- not only when a sync lands, which a reload lost -- and saved so
     the other devices see it (Jose, Sep 26, 2026: "why isn't it
     highlighting") */
  function dkGold() {
    if (!DKB || !DKB.bets) return;
    var added = false;
    DKB.bets.forEach(function (bet) {
      (bet.legs || []).forEach(function (lg) {
        if (!lg.sel) return;
        if (!(lg.sel in placed)) { placed[lg.sel] = true; added = true; }
        if (!placed[lg.sel]) return;                 /* taken off by hand */
        document.querySelectorAll("button.price[data-oid]").forEach(function (b) {
          if (b.dataset.oid === lg.sel && !b.classList.contains("placed")) b.classList.add("placed");
        });
      });
    });
    if (added) {
      try { localStorage.setItem(PLACEDKEY, JSON.stringify(placed)); } catch (e) {}
      if (typeof placedState === "function") placedState();
      if (typeof pushState === "function") pushState();
    }
  }
  var bankFix = false;
  function dkApply() {
    /* the book's balance is the balance, every time it is read -- a unit taken
       off before the read landed stayed off, and the wallet said $150.22 with
       $250.22 on DraftKings (Jose, Sep 28, 2026) */
    var wal = DKB && DKB.wallet;
    /* no balance set yet: the tracked slips still count from nothing, so a
       win shows as money in (Oct 3, 2026: $0.00 after an $810 win) */
    if ((!wal || typeof wal.bal !== "number") && DKB && (DKB.sent || []).length && !(typeof DKB.balance === "number")) wal = { bal: 0, at: 0 };
    if (wal && typeof wal.bal === "number" && wal.at >= (DKB.bookAt || 0)) {
      var b0 = wal.bal;
      (DKB.sent || []).forEach(function (bet) {
        if ((Date.parse(bet.placed) || 0) < wal.at) return;
        b0 -= bet.wager || 0;
        var legs = bet.legs || [];
        if (legs.length && legs.every(function (lg) { return (BANK.legs[lg.sel] || {}).st === "won" || (window.TRKST || {})[lg.sel] === "won"; })) b0 += bet.topay || 0;
      });
      b0 = Math.round(b0 * 100) / 100;
      if (BANK.bal !== b0) { BANK.bal = b0; bankFix = true; }
    } else if (DKB && typeof DKB.balance === "number" && BANK.bal !== DKB.balance) { BANK.bal = DKB.balance; bankFix = true; }
    if (!DKB || !DKB.at || (BANK.dkAt || 0) >= DKB.at) { var f0 = bankFix; bankFix = false; return f0; }
    BANK.out = BANK.out || {}; BANK.paid = BANK.paid || {};
    (DKB.bets || []).forEach(function (bet) {
      /* the sweep sends the book's own ISO time and selection ids; the
         extension sent the screen's words */
      var d = /^\d{4}-\d\d-\d\dT/.test(bet.placed || "") ? dayKeyOf(bet.placed) : dkDay(bet.placed);
      (bet.legs || []).forEach(function (lg) {
        var v = lg.sel && BANK.legs[lg.sel];
        if (v && lg.odds) v.o = String(lg.odds).replace("-", "\u2212");
      });
      if (!d) return;
      BANK.out[d] = 1;
      if (bet.status === "won" || bet.status === "lost") BANK.paid[d] = bet.status;
      /* each gold leg takes the price its slip filled at */
      (bet.legs || []).forEach(function (lg) {
        var pick = String(lg.pick || "").toLowerCase(), ml = /moneyline/i.test(lg.market || "");
        Object.keys(BANK.legs).forEach(function (id) {
          var v = BANK.legs[id], lab = String(v.l || "").split(" \u00b7 ")[0].toLowerCase();
          if (!lab || !pick || dayKeyOf(v.k || "") !== d) return;
          var mine = ml ? / ml$/.test(lab) && pick.indexOf(lab.replace(/ ml$/, "")) === 0 : false;
          if (mine && lg.odds) v.o = String(lg.odds).replace("-", "\u2212");
        });
      });
    });
    if (typeof DKB.balance === "number" && !(DKB.wallet && DKB.wallet.at >= (DKB.bookAt || 0))) BANK.bal = DKB.balance;
    BANK.dkAt = DKB.at;
    return true;
  }
  /* the double tap: ask the site to read the book now, then watch /bets
     until a sync newer than the ask lands -- the helmet's own way
     (Jose, Sep 26, 2026) */
  function dkFresh(done) {
    fetch("bets?k=" + encodeURIComponent(ARENAKEY), { method: "POST", cache: "no-store",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ pull: true }) })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || !j.asked) { done(false, false); return; }
        var t0 = Date.now(), tries = 0;
        (function look() {
          fetch("bets?k=" + encodeURIComponent(ARENAKEY), { cache: "no-store" })
            .then(function (r) { return r.json(); })
            .then(function (b) {
              /* a fresh sync wins: an expiry flagged by an older read never
                 turns a good one red (Jose, Sep 29, 2026) */
              if (b && b.at && b.at >= j.asked) { DKB = withSent(b); DKB_T = Date.now(); bankDraw(); done(true, true); return; }
              if (b && b.expired && b.expired >= j.asked && b.expired > (b.at || 0)) { done(false, false); return; }   /* login gone: red */
              if (++tries > 75 || Date.now() - t0 > 150000) { done(true, false); return; }
              if (done.step) done.step(Math.min(92, 20 + tries * 2));
              /* every two seconds: the green comes up as soon as the book's
                 answer lands, not up to five seconds after (Jose, Sep 28, 2026) */
              setTimeout(look, 2000);
            }).catch(function () { done(false, false); });
        })();
      }).catch(function () { done(false, false); });
  }
  window._dkFresh = dkFresh;
  /* the slips the board itself handed to DraftKings: kept by the site the
     moment "Add to betslip" is tapped, so the wallet tracks them with no
     DraftKings login at all (Jose, Oct 3, 2026: "the bets I build outside
     wouldn't be the bets we track"). A slip DraftKings' own read also
     carries, the same legs, is shown once, as DraftKings has it. */
  function withSent(j) {
    var bets = (j.bets || []).slice(), seen = {};
    bets.forEach(function (b) {
      seen[(b.legs || []).map(function (l) { return l.sel; }).sort().join("|")] = 1;
    });
    (j.sent || []).forEach(function (b) {
      var k = (b.legs || []).map(function (l) { return l.sel; }).sort().join("|");
      if (!seen[k]) bets.push(b);
    });
    var out = {};
    for (var key in j) out[key] = j[key];
    out.bets = bets;
    out.bookAt = j.at || 0;
    (j.sent || []).forEach(function (b) { var t = Date.parse(b.placed) || 0; if (t > (out.at || 0)) out.at = t; });
    if (j.wallet && j.wallet.at > (out.at || 0)) out.at = j.wallet.at;
    return out;
  }
  /* "Add to wallet": the slip's legs, the price DraftKings filled it at and
     the stake, confirmed by him, kept by the site; from then on the wallet
     tracks it and the balance moves with it (Jose, Oct 3, 2026: "add to
     betslip and add to wallet, then I confirm the balance one time") */
  function money0(v) { var n = parseFloat(String(v).replace(/[^0-9.\-]/g, "")); return isNaN(n) ? null : n; }
  function decOf(o) {
    var n = parseInt(String(o || "").replace(/\u2212|\u2013/g, "-").replace(/[^\-0-9]/g, ""), 10);
    return isNaN(n) || !n ? null : (n > 0 ? 1 + n / 100 : 1 + 100 / -n);
  }
  var PROMOS = [], BOOST = null, PROMOT = 0;
  function promoLoad() {
    if (Date.now() - PROMOT < 300000) return Promise.resolve();
    PROMOT = Date.now();
    return fetch("promos.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : []; })
      .then(function (j) { PROMOS = j || []; }).catch(function () { PROMOS = []; });
  }
  function sportOf(gid) {
    if ((typeof SCHED === "object" ? SCHED : []).some(function (r) { return String(r[1]) === String(gid); })) return "nfl";
    if ((typeof CFB === "object" ? CFB : []).some(function (r) { return String(r[1]) === String(gid); })) return "college-football";
    return "";
  }
  /* a boost fits a slip when it is running now, every leg is in its league
     (or on its one game), the slip has its fewest legs, and the price is at
     its minimum odds or longer */
  function boostsFor(legs, odds) {
    var now = Date.now(), d = decOf(odds), gids = legs.map(function (b) { return String(b.g || ""); });
    return PROMOS.filter(function (p) {
      if (Date.parse(p.start) > now || Date.parse(p.end) < now) return false;
      if (legs.length < (p.minLegs || 1)) return false;
      if (p.minOdds && d && d < decOf(p.minOdds)) return false;
      if (p.gid) return gids.every(function (g) { return g === String(p.gid); });
      if (p.sport) return gids.every(function (g) { return sportOf(g) === p.sport; });
      return false;
    }).sort(function (a, b) { return (b.gid ? 1 : 0) - (a.gid ? 1 : 0) || b.pct - a.pct; });
  }
  /* the slip's foot, the way DraftKings' reads: the price, the stake chips
     and the amount (the keypad only when the amount is tapped), a boost only
     when one fits, then Place Bet with the amount and the total payout, which
     opens DraftKings with these legs, and under it Track bet, which keeps the
     bet on the wallet (Jose, Oct 3, 2026) */
  function slipBets() { return window._slipBets || []; }
  function stakeOf() { return money0(document.getElementById("swstake").value) || 0; }
  function cm2(n) { return "$" + (Math.round(n * 100) / 100).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
  function payOf() {
    var bets = slipBets(), stake = stakeOf();
    if (bets.length === 1) {
      var d = decOf(document.getElementById("swodds").value);
      if (!d) return null;
      var pay = stake * d;
      if (BOOST) pay += (d - 1) * Math.min(stake, BOOST.max || stake) * BOOST.pct / 100;
      return pay;
    }
    return bets.reduce(function (t, g) { return t + stake * (decOf(parlay(g)) || 1); }, 0);
  }
  function payDraw() {
    var bets = slipBets(), stake = stakeOf(), pay = payOf();
    /* the switch flipped after the check: the button follows */
    if (typeof CHK === "object" && CHK.phase === "ready") setTimeout(function () { if (CHK.phase === "ready") chkReady(false, true); }, 0);
    var amt = document.getElementById("nsamtv");
    if (amt && !NSPAD.typing) amt.textContent = stake ? stake.toFixed(2) : "0.00";
    var el = document.getElementById("swpay");
    if (el) el.dataset.pay = pay ? pay.toFixed(2) : "";
    var total = stake * Math.max(1, bets.length);
    var wasEl = document.getElementById("nswas"), upEl = document.getElementById("nsboosted");
    var d1 = bets.length === 1 ? decOf(document.getElementById("swodds").value) : null;
    if (wasEl && upEl) {
      var up = BOOST && d1 ? 1 + (d1 - 1) * (1 + BOOST.pct / 100) : 0;
      wasEl.textContent = "";
      upEl.textContent = up ? (up >= 2 ? "+" + Math.round((up - 1) * 100) : "\u2212" + Math.round(100 / (up - 1))) : "";
      document.getElementById("swodds").classList.toggle("nsodds--under", !!up);
    }
    var b = document.getElementById("nsplaceb"), i = document.getElementById("nspayl");
    if (b) b.textContent = "Place Bet " + cm2(total);
    if (i) i.textContent = pay ? "Total Payout: " + cm2(pay) + (BOOST ? " with the " + BOOST.pct + "% boost" : "") : "";
  }
  /* the boost's cap: DraftKings' public list says $25, his own account
     $100 (Jose, Oct 3, 2026), so his is the default */
  function boostMax(p) {
    var mine = 0; try { mine = money0(localStorage.getItem("arena.boostmax")) || 0; } catch (e) {}
    return mine || Math.max(100, p.maxWager || 0);
  }
  var BOOSTOFF = false;
  function boostDraw() {
    var box = document.getElementById("swboost");
    if (!box) return;
    var bets = slipBets();
    var fit = bets.length === 1 ? boostsFor(bets[0], document.getElementById("swodds").value) : [];
    if (BOOST && !fit.some(function (p) { return p.id === BOOST.id; })) BOOST = null;
    if (!BOOST && fit.length && !BOOSTOFF) BOOST = { id: fit[0].id, pct: fit[0].pct, max: boostMax(fit[0]), head: fit[0].head };
    var p = BOOST ? fit.filter(function (x) { return x.id === BOOST.id; })[0] : fit[0];
    /* no boost fits: nothing is offered at all */
    box.innerHTML = p ? '<button type="button" class="nsbst' + (BOOST ? " on" : "") + '" data-id="' + p.id + '">' +
      '<span><b>' + p.pct + '% ' + esc(p.head.replace(/\s*\d+%.*$/, "")) + ' Boost</b><i>Up to $' + boostMax(p) + ' wager · ' + p.pct + '% profit boost</i></span>' +
      '<u class="nstog" aria-hidden="true"></u></button>' : "";
    payDraw();
  }
  var NSKEY = "", NSPAD = { typing: false, buf: "" };
  window._slipFoot = function () {
    var bets = slipBets();
    var key = window._slipShown + ":" + bets.map(function (g) { return g.map(function (b) { return b.id; }).join("+"); }).join("|");
    var odds = document.getElementById("swodds"), lab = document.getElementById("nslab");
    if (key !== NSKEY) {
      NSKEY = key;
      odds.value = window._slipPrice || "";
      BOOST = null; BOOSTOFF = false;
      chkSet("idle");
    }
    if (!stakeOf()) {
      var last = ""; try { last = localStorage.getItem("arena.stake") || ""; } catch (e1) {}
      document.getElementById("swstake").value = money0(last) || 25;
    }
    /* one bet: its price, which a tap can set to what DraftKings shows; more
       than one: how many, each at its own price */
    odds.hidden = bets.length !== 1;
    /* the one parlay's price is the row below, not twice */
    document.getElementById("sliplist").dataset.tab = window._slipShown || "";
    lab.textContent = bets.length === 1 ? "Price" : bets.length + " bets · " + cm2(stakeOf()) + " each";
    boostDraw();
    promoLoad().then(boostDraw);
  };
  function padShow(on) {
    var pad = document.getElementById("nspad"), amt = document.getElementById("nsamt");
    pad.hidden = !on; amt.classList.toggle("on", on);
    /* the keypad takes the room the nav had, so Track bet stays whole */
    document.getElementById("slipsheet").classList.toggle("padon", on);
    NSPAD.typing = false; NSPAD.buf = "";
    payDraw();
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest && e.target.closest(".nsbst, .nschip, #nsamt, #nspad button, #sliplink, #swsave");
    if (!t) return;
    if (t.classList.contains("nsbst")) {
      var p = PROMOS.filter(function (x) { return x.id === t.dataset.id; })[0];
      BOOSTOFF = !!BOOST;
      BOOST = BOOSTOFF || !p ? null : { id: p.id, pct: p.pct, max: boostMax(p), head: p.head };
      boostDraw(); return;
    }
    if (t.classList.contains("nschip")) {
      document.getElementById("swstake").value = stakeOf() + (+t.dataset.add);
      NSPAD.typing = false; window._slipFoot(); return;
    }
    if (t.id === "nsamt") {
      padShow(document.getElementById("nspad").hidden);
      /* the keypad opens in view, under the amount */
      return;
    }
    if (t.dataset.k) {
      /* the first key starts the amount over, the way a book's pad does */
      var k = t.dataset.k, buf = NSPAD.typing ? NSPAD.buf : "";
      if (k === "back") buf = buf.slice(0, -1);
      else if (k === "." ? buf.indexOf(".") < 0 : !/\.\d\d$/.test(buf)) buf += k;
      NSPAD.typing = true; NSPAD.buf = buf;
      document.getElementById("nsamtv").textContent = buf || "0";
      document.getElementById("swstake").value = money0(buf) || 0;
      try { if (money0(buf)) localStorage.setItem("arena.stake", String(money0(buf))); } catch (e0) {}
      lab0(); payDraw(); return;
    }
    if (t.id === "sliplink") { padShow(false); return; }
    if (t.id === "swsave") {
      if (CHK.phase === "idle") chkRun();
      else if (CHK.phase === "ready") track(t);
    }
  });
  /* Track bet confirms the price first (Jose, Oct 3, 2026): the first tap
     asks DraftKings again for every game on the slip, the way a double tap
     does, and the button fills left to right while it does; then it reads
     "Track at +812" with the fresh price, and the second tap keeps the bet */
  var CHK = { phase: "idle", run: 0 };
  function chkSet(phase, pc, text) {
    var t = document.getElementById("swsave");
    if (!t) return;
    CHK.phase = phase;
    if (phase === "idle") CHK.run++;
    t.classList.toggle("chk", phase === "checking");
    t.classList.toggle("rdy", phase === "ready");
    t.style.setProperty("--p", (pc || 0) + "%");
    t.disabled = phase === "checking";
    t.textContent = text || (phase === "checking" ? "Checking DraftKings" : "Track bet");
  }
  /* a leg's price in what DraftKings sent back: each price sits just before
     its own id, wherever it is in the answer */
  function chkFind(j, sel) {
    var out = "";
    (function walk(x) {
      if (out || !x || typeof x !== "object") return;
      if (Array.isArray(x)) {
        for (var i = 0; i + 1 < x.length; i++) {
          if (x[i + 1] === sel && typeof x[i] === "string" && /^[+\-\u2212]?\d/.test(x[i])) { out = x[i]; return; }
        }
        x.forEach(walk);
      } else Object.keys(x).forEach(function (k) { walk(x[k]); });
    })(j);
    return out.replace("-", "\u2212");
  }
  function chkReady(fresh, quiet) {
    var bets = slipBets();
    var odds = document.getElementById("swodds");
    if (fresh) { odds.value = window._slipPrice || odds.value; boostDraw(); }
    /* with a boost on, the price it pays at, the way DraftKings shows it */
    var up = document.getElementById("nsboosted").textContent;
    var say = bets.length === 1 ? "Track at " + ((BOOST && up) || odds.value || "") : "Track " + bets.length + " bets";
    if (quiet) { var t0 = document.getElementById("swsave"); if (t0) t0.textContent = say + (/last price/.test(t0.textContent) ? " \u00b7 last price" : ""); return; }
    chkSet("ready", 100, say + (fresh ? "" : " \u00b7 last price"));
  }
  function chkRun() {
    var bets = slipBets(), gids = [], seen = {};
    bets.forEach(function (g) { g.forEach(function (b) { if (b.g && !seen[b.g]) { seen[b.g] = 1; gids.push(String(b.g)); } }); });
    if (!gids.length || navigator.onLine === false) { chkReady(false); return; }
    var run = ++CHK.run, t0 = Date.now(), LIMIT = 240000;
    chkSet("checking", 6);
    var climb = function () {
      if (run !== CHK.run) return;
      var p = Math.min(1, (Date.now() - t0) / 60000);
      chkSet("checking", Math.round(6 + 86 * (1 - Math.pow(1 - p, 2))));
    };
    var tick = setInterval(function () { if (run !== CHK.run || CHK.phase !== "checking") { clearInterval(tick); return; } climb(); }, 500);
    var stop = function (fresh, st) {
      clearInterval(tick);
      if (run !== CHK.run) return;
      if (fresh && st && st.prices) {
        var moved = false;
        bets.forEach(function (g) { g.forEach(function (b) {
          var o = chkFind(st.prices[b.g], b.id);
          if (o && saved[b.id] && saved[b.id].o !== o) { saved[b.id].o = o; moved = true; }
        }); });
        if (moved) { try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (e) {} slip(); }
      }
      chkReady(fresh);
    };
    fetch("ask", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ games: gids.slice(0, 40) }) })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (a) {
        if (!a || !a.key) { stop(false); return; }
        var look = function () {
          if (run !== CHK.run) return;
          fetch("ask?key=" + encodeURIComponent(a.key), { cache: "no-store" })
            .then(function (r) { return r.ok ? r.json() : null; })
            .then(function (st) {
              if (st && st.prices && window._seatAsked) Object.keys(st.prices).forEach(function (id) { window._seatAsked(id, st.prices[id]); });
              if (st && st.state === "done") { stop(true, st); return; }
              if ((st && st.state === "failed") || Date.now() - t0 > LIMIT) { stop(false); return; }
              setTimeout(look, 3000);
            })
            .catch(function () { if (Date.now() - t0 > LIMIT) stop(false); else setTimeout(look, 3000); });
        };
        setTimeout(look, 2500);
      })
      .catch(function () { stop(false); });
  }
  function lab0() {
    var bets = slipBets();
    if (bets.length !== 1) document.getElementById("nslab").textContent = bets.length + " bets · " + cm2(stakeOf()) + " each";
  }
  document.addEventListener("input", function (e) {
    if (!e.target || !e.target.id) return;
    if (e.target.id === "swmaxin" && BOOST) { BOOST.max = money0(e.target.value); payDraw(); }
    if (e.target.id === "swodds") boostDraw();
  });
  function trackSay(text) {
    var el = document.createElement("div");
    el.className = "nstoast";
    el.innerHTML = '<svg viewBox="0 0 24 24" width="24" height="24" aria-hidden="true"><circle cx="12" cy="12" r="11" fill="#17c257"/><path d="M7 12.5l3.2 3.2L17 9" stroke="#fff" stroke-width="2.4" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg><div>Bet tracked<i></i></div>';
    el.querySelector("i").textContent = text;
    document.body.appendChild(el);
    setTimeout(function () { el.classList.add("off"); }, 2400);
    setTimeout(function () { el.remove(); }, 2900);
  }
  /* Track bet: each bet the tab makes is kept by the site, the wallet tracks
     it from then on, and its legs leave the slip so it cannot be tracked twice */
  function track(t) {
    var bets = slipBets(), stake = stakeOf(), kind = window._slipShown;
    var one = bets.length === 1, odds1 = document.getElementById("swodds").value.trim().replace("-", "−");
    if (!stake || !bets.length || (one && !decOf(odds1))) {
      t.classList.add("bad"); setTimeout(function () { t.classList.remove("bad"); }, 600); return;
    }
    try { localStorage.setItem("arena.stake", String(stake)); } catch (e2) {}
    var now = Date.now();
    var list = bets.map(function (g, n) {
      var odds = one ? odds1 : String(parlay(g)).replace("-", "−"), d = decOf(odds);
      var legs = g.map(function (b) {
        return { sel: b.id, pick: b.l, label: String(b.l || "").split(" · ")[0], market: "",
                 odds: b.o, g: b.g, evn: b.gn, status: "open", sgp: kind === "sgp" && g.length > 1 ? "1" : "" };
      });
      var pay = one ? payOf() : stake * d;
      return { id: "board-" + (now + n), type: legs.length < 2 ? "Single" : kind === "sgp" ? "SGP" : "Parlay",
               odds: odds, was: odds, wager: stake, topay: Math.round(pay * 100) / 100,
               boost: one && BOOST ? BOOST.pct + "% Profit Boost" : "", boosted: !!(one && BOOST),
               placed: new Date(now).toISOString(), status: "open", from: "board", legs: legs };
    });
    t.disabled = true;
    list.reduce(function (p, bet) {
      return p.then(function () {
        return fetch("bets?k=" + encodeURIComponent(ARENAKEY), { method: "POST",
          headers: { "content-type": "application/json" }, body: JSON.stringify({ sent: bet }) })
          .then(function (r) { if (!r.ok) throw 0; });
      });
    }, Promise.resolve()).then(function () {
      var total = list.reduce(function (s0, b) { return s0 + b.topay; }, 0);
      trackSay(cm2(stake * list.length) + (one ? " at " + list[0].odds : " on " + list.length + " bets") + " · pays " + cm2(total));
      padShow(false);
      bets.forEach(function (g) { g.forEach(function (b) { if (window._slipDrop) window._slipDrop(b.id); }); });
      return dkPull();
    }).catch(function () {
      t.classList.add("bad"); setTimeout(function () { t.classList.remove("bad"); }, 600);
    }).then(function () { t.disabled = false; chkSet("idle"); });
  }
  function dkPull(done) {
    DKB_T = Date.now();
    return fetch("bets?k=" + encodeURIComponent(ARENAKEY), { cache: "no-store" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        if (j && (j.at || (j.sent && j.sent.length))) { DKB = withSent(j); bankDraw(); }
        /* read, and was the last sync from the book recent: six hours */
        if (done) done(!!j, !!(j && j.at && Date.now() - j.at < 6 * 3600000));
      })
      .catch(function () { if (done) done(false); });
  }
  window._dkPull = dkPull;
  var CASHHIDE = false;
  try { CASHHIDE = localStorage.getItem("arena.cashhide") === "1"; } catch (e) {}
  /* ---- the slip, tracked ----
     A slip DraftKings holds, opened under its arrow, is drawn as the games
     it rides on: each game's line, the moneyline's score and win chance, the
     passers' head to head, and every touchdown leg with its count, live
     (Jose, Sep 29, 2026 -- the whole design is in the notes as
     wallet-slip-tracker). Every leg is tied to its game by DraftKings' own
     selection id, the same id each price on the board carries, never by a
     written name. */
  function legMap() {
    var m = {};
    var put = function (oid, v) { if (oid && !m[oid]) m[oid] = v; };
    [[typeof SCHED === "object" ? SCHED : [], "nfl", 10], [typeof CFB === "object" ? CFB : [], "college-football", 11]]
      .forEach(function (set) {
        set[0].forEach(function (g) {
          put(g[set[2]], { g: String(g[1]), k: "ml", s: 0, lg: set[1] });
          put(g[set[2] + 2], { g: String(g[1]), k: "ml", s: 1, lg: set[1] });
        });
      });
    (typeof FIGHTS === "object" ? FIGHTS : []).forEach(function (f) {
      put(f[9], { g: String(f[1]), k: "fml", s: 0, fight: 1 });
      put(f[11], { g: String(f[1]), k: "fml", s: 1, fight: 1 });
    });
    if (typeof FPROPS === "object") Object.keys(FPROPS).forEach(function (bid) {
      var fp = FPROPS[bid] || {};
      Object.keys(fp).forEach(function (key) {
        var v = fp[key];
        if (!Array.isArray(v)) return;
        var one = v.length === 1;
        v.forEach(function (c, s) { if (c && c[1]) put(c[1], { g: String(bid), k: "fm", key: key, s: one ? -1 : s, fight: 1 }); });
      });
    });
    if (typeof PROPS === "object") Object.keys(PROPS).forEach(function (gid) {
      var p = PROPS[gid] || {};
      (p.h2h || []).forEach(function (c, s) { if (c && c[1]) put(c[1], { g: gid, k: "h2h", s: s }); });
      ["ptd", "atd"].forEach(function (k) {
        (p[k] || []).forEach(function (side, s) {
          (side || []).forEach(function (c, i) { if (c && c[1]) put(c[1], { g: gid, k: k, s: s, n: i + 1 }); });
        });
      });
    });
    return m;
  }
  function trkRow(gid) {
    var hit = null;
    [[typeof SCHED === "object" ? SCHED : [], "nfl"], [typeof CFB === "object" ? CFB : [], "college-football"]].some(function (set) {
      return set[0].some(function (g) { if (String(g[1]) === String(gid)) { hit = { g: g, lg: set[1] }; return true; } return false; });
    });
    return hit;
  }
  /* the club's own color that shows on black: its bright one, else its first */
  function trkHue(ab) {
    var dull = function (c) {
      if (!c) return true;
      var n = parseInt(c.slice(1), 16), r = n >> 16, g = (n >> 8) & 255, b = n & 255, l = (r * 299 + g * 587 + b * 114) / 1000;
      return l < 45 || l > 235;
    };
    var a = (typeof ALTCOLOR === "object" && ALTCOLOR[ab]) || "", h = (typeof HUE === "object" && HUE[ab]) || (typeof CFBCOLOR === "object" && CFBCOLOR[ab]) || "";
    return !dull(a) ? a : !dull(h) ? h : "#8e8e93";
  }
  function trkImplied(p) {
    var n = parseInt(String(p || "").replace(/[−–]/g, "-"), 10);
    if (isNaN(n) || !n) return null;
    return n < 0 ? -n / (-n + 100) : 100 / (n + 100);
  }
  var TRKD = {}, OPENSLIP = {};
  /* what ESPN's summary says of one game: score, state, win chance, and each
     passer's yards, passing and rushing touchdowns, by his own ESPN id */
  function trkRead(d) {
    var comp = (((d.header || {}).competitions) || [{}])[0] || {};
    var st = (comp.status || {}).type || {}, out = { state: st.state || "pre", sc: {}, wp: null, qb: {} };
    out.detail = (st.state === "in") ? (st.shortDetail || "") : "";
    out.period = (comp.status || {}).period; out.clock = (comp.status || {}).displayClock;
    (comp.competitors || []).forEach(function (c) { out.sc[c.homeAway] = c.score; });
    var wp = d.winprobability || [];
    if (wp.length) out.wp = wp[wp.length - 1].homeWinPercentage;
    out.men = {};
    ((d.boxscore || {}).players || []).forEach(function (t) {
      (t.statistics || []).forEach(function (grp) {
        var lab = grp.labels || [], iy = lab.indexOf("YDS"), it = lab.indexOf("TD");
        (grp.athletes || []).forEach(function (a) {
          var nm = (a.athlete || {}).displayName || "", man = out.men[nm] = out.men[nm] || { id: String((a.athlete || {}).id || ""), st: {} };
          var line = man.st[grp.name] = {};
          lab.forEach(function (l, i) { line[l] = (a.stats || [])[i]; });
          var id = String((a.athlete || {}).id || ""), s = a.stats || [], q = out.qb[id] = out.qb[id] || { yd: 0, ptd: 0, rtd: 0 };
          if (grp.name === "passing") { q.yd = parseInt(s[iy], 10) || 0; q.ptd = parseInt(s[it], 10) || 0; }
          if (grp.name === "rushing") q.rtd = parseInt(s[it], 10) || 0;
        });
      });
    });
    /* each play with its quarter and clock, for a leg that asks when */
    out.plays = [];
    (((d.drives || {}).previous) || []).concat((d.drives || {}).current ? [(d.drives || {}).current] : []).forEach(function (dr) {
      (dr.plays || []).forEach(function (pl) {
        out.plays.push({ q: (pl.period || {}).number, c: (pl.clock || {}).displayValue, t: pl.text || "" });
      });
    });
    return out;
  }
  /* ---- a leg the board holds no price for: the props ----
     Tackles, yards, catches, a yes or no on the first quarter -- found in
     the one game it is on, the man in that game's own box score (Jose,
     Sep 29, 2026: "8 tackles ... a receiver to get 40 yards ... a yes or no
     first-quarter reception"). The game is DraftKings' own event number,
     through site/dkevents.json, else the two clubs its event is written
     with; never a written name alone. */
  var DKEVENTS = {};
  fetch("dkevents.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : {}; })
    .then(function (j) { DKEVENTS = j || {}; }).catch(function () {});
  function trkGameOf(lg) {
    if (lg.g) return String(lg.g);
    if (lg.ev && DKEVENTS[lg.ev]) return DKEVENTS[lg.ev];
    var m = /^([A-Z]{2,4})\s+\S.*?\s@\s([A-Z]{2,4})\s/.exec(String(lg.evn || "") + " ");
    if (!m) return "";
    var near = (typeof SCHED === "object" ? SCHED : []).filter(function (g) {
      return g[3] === m[1] && g[4] === m[2] && Math.abs(Date.parse(g[2]) - Date.now()) < 5 * 86400000;
    });
    return near.length === 1 ? String(near[0][1]) : "";
  }
  /* the stat a market names, where it is in ESPN's box score, how it is said */
  var PROPSTAT = [
    [/rush(ing)? \+ rec(eiving)? yards|rush \+ rec yds/i, [["rushing", "YDS"], ["receiving", "YDS"]], "RUSH+REC YDS"],
    [/receiving yards|rec yds/i, [["receiving", "YDS"]], "REC YDS"],
    [/longest reception/i, [["receiving", "LONG"]], "LONG REC"],
    [/receptions/i, [["receiving", "REC"]], "REC"],
    [/rushing yards|rush yds/i, [["rushing", "YDS"]], "RUSH YDS"],
    [/rushing attempts|carries/i, [["rushing", "CAR"]], "CAR"],
    [/passing yards|pass yds/i, [["passing", "YDS"]], "PASS YDS"],
    [/completions/i, [["passing", "C/ATT", 0]], "COMP"],
    [/pass(ing)? attempts/i, [["passing", "C/ATT", 1]], "ATT"],
    [/interceptions thrown|interceptions/i, [["passing", "INT"]], "INT"],
    [/tackles \+ assists|tackles and assists|total tackles/i, [["defensive", "TOT"]], "TKL+AST"],
    [/solo tackles/i, [["defensive", "SOLO"]], "SOLO"],
    [/sacks/i, [["defensive", "SACKS"]], "SACKS"],
    [/anytime td|touchdown scorer|anytime touchdown/i, [["rushing", "TD"], ["receiving", "TD"]], "TD"]
  ];
  /* who and what a prop leg says: "DeVonta Smith to Have 40+ Receiving
     Yards", or a market "Zack Baun Tackles + Assists" picked "Over 7.5" */
  function propParse(lg) {
    var pick = String(lg.pick || ""), mk = String(lg.market || ""), m;
    var yn = /^(yes|no)$/i.exec(pick.trim());
    if ((m = /^(.+?) to (?:have|record|score) (\d+)\+ (.+)$/i.exec(pick))) return { who: m[1], n: +m[2], over: true, what: m[3], mk: mk };
    var who = mk.replace(/\s*(-|\u2013)?\s*(o\/u|over\/under|milestones?|alt(ernate)?)\s*$/i, "");
    var stat = PROPSTAT.filter(function (p) { return p[0].test(who); })[0];
    if (stat) who = who.replace(stat[0], "").replace(/\s+(\d(st|nd|rd|th) quarter|first quarter)$/i, "").trim();
    if (yn) {
      /* "DeVonta Smith 1st Quarter Reception": the man is what comes before
         the quarter or the event it asks about */
      var man0 = mk.replace(/\s+((1st|2nd|3rd|4th|first) (quarter|half)|to (score|record|have)|anytime|first|reception|touchdown|td)\b.*$/i, "").trim();
      return { who: man0 || who || pick, yes: /yes/i.test(yn[1]), what: mk, mk: mk };
    }
    if ((m = /^(over|under)\s+([\d.]+)$/i.exec(pick))) return { who: who, n: /over/i.test(m[1]) ? Math.floor(+m[2]) + 1 : Math.floor(+m[2]), over: /over/i.test(m[1]), line: +m[2], what: mk, mk: mk };
    if ((m = /^(\d+)\+$/.exec(pick.trim()))) return { who: who, n: +m[1], over: true, what: mk, mk: mk };
    return { who: who || pick, what: mk, mk: mk };
  }
  /* the man in the game's own box score: the whole written name, else one
     man only whose surname and first initial fit -- two who fit is no one */
  function propMan(r, who) {
    if (!r || !r.men || !who) return null;
    var fold = function (x) { return String(x).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\b(jr|sr|ii|iii|iv)\b\.?/ig, "").replace(/[^a-z ]/ig, "").trim().toLowerCase(); };
    var w = fold(who), all = Object.keys(r.men);
    var hit = all.filter(function (n) { return fold(n) === w; });
    if (hit.length !== 1) {
      var parts = w.split(" "), last = parts[parts.length - 1], ini = parts[0][0];
      hit = all.filter(function (n) { var f = fold(n).split(" "); return f[f.length - 1] === last && f[0][0] === ini; });
    }
    return hit.length === 1 ? r.men[hit[0]] : null;
  }
  function propRow(x, r) {
    var P = propParse(x.lg), man = propMan(r, P.who);
    var stat = PROPSTAT.filter(function (p) { return p[0].test(P.what || "") || p[0].test(P.mk || ""); })[0];
    var st = (BANK.legs[x.lg.sel] || {}).st || String(x.lg.status || "").toLowerCase();
    st = st === "won" ? "won" : st === "lost" ? "lost" : "";
    var over = r && r.state === "post", pre = !r || r.state === "pre";
    var face = man && man.id ? trkFace("face/nfl/" + man.id + ".png", espnHead(man.id)) : "";
    var name = esc(famName(P.who || ""));
    /* a yes or no that asks when: the first quarter, read off the plays */
    var q1 = /1st quarter|first quarter/i.test(P.mk || "");
    if (P.yes !== undefined) {
      var what = q1 && /reception/i.test(P.mk) ? "1Q REC" : esc(String(P.what || "").replace(P.who, "").trim().toUpperCase() || "YES/NO");
      var when = "", happened = false, left = 0;
      if (q1 && r && r.plays && man) {
        var last = String(P.who).split(" ").pop().toLowerCase(), ini = String(P.who).trim()[0].toLowerCase();
        var re = new RegExp("\\bto " + ini + "\\.\\s?" + last + "\\b", "i");
        var got = r.plays.filter(function (p) { return p.q === 1 && re.test(p.t) && !/incomplete|no play|penalty/i.test(p.t); })[0];
        if (got) { happened = true; when = "caught at Q1 " + got.c; }
      }
      var q1over = r && (r.state === "post" || (r.period || 0) > 1);
      if (!st && q1) st = happened ? (P.yes ? "won" : "lost") : (q1over ? (P.yes ? "lost" : "won") : "");
      if (q1 && r && r.state === "in" && r.period === 1 && !happened) {
        var cl = String(r.clock || "15:00").split(":"); left = (+cl[0] * 60 + (+cl[1] || 0));
        when = "Q1 " + r.clock + " left";
      }
      var fill = st ? 100 : q1 && r && r.period === 1 ? Math.round((900 - left) / 900 * 100) : 0;
      if (st === "lost") TRKLOST[x.lg.sel] = 1;
      /* every kind of leg tells the faces how it stands, fights and props too */
      TRKST[x.lg.sel] = st || "";
      var box = st === "won" ? " trkn--won" : st === "lost" ? " trkn--lost" : pre ? " trkn--pre" : "";
      return '<div class="trkr"><span class="trkc">' + face + '</span><div class="trkm"><div class="trkl"><b>' + (P.yes ? "YES" : "NO") + "</b>" + name +
        ' <i>\u00b7 ' + what + '</i></div><div class="trkbar trkbar--one"><i style="width:' + fill + "%;background:" +
        (st === "won" ? "var(--green)" : st === "lost" ? "#e2564d" : "#fff") + '"></i></div>' + (when ? '<div class="trkq">' + esc(when) + "</div>" : "") +
        '</div><span class="trkn' + box + '">' + (st === "won" ? "\u2713" : st === "lost" ? "\u2717" : "\u2014") + "</span></div>";
    }
    /* a count against a line: the bar toward it, the count in the box */
    var have = 0;
    if (stat && man) stat[1].forEach(function (src) {
      var v = ((man.st[src[0]] || {})[src[1]]);
      if (src[2] !== undefined && v) v = String(v).split("/")[src[2]];
      have += parseFloat(v) || 0;
    });
    var n = P.n || 1;
    if (!st && P.over && have >= n) st = "won";
    if (!st && P.over === false && have > (P.line || n)) st = "lost";
    if (!st && over) st = P.over === false ? "won" : have >= n ? "won" : "lost";
    var pct = Math.min(100, Math.round(have / n * 100));
    if (st === "lost") TRKLOST[x.lg.sel] = 1;
      /* every kind of leg tells the faces how it stands, fights and props too */
      TRKST[x.lg.sel] = st || "";
    var bx = st === "won" ? " trkn--won" : st === "lost" ? " trkn--lost" : pre ? " trkn--pre" : "";
    var lab = (P.over === false ? "U" + (P.line || n) : n + "+");
    return '<div class="trkr"><span class="trkc">' + face + '</span><div class="trkm"><div class="trkl"><b>' + esc(lab) + "</b>" + name +
      ' <i>\u00b7 ' + esc(stat ? stat[2] : String(P.what || "").toUpperCase()) + '</i></div><div class="trkbar trkbar--one"><i style="width:' + pct +
      "%;background:" + (st === "won" ? "var(--green)" : st === "lost" ? "#e2564d" : "#fff") + '"></i></div></div><span class="trkn' + bx + '">' +
      (Math.round(have * 10) / 10) + "</span></div>";
  }
  function trkChip(r, kick) {
    if (!r || r.state === "pre") return '<span class="trkst trkst--pre">PRE</span>';
    if (r.state === "post") return '<span class="trkst trkst--fin">FINAL</span>';
    var q = r.period > 4 ? "OT" : "Q" + r.period;
    var said = /half/i.test(r.detail) ? "HALF" : q + " " + (r.clock || "");
    return '<span class="trkst">LIVE ' + esc(said) + "</span>";
  }
  function trkFace(src, alt) {
    return '<img src="' + src + '" alt="" loading="lazy"' + (alt ? ' data-next="' + alt + '"' : "") +
      ' onerror="if(this.dataset.next){this.src=this.dataset.next;this.dataset.next=\'\';}else{this.style.visibility=\'hidden\';}">';
  }
  function espnHead(id) { return "https://a.espncdn.com/i/headshots/nfl/players/full/" + id + ".png"; }
  /* one slip, drawn as its games */
  /* a fight's moneyline the board holds without DraftKings' id: the bout is
     the one another leg of the same DK event already found, or the one bout
     whose two men are the two DK names on the event ("Raul Rosas Jr. vs
     Raoni Barcelos", suffixes and accents out); the side is whichever of
     those two the pick names, and a pick that fits both takes neither */
  function trkFightOf(lg, byEv) {
    /* a moneyline tracked from the board carries its bout: when DraftKings
       moves the price and its id with it, the bout and the name still say
       which man it is (Oct 3, 2026: Silva drew as "PM" with no tracking) */
    if (lg.g && /\u2016\s*ML\b/.test(String(lg.label || lg.pick || ""))) {
      var fr0 = (typeof FIGHTS === "object" ? FIGHTS : []).filter(function (x) { return String(x[1]) === String(lg.g); })[0];
      if (fr0) {
        var who0 = String(lg.label || lg.pick).split("\u2016")[0].trim().toLowerCase();
        var la = String(fr0[3]).toLowerCase().split(" ").pop(), lb = String(fr0[5]).toLowerCase().split(" ").pop();
        var s0 = who0.indexOf(la) >= 0 && who0.indexOf(lb) < 0 ? 0 : who0.indexOf(lb) >= 0 && who0.indexOf(la) < 0 ? 1 : -1;
        if (s0 >= 0) return { g: String(fr0[1]), k: "fml", s: s0, fight: 1 };
      }
    }
    if (!/moneyline|fight winner|to win|bout odds/i.test(String(lg.market || "") + " " + String(lg.label || ""))) return null;
    var fold = function (x) { return String(x || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/\b(jr|sr|ii|iii|iv)\b\.?/ig, "").replace(/[^a-z ]/ig, "").replace(/\s+/g, " ").trim().toLowerCase(); };
    var last = function (x) { return fold(x).split(" ").pop(); };
    var f = null, all = typeof FIGHTS === "object" ? FIGHTS : [];
    if (lg.ev && byEv[lg.ev]) f = trkFightRow(byEv[lg.ev]).g;
    else {
      var two = String(lg.evn || "").split(/\s+vs\.?\s+/i);
      if (two.length !== 2) return null;
      var a = fold(two[0]), b = fold(two[1]);
      var near = all.filter(function (g) { return Math.abs(Date.parse(g[2]) - Date.now()) < 5 * 86400000; });
      var hit = near.filter(function (g) { var l = fold(g[3]), r = fold(g[5]); return (l === a && r === b) || (l === b && r === a); });
      if (!hit.length) hit = near.filter(function (g) { var l = last(g[3]), r = last(g[5]); return (l === last(a) && r === last(b)) || (l === last(b) && r === last(a)); });
      if (hit.length !== 1) return null;
      f = hit[0];
    }
    var p = fold(lg.pick), s = p === fold(f[3]) ? 0 : p === fold(f[5]) ? 1 : -1;
    if (s < 0) { var l0 = last(p) === last(f[3]), l1 = last(p) === last(f[5]); s = l0 && !l1 ? 0 : l1 && !l0 ? 1 : -1; }
    return s < 0 ? null : { g: String(f[1]), k: "fml", s: s, fight: 1 };
  }
  function slipTrack(bet) {
    var map = legMap(), games = {}, order = [], loose = [], byEv = {};
    (bet.legs || []).forEach(function (lg) { var v = map[lg.sel]; if (v && v.fight && lg.ev) byEv[lg.ev] = v.g; });
    (bet.legs || []).forEach(function (lg) {
      var v = map[lg.sel] || trkFightOf(lg, byEv);
      if (!v) { var pg = trkGameOf(lg); if (pg) v = { g: pg, k: "prop" }; }
      var row = v && (v.fight ? trkFightRow(v.g) : trkRow(v.g));
      if (!v || !row) { loose.push(lg); return; }
      if (!games[v.g]) { games[v.g] = { row: row, legs: [] }; order.push(v.g); }
      games[v.g].legs.push({ lg: lg, v: v });
    });
    if (!order.length) return "";
    order.sort(function (a, b) { return Date.parse(games[a].row.g[2]) - Date.parse(games[b].row.g[2]); });
    var html = order.map(function (gid) {
      if (games[gid].row.fight) return fightBlock(gid, games[gid]);
      var G = games[gid], g = G.row.g, lg = G.row.lg, r = TRKD[gid] || null;
      var away = g[3], home = g[4], kick = new Date(g[2]);
      var day = kick.toLocaleDateString("en-US", { weekday: "short", month: "numeric", day: "numeric", timeZone: "America/New_York" }).replace(",", "");
      var tm = kick.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
      var out = '<div class="trkg"><div class="trkh">' + esc(day) + " · " + esc(tm) + " · " + esc(away) + " @ " + esc(home) + " " + trkChip(r) + "</div>";
      var pic = function (who) { var h = gamePic(gid, who); return h ? h.src : ""; };
      var legSt = function (x) {
        var st = (BANK.legs[x.lg.sel] || {}).st || String(x.lg.status || "").toLowerCase();
        return st === "won" ? "won" : st === "lost" ? "lost" : "";
      };
      /* the moneyline: both clubs, the score, each side's chance to win */
      G.legs.filter(function (x) { return x.v.k === "ml"; }).forEach(function (x) {
        var s = x.v.s, ph;
        if (r && r.wp != null) ph = r.wp;
        else {
          var pa = trkImplied(lg === "nfl" ? g[9] : g[10]), pb = trkImplied(lg === "nfl" ? g[11] : g[12]);
          ph = pa != null && pb != null ? pb / (pa + pb) : 0.5;
        }
        var wa = Math.round((1 - ph) * 100), wh = 100 - wa;
        var sa = r ? (r.sc.away || 0) : 0, sh = r ? (r.sc.home || 0) : 0;
        /* over, the score settles it: behind at FINAL, the slip is dead */
        var mst = legSt(x) || (r && r.state === "post" && +sa !== +sh ? ((s === 0 ? +sa > +sh : +sh > +sa) ? "won" : "lost") : "");
        if (mst === "lost") TRKLOST[x.lg.sel] = 1;
        TRKST[x.lg.sel] = mst;
        out += '<div class="trkr trkr--two' + (mst ? " trkr--" + mst : "") + '">' +
          '<span class="trkc trkc--logo' + (s === 0 ? " trkc--mine" : "") + '">' + trkFace(pic(away)) + "</span>" +
          '<div class="trkm"><div class="trkt"><small>(' + wa + "%)</small><b>" + esc(sa) + "</b><em>–</em><b>" + esc(sh) + "</b><small>(" + wh + "%)</small></div>" +
          '<div class="trkbar"><i style="width:' + wa + "%;background:" + trkHue(away) + '"></i><i style="flex:1;background:' + trkHue(home) + '"></i></div></div>' +
          '<span class="trkc trkc--logo' + (s === 1 ? " trkc--mine" : "") + '">' + trkFace(pic(home)) + "</span></div>";
      });
      /* the head to head: his passer on the left, both yards and the gap */
      G.legs.filter(function (x) { return x.v.k === "h2h"; }).forEach(function (x) {
        var s = x.v.s, me = s === 0 ? [g[5], g[6], away] : [g[7], g[8], home], him = s === 0 ? [g[7], g[8], home] : [g[5], g[6], away];
        var ym = r && r.qb[String(me[1])] ? r.qb[String(me[1])].yd : 0, yh = r && r.qb[String(him[1])] ? r.qb[String(him[1])].yd : 0;
        ym = +ym || 0; yh = +yh || 0;
        var gap = ym - yh, share = ym + yh ? Math.round(ym / (ym + yh) * 100) : 50;
        var hst = legSt(x) || (r && r.state === "post" && gap !== 0 ? (gap > 0 ? "won" : "lost") : "");
        if (hst === "lost") TRKLOST[x.lg.sel] = 1;
        TRKST[x.lg.sel] = hst;
        out += '<div class="trkr trkr--two' + (hst ? " trkr--" + hst : "") + '">' +
          '<span class="trkc trkc--mine">' + trkFace(pic(me[0])) + "</span>" +
          '<div class="trkm"><div class="trkt trkt--h2h"><span>' + esc(famName(me[0])) + "</span><b>" + ym + "</b>" +
          '<em class="' + (gap < 0 ? "dn" : "up") + '">' + (gap >= 0 ? "+" : "−") + Math.abs(gap) + "</em>" +
          '<b class="dim">' + yh + '</b><span class="dim">' + esc(famName(him[0])) + "</span></div>" +
          '<div class="trkbar"><i style="width:' + share + "%;background:" + trkHue(me[2]) + '"></i><i style="flex:1;background:' + trkHue(him[2]) + '"></i></div></div>' +
          '<span class="trkc">' + trkFace(pic(him[0])) + "</span></div>";
      });
      /* the touchdown legs, by passer: both kinds on one man sit as a pair of
         short rows; one alone is the full row */
      [0, 1].forEach(function (s) {
        var mine = G.legs.filter(function (x) { return (x.v.k === "ptd" || x.v.k === "atd") && x.v.s === s; });
        if (!mine.length) return;
        var qb = s === 0 ? [g[5], g[6]] : [g[7], g[8]], q = (r && r.qb[String(qb[1])]) || { ptd: 0, rtd: 0 };
        var pair = mine.some(function (x) { return x.v.k === "ptd"; }) && mine.some(function (x) { return x.v.k === "atd"; });
        mine.sort(function (a, b) { return a.v.k < b.v.k ? 1 : -1; }).forEach(function (x) {
          var n = x.v.n || 1, have = x.v.k === "ptd" ? q.ptd : q.rtd;
          /* a final game settles every count: short of its rung it lost (the
             box went gold at FINAL -- Moore's 0 PTD, Sep 29, 2026) */
          var st = legSt(x) || (have >= n ? "won" : (r && r.state === "post") ? "lost" : "");
          if (st === "lost") TRKLOST[x.lg.sel] = 1;
          var box = st === "won" ? " trkn--won" : st === "lost" ? " trkn--lost" : (!r || r.state === "pre") ? " trkn--pre" : "";
          var mk = x.v.k === "ptd" ? '<svg class="trkmk" viewBox="0 0 20 21"><use href="#fb"/></svg>' : '<svg class="trkmk" viewBox="0 0 52 47"><use href="#rush"/></svg>';
          var what = x.v.k === "ptd" ? "PTD" : "RTD", pct = Math.min(100, Math.round(have / n * 100));
          TRKST[x.lg.sel] = st; TRKPC[x.lg.sel] = st === "won" ? 100 : pct;
          var bar = '<div class="trkbar trkbar--one"><i style="width:' + pct + "%;background:" + (st === "won" ? "var(--green)" : st === "lost" ? "#e2564d" : "#fff") + '"></i></div>';
          out += pair
            ? '<div class="trkr trkr--pair"><span class="trkc trkc--sm">' + trkFace(pic(qb[0])) + '</span><div class="trkl"><b>' + n + "+</b>" + what + mk + "</div>" + bar + '<span class="trkn' + box + '">' + have + "</span></div>"
            : '<div class="trkr"><span class="trkc">' + trkFace(pic(qb[0])) + '</span><div class="trkm"><div class="trkl"><b>' + n + "+</b>" + esc(famName(qb[0])) + ' <i>· ' + what + "</i>" + mk + "</div>" + bar + '</div><span class="trkn' + box + '">' + have + "</span></div>";
        });
      });
      G.legs.filter(function (x) { return x.v.k === "prop"; }).forEach(function (x) { out += propRow(x, r); });
      return out + "</div>";
    }).join("");
    /* a leg off no game the board carries keeps its plain line */
    if (loose.length) html += '<div class="trkg">' + loose.map(function (lg) {
      return '<div class="trkloose">' + esc(lg.label || lg.pick || "") + '<b>' + esc(String(lg.odds || "").replace("-", "−")) + "</b></div>";
    }).join("") + "</div>";
    return html;
  }
  /* the games on the slips that are open, read from ESPN once they are under
     way -- the same feed the live cards use, held five seconds -- and the
     open slips drawn again as each answer lands */
  function trkPull() {
    var map = legMap(), want = {};
    /* every slip on the wallet, open or not: a slip settles in the
       background, not only once its legs are looked at (Oct 3, 2026) */
    document.querySelectorAll("#cashlegs .slipcard[data-bet]").forEach(function (c) {
      var bet = (DKB && DKB.bets || []).filter(function (b) { return String(b.id) === c.dataset.bet; })[0];
      (bet && bet.legs || []).forEach(function (lg) { var v = map[lg.sel]; var g0 = v ? v.g : trkGameOf(lg); if (g0) want[g0] = 1; });
    });
    Object.keys(want).forEach(function (gid) {
      var fr = trkFightRow(gid);
      if (fr) { if (Date.parse(fr.g[2]) <= Date.now() + 20 * 60000) fightPull(fr.g); return; }
      var row = trkRow(gid);
      if (!row || Date.parse(row.g[2]) > Date.now() + 20 * 60000) return;
      gameFeed(gid, row.lg).then(function (d) {
        TRKD[gid] = trkRead(d);
        if (typeof bankDraw === "function") bankDraw(); else trkPaint();
      }).catch(function () {});
    });
  }
  function trkPaint() {
    document.querySelectorAll("#cashlegs .slipcard[data-bet] .sltrk").forEach(function (el) {
      var id = el.closest(".slipcard").dataset.bet;
      var bet = (DKB && DKB.bets || []).filter(function (b) { return String(b.id) === id; })[0];
      if (bet) el.innerHTML = slipTrack(bet);
    });
  }
  window.slipOpen = function (btn) {
    var c = btn.closest(".slipcard"), on = c.classList.toggle("slipcard--open");
    if (c.dataset.bet) { if (on) OPENSLIP[c.dataset.bet] = 1; else delete OPENSLIP[c.dataset.bet]; }
    if (on) trkPull();
  };
  setInterval(function () {
    var sh = document.getElementById("cashsheet");
    if (sh && !sh.hidden && document.visibilityState === "visible") trkPull();
  }, 15000);
  /* ---- the slip, tracked: fights (Jose, Sep 29, 2026) ----
     Every fight leg is one row -- picture, name over the market, the
     market's own marks, the price -- and the legs that ask about a window of
     the fight carry a bar for just that window. The spec is in the notes as
     wallet-slip-tracker. */
  function trkFightRow(bid) {
    var hit = null;
    (typeof FIGHTS === "object" ? FIGHTS : []).some(function (f) { if (String(f[1]) === String(bid)) { hit = { g: f, fight: 1 }; return true; } return false; });
    return hit;
  }
  /* each market: its words, its marks, and the stretch of the fight it asks
     about, in seconds ([from, to]; "last" is the final round and the cards) */
  function fightMarket(key, R) {
    var m, rs = function (n) { return [(n - 1) * 300, n * 300]; };
    var T = {
      ko: ["KO", ["mko"]], sub: ["SUB", ["msub"]], dec: ["DEC", ["mdec"]], ud: ["UD", ["mud"]], sdmd: ["SD/MD", ["msd"]],
      kosub: ["FINISH", ["mko", "msub"]], finish: ["FINISH", ["mko", "msub"]], kodec: ["KO OR DEC", ["mko", "mdec"]],
      subdec: ["SUB OR DEC", ["msub", "mdec"]], cards: ["CARDS", ["mdec"]], koonly: ["KO ONLY", ["mko"]], subonly: ["SUB ONLY", ["msub"]],
      deconly: ["DEC ONLY", ["mdec"]], finishonly: ["FINISH ONLY", ["mko", "msub"]], rd1only: ["R1 ONLY", ["r1"], rs(1)],
      anyko: ["ANY KO", ["mko"]], anysub: ["ANY SUB", ["msub"]], anydec: ["ANY DEC", ["mdec"]], anyud: ["ANY UD", ["mud"]],
      anysdmd: ["ANY SD/MD", ["msd"]], dist: ["GTD", ["gtd"], "all"], nodist: ["ITD", ["itd"], "all"],
      first60: ["FIRST 60 SEC", ["s60"], [0, 60]], last10: ["LAST 10 RD", ["s10"], "last10"],
      rd12: ["RD 1-2", ["mko", "msub", "r1", "r2"], [0, 600]], rdlastdec: ["R" + R + " OR DEC", ["r" + R, "mdec"], "last"]
    };
    if (T[key]) return T[key];
    if ((m = /^rd(\d)$/.exec(key))) return ["RD " + m[1], ["r" + m[1]], rs(+m[1])];
    if ((m = /^kord(\d)$/.exec(key))) return ["KO R" + m[1], ["mko", "r" + m[1]], rs(+m[1])];
    if ((m = /^subrd(\d)$/.exec(key))) return ["SUB R" + m[1], ["msub", "r" + m[1]], rs(+m[1])];
    if ((m = /^anykord(\d)$/.exec(key))) return ["ANY KO R" + m[1], ["mko", "r" + m[1]], rs(+m[1])];
    if ((m = /^anysubrd(\d)$/.exec(key))) return ["ANY SUB R" + m[1], ["msub", "r" + m[1]], rs(+m[1])];
    return [key.toUpperCase(), []];
  }
  /* the night's scoreboard, one read per night every five seconds at most */
  var FNIGHT = {};
  function fightPull(f) {
    var k = new Date(Date.parse(f[2])).toLocaleDateString("en-CA", { timeZone: "America/New_York" }).replace(/-/g, "");
    var box = FNIGHT[k];
    if (box && Date.now() - box.at < 5000) return;
    FNIGHT[k] = { at: Date.now() };
    /* the night's file first: it carries theScore's method (Knockout, Split
       Decision), where the scoreboard only ever says "Unofficial Winner" */
    var saved = fetch("final/mma-" + f[0] + ".json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : {}; }).catch(function () { return {}; });
    var live = fetch(espnUrl(MMA + "?dates=" + k)).then(function (r) { return r.json(); }).catch(function () { return {}; });
    Promise.all([live, saved]).then(function (two) {
      var d = { events: [].concat(two[0].events || [], two[1].events || []) };
      (d.events || []).forEach(function (e) {
        (e.competitions || []).forEach(function (c) {
          var st = c.status || {}, ty = st.type || {}, per = st.period || 0, clk = String(st.displayClock || "0:00").split(":");
          var secs = (+clk[0] || 0) * 60 + (+clk[1] || 0), out = { state: ty.state || "pre", period: per, clock: st.displayClock };
          /* live, the clock is what is left of the round; over, it is when it ended */
          out.gone = ty.state === "in" ? (per - 1) * 300 + (300 - secs) : ty.state === "post" ? (per - 1) * 300 + (st.clock || secs) : 0;
          var said = "";
          (c.details || []).forEach(function (dd) { var t = (dd.type || {}).text || ""; if (t.indexOf("Unofficial Winner") === 0) said = t.slice(17); });
          out.result = String((c.how && c.how.type) || (st.result || {}).name || said).toLowerCase();
          var was = TRKD["f" + c.id];
          if (was && was.state === "post" && ty.state !== "post") return;
          if (was && was.result && !out.result && ty.state === "post") out.result = was.result;
          out.cards = (c.how && c.how.scorecard) || (was && was.cards) || "";
          out.winner = null;
          (c.competitors || []).forEach(function (m) { if (m.winner) out.winner = String(m.id); });
          TRKD["f" + c.id] = out;
          /* over with no method in either: UFC Stats' own word, off the
             rewind anim_rebuild.py cut from it */
          if (ty.state === "post" && !out.result && !out.asked) {
            out.asked = 1;
            fetch(animPath(c.id)).then(function (r) { return r.ok ? r.json() : {}; }).then(function (a) {
              if (a && a.how) { out.result = String(a.how).toLowerCase(); if (typeof bankDraw === "function") bankDraw(); }
            }).catch(function () {});
          }
        });
      });
      if (typeof bankDraw === "function") bankDraw();
    }).catch(function () {});
  }
  /* did it land: the winner, the way, the round and the second */
  function fightSettle(key, s, f, r, R) {
    if (!r || r.state !== "post") return "";
    var side = s === 0 ? String(f[4]) : s === 1 ? String(f[6]) : null;
    var mine = side === null ? !!r.winner : r.winner === side;
    var how = /sub/.test(r.result) ? "sub" : /dec/.test(r.result) ? "dec" : /ko|knock/.test(r.result) ? "ko" : "";
    var dec = how === "dec", fin = how === "ko" || how === "sub", rd = r.period;
    var ud = /unan/.test(r.result), sm = /split|major/.test(r.result), m;
    var ok = {
      ko: mine && how === "ko", sub: mine && how === "sub", dec: mine && dec, ud: mine && ud, sdmd: mine && sm,
      kosub: mine && fin, finish: mine && fin, kodec: mine && (how === "ko" || dec), subdec: mine && (how === "sub" || dec),
      cards: mine && dec, koonly: mine && how === "ko", subonly: mine && how === "sub", deconly: mine && dec, finishonly: mine && fin,
      rd1only: mine && fin && rd === 1, anyko: how === "ko", anysub: how === "sub", anydec: dec, anyud: ud, anysdmd: sm,
      dist: dec, nodist: fin, first60: fin && r.gone <= 60, last10: fin && (r.gone % 300 >= 290 || r.gone % 300 === 0),
      rd12: mine && fin && rd <= 2, rdlastdec: mine && (dec || (fin && rd === R))
    }[key];
    if (ok === undefined) {
      if ((m = /^rd(\d)$/.exec(key))) ok = mine && fin && rd === +m[1];
      else if ((m = /^kord(\d)$/.exec(key))) ok = mine && how === "ko" && rd === +m[1];
      else if ((m = /^subrd(\d)$/.exec(key))) ok = mine && how === "sub" && rd === +m[1];
      else if ((m = /^anykord(\d)$/.exec(key))) ok = how === "ko" && rd === +m[1];
      else if ((m = /^anysubrd(\d)$/.exec(key))) ok = how === "sub" && rd === +m[1];
    }
    return ok === undefined ? "" : ok ? "won" : "lost";
  }
  /* a window the fight has run past with nothing to show: the leg is lost
     now, not at the final bell (Jose, Sep 29, 2026: "as soon as that 60
     seconds hits ... it should just be removed") */
  function fightPast(win, r, R) {
    if (!r || r.state !== "in" || !win || win === "all") return false;
    if (win === "last") return false;
    if (win === "last10") return false;
    return r.gone >= win[1];
  }
  var TRKLOST = {};
  /* each leg's state and how far along it is, as the tracker last saw it:
     the faces fill by it and the badge counts by it (Jose, Oct 3, 2026) */
  var TRKST = window.TRKST = {}, TRKPC = window.TRKPC = {};
  function fightBlock(bid, G) {
    var f = G.row.g, r = TRKD["f" + bid] || null, R = parseInt(((typeof FPROPS === "object" && FPROPS[bid]) || {}).rounds, 10) || 3;
    var L = f[3], Rn = f[5], kick = new Date(f[2]);
    var day = kick.toLocaleDateString("en-US", { weekday: "short", month: "numeric", day: "numeric", timeZone: "America/New_York" }).replace(",", "");
    var tm = kick.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
    var chip = !r || r.state === "pre" ? '<span class="trkst trkst--pre">PRE</span>' : r.state === "post" ? '<span class="trkst trkst--fin">FINAL</span>'
      : '<span class="trkst">LIVE R' + r.period + " " + esc(r.clock || "") + "</span>";
    var out = '<div class="trkg"><div class="trkh">' + esc(day) + " · " + esc(tm) + " · " + esc(f[7] || "") + " " + chip + "</div>";
    var pic = function (who) { var h = gamePic(bid, who); return h ? h.src : ""; };
    var sur = function (n) { return esc(lastName(n) || n); };
    var faceL = trkFace(pic(L)), faceR = trkFace(pic(Rn));
    G.legs.forEach(function (x) {
      var st0 = (BANK.legs[x.lg.sel] || {}).st || String(x.lg.status || "").toLowerCase();
      st0 = st0 === "won" ? "won" : st0 === "lost" ? "lost" : "";
      if (x.v.k === "fml") {
        var imp = function (p) { return trkImplied(p); }, pa = imp(f[8]), pb = imp(f[10]);
        var wa = pa != null && pb != null ? Math.round(pa / (pa + pb) * 100) : 50;
        var won = st0 || (r && r.state === "post" && r.winner ? (r.winner === String(x.v.s === 0 ? f[4] : f[6]) ? "won" : "lost") : "");
        TRKST[x.lg.sel] = won || "";
        if (won === "lost") TRKLOST[x.lg.sel] = 1;
        out += '<div class="trkr trkr--two' + (won ? " trkr--" + won : "") + '"><span class="trkc' + (x.v.s === 0 ? " trkc--mine" : "") + '">' + faceL +
          '</span><div class="trkm"><div class="trkt trkt--fml"><small>(' + wa + "%)</small><b>" + esc(String(f[8] || "").replace("-", "−")) +
          '</b><em>–</em><b class="dim">' + esc(String(f[10] || "").replace("-", "−")) + "</b><small>(" + (100 - wa) + "%)</small></div>" +
          '<div class="trkbar"><i style="width:' + wa + '%;background:#d12a2a"></i><i style="flex:1;background:#2a6bd1"></i></div></div>' +
          '<span class="trkc' + (x.v.s === 1 ? " trkc--mine" : "") + '">' + faceR + "</span></div>";
        return;
      }
      var M = fightMarket(x.v.key, R), win = M[2], any = x.v.s === -1;
      var st = st0 || fightSettle(x.v.key, x.v.s, f, r, R);
      if (!st && fightPast(win, r, R)) st = "lost";
      if (st === "lost") TRKLOST[x.lg.sel] = 1;
      /* every kind of leg tells the faces how it stands, fights and props too */
      TRKST[x.lg.sel] = st || "";
      var img = any ? '<span class="trkc trkc--duo">' + faceL + faceR + "</span>" : '<span class="trkc">' + (x.v.s === 0 ? faceL : faceR) + "</span>";
      var name = any ? sur(L) + " / " + sur(Rn) : sur(x.v.s === 0 ? L : Rn);
      var n = M[1].length, grid = n <= 1 ? "ic1" : n === 2 ? "ic2" : "ic4";
      var icons = M[1].map(function (k0) { return '<span class="mic"><svg><use href="#' + k0 + '"/></svg></span>'; }).join("");
      var box = st === "won" ? " trkn--won" : st === "lost" ? " trkn--lost" : " trkn--pre";
      var bar = "";
      if (win) {
        var from = 0, to = R * 300, lab = "", ticks = [], goneNow = r ? r.gone : 0, zone = null;
        if (Array.isArray(win)) { from = win[0]; to = win[1]; }
        else if (win === "last") { from = (R - 1) * 300; to = R * 300; }
        else if (win === "last10") { var cur = r && r.period ? r.period : 1; from = (cur - 1) * 300; to = cur * 300; zone = 290; }
        var len = to - from;
        for (var t = from + 300; t < to; t += 300) ticks.push((t - from) / len * 100);
        var inWin = Math.max(0, Math.min(len, goneNow - from));
        var rdEnd = Math.ceil(to / 300), left = to - goneNow;
        var mmss = function (sec) { sec = Math.max(0, Math.round(sec)); return Math.floor(sec / 60) + ":" + ("0" + sec % 60).slice(-2); };
        if (win === "last10") lab = "R" + rdEnd + " · last 10 in " + mmss(to - 10 - goneNow);
        else if (goneNow < from) lab = (to === 60 ? "60 SEC" : "R" + rdEnd + (win === "last" ? " + cards" : "")) + " · starts in " + mmss(from - goneNow);
        else lab = (to === 60 ? "60 SEC" : "R" + rdEnd + (win === "last" ? " + cards" : "")) + " · " + mmss(left);
        if (st === "won") lab = lab.split(" · ")[0];
        bar = '<div class="tlr"><div class="tlb"><i style="width:' + (st === "won" ? 100 : inWin / len * 100).toFixed(1) + "%" +
          (st === "won" ? ";background:var(--green)" : "") + '"></i>' +
          ticks.map(function (p) { return '<s style="left:' + p.toFixed(2) + '%"></s>'; }).join("") +
          (zone ? '<b style="left:' + (zone / 300 * 100).toFixed(2) + '%"></b>' : "") + '</div><span class="tle">' + esc(lab) + "</span></div>";
      }
      /* gone the distance: the judges' three cards under the row */
      if (r && r.state === "post" && r.cards && /dec|ud|sdmd|cards|dist/.test(x.v.key) && x.v.key !== "nodist")
        bar = '<div class="tlr"><span class="tle">' + esc(String(r.cards).split(/,\s*/).join(" · ")) + "</span></div>";
      out += '<div class="mw"><div class="trkr mr"><span class="mwimg">' + img + '</span><div class="mt"><span>' + name + "</span><b>" + esc(M[0]) +
        '</b></div><div class="kob"><div class="icg ' + grid + '">' + icons + '</div><span class="trkn' + box + '">' +
        esc(String(x.lg.odds || "").replace("-", "−")) + "</span></div></div>" + bar + "</div>";
    });
    return out + "</div>";
  }
  var CASHDAY = 0;
  function cashDay(b) {
    CASHDAY = +b.dataset.d;
    [].forEach.call(b.parentNode.children, function (x) { x.classList.toggle("on", x === b); });
    var pill = document.getElementById("cashpill");
    if (pill) pill.textContent = ["Yesterday", "Today", "Tomorrow"][CASHDAY + 1];
    bankDraw();
  }
  /* the day is one button on the right of the balance: each tap goes
     today, tomorrow, yesterday and round again (Jose, Oct 3, 2026) */
  /* a boosted bet's price is the one it pays at: the profit boost on top */
  function boostedOdds(bet) {
    var o = String(bet.odds || "").replace("-", "\u2212"), m = /(\d+)%/.exec(bet.boost || "");
    var n = parseInt(o.replace("\u2212", "-"), 10);
    if (!m || !bet.boosted || isNaN(n) || !n) return o;
    /* what it pays says the price exactly; DraftKings rounds its own legs */
    if (bet.wager && bet.topay) { var r = bet.topay / bet.wager; if (r > 1) return r >= 2 ? "+" + Math.round((r - 1) * 100) : "\u2212" + Math.round(100 / (r - 1)); }
    var d = n > 0 ? 1 + n / 100 : 1 + 100 / -n, up = 1 + (d - 1) * (1 + m[1] / 100);
    return up >= 2 ? "+" + Math.round((up - 1) * 100) : "\u2212" + Math.round(100 / (up - 1));
  }
  function cashNext() {
    var d = CASHDAY === 0 ? 1 : CASHDAY === 1 ? -1 : 0;
    var b = document.querySelector('#cashdays button[data-d="' + d + '"]');
    if (b) cashDay(b);
  }
  window.cashNext = cashNext;
  /* -1, 0 or 1: yesterday or before, today, tomorrow or after, by the first
     kickoff or first bell among the slip's legs that the board can place */
  function slipDay(bet, kickOf) {
    var map = legMap(), k = 9e15;
    (bet.legs || []).forEach(function (lg) {
      var t = kickOf(lg.sel), v = map[lg.sel] || trkFightOf(lg, {});
      if (t >= 9e15 && v) { var row = v.fight ? trkFightRow(v.g) : trkRow(v.g); if (row) t = Date.parse(row.g[2]); }
      if (t >= 9e15) { var pg = trkGameOf(lg), row2 = pg && trkRow(pg); if (row2) t = Date.parse(row2.g[2]); }
      if (t < k) k = t;
    });
    if (k >= 9e15) return 0;
    var day = function (ms) { return Date.parse(new Date(ms).toLocaleDateString("en-CA", { timeZone: "America/New_York" }) + "T00:00Z"); };
    var d = Math.round((day(k) - day(Date.now())) / 86400000);
    return d < 0 ? -1 : d > 0 ? 1 : 0;
  }
  /* ---- the alerts: service worker, the bell, the settings, the landing ---- */
  var ALERTKINDS = [["td", "Touchdowns and your next rung"], ["redzone", "Red zone"], ["wp", "Win chance swings"],
                    ["final", "Finals"], ["leghit", "Each leg that hits"], ["slip", "One leg left and you won"], ["pregame", "Before kickoff"],
                    ["change", "Changes after you bet"]];
  var SWREG = null;
  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("sw.js").then(function (r) { SWREG = r; alertBell(); }).catch(function () {});
    navigator.serviceWorker.addEventListener("message", function (e) { if (e.data && e.data.go) landOn(e.data.go); });
  }
  function b64key(s) {
    var raw = atob(s.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((s.length + 3) % 4)), out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }
  function alertBell() {
    var bell = document.getElementById("cashbell");
    if (!bell || !SWREG || !SWREG.pushManager) return;
    SWREG.pushManager.getSubscription().then(function (sub) {
      bell.classList.toggle("on", !!sub && typeof Notification !== "undefined" && Notification.permission === "granted");
    }).catch(function () {});
  }
  function alertPanel() {
    var box = document.getElementById("alertset");
    if (!box) return;
    if (!box.hidden) { box.hidden = true; return; }
    box.hidden = false;
    var standalone = window.navigator.standalone || (window.matchMedia && matchMedia("(display-mode: standalone)").matches);
    if (!SWREG || !SWREG.pushManager || typeof Notification === "undefined") {
      box.innerHTML = "<h4>Alerts</h4><div class='asay'>" + (standalone ? "This phone can't take alerts." :
        "Add Stacked to your home screen first (Share, then Add to Home Screen), and open it from there.") + "</div>";
      return;
    }
    box.innerHTML = "<h4>Alerts</h4><div class='asay'>Reading…</div>";
    fetch("push", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (st) {
      var draw = function (on) {
        box.innerHTML = "<h4>Alerts</h4>" + (on ? ALERTKINDS.map(function (k) {
          return '<label>' + esc(k[1]) + '<input type="checkbox" data-k="' + k[0] + '"' + (st.prefs && st.prefs[k[0]] === false ? "" : " checked") + '></label>';
        }).join("") + '<button type="button" class="atest">Send a test</button>' :
          "<div class='asay'>Get alerts on your slips with the app closed: touchdowns, red zone, finals, one leg left.</div>" +
          '<button type="button" class="atest" data-on="1">Turn on alerts</button>');
        box.querySelectorAll("input[data-k]").forEach(function (inp) {
          inp.addEventListener("change", function () {
            var p = {}; p[inp.dataset.k] = inp.checked;
            fetch("push", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ prefs: p }) });
          });
        });
        var b = box.querySelector(".atest");
        if (b) b.addEventListener("click", function () {
          if (b.dataset.on) {
            /* asked from his tap: the phone only allows it from one */
            Notification.requestPermission().then(function (perm) {
              if (perm !== "granted") { box.querySelector(".asay").textContent = "Alerts are off in the phone's settings for Stacked."; return; }
              return SWREG.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64key(st.key) }).then(function (sub) {
                return fetch("push", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ sub: sub.toJSON() }) });
              }).then(function () { alertBell(); draw(true); });
            }).catch(function () { box.querySelector(".asay").textContent = "Couldn't turn alerts on."; });
          } else {
            b.textContent = "Sent";
            fetch("push", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ test: true }) });
          }
        });
      };
      SWREG.pushManager.getSubscription().then(function (sub) { draw(!!sub && Notification.permission === "granted"); });
    }).catch(function () { box.innerHTML = "<h4>Alerts</h4><div class='asay'>Couldn't reach the alerts.</div>"; });
  }
  (function () {
    var bell = document.getElementById("cashbell");
    if (bell) bell.addEventListener("click", function (e) { e.stopPropagation(); alertPanel(); });
  })();
  /* a tapped alert lands on what it was about: the slip, open, in the
     wallet, or the game's card (Jose, Sep 29, 2026) */
  function landOn(url) {
    var h = String(url || "").split("#")[1] || "", m;
    if ((m = /^slip=(.+)$/.exec(h))) {
      var sheet = document.getElementById("cashsheet");
      if (sheet) { sheet.hidden = false; document.documentElement.classList.add("cashlock"); }
      var tries = 0;
      (function find() {
        if (typeof bankDraw === "function") bankDraw();
        var card = document.querySelector('#cashlegs .slipcard[data-bet="' + m[1] + '"]');
        if (!card && typeof cashDay === "function") {
          [-1, 0, 1].some(function (d) { var b = document.querySelector('#cashdays [data-d="' + d + '"]'); if (b) cashDay(b); return !!document.querySelector('#cashlegs .slipcard[data-bet="' + m[1] + '"]'); });
          card = document.querySelector('#cashlegs .slipcard[data-bet="' + m[1] + '"]');
        }
        if (card) { var v = card.querySelector(".slview"); if (v && !card.classList.contains("slipcard--open")) slipOpen(v); card.scrollIntoView({ block: "start" }); return; }
        if (++tries < 20) setTimeout(find, 300);
      })();
    } else if ((m = /^(game|bout)=(.+)$/.exec(h))) {
      var tries2 = 0, attr = m[1] === "bout" ? "data-bout" : "data-espn", id2 = m[2];
      (function find2() {
        var c = document.querySelector('.gcard[' + attr + '="' + id2 + '"]');
        if (c) { c.scrollIntoView({ block: "center", behavior: "smooth" }); return; }
        if (++tries2 < 20) setTimeout(find2, 300);
      })();
    }
  }
  if (/^#(slip|game|bout)=/.test(location.hash)) setTimeout(function () { landOn(location.href); history.replaceState(null, "", location.pathname); }, 1500);
  function bankDraw() {
    var box = document.getElementById("cashlegs"), amt = document.getElementById("cashamt");
    if (!box || !amt || !BANKMET) return;
    var moved = false;
    /* read once when the page opens; after that only on a double tap of the
       bag (Jose, Sep 26, 2026: "every min?") */
    if (!DKB_T) dkPull();
    /* what the page shows of each gold leg is kept, so a leg on another tab
       or a finished card is still drawn */
    document.querySelectorAll("button.price.placed[data-oid]").forEach(function (b) {
      var card = cardOf(b), id = b.dataset.oid;
      /* a moneyline settles on the final score: nothing else on a football
         card marks it, so a club that won stayed gold (Jose, Sep 25, 2026:
         Army won 21-17 and its leg never went green) */
      if (card && /^0ML/.test(id) && !b.classList.contains("won") && !b.classList.contains("lost") &&
          typeof isOver === "function" && isOver(card) && card.dataset.ls !== undefined) {
        var gid = card.dataset.espn, row = null;
        [[SCHED, 9], [CFB, 10]].forEach(function (pair) {
          (pair[0] || []).forEach(function (r) { if (String(r[1]) === String(gid)) row = [r, pair[1]]; });
        });
        if (row) {
          var ls = parseInt(card.dataset.ls, 10), rs = parseInt(card.dataset.rs, 10);
          var left = row[0][row[1] + 1] === id, right = row[0][row[1] + 3] === id;
          if ((left || right) && !isNaN(ls) && !isNaN(rs) && ls !== rs) {
            var won0 = left ? ls > rs : rs > ls;
            b.classList.add(won0 ? "won" : "lost");
          }
        }
      }
      var st = b.classList.contains("won") ? "won" : b.classList.contains("lost") ? "lost" : "live";
      var was = BANK.legs[id] || {};
      /* the leg keeps the price it was placed at and the slip's own label:
         read off a live card the label took the clock for its market, and
         the tiles wore "20:26" where ML belongs */
      var pick = saved[id] && saved[id].l ? saved[id] : null;
      var lab = was.l && !/ \u00b7 (\d+:\d\d|FINAL|LIVE)/.test(was.l) ? was.l
              : pick ? pick.l : labelFor(b).replace(/ \u00b7 .*$/, "") + " \u00b7 " +
                (card && card.dataset.kick ? new Date(card.dataset.kick).toLocaleTimeString("en-US",
                  {timeZone: "America/New_York", hour: "numeric", minute: "2-digit"}) : "");
      var now = {o: was.o || (pick && pick.o) || priceOf(b), l: lab,
                 g: card ? (card.dataset.espn || card.dataset.bout || "") : (was.g || ""), st: st,
                 k: (card && card.dataset.kick) || was.k || ""};
      if (JSON.stringify(now) !== JSON.stringify(was)) { BANK.legs[id] = now; moved = true; }
    });
    Object.keys(BANK.legs).forEach(function (id) { if (!placed[id]) { delete BANK.legs[id]; moved = true; } });
    if (dkApply()) moved = true;
    dkGold();
    /* today's games only, by each game's own start on the Eastern clock:
       yesterday's gold is still on the board until the day's marks clear,
       and it is not part of today's run (Jose, Sep 25, 2026) */
    var today = dayKeyOf(new Date().toISOString());
    var legsOn = function (d) {
      return Object.keys(placed).filter(function (id) {
        var v = BANK.legs[id];
        return v && v.k && dayKeyOf(v.k) === d;
      });
    };
    /* the day's run is today's; a night game still going past midnight keeps
       its own day until it settles */
    var dayk = today;
    if (!legsOn(today).length) {
      Object.keys(placed).forEach(function (id) {
        var v = BANK.legs[id], d = v && v.k ? dayKeyOf(v.k) : "";
        if (d && d !== today && !BANK.paid[d] && Date.now() - Date.parse(v.k) < 20 * 3600000) dayk = d;
      });
    }
    var legs = legsOn(dayk).sort()
      .map(function (id) { var v = BANK.legs[id]; return {id: id, o: v.o, l: v.l, g: v.g, st: v.st}; });
    var state = "";
    /* the unit comes off the balance the moment the day has gold on it, the
       way DraftKings takes it when the slip is placed, and goes back if every
       leg is taken off before anything settles (Jose, Sep 25, 2026) */
    BANK.out = BANK.out || {};
    /* never handed back on its own: a page drawn before its cards sees no
       gold at all, and read that as the legs taken off (Sep 25, 2026) */
    /* once the book has ever been read, the book keeps the balance: the page
       never takes a unit or pays one out itself again */
    if (legs.length && !BANK.out[dayk] && !(DKB && DKB.at) && !BANK.dkAt) {
      BANK.bal = Math.round((BANK.bal - UNIT) * 100) / 100; BANK.out[dayk] = 1; moved = true;
    }
    if (legs.length) {
      var lost = legs.some(function (b) { return b.st === "lost"; });
      var won = legs.every(function (b) { return b.st === "won"; });
      state = lost ? "lost" : won ? "won" : "";
      /* once a day: the whole payout on a cash, nothing on a miss */
      if (state && !BANK.paid[dayk] && !(DKB && DKB.at) && !BANK.dkAt) {
        var dec = 1;
        legs.forEach(function (b) { dec *= toDec(b.o) || 1; });
        BANK.bal = Math.round((BANK.bal + (won ? UNIT * dec : 0)) * 100) / 100;
        BANK.paid[dayk] = state;
        moved = true;
      }
    }
    /* held down, the balance hides every dollar figure in the panel, and
       held again shows them; this device remembers (Jose, Sep 26, 2026) */
    var cm = function (v) { return CASHHIDE ? "\u2022\u2022\u2022\u2022\u2022\u2022" : money(v); };
    amt.textContent = cm(BANK.bal);
    /* the book's open slips, each as its own card; none, and the balance
       stands alone (Jose, Sep 26, 2026) */
    if (DKB && DKB.at) {
      /* each leg's kickoff, off its card on the board: the legs in a slip run
         in the order they are played, and the slips by their first game --
         Texas at noon before Georgia at 3:30 (Jose, Sep 26, 2026) */
      var kickOf = function (sel) {
        var v = BANK.legs[sel];
        if (v && v.k) return Date.parse(v.k);
        var b0 = document.querySelector('button.price[data-oid="' + (window.CSS && CSS.escape ? CSS.escape(sel) : sel) + '"]');
        var c0 = b0 && b0.closest(".gcard");
        return c0 && c0.dataset.kick ? Date.parse(c0.dataset.kick) : 9e15;
      };
      /* a leg on more than one slip leads every slip it is on, in the same
         order on each, and the rest follow by kickoff: Texas first on both
         tickets it is on (Jose, Sep 26, 2026) */
      var onSlips = {};
      (DKB.bets || []).forEach(function (bet) {
        var once = {};
        (bet.legs || []).forEach(function (lg) { if (!once[lg.sel]) { once[lg.sel] = 1; onSlips[lg.sel] = (onSlips[lg.sel] || 0) + 1; } });
      });
      var open = (DKB.bets || []).map(function (bet) {
        var legs0 = (bet.legs || []).map(function (lg, i) { return { lg: lg, k: kickOf(lg.sel), n: onSlips[lg.sel] || 1, i: i }; })
          .sort(function (a, b) {
            var sa = a.n > 1 ? 0 : 1, sb = b.n > 1 ? 0 : 1;
            return sa - sb || a.k - b.k || a.i - b.i;      /* a tie keeps the book's order */
          });
        return { bet: bet, legs: legs0.map(function (x) { return x.lg; }), k: legs0.length ? legs0[0].k : 9e15 };
      }).sort(function (a, b) { return a.k - b.k; })
        .map(function (x) { return Object.assign({}, x.bet, { legs: x.legs }); })
        /* a slip with a leg the board has seen lose is over: it leaves the bag
           on its own, without waiting on the next read of the book (Jose,
           Sep 26, 2026: "it should drop automatically") */
        .filter(function (bet) {
          return !(bet.legs || []).some(function (lg) { return (BANK.legs[lg.sel] || {}).st === "lost" || TRKLOST[lg.sel]; });
        })
        /* the day picked under the balance: a slip is on the day its first
           game starts, Eastern; anything after tomorrow waits under Tomorrow */
        .filter(function (bet) { return slipDay(bet, kickOf) === CASHDAY; });
      var LMAP = legMap();
      if (!open.length) box.innerHTML = '<div class="cashnone">No slips ' + ["yesterday", "today", "tomorrow"][CASHDAY + 1] + "</div>";
      else box.innerHTML = open.map(function (bet) {
        var ls = (bet.legs || []).map(function (lg) {
          var v = BANK.legs[lg.sel] || {};
          /* a result the clock wrote onto the slip settles the leg on every
             device at once (Oct 3, 2026) */
          var ls0 = String(lg.status || "").toLowerCase();
          if (!v.st && (ls0 === "won" || ls0 === "lost")) v = Object.assign({}, v, { st: ls0 });
          /* the leg's own game, off its card: the picture is settled by the
             game, not the first word of a name ("Kansas" for Kansas State --
             Jose, Sep 26, 2026) */
          var b2 = document.querySelector('button.price[data-oid="' + (window.CSS && CSS.escape ? CSS.escape(lg.sel) : lg.sel) + '"]');
          var c2 = b2 && b2.closest(".gcard");
          var gid = v.g || (c2 ? (c2.dataset.espn || c2.dataset.bout || "") : "") || (LMAP[lg.sel] || {}).g || "";
          var lab = v.l || ((lg.label || lg.pick || "") + " \u00b7 ");
          var pic0 = "";
          if (!LMAP[lg.sel]) {
            var pg0 = trkGameOf(lg);
            if (pg0) {
              gid = gid || pg0;
              var P0 = propParse(lg), m0 = propMan(TRKD[pg0], P0.who);
              if (m0 && m0.id) pic0 = m0.id;
              lab = (famName(P0.who || "") + " " + (P0.yes !== undefined ? (P0.yes ? "YES" : "NO") : P0.over === false ? "U" + (P0.line || "") : (P0.n || "") + "+")).trim() + " \u00b7 ";
            }
          }
          /* a fight leg wears its fighter, or both men for a leg on the fight,
             off the bout it was placed on, and the market's own mark */
          var fv = (LMAP[lg.sel] && LMAP[lg.sel].fight) ? LMAP[lg.sel] : trkFightOf(lg, {}), fw = "", fmk = "";
          var fr0 = fv && trkFightRow(fv.g), bv = LMAP[lg.sel], br0 = bv && !bv.fight && trkRow(bv.g);
          if (br0) {
            gid = String(bv.g);
            fw = bv.k === "ml" ? br0.g[bv.s === 0 ? 3 : 4] : br0.g[bv.s === 0 ? 5 : 7];
            fmk = markFor(bv.k === "ml" ? "ML" : bv.k === "h2h" ? "H2H" : (bv.n || 1) + "+ " + (bv.k === "ptd" ? "PTD" : "ATD"));
          }
          if (fr0) {
            gid = String(fv.g);
            fw = fv.s === 0 ? fr0.g[3] : fv.s === 1 ? fr0.g[5] : fr0.g[3] + " vs " + fr0.g[5];
            fmk = fv.k === "fml" ? markFor("ML") : (fightMarket(fv.key, parseInt(((typeof FPROPS === "object" && FPROPS[fv.g]) || {}).rounds, 10) || 3)[1] || []).slice(0, 1).map(function (k0) {
              return '<i class="slmk slmk--m"><svg aria-hidden="true"><use href="#' + k0 + '"/></svg></i>'; }).join("");
          }
          return { id: lg.sel, o: String(lg.odds || "").replace("-", "\u2212"), l: lab,
                   /* what DraftKings said, or else what the tracker settled
                      it as: a slip tracked from the board has nobody else to
                      say (Oct 3, 2026: all six won and the card sat open) */
                   g: gid, st: v.st === "won" || v.st === "lost" ? v.st : (TRKST[lg.sel] || ""), pic: pic0, fw: fw, fmk: fmk };
        });
        var st = ls.some(function (b) { return b.st === "lost"; }) ? "lost" : ls.length && ls.every(function (b) { return b.st === "won"; }) ? "won" : "";
        /* the icons only; the words fold under a "View picks" the way
           DraftKings' own slip does (Jose, Sep 26, 2026) */
        /* the names as one line, the way the slip always read; the legs'
           prices stay behind the page (Jose, Sep 26, 2026) */
        var rows = (bet.boost ? '<li class="slboostrow"><span class="slboost">' + esc(bet.boost.toUpperCase()) + '</span>' +
            /* the price before the boost, beside the boost itself */
            (bet.was && !CASHHIDE ? '<b><s class="slwas">' + esc(String(bet.was).replace("-", "\u2212")) + '</s></b>' : "") + '</li>' : "");
        /* the arrow rides right after the last icon, however many there are,
           and opens the legs under them (Jose, Sep 26, 2026) */
        var arrow = '<button type="button" class="slview" aria-label="Show picks" ' +
          'onclick="slipOpen(this)">' +
          '<svg viewBox="0 0 24 24" aria-hidden="true"><polygon points="5,9 12,16 19,9" fill="currentColor"/></svg></button>';
        /* the arrow is pinned at the row's right end; the faces scroll under it */
        /* the tracker first, so the faces can fill by what it counted */
        var trk = slipTrack(bet);
        var avs = slipAvatars(ls);
        var at = Date.parse(bet.placed || ""), kind = String(bet.type || (ls.length > 1 ? "Parlay" : "Single")).toUpperCase();
        var top = '<div class="slktop"><span class="slkind">' + esc(kind) + '</span><span class="slkind slkind--n">' + ls.length +
          (ls.length > 1 ? " legs" : " leg") + '</span>' +
          /* the drop-down where the time was: it opens the tracking (Jose, Oct 3, 2026) */
          arrow + '</div>';
        return '<div class="slipcard slipcard--nw' + (st ? " slipcard--" + st : "") + (OPENSLIP[bet.id] ? " slipcard--open" : "") +
          (trk ? " slipcard--trk" : "") + '" data-bet="' + esc(String(bet.id || "")) + '">' + top + avs +
          '<div class="slnames">' + esc(slipNames(ls)) + '</div>' +
          /* the top of the card holds what DraftKings' does -- the price,
             what went in, what it pays -- and the drop-down opens the legs
             under it (Jose, Oct 3, 2026) */
          '<div class="slgrid">' +
          '<b class="slgodds">' + (CASHHIDE ? "\u2022\u2022\u2022\u2022" : esc(boostedOdds(bet))) + '</b>' +
          '<b>' + cm(bet.wager || 0) + '</b>' +
          '<b class="cashpay">' + cm(bet.topay || 0) + '</b>' +
          '<span>Price</span><span>Amount</span><span>Total payout</span>' +
          '</div>' +
          (rows ? '<ul class="slpicks">' + rows + '</ul>' : "") + (trk ? '<div class="sltrk">' + trk + "</div>" : "") +
          '</div>';
      }).join("");
      /* a leg the tracker just saw lose is only known once its slip is drawn:
         draw again at once, and the dead slip is gone */
      if (open.some(function (bet) { return (bet.legs || []).some(function (lg) { return TRKLOST[lg.sel]; }); })) setTimeout(bankDraw, 0);
      /* the icon's badge while the app is open: legs still being played on
         the open slips (the clock sets it while the app is closed) */
      try {
        var liveN = (DKB.bets || []).filter(function (b0) { return !(b0.legs || []).some(function (lg) { return (BANK.legs[lg.sel] || {}).st === "lost" || TRKLOST[lg.sel]; }); })
          .reduce(function (t, b0) { return t + (b0.legs || []).filter(function (lg) { var st = String(lg.status || "").toLowerCase(); return st !== "won" && st !== "lost" && TRKST[lg.sel] !== "won"; }).length; }, 0);
        if (navigator.setAppBadge) { if (liveN) navigator.setAppBadge(liveN); else navigator.clearAppBadge(); }
      } catch (e) {}
      /* the day's totals stand still under the slips, which scroll between
         the balance and them (Jose, Sep 26, 2026) */
      var dayEl = document.getElementById("cashday");
      if (dayEl) dayEl.innerHTML = (open.length > 1 ? '<div class="slipcard slday"><div class="slgrid">' +
        '<b>' + open.length + '</b>' +
        '<b>' + cm(open.reduce(function (t, b0) { return t + (b0.wager || 0); }, 0)) + '</b>' +
        '<b class="cashpay">' + cm(open.reduce(function (t, b0) { return t + (b0.topay || 0); }, 0)) + '</b>' +
        '<span>Slips ' + ["yesterday", "today", "tomorrow"][CASHDAY + 1] + '</span><span>Wagered</span><span>Total payout</span></div></div>' : "");
    } else if (!legs.length) {
      box.innerHTML = "";
      var dayEl0 = document.getElementById("cashday"); if (dayEl0) dayEl0.innerHTML = "";
    } else {
      box.innerHTML = '<div class="slipcard' + (state ? " slipcard--" + state : "") + '">' +
        slipAvatars(legs) + '<div class="slnames">' + esc(slipNames(legs)) + '</div>' +
        '<div class="slfoot"><b>' + legs.length + (legs.length > 1 ? " legs" : " leg") +
        '</b><span class="slpay">' + parlay(legs) + '</span></div></div>' +
        /* the foot of a receipt: what went in, and what comes back if every
           leg lands, the unit included (Jose, Sep 25, 2026) */
        '<div class="cashrcpt"><div><span>Amount</span><b>' + cm(UNIT) + '</b></div>' +
        '<div><span>Total payout</span><b class="cashpay">' +
        cm(UNIT * legs.reduce(function (d, b) { return d * (toDec(b.o) || 1); }, 1)) + '</b></div></div>';
    }
    if (moved) { bankKeep(); if (typeof pushState === "function") pushState(); }
  }
  window.bankDraw = bankDraw;
  setInterval(function () { if (document.visibilityState === "visible") bankDraw(); }, 15000);
  /* the dollar button: dragged, it follows the finger and settles on the
     nearer side; tapped, it opens the balance beside it. Where it rests is
     this device's own, kept in the browser. */
  (function () {
    var fab = document.getElementById("cashfab"), sheet = document.getElementById("cashsheet");
    if (!fab || !sheet) return;
    var KEY = "arena.cashfab.v1", M = 12;
    function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }
    function place(x, y) {
      var w = fab.offsetWidth, h = fab.offsetHeight;
      fab.style.right = "auto"; fab.style.bottom = "auto";
      fab.style.left = clamp(x, M, innerWidth - w - M) + "px";
      fab.style.top = clamp(y, M + 40, floorY() - h) + "px";
      fab._want = y;
    }
    /* the lowest the wallet may sit: above the nav, and above the slip bar
       while it is up, so its figures are never under the wallet */
    function floorY() {
      var sb = document.getElementById("slipbar");
      if (sb && !sb.hidden) {
        var r = sb.getBoundingClientRect();
        if (r.height) return r.top - 8;
      }
      return innerHeight - 96;
    }
    var sbar = document.getElementById("slipbar");
    if (sbar) new MutationObserver(function () {
      if (fab.style.top) place(parseFloat(fab.style.left) || M, fab._want != null ? fab._want : parseFloat(fab.style.top));
    }).observe(sbar, { attributes: true, attributeFilter: ["hidden"] });
    function settle() {
      var r = fab.getBoundingClientRect();
      var left = r.left + r.width / 2 < innerWidth / 2;
      place(left ? M : innerWidth - r.width - M, r.top);
      try { localStorage.setItem(KEY, JSON.stringify({ side: left ? "l" : "r", y: r.top / innerHeight })); } catch (e) {}
      if (!sheet.hidden) openSheet();
    }
    try {
      var at = JSON.parse(localStorage.getItem(KEY) || "null");
      if (at) place(at.side === "l" ? M : innerWidth - 52 - M, at.y * innerHeight);
    } catch (e) {}
    function openSheet() { bankDraw(); sheet.hidden = false; }
    /* the board stands still under the panel: only the slips scroll
       (Jose, Sep 26, 2026) */
    var lockBg = function () { document.documentElement.classList.toggle("cashlock", !sheet.hidden); };
    new MutationObserver(lockBg).observe(sheet, { attributes: true, attributeFilter: ["hidden"] });
    document.addEventListener("touchmove", function (e) {
      if (sheet.hidden) return;
      var list = document.getElementById("cashlegs");
      if (list && list.contains(e.target) && list.scrollHeight > list.clientHeight) return;
      /* a row of faces wider than its card swipes sideways (Jose, Oct 3, 2026) */
      var row = e.target.closest && e.target.closest(".slavs");
      if (row && row.scrollWidth > row.clientWidth + 2) return;
      if (e.cancelable) e.preventDefault();
    }, { passive: false });
    document.addEventListener("wheel", function (e) {
      if (sheet.hidden) return;
      var list = document.getElementById("cashlegs");
      if (list && list.contains(e.target) && list.scrollHeight > list.clientHeight) return;
      e.preventDefault();
    }, { passive: false });
    var amtEl = document.getElementById("cashamt"), holdT = null;
    if (amtEl) {
      amtEl.addEventListener("pointerdown", function () {
        clearTimeout(holdT);
        holdT = setTimeout(function () {
          CASHHIDE = !CASHHIDE;
          try { localStorage.setItem("arena.cashhide", CASHHIDE ? "1" : "0"); } catch (e) {}
          if (navigator.vibrate) navigator.vibrate(12);
          bankDraw();
        }, 450);
      });
      ["pointerup", "pointerleave", "pointercancel"].forEach(function (ev) {
        amtEl.addEventListener(ev, function () { clearTimeout(holdT); });
      });
      amtEl.addEventListener("contextmenu", function (e) { e.preventDefault(); });
      amtEl.addEventListener("click", function () {
        if (CASHHIDE || document.getElementById("cashset")) return;
        var f = document.createElement("div");
        f.id = "cashset"; f.className = "cashset";
        f.innerHTML = '<input type="text" inputmode="decimal" placeholder="Your DraftKings balance">' +
          '<button type="button">Set</button>';
        amtEl.insertAdjacentElement("afterend", f);
        var inp = f.querySelector("input"); inp.value = BANK.bal != null ? String(BANK.bal) : ""; inp.focus();
        f.querySelector("button").addEventListener("click", function () {
          var n = parseFloat(String(inp.value).replace(/[^0-9.]/g, ""));
          if (isNaN(n)) { f.remove(); return; }
          fetch("bets?k=" + encodeURIComponent(ARENAKEY), { method: "POST",
                headers: { "content-type": "application/json" }, body: JSON.stringify({ wallet: n }) })
            .then(function () { f.remove(); return dkPull(); }).catch(function () { f.remove(); });
        });
      });
      amtEl.style.webkitUserSelect = amtEl.style.userSelect = "none";
      amtEl.style.webkitTouchCallout = "none";
    }
    var sx = 0, sy = 0, ox = 0, oy = 0, moved = false, down = false;
    fab.addEventListener("pointerdown", function (e) {
      down = true; moved = false; sx = e.clientX; sy = e.clientY;
      var r = fab.getBoundingClientRect(); ox = r.left; oy = r.top;
      fab.setPointerCapture(e.pointerId);
    });
    fab.addEventListener("pointermove", function (e) {
      if (!down) return;
      var dx = e.clientX - sx, dy = e.clientY - sy;
      if (!moved && Math.abs(dx) + Math.abs(dy) < 6) return;
      moved = true; fab.classList.add("drag"); sheet.hidden = true;
      place(ox + dx, oy + dy);
    });
    /* a double tap reads the bets the DK extension sent, the fill climbing
       the bag and going green when it is in, red if it fails, the way the
       helmet's does (Jose, Sep 26, 2026) */
    var wal = fab.querySelector(".wal"), fillEl = fab.querySelector(".wal-lv");
    var tapT = null, fadeT = null, popT = null;
    window._walletPull = function () { pullNow(); };
    /* the wallet opens off the Stacked mark's double tap; its floating button
       is gone (Jose, Oct 3, 2026: "move the fab to the stacked logo") */
    window._walletOpen = function () { if (sheet.hidden) openSheet(); else sheet.hidden = true; };
    if (fab) fab.style.display = "none";
    function pullNow() {
      clearTimeout(fadeT); clearTimeout(popT);
      wal.className = "wal filling";
      fillEl.style.transition = "none"; fillEl.style.height = "0";
      void fillEl.offsetHeight; fillEl.style.transition = "";
      /* the fill never stops: it is paced to how long the last syncs took,
         so it is near the top about when the answer lands, and it keeps
         creeping -- slower and slower, never still -- if the answer is late.
         The answer finishes it, and the card pops as it touches the top
         (Jose, Sep 28, 2026: "move continuously ... slower or faster,
         depending on when we get the result") */
      var EXP = 45000;
      try { EXP = Math.max(8000, Math.min(150000, parseFloat(localStorage.getItem("arena.dkSyncMs")) || 45000)); } catch (e0) {}
      fillEl.style.transition = "none";
      var t0 = performance.now(), climbing = true;
      var climbT = null;
      (function step() {
        if (!climbing) return;
        var k = (performance.now() - t0) / EXP;
        /* a steady climb to 75% by the time the last runs took, then a crawl
           that never reaches the top: only the answer fills the rest, so it
           touches the top and turns green together (Jose, Sep 28, 2026: "at
           59 seconds and then 60 it should go, fill and then green") */
        var h = k < 1 ? 75 * k : 75 + 13 * (1 - Math.exp(-1.2 * (k - 1)));
        /* the wallet's inside runs from 13% to 70% of its box (wallet-inner.png):
           the fill is laid on that, so 88% looked full at the old scale */
        fillEl.style.height = (12.9 + 0.57 * h).toFixed(2) + "%";
        climbT = requestAnimationFrame(step);
      })();
      var fin = function (ok, fresh) {
        climbing = false; cancelAnimationFrame(climbT);
        /* how long this one took, to pace the next */
        if (ok) { try {
          var took = performance.now() - t0, was = parseFloat(localStorage.getItem("arena.dkSyncMs")) || took;
          localStorage.setItem("arena.dkSyncMs", String(Math.round(was * 0.6 + took * 0.4)));
        } catch (e1) {} }
        var cls = !ok ? "bad" : fresh ? "ok" : "none", fired = false;
        /* the card pops the moment the fill reaches the top -- on the fill's
           own end, not on a timer that ran late or not at all (Jose, Sep 28,
           2026: "when it's at the top the card pops up"): the wallet is at
           rest again and the card rises, in the same frame. green: a fresh
           sync; grey: read, nothing new from the book in six hours; red: the
           read failed */
        var top = function () {
          if (fired) return;
          fired = true;
          fillEl.removeEventListener("transitionend", onEnd);
          clearTimeout(popT);
          fillEl.style.transition = "";
          wal.className = "wal pop " + cls;
          fadeT = setTimeout(function () {
            wal.className = "wal sink " + cls;
            fadeT = setTimeout(function () { wal.className = "wal"; }, 400);
          }, 2400);
        };
        var onEnd = function (e) { if (!e || e.propertyName === "height") top(); };
        fillEl.addEventListener("transitionend", onEnd);
        fillEl.style.height = getComputedStyle(fillEl).height;   /* from wherever it has got to */
        void fillEl.offsetHeight;
        fillEl.style.transition = "height .35s ease-out";
        fillEl.style.height = "100%";
        popT = setTimeout(top, 420);   /* if the browser drops the end event */
      };
      /* the climb is its own; the checks along the way no longer move it */
      fin.step = function () {};
      (window._dkFresh || function (d) { d(false); })(fin);
    }
    function up() {
      if (!down) return;
      down = false; fab.classList.remove("drag");
      if (moved) { settle(); return; }
      /* its read is the Stacked mark's double tap now, so a tap opens it at
         once (Jose, Oct 1, 2026: "now the wallet has no double tap") */
      if (sheet.hidden) openSheet(); else sheet.hidden = true;
    }
    fab.addEventListener("pointerup", up);
    fab.addEventListener("pointercancel", up);
    document.addEventListener("pointerdown", function (e) {
      if (!sheet.hidden && !fab.contains(e.target) && !sheet.contains(e.target)) sheet.hidden = true;
    });
    addEventListener("resize", function () { if (fab.style.left) settle(); });
  })();
</script>

<script>
  /* the search (Jose, Sep 28, 2026): pull down from the top of any page and
     it drops in; a name gives his card, a few give the 1+ PTD parlay. It all
     comes from qbsearch.json, written by build/qb_search.py, so it answers as
     he types and asks nobody for anything */
  (function () {
    var box = document.getElementById("qsearch"), inp = document.getElementById("qsin"),
        sug = document.getElementById("qssug"), out = document.getElementById("qsout"),
        bar = document.getElementById("qsbar"), hint = document.getElementById("qspull");
    if (!box) return;
    var DATA = null, picked = [], LU = null, LUAT = 0;
