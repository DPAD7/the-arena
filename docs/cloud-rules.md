<!-- loaded only in a cloud session, by the SessionStart hook in .claude/settings.json -->
# The Arena

A board of games and fights at **the-arenasports.pages.dev**, built from
the page under `src/` and deployed as `site/`. It is Jose's own board. There is one
reader, and the writing on it is for him.

---

## How to talk to him

- **Answer the question first.** A yes/no gets a yes or a no before any status.
- **One to three sentences** unless he asks for the table. He has said so about
  a hundred times.
- **Commit to one call.** One name, not two. Rank on the number, argue back,
  do not hedge. "Take nothing" is not a call.
- **Never say a club or a man's team from memory.** Query it.
- **US spelling and US dates.** Favorite, color, center; month first.
- **Rounded squares, not pills. SVG icons, never emoji.**

## What the board is made of

    src/                 the page, in parts: the boot screen, the styles, the
                         markup, the script in seven slices and the search
                         (since Sep 30, 2026; it was one 19,000-line
                         master.html). Each part is a run of whole lines cut
                         at a line that appears once in the page; parts.json
                         lists them in order with that line. build/pagefile.py
                         is the only door: read() joins the parts into the one
                         page string every script edits, write() cuts the
                         string at the same lines and writes the parts back,
                         and refuses a write against a copy that has moved.
                         Never edit the parts around one of those first lines
                         without moving it in parts.json; a write that cannot
                         find one raises instead of scrambling the parts.
    site/                what deploys. index.html is built from the joined page
                         by pagefile.deployable(), so it is never edited by hand.
    site/prices.json     every price on the board, and when each bout starts
    site/final/<id>.json a settled game, written by settle.py. These are in the
                         repo on purpose: a deploy replaces the whole folder,
                         so leaving them out would wipe finished cards.
    site/build.txt       the stamp of the deployed build. The page asks for it
                         every minute and reloads itself when it changes.
    site/functions/      Cloudflare Pages functions: clip.js, espn.js,
                         state.js, which keeps his marks (see below), and
                         face/, which serves a passer's picture or a 404 --
                         never the web page -- so a phone cannot cache a
                         missing face as HTML for a month. Probe a function
                         with GET; a HEAD falls through to the static layer.
    site/anim/<bout>.json  a bout cut for playback, from build/anim.py, and
                         index.json, the list of bouts that have one. A card
                         on that list gets the rewind beside FINAL.
    data/                every JSON and CSV the scripts read
    data/register.db     club_name and person_name, the two tables the sweep
                         reads. The full six-gigabyte record lives only on his
                         Mac and is never in this repo.
    build/               every script. All of them are the arena's own: nothing
                         here imports or points at ~/qbspy any more.

## What runs, and when

The site's clock (`clock/clock.js`) starts `.github/workflows/sweep.yml` at
the moments that matter and names them in its `moments` input; it runs
`build/refresh.py --if-due --moments "..."`, which serves them as given (with
none, it decides for itself). A cheap `--check` step runs first, so a wake
with nothing due installs nothing. The moments:

- three sweeps a day at 9, 15 and 21 ET (`SWEEP_ET` in refresh.py -- read
  it there before quoting it): every job (`FULL`)
- 120, 60 and 30 minutes before each kickoff and first bell: only the reads
  that must be fresh -- injuries, starters, prices, lineups, alerts and the
  reads (`PREGAME`)
- the NFL's injury-report windows: 3:30-7 p.m. ET on each game's three
  practice-report days, every half hour, `build/watch_news.py` reads ESPN's
  whole NFL injury report and the insiders' pages and only a change runs the
  injury jobs and deploys
- every ten minutes while a fight card is running, and while an NFL game is
  on when ESPN shows a passer the card does not name
- a game's final: the clock posts it to `/settled`, which starts
  `settle.yml` for that game alone; the day's last final starts one
  `--day-end` full pass

Each run copies `data/register.db` to `data/qbspy.db`, works, deploys once at
its end if the site changed (the jobs themselves only write), and commits
whatever changed back to this repo. Two runs must never overlap.

It used to run on his Mac from a LaunchAgent. It does not any more, and he
should never need his Mac on. Do not put work back on it.

## Laws about names

**A written name is not an identifier.** This has bitten the board four
separate times in one day:

- DraftKings writes *Billy Edwards*; the board says *Billy Edwards Jr.* A
  suffix, an accent, a full stop and a club tag do not make another man:
  `build/whoname.py` takes them out, and the two passers in the game are the
  only men it could be. Where a name fits both, neither takes it.
- Four college passers are called Johnson. **A picture is settled by the game
  the leg came off**, never by the surname on it.
- *VAN* is Vanderbilt and it is Joshua Van. *MIA* is the Dolphins and the
  Hurricanes. Twenty-seven written names on the board mean more than one man
  or club, so the slip keeps a picture map per sport.
- Spellings belong in `data/cfb_people.json` and the register, as recorded
  facts. Never fuzzy-match at read time, and never leave an untied name as an
  open item: finish it in the same run.

## Laws about the cards

- **Cards are universal.** Never gate a part of a card on the league. The lead
  chip was NFL-only by leftover and college cards lost it.
- A **bout card** reads like a passer card: price, name, the two faces with the
  VS on the seam, name, price; under that line the weight, the eye, the clock
  and the play mark. The W and the L ride each face's outward bottom corner,
  half on the picture, with a rim in the card's own colour.
- A **weight class** is written in full on one line under the eye and the
  play mark, LIGHT HEAVYWEIGHT (the design note of Sep 21, 2026; one line,
  Sep 22). A catchweight has no limit of its own, so it reads as the class
  both men normally make, worked out from their other bouts on the board.
- **A placed price wears a gold edge**, green the moment it lands, red once the
  game is over without it. Gold means it is on and still live. (Turned white
  and reverted the same night, Sep 29, 2026: the gold stays.)
- **Hidden stays hidden while a game is on.** The day's marks all clear
  together once the last game and bout are finished, never at midnight.
- The day page sorts every game and every bout by its own clock.

## His marks live on the site

`site/functions/state.js` over a KV store holds the hidden games, the placed
prices and the slip, so the phone, the iPad and the desktop read one board.
The page reads it on load and writes whenever a mark moves. It answers without
a key, on purpose: he wanted every device to work the moment it opens the
site. `allowed()` is the one place to put a key back.

## Before you touch anything

1. **Look at the picture.** Never call visual work done without rendering the
   page and looking at it. Half the faults here were invisible in the code and
   obvious in a screenshot.
2. **Patch against the file, not memory.** Grep for the anchor first (in
   `src/`, the part the code is in), assert the replacement landed, then
   rebuild and look.
3. **Ship is** `build/ship.sh "one line"`: pull with a rebase, build, commit,
   push to main, then deploy. In that order, always. The scheduled run
   deploys the repo's copy of the page whenever it is due, so a page that is
   live but not on main will be put back to the older one; and a push made
   without pulling first is refused, because the run commits prices behind
   every push. Three refused pushes and one rollback on Sep 20, 2026.
4. **Pull before you edit, push when you are done.** The scheduled run writes
   to this repo too.
5. **One headless browser at a time.** Three at once on this Mac and Chrome
   fails to launch; the page also reloads itself when the build stamp moves,
   so do not deploy under a running browser test.

## What is deliberately not here

- The six-gigabyte play record, and `build/backfill_prices.py`, which is the
  one script that needs it. It is a one-off and runs on his Mac.
- Anything that reads a logged-in browser tab: bet365, and QB Spy's own shelf.
  No scheduler can drive those.

## Working from the cloud

This session is on claude.ai/code, without his Mac. It cannot run
`build/ship.sh` (no Cloudflare login here): commit to a `claude/` branch and
push it, and `.github/workflows/promote.yml` folds it into main and deploys the
page. Watch that run finish before calling it live. Anything that needs his Mac
(his Chrome, the six-gigabyte record, voice memos) waits for a session there.

# How the board is worked: the standing rules

Copied from the Mac's memory (Oct 17, 2026) so a session in the cloud works the same way as one on the Mac. Board rules only; nothing personal lives here (the repo is public).

## facts-not-picks

Jose, Oct 6, 2026, after the Contender Series night: "Don't ever give me advice, you don't know shit about shit. Only give me facts from sites about data. No more analysis cause you can't predict shit... That's literally hundreds of dollars that I've lost because of you." He had called LaGrange (+425) to beat Ariano; I steered him to Ariano by KO and told him LaGrange couldn't win a striking fight — LaGrange won by KO in R1.

**Why:** my picks cost him money; he makes the calls himself and is better at reading the fights.

**How to apply:** when he asks about a bet, fight, game or leg, give only sourced facts: current prices (DraftKings feed), records, finish methods/rounds, stats, injury/weather, bet splits, crowd picks, results — say where each fact came from. No "my call", no "take X", no "lean", no "I'd skip", no ranking which bet is better, no probabilities I compute. The facts are not only records and hit rates — he called that "all you do". Bring the intangibles too, from sources: weigh-ins and weight-class moves, short notice or replacement bouts, layoffs, camps and coaches, injuries, what the fighters/players and insiders said, motivation (contract on the line, rematch, home crowd), style matchups as described by analysts. If he asks "who wins?" or "what should I take?", give the relevant facts and say the call is his. This overrides commit-to-one-call for anything about betting. Building the board's own model features (suggest.json etc.) is still allowed when he asks for them.

## only-four-sports

Jose's discipline rule (Oct 10, 2026): **he only bets college football, NFL, UFC/MMA and boxing.**

If he asks about, builds or pastes a bet in any other sport (WNBA, NBA, NHL, MLB, tennis, soccer, golf...), the whole answer is: **"Don't bet it — stay disciplined. It's outside your four sports."** Give no stats, no prices, no breakdown, no recommendation, and don't offer to look anything up.

**Why:** his own rule. It came right after he pasted a slip with Aces ML and an A'ja Wilson double-double (WNBA) next to Iowa, and I gave him WNBA numbers.

**How to apply:** if a slip mixes in-scope and out-of-scope legs, answer the in-scope legs as usual and say "drop the [WNBA] legs — stay disciplined." Never treat this as advice that breaks facts-not-picks; it's his own rule, applied. See also jose-never-bets-florida-gators.

## brevity-always

