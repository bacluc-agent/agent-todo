import json
from datetime import datetime, timezone

import model_availability


class TestParseFreeModels:
    def test_extracts_free_models(self):
        output = (
            "opencode/big-pickle\n"
            "opencode/ling-3.0-flash-fin-free\n"
            "opencode/mimo-v2.5-free\n"
            "custom-provider/other-free\n"
            "custom-provider/big-pickle\n"
            "standalone-free\n"
            "big-pickle\n"
            "opencode/paid-model\n"
            "other/paid-model\n"
        )
        assert model_availability.parse_free_models(output) == [
            "big-pickle",
            "custom-provider/big-pickle",
            "custom-provider/other-free",
            "opencode/big-pickle",
            "opencode/ling-3.0-flash-fin-free",
            "opencode/mimo-v2.5-free",
            "standalone-free",
        ]

    def test_deduplicates(self):
        assert model_availability.parse_free_models("opencode/a-free\nopencode/a-free\n") == [
            "opencode/a-free"
        ]


class TestParseGoModelIds:
    def test_extracts_and_deduplicates_ids(self):
        data = json.dumps(
            {"data": [{"id": "glm-5.2"}, {"id": "qwen3.8-flash"}, {"id": "glm-5.2"}]}
        )
        assert model_availability.parse_go_model_ids(data) == ["glm-5.2", "qwen3.8-flash"]

    def test_invalid_json_returns_empty(self):
        assert model_availability.parse_go_model_ids("not json") == []


class TestBuildCandidates:
    def test_skips_providers_without_api_key(self):
        env = {"OPENCODE_GO_API_KEY": "key1"}
        assert model_availability.build_candidates(
            ["opencode/a-free"], ["glm-5.2"], env
        ) == [
            "opencode-go-openai/glm-5.2",
            "opencode-go-anthropic/glm-5.2",
            "opencode/a-free",
        ]

    def test_free_models_last(self):
        env = {"OPENCODE_GO_API_KEY": "key1", "OPENCODE_GO_2_API_KEY": "key2"}
        candidates = model_availability.build_candidates(
            ["opencode/a-free"], ["glm-5.2"], env
        )
        assert candidates[-1] == "opencode/a-free"
        assert len(candidates) == 5


class TestIsCacheFresh:
    def test_fresh_available(self):
        now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
        entry = {"ok": True, "checked": "2026-09-06T10:00:00Z"}
        assert model_availability.is_cache_fresh(entry, now)

    def test_expired_available(self):
        now = datetime(2026, 9, 7, 12, 0, tzinfo=timezone.utc)
        entry = {"ok": True, "checked": "2026-09-06T10:00:00Z"}
        assert not model_availability.is_cache_fresh(entry, now)

    def test_fresh_failed(self):
        now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
        entry = {"ok": False, "checked": "2026-09-06T11:00:00Z"}
        assert model_availability.is_cache_fresh(entry, now)

    def test_expired_failed(self):
        now = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)
        entry = {"ok": False, "checked": "2026-09-06T11:00:00Z"}
        assert not model_availability.is_cache_fresh(entry, now)

    def test_missing_or_malformed_entry(self):
        now = datetime(2026, 9, 6, 12, 0, tzinfo=timezone.utc)
        assert not model_availability.is_cache_fresh(None, now)
        assert not model_availability.is_cache_fresh({"ok": "yes"}, now)
        assert not model_availability.is_cache_fresh({"ok": True}, now)


class TestMergeResults:
    def test_merges_and_overwrites(self):
        cache = {"opencode/a-free": {"ok": True, "checked": "old"}}
        results = {"opencode/a-free": False, "opencode-go-openai/glm-5.2": True}
        assert model_availability.merge_results(cache, results, "2026-09-06T12:00:00Z") == {
            "opencode/a-free": {"ok": False, "checked": "2026-09-06T12:00:00Z"},
            "opencode-go-openai/glm-5.2": {"ok": True, "checked": "2026-09-06T12:00:00Z"},
        }


class TestAvailableModels:
    def test_free_first_then_paid(self):
        cache = {
            "opencode-go-openai/glm-5.2": {"ok": True, "checked": "x"},
            "opencode/a-free": {"ok": True, "checked": "x"},
            "opencode/b-free": {"ok": False, "checked": "x"},
            "opencode-go-openai-2/glm-5.2": {"ok": True, "checked": "x"},
        }
        assert model_availability.available_models(
            cache, ["opencode/a-free", "opencode/b-free"], ["glm-5.2"]
        ) == [
            "opencode/a-free",
            "opencode-go-openai/glm-5.2",
            "opencode-go-openai-2/glm-5.2",
        ]


class TestReadCache:
    def test_reads_issue_body(self, monkeypatch):
        monkeypatch.setattr(
            model_availability,
            "run_gh",
            lambda *args: '{"opencode/a-free": {"ok": true, "checked": "x"}}',
        )
        assert model_availability.read_cache() == {
            "opencode/a-free": {"ok": True, "checked": "x"}
        }

    def test_returns_empty_on_failure(self, monkeypatch):
        def fail(*args):
            raise RuntimeError("gh failed")

        monkeypatch.setattr(model_availability, "run_gh", fail)
        assert model_availability.read_cache() == {}


class TestWriteCache:
    def test_writes_issue_body(self, monkeypatch):
        calls = []

        def fake_run_gh(*args):
            calls.append(args)

        monkeypatch.setattr(model_availability, "run_gh", fake_run_gh)
        model_availability.write_cache({"a": 1})
        assert calls == [("issue", "edit", "49", "--body", '{"a": 1}')]

    def test_swallows_failure(self, monkeypatch):
        def fail(*args):
            raise RuntimeError("gh failed")

        monkeypatch.setattr(model_availability, "run_gh", fail)
        model_availability.write_cache({"a": 1})