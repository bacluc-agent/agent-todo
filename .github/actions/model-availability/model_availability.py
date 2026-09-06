#!/usr/bin/env python3
"""Probe model availability and merge results into the cache on issue #49."""

import concurrent.futures
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone

CACHE_ISSUE = 49
AVAILABLE_TTL_HOURS = 24
FAILED_TTL_HOURS = 2
PROVIDERS = (
    ("opencode-go-openai", "OPENCODE_GO_API_KEY", "https://opencode.ai/zen/go/v1"),
    ("opencode-go-openai-2", "OPENCODE_GO_2_API_KEY", "https://opencode.ai/zen/go/v1"),
    ("opencode-go-anthropic", "OPENCODE_GO_API_KEY", "https://opencode.ai/zen/go/v1"),
    ("opencode-go-anthropic-2", "OPENCODE_GO_2_API_KEY", "https://opencode.ai/zen/go/v1"),
)
MAX_CONCURRENT = 5
PROBE_TIMEOUT_SECONDS = 60
PROBE_PROMPT = "Respond with exactly OK."


def run_gh(*args: str) -> str:
    return subprocess.run(
        ["gh", *args], check=True, capture_output=True, text=True
    ).stdout


def read_cache() -> dict:
    try:
        body = run_gh(
            "issue", "view", str(CACHE_ISSUE), "--json", "body", "--jq", ".body"
        )
        cache = json.loads(body)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


def write_cache(cache: dict) -> None:
    try:
        run_gh("issue", "edit", str(CACHE_ISSUE), "--body", json.dumps(cache))
    except Exception:
        pass


def parse_free_models(opencode_models_output: str) -> list[str]:
    return sorted(
        set(re.findall(r"^opencode/[^\s]+-free$", opencode_models_output, re.MULTILINE))
    )


def parse_go_model_ids(models_json: str) -> list[str]:
    try:
        data = json.loads(models_json)
        return sorted(set(m["id"] for m in data.get("data", []) if m.get("id")))
    except (json.JSONDecodeError, AttributeError, TypeError):
        return []


def discover_models() -> tuple[list[str], list[str]]:
    output = subprocess.run(
        ["opencode", "models"], check=True, capture_output=True, text=True, timeout=600
    ).stdout
    free_models = parse_free_models(output)
    go_model_ids: set[str] = set()
    for _provider, key_env, base_url in PROVIDERS:
        api_key = os.environ.get(key_env)
        if not api_key:
            continue
        try:
            session_id = os.urandom(16).hex()
            request = urllib.request.Request(
                f"{base_url}/models",
                headers={
                    "x-opencode-session": session_id,
                    "User-Agent": "curl/8.5.0",
                    "Authorization": f"Bearer {api_key}",
                },
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                go_model_ids.update(parse_go_model_ids(response.read().decode()))
        except Exception:
            pass
    return free_models, sorted(go_model_ids)


def build_candidates(
    free_models: list[str], go_model_ids: list[str], env: dict
) -> list[str]:
    candidates = []
    for model in go_model_ids:
        for provider, key_env, _ in PROVIDERS:
            if env.get(key_env):
                candidates.append(f"{provider}/{model}")
    candidates.extend(free_models)
    return candidates


def is_cache_fresh(entry, now: datetime) -> bool:
    if not isinstance(entry, dict) or not isinstance(entry.get("ok"), bool):
        return False
    ttl_hours = AVAILABLE_TTL_HOURS if entry["ok"] else FAILED_TTL_HOURS
    try:
        checked = datetime.fromisoformat(entry["checked"].replace("Z", "+00:00"))
    except (KeyError, ValueError, TypeError):
        return False
    return (now - checked).total_seconds() < ttl_hours * 3600


def probe_model(
    candidate: str, work_dir: str, timeout: int = PROBE_TIMEOUT_SECONDS
) -> bool:
    probe_dir = os.path.join(work_dir, "probe-" + candidate.replace("/", "-"))
    os.makedirs(probe_dir, exist_ok=True)
    try:
        result = subprocess.run(
            [
                "opencode",
                "--pure",
                "run",
                "--dir",
                probe_dir,
                "--model",
                candidate,
                PROBE_PROMPT,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False
    text = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", result.stdout)
    return result.returncode == 0 and re.fullmatch(r"\s*OK\.?\s*", text) is not None


def probe_candidates(candidates: list[str], work_dir: str) -> dict[str, bool]:
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as executor:
        futures = {
            executor.submit(probe_model, candidate, work_dir): candidate
            for candidate in candidates
        }
        for future in concurrent.futures.as_completed(futures):
            candidate = futures[future]
            try:
                results[candidate] = future.result()
            except Exception:
                results[candidate] = False
    return results


def merge_results(cache: dict, results: dict[str, bool], checked: str) -> dict:
    merged = dict(cache)
    for candidate, ok in results.items():
        merged[candidate] = {"ok": ok, "checked": checked}
    return merged


def available_models(
    cache: dict, free_models: list[str], go_model_ids: list[str]
) -> list[str]:
    available = []
    for model in free_models:
        if cache.get(model, {}).get("ok"):
            available.append(model)
    for provider, _, _ in PROVIDERS:
        for model in go_model_ids:
            candidate = f"{provider}/{model}"
            if cache.get(candidate, {}).get("ok"):
                available.append(candidate)
    return list(dict.fromkeys(available))


def write_outputs(cache: dict, available: list[str]) -> None:
    lines = [
        "cache-json<<CACHE_EOF",
        json.dumps(cache),
        "CACHE_EOF",
        "available-models<<MODELS_EOF",
        *available,
        "MODELS_EOF",
        "",
    ]
    output = "\n".join(lines)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as handle:
            handle.write(output)
    else:
        print(output, end="")


def main() -> int:
    cache = read_cache()
    free_models, go_model_ids = discover_models()
    candidates = build_candidates(free_models, go_model_ids, os.environ)
    now = datetime.now(timezone.utc)
    pending = [c for c in candidates if not is_cache_fresh(cache.get(c), now)]
    work_dir = os.environ.get("RUNNER_TEMP") or tempfile.gettempdir()
    results = probe_candidates(pending, work_dir)
    checked = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    cache = merge_results(cache, results, checked)
    write_cache(cache)
    available = available_models(cache, free_models, go_model_ids)
    write_outputs(cache, available)
    print("Available models:")
    print("\n".join(available) if available else "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())