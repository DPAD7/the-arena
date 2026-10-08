    function load() {
      /* the lineup is asked again when the sweep has written a new one: a man
         on the injury report since it was read shows on the next open */
      if (!LU || LUAT !== (window.FILESTAMP || LUAT)) {
        var stamp = window.FILESTAMP;
        fetch("lineups.json", { cache: "no-store" }).then(function (r) { return r.ok ? r.json() : {}; })
          .then(function (j) { LU = j || {}; LUAT = stamp; if (box.classList.contains("open")) draw(); }).catch(function () { LU = LU || {}; });
      }
      if (DATA) return Promise.resolve(DATA);
      return fetch("qbsearch.json", { cache: "no-store" }).then(function (r) { return r.json(); })
        .then(function (j) { DATA = j || { qbs: {} }; return DATA; }).catch(function () { DATA = { qbs: {} }; return DATA; });
    }
    function esc(t) { return String(t == null ? "" : t).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); }
    /* the search holds every QB the board holds, always: each club's man for
       its next game and everyone on the season list, taken from the page's own
       data every time it opens, so it never waits on a rebuild of the file
       (Jose, Sep 28, 2026: "make it match once and for all") */
    /* the games that are over: the board's own settled cards, and the
       result the sweep writes to final/<id>.json within minutes of the end */
    var ENDED = {};
    function ended() {
      var now = Date.now(), ask = [];
      document.querySelectorAll('.gcard[data-settled="1"][data-espn]').forEach(function (c) { ENDED[c.dataset.espn] = 1; });
      (typeof SCHED === "object" ? SCHED : []).forEach(function (g) {
        var t = Date.parse(g[2]), id = String(g[1]);
        if (t <= now && t > now - 6 * 3600000 && !ENDED[id]) ask.push(id);
      });
      return Promise.all(ask.map(function (id) {
        return fetch("final/" + id + ".json", { cache: "no-store" }).then(function (r) {
          if (r.ok && /json/.test(r.headers.get("content-type") || "")) ENDED[id] = 1;
        }).catch(function () {});
      }));
    }
    function fromBoard() {
      var qs = DATA.qbs, now = Date.now(), next = {};
      (typeof SCHED === "object" ? SCHED : []).forEach(function (g) {
        var t = Date.parse(g[2]);
        /* a game is his next until it is final -- then next week's -- not
           until a clock runs out: four hours on, a game still being played
           had gone, and a finished one sat there for hours (Jose, Sep 28,
           2026: "says next week's game once it's done") */
        if (ENDED[String(g[1])] || t < now - 6 * 3600000) return;
        [[g[3], g[5], g[6], 0, g[4]], [g[4], g[7], g[8], 1, g[3]]].forEach(function (p) {
          if (!p[2]) return;
          if (!next[p[0]] || t < next[p[0]].t) next[p[0]] = { t: t, iso: g[2], gid: String(g[1]), n: p[1], id: String(p[2]), side: p[3], o: p[4] };
        });
      });
      var add = function (id, n, club) {
        var q = qs[id] || (qs[id] = { n: n, t: club, lg: "nfl", g: [], nx: null });
        if (club) q.t = club;
        return q;
      };
      try { if (typeof moneyRows === "function" && LEDGER) moneyRows().forEach(function (r) { add(String(r.id), r.name, qs[r.id] ? null : r.club); }); } catch (e) {}
      Object.keys(next).forEach(function (club) {
        var x = next[club], q = add(x.id, x.n, club);
        var lad = ((((typeof PROPS === "object" && PROPS[x.gid]) || {}).ptd) || [])[x.side] || [];
        /* the price is always the board's own, never the file's older copy */
        if (q.nx && q.nx.gid === x.gid) { q.nx.px = (lad[0] && lad[0][0]) || q.nx.px; return; }
        var et = new Date(new Date(x.iso).toLocaleString("en-US", { timeZone: "America/New_York" }));
        var w = (typeof WIRE === "object" && WIRE[x.id]) || {};
        q.nx = { d: x.iso, gid: x.gid, o: x.o, h: x.side === 1, px: (lad[0] && lad[0][0]) || "",
                 sl: et.getDay() !== 0 ? 0 : et.getHours() < 14 ? 1 : et.getHours() < 18 ? 4 : 0,
                 wx: ((typeof ALERTS === "object" && ALERTS[x.gid]) || {}).wx || {}, inj: w.status || "",
                 al: q.nx && q.nx.o === x.o ? q.nx.al : null };
      });
      fromBoard.next = next;
      /* a man another club now starts in his place has no next game of his own */
      Object.keys(qs).forEach(function (id) {
        var q = qs[id], x = q.nx && next[q.t];
        if (x && x.gid === q.nx.gid && x.id !== id) q.nx = null;
      });
    }
    /* the 32: each club's man for its next game, starred first (newest star
       first), then by club. A tap puts him in the search; the star keeps him
       at the front (Jose, Sep 28, 2026) */
    var row = document.getElementById("qsrow");
    var STAR = '<svg viewBox="0 0 24 24" aria-hidden="true"><polygon points="12,2.8 14.8,9 21.4,9.6 16.4,14 17.9,20.6 12,17.2 6.1,20.6 7.6,14 2.6,9.6 9.2,9"/></svg>';
    function qsRow() {
      if (!row || !DATA) return;
      var nx = fromBoard.next || {}, st = window.STARS || {};
      var men = Object.keys(nx).map(function (club) { return { club: club, id: nx[club].id, n: nx[club].n }; })
        .filter(function (m) { return m.id; });
      men.sort(function (a, b) {
        var sa = st[a.id] || 0, sb = st[b.id] || 0;
        if (sa || sb) return sb - sa;
        return a.club < b.club ? -1 : a.club > b.club ? 1 : 0;
      });
      row.innerHTML = men.map(function (m) {
        var tint = (typeof HUE === "object" && HUE[m.club]) || "#333";
        var last = typeof famName === "function" ? famName(m.n) : String(m.n).split(" ").pop();
        return '<button type="button" class="qst' + (picked.indexOf(m.id) >= 0 ? " on" : "") + '" data-id="' + esc(m.id) + '">' +
          '<span class="qst-pic" style="--tint:' + tint + '">' + face(m.id, "nfl") +
          '<span class="qst-star' + (st[m.id] ? " on" : "") + '" role="button" aria-label="Star ' + esc(m.n) + '">' + STAR + "</span></span>" +
          "<b>" + esc(last) + "</b></button>";
      }).join("");
      row.hidden = CFBMODE || !!inp.value.trim();
    }
    window.qsRow = qsRow;
    if (row) row.addEventListener("click", function (e) {
      var t = e.target.closest(".qst");
      if (!t) return;
      var id = t.dataset.id;
      if (e.target.closest(".qst-star")) {
        e.stopPropagation();
        var st = window.STARS || {};
        if (st[id]) delete st[id]; else st[id] = Date.now();
        window.STARS = st;
        try { localStorage.setItem("arena.stars", JSON.stringify(st)); } catch (e2) {}
        if (typeof pushState === "function") pushState();
        qsRow();
        /* the same star on Clips (Jose, Sep 29, 2026: "so the fav button works together") */
        if (window.clipsDraw) window.clipsDraw();
        return;
      }
      /* in the search, the way picking his name there would: a second man
         makes it a parlay, a man already in comes out */
      var at = picked.indexOf(id);
      if (at >= 0) picked.splice(at, 1); else picked.push(id);
      inp.value = ""; draw();
    });
    /* the college page's own row (Jose, Oct 3, 2026): each team playing this
       week -- its quarterback's face, his last name, the school under it --
       with a star, in the order they play. Starred teams are the ones the
       board shows. */
    var CFBMODE = false, SCHOOLS = null, RANKS = null, crow = document.getElementById("qscfb");
    function tabNow() { var t = document.querySelector('.sptab[aria-selected="true"]'); return t ? t.dataset.sp : ""; }
    function cfbRow() {
      if (!crow) return;
      var st = window.STARS || {}, q = inp.value.trim().toLowerCase(), list = [], seen = {};
      var on = {};
      document.querySelectorAll('.gcard[data-lg="college-football"][data-espn]').forEach(function (c) { on[c.dataset.espn] = 1; });
      (typeof CFB === "object" ? CFB : []).forEach(function (g) {
        if (!on[String(g[1])]) return;
        [[g[3], g[5], g[6]], [g[4], g[7], g[8]]].forEach(function (p) {
          if (seen[p[0]]) return; seen[p[0]] = 1;
          list.push({ ab: p[0], n: p[1] || "", id: p[2] || "", gid: String(g[1]), t: Date.parse(g[2]) || 0,
                      school: (SCHOOLS && SCHOOLS[p[0]]) || p[0] });
        });
      });
      if (q) list = list.filter(function (m) { return (m.n + " " + m.school + " " + m.ab).toLowerCase().indexOf(q) >= 0; });
      /* in the order they play; a star marks a team, it does not move it
         (Jose, Oct 3, 2026) */
      /* starred first, by this week's rank (#1, #12, #14, then the unranked);
         the rest in the order they play (Jose, Oct 3, 2026) */
      var rk = RANKS || {};
      list.sort(function (a, b) {
        var sa = st["cfb:" + a.ab] ? 1 : 0, sb = st["cfb:" + b.ab] ? 1 : 0;
        if (sa !== sb) return sb - sa;
        if (sa) { var ra = rk[a.ab] || 99, rb = rk[b.ab] || 99; if (ra !== rb) return ra - rb; }
        return a.t - b.t;
      });
      crow.innerHTML = list.map(function (m) {
        var last = typeof famName === "function" ? famName(m.n) : String(m.n).split(" ").pop();
        return '<button type="button" class="qst qst--cfb" data-ab="' + esc(m.ab) + '" data-gid="' + esc(m.gid) + '">' +
          '<span class="qst-pic">' + (m.id ? face(m.id, "cfb") : "") +
          '<span class="qst-star' + (st["cfb:" + m.ab] ? " on" : "") + '" role="button" aria-label="Star ' + esc(m.school) + '">' + STAR + "</span></span>" +
          "<b>" + esc(last || m.ab) + "</b><i>" + ((RANKS || {})[m.ab] ? "<em>#" + RANKS[m.ab] + "</em> " : "") + esc(m.ab) + "</i></button>";
      }).join("") || '<div class="qsnone">No college games on this page</div>';
    }
    if (crow) crow.addEventListener("click", function (e) {
      var t = e.target.closest(".qst--cfb");
      if (!t) return;
      if (e.target.closest(".qst-star")) {
        e.stopPropagation();
        var st = window.STARS || {}, k = "cfb:" + t.dataset.ab;
        if (st[k]) delete st[k]; else st[k] = Date.now();
        window.STARS = st;
        try { localStorage.setItem("arena.stars", JSON.stringify(st)); } catch (e2) {}
        if (typeof pushState === "function") pushState();
        cfbRow();
        if (window._render) window._render();
        return;
      }
      /* a tap goes to the game */
      var card = document.querySelector('.gcard[data-espn="' + t.dataset.gid + '"]');
      close();
      if (card && !card.closest(".hidebox")) card.scrollIntoView({ block: "center", behavior: "smooth" });
    });
    function open() {
      if (box.classList.contains("open")) return;
      var tab = tabNow();
      if (tab !== "nfl" && tab !== "college-football") return;
      CFBMODE = tab === "college-football";
      box.classList.toggle("qs--cfb", CFBMODE);
      if (crow) crow.hidden = !CFBMODE;
      if (row) row.hidden = CFBMODE;
      inp.placeholder = CFBMODE ? "Search a QB or a school" : "Search a QB, or a few for a parlay";
      if (CFBMODE) fetch("ranks.json", { cache: "no-store" }).then(function (r) { return r.json(); })
        .then(function (j) { RANKS = j || {}; cfbRow(); }).catch(function () { RANKS = RANKS || {}; });
      if (CFBMODE && !SCHOOLS) fetch("cfb_schools.json").then(function (r) { return r.json(); })
        .then(function (j) { SCHOOLS = j || {}; cfbRow(); }).catch(function () { SCHOOLS = {}; });
      box.classList.add("open"); load().then(ended).then(function () { try { fromBoard(); } catch (e) {} draw(); });
      setTimeout(function () { try { inp.focus(); } catch (e) {} }, 60);
    }
    function close() { box.classList.remove("open"); try { inp.blur(); } catch (e) {} }
    window.openSearch = open;
    document.getElementById("qsgrab").addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
      if (e.key === "/" && !box.classList.contains("open") && !/INPUT|TEXTAREA/.test((e.target || {}).tagName || "")) { e.preventDefault(); open(); }
    });
    document.addEventListener("pointerdown", function (e) {
      if (box.classList.contains("open") && !box.contains(e.target)) close();
    });
    /* pull down at the very top of the page; HOT and the sheets keep their own gestures */
    var y0 = null;
    addEventListener("touchstart", function (e) {
      y0 = null;
      if (box.classList.contains("open") || window.scrollY > 2 || document.documentElement.classList.contains("hotlock")) return;
      if (tabNow() !== "nfl" && tabNow() !== "college-football") return;
      if (document.querySelector("dialog[open]")) return;
      /* a drag that starts on a card's hide corner is the hide, never the
         search (Jose, Sep 28, 2026: "conflicting with the drag down to hide") */
      if (e.target.closest && e.target.closest((window.OWNDRAG || ".gcorner") + ", .gcorner--pulling")) return;
      /* nor while a sheet of the wallet's is up */
      if (document.querySelector(".cashsheet:not([hidden]), .cashfab.drag")) return;
      y0 = e.touches[0].clientY;
    }, { passive: true });
    addEventListener("touchmove", function (e) {
      if (y0 === null) return;
      var dy = e.touches[0].clientY - y0;
      if (dy > 10) { hint.style.opacity = Math.min(1, dy / 70); hint.style.transform = "translate(-50%, " + Math.min(0, dy - 80) + "px)"; }
    }, { passive: true });
    addEventListener("touchend", function (e) {
      if (y0 === null) return;
      if (document.querySelector(".gcorner--pulling, .gcorner--armed, .cashfab.drag")) { y0 = null; hint.style.opacity = 0; hint.style.transform = ""; return; }
      var dy = (e.changedTouches[0] || {}).clientY - y0;
      hint.style.opacity = 0; hint.style.transform = "";
      y0 = null;
      if (dy > 70) open();
    }, { passive: true });

    function face(id, lg) { return '<img class="qsface" alt="" loading="lazy" src="face/' + (lg === "cfb" ? "college-football" : "nfl") + "/" + esc(id) + '.png" onerror="this.style.visibility=\'hidden\'">'; }
    function num(p) { var n = parseInt(String(p || "").replace(/[−]/g, "-"), 10); return isNaN(n) ? null : n; }
    function band(p) { var n = num(p); return n === null ? "pn" : n <= -600 ? "pr" : n <= -500 ? "py" : "pg"; }
    function show(p) { return p ? String(p).replace("-", "−") : "—"; }
    function dec(p) { var n = num(p); return n === null ? null : n > 0 ? 1 + n / 100 : 1 + 100 / -n; }
    function when(iso, sl) {
      var d = new Date(iso);
      return d.toLocaleDateString("en-US", { weekday: "short", timeZone: "America/New_York" }) + " " +
             d.toLocaleDateString("en-US", { month: "numeric", day: "numeric", timeZone: "America/New_York" }) + " " +
             d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", timeZone: "America/New_York" });
    }
    function wxSay(w) {
      if (!w || w.t === undefined) return "—";
      if (w.in) return "Indoors";
      var s2 = w.t + "°";
      if (w.g) s2 += ", gusts " + w.g + " mph";
      if ((w.p || 0) >= 20) s2 += ", " + w.p + "% rain";
      return s2;
    }
    function badWx(w) { return w && !w.in && ((w.g || 0) >= 15 || (w.p || 0) >= 50); }
    function slotSay(sl) { return sl === 1 ? "1:00" : sl === 4 ? "4:00" : "other"; }

    function match(q) {
      var qs = DATA ? DATA.qbs : {}, t = q.trim().toLowerCase();
      if (!t) return [];
      var parts = t.split(/[\s.'-]+/).filter(Boolean), hits = [];
      Object.keys(qs).forEach(function (id) {
        if (picked.indexOf(id) >= 0) return;
        var words = qs[id].n.toLowerCase().split(/[\s.'-]+/);
        var ok = parts.every(function (pt) { return words.some(function (w) { return w.indexOf(pt) === 0; }); });
        if (ok) hits.push(id);
      });
      hits.sort(function (a, b) {
        var A = qs[a], B = qs[b];
        return (A.lg === "nfl" ? 0 : 1) - (B.lg === "nfl" ? 0 : 1) || B.g.length - A.g.length || A.n.localeCompare(B.n);
      });
      return hits.slice(0, 8);
    }
    function draw() {
      if (CFBMODE) { cfbRow(); sug.innerHTML = ""; out.innerHTML = ""; return; }
      var qs = DATA ? DATA.qbs : {};
      [].slice.call(bar.querySelectorAll(".qschip")).forEach(function (c) { c.remove(); });
      picked.forEach(function (id) {
        var c = document.createElement("button"); c.type = "button"; c.className = "qschip";
        c.innerHTML = esc((qs[id] || {}).n || id) + " <i>×</i>";
        c.addEventListener("click", function () { picked = picked.filter(function (x) { return x !== id; }); draw(); });
        bar.insertBefore(c, inp);
      });
      inp.placeholder = picked.length ? "Add another" : "Search a QB, or a few for a parlay";
      var hits = match(inp.value);
      sug.innerHTML = hits.map(function (id) {
        var q = qs[id];
        return '<li data-id="' + esc(id) + '">' + face(id, q.lg) + '<div><b>' + esc(q.n) + '</b><br><span>' +
               esc(q.t) + " · " + (q.lg === "nfl" ? "NFL" : "CFB") + "</span></div></li>";
      }).join("");
      /* a name it cannot find says so, never a blank (Jose, Sep 28, 2026: "this is awkward") */
      if (!hits.length && DATA && inp.value.trim())
        sug.innerHTML = '<li class="qsnone"><div><b>No QB called “' + esc(inp.value.trim()) + '”</b><br><span>NFL starters and anyone who has played this season</span></div></li>';
      out.innerHTML = picked.length === 1 ? card(picked[0]) : picked.length > 1 ? parlay(picked) : "";
      qsRow();
    }
    sug.addEventListener("click", function (e) {
      var li = e.target.closest("li[data-id]"); if (!li) return;
      picked.push(li.dataset.id); inp.value = ""; draw();
      try { inp.focus(); } catch (e2) {}
    });
    inp.addEventListener("input", draw);
    inp.addEventListener("keydown", function (e) {
      if (e.key === "Enter") { var li = sug.querySelector("li[data-id]"); if (li) { picked.push(li.dataset.id); inp.value = ""; draw(); } }
      if (e.key === "Backspace" && !inp.value && picked.length) { picked.pop(); draw(); }
    });

    function wxShort(w) {
      if (!w || w.t === undefined) return "—";
      if (w.in) return "Indoors";
      return w.t + "°" + (w.g ? " · " + w.g + " mph" : "");
    }
    /* his club's last lineup on offense against tonight's opponent's on
       defense, off site/lineups.json (build/lineups.py) */
    /* the spot a man holds, as it is said: LT, DE, OLB, CB */
    function SPOTNAME(k, p) {
      var b = String(k || "").replace(/[0-9]/g, "");
      var n = { lde: "DE", rde: "DE", ldt: "DT", rdt: "DT", nt: "NT", lolb: "OLB", rolb: "OLB", lilb: "ILB", rilb: "ILB",
                wlb: "LB", mlb: "LB", slb: "LB", lcb: "CB", rcb: "CB" }[b];
      return n || (b ? b.toUpperCase() : String(p || ""));
    }
    /* hold a jersey and his name shows over it; lift the finger and it is
       gone. A tap does nothing (Jose, Sep 28, 2026: "tap and hold is the
       best and as soon as I take my finger off, it goes away") */
    (function () {
      var tip = null, hold = null, x0 = 0, y0 = 0;
      function hide() { clearTimeout(hold); hold = null; if (tip) { tip.remove(); tip = null; } }
      document.addEventListener("pointerdown", function (e) {
        var j = e.target.closest && e.target.closest("#qsearch .qsj[data-nm]");
        hide();
        if (!j || !j.dataset.nm) return;
        x0 = e.clientX; y0 = e.clientY;
        hold = setTimeout(function () {
          var r = j.getBoundingClientRect();
          tip = document.createElement("div");
          tip.className = "qstip";
          tip.innerHTML = "<b>" + esc(j.dataset.nm) + "</b> " + esc(j.dataset.pos || "") +
            (j.dataset.was ? "<span>in for " + esc(j.dataset.was) + "</span>" :
             j.classList.contains("q") ? '<span class="q">questionable</span>' : "");
          document.body.appendChild(tip);
          var w = tip.getBoundingClientRect().width;
          tip.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.left + r.width / 2 - w / 2)) + "px";
          tip.style.top = (r.top - tip.getBoundingClientRect().height - 8) + "px";
        }, 220);
      });
      document.addEventListener("pointermove", function (e) {
        if (hold && !tip && Math.hypot(e.clientX - x0, e.clientY - y0) > 8) hide();
      });
      ["pointerup", "pointercancel", "scroll"].forEach(function (ev) { document.addEventListener(ev, hide, true); });
      document.addEventListener("contextmenu", function (e) {
        if (e.target.closest && e.target.closest("#qsearch .qsj")) e.preventDefault();
      });
    })();
    /* what can sink his legs this week, said in full on his card */
    function riskList(club, id) {
      var rs = typeof qbRisks === "function" ? qbRisks(club, id) : [];
      if (!rs.length) return "";
      return '<div class="qsrisk"><span>Consider</span>' + rs.map(function (x) {
        return "<p><b>" + esc(x.say) + "</b><small>" + esc(x.why) + "</small></p>"; }).join("") + "</div>";
    }
    /* both clubs' injury reports, his club first, each split offense and
       defense, the worst first (Jose, Sep 29, 2026) */
    function injList(gid, mine, theirs) {
      var all = ((typeof ALERTS === "object" && ALERTS && ALERTS[gid]) || {}).inj || [];
      var OFF = /^(QB|RB|FB|WR|TE|OT|OG|OL|G|T|C|LS|K|PK|P)$/;
      var RANK = { "Out": 0, "Injured Reserve": 1, "Suspension": 1, "Doubtful": 2, "Questionable": 3 };
      var TAG = { "Out": ["out", "OUT"], "Injured Reserve": ["ir", "IR"], "Suspension": ["ir", "SUSP"], "Doubtful": ["d", "D"], "Questionable": ["q", "Q"] };
      var side = function (club) {
        var men = all.filter(function (x) { return x.t === club; })
          .sort(function (a, b) { return (a.s in RANK ? RANK[a.s] : 9) - (b.s in RANK ? RANK[b.s] : 9); });
        var rows = function (list) {
          return list.length ? list.map(function (x) {
            var tg = TAG[x.s] || ["q", x.s];
            return "<p><i>" + esc(x.p) + "</i><span>" + esc(x.n) + '</span><b class="' + tg[0] + '">' + tg[1] + "</b></p>";
          }).join("") : '<div class="none">None</div>';
        };
        return "<div><h5>" + esc(club) + "</h5><h6>OFFENSE</h6>" + rows(men.filter(function (x) { return OFF.test(x.p); })) +
          "<h6>DEFENSE</h6>" + rows(men.filter(function (x) { return !OFF.test(x.p); })) + "</div>";
      };
      return '<div class="qsinj">' + side(mine) + side(theirs) + "</div>";
    }
    function formation(gid, mine, theirs) {
      var g = (LU || {})[gid] || {}, o = (g[mine] || {}).off, d = (g[theirs] || {}).def;
      if (!o || !o.length || !d || !d.length) return "";
      var cut = function (list, ps) { return list.filter(function (m) { return ps.indexOf(m.p) >= 0; }); };
      var spots = [], outs = 0, qs = 0;
      var put = function (m, x, y, club) {
        if (!m) return;
        if (m.s === "out") outs++; else if (m.s === "q") qs++;
        spots.push('<i class="qsj' + (m.s ? " " + m.s : "") + '" data-nm="' + esc(m.nm || "") + '" data-pos="' + esc(SPOTNAME(m.k, m.p)) +
          '" data-was="' + esc(m.was || "") + '" style="left:' + x + "%;top:" + y + "px;background-image:url(ico/jersey/" +
          esc(String(club).toLowerCase()) + '.png)"><em' + (m.n ? "" : ' class="pos"') + ">" +
          /* a man signed this week has no number yet: his spot is written instead */
          esc(m.n || SPOTNAME(m.k, m.p)) + "</em></i>");
      };
      // every man in his named spot off ESPN's chart (lt, lg, c ... lcb, fs);
      // the defense faces the offense, so its left is the offense's right
      /* the formations as they line up (Jose, Sep 28, 2026): on offense seven
         on the line -- five linemen, the tight end on the right, the X
         receiver split left -- the Z and the slot a step off it, the passer
         under the centre and the back behind him. On defense a 4-3 is four
         down, the strong-side backer over the tight end and the strong safety
         his side; a 3-4 is two ends and the nose with its outside backers up
         on the edges. The defense faces the offense, so its left is the
         offense's right. */
      var three4 = d.some(function (m) { return m.k === "nt" || m.k === "lilb"; });
      /* every defender squared up on an offensive spot, the same spacing as
         the line across from him (Jose, Sep 28, 2026: "why is defense
         randomly spaced") */
      /* the NFL's own diagrams (Jose, Sep 28, 2026, "Meet the defense"):
         a 4-3 is DE DT DT DE even across the line, three backers even behind
         them, then CB S S CB in one row; a 3-4 is DE DT DE, four backers in
         one row with the corners out wide on it, the two safeties deep */
      /* no fullback in the set: one back, offset to the two-receiver side;
         the tight end on the other side, next to the left tackle, with the X
         split outside him (Jose, Sep 28, 2026) */
      var OFFX = { lt: 30, lg: 38, c: 46, rg: 54, rt: 62, te: 22, wr1: 5, wr2: 95, wr3: 80, qb: 46, rb: 56, fb: 56 };
      var OFFY = { lt: 58, lg: 58, c: 58, rg: 58, rt: 58, te: 58, wr1: 58, wr2: 46, wr3: 46, qb: 32, rb: 6, fb: 6 };
      var DX = three4
        ? { rde: 30, nt: 46, lde: 62, slb: 22, rolb: 22, rilb: 38, lilb: 54, mlb: 46, wlb: 70, lolb: 70,
            rcb: 5, lcb: 95, ss: 34, fs: 58 }
        : { rde: 22, rdt: 38, ldt: 54, lde: 70, slb: 30, mlb: 46, wlb: 62,
            rcb: 5, ss: 32, fs: 60, lcb: 95 };
      var DY = three4
        ? { rde: 92, nt: 92, lde: 92, wlb: 122, rolb: 122, rilb: 122, lilb: 122, mlb: 122, slb: 122, lolb: 122,
            rcb: 122, lcb: 122, fs: 152, ss: 152 }
        : { rde: 92, rdt: 92, ldt: 92, lde: 92, wlb: 122, mlb: 122, slb: 122,
            rcb: 152, fs: 152, ss: 152, lcb: 152 };
      var X = {}, Y = {};
      [OFFX, DX].forEach(function (m) { Object.keys(m).forEach(function (k) { X[k] = m[k]; }); });
      [OFFY, DY].forEach(function (m) { Object.keys(m).forEach(function (k) { Y[k] = m[k]; }); });
      var place = function (list, club) {
        list.forEach(function (m) {
          var k = m.k || "";
          if (X[k] === undefined || Y[k] === undefined) return;
          put(m, X[k], Y[k], club);
        });
      };
      place(o, mine);
      place(d, theirs);
      var key = (outs ? '<i style="border-color:#ff3b30"></i>starter out, backup in' : "") +
                (qs ? '<i style="border-color:#ffd60a"></i>questionable' : "");
      var shut = false;
      try { shut = localStorage.getItem("arena.qsform") === "shut"; } catch (e) {}
      return '<div class="qsform' + (shut ? " shut" : "") + '"><span class="qshd" onclick="qsFold(this)">' + esc(mine) + " offense vs " + esc(theirs) +
        ' defense<button type="button" class="qsfold" aria-label="Fold the lineup"><svg viewBox="0 0 24 24" aria-hidden="true"><polygon points="5,9 12,16 19,9" fill="currentColor"/></svg></button></span>' +
        '<div class="qsfield"><div class="los"></div>' + spots.join("") + "</div>" + (key ? '<div class="qskey">' + key + "</div>" : "") +
        injList(gid, mine, theirs) + "</div>";
    }
    function card(id) {
      var q = DATA.qbs[id]; if (!q) return "";
      var yd = 0, p = 0, ru = 0, hit = 0, priced = 0, wins = 0, losses = 0;
      q.g.forEach(function (g) {
        yd += g.yd; p += g.p; ru += g.ru; if (g.p > 0) hit++;
        if (/^W/.test(g.r)) wins++; else if (/^L/.test(g.r)) losses++;
      });
      var h = '<div class="qscard"><div class="qswho">' + face(id, q.lg) + '<div><div class="qsnm">' + esc(q.n) +
        '</div><div class="qssub">' + esc(q.t) + " · QB" + (q.g.length ? " · " + wins + "–" + losses : "") + "</div></div></div>";
      h += '<div class="qssea"><div><b>' + yd + "</b><span>Pass yds</span></div><div><b>" + p + "</b><span>PTD</span></div><div><b>" +
           ru + "</b><span>RTD</span></div><div><b>" + hit + "/" + q.g.length + "</b><span>1+ PTD</span></div></div>";
      if (q.g.length) {
        h += '<div class="qsh">This season</div><table><tr><th>Date</th><th>Opp</th><th class="r">Yds</th><th class="r">PTD</th><th class="r">RTD</th><th class="r">1+ PTD</th></tr>';
        q.g.forEach(function (g) {
          var d = new Date(g.d).toLocaleDateString("en-US", { month: "numeric", day: "numeric", timeZone: "America/New_York" });
          h += "<tr><td>" + d + "</td><td>" + (g.h ? "vs " : "@ ") + esc(g.o) + (g.r ? " · " + esc(g.r.split(" ")[0]) : "") +
               '</td><td class="r">' + g.yd + '</td><td class="r">' + g.p + '</td><td class="r">' + g.ru + '</td><td class="r"><span class="qspx ' +
               band(g.px) + '">' + show(g.px) + "</span> " + (g.p > 0 ? '<span class="ok">✓</span>' : '<span class="no">✕</span>') + "</td></tr>";
        });
        h += "</table>";
      }
      var nx = q.nx;
      if (nx) {
        /* under way: it says so, and gives way to next week's once final */
        h += '<div class="qsh">' + (Date.parse(nx.d) <= Date.now() ? "Live · " : "Next · ") + (nx.h ? "vs " : "@ ") + esc(nx.o) + " · " + esc(when(nx.d)) + "</div><div class=\"qsnext\">" +
          '<div class="qstile"><span>1+ PTD</span><b class="' + band(nx.px) + '">' + (nx.px ? show(nx.px) : "not posted") + "</b></div>" +
          '<div class="qstile"><span>' + esc(nx.o) + " allows</span><b>" + (nx.al === null || nx.al === undefined ? "—" : nx.al + " PTD/g") + "</b></div>" +
          '<div class="qstile"><span>Weather</span><b>' + esc(wxShort(nx.wx)) + "</b></div></div>" +
          riskList(q.t, id) + formation(nx.gid, q.t, nx.o);
        var one = slipLegs([id]).length;
        h += '<button type="button" class="qsadd"' + (one ? "" : " disabled") + ">" +
          (one ? "Add 1+ PTD to betslip" : "No price posted yet") + "</button>";
      } else {
        h += '<div class="qsnote">No game on the board for him this week.</div>';
      }
      return h + "</div>";
    }
    function parlay(ids) {
      var d = 1, chance = 1, notes = [], priced = 0;
      var legs = ids.map(function (id) {
        var q = DATA.qbs[id]; if (!q) return "";
        var nx = q.nx, px = nx && nx.px ? nx.px : "", last = q.g[0];
        var hits = q.g.map(function (g) { return g.p > 0 ? "✓" : "✕"; }).reverse().join("");
        var hit = q.g.filter(function (g) { return g.p > 0; }).length;
        var dd = dec(px);
        if (dd) { d *= dd; chance *= 1 / dd; priced++; }
        var last2 = typeof famName === "function" ? famName(q.n) : q.n.split(" ").slice(-1)[0];
        if (!nx) notes.push(last2 + " has no game this week.");
        else {
          if (!px) notes.push(last2 + "’s price isn’t posted yet.");
          if (num(px) !== null && num(px) <= -600) notes.push(last2 + " is −600 or longer.");
          if (nx.inj) notes.push(last2 + " is " + nx.inj.toLowerCase() + ".");
          if (badWx(nx.wx)) notes.push(last2 + ": " + wxSay(nx.wx) + ".");
        }
        var slots = {};
        q.g.forEach(function (g) { slots[slotSay(g.sl)] = (slots[slotSay(g.sl)] || 0) + 1; });
        return '<div class="qsleg">' + face(id, q.lg) + '<div><div class="n2">' + esc(q.n) + '</div><div class="rec"><span class="ok">' +
          hits.replace(/✕/g, '</span><span class="no">✕</span><span class="ok">') + "</span> " + hit + "/" + q.g.length +
          (nx ? " · next " + (nx.h ? "vs " : "@ ") + esc(nx.o) + " " + esc(when(nx.d)) : "") + '</div></div><div class="qspx ' + band(px) + '">' +
          (px ? show(px) : "—") + "</div></div>";
      }).join("");
      var price = priced === ids.length && priced ? (d >= 2 ? "+" + Math.round((d - 1) * 100) : "−" + Math.round(100 / (d - 1))) : "—";
      var h = '<div class="qscard"><div class="qsh" style="margin-top:0">1+ PTD parlay · this week</div>' + legs +
        '<div class="qstot"><div><b>' + ids.length + '</b><span>Legs</span></div><div><b class="pg">' + price + '</b><span>Parlay</span></div><div><b>' +
        (priced === ids.length && priced ? Math.round(chance * 100) + "%" : "—") + "</b><span>All hit</span></div></div>";
      if (notes.length) h += '<div class="qsnote">' + notes.map(esc).join("<br>") + "</div>";
      var n = slipLegs(ids).length;
      h += '<button type="button" class="qsadd"' + (n ? "" : " disabled") + ">" +
        (!n ? "No prices posted yet" : n === ids.length ? "Add to betslip" : "Add " + n + " of " + ids.length + " to betslip") + "</button>";
      return h + "</div>";
    }
    /* each man's 1+ PTD for his next game, price and id off the board itself;
       a man whose price is not posted is left off */
    function slipLegs(ids) {
      var out = [];
      ids.forEach(function (id) {
        var q = DATA.qbs[id], nx = q && q.nx;
        if (!nx || !nx.gid) return;
        /* the slip is for games still to come: one under way is never added,
           the same as the board locks its prices at kickoff (audit, Sep 28) */
        if (Date.parse(nx.d) <= Date.now()) return;
        var side = nx.h ? 1 : 0;
        var r0 = ((((typeof PROPS === "object" && PROPS[nx.gid]) || {}).ptd || [])[side] || [])[0];
        if (!r0 || !r0[0] || !r0[1]) return;
        var row = null;
        (typeof SCHED === "object" ? SCHED : []).forEach(function (g) { if (String(g[1]) === String(nx.gid)) row = g; });
        var t = new Date(nx.d).toLocaleTimeString("en-US", { timeZone: "America/New_York", hour: "numeric", minute: "2-digit" });
        out.push({ oid: r0[1], o: r0[0], g: nx.gid, gn: row ? row[3] + " @ " + row[4] : "",
                   l: (typeof famName === "function" ? famName(q.n) : q.n) + " 1+ PTD \u00b7 " + t });
      });
      return out;
    }
    out.addEventListener("click", function (e) {
      var b = e.target.closest(".qsadd");
      if (!b || b.disabled || !window.addLegs) return;
      var n = window.addLegs(slipLegs(picked));
      b.textContent = n ? "Added " + n + " to betslip" : "No prices posted yet";
      b.classList.add("qsadd--done");
    });

    /* ---- hold a QB's face: his season, game by game (Jose, Oct 3, 2026) ----
       Half a second on an NFL card's face lifts his season over the blurred
       board, the way theScore's long press does: the record, yards a game,
       touchdowns, then each game -- result, opponent, passing yards, the
       margin over the other passer, passing and rushing touchdowns. A finger
       that moves is a scroll or a swipe, and the hold lets it go. */
    /* the little tap a hold gives, the way theScore's does (Jose, Oct 8,
       2026). Android takes navigator.vibrate; iPhone Safari ignores it but,
       from iOS 18, taps the hand when a switch is flipped -- so a switch no
       one sees is flipped instead */
    var buzzSw = null;
    function buzz() {
      if (navigator.vibrate && navigator.vibrate(10)) return;
      try {
        if (!buzzSw) {
          buzzSw = document.createElement("label");
          buzzSw.setAttribute("aria-hidden", "true"); buzzSw.dataset.buzz = "1";
          buzzSw.style.cssText = "position:fixed;left:-9999px;top:0;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none";
          var sw = document.createElement("input");
          sw.type = "checkbox"; sw.setAttribute("switch", ""); sw.tabIndex = -1;
          buzzSw.appendChild(sw);
          document.body.appendChild(buzzSw);
        }
        buzzSw.click();
      } catch (e) {}
    }
    window._buzz = buzz;
    var pop = document.createElement("div");
    pop.className = "qblog"; pop.hidden = true;
    document.body.appendChild(pop);
    function etDay(iso) { return new Date(iso).toLocaleDateString("en-US", { month: "numeric", day: "numeric", timeZone: "America/New_York" }); }
    function seasonOf(id) {
      var qs = DATA.qbs, q = qs[id];
      if (!q) return "";
      var games = (q.g || []).slice().sort(function (a, b) { return a.d < b.d ? -1 : 1; });
      var tot = { yd: 0, p: 0, ru: 0, w: 0, l: 0 };
      var rows = games.map(function (g) {
        var oy = null, on = "";
        Object.keys(qs).forEach(function (k) {
          var x = qs[k];
          if (x.t !== g.o) return;
          (x.g || []).forEach(function (y) { if (y.d === g.d && y.o === q.t) { oy = y.yd; on = x.n; } });
        });
        var w = /^W/.test(g.r || ""), m = oy === null ? null : (g.yd || 0) - oy;
        tot.yd += g.yd || 0; tot.p += g.p || 0; tot.ru += g.ru || 0; if (w) tot.w++; else if (/^L/.test(g.r || "")) tot.l++;
        var lastOn = on ? (typeof famName === "function" ? famName(on) : on.split(" ").pop()) : "";
        return '<tr><td class="ql-d">' + etDay(g.d) + '</td>' +
          '<td><span class="ql-wl ' + (w ? "w" : "l") + '">' + esc((g.r || " ").charAt(0)) + '</span> <span class="ql-sc">' + esc(String(g.r || "").slice(2)) + '</span></td>' +
          '<td class="ql-o">' + (g.h ? "vs " : "@ ") + esc(g.o) + '</td>' +
          '<td class="ql-n">' + (g.yd || 0) + '</td>' +
          '<td class="ql-n ' + (m > 0 ? "up" : m < 0 ? "dn" : "") + '">' + (m === null ? "—" : (m > 0 ? "+" : m < 0 ? "−" : "") + Math.abs(m)) + (lastOn ? "<i>" + esc(lastOn) + "</i>" : "") + '</td>' +
          '<td class="ql-n"><b' + ((g.p || 0) > 0 ? ' class="hit"' : "") + '>' + (g.p || 0) + '</b></td>' +
          '<td class="ql-n"><b' + ((g.ru || 0) > 0 ? ' class="hit"' : "") + '>' + (g.ru || 0) + '</b></td></tr>';
      }).join("");
      var n = games.length || 1, nx = q.nx;
      var next = nx ? "next: " + (nx.h ? "vs " : "@ ") + esc(nx.o) + ", " + new Date(nx.d).toLocaleString("en-US", { weekday: "short", hour: "numeric", minute: "2-digit", timeZone: "America/New_York" }) : "";
      return '<div class="ql-card"><div class="ql-hd">' + face(id, "nfl") + '<div><b>' + esc(q.n) + '</b><i>' + esc(q.t || "") + (next ? " · " + next : "") + '</i></div></div>' +
        '<div class="ql-sum"><div><b>' + tot.w + "-" + tot.l + '</b><span>Record</span></div><div><b>' + Math.round(tot.yd / n) + '</b><span>Yds / game</span></div>' +
        '<div><b>' + tot.p + '</b><span>Pass TD</span></div><div><b>' + tot.ru + '</b><span>Rush TD</span></div></div>' +
        (games.length ? '<table class="ql-t"><tr><th>Date</th><th>Result</th><th>Opp</th><th>Pass yds</th><th>H2H</th><th>PTD</th><th>RTD</th></tr>' + rows + '</table>'
                      : '<div class="ql-none">No games played yet</div>') + '</div>';
    }
    function popOpen(id, at) {
      load().then(function () {
        var html = seasonOf(id);
        if (!html) return;
        pop.innerHTML = html; pop.hidden = false; openedAt = Date.now();
        /* over the card he is holding, not the top of the screen (Jose, Oct 3,
           2026: "I told you where I wanted it") */
        var cd = pop.querySelector(".ql-card");
        if (at && cd) {
          /* the card's own size: the face and name are already on it, so the
             season sits in its place, scrolling inside if it runs long */
          cd.classList.add("ql-card--in");
          cd.style.position = "fixed"; cd.style.left = at.left + "px"; cd.style.width = at.width + "px";
          cd.style.top = at.top + "px"; cd.style.height = at.height + "px"; cd.style.maxHeight = "none";
        }
        document.documentElement.classList.add("qblog-on");
      });
    }
    function popClose() { pop.hidden = true; document.documentElement.classList.remove("qblog-on"); }
    var openedAt = 0;
    /* the lift that ends the hold can land as a tap on the backdrop: taps in
       the first moment after it opens do not close it */
    pop.addEventListener("click", function (e) { if (Date.now() - openedAt > 600 && !e.target.closest(".ql-card")) popClose(); });
    var hold = null, hx = 0, hy = 0, held = false;
    /* pointer events, which an iPhone reports for a held finger the same as
       a mouse; a move of more than a few pixels, or the page taking the
       finger for a scroll (pointercancel), lets it go */
    document.addEventListener("pointerdown", function (e) {
      var im = e.target.closest && e.target.closest('.gcard[data-lg="nfl"] img.qbface');
      /* the right man's face sits under the hide corner: look through it to
         the face (the corner keeps its own drag; a hold that never moves is
         not a drag) */
      if (!im && document.elementsFromPoint) {
        im = document.elementsFromPoint(e.clientX, e.clientY).filter(function (x) {
          return x.matches && x.matches('.gcard[data-lg="nfl"] img.qbface');
        })[0] || null;
      }
      held = false;
      clearTimeout(hold); hold = null;
      if (!im || !e.isPrimary) return;
      var m = /face\/nfl\/(\d+)\.png/.exec(im.getAttribute("src") || "");
      if (!m) return;
      /* only the face's own section: not the strip with the travel mark and the
         record above it, not the name and price under it (Jose, Oct 3, 2026) */
      var r = im.getBoundingClientRect(), fy = (e.clientY - r.top) / (r.height || 1);
      if (fy < 0.17 || fy > 0.78) return;
      hx = e.clientX; hy = e.clientY;
      hold = setTimeout(function () { hold = null; held = true; buzz(); popOpen(m[1]); }, 450);
    }, true);
    document.addEventListener("pointermove", function (e) {
      if (hold && (Math.abs(e.clientX - hx) > 12 || Math.abs(e.clientY - hy) > 12)) { clearTimeout(hold); hold = null; }
    }, true);
    ["pointerup", "pointercancel"].forEach(function (k) {
      document.addEventListener(k, function () { clearTimeout(hold); hold = null; }, true);
    });
    /* the tap that ends a hold is not also a tap on the card */
    document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("[data-buzz]")) return; if (held) { held = false; e.stopPropagation(); e.preventDefault(); } }, true);
    document.addEventListener("contextmenu", function (e) { if (e.target.closest && e.target.closest("img.qbface")) e.preventDefault(); });
    window._qbLog = popOpen;

    /* ---- hold a fighter's record: his whole career (Jose, Oct 8, 2026) ----
       Half a second on the record over a UFC face lifts his pro record over
       the blurred board: the path through the promotions, the streak and his
       UFC record with CUT RISK, every fight newest first with its odds. The
       career is ufc_records.json, written by build/ufc_records.py; the NEXT
       row is read off the card he is holding, so its price is the live one. */
    var RH = null, rhPop = document.createElement("div");
    rhPop.className = "rh-pop"; rhPop.hidden = true;
    document.body.appendChild(rhPop);
    function rhLoad() {
      if (!RH) RH = fetch("ufc_records.json", { cache: "no-cache" }).then(function (r) { return r.json(); }).catch(function () { RH = null; return {}; });
      return RH;
    }
    var RHLB = { 115: "Strawweight", 125: "Flyweight", 135: "Bantamweight", 145: "Featherweight", 155: "Lightweight",
                 170: "Welterweight", 185: "Middleweight", 205: "Light Heavyweight", 265: "Heavyweight" };
    function rhOpen(card, side) {
      var mine = side === "l" ? "lf" : "rf", his = side === "l" ? "rf" : "lf";
      var id = card.dataset[mine + "id"];
      rhLoad().then(function (all) {
        var x = all && all[id];
        if (!x) return;
        var kick = card.dataset.kick ? new Date(card.dataset.kick) : null;
        var tue = kick && kick.toLocaleDateString("en-US", { weekday: "short", timeZone: "America/New_York" }) === "Tue";
        var lbm = /(\d{3})/.exec(card.dataset.wt || ""), lb = lbm ? +lbm[1] : null;
        /* his price: the price on his own half of the card */
        var slots = card.querySelectorAll(".gml");
        var slot = slots[side === "l" ? 0 : slots.length - 1];
        var pm = slot && /[+−-]\d{3,}/.exec(slot.textContent || "");
        var price = pm ? pm[0].replace("−", "-") : "–";
        var opp = card.dataset[his] || "", oid = card.dataset[his + "id"];
        var tags = '<span class="rh-tg">' + (tue ? "DWCS" : "UFC") + "</span>";
        if (lb && x.lb && RHLB[lb] && Math.abs(lb - x.lb) >= 10) {
          tags += '<span class="rh-tg rh-wc">' + (lb > x.lb ? "&#8593; UP TO " : "&#8595; DOWN TO ") + lb + "</span>";
        }
        /* missed weight and short notice for this bout, off the event's page */
        if (kick && x.nx) {
          [0, -1, 1].forEach(function (k) {
            var d = new Date(kick.getTime() + k * 864e5).toLocaleDateString("en-CA", { timeZone: "America/New_York" });
            if (x.nx[d] && tags.indexOf(x.nx[d]) < 0) tags += x.nx[d];
          });
        }
        var when = kick ? kick.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "America/New_York" }) + " '" + String(kick.getFullYear()).slice(2) : "";
        var next = '<div class="rh-r rh-nx"><b class="rh-nxb"><svg width="8" height="9" viewBox="0 0 8 9"><path d="M1 .5 7.5 4.5 1 8.5Z" fill="#fff"/></svg></b>' +
          '<div class="rh-o"><div>' + (oid ? '<img class="rh-fc" src="face/mma/' + oid + '.png" alt="" onerror="var s=document.createElement(\'span\');s.className=this.className;this.replaceWith(s)">' : '<span class="rh-fc"></span>') +
          esc(opp) + tags + "</div><small>" + (lb && RHLB[lb] ? RHLB[lb] + " · " : "") + when + "</small></div>" +
          '<div class="rh-od">' + esc(price) + "</div></div>";
        var path = x.path, chips = x.chips;
        if (tue) {
          path += '<div class="rh-t rh-deb"><b>DWCS</b><span>Tue</span><small>' + when.replace(/ '\d+$/, "") + "</small></div>";
          chips = '<span class="rh-chip rh-dw">DWCS TUESDAY</span>' + chips;
        } else if (!x.uw && !x.ul) {
          path += '<div class="rh-t rh-deb"><b>0-0</b><span>UFC</span><small>debut</small></div>';
          chips = '<span class="rh-chip rh-debc">UFC DEBUT</span>' + chips;
        }
        rhPop.innerHTML = '<div class="rh-card">' + x.head + '<div class="rh-path">' + path + "</div>" +
          '<div class="rh-st">' + x.st + chips + "</div>" + x.loss +
          '<div class="rh-hd"><span></span><span>Opponent</span><span>Odds</span></div>' +
          '<div class="rh-list">' + next + x.rows + "</div></div>";
        rhPop.hidden = false; rhAt = Date.now();
        document.documentElement.classList.add("qblog-on");
      });
    }
    function rhClose() { rhPop.hidden = true; document.documentElement.classList.remove("qblog-on"); }
    var rhAt = 0, rhHold = null, rhX = 0, rhY = 0, rhHeld = false;
    rhPop.addEventListener("click", function (e) { if (Date.now() - rhAt > 600 && !e.target.closest(".rh-card")) rhClose(); });
    /* his face, the same section the NFL card's hold uses (Jose, Oct 8,
       2026: "Is that where it is on the NFL?"): looked through whatever
       sits over it, and only the face itself -- not the strip above it or
       the name and price under it */
    function rhAtPoint(x, y) {
      var im = (document.elementsFromPoint ? document.elementsFromPoint(x, y) : []).filter(function (el) {
        return el.matches && el.matches('.gcard[data-sport="mma"] img.ffab');
      })[0];
      if (!im) return null;
      var r = im.getBoundingClientRect(), fy = (y - r.top) / (r.height || 1);
      return fy < 0.17 || fy > 0.78 ? null : im;
    }
    document.addEventListener("pointerdown", function (e) {
      rhHeld = false; clearTimeout(rhHold); rhHold = null;
      if (!e.isPrimary || !rhPop.hidden) return;
      var f = rhAtPoint(e.clientX, e.clientY);
      if (!f) return;
      /* his half of the card is his side: the left face is the left man */
      var card = f.closest(".gcard");
      if (!card) return;
      var cr = card.getBoundingClientRect(), fr = f.getBoundingClientRect();
      var side = (fr.left + fr.width / 2) < (cr.left + cr.width / 2) ? "l" : "r";
      rhLoad();
      rhX = e.clientX; rhY = e.clientY;
      rhHold = setTimeout(function () { rhHold = null; rhHeld = true; buzz(); rhOpen(card, side); }, 450);
    }, true);
    document.addEventListener("pointermove", function (e) {
      if (rhHold && (Math.abs(e.clientX - rhX) > 12 || Math.abs(e.clientY - rhY) > 12)) { clearTimeout(rhHold); rhHold = null; }
    }, true);
    ["pointerup", "pointercancel"].forEach(function (k) {
      document.addEventListener(k, function () { clearTimeout(rhHold); rhHold = null; }, true);
    });
    document.addEventListener("click", function (e) { if (e.target.closest && e.target.closest("[data-buzz]")) return; if (rhHeld) { rhHeld = false; e.stopPropagation(); e.preventDefault(); } }, true);
    window._rhOpen = rhOpen;
    /* the board never zooms (Jose, Oct 3, 2026: "I don't want it to zoom").
       iPhone Safari ignores user-scalable=no, so the pinch is refused, and a
       page that is zoomed anyway is snapped back to its own size by writing
       the viewport tag again */
    ["gesturestart", "gesturechange"].forEach(function (k) { document.addEventListener(k, function (e) { e.preventDefault(); }, { passive: false }); });
    document.addEventListener("touchmove", function (e) { if (e.touches && e.touches.length > 1) e.preventDefault(); }, { passive: false });
    function unzoom() {
      var vv = window.visualViewport, m = document.querySelector('meta[name="viewport"]');
      if (!vv || !m || vv.scale <= 1.01) return;
      var c = m.getAttribute("content");
      m.setAttribute("content", c.replace(/maximum-scale=[\d.]+/, "maximum-scale=1.0001"));
      setTimeout(function () { m.setAttribute("content", c); }, 50);
    }
    if (window.visualViewport) window.visualViewport.addEventListener("resize", unzoom);
    unzoom();
    /* the bars sit on the glass's bottom, not the page's: iOS can leave the
       layout viewport shorter than the screen (after a keyboard, or with a
       call running), and a fixed bar then floats halfway up the board
       (Jose, Oct 6, 2026: "what's up with the NAV?"). The gap between the two
       is measured and the bars are dropped by it. */
    /* and against the screen itself: the bar floated up again with no call
       on (Jose, Oct 6, 9:09 PM), so iOS had shrunk both viewports alike and
       the gap above read nothing. What the page loses against the screen,
       past what it lost when it opened, is put back under the bars -- never
       while he is typing, when the keyboard is meant to take that room */
    var GAP0 = null;
    function typing() {
      var a = document.activeElement;
      return !!a && (a.tagName === "INPUT" || a.tagName === "TEXTAREA" || a.isContentEditable);
    }
    function keepBars() {
      var vv = window.visualViewport, drop = 0;
      if (vv) {
        var gap = Math.round(vv.offsetTop + vv.height - window.innerHeight);
        if (gap > 2) drop = gap;
      }
      var lost = (screen.height || 0) - window.innerHeight;
      if (GAP0 === null && !typing()) GAP0 = lost;
      if (!drop && !typing() && GAP0 !== null && lost - GAP0 > 40) drop = lost - GAP0;
      document.documentElement.style.setProperty("--vvdrop", drop + "px");
    }
    /* the keyboard going away is when iOS leaves it short: ask it to settle */
    document.addEventListener("focusout", function () {
      setTimeout(function () { window.scrollTo(window.scrollX, window.scrollY); keepBars(); }, 120);
    });
    document.addEventListener("visibilitychange", function () { if (!document.hidden) setTimeout(keepBars, 120); });
    window.addEventListener("scroll", function () { if (!window._kbT) window._kbT = setTimeout(function () { window._kbT = 0; keepBars(); }, 250); }, { passive: true });
    /* when the bar is seen floating, what the phone says about its own
       screen is written to the state once, so the cause is read off the real
       numbers instead of guessed (Jose, Oct 6, 2026: "it happens when I
       scroll, anytime I scroll") */
    var DIAGAT = 0;
    function navProbe() {
      var bar = document.getElementById("sportbar");
      if (!bar || typing() || Date.now() - DIAGAT < 60000) return;
      var r = bar.getBoundingClientRect(), vv = window.visualViewport || {};
      if (r.bottom > (screen.height || 9999) - 160) return;
      DIAGAT = Date.now();
      var row = { ih: innerHeight, ch: document.documentElement.clientHeight, sh: screen.height,
                  vh: Math.round(vv.height || 0), vt: Math.round(vv.offsetTop || 0), vs: vv.scale || 0,
                  sy: Math.round(scrollY), top: Math.round(r.top), bot: Math.round(r.bottom), gap0: GAP0,
                  drop: getComputedStyle(document.documentElement).getPropertyValue("--vvdrop"),
                  sa: navigator.standalone ? 1 : 0, ua: navigator.userAgent.slice(-60) };
      var set = {}; set[String(DIAGAT)] = row;
      try {
        fetch("state?k=" + encodeURIComponent(typeof ARENAKEY !== "undefined" ? ARENAKEY : "arena-001bff8ddf784985"), { method: "POST", headers: { "content-type": "application/json" },
          body: JSON.stringify({ patch: { navdiag: { set: set } } }) });
      } catch (e) {}
    }
    window.addEventListener("scroll", function () { clearTimeout(window._npT); window._npT = setTimeout(navProbe, 400); }, { passive: true });
    if (window.visualViewport) {
      window.visualViewport.addEventListener("resize", keepBars);
      window.visualViewport.addEventListener("scroll", keepBars);
    }
    window.addEventListener("resize", keepBars);
    window.addEventListener("pageshow", keepBars);
    keepBars();
  })();
</script>

<!-- a push from a phone lands on the board by itself (tested Sep 19, 2026) -->