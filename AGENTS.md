/completion-check-command

```bash
./scripts/completion-check
```

## Standing Task: Issue #16 - Optimize Actions

This repository has an active task (issue #16) to optimize GitHub Actions workflows, prompts, agent markdowns, and opencode config based on analysis of failed action runs. Key findings from failed run 34011838269:

- All models failed during probing (server errors, URL parsing errors, format errors)
- The `vshn-us-ai` provider has models with broken baseURL configuration
- Model discovery timed out because no working model was found
- No PR deduplication logic exists - the agent creates duplicate PRs
- Poor debuggability - insufficient logging of model availability and errors

## Workflow Structure

- `.github/workflows/hourly-issue.yml` - Scheduled hourly runner that selects an issue and dispatches it
- `.github/workflows/opencode.yml` - Called by the hourly runner; runs the coordinator agent
- `.github/actions/setup-opencode/action.yml` - Sets up OpenCode CLI and configuration from provision-machines repo
- `scripts/issue-selection-tail.txt` - Tail instruction appended to the issue selection prompt
- `.opencode/agent/issue-selector.md` - Agent definition for selecting issues

## PR Deduplication

Before creating a PR, always check for existing PRs:
`gh pr list --state all --head issue-<number>`
If a PR exists, do not create a duplicate.

## Completion Check

Run `./scripts/completion-check` to verify formatting and action linting pass.
