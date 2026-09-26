/* Reads My Bets. DraftKings draws only about ten cards at a time and swaps
   them as the list scrolls, so the cards are collected while scrolling, not
   after. Each card is read by the test ids the page puts on it, with its own
   text as the fallback, so a renamed id does not lose the bet. */
(function () {
  function money(t) {
    const m = /\$\s*([\d,]+(?:\.\d\d)?)/.exec(t || "");
    return m ? parseFloat(m[1].replace(/,/g, "")) : null;
  }
  function tid(card, name, id) {
    const el = card.querySelector('[data-test-id="' + name + "-" + id + '"]');
    return el ? el.innerText.trim() : "";
  }
  function readCard(card) {
    const id = card.getAttribute("data-test-id").replace(/^bet-card-/, "");
    const text = card.innerText;
    /* every leg: a pick, its market and its price. The card's own heading
       ("2 PICKS PARLAY") uses the same id and is not a leg */
    const legs = [];
    card.querySelectorAll('[data-test-id^="bet-details-title-"]').forEach(function (t) {
      if (/\b(PICKS?|PARLAY|SGP)\b/i.test(t.innerText)) return;
      const lid = t.getAttribute("data-test-id").replace(/^bet-details-title-/, "");
      legs.push({
        pick: t.innerText.trim(),
        market: tid(card, "bet-details-subtitle", lid),
        odds: tid(card, "bet-details-displayOdds", lid).replace(/−/g, "-")
      });
    });
    const head = (text.split("\n").find(function (l) { return /Parlay|Straight|Single|SGP|Pick/i.test(l); }) || "").trim();
    /* the screen writes these in capitals, WON and LOST */
    const status = (/\b(Won|Lost|Open|Live|Cashed Out|Push|Void|Pending)\b/i.exec(text) || [])[1] || "";
    const total = (/(?:Parlay|Pick)[^+−\-\n]*([+−\-]\d+)/i.exec(text) || [])[1] || "";
    return {
      card: id,
      id: (/Bet ID:\s*([A-Z0-9]+)/i.exec(text) || [])[1] || id,
      head: head,
      odds: (total || (legs.length === 1 ? legs[0].odds : "")).replace(/−/g, "-"),
      status: status.toLowerCase(),
      wager: money((/Wager:[^\n|]*/i.exec(text) || [""])[0]),
      paid: money((/(?:Paid|Returned|Cashed Out)[^\n|]*/i.exec(text) || [""])[0]),
      topay: money((/(?:To Pay|Payout|To Win)[^\n|]*/i.exec(text) || [""])[0]),
      placed: ((/Placed:\s*([^\n]+)/i.exec(text) || [])[1] || "").trim(),
      legs: legs
    };
  }
  /* the cash balance: the largest dollar figure across the top of the page.
     The bonus sits beside it ($0.41) and is not the balance -- the first
     sync read that one (Sep 26, 2026) */
  function balance() {
    let best = null;
    document.querySelectorAll("body *").forEach(function (el) {
      if (el.children.length) return;
      const r = el.getBoundingClientRect();
      if (r.top > 160 || r.height === 0) return;
      const m = /^\s*\$\s*([\d,]+\.\d\d)\s*\+?\s*$/.exec(el.textContent || "");
      if (m) { const v = parseFloat(m[1].replace(/,/g, "")); if (best === null || v > best) best = v; }
    });
    return best;
  }
  /* a card shows its legs and when it was placed only once it is opened */
  function openCards() {
    document.querySelectorAll('[data-test-id^="bet-card-"]').forEach(function (c) {
      if (c.dataset.arenaOpened) return;
      const btn = [].slice.call(c.querySelectorAll("button, [role=button]")).find(function (b) {
        return /show legs|show details|view details/i.test(b.innerText || "");
      });
      c.dataset.arenaOpened = "1";
      if (btn) btn.click();
    });
  }
  async function readAll() {
    const seen = {};
    const grab = function () {
      document.querySelectorAll('[data-test-id^="bet-card-"]').forEach(function (c) {
        try { const b = readCard(c); seen[b.id] = b; } catch (e) {}
      });
    };
    /* the list scrolls in the page or in its own box, whichever is taller */
    const boxes = [document.scrollingElement].concat([].slice.call(document.querySelectorAll("div")).filter(function (d) {
      return d.scrollHeight > d.clientHeight + 200 && /(auto|scroll)/.test(getComputedStyle(d).overflowY);
    }));
    const box = boxes.sort(function (a, b) { return b.scrollHeight - a.scrollHeight; })[0];
    box.scrollTop = 0;
    let still = 0, last = -1;
    for (let i = 0; i < 400 && still < 4; i++) {
      openCards();
      await new Promise(function (r) { setTimeout(r, 300); });
      grab();
      const n = Object.keys(seen).length;
      still = n === last ? still + 1 : 0;
      last = n;
      box.scrollTop += Math.max(300, box.clientHeight * 0.7);
      await new Promise(function (r) { setTimeout(r, 350); });
    }
    grab();
    return { balance: balance(), bets: Object.keys(seen).map(function (k) { return seen[k]; }) };
  }
  chrome.runtime.onMessage.addListener(function (msg, _from, reply) {
    if (!msg || !msg.read) return;
    readAll().then(reply);
    return true;
  });
})();
