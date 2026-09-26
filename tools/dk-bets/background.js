/* A click on the icon: the page reads its bets, and this sends them to the
   board. The send is made from here, not the page, so DraftKings' own rules
   about where the page may post do not apply. */
const BOARD = "https://the-arenasports.pages.dev/bets?k=arena-001bff8ddf784985";

function badge(text, color) {
  chrome.action.setBadgeText({ text: text });
  chrome.action.setBadgeBackgroundColor({ color: color });
}

chrome.action.onClicked.addListener(async (tab) => {
  badge("...", "#8e8e93");
  let got;
  try {
    got = await chrome.tabs.sendMessage(tab.id, { read: true });
  } catch (e) {
    badge("DK?", "#e2564d");     /* not a DraftKings page, or it needs a reload */
    return;
  }
  /* no open bets is an answer too, and is sent; no balance means the page
     had not drawn, and nothing is sent */
  if (!got || !got.bets || typeof got.balance !== "number") { badge("DK?", "#e2564d"); return; }
  try {
    const r = await fetch(BOARD, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(got)
    });
    badge(r.ok ? String(got.bets.length) : "ERR", r.ok ? "#3fbf5a" : "#e2564d");
  } catch (e) {
    badge("ERR", "#e2564d");
  }
});
