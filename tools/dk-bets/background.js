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
    badge("TAB", "#e2564d");
  }
});

chrome.runtime.onMessage.addListener((msg) => {
  if (!msg || !msg.done) return;
  if (msg.done === "sent") badge(String(msg.n), "#3fbf5a");
  else if (msg.done === "nobalance") badge("BAL", "#e2564d");
  else badge("ERR", "#e2564d");
});
