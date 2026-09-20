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

# 1. the sweep's commits first, with ours stashed over them
git pull --rebase --autostash -q origin main

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
