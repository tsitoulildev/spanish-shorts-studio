#!/usr/bin/env bash
# Approves and merges a lesson pull request ONLY when every gate has passed, then starts the upload.
# Inputs (env): REPO, BRANCH, SHA, GH_TOKEN. Exits 0 without merging whenever a condition is not met
# (the pull request then simply waits for a human).
set -euo pipefail

skip() { echo "NOT merging: $*"; exit 0; }

case "$BRANCH" in lesson/*) ;; *) skip "branch $BRANCH is not a lesson branch";; esac
id="${BRANCH#lesson/}"
case "$id" in ''|*[!a-z0-9-]*) skip "bad lesson id";; esac
owner="${REPO%%/*}"

pr="$(gh api "repos/$REPO/pulls?head=$owner:$BRANCH&state=open" --jq '.[0].number // empty')"
[ -n "$pr" ] || skip "no open pull request for $BRANCH yet"

head_sha="$(gh api "repos/$REPO/pulls/$pr" --jq .head.sha)"
[ "$head_sha" = "$SHA" ] || skip "branch moved on (PR head ${head_sha::7}, checked ${SHA::7})"

# 1. The pull request may change exactly the lesson file and the review log, nothing else.
files="$(gh api "repos/$REPO/pulls/$pr/files" --paginate --jq '.[].filename' | sort)"
want="$(printf '%s\n' "docs/LANGUAGE_REVIEW.md" "lessons/$id.json" | sort)"
[ "$files" = "$want" ] || skip "unexpected files in the pull request: $(echo $files)"

# 2. The Build must have succeeded on exactly this commit.
ok="$(gh api "repos/$REPO/actions/workflows/lessons.yml/runs?head_sha=$SHA" --jq '[.workflow_runs[]|select(.status=="completed" and .conclusion=="success")]|length')"
[ "${ok:-0}" -ge 1 ] || skip "no successful Build for ${SHA::7}"

# 3. The measurements of that build: within 40 s, QA PASS, no FAIL/WARN/OVER LIMIT for this lesson.
git fetch -q origin renders
report="$(git show "origin/renders:reports/$SHA.txt" 2>/dev/null)" || skip "no report for ${SHA::7} on the renders branch"
section="$(printf '%s\n' "$report" | awk -v id="$id" '
  $0 ~ "^"id": " {on=1; print; next}
  on && /^ / {print; next}
  on {exit}')"
[ -n "$section" ] || skip "lesson $id is not in the report"
echo "$section"
echo "$section" | head -1 | grep -q "within limit" || skip "duration not within the limit"
echo "$section" | grep -q "qa: QA: PASS" || skip "QA verdict is not PASS"
if echo "$section" | grep -Eq "FAIL|WARN|OVER LIMIT|BLOCK"; then skip "report contains FAIL/WARN/BLOCK/OVER LIMIT"; fi

# 4. Mergeable, and merge exactly the commit that was checked.
echo "all gates passed: merging PR #$pr"
gh api "repos/$REPO/pulls/$pr/merge" --method PUT -f merge_method=merge -f sha="$SHA" --jq .message || skip "merge refused (conflict or not mergeable)"

# A merge made with the workflow token does not start other workflows, so start the upload explicitly.
gh workflow run publish.yml --repo "$REPO" -f lesson="$id" -f privacy=private
echo "upload of $id started (private)"
