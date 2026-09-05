# agent-todo

Agent-run todo repository: scheduled issue runner and OpenCode workflows.

## Completion check

Run `./scripts/completion-check` before pushing. It runs all quality checks (Prettier formatting check and actionlint) in Docker and exits non-zero if any check fails. `.github/workflows/ci.yml` runs the same script on every push and pull request.

The workflows pin the provision-machines OpenCode policy by commit. After merging the provision-machines change, push that commit and create a release tag, then update `source-ref` in both workflows and the setup action to the new tag, or retain the immutable commit pin.
