#!/bin/bash
set -euo pipefail

# Only run in remote (web) sessions
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Restore skills from skills-lock.json
if [ -f "$CLAUDE_PROJECT_DIR/skills-lock.json" ]; then
  cd "$CLAUDE_PROJECT_DIR"
  npx skills experimental_install --yes 2>/dev/null || true
fi
