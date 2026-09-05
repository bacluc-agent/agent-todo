# AGENTS.md

## Completion check

Before declaring any work done, run the repository's completion check from the repo root:

    ./scripts/completion-check

It runs all quality checks (Prettier formatting check and actionlint for `.github/`) in Docker and exits non-zero if any check fails. Fix everything it reports, rerun it until it passes, and only then declare the work complete.

`.github/workflows/ci.yml` runs the exact same script on every push and pull request, so a green `./scripts/completion-check` locally is the definition of done. To fix formatting automatically instead of only checking it:

    docker run --rm -u "$(id -u):$(id -g)" -v "$PWD:/workspace" -w /workspace ghcr.io/bacluc/prettier-image/prettier-image:3.9.4 --write .
