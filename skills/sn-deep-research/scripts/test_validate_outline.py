#!/usr/bin/env python3
"""Deterministic tests for the outline v2 cross-file hard gates."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("validate_outline.py")
SPEC = importlib.util.spec_from_file_location("validate_outline", SCRIPT_PATH)
VALIDATOR = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(VALIDATOR)


def make_outline(*, strength="auto", requested_type=None, primary_type="checklist"):
    resolution = {
        "auto": "auto_selected",
        "required": "required_honored",
        "preferred": "preferred_honored",
    }[strength]
    return {
        "schema_version": "2.0",
        "paradigm": {"main": "evaluation", "secondary": None},
        "depth_level": "overview",
        "global_arc": "a" * 40,
        "organization_decision": {
            "reader_task": "r" * 10,
            "primary_unit_type": primary_type,
            "supporting_unit_types": [],
            "opening_summary": "none",
            "toc": False,
            "numbered_headings": False,
            "preference": {
                "requested_type": requested_type,
                "custom_type": None,
                "strength": strength,
                "resolution": resolution,
                "adaptation_reason": None,
            },
            "evidence_fit": "e" * 20,
        },
        "L0_draft": None,
        "style_contract": {
            "register": "research_brief",
            "voice": "neutral_analytical",
            "terminology": {"preferred": {}},
            "citation_style": "footnote",
        },
        "content_units": [
            {
                "id": "u1",
                "type": primary_type,
                "role": "primary",
                "title": "Unit",
                "reader_task": "t" * 10,
                "word_budget": 100,
                "lead": None,
                "render_contract": {
                    "mode": "checklist",
                    "show_heading": True,
                    "schema": ["Item", "State"],
                    "instructions": "i" * 10,
                },
                "elements": [
                    {
                        "id": "e1",
                        "label": "Item",
                        "purpose": "p" * 10,
                        "evidence_refs": [
                            {"claim_id": "d1.c1", "role": "primary_support"}
                        ],
                        "writing_context_refs": [],
                    }
                ],
                "evidence_subset": ["d1.c1"],
            }
        ],
        "claim_routing_table": {
            "d1.c1": {"primary": "u1", "secondary": []}
        },
        "scan_summary": {
            "totals": {"claims": 1, "sources": 1, "primary_ratio": 1.0},
            "topic_clusters": [],
            "conflicts": [],
            "key_entities": [],
            "timeline_density": [],
            "gaps": [],
            "reader_task_signal": {
                "panorama": 0.0,
                "comparison": 0.0,
                "investigation": 0.0,
                "timeline": 0.0,
                "evaluation": 1.0,
                "forecast": 0.0,
            },
        },
    }


def make_format(*, strength="auto", requested_type=None):
    return {
        "container": "markdown",
        "selected_format": {"id": "research_report"},
        "structure_preference": {
            "requested_type": requested_type,
            "custom_type": None,
            "strength": strength,
            "notes": "test",
        },
        "confirmed_by_user": True,
    }


def make_claim():
    return {
        "id": "d1.c1",
        "text": "A source-backed claim",
        "kind": "factual",
        "polarity": "neutral",
        "topic_tag": "test_topic",
        "answers_key_question": "kq1",
        "evidence": [
            {
                "source_id": "source_a",
                "snippet": "verbatim evidence",
                "quote_type": "direct",
                "snapshot_ref": "source_cache/url_hash/content_hash.md",
            }
        ],
    }


def make_context():
    return {
        "id": "d1.w1",
        "kind": "availability_gap",
        "text": "No public data covers the requested interval.",
        "source_ids": ["source_a"],
        "applies_to": ["kq1"],
        "use": "State the public-data limitation.",
    }


def make_subset(*, context=None):
    claim = copy.deepcopy(make_claim())
    claim["narrative_role"] = "primary_support"
    return {
        "schema_version": "2.0",
        "content_unit_id": "u1",
        "claims": [claim],
        "writing_context": [] if context is None else [copy.deepcopy(context)],
        "sources": [{"id": "source_a"}],
    }


def rules(errors):
    return {error["rule"] for error in errors}


class FormatContractTests(unittest.TestCase):
    def test_cli_required_version_rejects_other_schema(self):
        outline = make_outline()
        with tempfile.TemporaryDirectory() as temp_dir:
            outline_path = Path(temp_dir) / "outline.json"
            outline_path.write_text(json.dumps(outline), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(outline_path),
                    "--require-version",
                    "1.0",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("O002", rules(payload["errors"]))

    def test_exact_format_preference_passes(self):
        outline = make_outline(
            strength="required",
            requested_type="checklist",
            primary_type="checklist",
        )
        self.assertEqual(
            VALIDATOR.validate_format_contract(
                outline,
                make_format(strength="required", requested_type="checklist"),
            ),
            [],
        )

    def test_cli_format_mismatch_fails(self):
        outline = make_outline()
        format_data = make_format(strength="required", requested_type="matrix")
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            outline_path = temp_path / "outline.json"
            format_path = temp_path / "format.json"
            outline_path.write_text(json.dumps(outline), encoding="utf-8")
            format_path.write_text(json.dumps(format_data), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(outline_path), "--format", str(format_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 1)
        self.assertIn("U112", rules(payload["errors"]))
        self.assertIn("U113", rules(payload["errors"]))


class OutlineStructureTests(unittest.TestCase):
    def test_numbered_headings_require_numbered_unit_titles(self):
        outline = make_outline()
        outline["organization_decision"]["numbered_headings"] = True
        errors, _ = VALIDATOR.validate_outline(outline)
        self.assertIn("U075", rules(errors))
        outline["content_units"][0]["title"] = "1. Unit"
        errors, _ = VALIDATOR.validate_outline(outline)
        self.assertNotIn("U075", rules(errors))

    def test_required_structure_rejects_another_primary_type(self):
        outline = make_outline(
            strength="required",
            requested_type="checklist",
            primary_type="checklist",
        )
        second_unit = copy.deepcopy(outline["content_units"][0])
        second_unit.update({"id": "u2", "type": "narrative", "title": "Other"})
        second_unit["elements"][0]["evidence_refs"][0]["role"] = "supporting_context"
        outline["content_units"].append(second_unit)
        outline["claim_routing_table"]["d1.c1"]["secondary"] = [
            {"unit": "u2", "role": "supporting_context"}
        ]

        errors, _ = VALIDATOR.validate_outline(outline)
        self.assertIn("U074", rules(errors))

    def test_auto_structure_rejects_another_primary_type(self):
        outline = make_outline()
        second_unit = copy.deepcopy(outline["content_units"][0])
        second_unit.update({"id": "u2", "type": "narrative", "title": "Other"})
        second_unit["elements"][0]["evidence_refs"][0]["role"] = "supporting_context"
        outline["content_units"].append(second_unit)
        outline["claim_routing_table"]["d1.c1"]["secondary"] = [
            {"unit": "u2", "role": "supporting_context"}
        ]
        errors, _ = VALIDATOR.validate_outline(outline)
        self.assertIn("U074", rules(errors))

    def test_gap_only_unit_uses_routed_writing_context(self):
        outline = make_outline()
        element = outline["content_units"][0]["elements"][0]
        element["evidence_refs"] = []
        element["writing_context_refs"] = ["d1.w1"]
        outline["content_units"][0]["evidence_subset"] = []
        outline["claim_routing_table"] = {}
        errors, _ = VALIDATOR.validate_outline(outline)
        self.assertEqual(errors, [])

        subset = make_subset(context=make_context())
        subset["claims"] = []
        subset_errors = VALIDATOR.validate_subset(
            subset,
            outline,
            {},
            {"d1.w1": make_context()},
        )
        self.assertEqual(subset_errors, [])


class SubsetCoverageTests(unittest.TestCase):
    def run_cli(self, outline, subset_payloads):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            outline_path = temp_path / "outline.json"
            subsets_path = temp_path / "content_units"
            subsets_path.mkdir()
            outline_path.write_text(json.dumps(outline), encoding="utf-8")
            for filename, payload in subset_payloads.items():
                (subsets_path / filename).write_text(json.dumps(payload), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), str(outline_path), "--subsets", str(subsets_path)],
                check=False,
                capture_output=True,
                text=True,
            )
        return result, json.loads(result.stdout)

    def test_empty_subset_directory_fails(self):
        result, payload = self.run_cli(make_outline(), {})
        self.assertEqual(result.returncode, 1)
        self.assertIn("U200", rules(payload["errors"]))

    def test_duplicate_subset_for_one_unit_fails(self):
        subset = make_subset()
        result, payload = self.run_cli(
            make_outline(),
            {
                "u1.evidence_subset.json": subset,
                "u1-copy.evidence_subset.json": subset,
            },
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("U200", rules(payload["errors"]))

    def test_subset_filename_must_match_content_unit_id(self):
        result, payload = self.run_cli(
            make_outline(),
            {"wrong.evidence_subset.json": make_subset()},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("U200", rules(payload["errors"]))

    def test_exactly_one_subset_passes(self):
        result, payload = self.run_cli(
            make_outline(),
            {"u1.evidence_subset.json": make_subset()},
        )
        self.assertEqual(result.returncode, 0)
        self.assertTrue(payload["ok"])

    def test_full_cli_contract_passes(self):
        outline = make_outline()
        outline["content_units"][0]["elements"][0]["writing_context_refs"] = ["d1.w1"]
        context = make_context()
        evidence = {
            "claims": [make_claim()],
            "writing_context": [context],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            subsets_path = temp_path / "content_units"
            subsets_path.mkdir()
            paths = {
                "outline": temp_path / "outline.json",
                "format": temp_path / "format.json",
                "subset": subsets_path / "u1.evidence_subset.json",
                "evidence": temp_path / "d1.evidence.json",
            }
            payloads = {
                "outline": outline,
                "format": make_format(),
                "subset": make_subset(context=context),
                "evidence": evidence,
            }
            for name, path in paths.items():
                path.write_text(json.dumps(payloads[name]), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT_PATH),
                    str(paths["outline"]),
                    "--format",
                    str(paths["format"]),
                    "--subsets",
                    str(subsets_path),
                    "--evidence",
                    str(paths["evidence"]),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        payload = json.loads(result.stdout)
        self.assertEqual(result.returncode, 0, payload)
        self.assertTrue(payload["ok"])


class EvidenceBoundaryTests(unittest.TestCase):
    def validate(self, subset, evidence_index=None, context_index=None, outline=None):
        return VALIDATOR.validate_subset(
            subset,
            outline or make_outline(),
            evidence_index,
            context_index,
        )

    def test_unknown_claim_fails_when_evidence_index_is_supplied(self):
        self.assertIn("U212", rules(self.validate(make_subset(), evidence_index={})))

    def test_non_object_evidence_fails(self):
        subset = make_subset()
        subset["claims"][0]["evidence"] = ["not-an-object"]
        errors = self.validate(subset, evidence_index={"d1.c1": make_claim()})
        self.assertIn("U212", rules(errors))

    def test_each_evidence_field_is_immutable(self):
        for field, replacement in (
            ("source_id", "source_b"),
            ("snippet", "rewritten"),
            ("quote_type", "paraphrase"),
            ("snapshot_ref", "source_cache/other/version.md"),
        ):
            with self.subTest(field=field):
                subset = make_subset()
                subset["claims"][0]["evidence"][0][field] = replacement
                errors = self.validate(subset, evidence_index={"d1.c1": make_claim()})
                self.assertIn("U212", rules(errors))

    def test_missing_snapshot_ref_fails(self):
        subset = make_subset()
        del subset["claims"][0]["evidence"][0]["snapshot_ref"]
        errors = self.validate(subset, evidence_index={"d1.c1": make_claim()})
        self.assertIn("U212", rules(errors))

    def test_non_evidence_claim_field_is_immutable(self):
        subset = make_subset()
        subset["claims"][0]["answers_key_question"] = "kq2"
        errors = self.validate(subset, evidence_index={"d1.c1": make_claim()})
        self.assertIn("U212", rules(errors))

    def test_exact_claim_copy_passes(self):
        errors = self.validate(make_subset(), evidence_index={"d1.c1": make_claim()})
        self.assertEqual(errors, [])


class WritingContextBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.outline = make_outline()
        self.outline["content_units"][0]["elements"][0]["writing_context_refs"] = ["d1.w1"]
        self.claim_index = {"d1.c1": make_claim()}
        self.context = make_context()

    def validate(self, subset, context_index):
        return VALIDATOR.validate_subset(
            subset,
            self.outline,
            self.claim_index,
            context_index,
        )

    def test_exact_routed_context_passes(self):
        errors = self.validate(
            make_subset(context=self.context),
            {"d1.w1": self.context},
        )
        self.assertEqual(errors, [])

    def test_missing_routed_context_fails(self):
        errors = self.validate(make_subset(), {"d1.w1": self.context})
        self.assertIn("U215", rules(errors))

    def test_unrouted_extra_context_fails(self):
        outline = make_outline()
        errors = VALIDATOR.validate_subset(
            make_subset(context=self.context),
            outline,
            self.claim_index,
            {"d1.w1": self.context},
        )
        self.assertIn("U215", rules(errors))

    def test_modified_context_fails(self):
        modified = copy.deepcopy(self.context)
        modified["text"] = "Changed boundary text"
        errors = self.validate(make_subset(context=modified), {"d1.w1": self.context})
        self.assertIn("U216", rules(errors))

    def test_unknown_context_fails(self):
        errors = self.validate(make_subset(context=self.context), {})
        self.assertIn("U216", rules(errors))


if __name__ == "__main__":
    unittest.main()
