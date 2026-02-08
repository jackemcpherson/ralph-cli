#!/usr/bin/env bash
# setup-branch-protection.sh — Configure branch protection rules for the main branch
#
# Usage:
#   ./scripts/setup-branch-protection.sh [OWNER/REPO]
#
# Arguments:
#   OWNER/REPO  GitHub repository in "owner/repo" format.
#               Defaults to the current repository detected by gh.
#
# Prerequisites:
#   - GitHub CLI (gh) authenticated with admin access to the repository
#   - Repository must exist on GitHub
#
# What this script configures:
#   - Requires at least 1 approving PR review before merging
#   - Requires the following status checks to pass before merging:
#       * CI test matrix (all OS/Python version combinations)
#       * version-check
#       * CodeQL Analysis
#   - Requires branches to be up to date with main before merging
#   - Prevents force pushes to main
#   - Applies to everyone including administrators
#
# Example:
#   ./scripts/setup-branch-protection.sh jackemcpherson/ralph-cli

set -euo pipefail

REPO="${1:-$(gh repo view --json nameWithOwner --jq '.nameWithOwner')}"
BRANCH="main"

echo "Configuring branch protection for ${REPO} (${BRANCH})..."

gh api \
  --method PUT \
  "repos/${REPO}/branches/${BRANCH}/protection" \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": [
      "test (ubuntu-latest, 3.11)",
      "test (ubuntu-latest, 3.12)",
      "test (ubuntu-latest, 3.13)",
      "test (windows-latest, 3.11)",
      "test (windows-latest, 3.12)",
      "test (windows-latest, 3.13)",
      "version-check",
      "CodeQL Analysis"
    ]
  },
  "required_pull_request_reviews": {
    "required_approving_review_count": 1
  },
  "enforce_admins": true,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
EOF

echo "Branch protection configured successfully for ${REPO} (${BRANCH})."
echo ""
echo "Protection rules applied:"
echo "  - PR reviews: 1 approval required"
echo "  - Status checks: CI matrix, version-check, CodeQL (must be up to date)"
echo "  - Force pushes: blocked"
echo "  - Admin enforcement: enabled"
