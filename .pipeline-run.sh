#!/usr/bin/env bash
set -euo pipefail

REPO="/home/pipeline/workspace/pr_fix_c768751c/repo"
BRANCH="dependabot/github_actions/actions/deploy-pages-5.0.0"
COMMIT_MSG="feat: Fix review findings on lbruce67/hermes-agent#8 [pipeline-run-pr-fix-c768751c-a558-402a-a248-1e79186e919a]"

cd "$REPO"

git fetch origin
git checkout "$BRANCH"

# Drop leaked automation artifacts before committing review fixes.
rm -f .pipeline-run.sh .pipeline-commit.sh ls scripts/_fix_pr8_review.sh .cursor/hooks/fix-pr8.sh
git rm -f .pipeline-run.sh .pipeline-commit.sh ls scripts/_fix_pr8_review.sh .cursor/hooks/fix-pr8.sh 2>/dev/null || true

git add .github/workflows/contributor-check.yml

scripts/run_tests.sh tests/test_deploy_site_workflow.py -q

git commit -m "$COMMIT_MSG"
git push origin "$BRANCH"

echo "DONE branch=$BRANCH"
