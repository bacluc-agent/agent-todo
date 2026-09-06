#!/bin/bash
# Script to update provision-machines opencode.jsonc
# This script applies the optimizations identified from failed run 34011838269
# Run this against the provision-machines repository to apply the changes.
#
# Changes needed:
# 1. Add a comment before the "provider" section noting known-broken models
# 2. Add "disabled": true to the vshn-us-ai provider
#
# Usage:
#   cd provision-machines
#   bash scripts/disable-vshn-us-ai.sh

set -Eeuo pipefail

FILE="deploys/development_tools/ai_agent_devcontainer/files/opencode/opencode.jsonc"

if [[ ! -f "$FILE" ]]; then
    echo "Error: $FILE not found" >&2
    exit 1
fi

# Add comment about known-broken models before the provider section
python3 - "$FILE" <<'PY'
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
text = root.read_text()

# Add comment about known-broken models before "provider":
comment = (
    '// Known broken models from failed run 34011838269:\n'
    '// - vshn-us-ai: broken baseURL ("undefined/chat/completions")\n'
    '// - opencode-go-openai: grok-4.6 fails with "not supported for format oa-compat"\n'
    '// - opencode-go-anthropic-2: models fail with server errors\n'
)
if 'Known broken models' not in text:
    text = text.replace('  "provider": {', comment + '  "provider": {', 1)

# Add disabled: true to vshn-us-ai provider
if '"disabled": true' not in text:
    text = text.replace(
        '    "vshn-us-ai": {\n      "npm": "@ai-sdk/openai-compatible",\n      "name": "VSHN US AI",',
        '    "vshn-us-ai": {\n      "npm": "@ai-sdk/openai-compatible",\n      "name": "VSHN US AI",\n      "disabled": true,'
    )

root.write_text(text)
print(f"Updated {root}")
PY
