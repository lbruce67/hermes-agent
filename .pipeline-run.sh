#!/usr/bin/env bash
set -euo pipefail

REPO="/home/pipeline/workspace/pr_fix_7c8ed4b4/repo"
BRANCH="pipeline/unknown-fix-review-findings-on-lbruce67-hermes-agent-8"
PR_BRANCH="dependabot/github_actions/actions/deploy-pages-5.0.0"
COMMIT_MSG="feat: Fix review findings on lbruce67/hermes-agent#8 [pipeline-run-pr-fix-7c8ed4b4-a638-42ab-82eb-3088f79e28bc]"

cd "$REPO"

git fetch origin
git checkout "$PR_BRANCH"
git checkout -B "$BRANCH"

scripts/run_tests.sh tests/test_deploy_site_workflow.py -q

git add .github/workflows/contributor-check.yml
git commit -m "$COMMIT_MSG"
git push -u origin "$BRANCH"

echo "DONE branch=$BRANCH"
