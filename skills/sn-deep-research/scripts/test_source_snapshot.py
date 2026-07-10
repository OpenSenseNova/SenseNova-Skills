#!/usr/bin/env python3
"""Deterministic tests for source snapshots and evidence integration."""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from source_snapshot import (
    SnapshotError,
    _atomic_install,
    contains_direct_quote,
    lookup_snapshots,
    normalize_url,
    parse_snapshot_ref,
    store_snapshot,
    verify_snapshot,
)
from validate_evidence import validate


class SourceSnapshotTests(unittest.TestCase):
    def test_url_normalization_is_conservative_and_stable(self):
        self.assertEqual(
            normalize_url("HTTPS://Example.COM:443/path?q=2&q=1#section"),
            "https://example.com/path?q=2&q=1",
        )
        self.assertEqual(normalize_url("http://example.com"), "http://example.com/")
        with self.assertRaises(SnapshotError):
            normalize_url("https://user:secret@example.com/private")

    def test_store_lookup_and_verify_exact_versions(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "source_cache"
            url = "HTTPS://Example.COM:443/report#top"
            first = store_snapshot(cache, url, "# Report\n\nRevenue rose 20%.\n")
            repeated = store_snapshot(cache, url, "# Report\n\nRevenue rose 20%.\n")
            second = store_snapshot(cache, url, "# Report\n\nRevenue rose 21%.\n")

            self.assertEqual(first["snapshot_ref"], repeated["snapshot_ref"])
            self.assertNotEqual(first["snapshot_ref"], second["snapshot_ref"])
            verified = verify_snapshot(cache, first["snapshot_ref"], url)
            self.assertEqual(verified["text"], "# Report\n\nRevenue rose 20%.\n")
            self.assertEqual(
                [item["snapshot_ref"] for item in lookup_snapshots(cache, url)],
                sorted([first["snapshot_ref"], second["snapshot_ref"]]),
            )

    def test_snapshot_ref_rejects_unsafe_or_noncanonical_paths(self):
        invalid_refs = [
            "../source_cache/a/b.md",
            "source_cache/../a.md",
            "source_cache/AA/BB.md",
            "source_cache/" + "a" * 64 + "/" + "b" * 64 + ".meta.json",
        ]
        for ref in invalid_refs:
            with self.subTest(ref=ref), self.assertRaises(SnapshotError):
                parse_snapshot_ref(ref)

    def test_cache_root_must_not_be_a_symlink(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            outside = root / "outside"
            outside.mkdir()
            cache_link = root / "source_cache"
            cache_link.symlink_to(outside, target_is_directory=True)
            with self.assertRaisesRegex(SnapshotError, "real directory"):
                store_snapshot(cache_link, "https://example.com/a", "content")

    def test_atomic_install_never_replaces_different_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir) / "immutable.md"
            _atomic_install(target, b"first")
            _atomic_install(target, b"first")
            with self.assertRaises(SnapshotError):
                _atomic_install(target, b"second")
            self.assertEqual(target.read_bytes(), b"first")

    def test_verify_detects_tampered_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "source_cache"
            stored = store_snapshot(cache, "https://example.com/a", "original")
            url_digest, content_digest = parse_snapshot_ref(stored["snapshot_ref"])
            (cache / url_digest / f"{content_digest}.md").write_text(
                "changed", encoding="utf-8"
            )
            with self.assertRaisesRegex(SnapshotError, "content hash"):
                verify_snapshot(cache, stored["snapshot_ref"])

    def test_verify_detects_tampered_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            cache = Path(temp_dir) / "source_cache"
            stored = store_snapshot(cache, "https://example.com/a", "original")
            url_digest, content_digest = parse_snapshot_ref(stored["snapshot_ref"])
            meta_path = cache / url_digest / f"{content_digest}.meta.json"
            metadata = json.loads(meta_path.read_text(encoding="utf-8"))
            metadata["normalized_url"] = "https://example.com/other"
            meta_path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(SnapshotError, "URL hash"):
                verify_snapshot(cache, stored["snapshot_ref"])

    def test_direct_quote_only_normalizes_unicode_whitespace(self):
        body = "The reported\nvalue was 42 percent."
        self.assertTrue(contains_direct_quote(body, "reported value was 42 percent"))
        self.assertFalse(contains_direct_quote(body, "reported value was about 42 percent"))


class EvidenceSnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache = Path(self.temp_dir.name) / "source_cache"
        self.url = "https://example.com/report"
        self.snapshot = store_snapshot(
            self.cache,
            self.url,
            "# Report\n\nThe measured value was\n42 percent in 2024.\n",
        )
        self.evidence = {
            "schema_version": "1.2",
            "mode": "initial",
            "dimension_id": "d1",
            "upstream_usage": [],
            "headline": "该指标在 2024 年达到 42%",
            "key_findings": [
                {"finding": "该指标在 2024 年达到 42%，有原始报告支持", "claim_ids": ["d1.c1"]},
                {"finding": "固定来源快照可以复核该指标的原始口径", "claim_ids": ["d1.c1"]},
            ],
            "claims": [{
                "id": "d1.c1",
                "text": "该指标在 2024 年达到 42%",
                "kind": "factual",
                "polarity": "neutral",
                "topic_tag": "measured_value",
                "answers_key_question": "kq1",
                "evidence": [{
                    "source_id": "official_report",
                    "snippet": "The measured value was 42 percent in 2024.",
                    "quote_type": "direct",
                    "snapshot_ref": self.snapshot["snapshot_ref"],
                }],
            }],
            "sources": [{
                "id": "official_report",
                "url": self.url,
                "title": "Official report",
                "quality": "primary",
                "published_at": "2024",
            }],
        }

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_v12_verifies_snapshot_and_direct_quote(self):
        self.assertEqual(validate(self.evidence, self.cache), [])

    def test_validator_cli_accepts_source_cache(self):
        evidence_path = Path(self.temp_dir.name) / "d1.evidence.json"
        evidence_path.write_text(
            json.dumps(self.evidence, ensure_ascii=False), encoding="utf-8"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("validate_evidence.py")),
                str(evidence_path),
                "--source-cache",
                str(self.cache),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["stats"]["source_cache_verified"])

    def test_validator_cli_checks_plan_contract(self):
        evidence_path = Path(self.temp_dir.name) / "d1.evidence.json"
        plan_path = Path(self.temp_dir.name) / "plan.json"
        evidence_path.write_text(
            json.dumps(self.evidence, ensure_ascii=False), encoding="utf-8"
        )
        plan_path.write_text(json.dumps({
            "dimensions": [{"id": "d1", "dependency_inputs": []}],
        }), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("validate_evidence.py")),
                str(evidence_path),
                "--source-cache",
                str(self.cache),
                "--require-version",
                "1.2",
                "--expected-mode",
                "initial",
                "--plan",
                str(plan_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["stats"]["plan_contract_verified"])

    def test_validator_cli_checks_upstream_claim_existence(self):
        evidence_path = Path(self.temp_dir.name) / "d1.evidence.json"
        plan_path = Path(self.temp_dir.name) / "plan.json"
        upstream_path = Path(self.temp_dir.name) / "d2.evidence.json"
        data = copy.deepcopy(self.evidence)
        data["upstream_usage"] = [{
            "dimension_id": "d2",
            "needed_for": "entity_selection",
            "consumed_claim_ids": ["d2.c1"],
            "scope_changes": ["只检索上游已确认的对象"],
            "skipped_searches": ["不再重复搜索候选对象"],
        }]
        evidence_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        plan_path.write_text(json.dumps({
            "dimensions": [{"id": "d1", "dependency_inputs": [{
                "dimension_id": "d2",
                "needed_for": "entity_selection",
            }]}],
        }), encoding="utf-8")
        upstream_path.write_text(json.dumps({
            "dimension_id": "d2",
            "claims": [{"id": "d2.c1"}],
            "key_findings": [{"claim_ids": ["d2.c1"]}],
        }), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).with_name("validate_evidence.py")),
                str(evidence_path),
                "--source-cache",
                str(self.cache),
                "--require-version",
                "1.2",
                "--expected-mode",
                "initial",
                "--plan",
                str(plan_path),
                "--upstream-evidence",
                str(upstream_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["stats"]["upstream_evidence_verified"])

    def test_v12_rejects_missing_snapshot_ref(self):
        data = copy.deepcopy(self.evidence)
        del data["claims"][0]["evidence"][0]["snapshot_ref"]
        self.assertIn("V034", {error["rule"] for error in validate(data, self.cache)})

    def test_v12_requires_source_cache_verification(self):
        self.assertIn("V037", {error["rule"] for error in validate(self.evidence)})

    def test_v12_requires_upstream_usage(self):
        data = copy.deepcopy(self.evidence)
        del data["upstream_usage"]
        self.assertIn("V007", {error["rule"] for error in validate(data, self.cache)})

    def test_writing_context_requires_writer_usable_fields(self):
        data = copy.deepcopy(self.evidence)
        data["writing_context"] = [{"id": "d1.w1"}]
        rules = {error["rule"] for error in validate(data, self.cache)}
        self.assertTrue({"V062", "V063", "V064"}.issubset(rules))

    def test_quick_accepts_one_key_finding_without_meta_padding(self):
        data = copy.deepcopy(self.evidence)
        data["mode"] = "quick"
        data["key_findings"] = data["key_findings"][:1]
        self.assertEqual(validate(data, self.cache, expected_mode="quick"), [])

    def test_initial_still_requires_two_key_findings(self):
        data = copy.deepcopy(self.evidence)
        data["key_findings"] = data["key_findings"][:1]
        self.assertIn("V006", {error["rule"] for error in validate(data, self.cache)})

    def test_expected_mode_blocks_quick_validation_downgrade(self):
        data = copy.deepcopy(self.evidence)
        data["mode"] = "quick"
        self.assertIn(
            "V009",
            {error["rule"] for error in validate(data, self.cache, expected_mode="initial")},
        )

    def test_plan_contract_rejects_mode_quick(self):
        data = copy.deepcopy(self.evidence)
        data["mode"] = "quick"
        plan = {"dimensions": [{"id": "d1", "dependency_inputs": []}]}
        self.assertIn(
            "V009",
            {error["rule"] for error in validate(data, self.cache, plan)},
        )

    def test_v12_validates_upstream_usage_contract(self):
        data = copy.deepcopy(self.evidence)
        data["upstream_usage"] = [{
            "dimension_id": "d2",
            "needed_for": "entity_selection",
            "consumed_claim_ids": ["d2.c1"],
            "scope_changes": ["只检索上游已确认的对象"],
            "skipped_searches": ["不再重复搜索候选对象"],
        }]
        self.assertEqual(validate(data, self.cache), [])

    def test_v12_rejects_incomplete_upstream_usage(self):
        data = copy.deepcopy(self.evidence)
        data["upstream_usage"] = [{
            "dimension_id": "d2",
            "needed_for": "summary",
            "consumed_claim_ids": ["d3.c1"],
            "scope_changes": [],
            "skipped_searches": [],
        }]
        rules = {error["rule"] for error in validate(data, self.cache)}
        self.assertIn("V007", rules)

    def test_plan_dependency_inputs_must_match_upstream_usage(self):
        plan = {
            "dimensions": [{"id": "d1", "dependency_inputs": [{
                "dimension_id": "d2",
                "needed_for": "entity_selection",
            }]}]
        }
        self.assertIn(
            "V008",
            {error["rule"] for error in validate(self.evidence, self.cache, plan)},
        )
        data = copy.deepcopy(self.evidence)
        data["upstream_usage"] = [{
            "dimension_id": "d2",
            "needed_for": "entity_selection",
            "consumed_claim_ids": ["d2.c1"],
            "scope_changes": ["只检索上游已确认的对象"],
            "skipped_searches": ["不再重复搜索候选对象"],
        }]
        upstream = {
            "dimension_id": "d2",
            "claims": [{"id": "d2.c1"}],
            "key_findings": [{"claim_ids": ["d2.c1"]}],
        }
        self.assertEqual(
            validate(data, self.cache, plan, upstream_evidence_data=[upstream]),
            [],
        )

    def test_consumed_claim_must_exist_in_upstream_key_findings(self):
        data = copy.deepcopy(self.evidence)
        data["upstream_usage"] = [{
            "dimension_id": "d2",
            "needed_for": "entity_selection",
            "consumed_claim_ids": ["d2.c999"],
            "scope_changes": ["只检索上游已确认的对象"],
            "skipped_searches": ["不再重复搜索候选对象"],
        }]
        plan = {"dimensions": [{"id": "d1", "dependency_inputs": [{
            "dimension_id": "d2",
            "needed_for": "entity_selection",
        }]}]}
        upstream = {
            "dimension_id": "d2",
            "claims": [{"id": "d2.c1"}],
            "key_findings": [{"claim_ids": ["d2.c1"]}],
        }
        errors = validate(
            data,
            self.cache,
            plan,
            upstream_evidence_data=[upstream],
        )
        self.assertIn("V008", {error["rule"] for error in errors})

    def test_v12_rejects_direct_quote_not_in_snapshot(self):
        data = copy.deepcopy(self.evidence)
        data["claims"][0]["evidence"][0]["snippet"] = "The measured value was 43 percent."
        self.assertIn("V036", {error["rule"] for error in validate(data, self.cache)})

    def test_v12_rejects_numeric_snippet_not_in_snapshot(self):
        data = copy.deepcopy(self.evidence)
        item = data["claims"][0]["evidence"][0]
        item["quote_type"] = "numeric"
        item["snippet"] = "43 percent"
        self.assertIn("V036", {error["rule"] for error in validate(data, self.cache)})

    def test_v12_rejects_snapshot_from_another_url(self):
        data = copy.deepcopy(self.evidence)
        data["sources"][0]["url"] = "https://example.com/other"
        self.assertIn("V035", {error["rule"] for error in validate(data, self.cache)})

    def test_v11_remains_backward_compatible(self):
        data = copy.deepcopy(self.evidence)
        data["schema_version"] = "1.1"
        del data["claims"][0]["evidence"][0]["snapshot_ref"]
        self.assertEqual(validate(data, self.cache), [])

    def test_new_controller_rejects_v11_compatibility_mode(self):
        data = copy.deepcopy(self.evidence)
        data["schema_version"] = "1.1"
        del data["claims"][0]["evidence"][0]["snapshot_ref"]
        self.assertIn(
            "V001",
            {error["rule"] for error in validate(
                data,
                self.cache,
                expected_mode="initial",
                required_version="1.2",
            )},
        )


if __name__ == "__main__":
    unittest.main()
