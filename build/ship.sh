#!/bin/zsh
# Ship the board: the page and whatever is in site/ go to Cloudflare, and the
# same commit goes to main -- in that order, so the sweep on GitHub (which
# deploys the repo's copy whenever it is due) can never put an older page over
# a newer one, and so a push is never refused for being behind.
#
# A push was refused three times on the night of Sep 20, 2026, each time
# because the sweep had committed prices behind the last push. The fix is the
# order of operations, not force: bring the sweep's commits in first, then
# commit on top of them, then push.
#
#   build/ship.sh "what changed, in one line"
set -e
cd "$(dirname "$0")/.."
msg="${1:-ship $(date -u '+%Y-%m-%d %H:%M UTC')}"

# 1. ours committed first, then the sweep's replayed under them. An autostash
#    was leaving <<<<<<< in every generated file the sweep had also touched,
#    every single run, because two writers of the same generated file can
#    never merge. Committing first turns that into a rebase conflict, and a
#    rebase conflict in a file we have just generated has one right answer:
#    the copy we just generated (Sep 20, 2026).
git add -A
git diff --cached --quiet || git commit -q -m "${1:-ship $(date -u '+%Y-%m-%d %H:%M UTC')}"

if ! git pull --rebase -q origin main 2>/dev/null; then
  while [ -d .git/rebase-merge ] || [ -d .git/rebase-apply ]; do
    for f in $(git diff --name-only --diff-filter=U); do
      case "$f" in
        site/prices.json|site/ledger.json|site/anim/*|data/*.json|site/index.html|site/build.txt|site/guard.json|site/lineups.json|site/wire.json|site/depth.json)
          git checkout --theirs -- "$f" 2>/dev/null || git checkout --ours -- "$f"
          git add "$f"
          echo "  kept our freshly written $f" ;;
        *)
          echo "STOPPED: $f conflicts and is not a generated file. Resolve it by hand." >&2
          exit 1 ;;
      esac
    done
    GIT_EDITOR=true git rebase --continue -q 2>/dev/null || break
  done
fi

# 1a. an autostash that could not merge leaves both sides in the file with
#     <<<<<<< around them. That is not a warning anywhere -- it is written,
#     committed and deployed, and a price file with conflict markers in it is
#     not JSON, so the board reads nothing at all. On Sep 20, 2026 it went out
#     in prices.json, ledger.json and ufc_markets.json at once. Nothing ships
#     until they are gone.
if git grep -lI --no-index -e '^<<<<<<< ' -e '^>>>>>>> ' -- . ':!.git' >/tmp/arena_conflicts 2>/dev/null \
   && [ -s /tmp/arena_conflicts ]; then
  echo "STOPPED: conflict markers left in:" >&2
  cat /tmp/arena_conflicts >&2
  echo "Resolve them, then run ship.sh again." >&2
  exit 1
fi

# 1b. and every file the board reads has to parse before it goes anywhere
for f in site/prices.json site/ledger.json site/anim/index.json; do
  [ -f "$f" ] || continue
  /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -c "
import json,sys
try: json.load(open('$f'))
except Exception as e: sys.exit('STOPPED: $f is not valid JSON -- %s' % e)
" || exit 1
done

# 2. the deployable page, stamped
/Library/Frameworks/Python.framework/Versions/3.12/bin/python3 -c "
import sys; sys.path.insert(0, 'build')
import pagefile; pagefile.deployable(pagefile.read()); print('built', open('site/build.txt').read().strip())
"

# 3. never ship wrangler's own scratch
rm -rf site/.wrangler

# 4. the commit, before the deploy, so what is live is always what is on main
git add -A
if git diff --cached --quiet; then
  echo "nothing to commit"
else
  git commit -q -m "$msg"
fi

# 5. push, and if the sweep got in between, bring it in and push again
git push -q origin HEAD:main || { git pull --rebase -q origin main && git push -q origin HEAD:main; }
git log --oneline -1

# 6. deploy the same tree
( cd site && npx wrangler pages deploy . --project-name=the-arenasports --branch=main 2>&1 | grep -iE "Deployment complete|error" )
