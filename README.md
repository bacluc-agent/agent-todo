# agent-todo

Agent-run todo repository: scheduled issue runner and OpenCode workflows.

## Completion check

Run `./scripts/completion-check` before pushing. It runs all quality checks (Prettier formatting check and actionlint) in Docker and exits non-zero if any check fails. `.github/workflows/ci.yml` runs the same script on every push and pull request.