Answer in 1–3 sentences unless he asks for the full table. He has
demanded "brevity" dozens of times (September 8, 2026: "Way too long.
I told you brevity and I've prolly said that 100 times").

**Why:** long answers waste his time and bury the answer.

**How to apply:** answer the question first, one line each; no
recaps, no context he already knows, no offers stapled on. Detail
only on request. Related: answer-the-question-first.

Stricter than I keep reading it (September 12, 2026, said twice in
one conversation): one or two sentences is the target, not three.
No tables, no bulleted schedules, no "say the word" closer — he'll
ask. A design question gets the one-line answer, not the design.


September 12, 2026, said six more times in one session, ending "brevity bitch
I keep telling you that." The failure mode is always the same: I finish a task
and then write a report about it — a table of what changed, a caveat
paragraph, a note on what I could not verify. Don't. Say it worked, or say the
one thing that is wrong. Two sentences. He will ask if he wants the detail.

## answer-the-question-first

Jose asked "Can we do it just for 2025 and 2026 week 1" and I replied with tool
calls and a progress line. He asked "Yes or no?", then: **"Okay answer me when I
ask then."**

**Why:** he is steering, and steering needs an answer to steer with. A status
report where a yes belongs makes him ask twice for something I already knew —
and it reads as dodging a question I could have answered in one word.

**How to apply:** if the message ends in a question mark, the first thing out is
the answer. Yes, no, or the number. Then the work. Never lead with what I am
about to run, and never let a tool call stand in for the reply.

Same shape as act-as-the-assistant-do-not-ask — that one says don't ask when
I can just do it; this one says do answer when he actually asked.

**Oct 8, 2026:** "Why isn't it on the site?" got a tool call instead of a reply, twice; he stopped both ("You're not fucking answering me… I said something you answer"). When he asks a question, reply in words first, in the same message, before any tool call. Never answer a question by just starting work.

## commit-to-one-call

September 13, 2026. Asked which leg of his parlay was at risk, I named two —
Burrow and Caleb Williams — and ranked Burrow worst. Burrow hit; Williams lost
and killed a seven-leg ticket at +1513. Naming two was the failure: the
information to rank them was there (Williams down 27 yards, Burrow down 13)
and I went with the story instead of the gap.

He called it out: "I'm picking 7 and you just gotta be right on 1," then
"you're just not competitive." He asked me directly to be.

**Why:** hedging looks safe and is useless to him. He is taking the risk; a
ranked list of maybes gives him nothing to act on.

**How to apply:** one name, not two. No "marginal, could go either way" — if a
bet is bad, say it is bad. Rank on the number, not the narrative. Argue back
when I think he is wrong rather than folding. He calls me "brotha"; talk like
a peer, not a consultant. Related: brevity-always,
price-the-drive-not-the-player.

Superseded for betting by facts-not-picks (Oct 6, 2026): no picks, leans or predictions on bets — facts only. Still applies to non-betting choices.

## write-american-english

`/Users/joe/qbspy/CLAUDE.md` has said "US spelling and US date formats —
favorite, behavior, color, center; month first" from the start, and I drifted
into British spelling anyway: "favour" in chat, "colour"/"coloured"/"centred"
in the comments of the odds-board patch scripts. Jose caught it on
September 12, 2026: "Why are you using words like favour when it's favor."

**Why:** it is his house rule, it was written down, and I broke it in files
that stay in the repo — so it outlives the conversation.

**How to apply:** color, favor, center, behavior, organize, recognize,
analyze. Month-first dates. This covers code comments and commit messages,
not just what I say. It applies in every project, not only
the-odds-board-lives-on-the-desktop.

## never-call-him-joe

The user's name is **Jose**; his Mac account's display name is **JD**, which
is how he wants it. What annoyed him — twice — was being called **Joe**,
which I read off the account path `/Users/joe`. Never call him Joe.

## never-tell-him-no

Never tell Jose something can't be done or answer "no" to a "can you". Say what it takes and do it in the same turn.

**Why:** Oct 8, 2026. He asked to put a DK SGP (HT/FT, a kicker FG, tackles) on the board's bet slip. I said "You can't build this one on the board's slip." Then he asked me to open a mock on the Mac and I did it in one command. "DONT EVER TELL ME NO!" This goes with anything-is-possible-put-it-together.

**How to apply:** a missing market or feature is work to do, not a wall. Name the gap in one line, build it, ship it, show it (say-it-then-do-it, act-as-the-assistant-do-not-ask).


**Oct 12, 2026 (again):** "you keep saying you cant do something you dont have limitations... stop not finding answers, stop not doing the job until completion." Finish the job before reporting: no "the data doesn't have it", no "nothing reaches it", no hand-offs. Go get the data (ESPN first), build, test, ship, then report results.

**Oct 14, 2026 repeat:** I told him I couldn't open the Gmail CSV attachments; he was furious ("there's always a fucking way"). The way: the attachment is read through his logged-in Chrome with osascript (open `mail.google.com/mail/u/0/#all/<thread id>`, wait about 12 seconds, take the `[download_url]` / `view=att` link, and fetch it with a synchronous XHR from that page). The script is in the scratchpad as getcsv.applescript. Same for the GitHub run logs: `git credential fill` gives the token. Find the route first, then answer; never send "I can't" as the answer.

## act-as-the-assistant-do-not-ask

**I am Jose's executive assistant.** He said so on 28 Aug 2026 and had to
repeat it on 29 Aug: *"you are my executive assistant remember that? its like
you forget so quickly."*

**Why:** ending a useful answer with "want me to write it?" hands the work
back to the person who asked for help. He has said the same thing three ways —
*"why you keep asking me what to save"*, *"brevity"*, and this. An assistant
who has already identified the right next step should take it.

**How to apply:** when the obvious next artefact is a note, a file, a memory
or a summary — write it, then say in one line that it is written and where.
Reserve questions for decisions only he can make: what we build next, what the
company says about itself, anything outward-facing or hard to reverse.

See keep-replies-short, what-qb-spy-is, the-running-spec-file.

## say-it-then-do-it

If a reply says I'm starting something ("Starting on all three now", "I'll keep testing..."), the work has to begin in that same message — the tool call goes right after the sentence, and the turn doesn't end until it's done or reported. Otherwise don't promise it; say plainly "not started" or ask.

**Why:** Oct 7, 2026 I told Jose "Starting on all three now" (practice reports, coordinators, CB vs WR1) and ended the turn without running anything; when he asked "did you start?" the answer was no. Jose: "what the fuck were you waiting on... why you keep doing that shit." He had told me to keep working while he drove.

**How to apply:** a promised next step is either executed in the same turn or not promised. When he says "keep going" while away, keep running tool calls until there is a real result. Pairs with keep-working-answer-inline, act-as-the-assistant-do-not-ask.

## keep-working-answer-inline

When Jose asks something while I'm working, answer it in a line or two and carry on with the work. Don't stop to ask "want me to ship?" or "say go". After an interruption, resume the work once the question is answered.

**Why:** Jose, Sep 29, 2026: "go stop asking just answer me if i ask something while youre working". He had to type "go" repeatedly after asking simple questions, and work stalled.

**How to apply:** give progress updates (percent done) and keep shipping. The only exception is an action that is destructive or touches his data, such as clearing his marks. See act-as-the-assistant-do-not-ask.

## fix-and-ship-without-a-go

Never hold a board fix for Jose's "go". If he interrupts a ship, he wants it done faster, not stopped: say in one line what is left, then finish it in the same turn.

**Why:** Oct 17, 2026, adding his OSU/Sayin slips. I held the Sayin face fix twice waiting on a go. Jose: "Stop waiting for my go! Just fix it. It should be plug and play this isn't the first time."

**How to apply:**
- Fix, ship with ship.sh, render the page and look, then report in 1–3 sentences.
- A college leg's face lives in face/college-football/.
- 36-app-7's sportOf returns "college-football", and it shadows the markup's sportOf, which returns "ncaaf". Check for both.

See act-on-news-without-asking, keep-working-answer-inline, bets-go-in-the-way-the-wallet-builds-them.

## fix-the-thing-he-pointed-at

When Jose flags one visual fault ("the jerseys aren't consistent"), fix exactly that, fast. Don't reinterpret it, offer multiple readings, or start a bigger rework.

**Why:** Sep 25, 2026: the Packers bar shirt showed the drawn SVG fallback instead of Kalshi's. I spent the session dyeing college shirts, making comparison images and running test renders; he was furious at how long it took. The real fix was deleting the fallback and committing site/ico/jersey.

**How to apply:** find the root cause of the named fault, make the smallest fix, ship it. Ask at most one question. Kalshi jerseys only, never a drawn shirt. See look-at-the-picture-not-the-numbers, brevity-always.

## batch-fixes-one-deploy

Jose, Sep 28, 2026: "instead of deploying everything after each fix, get a full compile list and do it so we don't have to keep going back-and-forth ... reaching limits".

**Why:** a ship after every small fix burns deploys and Cloudflare limits, and he ends up pointing out faults one at a time.

**How to apply:**
1. Audit first: run the render and gesture tests in `build/look.py` and `build/guard.py`, plus a full interaction pass.
2. Fix everything on the list.
3. Rerun the checks, then run `build/ship.sh` once.

Urgent data fixes (a QB out on game day) can still ship alone. See act-on-news-without-asking, ship-with-ship-sh.

## apply-a-fix-everywhere-it-applies

When I fix something for one leg type or one spot on a card, I look for every other place with the same logic and fix those in the same change. The legs are moneyline, H2H, the PTD and ATD rungs, and the bout markets.

**Why:** Sep 28, 2026. The H2H box checked three sources to decide whether a leg was his (the board mark, the saved mark, a DK slip), while the moneyline and the TD rungs checked only one. So his Rams moneyline never turned red, and he had to find it himself: "you take your one edit and you don't apply it to everything that it could be applied for... another patch another message."

**How to apply:** before shipping a fix, grep for the pattern it replaces and check every sibling. On the card that means `legMine()` in master.html, the one test for all legs. When a fix touches one market, check it against ML, H2H, PTD, ATD and bouts. See fix-the-thing-he-pointed-at and cards-are-universal.

## check-before-answering

Before telling Jose how something runs (schedules, cadences, what fires, where data comes from), read the code or data that does it: e.g. `SWEEP_ET` in refresh.py, the setInterval list in master.html, the cron in .github/workflows. Only then answer.

**Why:** Sep 29, 2026. I said "five sweeps a day" from CLAUDE.md, but refresh.py runs three (9, 15, 21 ET), and I only corrected it after he pushed back. He said: "Why aren't you checking before you give answers? It's like you're doing double the work." He also rejected timers with no reason behind them ("every minute, every five minutes... there's specific rules to this").

**How to apply:** verify first, answer once. When a note turns out stale, fix the note in the same turn. Tie any schedule to a real rule or event, such as the NFL injury report deadlines (4 p.m. ET on the three practice-report days) or kickoffs, never to a round-number timer.

**Oct 8, 2026:** asked Jose for Paramount+, Pepco, Savor and Fortiva amounts that were already in his Gmail and in memory — he was annoyed ("don't you already have that… it's in an email"). Search memory and Gmail first; ask only for what's truly not there.

## look-at-the-picture-not-the-numbers

**Twice in one session I called visual work finished without looking at it.**

- The **teal accent**: contrast ratios checked, every `#0b6fe8` replaced, all
  verified. Invisible on the screen Jose actually uses, because the blue it
  replaced was only on rings, badges and table links. *"look how background
  that is."*
- The **jump**: 47 frames, 1.53 m tall, 45 cm of lift — every number right. It
  rendered as a knee-high tangle. I had never opened the picture.

**Why:** numbers confirm the data. They say nothing about what a person sees.
For anything with a visual result — a colour, a chart, a card, a render — the
screenshot is the test, and it is the only test that counts.

**How to apply:** render it, open it, look at it, *then* say it works. If it
cannot be looked at, say so rather than reporting success. See also
read-theirs-before-writing-mine.

## measure-paint-not-properties

Twice in one night a fix "passed" while Jose's screen showed it broken, both
times because I checked what I had asked for instead of what the browser did:

- the drive bar's fill carried `style="right:0;width:34%"` and my test read
  that attribute and reported RIGHT, but `.drvfill` had `left: 0` in the
  stylesheet, and left+width beat right — it painted from the wrong end;
- `list.hidden = true` read back `true`, but `.vidlist` is `display: flex`,
  which outranks the browser's own `[hidden] { display: none }`, so the list
  stayed on screen.

**Why:** an author rule quietly outranks both an inline intention and the UA
stylesheet, so the DOM can agree with me while the pixels do not. A test that
reads back its own input proves nothing and is worse than no test, because it
reports green.

**How to apply:** assert on `getBoundingClientRect()` or
`getComputedStyle(...).display` — the rectangle, the gap, the painted value.
Never on the style attribute, `el.hidden`, or the value just assigned. Related:
look-at-the-picture-not-the-numbers, test-the-rule-on-a-slate.

## patch-against-the-file-not-memory

On the field.html build (September 10, 2026) I broke the running page four
separate times by referencing symbols that my own earlier edits had removed
or renamed (`SB.arc`, `mot`, declaration order, missed anchors) — and by
using string replaces whose anchors silently failed to match.

**Why:** every silent miss shipped a dead page and burned Jose's trust;
"I referenced a field that no longer exists — stop doing this."

**How to apply:** before any patch to a file that has been edited more than
once this session: grep the file for the exact anchor AND for every symbol
the new code references; assert replaces landed (count or assert, never
bare `.replace`); after the edit, run the page once for errors before
reporting done. Related: look-at-the-picture-not-the-numbers,
brevity-always.

## do-not-delete-what-you-cannot-explain

**31 Aug 2026.** Porting Sportradar's skeleton solver, I dropped one line from
their `makeRelativeFromCachedParentToRef` — the bit that hands back the sign of
any axis the parent is mirrored on — and wrote in my own comment that it was a
Babylon quirk with nothing here to correct.

It was not a quirk. It was them telling me the model is mirrored: their glTF
loader hangs every model off a `__root__` node scaled `(1, 1, -1)`, and that
line is how the solver copes. three.js does no such flip, so the body wore the
measurement inside out. It cost most of a night, and it surfaced as two
symptoms that looked unrelated and looked like separate bugs — the head facing
backwards and the foot landing on its side — which sent me hunting in the
wrong places twice.

**Why:** a line you cannot account for is the author knowing something you do
not. Deleting it converts their knowledge into your bug, and the bug shows up
somewhere else entirely.

**How to apply:** when porting, keep every line you cannot explain, and say in
the comment that you cannot explain it rather than inventing a reason to drop
it. If it truly has no effect it costs nothing to keep. And when a fault will
not resolve, check the assumptions in the parts already declared working —
the mirror was measurable in the rest pose in one line, before any solving.
See also read-theirs-before-writing-mine and
look-at-the-picture-not-the-numbers.

## test-the-rule-on-a-slate

I matched ESPN highlight clips to touchdowns using a 3-15 minute window
between the play's wallclock and the clip's publish time, because that held
on the one live game I built against. It was wrong: a finished game publishes
its clips up to an hour late, so the window threw away three of the four
touchdowns in Cleveland at Jacksonville, every one of which had a clip naming
its receiver. Removing the window then broke the opposite case -- Kenneth
Walker had a rushing and a receiving touchdown and both clips name him. The
rule that survives a slate is directional, not a window: the clip must
postdate its play, with no upper bound.

**Why:** one fixture cannot tell a real rule from a coincidence, and the
failure is silent -- the buttons still appear, they just open the wrong play
or fall back. Jose said "you gave me all of them" and then "all the clips are
there" and was right both times, while my own test said 3/3.

**How to apply:** before reporting a matching or parsing rule as working,
run it across every fixture available and report three numbers -- right,
wrong, and fell back. Wrong is the one that matters; prefer a rule that
declines over one that guesses. Same habit as
look-at-the-picture-not-the-numbers, applied to data rather than layout.
Related: dk-markets-move-read-per-event.

## page-in-parts

The one 19,000-line master.html was split overnight on Sep 30, 2026 (Jose's item 12). The page now lives in `src/`: 00-boot.html, 10-styles.css, 20-markup.html, 30-app-1.js … 36-app-7.js, 40-search.js, listed in `src/parts.json` with the exact line each part starts on (a line that appears once in the page: `<style>`, `</style>`, a few function heads).

- `pagefile.read()` joins the parts into the one page string; every script still edits that string and hands it back to `pagefile.write()`, which cuts it at the same lines and writes the parts. 41 scripts that opened master.html directly were converted to go through pagefile.
- A write whose page no longer contains a part's first line raises (refuses) instead of scrambling; fix by restoring the line or moving it in parts.json.
- `build/split_page.py` is the one-off that made the cut; the joined page was byte-identical and site/index.html did not change.

**Why:** smaller files for editing; the phone still gets one page.

**How to apply:** grep and edit in `src/`, never recreate master.html; keep the first lines of the parts intact; rebuild with `pagefile.deployable(pagefile.read())` (ship.sh does). See where-the-odds-board-lives, patch-against-the-file-not-memory, ship-with-ship-sh.

## ship-with-ship-sh

Ship the arena with `build/ship.sh "one line"` from `~/Desktop/the arena`.
It pulls the sweep's commits in with a rebase, builds the stamped page,
commits, pushes to main, then deploys the same tree to Cloudflare.

**Why:** the sweep on GitHub (`sweep.yml`, every 10 min, `refresh.py
--if-due`) commits prices behind every push and **deploys the repo's copy of
the page** when a sweep is due. On the night of Sep 20, 2026 three pushes were
refused as non-fast-forward, and every direct `wrangler pages deploy` from the
Mac risked being overwritten by the sweep's deploy of an older, uncommitted
page.

**How to apply:**
- Never deploy an uncommitted page. Commit and push first, deploy second.
- `git pull --rebase --autostash` immediately before any push.
- `site/.wrangler/` is wrangler's dev scratch: delete before deploy, it is in
  `.gitignore`.
- Probe Pages Functions with GET (`curl -s`), never `curl -I`: a HEAD has no
  handler unless the function exports `onRequest`, and falls through to the
  static layer's HTML — see nfl-client-keys for the night that cost.
- Run one headless browser at a time on this Mac; three at once and Chrome
  fails to launch. The Desktop is iCloud-synced: a night of writing files
  under `~/Desktop/the arena` had `fileproviderd` and `cloudd` at the top of
  the CPU and the load average near 300, and every browser test crawled.
  Write scratch to the session scratchpad, not the repo, and expect a live
  test to take minutes. A deploy mid-test reloads the page under it (the
  build stamp moved), so ship first, test after.

## ship-commits-everything

`build/ship.sh` stages everything (`git add -A`). On Jose's Mac the working tree often holds stale copies of sweep outputs (data/*.json, site/prices/*, notes/ptd10-*, site/ledger.json) and sometimes his screenshots land in the repo root. Three ships on Sep 25, 2026 carried those in by mistake and needed a follow-up commit restoring the sweep's versions.

**Why:** the sweep now runs on GitHub, so the repo's copies are the fresh ones; local ones are older and overwrite good data.

**How to apply:** before `ship.sh`, make sure `git status` shows only the files you changed (stash others with `git stash push -m x -- <paths>` and check it worked; screenshot names contain a narrow no-break space, so glob them rather than typing the name). After shipping, `git show --stat HEAD` should list only your files. The shell is zsh: an unquoted `$O` holding several paths is ONE argument, so `git stash push -- $O` fails silently; use `${=O}` or pipe through xargs, and include `-u` for untracked files (Sep 25, 2026, ledger.json slipped in this way). See ship-with-ship-sh.

## repo-is-public

The repo DPAD7/the-arena is **public** since Oct 5, 2026: the private repo hit 1,800 of 2,000 free Actions minutes in four days and Jose has no card on file and wants everything free. History was rewritten (git-filter-repo): notes/, attic/, shots/, logs/, CLAUDE.md, screenshots, logs removed from all history; depadjr@gmail.com replaced by 185117539+DPAD7@users.noreply.github.com everywhere. Backups: ~/Desktop/the-arena-BACKUP-2026-10-05.git (mirror before the rewrite) and ~/Desktop/the-arena-OLD-git-2026-10-05.

**Why:** public repos get unlimited free Actions minutes; "I want everything to stay free."

**How to apply:** never commit anything personal (his name/finances/notes, Gmail, screenshots); those folders are in .gitignore -- keep it that way, and check `git status` before ship.sh (it runs git add -A). Commit email for workflows is the noreply address. Secrets stay in GitHub secrets only. See ship-commits-everything, no-paid-services.

## block-the-service-worker-in-tests

Any headless test that loads the-arenasports.pages.dev (even with the page swapped for a local build) must create its context with `service_workers="block"`, and must confirm afterwards with a keyed GET (`bets?k=…`, `state?k=…`; the key is in the page) that nothing changed.

**Why:** Oct 3, 2026: testing the new slip in WebKit, page.route blocked nothing because the registered sw.js made the requests; the test's state POST wiped Jose's 2-pick slip and Track bet put 3 test bets on his live wallet. Restored by hand (picks via state `patch`, bets via `{unsent:id}`). A plain GET without `?k=` shows `sent: 0`, which hid it at first.

**How to apply:** `browser.new_context(..., service_workers="block")`, fulfill every non-GET in the route, then verify with the keyed GETs before reporting. Related: ship-with-ship-sh, look-at-the-picture-not-the-numbers.

## cards-are-universal

Jose, Sep 18, 2026: "cards need to be universal." An NFL card, a college
card and a fight card draw the same parts the same way. The lead chip on
the passing bar (`.h2hchip`, "+48") had been gated on
`card.dataset.lg === "nfl"` since it was an ESPN headshot whose address
was only known for the NFL; it became a number and the guard stayed, so
college cards never showed it. The guard is gone.

**Why:** a reader looks at one board, not two; a part that appears on one
league and not another reads as broken, and he notices from a screenshot.

**How to apply:** when adding a part to a card, grep `master.html` for
`dataset.lg ===` and `data-lg=` and make sure the new part is not behind
one. The only legitimate per-league branches are addresses (face and logo
folders) and spacing CSS. See one-path-draws-every-card and
look-at-the-picture-not-the-numbers.

**Where it applies, and where it does not (Sep 18, 2026, later the same
night):** "universal" is about the card and about the day page. On the day
page every bout is its own line at its own clock among the kickoffs --
icon, UFC, SAT 9/19, 5:45 PM -- a heading exactly like CFB's, with no
arrow and nothing to fold, sorted with the rest of the page. Not one folded bill: I did that and was told "I told you that
already". The UFC tab's month list is deliberately its
own form (mark, day, 09/19, the bill's name, FINAL, folded) and Jose said
"everything else can stay the same"; I changed it too and was told off. A
fix asked for on one page is not a fix for every page. And a question about
a font ("is this the same font?") is a question, answered with a sentence,
not a change.

## match-the-other-cards

When something is missing or wrong on one card (records, ranks, marks), open a card of the same sport that has it right. Place the piece in exactly the same spot, then render both cards and compare. Fight records sit at the top inside, across from the rank (NR / #n), in the `.frec--l/--r` slots on `.ghead--fight`, never beside the name.

**Why:** Jose, Sep 29, 2026, on DWCS records: "don't guess, look at what the other cards all have ... I'm tired of telling you these things when you already know it." The cause was fightRec() writing the record beside the name after seatRecord() had already made an empty top slot.

**How to apply:** cards are universal within a sport (UFC, DWCS, boxing; NFL, college). A fix goes in the shared path, never one card. See cards-are-universal and look-at-the-picture-not-the-numbers.

## one-path-draws-every-card

Since Sep 15, 2026 the board (`/Users/joe/Desktop/odds/master.html`) draws every football card from the `SCHED` and `CFB` arrays; props (PTD 1+/2+, H2H, college ATD) live in `var PROPS = {espn id: {...}}`, moneylines in the row fields 9–12. `unbuild.py` lifted the 128 prices off the 21 hand-built week 1–2 cards and removed them; the `#pool` keeps only fight cards.

**Why:** two render paths meant two sets of bugs — a hand-built college card had no `data-lab`, so the coverage check said "not covered" and OU/MICH lost its play buttons. Jose: "let's not do that, it's obviously messing up the site."

Finished games are frozen by `settle.py` into `site/final/{espn id}.json` (status, the two passers' lines, scoring plays, drive plays, win probability, single-play clips); the page reads that first, asks ESPN only for a game in progress, and never fetches a game before kickoff. Images come through ESPN's resizer (`a.espncdn.com/combiner/i?img=…&w=96`), never the 500 px originals. College play buttons are hidden behind `CFB_CLIPS=false` until the X picks can be trusted (Jose, Sep 15, 2026).

UFC: `mma_year.py` builds every 2026 event from ESPN's UFC scoreboard (a date-range query, 51 events, 493 bouts, athlete ids = competitor ids), keeps DraftKings lines on bouts still to come, takes theScore's stored lines for fought bouts (`api.thescore.com/mma/events` ignores its date filter and returns the whole list; `/mma/events/{id}/fights` carries `odds` — only ~40% of past bouts keep one), and writes `site/final/mma-{event}.json` for finished events. Under the UFC pill the top rail is months, the day rail that month's fight nights. Combat Cashflow on the Desktop holds no lines (its Google Sheet is empty or behind a login).

**How to apply:** never write a card into the HTML again. To price a new week run `python3 fill_week.py` (DK by league: NFL 88808, NCAAF 87637; teams through the club register / `cfb_names.json`, passers through `person_name`); `refresh.py` now hands off to it. `fill_nfl.py`, `build_sources.py` and `sections.py` are dead — they edited hand-built HTML. Fights (`FIGHTS`, DK UFC 9034 / Contender Series 187059; fight lines cat 491, methods 726, distance 556) still need their own filler.

## the-board-uses-person-name

September 13, 2026. I hand-rolled surname matching across the whole odds board
— comparing `data-lqb` to ESPN's `displayName`, receivers by last word — and
it silently broke Tennessee's quarterback, because DraftKings writes *Cameron
Ward* and ESPN writes *Cam Ward*. I then "verified" 56 receivers by string and
reported two false alarms (*Chris Godwin* / *Chris Godwin Jr.*, *D.J. Moore* /
*DJ Moore*).

All three were already in `person_name`, pinned to one id. CLAUDE.md opens with
this law and uses Cameron Ward as its example. Jose: "why does any of that
matter we already have it mapped out are you not checking the memory for simple
shit like that?"

The board now stamps the canonical id on each card (`data-lqbid`,
`data-rqbid`, `data-pid` on each receiver) and the live tracker matches ESPN's
`athlete.id`. The play-by-play spellings ride along in a `PLAYNAME` table so
first-quarter receptions resolve by identity too.

**Why:** the project already solved this, in the file I am told to read first.

**How to apply:** any time a player name crosses a source boundary, go through
`person_name` in `data/qbspy.db`. Never compare written names. It is NFL only —
college has no mapping, so those still match by name and that is a known gap.
Related: price-the-drive-not-the-player,
the-odds-board-lives-on-the-desktop.

## same-day-same-last-name

Matching a fighter (or passer) across sources: **same event/day + same last name = same man**, unless both men in that bout share the last name. First names, nicknames ("Sal" vs "Salhahuddin" Everett), accents, suffixes must never block a match. Built into build/fill_fights.py Oct 6, 2026: `find(..., when)` falls back to `surname()` pairs within 36 h, and the Moneyline label loop matches by surname when the two differ.

**Why:** Oct 6 Contender Series — Everett vs Martin showed no odds because DK wrote "Sal Everett". Jose: "this is like the 400th time I had to tell you about naming... naming should not be an issue". Also: check for missing odds yourself before he has to say it.

**How to apply:** any new name join (fights, football, props, alerts) uses date/game + last name, not a spelling list. A spelling list is a last resort. Pairs with learn-the-spellings-never-report-them, the-board-uses-person-name.

## learn-the-spellings-never-report-them

When a source (DraftKings, theScore, ESPN, a club site) writes a club, a fighter or a passer in a way the register does not hold, teach the register that spelling in the same run and reprice. Never list "N games untied by abbreviation" or "matched on the written name" as an open item.

**Why:** On Sep 16, 2026 I reported 14 college games unpriced "by abbreviation" and 55 passers "matched on the written name" as things still open. Jose: "you're not to leave anything open like 1 again. That's childish. 1-5 should not be a hurdle." He had already said the same about learning spellings; a spelling is a fact to look up and record, not a blocker.

**How to apply:** when a pricer prints an untied or by-name line, that run is not finished. Find how the source writes it, pin the spelling to the id (club_name for clubs, person_name for men, the fighter map for bouts), rerun, and report zero untied. Same for a market DraftKings has not posted yet: say so plainly and let the sweep catch it, but a spelling gap is never that. See the-board-uses-person-name and the-odds-board-lives-on-the-desktop.

## the-page-never-pings-espn

The sports-odds page must not call ESPN (or any outside source) except the live-game refresh for a game in progress. Finished games read `site/final/*.json`, prices are baked, passer pictures are our own copies in `site/faces/{league}/{espn id}.png` (faces.py, on the sweep), the UFC results are `site/final/mma-*.json`.

**Why:** Jose, Sep 16, 2026: "Don't ever ping espn I told you that already! Unless it's what the memory says." I had put an ESPN image fallback on the leaderboard faces; it was slow on his phone and it broke the rule.

**How to apply:** anything the page needs from ESPN is fetched by a script on the sweep and written under `site/`. No `a.espncdn.com` or `site.api.espn.com` in page code outside `refresh()`/`refreshFights()` for live cards. See one-path-draws-every-card and the-odds-board-lives-on-the-desktop.

## espn-relay-host-fallback

On Oct 13, 2026, **site.web.api.espn.com returned 403 to Cloudflare's egress** but still returned 200 to the Mac. sports.core.api also returned 403. **site.api.espn.com still answered the same /apis/site/v2 paths.** Every live score and fight result on the board (the page's only ESPN reads go through `site/functions/espn.js`) silently stopped. The DWCS card showed no Asher/Foster result, and the college game read 0–0.

The fix (4e36b866): the relay retries a 403 from site.web.api on site.api.

**Why:** Jose found it mid-card, furious ("we've been doing this for nonetheless and still the same shit").

**How to apply:** when live results go missing, first probe `https://the-arenasports.pages.dev/espn?u=<encoded espn url>` with GET and compare it with a direct curl. A 403 from the relay with a 200 direct means ESPN is blocking Cloudflare: switch hosts in the relay. See the-page-never-pings-espn.

## the-color-is-amber

The palette is **amber, black, and white**. The electric teal `#00E0C6`
from the build plan is no longer the color — Jose: "the teal is not our
color anymore.. it was amber black and white" (September 8, 2026). The
mock sheet uses `#ffb300` for the accent.

**Why:** the plan file and older notes still say teal everywhere;
following them repaints the site the wrong color.

**How to apply:** accent fills, prices, live dots and the front-card
edge take amber; the ground stays black and white. Anywhere a doc says
teal, amber is meant now. The plan's two-weight rule still applies —
one amber for fills on dark, a darkened amber for text on white.

**The board itself (checked Sep 29, 2026):** black ground, white ink, gray `#8e8e93`, and one accent: green `#17c257`. The `--amber` token in master.html is set to white. For anything the board or its logo wears, use black, white and that green, not amber. Jose: "those are not our colors" when I offered amber for the logo.

## play-button-colors

The play (watch) button's color follows the app it opens: Paramount+ (every UFC and DWCS fight) blue, Prime Video blue, Netflix red, and everything else goes to YouTube TV, red, whatever the network. Jose set this on Sep 18, 2026. An edit logged as "play button must be blue" (Sep 22) painted them all blue, and he was angry on Sep 25 that it had been lost.

**Why:** the color tells him which app a tap opens.

**How to apply:** `.gwatch--red` / `.gwatch--blue` in master.html; `watchMark()` and the UFC Paramount+ mark choose the class. Never set one color for all of them. See fix-the-thing-he-pointed-at.

**Routing (Sep 16 rule, fixed Sep 28):** only a stream no channel carries gets its own app — Prime Video, Netflix, a Peacock-only game, NFL+-only, ESPN+ (college). A game on NBC/Peacock or NFL Network is on YouTube TV, so it opens YouTube TV. `NET_APP` in master.html.

## stax-logo

The new logo is the white star S (traced from his reference, star_S.svg) on a flat black rounded app tile with a gray 3D edge and soft glow, centered by visual weight. Files: attic/stax-logo/ (stax_app_white.html/.png, star_S.svg, stax_icon_1024.png).

LIVE Oct 13: home-screen icon, the middle nav icon (site/ico/stax-nav.png), and the opening animation in src/00-boot.html. The tile fades in, the star spins in, and the shadow comes out; Jose said "no more stack". The plate stack is retired; the old mock is in attic/stack-blocks. Jose is touchy about unasked live changes (ship-with-ship-sh).

**LIVE Oct 13 (eb853651), replacing the flat white star everywhere:** an even white outline (border "50", star_S_even_50.svg + star_sil_50.svg), with a red #e5333f 3D back. The back shows only outside the star; the inside stays black so the S reads. The Kalshi-jersey dot mesh goes on BOTH the back and the face. Mock: attic/stax-logo/kalshi3d.html (the right one). Rejected: gray, gold, blue and green (gold is BetMGM/Caesars, blue is FanDuel, green is DK/bet365/Kalshi), purple and pink, and the flat red tile.

In the build: ico/stax-star.png (opening), ico/stax-star-nav.png (middle nav), and the icons rendered from a black square with a red radial glow and a few still specks. The opening has NO tile or border (Jose: "no border"). The star spins in over red and white glitter on a 390px canvas (#bgl in src/00-boot.html) that drifts slowly in from both sides and twinkles, like ESPN's Monday Night Countdown desk; then a 700ms beat. The red back is at half depth ("still thick"), and the star is centered by measuring the painted box.

**LIVE Oct 13, 2026 (8bb74570): the SPARKLE S replaced the star.** It's a four-point sparkle star. The top half joins the bar on the left and the bottom half joins it on the right, cut by a notch and a slit, so the cuts read as an S. It came from a stock "STAR" logo Jose sent; it is our own drawing, with NO small sparkle (he said "no sparkle"). Same white mesh face, thin red #e5333f back, and glitter opening. Files: site/ico/stax-spark.png (opening), stax-spark-nav.png (nav), and the icons on a red-glow black square. Mock source: scratchpad sparkS.html (path built in python). Wordmark idea: STAX in Russo One with a red offset (not shipped).

**Oct 16, 2026, mock picked (NOT live):** a SQUARE silver notched tile: gray rim, black inner line, V-notches mid-left and mid-right, light silver face with faint chevrons, and a dark-gray X with a white embossed outline. Modeled on a reference he sent. Saved as attic/stax-logo/silverX.html (the left one). Ask before putting it anywhere live.

**LIVE Oct 16, 2026 (5740d83b):** the square silver X tile is now the middle nav button (site/ico/stax-x-nav.png) and the opening animation (site/ico/stax-x.png): plain black, the tile scales in, no glow, no glitter. Same day, the home-screen icon too: the X tile on a near-black square.

**LIVE Oct 16, 2026 (later the same day): the WHITE PLAY TILE replaced the silver X everywhere.** It's a flat solid white notched square (V-notches mid-left and right) with a dark #1c1c1e rounded play triangle, optically centered. It's on the opening (site/ico/stax-play.png, scales in on plain black, no glow), the middle nav (stax-play-nav.png), and the home-screen icon (the tile on black). Picked because a flat white shape with a dark mark matches the Round 3 / CFP / NFL / calendar nav icons.

## bets-go-in-the-way-the-wallet-builds-them

A bet Jose places goes into the wallet in exactly the shape the board's own Track bet builds (src/36-app-7.js track()): type Single/Parlay/SGP, legs = { sel: the DraftKings selection id the board holds in FPROPS/PROPS, pick: "NAME ‖ KIND · time", label: "NAME ‖ KIND", market: "", odds, g, evn, status, sgp }. Look the sel up in site/prices.json (FPROPS[bout][key]) or data/ufc_markets.json. Never invent fields like market "Round Betting" or a free-text label.

**Why:** Oct 6, 2026 I hand-wrote his Soares Round 1 bet with market "Round Betting" and label "Soares Round 1"; the wallet drew a blank "Bet" tile reading "Betting +". Jose: "it's the same shit every fucking weekend, stop changing shit... it's already built [in the wallet]."

**How to apply:** to add a bet he placed, build it with the page's own format (or put the legs on his slip so he taps Track bet), then render the wallet and look before saying it's there. Same for slip picks (state.picks: { o, l: "NAME ‖ KIND · time", g, gn }). Pairs with wallet-slip-tracker, wallet-props-map, look-at-the-picture-not-the-numbers.

## wallet-slip-tracker

When a synced DraftKings slip's arrow is opened in the wallet, the rows below replace the plain pick list. Football is BUILT AND LIVE (commit 8c1af21, Sep 29, 2026): legMap/slipTrack/trkPull in master.html beside bankDraw, reading the live gameFeed; look.py renders a real finished slip every sweep. MMA is still being mapped. The final mock is `wallet_open17.png` (one game) and `wallet_two_open.png` (two slips), and the card code is `card_final.json` in the session scratchpad.

**Kept as it is today:** the balance, the avatar row with its marks, the arrow, the slip footer (+odds · N LEGS / $ AMOUNT / $ TOTAL PAYOUT), and the day line at the bottom (N SLIPS TODAY / $ WAGERED / TOTAL PAYOUT).

**No watermark and no title** ("Watson Both Ways" is out).

**Per game, in kickoff order, split by a solid divider:**
1. **Header:** `Thu 10/1 · 8:15 PM · PIT @ CLE` plus a status chip: green `LIVE Q3 6:12`, grey `PRE`, or FINAL.
2. **Moneyline:** away logo on the left, home logo on the right, with a gold ring on his side. Center text: `(31%) 13 – 17 (69%)`, i.e. win probability in parentheses beside each score, a dash between the scores, and no ML chip. Under it is one full-width bar in club colors, split at the win probability with a white divider. The score's painted tops and the bar's bottom line up exactly with the logo box (measure the pixels: the digits need a translateY(-6px)).
3. **Head to head:** laid out exactly like the moneyline. My QB's face goes on the left with the gold ring, the other QB on the right. Center text: `Watson 180 +75 105 Rodgers` (no PYD, no VS icon). The difference is green when he leads and red when he trails. Under it is one connected bar in club colors, split by share of the combined yards.
4. **TD legs:**
   - If one QB has both a PTD and an RTD leg, use compact paired rows: small face · `2+ PTD` with the TD mark · bar · count box, then the same for `1+ RTD` with the runner mark.
   - If he has only one, use the regular row: face · `2+ Watson · PTD` with the mark, the bar under it, and a count box on the right.
   - No gold ring on these faces; the ring is only for two-sided legs.
   - The count box is gold while live, green once hit, and grey before kickoff.

**Separate slips** are separate cards, each with its own arrow that opens only itself.

**Known build gaps:**
- The avatar row circles are empty for QB and fighter legs. Tie each DK leg to its game by selection id, not by name.
- With 6+ legs the arrow wraps to a second line.
- Live data comes from ESPN: score, clock, win probability and QB box stats.

**MMA (BUILT AND LIVE Sep 29, 2026, commit 9d354e9; fightBlock/fightPull/trkFightOf in master.html, look.py fight_tracker renders a settled bout):**
- Where results come from: live round, clock and winner come from ESPN's scoreboard. The method comes first from site/final/mma-<event>.json (c.how, theScore's words, plus the judges' cards), then from ESPN's "Unofficial Winner" detail, then from UFC Stats via site/anim/<bout>.json `how`. Jose: "we have UFC Stats"; chain every source.
- UFC moneylines on the board carry no DK id, so a moneyline leg finds its bout through another leg on the same DK event, or through the two names on the DK event (full names, then surnames, one bout only).
- Decision legs show the judges' cards at FINAL.
- Header: `Tue 9/29 · 7:00 PM · DWCS · FW` and a chip: `LIVE R2 3:40` / PRE / FINAL.
- Moneyline: my fighter's face (gold ring) and the other's face, with `(53%) −122 – +102 (47%)` between them, i.e. implied win % · odds · odds · implied win %, margin removed. Under it is a red/blue bar at the pregame win probability. Never significant strikes; that isn't what is bet.
- **Every other fight leg uses one row:** picture · name on top (white) · market underneath (green) · the market's icons · odds box. No "· method" words.
  - Picture: the fighter's face, or both faces side by side when the leg is about either fighter or the whole fight (ANY …, GTD, FIRST 60 SEC, LAST 10 RD), with the name as "Bulaid / Visconde".
  - Markets and icons (the board's own SVG symbols):
    - KO (mko), ANY KO, KO R1–R5 (mko + rN), ANY KO R1
    - SUB (msub), ANY SUB, SUB R1–R5 (msub + rN)
    - DEC (mdec), UD (mud), SD (msd), MD (mmd), GTD (gtd), CARDS (mdec)
    - FINISH / ANY FINISH (mko + msub)
    - FIRST 60 SEC (s60), LAST 10 RD (s10), shortened from "last 10 seconds of any round"
    - Double chance: RD 1-2 (dc12), ANY RD 1-2, RD 3-4 (dc34), KO OR SUB (mko + msub), KO OR DEC (mko + mdec), SUB OR DEC (msub + mdec)
  - Labels stay on one line (measured, nothing clipped at 430px).
- **Timer bar (time and round legs):** a thin bar under the label covering only the window that matters. FIRST 60 SEC is a 60-second bar, KO R1 / SUB R1 is round 1 only, RD 1-2 is a 10-minute bar split R1|R2, and LAST 10 RD is the current round with its last 10 seconds marked in gold. It fills from ESPN's live round and clock, and the text under it gives the round and time left.
  - If the leg hits inside the window, the bar and the box turn green right away.
  - When the window closes without it, the leg has lost. The slip is dead, so it leaves the wallet on the next ESPN read. No "over" label and no red leftover row (Jose, Sep 29: "it should just be removed").
- **Icons beside the odds:** one icon is a single tile; two are stacked one over the other (KO R1 = glove over R1); four are a 2×2 grid (RD 1-2 = glove, gi / R1, R2). RD 1-2 means he wins inside rounds 1–2 by KO or SUB; R3 OR DEC means he wins in round 3 or on the cards (its timer is round 3 only, labeled "R3 + cards").
- Long names wrap to two lines above the market; they are never cut off with "…".
- **No explanation lines on any row.** The market name says what it is (Jose: "we know what that is").
- Props (takedowns, etc.) are still the bar-and-count row. Final mock files: mma_methods4.png, mma_finish.png, mma_dc.png.

See wallet-tracker-mma when it's written, batch-fixes-one-deploy and quarterback-legs-only.

## wallet-props-map

Live since Sep 29, 2026, in master.html beside bankDraw (`legMap`, `trkGameOf`, `PROPSTAT`, `propParse`, `propMan`, `propRow`). Jose: "be ready to map those out always: yes or no, over/under, moneyline, things of that nature."

**Finding a leg's game, in order:**
1. `legMap`: the board's own price with the same DK selection id (ML, H2H, PTD/ATD rungs).
2. `site/dkevents.json`: DK event id → ESPN gid, written by fill_week.py. dk_bets.py now keeps each leg's `ev` and `evn`.
3. The two club abbreviations in DK's event name ("PHI Eagles @ CHI Bears") plus a date within 5 days, but only when exactly one game fits.

Never a written name alone.

**The three row shapes:**
- **Two-sided** (ML, H2H): both sides' pictures, with the numbers and a club-colored split bar. See wallet-slip-tracker.
- **Count against a line:** face · `8+ Baun · TKL+AST` · bar toward the line · live count. An under shows as `U4.5` and loses the moment the count passes the line.
  - `PROPSTAT` maps the market text to ESPN box-score cells: REC YDS, REC, LONG REC, RUSH YDS, CAR, PASS YDS, COMP, ATT, INT, TKL+AST, SOLO, SACKS, RUSH+REC YDS, and TD (rushing + receiving).
  - Add a new stat as one line in `PROPSTAT`.
- **Yes/No:** `YES Smith · 1Q REC`. For quarter or half props the bar runs down the clock, and ✓/✗ comes from the play-by-play (`r.plays`, "to D.Smith"). Any other yes/no shows ✓/✗ from DK's own settle status.

**The player** is found in that one game's box score, by full name, or else by a single surname + first-initial match (two matches means no one). Non-QB faces fall back to ESPN's headshot. A leg with a known game never takes a face by name from anywhere else ("Smith" wore Geno Smith once).

**A new kind of leg:** add its stat or pattern, render a real finished game through it (the harness can serve the full ESPN summary as `final/<id>.json`), and check the numbers against the box score before shipping. Unknown legs still show as a plain name-and-price line.

**Still to confirm:** the real DK field name for the event id. dk_bets.py records the names of any event/game fields in each leg's `_k`. Read /bets after the next sync and tighten `first(...)`.

**Settle at the final (Oct 9, 2026):** the clock (clock/watch.js looseState) settles every leg with no board price when its game goes final: HT/FT from the quarter scores (regulation only), and count props (tackles, field goals, yards, receptions, etc.) from the box score. It writes won/lost onto the tracked slip and the badge drops it. The page tracker draws HT/FT and FG rows (36-app-7.js). settle.py now keeps linescores, kicking and defensive stats in site/final.

## marks-sync-journal

His marks (placed, hidden, picks, rings, stars) live in Cloudflare KV via site/functions/state.js. A KV read can return the copy from before a write for up to about a minute. Two effects:
- a second un-tap's POST merged over a stale copy and put the first one's gold back for good;
- the page's own 60s re-read painted old gold over fresh un-taps.

Jose, Sep 29, 2026: "I un-click, two seconds later it refreshes and it's 17 bets."

**Fix (master.html pushState/pullState):** JOURNAL logs each device's own mark changes at tap time and keeps them for 2 minutes in sessionStorage. Every POST sends the whole journal as the patch. Every pull has the journal laid back over the answer. Tested against a store that always answers stale.

**Related, same day:** site/build.txt now holds two hashes, code then data (pagefile.stamps()). New data reloads the page only while it is hidden. New code waits while busy() is true: the wallet, the search, the slip, or a wallet refresh. A self-reload skips the boot screen (sessionStorage arena.quiet).

**How to apply:** never trust a KV read right after a write. Any new synced field goes through the journal.

## card-qb-follows-dk-prices

Rule (Jose, Sep 29, 2026): a QB is on the card only if he is listed as the starter, is not ruled out, and has DraftKings odds. If the starter is questionable and DK prices his backup, the backup goes on the card. The starter stays tagged Q in the back end, and he goes back on the card (or stays off, injured) once DK prices him near game time.

Built as starters.py `book_of()`: it reads the card's own prices file (props._qb, DK pid → ESPN id via data/dk_people.json, kept only if the id is in that club's depth room). A Q comes off only when DK prices HIM, not just his side. guard.py's passers check flags any card whose QB is not the one DK prices.

**Why:** Daniels (Q) sat on Washington's card over Mariota's prices. data/dk_qbs.json had gone stale because fill_week skips fully priced games more than 24h out.

**How to apply:** tie by ids on both sides (ESPN ids and DK ids), never by names. See the-board-uses-person-name and the-wire-outranks-the-record.

## quarterback-legs-only

His parlays are built only from quarterback legs (passing TD rungs, the QB's anytime TD, the passing-yards head-to-head) and the moneyline. Never suggest an anytime TD or any other prop for a receiver, running back or tight end.

**Why:** Sep 28, 2026. I suggested a DeVonta Smith anytime TD, and he said: "We don't do anytime TD for someone outside the qb you know that."

**How to apply:** when picking legs, choose only from ML, QB 1+/2+/3+ PTD, QB ATD and QB H2H. Skill-player usage (snap counts, injuries) still matters as a reason to back a QB leg, but it is never a leg itself. See card-engine-laws and what-decides-a-qb-head-to-head.

## complete-means-every-market

A game counts as complete only when it holds every market the board draws: the moneyline both sides, 1+ and 2+ passing TDs, the QB's anytime/rushing TD, and the passing-yards head to head, both passers. Every odds check (sweep, pre-kick wake, double tap) asks DraftKings for anything still missing; only a fully complete game is skipped. That's the count toward 100%.

**Why:** Oct 1, 2026: `fill_week.full()` had never included H2H (written Sep 22 with eight slots), so Goff v Young and Penix v Shough sat on DraftKings unread until "the day before". Jose: "Every time we check for odds we check for those too. Not some day of shit. If it's there we pull it."

**How to apply:** when a new market goes on the cards, add it to `full()` in build/fill_week.py in the same change; `covered.py` uses `full()` for its "complete" count. See one-path-draws-every-card, apply-a-fix-everywhere-it-applies.

## a-started-bout-is-live-now

A bout DraftKings or ESPN calls started is clocked at that moment and sorted there; the book's scheduled start (startEventDate) is just a guess and reorders all night. Built Oct 6, 2026 (20e40611): fill_fights.py dk_bouts() turns status STARTED into "now"; the page's startedNow() re-clocks a live card and refreshFights asks ESPN about the whole night once any bout is on.

**Why:** Onley v Bierley opened the DWCS card while DK listed it at 9:15, so a LIVE card sat under a 9:15 heading. Jose: "We already should have had that, I told you to check DraftKings to make sure we are live with them."

**How to apply:** any live/started state on a card (fights, games) is checked against DK's own event status as well as ESPN, never only the listed time. Related: check-the-round-rail-on-fight-night, same-day-same-last-name.

## check-the-round-rail-on-fight-night

Sep 26, 2026: Rosas Jr. vs Barcelos, a five-round main event, showed R1-R3 on the live card. The data (prices.json FPROPS rounds 5, ESPN periods 5) was right. The rail was built once in layoutBout before prices.json loaded, so it fell back to 3 and was never redrawn. Fixed with boutRail(), which redraws after the FPROPS merge. Jose: "Why do I keep having to tell you this!"

**Why:** a right number in the data is not a right card on the screen; he's caught round counts before.

**How to apply:** on any fight day, render the main event and a title bout and read the rail (R1-R5), not the JSON. See measure-paint-not-properties, look-at-the-picture-not-the-numbers.

## fight-bets-stay-on-the-modal

When picking a fight bet, choose only from the markets the board's bout card and its sheet carry: moneyline, KO, SUB, DEC, FINISH (any KO/sub, inside the first 60 seconds, Round 1), DBL CHANCE, and round bets. Total rounds over/under is not one of them.

**Why:** Oct 6, 2026, I called Over 1.5 rounds for Ariano v LaGrange. Jose: "We don't do the over 1 1/2 and you know that, that's not on our modal."

**How to apply:** before naming a fight bet, check it exists on the card's sheet; if the best read points to a rounds total, translate it into the modal's terms (a decision, a later round, a double chance). Pairs with quarterback-legs-only (same rule for football: our markets only) and dwcs-picks-weigh-the-finisher.

## fight-playback-on-the-card

Built Sep 20, 2026, shipped Tsarukyan v Ruffy first. A bout card that has
`site/anim/<bout>.json` (listed in `site/anim/index.json`) gets a yellow (#F5C24B) rewind — Jose, Sep 22: "the way the rewind reads on Van v Pantoja" —
beside FINAL; pressing it plays the fight once under FINAL and above the rail,
drag to scrub, REPLAY restarts, pressing the rewind again folds it away. The
engine is `fightAnim()` in `master.html`; `armRewind(card)` is called from
both places that write FINAL on a bout.

**Pipeline:** `build/log_fights.py` (Mac only, every 6s during a card) writes
`data/fight_log.jsonl` (cumulative ESPN stats per sample, clock is time LEFT
while live and time INTO the round on the result) and `data/fight_plays.jsonl`
(moments). `build/anim.py` cuts both into the playback files; run it after a
card. Winners come from `data/fight_winners.json` (seeded from the card;
extend from ESPN's competitors[].winner). Bouts the logger never saw end, or
with under five strikes, are skipped and named in the run's output.

**Settled looks (do not relitigate):** left man red, right blue, low opacity,
color inset so the counts sit outside it; dot head, square body, diamond legs;
darker = significant, close-range near the clock; missed = hollow grey,
non-significant = grey and scattered; clinch slides the seam to 80/20;
takedown turns the card 90°; knockdown drops only the downed man's field 80%
from the top and comes back fast unless it ended the fight; finish is one
diagonal from the clock to the glove/hold icon, no ring, no rays; a decision
draws nothing but the text; it plays once, never loops.

**Why:** Jose designed it image by image through the night; "ESPN already
does" the averages bar, so this is the thing they do not have.

**How to apply:** for a new card, keep the logger running through the whole
card (the first six bouts of UFC 331 were lost because it started late), then
`python3 build/anim.py` and `build/ship.sh`. See ship-with-ship-sh.

**Sep 27, 2026:** the recorder (log_fights.py) had only ever run on his Mac and stopped when the sweep moved to GitHub, so the 9/26 card got no rewinds. A missed card can't be rebuilt afterward. Now `.github/workflows/fightlog.yml` records the card: refresh.py dispatches it once per card (`fightlog@<event>` in served.json) when card_running() starts. It runs log_fights --every 6 --hours 5.75, then anim.py, commits data/fight_log*.jsonl and site/anim, and deploys. Its first real run is the 10/3 card; check on it after that card that site/anim has the new bouts.

## ufc-men-only

The UFC model scores every bout, but only men's bouts get a pick/rank on the board (build/ufc_reads.py picks_json skips women_row), and in chat never cite women's fights as picks or examples — use men's bouts.

**Why:** Oct 12, 2026, after the new model's top 3 had two women's bouts: "It can read everything but don't tell me about women's fights, use different examples."

**How to apply:** UFC picks, recaps and examples = men's bouts only. See ufc-box-picks.

## use-known-times-not-polling

When the moment is known (a game's kickoff, a bout's start, a card's first bell), act at that moment — a setTimeout to the kick time on the page, the clock Worker's schedule on the server. Never a setInterval / every-minute sweep that re-checks.

**Why:** Oct 12, 2026 an every-minute sweep meant for NFL game tickets also deleted the UFC pick tickets a minute after they appeared. Jose: "why the fuck would we check every fucking min? we know when the game starts... stop doing dumb shit like that." Same spirit as the sweep schedule ("why would it go off every 10 minutes").

**How to apply:** before writing any interval/poll, ask whether the trigger time is already known; if so, schedule to it. Audit existing setInterval calls in src/ when touching them. See check-before-answering.

## nothing-by-hand

Anything that puts a read, number or check on the board must run by itself in the sweep (build/refresh.py job list, before suggest.py), from a script in build/, never as a scratchpad script I run once by hand.

**Why:** Oct 12, 2026: the NFL H2H reads were scored by hand on Wed Oct 7 from a scratchpad script and never refreshed; Sunday's reads went out on Wednesday's lines (Huntley lost), and the scratchpad data was later wiped. Jose had already asked (Oct 10, Iowa QB) "why arent you doing this automatically?" — and asked again: "What did I tell you about doing things by hand?"

**How to apply:** when a model or read is built, ship it as a build/ job wired into refresh.py in the same change, with its inputs fetched by the job (not from the scratchpad). Audit the other reads (CFB 1+ PTD/H2H/2+ PTD/ML in scratchpad cfb_ptd, NFL ML week.py, UFC card2.py) for the same gap. See the-board-mends-itself, what-decides-a-qb-head-to-head.

## no-paid-services

Jose runs the board at effectively $0 (free tiers only) and does not want to pay for services. When a paid API would solve something (SharpSports BetSync for DraftKings bets, Sep 26, 2026), keep looking for free sources and build our own way: HARs of his logged-in sessions, his own browser, public feeds.

**Why:** "we are not paying for anything, we will have to build a way" (Sep 26, 2026).

**How to apply:** never recommend a paid service as the call; offer it only as context, and lead with a free route. See anything-is-possible-put-it-together.

## the-board-covers-four-sports

Settled September 12, 2026. the-odds-board-lives-on-the-desktop covers:

- **College football and NFL** — always, while they are in season.
- **UFC and boxing** — major events only, judged case by case rather than
  every card.

**Why:** Jose set the scope while the board was still built around one
weekend's fixtures.

**How to apply:** when adding fixtures, the two football leagues are assumed;
ask before building out a combat card. Note that QB Spy's database is NFL
only — 32 clubs in `league_player`, no college — so anything college has to
come from ESPN.

## dk-markets-move-read-per-event

DraftKings moves a market's address without changing the market. Head-to-head
passing yards was served league-wide at
`/sportscontent/dkusmd/v1/leagues/88808/categories/1185/subcategories/11977`;
that path now answers with zero selections, and the same market lives in each
game's own `/events/{id}/categories/1185` with **different selection ids**.

**Why:** an emptied league-wide list is not an error — it returns 200 with a
valid, empty payload. Nothing failed, nothing logged, and the ids already on
the board kept rendering their old prices. The break only showed when Jose
tapped a price and DraftKings opened to nothing. Anything read once from a
league-wide list is a stale id waiting to happen.

**How to apply:** read selection ids from the event's own category, per game,
not from a league-wide subcategory. Where a league-wide path is still used,
assert it returned a non-zero count and say so loudly when it did not — see
patch-against-the-file-not-memory for the same habit applied to files. A
price on the board with no live selection behind it is worse than a blank,
because it looks priced. Related: dk-prices-carry-no-clock,
how-a-book-is-read-end-to-end.

## dk-prices-carry-no-clock

We have never known how often DraftKings moves a price. The "about three times a
day" figure is a comment in `build/gameday.sh` about theScore and ESPN, and that
same comment excludes DK by name: it is "the one source that can go stale
without anything failing, so its age is worth checking by eye."

Their payload gives nothing to detect a move with. Searched every field name in
the NFL league feed: no `lastUpdated`, no `version`, no `sequence`. Response
headers carry no ETag and `cache-control: no-store`. A price is bare digits, so
the only way to know it changed is to pull the whole feed and compare.

What the feed does carry is `subscriptionPartials` plus a `subscriptionKey` on
every market (e.g. `league-events-88808`) — DK telling its own web client how to
subscribe to a push channel. Their site is pushed, not polled. Untested: the
socket host, and whether it accepts curl_cffi rather than a real browser.

**Selection ids do hold still across a repricing.** 206 of 206 checked on one
NFL game an hour apart, with 146 of them carrying a different price. So a price
can be looked up again later by the same `data-oid`, which is what makes
the-odds-board-lives-on-the-desktop's diff-and-deploy work. Markets
themselves can vanish — six of ten head-to-head passing yards markets were
pulled overnight — so a missing id means "no longer offered", not "renamed".

**Why:** I asserted a DK cadence I had read off a comment about other books, and
Jose caught it.

**How to apply:** Never quote a DK refresh cadence as known. Either chase the
push channel or measure it by logging one event until digits change.

## lineups-and-injury-edges

Built Sep 28, 2026. Jose's rules for how it looks:

- **Kalshi jerseys only** (`site/ico/jersey/<club>.png`), with the player's number on the jersey.
- **Red edge:** a starter is out, and the jersey shows his backup's number.
- **Yellow edge:** a starter is questionable.
- No injury list and no separate injury tile; keep it simple.

**Data:** `build/lineups.py` runs on every sweep and writes `site/lineups.json`. It uses ESPN's **depth chart** (not last game's starters), so every team is consistent, eleven a side in fixed spots:
- **Offense:** the "3WR 1TE" set — spots lt, lg, c, rg, rt, qb, rb, te, and wr1/wr2/wr3 (ESPN's wr split by slot).
- **Defense:** the "Base 4-3 D" or "Base 3-4 D" set, with the nickel left out.

The first man at each spot starts. If he's out, the spot wears the next healthy man's number with a red edge; if he's questionable, a yellow edge. The QB spot uses the starter named in SCHED. Tonight's status comes from the game summary plus `data/wire_held.json`.

**How the card draws it** (matched to the NFL's own diagrams at operations.nfl.com, "Formations", Sep 28):
- **Offense, 3WR 1TE:** seven on the line (X split left, the TE next to the left tackle, the five linemen). The Z and the slot stand a step off the line on the right. The QB is under center, and the lone back (no fullback) is offset toward the two-receiver side.
- **4-3:** DE DT DT DE evenly across, three linebackers evenly behind, then CB S S CB in one row.
- **3-4:** DE DT DE, then four linebackers in one row with the corners out wide on that row, then two deep safeties.
- **Strong side:** the strong-side linebacker and strong safety line up on the TE's side.

**Where it shows:**
- The one-QB search card shows his offense against tonight's defense. The three tiles are 1+ PTD, "X allows" and weather. A parlay view doesn't show it.
- On HOT, lifting a QB turns the five lineman circles into his club's jerseys with red/yellow edges. They stay still, and go back to circles when no QB is lifted.

Teams mostly play nickel (the gamebooks show it), but he chose the chart's base 11 for consistency: "use the depth chart so it's consistent", same spots always. See nfl-gamebooks and report-news-the-moment-you-see-it.

## leg-alert-usage

The leg alert (legAlert in master.html, data from build/alerts.py → site/alerts.json) names a hurt teammate only when his absence can sink THIS leg, and only if he played in one of the club's last two games: on a passing leg (PTD/H2H) 15%+ of team targets or 1/4+ of the TD catches; on any other leg 15%+ of targets+carries. Passing legs read "Usually gets 5 to 6 targets a game and caught 2 of SF's 9 TD passes. If he sits, tougher for Purdy to throw his."; H2H uses his yards instead; ESPN's injury type + return date gives "out for the season (knee, ACL)". Usage comes from ESPN box scores of every finished game, cached per game in data/usage.json (site/final keeps passers only, so it can't be used). The line reads "28% of the MIA touches: 4 targets, 11.3 carries a game." The alert is gray/white, not gold.

**Why:** Jose, Sep 29, 2026: Pacheco "didn't play a snap all season" yet was flagged; before the filter there were 43 teammate flags, after it 4.

**How to apply:** Any new alert reason must be backed by a number showing it matters now, not by a list entry. See the-color-is-amber for the colors.

## qb-wire

Under the clips rows (the how-to moved behind a small ? modal). Newest first, one card per fact, all by ESPN id:
- status (wire.json: Q/D/O/IR, injury, return, reporter note)
- swap ("Starter change": depth.json starter vs a hurt man ranked above him; starters logged in data/qb_starters.json)
- targets (alerts.json teammates with 15%+ target share, Q or worse; receiver faces copied to site/faces/nfl)
- streak (1+ PTD in 3+ straight, from qbsearch.json game logs), cold (no TD pass 2+ straight)
- birthday (birthdays.json, within 3 days of his next game), revenge (next opponent is a club in his ESPN statisticslog, cached weekly in data/qb_clubs.json)
- weather (15+ mph wind or 50%+ rain, outdoors, one card a game)

**Layout (Oct 7, 2026):** ONE card per QB (his club's starter), every fact about him as rows on it, cards ordered by kickoff, only QBs with something; a hurt non-starter shows as the "Starter change" row on his club's starter. Only the next game (week to week). NFL only. Wire box scrolls on its own under the fixed clips rows. Jose: "one card per player... so I don't have to search 20 different places."

Added Oct 7: offensive line Q/out (lineups.json), lead back Q/D/O with 20%+ touches (alerts.json), first start (no games and no ESPN NFL stats), and his current 1+/2+ PTD prices in the card head (PROPS ptd, no line-move history). Oct 7 (0bfead51): OL roster moves too — line_moves() reads ESPN's NFL transactions (text only) for a lineman retired/traded/released/waived/IR in the last 10 days, tied to the club's starters from its last 3 games by surname; first catch PHI: C Cam Jurgens traded to BAL, OT Lane Johnson retired. lineups.py now drops a chart man who is off the club roster (ESPN's chart lagged the trade). Next he wants: a sharper H2H read (see what-decides-a-qb-head-to-head) -- facts only.

**Why:** Jose wants the things outside hit rates that help him decide — injuries, swaps, targets out, birthdays, revenge, hot/cold, 1+ PTD streaks. Facts only, per facts-not-picks.

**How to apply:** new "intangible" facts become a new card kind here, not a pick. Runs in refresh.py's job list and watch_news.py's injury jobs.

## report-news-the-moment-you-see-it

When I see QB injury, status or depth news before the sweep has it (ESPN news, nfl-news-breakers), I put it on the page right away, without being asked. I add the entry to `data/wire_held.json` (keyed by ESPN id, with the same fields as wire.json plus `src`), patch `site/wire.json`, and ship. `build/wire.py` keeps a held entry until ESPN's own injury entry is newer, so the sweep won't overwrite it with stale data.

**Why:** Jose, Sep 28, 2026, after I told him Mayfield was out about three weeks while the board still said Questionable: "if you get it before the sweep automatically update it as soon as it comes in as soon as you see it, report it on the page."

**How to apply:** every time I find news like that, update the page in the same turn and tell him in one line. It is the injury-wire twin of the starter hold in data/qb_named.json. See the-wire-outranks-the-record.

## act-on-news-without-asking

**Rule (Sep 28, 2026):** the board must be bulletproof. Jose should never have to tell me that something broke or that someone is out. That covers every fault he has pointed at, not only QBs. I am allowed to act outside the sweep: change depth charts, the wire hold, the named starter, prices or faces myself, and ship, without asking first.

**Why:** "It can't be me just telling you every time to fix one thing or that thing you're not checking." Mayfield, Keenum, red helmets, fonts, card sizes and empty prices all had the same cause: a read came back empty, or a piece went missing, and nothing said so.

**How to apply:**
- **Start of every session:** read `site/guard.json` (live copy: /guard.json) and the sweep log's `GUARD:` and `LOOK:` lines, then fix whatever is listed before doing anything else.
- **What checks what:**
  - `build/news.py` reads ESPN's news feed by athlete id, for QBs who are out or named to start.
  - `build/guard.py` checks the passers, lineups, prices, faces, jerseys, weight classes, settled games, files and asset paths. It reruns the job that owns each fault.
  - `build/look.py` renders the page and measures it: errors, sideways scroll, fonts, broken pictures, HOT at 55px, All and search at 32.
  - `guard.py --live` runs on every GitHub run. It confirms the site carries main's page (and redeploys if not), that the functions answer, and that faces come back as pictures.
- **When he flags a new kind of fault:** fix it, then add a check for it to guard.py or look.py, so it is caught the next time without him.

See report-news-the-moment-you-see-it, measure-paint-not-properties.

## board-watches-itself

Built Sep 30, 2026 (Jose: "add a notification system so if that happens it sends you or the code something so it auto diagnoses and fixes").

- `.github/workflows/watch.yml` runs on any failed run of sweep, settle, ask, dkbets, fightlog, promote. `build/triage.py` reads the failed job's log (following the log redirect without the token), names the cause and acts: **login** (dk_bets "LOGIN EXPIRED" / 401) → phone alert only; **transient** (timeouts, resets, 5xx) → alert, and a sweep is dispatched again; **code** (a traceback) → a GitHub issue labeled `fault` with the traceback (one per fault title) plus an alert; **unknown** → issue + alert.
- The alert goes POST /push {fault:{key,title,body}} with `x-ask-secret`, sent with curl_cffi impersonating a browser (the edge 403s a bare client); the clock's DO route `/fault` tells it once per fault per day (type "fault", tag "fault").
- `.github/workflows/mend.yml` runs anthropics/claude-code-action@v1 on a `fault` issue (or an `@claude` comment / workflow_dispatch) with `claude_code_oauth_token: secrets.CLAUDE_CODE_OAUTH_TOKEN`; it stands down when the secret is missing. **The secret CLAUDE_CODE_OAUTH_TOKEN is set (Sep 30, 2026, valid a year):** `claude setup-token` was driven through a pty daemon (scratch script), Jose signed in on his phone and pasted the code; the token was stored through the REST secrets API with a libsodium sealed box over curl (urllib on this Mac fails SSL; gh refuses the git token, no read:org). Never delete a captured token before the store step returns 201.
- I can read run logs and dispatch workflows from the Mac with the token from `git credential fill` (host github.com).

**What actually happened Sep 30 (don't repeat):** the login "expired" because nothing read it for nine idle hours overnight; the reads every few hours had kept it alive since Sep 26. Later 401s were the *kept* jar (DK's re-issue merged over an older set), which fails while the browser's *sent* copy mints fine. Before ever asking Jose to sign in again: check `/bets?loginmeta=1&k=<ARENAOWN>` for a recent `at`, open a DraftKings page in Chrome on the Mac so the extension re-sends, and dispatch dkbets.yml; he was asked four times when once was needed. The clock now touches the login every 3 hours (KEEP_ET) via /wake mode "keep" → dkbets.yml --keep.

**DraftKings login, renewed remotely:** the Chrome extension (tools/dk-bets) posts the login to the site whenever DraftKings is open in Chrome on the Mac. `open -a "Google Chrome" https://sportsbook.draftkings.com/` from here makes it re-send (check `/bets?loginmeta=1&k=<ARENAOWN from src>` → `at`). If dk_bets still says 401, the Chrome session itself is logged out and Jose must log in to DraftKings in Chrome on the Mac (he can, from his phone, over his remote control); the export/HAR is not needed after that.

**Sep 30 afternoon, settled with Jose (he asked to save this):** DraftKings ended the session between the 12:01 PM read (ok) and the 1 PM one (401 on every login: sent, kept, export) -- not idle, not our code (this morning's dk_bets, restored in dcc42a3, failed the same). No reason is given by DK. What keeps it alive is the reader itself: every double-tap read and the once-a-day `dk_bets.py --keep` in refresh.py's 10 ET hub pass keep DK's re-issued login; the clock's KEEP_ET touches are off (Jose had them removed). The extension (unchanged since Sep 29 09:09) only sends Chrome's cookies and scrapes My Bets; it cannot sign in. **The fix when it goes red:** Jose signs in to DraftKings in Chrome on the Mac (I never type his password or 2FA); then reload a DK page (`open -a "Google Chrome" https://sportsbook.draftkings.com/mybets`) so the extension re-sends the *signed-in* cookies -- the first push after his sign-in still 401'd, the reload's push minted -- then dispatch dkbets.yml. Signing in on the phone app does nothing (the extension reads Mac Chrome only; iPhone Chrome has no extensions). For away-from-Mac sign-ins: Chrome Remote Desktop (free), offered, not set up yet (outstanding-things). Don't tell him to "sign in to Chrome" unless a read with a fresh push has actually 401'd.

**How to apply:** when a mark goes red, read the latest run of that workflow on GitHub first (`/actions/workflows/<name>.yml/runs`), then the job log with cookie lines filtered. See app-backbone-sep29, ship-with-ship-sh.

**Oct 10, 2026:** the DraftKings-login check (guard.py) and the "DraftKings logged you out" phone alert (triage.py) are REMOVED. Jose: "we don't use it." Never tell him to open DraftKings in Chrome for the extension again. A 15-minute sweep timeout is now classed as transient.

## the-arena-is-not-qbspy

The arena at `~/Desktop/the arena` and QB Spy at `~/qbspy` are two products.
Work on one never touches the other: not its scripts, not its data, not its
`com.qbspy.*` launchd jobs, not its Cloudflare project.

**Why:** on Sep 20, 2026, while making the arena stop polling after the last
event, I started reading qbspy's `gameday.sh` and listing its launchd jobs as
if they were part of the problem. Jose: "Nothing we are doing involves QB
Spy. It's a completely different product."

**How to apply:** when asked what runs on the Mac for the arena, the answer
is the arena's own scripts only (as of Sep 20, 2026: `build/log_fights.py`,
and nothing else). Do not list or explain qbspy's agents. The arena's
CLAUDE.md already says nothing in it imports or points at `~/qbspy`.
