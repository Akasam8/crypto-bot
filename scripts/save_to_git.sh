#!/usr/bin/env bash
# Commit and push bot output. Retries on races, never leaves git stuck mid-rebase.
set -u
msg="$1"; shift
git config user.name "crypto-bot"
git config user.email "crypto-bot@users.noreply.github.com"
for p in "$@"; do [ -e "$p" ] && git add "$p"; done
git diff --cached --quiet && exit 0
git commit -q -m "$msg"
for i in 1 2 3 4 5; do
  if git pull --rebase -X theirs -q && git push -q; then exit 0; fi
  git rebase --abort 2>/dev/null || true
  sleep $((i * 5))
done
echo "push failed after 5 tries"
exit 1
