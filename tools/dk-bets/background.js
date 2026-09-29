/* A click on the icon asks the DraftKings page to read My Bets and send them
   to the board. The page sends them itself and then says how it went; a page
   that has to scroll and open every card can take longer than a message is
   kept open, and waiting on one here came back as DK? (Sep 26, 2026).

   The badge:  ...   reading
               a number, green   sent: that many open bets
               TAB, red   the page did not answer -- reload the DraftKings tab
               BAL, red   no balance on the page -- not logged in, or not loaded
               ERR, red   the board did not take it */
function badge(text, color) {
  chrome.action.setBadgeText({ text: text });
  chrome.action.setBadgeBackgroundColor({ color: color });
}

chrome.action.onClicked.addListener(async (tab) => {
  badge("...", "#8e8e93");
  try {
    await chrome.tabs.sendMessage(tab.id, { read: true });
  } catch (e) {
    /* a tab opened before the extension was loaded has no reader in it: put
       one in, and ask again */
    try {
      await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
      await chrome.tabs.sendMessage(tab.id, { read: true });
    } catch (e2) {
      badge("TAB", "#e2564d");
    }
  }
});

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || !msg.done) return;
  if (msg.done === "sent") badge(String(msg.n), "#3fbf5a");
  else if (msg.done === "nobalance") badge("BAL", "#e2564d");
  else badge("ERR", "#e2564d");
});

/* The login, kept fresh without an export: whenever a DraftKings page
   finishes loading, and every few hours while Chrome is open, the
   DraftKings cookies go to the board, which hands them back only to the
   reader. A login DraftKings has expired mends itself the next time
   DraftKings is open here (Jose, Sep 29, 2026: "without having to go back
   and forth"). */
const BOARD = "https://the-arenasports.pages.dev/bets?k=arena-001bff8ddf784985";
let lastSent = 0;
async function sendLogin(force) {
  if (!force && Date.now() - lastSent < 10 * 60 * 1000) return;
  const all = await chrome.cookies.getAll({ domain: "draftkings.com" });
  const cookies = {};
  all.forEach(function (c) { cookies[c.name] = c.value; });
  /* signed out: nothing worth sending */
  if (!Object.keys(cookies).length) return;
  try {
    const r = await fetch(BOARD, { method: "POST", headers: { "content-type": "application/json" },
                                   body: JSON.stringify({ login: { cookies: cookies } }) });
    if (r.ok) lastSent = Date.now();
  } catch (e) {}
}
chrome.tabs.onUpdated.addListener(function (id, info, tab) {
  if (info.status === "complete" && /^https:\/\/[^/]*draftkings\.com\//.test(tab.url || "")) sendLogin(false);
});
chrome.alarms.create("login", { periodInMinutes: 180 });
chrome.alarms.onAlarm.addListener(function (a) { if (a.name === "login") sendLogin(true); });
chrome.runtime.onInstalled.addListener(function () { sendLogin(true); });
chrome.runtime.onStartup.addListener(function () { sendLogin(true); });
